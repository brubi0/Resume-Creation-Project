import json
import os
import subprocess

import anthropic

from app.config import settings
from app.discovery_writer import read_discovery_md, write_discovery_md
from app.models import Deliverable, Message, Session
from app.prompts import _load_system_files

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8192


async def generate_all_deliverables(session: Session, db) -> None:
    """Generate all deliverables for a completed interview session."""
    from sqlalchemy import select

    # Load conversation history
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session.id)
        .order_by(Message.created_at.asc())
    )
    messages = result.scalars().all()

    files = _load_system_files()
    discovery_json = json.dumps(session.discovery_data or {}, indent=2)

    # Ensure discovery.md is current, then read it for richer prompt context
    write_discovery_md(session)
    discovery_md = read_discovery_md(session) or f"```json\n{discovery_json}\n```"

    # Get resume rules based on experience level
    if session.experience_level == "early_career":
        rules = files.get("system_resume_rules_early_career", "")
    else:
        rules = files.get("system_resume_rules", "")

    output_formats = files.get("system_output_formats", "")

    # Build candidate name from conversation or discovery data
    candidate_name = session.discovery_data.get("candidate_name", "Candidate")
    safe_name = candidate_name.replace(" ", "_")

    # Ensure output directory exists
    session_dir = os.path.join(settings.DELIVERABLES_DIR, str(session.id))
    os.makedirs(session_dir, exist_ok=True)

    # --- Generate Resume ---
    resume_md = await _generate_with_claude(
        system=f"You are a resume writer. Generate a complete resume in markdown.\n\n{rules}\n\n{output_formats}",
        user_content=f"Generate the final resume based on this discovery data:\n\n{discovery_md}",
    )
    resume_md_path = os.path.join(session_dir, f"{safe_name}_Resume_FINAL.md")
    _write_file(resume_md_path, resume_md)
    await _save_deliverable(db, session, "resume_md", f"{safe_name}_Resume_FINAL.md", resume_md_path)

    # Convert to DOCX via pandoc
    resume_docx_path = os.path.join(session_dir, f"{safe_name}_Resume_FINAL.docx")
    template_path = os.path.join(settings.TEMPLATES_DIR, "resume_template.docx")
    if os.path.exists(template_path):
        _pandoc_convert(resume_md_path, resume_docx_path, template_path)
        await _save_deliverable(db, session, "resume_docx", f"{safe_name}_Resume_FINAL.docx", resume_docx_path)

    # --- Generate Interview Prep ---
    prep_md = await _generate_with_claude(
        system=f"You are an interview coach. Generate an interview prep guide.\n\n{output_formats}",
        user_content=f"Generate interview prep based on this discovery data:\n\n{discovery_md}\n\nResume:\n{resume_md}",
    )
    prep_md_path = os.path.join(session_dir, f"{safe_name}_Interview_Prep.md")
    _write_file(prep_md_path, prep_md)
    await _save_deliverable(db, session, "interview_prep_md", f"{safe_name}_Interview_Prep.md", prep_md_path)

    # --- Generate Skills Matrix (HTML) ---
    profile = files.get(f"profile_{session.profile_slug}", "") if session.profile_slug else ""
    matrix_html = await _generate_with_claude(
        system=f"Generate a skills matrix as a complete HTML file with embedded CSS.\n\n{output_formats}\n\nProfile:\n{profile}",
        user_content=f"Generate the skills matrix based on:\n\n{discovery_md}",
    )
    matrix_path = os.path.join(session_dir, f"{safe_name}_Skills_Matrix.html")
    _write_file(matrix_path, matrix_html)
    await _save_deliverable(db, session, "skills_matrix_html", f"{safe_name}_Skills_Matrix.html", matrix_path)

    # --- Generate Score Card ---
    scorecard_md = await _generate_with_claude(
        system=f"You are a resume evaluator. Generate a score card.\n\n{output_formats}",
        user_content=f"Evaluate this resume and generate a score card:\n{resume_md}",
    )
    scorecard_path = os.path.join(session_dir, f"{safe_name}_Score_Card.md")
    _write_file(scorecard_path, scorecard_md)
    await _save_deliverable(db, session, "score_card_md", f"{safe_name}_Score_Card.md", scorecard_path)

    # Update session status
    session.status = "deliverables_generated"
    await db.commit()


