import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.deliverables import generate_all_deliverables, generate_targeted_deliverables
from app.models import Deliverable, Posting, Session, User
from app.prompts import get_profile_metadata
from app.schemas import DeliverableResponse, DeliverableWithContext, TargetRequest

router = APIRouter()


def _build_slug_to_role() -> dict[str, str]:
    return {p["slug"]: p["name"] for p in get_profile_metadata()}


@router.get("", response_model=list[DeliverableWithContext])
async def list_deliverables(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    slug_to_role = _build_slug_to_role()

    if user.role == "admin":
        result = await db.execute(
            select(Deliverable, Session, User)
            .join(Session, Deliverable.session_id == Session.id)
            .join(User, Session.user_id == User.id)
            .order_by(Deliverable.created_at.desc())
        )
        rows = result.all()
    else:
        session_result = await db.execute(
            select(Session.id).where(Session.user_id == user.id)
        )
        session_ids = [row[0] for row in session_result.all()]
        if not session_ids:
            return []
        result = await db.execute(
            select(Deliverable, Session, User)
            .join(Session, Deliverable.session_id == Session.id)
            .join(User, Session.user_id == User.id)
            .where(Deliverable.session_id.in_(session_ids))
            .order_by(Deliverable.created_at.desc())
        )
        rows = result.all()

    output = []
    for deliverable, session, candidate in rows:
        target_role = slug_to_role.get(session.profile_slug or "", "") or "General"
        output.append(
            DeliverableWithContext(
                id=deliverable.id,
                session_id=deliverable.session_id,
                type=deliverable.type,
                filename=deliverable.filename,
                created_at=deliverable.created_at,
                candidate_name=candidate.name,
                target_role=target_role,
            )
        )
    return output


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


@router.get("/{deliverable_id}/preview")
async def preview_deliverable(
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

    # Check access
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

    # Only allow preview for text-based files
    ext = os.path.splitext(deliverable.file_path)[1].lower()
    if ext not in (".md", ".html", ".txt"):
        raise HTTPException(status_code=400, detail="File type not previewable")

    with open(deliverable.file_path, "r", encoding="utf-8") as f:
        content = f.read()

    content_type = "text/html" if ext == ".html" else "text/markdown"
    return {"content": content, "content_type": content_type, "filename": deliverable.filename}


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


@router.post("/target", status_code=202)
async def trigger_targeting(
    body: TargetRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Session).where(Session.id == body.session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Save posting for reference
    posting = Posting(
        session_id=session.id,
        company=body.company,
        role=body.role,
        posting_text=body.posting_text,
    )
    db.add(posting)
    await db.flush()

    await generate_targeted_deliverables(
        session=session,
        posting_company=body.company,
        posting_role=body.role,
        posting_text=body.posting_text,
        include_cover_letter=body.include_cover_letter,
        db=db,
    )
    return {"detail": "Targeting complete"}
