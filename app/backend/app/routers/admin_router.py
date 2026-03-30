import os
import re

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import hash_password, require_admin
from app.config import settings
from app.database import get_db
from app.models import Session, User
from app.prompts import get_profile_metadata, reload_system_files
from app.schemas import CandidateCreate, CandidateListItem, ProfileGenerateRequest, ProfileItem

_claude = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
_GENERATE_MODEL = "claude-sonnet-4-20250514"

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
    return get_profile_metadata()


@router.post("/profiles/generate", response_model=ProfileItem)
async def generate_profile(
    body: ProfileGenerateRequest,
    _admin: User = Depends(require_admin),
):
    """Generate a new role profile using Claude + web search, save it to disk."""
    guide_path = os.path.join(settings.SYSTEM_DIR, "profile-generation-guide.md")
    example_path = os.path.join(settings.PROFILES_DIR, "netsuite_administrator.md")

    guide = ""
    if os.path.exists(guide_path):
        with open(guide_path, "r", encoding="utf-8") as f:
            guide = f.read()

    example = ""
    if os.path.exists(example_path):
        with open(example_path, "r", encoding="utf-8") as f:
            example = f.read()

    system_prompt = (
        "You are a resume consultant generating an industry skills profile for a web-based resume tool.\n\n"
        "Follow this generation guide exactly:\n\n"
        f"{guide}\n\n"
        "Use this profile as your structural template — your output must match this format precisely:\n\n"
        f"{example}\n\n"
        "After researching (via web search or training knowledge), output ONLY the complete profile "
        "in markdown — starting with '# Profile:' and nothing before it. No explanation, no preamble."
    )

    parts = [f"Role: {body.role_name}"]
    if body.industry:
        parts.append(f"Industry: {body.industry}")
    if body.must_have_tools:
        parts.append(f"Must-have tools/certs: {body.must_have_tools}")
    user_prompt = "Generate a complete skills profile for:\n" + "\n".join(parts)

    messages: list[dict] = [{"role": "user", "content": user_prompt}]

    # Agentic loop — Claude may call web_search multiple times
    MAX_ITERATIONS = 8
    profile_text = ""
    for _ in range(MAX_ITERATIONS):
        response = _claude.messages.create(
            model=_GENERATE_MODEL,
            max_tokens=8192,
            system=system_prompt,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            # Extract text blocks
            for block in response.content:
                if hasattr(block, "text"):
                    profile_text += block.text
            break
        elif response.stop_reason == "tool_use":
            # Append assistant turn and loop — web_search is server-side
            messages.append({"role": "assistant", "content": response.content})
        else:
            break

    # Strip anything before the profile header
    marker = "# Profile:"
    idx = profile_text.find(marker)
    if idx == -1:
        raise HTTPException(status_code=500, detail="Claude did not return a valid profile.")
    profile_text = profile_text[idx:].strip()

    # Derive slug from role_name
    slug = re.sub(r"[^a-z0-9]+", "_", body.role_name.lower()).strip("_")
    profile_path = os.path.join(settings.PROFILES_DIR, f"{slug}.md")
    with open(profile_path, "w", encoding="utf-8") as f:
        f.write(profile_text)

    # Reload cache so new profile appears immediately
    reload_system_files()

    # Parse metadata from generated file
    meta = next((p for p in get_profile_metadata() if p["slug"] == slug), None)
    if meta:
        return ProfileItem(**meta)
    return ProfileItem(slug=slug, name=body.role_name)
