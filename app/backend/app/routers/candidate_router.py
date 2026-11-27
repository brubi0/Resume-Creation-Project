import io

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_candidate
from app.claude_service import chat_with_claude
from app.database import get_db
from app.discovery_writer import write_discovery_md
from app.models import Message, Session, User
from app.prompts import build_system_prompt, get_available_profiles, get_profile_metadata
from app.session_state import validate_updates
from app.schemas import (
    ChatStatusResponse,
    JobDescriptionUpdate,
    MessageResponse,
    MessageSend,
    NewSessionRequest,
    ProfileItem,
    ProfileSelect,
    SessionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


_ADVISORY_LOCK_SQL = text("SELECT pg_advisory_xact_lock(hashtext(:key))")
TURN_STALE_AFTER = timedelta(minutes=3)


def _current_query(user: User):
    # "Current" = newest non-abandoned session; history is never deleted.
    # A candidate can have several non-abandoned sessions (completed ones are
    # kept when a new interview starts), so take the newest, not "exactly one".
    return (
        select(Session)
        .where(Session.user_id == user.id, Session.status != "abandoned")
        .order_by(Session.created_at.desc(), Session.id.desc())
        .limit(1)
    )


async def _latest_session(user: User, db: AsyncSession) -> Session | None:
    result = await db.execute(_current_query(user))
    return result.scalars().first()


async def _lock_and_load_current(user: User, db: AsyncSession) -> Session | None:
    """The one place session creation/replacement serializes (per user).

    Takes the transaction-scoped advisory lock (released by commit/rollback),
    then loads the current session FOR UPDATE.
    """
    await db.execute(_ADVISORY_LOCK_SQL, {"key": f"session:{user.id}"})
    result = await db.execute(
        _current_query(user).with_for_update().execution_options(populate_existing=True)
    )
    return result.scalars().first()


async def get_or_create_session(user: User, db: AsyncSession) -> Session:
    session = await _latest_session(user, db)
    if session:
        return session

    # The chat page loads the session and messages in parallel on first visit, so
    # two requests can both find nothing. Only the create path takes the lock, so
    # normal reads never wait on it.
    session = await _lock_and_load_current(user, db)
    if not session:
        session = Session(user_id=user.id)
        db.add(session)
    await db.commit()  # releases the lock
    await db.refresh(session)
    return session


def _bump(session: Session) -> None:
    session.version = (session.version or 0) + 1


def _json(status: int, code: str, message: str) -> JSONResponse:
    # "detail" keeps the current frontend's generic error display working.
    return JSONResponse(
        status_code=status, content={"code": code, "message": message, "detail": message}
    )


@router.get("/session", response_model=SessionResponse)
async def get_session(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    session = await get_or_create_session(user, db)
    return session


@router.get("/messages", response_model=list[MessageResponse])
async def get_messages(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    session = await get_or_create_session(user, db)
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()


async def _lock_session_row(db: AsyncSession, session_id) -> Session:
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    return result.scalar_one()


def _owns_turn(session: Session, msg: Message | None, claimed_at: datetime) -> bool:
    """True while this request still holds the turn it claimed in Tx A.

    A turn older than TURN_STALE_AFTER can be taken over by a newer send (e.g. a
    retry while a slow model call is still running). The newer send marks our
    message failed and re-stamps turn_started_at, so a late reply must not apply
    its updates or release the newer turn.
    """
    return (
        msg is not None
        and msg.status == "pending"
        and session.turn_state == "pending"
        and session.turn_started_at == claimed_at
    )


async def _end_turn(
    db: AsyncSession, session_id, user_msg_id, claimed_at: datetime, *, status: str
) -> None:
    """Tx C / failed-B: mark the user's message and release the turn. Keeps the answer."""
    session = await _lock_session_row(db, session_id)
    msg = await db.get(Message, user_msg_id, populate_existing=True)
    if _owns_turn(session, msg, claimed_at):
        msg.status = status
        session.turn_state = "idle"
        session.turn_started_at = None
        _bump(session)
    await db.commit()


@router.post("/send", response_model=MessageResponse)
async def send_message(
    body: MessageSend,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    # ---- Tx A (short): claim the turn under a row lock -------------------
    await get_or_create_session(user, db)  # ensures one exists (advisory-locked)
    result = await db.execute(
        _current_query(user).with_for_update().execution_options(populate_existing=True)
    )
    session = result.scalars().first()
    if session is None:  # replaced while we waited on the row lock
        await db.rollback()
        return _json(409, "session_replaced", "This interview was replaced. Reload to continue.")
    if body.session_id is not None and body.session_id != session.id:
        await db.rollback()
        return _json(409, "session_replaced", "This interview was replaced. Reload to continue.")
    if session.status not in ("active", "interview_complete"):
        await db.rollback()
        raise HTTPException(status_code=400, detail="Session is not active")

    now = datetime.now(timezone.utc)
    turn_fresh = (
        session.turn_state == "pending"
        and session.turn_started_at is not None
        and now - session.turn_started_at < TURN_STALE_AFTER
    )

    user_msg: Message | None = None
    if body.client_message_id is not None:
        user_msg = (
            await db.execute(
                select(Message).where(
                    Message.session_id == session.id,
                    Message.client_message_id == body.client_message_id,
                )
            )
        ).scalars().first()
        if user_msg is not None and user_msg.status == "ok":
            reply = (
                await db.execute(
                    select(Message)
                    .where(
                        Message.session_id == session.id,
                        Message.role == "assistant",
                        Message.created_at >= user_msg.created_at,
                    )
                    .order_by(Message.created_at.asc())
                    .limit(1)
                )
            ).scalars().first()
            if reply is not None:
                out = MessageResponse.model_validate(reply)
                await db.rollback()
                return out
    if turn_fresh:
        await db.rollback()
        return _json(409, "turn_in_progress", "A reply is still being written. Please wait.")

    if user_msg is not None:
        # failed (or stale pending) retry: reuse the row, no duplicate message
        user_msg.status = "pending"
        user_msg.created_at = datetime.utcnow()
        user_msg.phase = session.phase
    else:
        user_msg = Message(
            session_id=session.id,
            role="user",
            content=body.content,
            phase=session.phase,
            status="pending",
            client_message_id=body.client_message_id,
        )
        db.add(user_msg)
        await db.flush()
    # Any other leftover pending message is from a dead turn.
    await db.execute(
        update(Message)
        .where(
            Message.session_id == session.id,
            Message.status == "pending",
            Message.id != user_msg.id,
        )
        .values(status="failed")
    )
    session.turn_state = "pending"
    session.turn_started_at = now
    _bump(session)
    await db.flush()

    # Everything the model call needs, loaded before we let go of the connection.
    system_prompt = build_system_prompt(session)
    rows = (
        await db.execute(
            select(Message)
            .where(
                Message.session_id == session.id,
                (Message.status == "ok") | (Message.id == user_msg.id),
            )
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
    ).scalars().all()
    api_messages = [{"role": m.role, "content": m.content} for m in rows]
    sid, user_msg_id = session.id, user_msg.id
    await db.commit()

    # ---- Model call: no transaction, no lock ------------------------------
    try:
        clean_text, metas = await chat_with_claude(system_prompt, api_messages)
    except Exception as exc:  # Stage 4 maps provider errors precisely
        logger.warning("session=%s model call failed: %s", sid, type(exc).__name__)
        await _end_turn(db, sid, user_msg_id, now, status="failed")
        return _json(
            503,
            "model_unavailable",
            "The assistant couldn't reply just now. Your answer was saved; please try again.",
        )

    # ---- Tx B: re-lock, validate against the fresh row, apply -------------
    session = await _lock_session_row(db, sid)
    current = await _latest_session(user, db)
    if session.status == "abandoned" or current is None or current.id != sid:
        await _end_turn(db, sid, user_msg_id, now, status="failed")
        return _json(409, "session_replaced", "This interview was replaced. Reload to continue.")

    user_msg = await db.get(Message, user_msg_id, populate_existing=True)
    if not _owns_turn(session, user_msg, now):
        # A newer send took over this (stale) turn; drop this late reply.
        await db.rollback()
        return _json(409, "turn_in_progress", "A newer message took over. Please wait.")

    accepted, _rejected = validate_updates(
        session, metas, available_profiles=get_available_profiles()
    )
    assistant_msg = Message(
        session_id=sid,
        role="assistant",
        content=clean_text,
        phase=session.phase,
        status="ok",
    )
    db.add(assistant_msg)
    for key, value in accepted.items():
        setattr(session, key, value)
    user_msg.status = "ok"
    session.turn_state = "idle"
    session.turn_started_at = None
    _bump(session)
    await db.commit()
    await db.refresh(assistant_msg)

    # Write discovery.md to disk whenever discovery data or phase changed
    if "discovery_data" in accepted or "phase" in accepted:
        try:
            write_discovery_md(session)
        except Exception:
            pass  # non-fatal — DB is the source of truth

    return assistant_msg


@router.patch("/job-description", response_model=SessionResponse)
async def set_job_description(
    body: JobDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    session = await get_or_create_session(user, db)
    session.job_description = body.job_description
    _bump(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/new-session", response_model=SessionResponse)
async def start_new_session(
    body: NewSessionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    current = await _lock_and_load_current(user, db)
    replaces = body.replaces_session_id if body else None
    if replaces is not None and current is not None and current.id != replaces:
        # Another tab or a retry already replaced it: hand back the current one.
        await db.commit()
        return current

    if replaces is None:
        # Legacy behaviour: abandon every active session (completed ones stay).
        result = await db.execute(
            select(Session)
            .where(Session.user_id == user.id, Session.status == "active")
            .with_for_update()
        )
        for old in result.scalars().all():
            old.status = "abandoned"
            _bump(old)
    elif current is not None and current.status == "active":
        current.status = "abandoned"
        _bump(current)

    session = Session(user_id=user.id)
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/profiles", response_model=list[ProfileItem])
async def list_profiles(
    user: User = Depends(require_candidate),
):
    """Return all available role profiles for the candidate to choose from."""
    return get_profile_metadata()


@router.patch("/profile", response_model=SessionResponse)
async def select_profile(
    body: ProfileSelect,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """Set the profile on the session and advance to Phase 1, skipping Phase 0 conversation."""
    session = await get_or_create_session(user, db)
    session.profile_slug = body.profile_slug
    _bump(session)
    # Advance past Phase 0 — profile is already chosen
    if session.phase == 0:
        session.phase = 1
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/resume", response_model=SessionResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """Accept a resume file (PDF, DOCX, or TXT) and store extracted text on the session."""
    content = await file.read()
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        try:
            from pypdf import PdfReader

            reader = PdfReader(io.BytesIO(content))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not parse PDF: {exc}")
    elif filename.endswith(".docx"):
        try:
            import docx

            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not parse DOCX: {exc}")
    elif filename.endswith(".txt") or file.content_type in ("text/plain", "application/octet-stream"):
        try:
            text = content.decode("utf-8", errors="replace")
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"Could not decode file: {exc}")
    else:
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Upload a PDF, DOCX, or TXT file.",
        )

    text = text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="No text could be extracted from the file.")

    session = await get_or_create_session(user, db)
    session.resume_text = text
    _bump(session)
    await db.commit()
    await db.refresh(session)
    return session


@router.get("/status", response_model=ChatStatusResponse)
async def get_status(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    session = await get_or_create_session(user, db)
    return ChatStatusResponse(
        phase=session.phase,
        experience_level=session.experience_level,
        profile_slug=session.profile_slug,
        job_description=session.job_description,
        resume_text=session.resume_text,
        status=session.status,
    )
