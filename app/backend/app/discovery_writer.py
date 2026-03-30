"""Write and read the per-session discovery.md file on disk.

The file lives at:  {DELIVERABLES_DIR}/{session_id}/discovery.md

It is the human-readable source of truth for all discovery data captured
during the interview.  It is written after every discovery update so that:
  - Admins can inspect progress without querying the DB
  - Deliverables generation uses a rich, formatted document rather than raw JSON
  - Session resumption context is richer for Claude
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from app.config import settings
from app.models import Session


# Map discovery_data keys to human-readable labels
_KEY_LABELS: dict[str, str] = {
    "candidate_name": "Candidate Name",
    "target_role": "Target Role",
    "alternate_roles": "Alternate Roles",
    "career_narrative": "Career Narrative",
    "differentiator": "Differentiator",
    "hidden_achievements": "Hidden Achievements",
    "metrics_per_role": "Metrics by Role",
    "leadership_influence": "Leadership & Influence",
    "technical_skills": "Technical Skills",
    "certifications": "Certifications",
    "education": "Education",
    "biggest_win": "Biggest Win",
    "biggest_challenge": "Biggest Challenge / Turnaround",
    "soft_skills": "Soft Skills",
    "work_style": "Work Style & Preferences",
    "why_this_field": "Why This Field",
    "projects": "Projects",
    "internships": "Internships",
    "transferable_skills": "Transferable Skills",
    "activities": "Activities & Organizations",
    "gpa": "GPA",
    "skills_proficiency": "Skills & Proficiency",
}


def _label(key: str) -> str:
    return _KEY_LABELS.get(key, key.replace("_", " ").title())


def session_dir(session: Session) -> str:
    return os.path.join(settings.DELIVERABLES_DIR, str(session.id))


def discovery_md_path(session: Session) -> str:
    return os.path.join(session_dir(session), "discovery.md")


def write_discovery_md(session: Session) -> None:
    """Write (or overwrite) the discovery.md file for this session."""
    os.makedirs(session_dir(session), exist_ok=True)

    lines: list[str] = []

    # --- Header ---
    lines.append("# Discovery File\n")
    lines.append(f"**Status:** {session.status}")
    lines.append(f"**Phase:** {session.phase}")
    if session.experience_level:
        lines.append(f"**Experience Level:** {session.experience_level.replace('_', ' ').title()}")
    if session.profile_slug:
        lines.append(f"**Industry Profile:** {session.profile_slug}")
    if session.job_description:
        lines.append("**Job Description:** *(attached below)*")
    lines.append(f"**Last Updated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    # --- Discovery data ---
    data = session.discovery_data or {}
    if data:
        lines.append("---\n")
        lines.append("## Discovery Data\n")
        for key, value in data.items():
            label = _label(key)
            if isinstance(value, dict):
                lines.append(f"**{label}:**")
                for k, v in value.items():
                    lines.append(f"  - {k}: {v}")
            elif isinstance(value, list):
                lines.append(f"**{label}:**")
                for item in value:
                    lines.append(f"  - {item}")
            else:
                lines.append(f"**{label}:** {value}")
        lines.append("")
    else:
        lines.append("---\n")
        lines.append("## Discovery Data\n")
        lines.append("*No discovery data collected yet.*\n")

    # --- Job description ---
    if session.job_description:
        lines.append("---\n")
        lines.append("## Target Job Description\n")
        lines.append("```")
        lines.append(session.job_description)
        lines.append("```\n")

    path = discovery_md_path(session)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def read_discovery_md(session: Session) -> str | None:
    """Return the discovery.md content, or None if it doesn't exist."""
    path = discovery_md_path(session)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return f.read()
