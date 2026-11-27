"""Interview question ids (from system/discovery*.md). Stage 5 extends this module."""

EXPERIENCED_QUESTION_IDS = [
    "target_role", "career_narrative", "differentiator", "hidden_achievements",
    "metrics_per_role", "leadership_influence", "skills_emphasis", "employment_gaps",
    "certifications", "education", "context", "skills_matrix",
]

EARLY_CAREER_QUESTION_IDS = [
    "target_role", "education", "projects", "work_experience", "internships",
    "certifications_skills", "activities", "differentiator", "skills_matrix",
]


def required_question_ids(experience_level: str | None) -> list[str]:
    if experience_level == "early_career":
        return list(EARLY_CAREER_QUESTION_IDS)
    return list(EXPERIENCED_QUESTION_IDS)
