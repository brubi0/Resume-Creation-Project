import json
import os
import re
from functools import lru_cache

from app.config import settings
from app.models import Session


@lru_cache(maxsize=1)
def _load_system_files() -> dict[str, str]:
    """Load all markdown files from system/ and profiles/ directories."""
    files = {}
    system_dir = settings.SYSTEM_DIR
    if os.path.isdir(system_dir):
        for fname in os.listdir(system_dir):
            if fname.endswith(".md"):
                key = fname.replace(".md", "")
                with open(os.path.join(system_dir, fname), "r", encoding="utf-8") as f:
                    files[f"system_{key}"] = f.read()

    profiles_dir = settings.PROFILES_DIR
    if os.path.isdir(profiles_dir):
        for fname in os.listdir(profiles_dir):
            if fname.endswith(".md") and fname != "README.md":
                key = fname.replace(".md", "")
                with open(
                    os.path.join(profiles_dir, fname), "r", encoding="utf-8"
                ) as f:
                    files[f"profile_{key}"] = f.read()

    return files


def reload_system_files():
    """Clear cache so files are re-read on next call."""
    _load_system_files.cache_clear()


def get_available_profiles() -> list[str]:
    """Return list of profile slugs available on disk."""
    profiles_dir = settings.PROFILES_DIR
    if not os.path.isdir(profiles_dir):
        return []
    return [
        f.replace(".md", "")
        for f in os.listdir(profiles_dir)
        if f.endswith(".md") and f != "README.md"
    ]


META_PATTERN = re.compile(r"<!--META:(.*?)-->", re.DOTALL)


def extract_meta(text: str) -> tuple[str, dict]:
    """Extract and strip META blocks from assistant response.

    Returns (cleaned_text, meta_dict).
    """
    meta = {}
    match = META_PATTERN.search(text)
    if match:
        try:
            meta = json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
        text = META_PATTERN.sub("", text).strip()
    return text, meta


def parse_session_updates(meta: dict) -> dict:
    """Convert META dict into session field updates."""
    updates = {}
    if "phase" in meta:
        updates["phase"] = int(meta["phase"])
    if "experience_level" in meta:
        updates["experience_level"] = meta["experience_level"]
    if "profile_slug" in meta:
        updates["profile_slug"] = meta["profile_slug"]
    if "status" in meta:
        updates["status"] = meta["status"]
    if "discovery_update" in meta and isinstance(meta["discovery_update"], dict):
        updates["_discovery_merge"] = meta["discovery_update"]
    return updates


_META_INSTRUCTIONS = """
IMPORTANT — Phase transition and data capture protocol:
When you complete a phase, detect the experience level, select a profile, or capture
structured discovery data, append a metadata block at the END of your message:

<!--META:{"phase": <number>, "experience_level": "<experienced|early_career>", "profile_slug": "<slug>", "status": "<active|interview_complete>", "discovery_update": {<key>: <value>}}-->

Only include the fields that changed. The user will NOT see this block.
Examples:
- After profile selection: <!--META:{"profile_slug": "financial_controller", "phase": 1}-->
- After detecting experience level: <!--META:{"experience_level": "experienced", "phase": 2}-->
- After capturing a discovery answer: <!--META:{"discovery_update": {"target_role": "Financial Controller"}}-->
- After completing all discovery questions: <!--META:{"phase": 3}-->
- After finishing the resume: <!--META:{"status": "interview_complete"}-->
"""


