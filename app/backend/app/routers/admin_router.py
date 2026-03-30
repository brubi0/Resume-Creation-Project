import re

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import hash_password, require_admin
from app.config import settings
from app.database import get_db
from app.models import Session, User
from app.schemas import CandidateCreate, CandidateListItem, ProfileItem

router = APIRouter()


def slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    return slug.strip("_")


@router.get("/candidates", response_model=list[CandidateListItem])
async def list_candidates(
    db: AsyncSession = Depends(get_db), _admin: User = Depends(require_admin)
):
    result = await db.execute(
        select(User)
        .where(User.role == "candidate")
        .options(selectinload(User.sessions))
        .order_by(User.created_at.desc())
    )
    candidates = result.scalars().all()
    items = []
    for c in candidates:
        latest = None
        if c.sessions:
            latest = max(c.sessions, key=lambda s: s.created_at)
        items.append(
            CandidateListItem(
                id=c.id,
                name=c.name,
                username=c.username,
                created_at=c.created_at,
                session_id=latest.id if latest else None,
                session_status=latest.status if latest else None,
                session_phase=latest.phase if latest else None,
            )
        )
    return items


@router.post("/candidates", response_model=CandidateListItem, status_code=201)
async def create_candidate(
    body: CandidateCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    username = slugify(body.name)
    existing = await db.execute(select(User).where(User.username == username))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Username '{username}' already exists",
        )

    user = User(
        name=body.name,
        username=username,
        password_hash=hash_password(body.password),
        role="candidate",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return CandidateListItem(
        id=user.id,
        name=user.name,
        username=user.username,
        created_at=user.created_at,
    )


@router.delete("/candidates/{user_id}", status_code=200)
async def delete_candidate(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(
        select(User).where(User.id == user_id, User.role == "candidate")
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Candidate not found")
    await db.delete(user)
    await db.commit()
    return {"detail": "Candidate deleted"}


@router.get("/profiles", response_model=list[ProfileItem])
async def list_profiles(_admin: User = Depends(require_admin)):
    import os

    profiles = []
    profiles_dir = settings.PROFILES_DIR
    if not os.path.isdir(profiles_dir):
        return profiles
    for fname in sorted(os.listdir(profiles_dir)):
        if not fname.endswith(".md") or fname == "README.md":
            continue
        slug = fname.replace(".md", "")
        name = slug.replace("_", " ").title()
        # Try to extract the actual name from the file header
        fpath = os.path.join(profiles_dir, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("# Profile:"):
                    name = line.replace("# Profile:", "").strip()
                    break
                if line.startswith("# "):
                    name = line.lstrip("# ").strip()
                    break
        profiles.append(ProfileItem(slug=slug, name=name))
    return profiles