async def generate_targeted_deliverables(
    session, posting_company: str, posting_role: str, posting_text: str,
    include_cover_letter: bool, db
) -> None:
    """Generate a targeted resume variant and optional cover letter for a specific job posting."""
    files = _load_system_files()
    write_discovery_md(session)
    discovery_md = read_discovery_md(session) or ""

    rules = files.get("system_resume_rules_early_career" if session.experience_level == "early_career" else "system_resume_rules", "")
    output_formats = files.get("system_output_formats", "")

    candidate_name = session.discovery_data.get("candidate_name", "Candidate")
    safe_name = candidate_name.replace(" ", "_")
    safe_company = posting_company.replace(" ", "_")
    safe_role = posting_role.replace(" ", "_")

    session_dir = os.path.join(settings.DELIVERABLES_DIR, str(session.id))
    os.makedirs(session_dir, exist_ok=True)

    # Read base resume if it exists
    base_resume_path = os.path.join(session_dir, f"{safe_name}_Resume_FINAL.md")
    base_resume = ""
    if os.path.exists(base_resume_path):
        with open(base_resume_path, "r", encoding="utf-8") as f:
            base_resume = f.read()

    # Generate targeted resume variant (summary rewrite only)
    targeted_md = await _generate_with_claude(
        system=(
            f"You are a resume writer specializing in job targeting.\n\n{rules}\n\n{output_formats}\n\n"
            f"Rules for targeted variants:\n"
            f"- Rewrite ONLY the Professional Summary section to incorporate keywords and priorities from the job posting\n"
            f"- Keep ALL other sections (Key Achievements, Experience, Certifications, Core Competencies) exactly as-is\n"
            f"- Weave keywords naturally — the summary must read like the candidate wrote it, not keyword stuffing\n"
            f"- Extract 10-15 key terms from the posting and use exact phrases where they fit naturally\n"
            f"- Flag any keywords the resume doesn't support with a comment: <!-- GAP: [keyword] -->\n"
        ),
        user_content=(
            f"Job Posting — {posting_company} ({posting_role}):\n\n{posting_text}\n\n"
            f"Base Resume:\n\n{base_resume if base_resume else discovery_md}\n\n"
            f"Generate the targeted resume variant. Rewrite only the Summary."
        ),
    )
    targeted_filename = f"{safe_name}_Resume_{safe_company}_{safe_role}.md"
    targeted_path = os.path.join(session_dir, targeted_filename)
    _write_file(targeted_path, targeted_md)
    await _save_deliverable(db, session, "resume_targeted_md", targeted_filename, targeted_path)

    # Convert to DOCX
    targeted_docx_filename = f"{safe_name}_Resume_{safe_company}_{safe_role}.docx"
    targeted_docx_path = os.path.join(session_dir, targeted_docx_filename)
    template_path = os.path.join(settings.TEMPLATES_DIR, "resume_template.docx")
    if os.path.exists(template_path):
        _pandoc_convert(targeted_path, targeted_docx_path, template_path)
        await _save_deliverable(db, session, "resume_targeted_docx", targeted_docx_filename, targeted_docx_path)

    # Optional cover letter
    if include_cover_letter:
        cover_letter_md = await _generate_with_claude(
            system=f"You are a cover letter writer.\n\n{output_formats}",
            user_content=(
                f"Job Posting — {posting_company} ({posting_role}):\n\n{posting_text}\n\n"
                f"Candidate Discovery Data:\n\n{discovery_md}\n\n"
                f"Base Resume:\n\n{base_resume if base_resume else ''}\n\n"
                f"Write a targeted cover letter for this specific role and company. "
                f"Follow the cover letter format in the output formats guide exactly."
            ),
        )
        cl_filename = f"{safe_name}_Cover_Letter_{safe_company}.md"
        cl_path = os.path.join(session_dir, cl_filename)
        _write_file(cl_path, cover_letter_md)
        await _save_deliverable(db, session, "cover_letter_md", cl_filename, cl_path)

        cl_docx_filename = f"{safe_name}_Cover_Letter_{safe_company}.docx"
        cl_docx_path = os.path.join(session_dir, cl_docx_filename)
        if os.path.exists(template_path):
            _pandoc_convert(cl_path, cl_docx_path, template_path)
            await _save_deliverable(db, session, "cover_letter_docx", cl_docx_filename, cl_docx_path)

    await db.commit()


async def _generate_with_claude(system: str, user_content: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text


async def _save_deliverable(
    db, session: Session, dtype: str, filename: str, file_path: str
) -> None:
    deliverable = Deliverable(
        session_id=session.id,
        type=dtype,
        filename=filename,
        file_path=file_path,
    )
    db.add(deliverable)
    await db.flush()


def _write_file(path: str, content: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _pandoc_convert(md_path: str, docx_path: str, template_path: str) -> None:
    try:
        subprocess.run(
            [
                "pandoc",
                md_path,
                "-o",
                docx_path,
                f"--reference-doc={template_path}",
            ],
            check=True,
            capture_output=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass  # DOCX generation is best-effort
