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

from sqlalchemy import delete, select, text, update

from app.claude_client import (
    ClaudeConfigError,
    ClaudeEmpty,
    ClaudeRefusal,
    ClaudeTruncated,
    ClaudeUnavailable,
    DOC_TIMEOUT,
    response_text,
    stream_message,
)
from app.config import settings
from app.database import async_session
from app.discovery_writer import write_discovery_md
from app.interview import QUESTION_LABELS, progress
from app.models import Deliverable, Message, Posting, Session
from app.prompts import _load_system_files, wrap_candidate_document
from app.storage import (
    download_name,
    resolve_inside,
    safe_component,
    session_dir,
    storage_name,
)

log = logging.getLogger("resume.generation")

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
    except ClaudeTruncated:
        msg = "The AI ran out of room writing this document. Try again."
    except ClaudeUnavailable:
        msg = "The AI service was unavailable. Try again in a few minutes."
    except ClaudeConfigError:
        msg = "The AI service is not configured correctly. Contact support."
    except Exception as exc:
        # type only: tracebacks/messages can quote candidate text
        log.error("generation failed session=%s: %s", session_id, type(exc).__name__)
        msg = "Document generation failed unexpectedly. Try again."
    try:
        async with async_session() as db:
            await db.execute(
                update(Session)
                .where(Session.id == session_id)
                .values(generation_status="failed", generation_error=msg[:500])
            )
            await db.commit()
    except Exception as exc:
        log.error("could not record generation failure session=%s: %s", session_id, type(exc).__name__)


# ------------------------------------------------------------------ primitives


def _inputs_hash(system: str, user_content: str) -> str:
    # discovery.md carries a "Last Updated" timestamp that changes every run
    body = re.sub(r"^\*\*Last Updated:\*\*.*$", "", f"{system}\n\x00\n{user_content}", flags=re.M)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


