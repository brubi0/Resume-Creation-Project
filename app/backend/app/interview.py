"""Interview question ids and progress (ids come from system/discovery*.md).

The app, not the model, decides which question is next: progress() derives it
from discovery_data, so a refresh or a resumed session lands on the right id.
"""

EXPERIENCED_QUESTION_IDS = [
    "target_role", "career_narrative", "differentiator", "hidden_achievements",
    "metrics_per_role", "leadership_influence", "skills_emphasis", "employment_gaps",
    "certifications", "education", "context", "skills_matrix",
]

EARLY_CAREER_QUESTION_IDS = [
    "target_role", "education", "projects", "work_experience", "internships",
    "certifications_skills", "activities", "differentiator", "skills_matrix",
]

QUESTION_LABELS = {
    "target_role": "Target role",
    "career_narrative": "Career narrative",
    "differentiator": "What sets them apart",
    "hidden_achievements": "Hidden achievements",
    "metrics_per_role": "Metrics by role",
    "leadership_influence": "Leadership and influence",
    "skills_emphasis": "Skills to emphasize",
    "employment_gaps": "Employment gaps",
    "certifications": "Certifications",
    "education": "Education",
    "context": "Context (industry, career change, constraints)",
    "skills_matrix": "Skills matrix",
    "projects": "Projects",
    "work_experience": "Work experience",
    "internships": "Internships",
    "certifications_skills": "Certifications and skills",
    "activities": "Activities and organizations",
}


def required_question_ids(experience_level: str | None) -> list[str]:
    if experience_level == "early_career":
        return list(EARLY_CAREER_QUESTION_IDS)
    return list(EXPERIENCED_QUESTION_IDS)


def known_question_ids(experience_level: str | None) -> set[str]:
    """Ids valid for skipped_questions. Level not yet known: either track's ids."""
    if experience_level is None:
        return set(EXPERIENCED_QUESTION_IDS) | set(EARLY_CAREER_QUESTION_IDS)
    return set(required_question_ids(experience_level))


def _has_answer(v) -> bool:
    if v is None:
        return False
    if isinstance(v, (str, list, dict)):
        return len(v) > 0 and (not isinstance(v, str) or bool(v.strip()))
    return True


def progress_for(experience_level: str | None, data: dict | None):
    """(answered_ids, skipped_ids, next_id, total). Follow-up detail keys never count."""
    data = data or {}
    skipped_raw = data.get("skipped_questions")
    skipped_set = set(skipped_raw) if isinstance(skipped_raw, list) else set()
    ids = required_question_ids(experience_level)
    answered = [q for q in ids if _has_answer(data.get(q))]
    skipped = [q for q in ids if q in skipped_set and q not in answered]
    done = set(answered) | set(skipped)
    next_id = next((q for q in ids if q not in done), None)
    return answered, skipped, next_id, len(ids)


def discovery_complete_for(experience_level: str | None, data: dict | None) -> bool:
    """Every id answered or skipped, and contact present (it may hold only `omitted`)."""
    _, _, next_id, _ = progress_for(experience_level, data)
    return next_id is None and isinstance((data or {}).get("contact"), dict)


def progress(session):
    return progress_for(session.experience_level, session.discovery_data)


def discovery_complete(session) -> bool:
    return discovery_complete_for(session.experience_level, session.discovery_data)
