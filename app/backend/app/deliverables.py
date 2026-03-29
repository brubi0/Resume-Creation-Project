import json
import os
import subprocess

import anthropic

from app.config import settings
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
        user_content=f"Generate the final resume based on this discovery data:\n```json\n{discovery_json}\n```",
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
        user_content=f"Generate interview prep based on this discovery data:\n```json\n{discovery_json}\n```\n\nResume:\n{resume_md}",
    )
    prep_md_path = os.path.join(session_dir, f"{safe_name}_Interview_Prep.md")
    _write_file(prep_md_path, prep_md)
    await _save_deliverable(db, session, "interview_prep_md", f"{safe_name}_Interview_Prep.md", prep_md_path)

    # --- Generate Skills Matrix (HTML) ---
    profile = files.get(f"profile_{session.profile_slug}", "") if session.profile_slug else ""
    matrix_html = await _generate_with_claude(
        system=f"Generate a skills matrix as a complete HTML file with embedded CSS.\n\n{output_formats}\n\nProfile:\n{profile}",
        user_content=f"Generate the skills matrix based on:\n```json\n{discovery_json}\n```",
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
