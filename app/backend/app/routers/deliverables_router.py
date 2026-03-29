import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.deliverables import generate_all_deliverables
from app.models import Deliverable, Session, User
from app.schemas import DeliverableResponse

router = APIRouter()


@router.get("", response_model=list[DeliverableResponse])
async def list_deliverables(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if user.role == "admin":
        # Admin can see all — optionally filter by session_id query param
        result = await db.execute(
            select(Deliverable).order_by(Deliverable.created_at.desc())
        )
    else:
        # Candidate sees only their own
        session_result = await db.execute(
            select(Session).where(Session.user_id == user.id)
        )
        session = session_result.scalar_one_or_none()
        if not session:
            return []
        result = await db.execute(
            select(Deliverable)
            .where(Deliverable.session_id == session.id)
            .order_by(Deliverable.created_at.desc())
        )
    return result.scalars().all()


@router.get("/{deliverable_id}/download")
async def download_deliverable(
    deliverable_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Deliverable).where(Deliverable.id == deliverable_id)
    )
    deliverable = result.scalar_one_or_none()
    if not deliverable:
        raise HTTPException(status_code=404, detail="Deliverable not found")

    # Check access: admin can download any, candidate only their own
    if user.role == "candidate":
        session_result = await db.execute(
            select(Session).where(
                Session.id == deliverable.session_id, Session.user_id == user.id
            )
        )
        if not session_result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Access denied")

    if not os.path.exists(deliverable.file_path):
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        deliverable.file_path,
        filename=deliverable.filename,
        media_type="application/octet-stream",
    )


@router.post("/generate", status_code=202)
async def trigger_generation(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    await generate_all_deliverables(session, db)
    return {"detail": "Deliverable generation started"}