def build_system_prompt(session: Session) -> str:
    """Build the system prompt for Claude based on the current session phase."""
    files = _load_system_files()
    profiles_list = get_available_profiles()
    parts = []

    parts.append(
        "You are a professional resume consultant conducting a structured interview "
        "to build an exceptional resume. You are warm, encouraging, and thorough. "
        "You ask questions ONE AT A TIME and probe for specifics and metrics."
    )

    if session.phase == 0:
        # Profile selection
        parts.append("\n## Your Task: Profile Selection (Phase 0)\n")
        workflow = files.get("system_workflow", "")
        # Extract Phase 0 section
        phase0 = _extract_section(workflow, "## Phase 0", "## Phase 1")
        if phase0:
            parts.append(phase0)
        parts.append(f"\nAvailable profiles: {', '.join(profiles_list) if profiles_list else 'None — you will need to generate one'}")
        parts.append(
            "\nAsk the candidate about their industry and target role. "
            "Match them to an available profile or note that one needs to be generated."
        )

    elif session.phase == 1:
        # Initial review + experience level detection
        parts.append("\n## Your Task: Initial Review (Phase 1)\n")
        workflow = files.get("system_workflow", "")
        phase1 = _extract_section(workflow, "## Phase 1", "## Phase 2")
        if phase1:
            parts.append(phase1)
        if session.profile_slug:
            profile = files.get(f"profile_{session.profile_slug}", "")
            if profile:
                parts.append(f"\n## Selected Profile\n{profile}")

    elif session.phase == 2:
        # Discovery interview
        parts.append("\n## Your Task: Discovery Interview (Phase 2)\n")
        if session.experience_level == "early_career":
            discovery = files.get("system_discovery_early_career", "")
        else:
            discovery = files.get("system_discovery", "")
        if discovery:
            parts.append(discovery)
        if session.profile_slug:
            profile = files.get(f"profile_{session.profile_slug}", "")
            if profile:
                parts.append(f"\n## Industry Profile\n{profile}")
        if session.discovery_data:
            parts.append(
                f"\n## Discovery Data Collected So Far\n```json\n{json.dumps(session.discovery_data, indent=2)}\n```"
            )

    elif session.phase == 3:
        # Resume transformation
        parts.append("\n## Your Task: Resume Transformation (Phase 3)\n")
        if session.experience_level == "early_career":
            rules = files.get("system_resume_rules_early_career", "")
        else:
            rules = files.get("system_resume_rules", "")
        if rules:
            parts.append(rules)
        output_formats = files.get("system_output_formats", "")
        if output_formats:
            resume_section = _extract_section(
                output_formats, "## 1. Resume", "## 2."
            )
            if resume_section:
                parts.append(f"\n## Output Format\n{resume_section}")
        if session.discovery_data:
            parts.append(
                f"\n## Complete Discovery Data\n```json\n{json.dumps(session.discovery_data, indent=2)}\n```"
            )

    elif session.phase >= 4:
        # Deliverable generation phases (4=Interview Prep, 5=Skills Matrix, 6=Score Card)
        phase_names = {4: "Interview Prep", 5: "Skills Matrix", 6: "Score Card"}
        phase_name = phase_names.get(session.phase, f"Phase {session.phase}")
        parts.append(f"\n## Your Task: Generate {phase_name} (Phase {session.phase})\n")
        output_formats = files.get("system_output_formats", "")
        if output_formats:
            parts.append(output_formats)
        if session.discovery_data:
            parts.append(
                f"\n## Discovery Data\n```json\n{json.dumps(session.discovery_data, indent=2)}\n```"
            )

    # Inject job description if provided — influences all phases
    if session.job_description:
        parts.append(
            "\n## Target Job Description\n"
            "The candidate has provided a specific job posting they are targeting. "
            "Use this to guide your questions, prioritize relevant experience, "
            "tailor resume language to match the role's requirements, and ensure "
            "the final resume addresses the key qualifications listed below.\n\n"
            f"```\n{session.job_description}\n```"
        )

    parts.append(_META_INSTRUCTIONS)
    return "\n\n".join(parts)


def _extract_section(text: str, start_header: str, end_header: str) -> str:
    """Extract a section of markdown between two headers."""
    start_idx = text.find(start_header)
    if start_idx == -1:
        return ""
    end_idx = text.find(end_header, start_idx + len(start_header))
    if end_idx == -1:
        return text[start_idx:]
    return text[start_idx:end_idx].strip()
