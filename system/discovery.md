# Discovery Interview Process

This file defines how to conduct the discovery interview. Ask questions ONE AT A TIME. Save every answer to the candidate's `discovery.md` immediately — do not batch.

---

## Interview Flow

### 1. Target Role
**Ask:** What specific role(s) are you targeting? (e.g., "Senior NetSuite Administrator", "Staff Software Engineer", "Controller")

Save the answer, then proceed.

### 2. Hidden Achievements
**Ask:** What accomplishments are NOT on your resume but you know you achieved? Think about: cost savings, error reductions, revenue impact, efficiency gains, team growth, process improvements.

Push back if answers are vague. Help them find the numbers.

### 3. Metrics Discovery (Per Role)
For each role on the resume, ask to uncover specific numbers:
- How many users/people did you support or manage?
- What was the company revenue/size/headcount?
- How many transactions/records/requests did you process?
- What percentage improvements did you achieve?
- How much time/money did you save?
- What was the scale of what you managed (budget, systems, locations)?

**Do not accept "a lot" or "many" — push for estimates.** Even rough numbers are better than none.

### 4. Skills Emphasis
**Ask:** Are there skills you want to emphasize more? Skills you want to downplay or remove?

### 5. Employment Gaps
**Ask:** Are there any gaps in employment I should know about? How should we address them?

If no gaps exist, note it and move on.

### 6. Certifications
**Ask:** Any certifications completed, in progress, or planned that are not on the resume?

### 7. Skills Matrix (Profile-Driven)
Load the selected industry profile from `profiles/`. For each skill category in the profile:
- Read the category description to the candidate
- Ask them to rate their proficiency level
- Skip categories that are not relevant

Save each rating immediately.

---

## Probing Techniques

When a candidate gives a weak answer, use these:

- **"What changed because of that?"** — Forces outcome thinking
- **"If you had to put a number on it..."** — Forces quantification
- **"What would have happened if you hadn't done that?"** — Reveals impact
- **"How many people/dollars/hours were involved?"** — Reveals scale
- **"What was it before vs. after?"** — Forces before/after comparison

---

## Discovery File Format

Save answers to `candidates/[name]/discovery.md` using this structure:

```markdown
# Discovery Session — [Full Name]

**Status:** IN_PROGRESS | COMPLETE
**Phase:** Discovery (Question X)
**Profile:** [profile name]
**Last Updated:** [date]

---

## Initial Review
[Observations from Phase 1]

## Target Role
[Answer]

## Hidden Achievements
- [Achievement with metrics]

## Role-Specific Metrics

### [Company — Title (dates)]
- [Metric]
- [Metric]

## Skills Emphasis
[Answer]

## Employment Gaps
[Answer]

## Certifications
[Answer]

## Skills Matrix Ratings
| Category | Proficiency |
|----------|-------------|
| [Skill]  | [Level]     |
```

---

## When to Move On

Move to Phase 3 (Resume Transformation) when:
- All 7 question areas have been covered
- Each role has at least 3-4 quantified data points
- The skills matrix ratings are complete for all relevant categories
- The candidate has nothing more to add

Update the discovery file status to `COMPLETE` before proceeding.
