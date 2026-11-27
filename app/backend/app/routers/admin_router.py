import os
import re
import shutil

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth import hash_password, require_admin
from app.claude_client import (
    ClaudeConfigError,
    ClaudeEmpty,
    ClaudeRefusal,
    ClaudeTruncated,
    ClaudeUnavailable,
    create_message,
    response_text,
)
from app.config import settings
from app.database import get_db
from app.models import Session, User
from app.prompts import get_profile_metadata, reload_system_files
from app.storage import resolve_inside, session_dir
from app.schemas import CandidateCreate, CandidateListItem, ProfileGenerateRequest, ProfileItem


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
    STATUS_PRIORITY = {
        "deliverables_generated": 0,
        "interview_complete": 1,
        "active": 2,
        "abandoned": 3,
    }

    items = []
    for c in candidates:
        best = None
        completed_sets = 0
        if c.sessions:
            completed_sets = sum(
                1 for s in c.sessions if s.status == "deliverables_generated"
            )
            best = min(
                c.sessions,
                key=lambda s: (STATUS_PRIORITY.get(s.status, 99), -s.created_at.timestamp()),
            )
        gen = next((s for s in c.sessions if s.generation_status == "running"), best)
        items.append(
            CandidateListItem(
                id=c.id,
                name=c.name,
                username=c.username,
                created_at=c.created_at,
                session_id=best.id if best else None,
                session_status=best.status if best else None,
                session_phase=best.phase if best else None,
                completed_sets=completed_sets,
                generation_status=gen.generation_status if gen else "idle",
                generation_error=gen.generation_error if gen else None,
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
    session_ids = (
        await db.execute(select(Session.id).where(Session.user_id == user.id))
    ).scalars().all()
    await db.delete(user)
    await db.commit()
    for sid in session_ids:
        try:
            shutil.rmtree(session_dir(sid), ignore_errors=True)
        except Exception:
            pass
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
    slug = re.sub(r"[^a-z0-9]+", "_", body.role_name.lower()).strip("_")[:60].strip("_")
    if not re.fullmatch(r"[a-z0-9_]{1,60}", slug):
        raise HTTPException(status_code=422, detail="Role name must contain letters or numbers.")
    try:
        profile_path = resolve_inside(settings.PROFILES_DIR, f"{slug}.md")
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid role name.")
    if os.path.exists(profile_path):
        raise HTTPException(status_code=409, detail="A profile with this name already exists.")

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
        try:
            # Not streamed: the pinned SDK's stream accumulator drops server_tool_use
            # inputs, and a pause_turn must be sent back unchanged. 16000 stays under
            # the SDK's non-streaming limit.
            response = await create_message(
                effort="high",
                max_tokens=16000,
                system=system_prompt,
                tools=[{"type": "web_search_20260209", "name": "web_search"}],
                messages=messages,
            )
            if response.stop_reason == "pause_turn":
                # Server-side web search paused mid-turn: send the turn back to resume it.
                messages.append({"role": "assistant", "content": response.content})
                continue
            profile_text = response_text(response)
        except ClaudeRefusal:
            raise HTTPException(status_code=422, detail="Claude declined to generate this profile.")
        except (ClaudeTruncated, ClaudeEmpty):
            raise HTTPException(
                status_code=422,
                detail="Claude's reply was incomplete. Try again.",
            )
        except ClaudeUnavailable:
            raise HTTPException(
                status_code=503, detail="The AI service is unavailable right now. Try again shortly."
            )
        except ClaudeConfigError:
            raise HTTPException(
                status_code=503, detail="The AI service is not configured correctly."
            )
        break

    # Strip anything before the profile header
    marker = "# Profile:"
    idx = profile_text.find(marker)
    if idx == -1:
        raise HTTPException(status_code=422, detail="Claude did not return a valid profile. Try again.")
    profile_text = profile_text[idx:].strip()

    try:
        with open(profile_path, "x", encoding="utf-8") as f:
            f.write(profile_text)
    except FileExistsError:
        raise HTTPException(status_code=409, detail="A profile with this name already exists.")

    # Reload cache so new profile appears immediately
    reload_system_files()

    # Parse metadata from generated file
    meta = next((p for p in get_profile_metadata() if p["slug"] == slug), None)
    if meta:
        return ProfileItem(**meta)
    return ProfileItem(slug=slug, name=body.role_name)