async def _generate_with_claude(system: str, user_content: str) -> str:
    # Streamed: long document generations can exceed non-streaming HTTP timeouts.
    response = await stream_message(
        effort="high",
        timeout=DOC_TIMEOUT,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    try:
        return response_text(response)
    except ClaudeEmpty:
        return ""  # the caller reports which document came back empty


async def _stage_text(
    stage: Path, key: str, ext: str, label: str, system: str, user: str, *, check=None
) -> str:
    """Generate (or reuse, when the prompt inputs are unchanged) one staged text file.

    `check(content) -> problem | None` runs on fresh output. A failing document is
    regenerated once; a second failure fails the run. Only a passing document is
    ever written, so a bad one can never be reused as a good staged file.
    """
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
    if check is not None and check(content):
        retry_user = (
            f"{user}\n\nYour previous attempt included contact details, placeholders or internal "
            "markers that were not confirmed. Rewrite the document using only the confirmed contact "
            "details above; leave out anything not listed. No placeholders."
        )
        content = await _generate_with_claude(system, retry_user)
        if not content or not content.strip():
            raise DocumentError(f"The {label} came back empty. Try again.")
        if check(content):
            raise DocumentError(
                f"The {label} included contact details or placeholders that weren't confirmed."
            )
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

    await asyncio.to_thread(write_discovery_md, session)  # admin-readable copy only
    messages = await _user_messages(session_id)
    snapshot = _snapshot_for(session, messages)
    check = _document_check(session)
    approved = (session.approved_resume or "").strip()

    if session.experience_level == "early_career":
        rules = files.get("system_resume_rules_early_career", "")
    else:
        rules = files.get("system_resume_rules", "")
    output_formats = files.get("system_output_formats", "")
    name = _candidate_name(session)

    stage = _staging(session_id, "base")

    if approved:
        # The candidate approved this text: it is the resume, verbatim (comments aside).
        resume_md = strip_comments(approved).strip() + "\n"
        if check(resume_md):
            raise DocumentError(
                "The resume included contact details or placeholders that weren't confirmed."
            )
        (stage / "resume.md").write_text(resume_md, encoding="utf-8")
        (stage / "resume.inputs.sha256").unlink(missing_ok=True)
        prep_user = f"Generate interview prep based on these facts:\n\n{snapshot}"
        score_user = f"Evaluate this resume and generate a score card:\n{resume_md}"
    else:
        resume_md = await _stage_text(
            stage, "resume", ".md", "resume",
            f"You are a resume writer. Generate a complete resume in markdown.\n\n{rules}\n\n{output_formats}\n\n{HEADER_RULE}\n\n{FACT_RULES}",
            f"Generate the final resume based on these facts:\n\n{snapshot}",
            check=check,
        )
        prep_user = f"Generate interview prep based on these facts:\n\n{snapshot}\n\nResume:\n{resume_md}"
        score_user = f"Evaluate this resume and generate a score card:\n{resume_md}"
    await _to_docx(stage / "resume.md", stage / "resume.docx")

    await _stage_text(
        stage, "prep", ".md", "interview prep guide",
        f"You are an interview coach. Generate an interview prep guide.\n\n{output_formats}\n\n{FACT_RULES}",
        prep_user,
        check=check,
    )

    profile = files.get(f"profile_{session.profile_slug}", "") if session.profile_slug else ""
    matrix_facts = snapshot if approved else f"{snapshot}\n\nResume:\n{resume_md}"
    await _stage_text(
        stage, "matrix", ".html", "skills matrix",
        f"Generate a skills matrix as a complete HTML file with embedded CSS.\n\n{output_formats}\n\nProfile:\n{profile}\n\n{FACT_RULES}",
        f"Generate the skills matrix based on:\n\n{matrix_facts}",
        check=check,
    )

    await _stage_text(
        stage, "score", ".md", "score card",
        f"You are a resume evaluator. Generate a score card.\n\n{output_formats}\n\n{FACT_RULES}",
        score_user,
        check=check,
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


FACT_RULES = (
    "Fact rules (they override any style guidance above):\n"
    "- Never invent employers, dates, titles, qualifications, certifications, achievements or numbers.\n"
    "- Use only numbers that appear in the facts you are given. When a number was described as an "
    "estimate, keep it marked as approximate (\"about\", \"~\").\n"
    "- Don't add metrics just to satisfy a quantification rule; a bullet without a number is fine.\n"
    "- Score cards assess the document's quality. Never predict hiring outcomes or interview probability.\n"
    "- Interview prep must not invent stories. Where a story is missing, say what the candidate should prepare.\n"
    "- Contact details: use only the confirmed contact listed. Anything marked as not listed stays out."
)

_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_GAP_RE = re.compile(r"<!--\s*GAP:\s*(.*?)-->", re.DOTALL | re.IGNORECASE)
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_URL_RE = re.compile(r"(?:https?://|www\.)\S+|\b(?:[\w-]+\.)+(?:com|org|net|io|co|edu|dev|me)/\S*", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?<![\d.])(?:\+?\d{1,2}[ .\-]?)?(?:\(\d{3}\)[ .\-]?|\d{3}[ .\-]?)\d{3}[ .\-]?\d{4}(?!\d)"
)
_PLACEHOLDER_RE = re.compile(
    r"\[(?:phone|email|company)\]|\bXX+%|email@example\.com|555-555-5555|lorem", re.IGNORECASE
)
_MARKER_RE = re.compile(r"<!--\s*META|discovery\.md|candidates/", re.IGNORECASE)

CONTACT_FIELDS_LISTED = ("location", "phone", "email", "linkedin", "other")


def strip_comments(text: str) -> str:
    return _COMMENT_RE.sub("", text)


def _redact_contact(text: str) -> str:
    """Remove emails, phone numbers and URLs (legacy upload text only)."""
    text = _EMAIL_RE.sub("", text)
    text = _URL_RE.sub("", text)
    return _PHONE_RE.sub("", text)


def _contact(session) -> tuple[dict, list[str]]:
    c = (session.discovery_data or {}).get("contact")
    if not isinstance(c, dict):
        return {}, []
    omitted = c.get("omitted") if isinstance(c.get("omitted"), list) else []
    fields = {k: v for k, v in c.items() if k in CONTACT_FIELDS_LISTED and isinstance(v, str) and v.strip()
              and k not in omitted}
    return fields, [o for o in omitted if o in CONTACT_FIELDS_LISTED]


def _phone_digits(s: str) -> str:
    d = re.sub(r"\D", "", s)
    return d[-10:] if len(d) >= 10 else d


def _answer_text(v) -> str:
    if isinstance(v, str):
        return v.strip()
    return json.dumps(v, ensure_ascii=False, indent=2)


def build_fact_snapshot(session, messages: list[str] | None = None) -> str:
    """Everything a document may rely on, and nothing it may not.

    Approved sessions: the approved resume is the resume; the original upload is
    never included. Legacy sessions (no approved resume): the upload with emails,
    phone numbers and URLs removed, plus the candidate's own chat answers
    (`messages`, in order) so later corrections win.
    """
    data = session.discovery_data or {}
    fields, omitted = _contact(session)
    out: list[str] = ["## Confirmed contact (use exactly as given; nothing else may appear)"]
    name = data.get("candidate_name")
    if isinstance(name, str) and name.strip():
        out.append(f"- Name: {name}")
    for k in CONTACT_FIELDS_LISTED:
        if k in fields:
            out.append(f"- {k.title()}: {fields[k]}")
    if omitted:
        out.append(
            "- Not listed by the candidate (leave out entirely, do not look for them elsewhere): "
            + ", ".join(omitted)
        )
    if len(out) == 1:
        out.append("- (no contact details were confirmed; leave contact details out)")

    answered, skipped, _next, _total = progress(session)
    out.append("\n## Interview answers")
    for qid in answered:
        out.append(f"### {QUESTION_LABELS.get(qid, qid)}\n{_answer_text(data[qid])}")
    extras = [k for k in data if k not in ("candidate_name", "contact", "skipped_questions")
              and k not in answered]
    for k in extras:
        out.append(f"### {k.replace('_', ' ').title()} (additional detail)\n{_answer_text(data[k])}")
    if skipped:
        out.append("\n## Skipped questions (the candidate chose not to answer; do not invent content)")
        out += [f"- {QUESTION_LABELS.get(q, q)}" for q in skipped]

    approved = getattr(session, "approved_resume", None)
    if approved and approved.strip():
        out.append(
            "\n## Approved resume (this IS the candidate's resume; the candidate approved it)\n"
            + strip_comments(approved).strip()
        )
    else:
        if messages:
            out.append(
                "\n## Candidate's answers, in order (later answers correct earlier ones)\n"
                + "\n\n".join(f"- {m.strip()}" for m in messages if m and m.strip())
            )
        if session.resume_text:
            out.append(
                "\n## Candidate's original resume (reference only; contact details were removed)\n"
                "Use it for facts, dates and employers the interview didn't cover; where it conflicts "
                "with the interview answers, the interview wins.\n\n"
                + wrap_candidate_document(_redact_contact(session.resume_text))
            )
    out.append("\n" + FACT_RULES)
    return "\n".join(out)


async def _user_messages(session_id) -> list[str]:
    async with async_session() as db:
        rows = (await db.execute(
            select(Message.content).where(
                Message.session_id == session_id, Message.role == "user", Message.status == "ok"
            ).order_by(Message.created_at.asc(), Message.id.asc())
        )).scalars().all()
    return list(rows)


def _snapshot_for(session, messages: list[str]) -> str:
    return build_fact_snapshot(session, None if getattr(session, "approved_resume", None) else messages)


def _visible_text(content: str) -> str:
    t = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", content)
    return re.sub(r"<[^>]+>", "\n", t)


def _document_check(session):
    """Return check(content) -> problem|None for generated Markdown/HTML."""
    fields, _omitted = _contact(session)
    emails = {fields["email"].strip().lower()} if "email" in fields else set()
    phones = {_phone_digits(fields["phone"])} if "phone" in fields else set()

    def check(content: str) -> str | None:
        if _MARKER_RE.search(content):
            return "internal marker"
        text = strip_comments(content)
        if _PLACEHOLDER_RE.search(text):
            return "placeholder"
        visible = _visible_text(text)
        for m in _EMAIL_RE.findall(visible):
            if m.lower() not in emails:
                return "email"
        for m in _PHONE_RE.findall(visible):
            if _phone_digits(m) not in phones:
                return "phone"
        return None

    return check


def _gaps(text: str) -> list[str]:
    out: list[str] = []
    for g in _GAP_RE.findall(text):
        g = " ".join(g.split())[:200]
        if g and g not in out:
            out.append(g)
    return out[:10]


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
    snapshot = _snapshot_for(session, await _user_messages(session_id))
    check = _document_check(session)
    rules = files.get(
        "system_resume_rules_early_career" if session.experience_level == "early_career" else "system_resume_rules", ""
    )
    output_formats = files.get("system_output_formats", "")
    name = _candidate_name(session)
    company, role, posting_text = posting.company, posting.role, posting.posting_text
    base_resume = await _base_resume_text(session_id)

    stage = _staging(session_id, f"target-{posting_id}")

    raw_resume = await _stage_text(
        stage, "resume_raw", ".md", "targeted resume",
        (
            f"You are a resume writer specializing in job targeting.\n\n{rules}\n\n{output_formats}\n\n"
            f"Rules for targeted variants:\n"
            f"- Rewrite ONLY the Professional Summary section to incorporate keywords and priorities from the job posting\n"
            f"- Keep ALL other sections (Key Achievements, Experience, Certifications, Core Competencies) exactly as-is\n"
            f"- Weave keywords naturally — the summary must read like the candidate wrote it, not keyword stuffing\n"
            f"- Extract 10-15 key terms from the posting and use exact phrases where they fit naturally\n"
            f"- Flag any keywords the resume doesn't support with a comment: <!-- GAP: [keyword] -->\n"
            f"- {HEADER_RULE}\n\n{FACT_RULES}\n"
        ),
        (
            f"Job Posting — {company} ({role}):\n\n{wrap_candidate_document(posting_text)}\n\n"
            f"Base Resume:\n\n{base_resume if base_resume else snapshot}\n\n"
            f"Generate the targeted resume variant. Rewrite only the Summary."
        ),
        check=check,
    )
    # GAP comments are for us, not the candidate: drop them from the resume, keep the list.
    gaps = _gaps(raw_resume)
    (stage / "resume.md").write_text(strip_comments(raw_resume).strip() + "\n", encoding="utf-8")
    await _to_docx(stage / "resume.md", stage / "resume.docx")

    items = [
        dict(type="resume_targeted_md", ext=".md", staged=stage / "resume.md",
             filename=download_name(name, "Resume", ".md", company, role)),
        dict(type="resume_targeted_docx", ext=".docx", staged=stage / "resume.docx",
             filename=download_name(name, "Resume", ".docx", company, role)),
    ]

    if include_cover_letter:
        cover = await _stage_text(
            stage, "cover", ".md", "cover letter",
            f"You are a cover letter writer.\n\n{output_formats}\n\n{HEADER_RULE}\n\n{FACT_RULES}",
            (
                f"Job Posting — {company} ({role}):\n\n{wrap_candidate_document(posting_text)}\n\n"
                f"Candidate facts:\n\n{snapshot}\n\n"
                f"Base Resume:\n\n{base_resume}\n\n"
                f"Write a targeted cover letter for this specific role and company. "
                f"Follow the cover letter format in the output formats guide exactly."
            ),
            check=check,
        )
        await _to_docx(stage / "cover.md", stage / "cover.docx")
        # The Markdown preview (only) carries the gaps list.
        preview = strip_comments(cover).strip() + "\n"
        if gaps:
            preview += "\n---\n\n**Gaps to address**\n" + "\n".join(f"- {g}" for g in gaps) + "\n"
        (stage / "cover.preview.md").write_text(preview, encoding="utf-8")
        items += [
            dict(type="cover_letter_md", ext=".md", staged=stage / "cover.preview.md",
                 filename=download_name(name, "Cover_Letter", ".md", company)),
            dict(type="cover_letter_docx", ext=".docx", staged=stage / "cover.docx",
                 filename=download_name(name, "Cover_Letter", ".docx", company)),
        ]

    _require_files(items)
    await _commit_set(session_id, items, kind="targeted", posting_id=posting_id,
                      replace_base=False, mark_generated=False)
    _clear_staging(stage)
