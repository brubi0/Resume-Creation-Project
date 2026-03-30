import json
import os
import re
from functools import lru_cache

from app.config import settings
from app.models import Session


def _format_discovery_for_prompt(discovery_data: dict) -> str:
    """Format discovery_data as readable markdown for Claude context."""
    if not discovery_data:
        return "None yet — start with question 1."
    lines = []
    for key, value in discovery_data.items():
        label = key.replace("_", " ").title()
        if isinstance(value, (dict, list)):
            lines.append(f"- **{label}:** {json.dumps(value)}")
        else:
            lines.append(f"- **{label}:** {value}")
    return "\n".join(lines)


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


def get_profile_metadata() -> list[dict]:
    """Return list of dicts with slug, name, industry, and target_roles parsed from each profile."""
    files = _load_system_files()
    result = []
    for key, content in files.items():
        if not key.startswith("profile_"):
            continue
        slug = key[len("profile_"):]
        name = slug.replace("_", " ").title()
        industry = ""
        target_roles = ""
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("# Profile:"):
                name = line[len("# Profile:"):].strip()
            elif line.startswith("**Industry:**"):
                industry = line[len("**Industry:**"):].strip()
            elif line.startswith("**Target Roles:**"):
                target_roles = line[len("**Target Roles:**"):].strip()
        result.append(
            {"slug": slug, "name": name, "industry": industry, "target_roles": target_roles}
        )
    result.sort(key=lambda x: x["name"])
    return result


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
        if session.resume_text:
            parts.append(
                f"\n## Candidate's Existing Resume\n"
                "The candidate has uploaded their current resume. Use it to understand "
                "their background, detect experience level, and identify what needs improvement.\n\n"
                f"```\n{session.resume_text}\n```"
            )

    elif session.phase == 2:
        # Discovery interview
        total_questions = 9 if session.experience_level == "early_career" else 12
        answered = len(session.discovery_data) if session.discovery_data else 0
        current_q = min(answered + 1, total_questions)

        parts.append("\n## Your Task: Discovery Interview (Phase 2)\n")
        resuming = answered > 0
        if resuming:
            parts.append(
                f"**RESUMING SESSION** — The candidate has already answered {answered} question(s). "
                f"Do NOT re-ask questions that are already answered (see 'Discovery Data Collected So Far'). "
                f"Pick up exactly where you left off.\n"
            )
        parts.append(
            f"**STRICT RULE — ONE QUESTION AT A TIME:**\n"
            f"You are on question {current_q} of {total_questions}. "
            f"Look at the 'Discovery Data Collected So Far' section to see what has already been answered. "
            f"Find the FIRST question in the list below that does NOT yet have an answer in the collected data. "
            f"Ask ONLY that single question. Do NOT ask multiple questions in the same message. "
            f"Do NOT move on until the candidate has answered the current question.\n"
        )
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
        if session.resume_text:
            parts.append(
                f"\n## Candidate's Existing Resume\n```\n{session.resume_text}\n```"
            )
        formatted = _format_discovery_for_prompt(session.discovery_data or {})
        parts.append(f"\n## Discovery Data Collected So Far\n{formatted}")

    elif session.phase == 3:
        # Resume transformation
        parts.append("\n## Your Task: Resume Transformation (Phase 3)\n")
        parts.append(
            "**MANDATORY PROCESS — follow in order, do not skip steps:**\n\n"
            "**Step 1 — Build the draft internally.**\n"
            "Write the full resume in markdown following the rules below. Do not show this to the candidate yet.\n\n"
            "**Step 2 — Run the self-audit checklist.**\n"
            "Check every bullet against the Final Checklist in the resume rules:\n"
            "- Does every bullet start with a strong past-tense action verb?\n"
            "- Does every bullet have at least one metric (%, $, count, time saved)? If not, cut or rewrite it.\n"
            "- Is there any task-only language ('Responsible for', 'Helped with', 'Assisted in')? Replace it.\n"
            "- Are there any weak verbs ('Worked on', 'Participated in', 'Was involved in')? Replace them.\n"
            "- Does the Summary/Profile section have a clear value proposition with a target role and one differentiator?\n"
            "- Is the section order correct for the track (experienced: Summary → Experience → Skills → Education)?\n"
            "- Are dates consistent and in the correct format?\n"
            "Fix any issues before proceeding.\n\n"
            "**Step 3 — Run the 7-second recruiter eye test.**\n"
            "Imagine a recruiter skimming for 7 seconds. Ask yourself:\n"
            "- Is the target role obvious from the top third of the resume?\n"
            "- Do the bullets lead with impact, not tasks?\n"
            "- Would a recruiter be compelled to read further?\n"
            "If not, revise the top third and the strongest bullets.\n\n"
            "**Step 4 — Present the polished resume to the candidate.**\n"
            "Only after completing steps 1-3, present the final resume in markdown. "
            "Briefly summarize the 2-3 strongest changes you made and why. "
            "Ask the candidate if they want any adjustments.\n"
        )
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
        if session.resume_text:
            parts.append(
                f"\n## Candidate's Existing Resume\n```\n{session.resume_text}\n```"
            )
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
