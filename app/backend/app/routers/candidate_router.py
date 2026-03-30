import io

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_candidate
from app.claude_service import chat_with_claude
from app.database import get_db
from app.models import Message, Session, User
from app.schemas import (
    ChatStatusResponse,
    JobDescriptionUpdate,
    MessageResponse,
    MessageSend,
    SessionResponse,
)

router = APIRouter()


async def get_or_create_session(user: User, db: AsyncSession) -> Session:
    result = await db.execute(
        select(Session)
        .where(Session.user_id == user.id, Session.status != "abandoned")
        .order_by(Session.created_at.desc())
    )
    session = result.scalar_one_or_none()
    if not session:
        session = Session(user_id=user.id)
        db.add(session)
        await db.commit()
        await db.refresh(session)
    return session


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


@router.post("/send", response_model=MessageResponse)
async def send_message(
    body: MessageSend,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    session = await get_or_create_session(user, db)

    if session.status not in ("active", "interview_complete"):
        raise HTTPException(status_code=400, detail="Session is not active")

    # Save user message
    user_msg = Message(
        session_id=session.id,
        role="user",
        content=body.content,
        phase=session.phase,
    )
    db.add(user_msg)
    await db.flush()

    # Get all messages for context
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    # Call Claude
    assistant_content, session_updates = await chat_with_claude(session, messages)

    # Save assistant message
    assistant_msg = Message(
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        phase=session.phase,
    )
    db.add(assistant_msg)

    # Apply any session updates from META blocks
    for key, value in session_updates.items():
        setattr(session, key, value)

    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg


@router.patch("/job-description", response_model=SessionResponse)
async def set_job_description(
    body: JobDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    session = await get_or_create_session(user, db)
    session.job_description = body.job_description
    await db.commit()
    await db.refresh(session)
    return session


@router.post("/new-session", response_model=SessionResponse)
async def start_new_session(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_candidate),
):
    # Mark only active sessions as abandoned — preserve completed ones
    result = await db.execute(
        select(Session).where(
            Session.user_id == user.id,
            Session.status == "active",
        )
    )
    for old_session in result.scalars().all():
        old_session.status = "abandoned"

    # Create fresh session
    session = Session(user_id=user.id)
    db.add(session)
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
