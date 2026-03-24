# Discovery Interview Process

This file defines how to conduct the discovery interview. Ask questions ONE AT A TIME. Save every answer to the candidate's `discovery.md` immediately — do not batch.

---

## Interview Flow

### 1. Target Role & Positioning
**Ask:** What specific role are you targeting? If you had an offer tomorrow, what would the title be?

If they list multiple roles, follow up:
- **"Which one is your #1 priority?"** — This becomes the primary. The resume is built for this role.
- **"Are the others backup options or equal priorities?"** — If significantly different (e.g., Controller vs. Consultant), note that separate resume versions may be needed.

Save the primary target role. Note alternates separately.

### 2. Career Narrative
**Ask:** In one sentence, what's the through-line of your career? What's the story you want a recruiter to take away?

If they struggle, offer framing options:
- "Are you a finance person who became a consultant, or a consultant who specializes in finance?"
- "Are you a turnaround specialist, a builder, or an optimizer?"
- "What's the pattern across your roles — what do people keep hiring you to do?"

This answer shapes the entire resume angle.

### 3. Differentiator
**Ask:** If a recruiter has 50 resumes on their desk for this role, what makes you different? What can you do that most other candidates can't?

Push back if the answer is generic ("I'm a hard worker", "I'm detail-oriented"). Look for:
- A rare combination of skills (e.g., "I'm a CPA who can also write SuiteScript")
- A specific track record (e.g., "I've walked into 3 broken finance departments and fixed all of them")
- A niche (e.g., "I specialize in QuickBooks-to-NetSuite migrations for manufacturing companies")

### 4. Hidden Achievements
**Ask:** What accomplishments are NOT on your resume but you know you achieved? Think about: cost savings, error reductions, revenue impact, efficiency gains, team growth, process improvements.

Push back if answers are vague. Help them find the numbers.

### 5. Metrics Discovery (Per Role)
For each role on the resume, ask to uncover specific numbers:
- How many users/people did you support or manage?
- What was the company revenue/size/headcount?
- How many transactions/records/requests did you process?
- What percentage improvements did you achieve?
- How much time/money did you save?
- What was the scale of what you managed (budget, systems, locations)?
- What was the situation when you arrived? (Turnaround? Growth? Maintenance?)

**Do not accept "a lot" or "many" — push for estimates.** Even rough numbers are better than none.

### 6. Leadership & Influence
**Ask:** Tell me about the people side of your work:
- Did you build, inherit, or manage a team? How many people?
- Did you train or mentor anyone? How many?
- Did you present to executives or the board?
- Did you make a decision that changed the direction of a project or department?
- Did anyone come to you as the go-to expert on something?

These signals matter — especially for senior roles (Controller, Manager, Director). A recruiter wants to know if you led or just executed.

### 7. Skills Emphasis
**Ask:** Are there skills you want to emphasize more? Skills you want to downplay or remove?

### 8. Employment Gaps
**Ask:** Are there any gaps in employment I should know about? How should we address them?

If no gaps exist, note it and move on.

### 9. Certifications
**Ask:** Any certifications completed, in progress, or planned that are not on the resume?

### 10. Education
**Ask:** What's your education background? Do you have a degree? If so, what field?

Handle based on the answer:
- **Degree:** Will include in resume
- **Partial / coursework only:** Will likely omit — 10+ years of experience and certifications carry more weight
- **No degree:** Will omit the section entirely — let the career speak

Be direct but respectful. Many strong candidates don't have degrees and don't need them on the resume.

### 11. Context Questions
**Ask these if relevant** (skip if not):
- **"Why are you looking?"** — Layoff, growth, escape, relocation. This affects positioning tone (confident vs. urgent)
- **"What do you NOT want in your next role?"** — Reveals what to downplay
- **"What would your best boss say about you in one sentence?"** — Uncovers soft differentiators the candidate won't volunteer
- **"What's the biggest mess you walked into and cleaned up?"** — This is almost always the best resume bullet and interview story

### 12. Skills Matrix (Profile-Driven)
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
- **"Would your manager agree with that number?"** — Gut-checks inflated claims
- **"What did that mean for the business?"** — Elevates from task to business impact

---

## Discovery File Format

Save answers to `candidates/[name]/discovery.md` using this structure:

```markdown
# Discovery Session — [Full Name]

**Status:** IN_PROGRESS | COMPLETE
**Phase:** Discovery (Question X of 12)
**Profile:** [profile name]
**Primary Target Role:** [role]
**Alternate Targets:** [roles, if any]
**Last Updated:** [date]

---

## Career Narrative
[One-sentence through-line]

## Differentiator
[What makes them different from 50 other candidates]

## Initial Review
[Observations from Phase 1]

## Target Role
[Primary target and reasoning]

## Hidden Achievements
- [Achievement with metrics]

## Role-Specific Metrics

### [Company — Title (dates)]
**Situation when arrived:** [context]
- [Metric]
- [Metric]

## Leadership & Influence
- [Team size, mentoring, executive interaction, decisions made]

## Skills Emphasis
[Answer]

## Employment Gaps
[Answer or "None"]

## Certifications
[Answer]

## Education
[Answer and recommendation: include, omit, or partial]

## Context
- Why looking: [answer]
- What to avoid: [answer]
- Best boss quote: [answer]
- Biggest mess cleaned up: [answer]

## Skills Matrix Ratings
| Category | Proficiency |
|----------|-------------|
| [Skill]  | [Level]     |
```

---

## When to Move On

Move to Phase 3 (Resume Transformation) when:
- All question areas have been covered (skip irrelevant ones)
- Each role has at least 3-4 quantified data points
- The career narrative and differentiator are clear
- The skills matrix ratings are complete for all relevant categories
- The candidate has nothing more to add

Update the discovery file status to `COMPLETE` before proceeding.
