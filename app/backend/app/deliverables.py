"""Document generation.

Contract: a run generates every file into session_dir/.staging/<run>/, verifies
them, and only then moves them into place under UUID names and swaps the DB rows
in one transaction. Any failure writes no rows, keeps the previous set, and sets
sessions.generation_status='failed' with a short, safe message.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import anthropic
from sqlalchemy import delete, select, text, update

from app.claude_client import ClaudeRefusal, response_text, stream_message
from app.config import settings
from app.database import async_session
from app.discovery_writer import read_discovery_md, write_discovery_md
from app.models import Deliverable, Posting, Session
from app.prompts import _load_system_files
from app.storage import (
    download_name,
    resolve_inside,
    safe_component,
    session_dir,
    storage_name,
)

log = logging.getLogger("resume.generation")

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

# Thinking counts toward max_tokens; documents run several thousand tokens.
MAX_TOKENS = 32000
STALE_CLAIM_MINUTES = 30

_tasks: set[asyncio.Task] = set()


class DocumentError(Exception):
    """A failure whose message is safe to show to the admin."""


# --------------------------------------------------------------- claim / tasks


async def claim_generation(db, session_id: uuid.UUID) -> bool:
    """Atomically mark the session as running. False if a live run holds it."""
    result = await db.execute(
        text(
            "UPDATE sessions SET generation_status='running', generation_error=NULL, "
            "generation_started_at=now() WHERE id=:id AND (generation_status <> 'running' "
            "OR generation_started_at IS NULL "
            f"OR generation_started_at < now() - interval '{STALE_CLAIM_MINUTES} minutes') "
            "RETURNING id"
        ),
        {"id": session_id},
    )
    row = result.first()
    await db.commit()
    return row is not None


def _spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_tasks.discard)


def start_base_generation(session_id: uuid.UUID) -> None:
    _spawn(_guarded(session_id, _generate_base(session_id)))


def start_targeted_generation(
    session_id: uuid.UUID, posting_id: uuid.UUID, include_cover_letter: bool
) -> None:
    _spawn(_guarded(session_id, _generate_targeted(session_id, posting_id, include_cover_letter)))


async def wait_for_generation_tasks(timeout: float = 120) -> None:
    """Await outstanding generation tasks (used by tests and shutdown)."""
    while _tasks:
        await asyncio.wait_for(
            asyncio.gather(*list(_tasks), return_exceptions=True), timeout=timeout
        )


async def _guarded(session_id: uuid.UUID, work) -> None:
    try:
        await work
        return
    except DocumentError as e:
        msg = str(e)
    except ClaudeRefusal:
        msg = "The AI declined to write this document. Review the interview notes and try again."
    except Exception:
        log.exception("generation failed session=%s", session_id)
        msg = "Document generation failed unexpectedly. Try again."
    try:
        async with async_session() as db:
            await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(generation_status="failed", generation_error=msg[:500])
            )
            await db.commit()
    except Exception:
        log.exception("could not record generation failure session=%s", session_id)


# ------------------------------------------------------------------ primitives


def _inputs_hash(system: str, user_content: str) -> str:
    # discovery.md carries a "Last Updated" timestamp that changes every run
    body = re.sub(r"^\*\*Last Updated:\*\*.*$", "", f"{system}\n\x00\n{user_content}", flags=re.M)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def _generate_with_claude(system: str, user_content: str) -> str:
    # Streamed: long document generations can exceed non-streaming HTTP timeouts.
    # The SDK client is synchronous, so run it off the event loop.
    def call() -> str:
        response = stream_message(
            client,
            effort="high",
            max_tokens=MAX_TOKENS,
            system=system,
            messages=[{"role": "user", "content": user_content}],
        )
        return response_text(response)

    return await asyncio.to_thread(call)


async def _stage_text(stage: Path, key: str, ext: str, label: str, system: str, user: str) -> str:
    """Generate (or reuse, when the prompt inputs are unchanged) one staged text file."""
    path = stage / f"{key}{ext}"
    hash_path = stage / f"{key}.inputs.sha256"
    digest = _inputs_hash(system, user)
    if path.is_file() and hash_path.is_file():
        try:
            if hash_path.read_text().strip() == digest:
                reused = path.read_text(encoding="utf-8")
                if reused.strip():
                    return reused
        except OSError:
            pass
    content = await _generate_with_claude(system, user)
    if not content or not content.strip():
        raise DocumentError(f"The {label} came back empty. Try again.")
    hash_path.unlink(missing_ok=True)
    path.write_text(content, encoding="utf-8")
    hash_path.write_text(digest)
    return content


def _pandoc_convert(md_path, docx_path, template_path) -> None:
    try:
        subprocess.run(
            ["pandoc", str(md_path), "-o", str(docx_path), f"--reference-doc={template_path}"],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except FileNotFoundError as e:
        raise DocumentError("Word conversion failed: pandoc is not installed on the server.") from e
    except subprocess.TimeoutExpired as e:
        raise DocumentError("Word conversion failed: it took too long. Try again.") from e
    except subprocess.CalledProcessError as e:
        raise DocumentError("Word conversion failed. Try again, or check the resume text.") from e


async def _to_docx(md_path: Path, docx_path: Path) -> None:
    template = Path(settings.TEMPLATES_DIR) / "resume_template.docx"
    if not template.is_file():
        raise DocumentError("Word conversion failed: the document template is missing on the server.")
    await asyncio.to_thread(_pandoc_convert, md_path, docx_path, template)


def _require_files(items) -> None:
    for it in items:
        p = it["staged"]
        if not p.is_file() or p.stat().st_size == 0:
            raise DocumentError("A generated file was missing or empty. Try again.")


async def _commit_set(session_id, items, *, kind, posting_id, replace_base, mark_generated):
    """Move staged files into place, then swap DB rows in one transaction."""
    sdir = session_dir(session_id)
    sdir.mkdir(parents=True, exist_ok=True)
    placed: list[Path] = []
    rows: list[Deliverable] = []
    try:
        for it in items:
            did = uuid.uuid4()
            dest = sdir / storage_name(did, it["ext"])
            os.replace(it["staged"], dest)
            placed.append(dest)
            rows.append(
                Deliverable(
                    id=did, session_id=session_id, type=it["type"], filename=it["filename"],
                    file_path=str(dest), kind=kind, posting_id=posting_id,
                )
            )
        old_paths: list[str] = []
        async with async_session() as db:
            if replace_base:
                old = (await db.execute(
                    select(Deliverable.file_path).where(
                        Deliverable.session_id == session_id, Deliverable.kind == "base"
                    )
                )).scalars().all()
                old_paths = list(old)
                await db.execute(
                    delete(Deliverable).where(
                        Deliverable.session_id == session_id, Deliverable.kind == "base"
                    )
                )
            db.add_all(rows)
            values = {"generation_status": "done", "generation_error": None}
            if mark_generated:
                values["status"] = "deliverables_generated"
            await db.execute(update(Session).where(Session.id == session_id).values(**values))
            await db.commit()
    except BaseException:
        for p in placed:
            p.unlink(missing_ok=True)
        raise
    for p in old_paths:
        try:
            resolve_inside(settings.DELIVERABLES_DIR, p).unlink(missing_ok=True)
        except (ValueError, OSError):
            pass


def _staging(session_id, run: str) -> Path:
    stage = session_dir(session_id) / ".staging" / run
    stage.mkdir(parents=True, exist_ok=True)
    return stage


def _clear_staging(stage: Path) -> None:
    shutil.rmtree(stage, ignore_errors=True)
    try:
        stage.parent.rmdir()  # only if now empty
    except OSError:
        pass


async def _load_session(session_id) -> Session:
    async with async_session() as db:
        session = (await db.execute(select(Session).where(Session.id == session_id))).scalar_one_or_none()
    if session is None:
        raise DocumentError("Session not found.")
    return session


def _candidate_name(session: Session) -> str:
    name = (session.discovery_data or {}).get("candidate_name")
    return name if isinstance(name, str) and name.strip() else "Candidate"


# ------------------------------------------------------------------ base set


async def _generate_base(session_id: uuid.UUID) -> None:
    session = await _load_session(session_id)
    files = _load_system_files()
    discovery_json = json.dumps(session.discovery_data or {}, indent=2)

    await asyncio.to_thread(write_discovery_md, session)
    discovery_md = read_discovery_md(session) or f"```json\n{discovery_json}\n```"
    candidate_ctx = _candidate_context(session, discovery_md)

    if session.experience_level == "early_career":
        rules = files.get("system_resume_rules_early_career", "")
    else:
        rules = files.get("system_resume_rules", "")
    output_formats = files.get("system_output_formats", "")
    name = _candidate_name(session)

    stage = _staging(session_id, "base")

    resume_md = await _stage_text(
        stage, "resume", ".md", "resume",
        f"You are a resume writer. Generate a complete resume in markdown.\n\n{rules}\n\n{output_formats}\n\n{HEADER_RULE}",
        f"Generate the final resume based on this discovery data:\n\n{candidate_ctx}",
    )
    await _to_docx(stage / "resume.md", stage / "resume.docx")

    await _stage_text(
        stage, "prep", ".md", "interview prep guide",
        f"You are an interview coach. Generate an interview prep guide.\n\n{output_formats}",
        f"Generate interview prep based on this discovery data:\n\n{candidate_ctx}\n\nResume:\n{resume_md}",
    )

    profile = files.get(f"profile_{session.profile_slug}", "") if session.profile_slug else ""
    await _stage_text(
        stage, "matrix", ".html", "skills matrix",
        f"Generate a skills matrix as a complete HTML file with embedded CSS.\n\n{output_formats}\n\nProfile:\n{profile}",
        f"Generate the skills matrix based on:\n\n{candidate_ctx}",
    )

    await _stage_text(
        stage, "score", ".md", "score card",
        f"You are a resume evaluator. Generate a score card.\n\n{output_formats}",
        f"Evaluate this resume and generate a score card:\n{resume_md}",
    )

    items = [
        dict(type="resume_md", ext=".md", staged=stage / "resume.md",
             filename=download_name(name, "Resume_FINAL", ".md")),
        dict(type="resume_docx", ext=".docx", staged=stage / "resume.docx",
             filename=download_name(name, "Resume_FINAL", ".docx")),
        dict(type="interview_prep_md", ext=".md", staged=stage / "prep.md",
             filename=download_name(name, "Interview_Prep", ".md")),
        dict(type="skills_matrix_html", ext=".html", staged=stage / "matrix.html",
             filename=download_name(name, "Skills_Matrix", ".html")),
        dict(type="score_card_md", ext=".md", staged=stage / "score.md",
             filename=download_name(name, "Score_Card", ".md")),
    ]
    _require_files(items)
    await _commit_set(session_id, items, kind="base", posting_id=None,
                      replace_base=True, mark_generated=True)
    _clear_staging(stage)


HEADER_RULE = (
    "Header: use the candidate's name and contact details exactly as given. "
    "If a detail is missing, leave it out. Never invent contact details or use "
    "placeholders like [Phone] or email@example.com."
)


def _candidate_context(session, discovery_md: str) -> str:
    """Discovery markdown plus contact details and the original resume, when present."""
    data = session.discovery_data or {}
    out = discovery_md or ""
    contact = data.get("contact")
    name = data.get("candidate_name")
    if contact or name:
        lines = ["", "", "## Contact Details (use exactly as given)"]
        if name:
            lines.append(f"- Name: {name}")
        if isinstance(contact, dict):
            for k, v in contact.items():
                if v:
                    lines.append(f"- {k.replace('_', ' ').title()}: {v}")
        elif contact:
            lines.append(f"- {contact}")
        out += "\n".join(lines)
    if session.resume_text:
        out += (
            "\n\n## Candidate's Original Resume (reference only)\n"
            "Use it for facts, dates, employers and contact details the interview didn't cover; "
            "where it conflicts with the interview answers, the interview wins.\n\n"
            f"{session.resume_text}"
        )
    return out


async def _base_resume_text(session_id) -> str:
    """Text of the session's current base resume, or "" if there isn't a readable one."""
    async with async_session() as db:
        row = (await db.execute(
            select(Deliverable.file_path)
            .where(
                Deliverable.session_id == session_id,
                Deliverable.kind == "base",
                Deliverable.type.in_(("resume_md", "resume")),
            )
            .order_by(Deliverable.created_at.desc())
            .limit(1)
        )).scalar_one_or_none()
    if not row:
        return ""
    try:
        return resolve_inside(settings.DELIVERABLES_DIR, row).read_text(encoding="utf-8")
    except (ValueError, OSError, UnicodeDecodeError):
        return ""


async def _generate_targeted(session_id: uuid.UUID, posting_id: uuid.UUID, include_cover_letter: bool) -> None:
    """A targeted resume variant and optional cover letter for one posting."""
    session = await _load_session(session_id)
    async with async_session() as db:
        posting = (await db.execute(select(Posting).where(Posting.id == posting_id))).scalar_one_or_none()
    if posting is None or posting.session_id != session_id:
        raise DocumentError("Job posting not found.")

    files = _load_system_files()
    await asyncio.to_thread(write_discovery_md, session)
    discovery_md = _candidate_context(session, read_discovery_md(session) or "")
    rules = files.get(
        "system_resume_rules_early_career" if session.experience_level == "early_career" else "system_resume_rules", ""
    )
    output_formats = files.get("system_output_formats", "")
    name = _candidate_name(session)
    company, role, posting_text = posting.company, posting.role, posting.posting_text
    base_resume = await _base_resume_text(session_id)

    stage = _staging(session_id, f"target-{posting_id}")

    await _stage_text(
        stage, "resume", ".md", "targeted resume",
        (
            f"You are a resume writer specializing in job targeting.\n\n{rules}\n\n{output_formats}\n\n"
            f"Rules for targeted variants:\n"
            f"- Rewrite ONLY the Professional Summary section to incorporate keywords and priorities from the job posting\n"
            f"- Keep ALL other sections (Key Achievements, Experience, Certifications, Core Competencies) exactly as-is\n"
            f"- Weave keywords naturally — the summary must read like the candidate wrote it, not keyword stuffing\n"
            f"- Extract 10-15 key terms from the posting and use exact phrases where they fit naturally\n"
            f"- Flag any keywords the resume doesn't support with a comment: <!-- GAP: [keyword] -->\n"
            f"- {HEADER_RULE}\n"
        ),
        (
            f"Job Posting — {company} ({role}):\n\n{posting_text}\n\n"
            f"Base Resume:\n\n{base_resume if base_resume else discovery_md}\n\n"
            f"Generate the targeted resume variant. Rewrite only the Summary."
        ),
    )
    await _to_docx(stage / "resume.md", stage / "resume.docx")

    items = [
        dict(type="resume_targeted_md", ext=".md", staged=stage / "resume.md",
             filename=download_name(name, "Resume", ".md", company, role)),
        dict(type="resume_targeted_docx", ext=".docx", staged=stage / "resume.docx",
             filename=download_name(name, "Resume", ".docx", company, role)),
    ]

    if include_cover_letter:
        await _stage_text(
            stage, "cover", ".md", "cover letter",
            f"You are a cover letter writer.\n\n{output_formats}\n\n{HEADER_RULE}",
            (
                f"Job Posting — {company} ({role}):\n\n{posting_text}\n\n"
                f"Candidate Discovery Data:\n\n{discovery_md}\n\n"
                f"Base Resume:\n\n{base_resume}\n\n"
                f"Write a targeted cover letter for this specific role and company. "
                f"Follow the cover letter format in the output formats guide exactly."
            ),
        )
        await _to_docx(stage / "cover.md", stage / "cover.docx")
        items += [
            dict(type="cover_letter_md", ext=".md", staged=stage / "cover.md",
                 filename=download_name(name, "Cover_Letter", ".md", company)),
            dict(type="cover_letter_docx", ext=".docx", staged=stage / "cover.docx",
                 filename=download_name(name, "Cover_Letter", ".docx", company)),
        ]

    _require_files(items)
    await _commit_set(session_id, items, kind="targeted", posting_id=posting_id,
                      replace_base=False, mark_generated=False)
    _clear_staging(stage)
