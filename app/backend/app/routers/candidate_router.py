import asyncio
import io

import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_candidate
from app.claude_client import (
    ClaudeConfigError,
    ClaudeEmpty,
    ClaudeRefusal,
    ClaudeTruncated,
    ClaudeUnavailable,
)
from app.claude_service import EmptyReply, chat_with_claude
from app.database import get_db
from app.discovery_writer import write_discovery_md
from app.models import Message, Session, User
from app.prompts import build_system_prompt, get_available_profiles, get_profile_metadata
from app.session_state import extract_resume, validate_updates
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
_UNAVAILABLE_MSG = "The interviewer didn't respond. Your answer is saved; tap Try again."


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
    except (ClaudeUnavailable, ClaudeTruncated, ClaudeEmpty, EmptyReply) as exc:
        logger.warning("session=%s model call failed: %s", sid, type(exc).__name__)
        await _end_turn(db, sid, user_msg_id, now, status="failed")
        return _json(503, "model_unavailable", _UNAVAILABLE_MSG)
    except ClaudeRefusal:
        logger.warning("session=%s model refused", sid)
        await _end_turn(db, sid, user_msg_id, now, status="failed")
        return _json(
            422,
            "model_refused",
            "The interviewer couldn't answer that message. Try rephrasing it, then tap Try again.",
        )
    except ClaudeConfigError:
        await _end_turn(db, sid, user_msg_id, now, status="failed")
        return _json(503, "model_unavailable", "The interviewer is unavailable right now.")
    except Exception as exc:
        logger.error("session=%s model call failed unexpectedly: %s", sid, type(exc).__name__)
        await _end_turn(db, sid, user_msg_id, now, status="failed")
        return _json(503, "model_unavailable", _UNAVAILABLE_MSG)

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

    # RESUME block: strip the markers from what is stored (the text stays), and offer
    # the draft to the validator, which only takes it in phase 3.
    clean_text, resume_draft = extract_resume(clean_text)
    accepted, _rejected = validate_updates(
        session, metas, available_profiles=get_available_profiles(), resume_draft=resume_draft
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


MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_PDF_PAGES = 30
MAX_TEXT_CHARS = 50_000
MAX_DOCX_ENTRIES = 200
MAX_DOCX_TOTAL = 30 * 1024 * 1024
MAX_DOCX_ENTRY = 20 * 1024 * 1024
PARSE_TIMEOUT = 20


class UploadRejected(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message


_NO_TEXT = (
    "We couldn't find any text in this file. It may be a scanned image. "
    "Upload a text-based PDF or a Word file, or skip the upload."
)
_BAD_CONTENT = "That file doesn't look like a {kind}. Upload a PDF, DOCX, or TXT file."


def _extract_pdf(content: bytes) -> str:
    from pypdf import PdfReader

    if not content.startswith(b"%PDF-"):
        raise UploadRejected(415, _BAD_CONTENT.format(kind="PDF"))
    try:
        reader = PdfReader(io.BytesIO(content))
        if reader.is_encrypted:
            raise UploadRejected(
                422,
                "This PDF is password-protected. Remove the password or upload a DOCX.",
            )
        if len(reader.pages) > MAX_PDF_PAGES:
            raise UploadRejected(
                422, f"That PDF has more than {MAX_PDF_PAGES} pages. Upload a shorter resume."
            )
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except UploadRejected:
        raise
    except Exception:
        raise UploadRejected(422, "We couldn't read that PDF. Try a DOCX or skip the upload.")


def _extract_docx(content: bytes) -> str:
    import zipfile

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile:
        raise UploadRejected(415, _BAD_CONTENT.format(kind="Word document"))
    with zf:
        infos = zf.infolist()
        if "word/document.xml" not in {i.filename for i in infos}:
            raise UploadRejected(415, _BAD_CONTENT.format(kind="Word document"))
        if (
            len(infos) > MAX_DOCX_ENTRIES
            or sum(i.file_size for i in infos) > MAX_DOCX_TOTAL
            or any(i.file_size > MAX_DOCX_ENTRY for i in infos)
        ):
            raise UploadRejected(422, "That Word file is too large or complex to read.")
    try:
        import docx

        doc = docx.Document(io.BytesIO(content))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                seen = set()
                for cell in row.cells:
                    if id(cell._tc) in seen:
                        continue
                    seen.add(id(cell._tc))
                    parts.append(cell.text)
        return "\n".join(parts)
    except Exception:
        raise UploadRejected(422, "We couldn't read that Word file. Try a PDF or skip the upload.")


def _extract_txt(content: bytes) -> str:
    if b"\x00" in content:
        raise UploadRejected(415, _BAD_CONTENT.format(kind="text file"))
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise UploadRejected(415, _BAD_CONTENT.format(kind="text file"))


@router.post("/resume", response_model=SessionResponse)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    """Accept a resume file (PDF, DOCX, or TXT) and store extracted text on the session."""
    chunks: list[bytes] = []
    size = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            return _json(413, "file_too_large", "That file is larger than 5 MB.")
        chunks.append(chunk)
    content = b"".join(chunks)
    filename = (file.filename or "").lower()

    if filename.endswith(".pdf"):
        extractor = _extract_pdf
    elif filename.endswith(".docx"):
        extractor = _extract_docx
    elif filename.endswith(".txt") or (
        "." not in filename and file.content_type in ("text/plain", "application/octet-stream")
    ):
        extractor = _extract_txt
    else:
        return _json(415, "unsupported_type", "Unsupported file type. Upload a PDF, DOCX, or TXT file.")

    try:
        text = await asyncio.wait_for(asyncio.to_thread(extractor, content), PARSE_TIMEOUT)
    except UploadRejected as rej:
        return _json(rej.status, "upload_rejected", rej.message)
    except asyncio.TimeoutError:
        return _json(422, "upload_timeout", "That file took too long to read. Try a simpler file or skip the upload.")
    except Exception:
        return _json(422, "upload_unreadable", "We couldn't read that file. Try another format or skip the upload.")

    text = text.strip()
    if not text:
        return _json(422, "no_text", _NO_TEXT)
    if len(text) > MAX_TEXT_CHARS:
        return _json(422, "text_too_long", "That resume has too much text (over 50,000 characters). Upload a shorter version.")

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
