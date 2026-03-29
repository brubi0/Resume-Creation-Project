from fastapi import APIRouter, Depends, HTTPException
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
    # Mark any active/complete sessions as abandoned
    result = await db.execute(
        select(Session).where(
            Session.user_id == user.id,
            Session.status.notin_(["abandoned"]),
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
        status=session.status,
    )
