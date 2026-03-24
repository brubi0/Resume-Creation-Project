# Resume Workflow

This is the master orchestrator for the resume creation system. Claude reads this file as the entry point and follows the phases in order.

---

## How to Start

When the user says "run the resume workflow", "start a new resume", or similar:

1. Check if a candidate name was provided
2. Check if a resume file exists in `input/` (quick start) or in `candidates/[name]/input/`
3. If no candidate directory exists, create one under `candidates/[name]/`
4. Begin Phase 0

---

## Phase 0: Profile Selection

Before starting the interview, determine which industry profile to use.

1. Check `profiles/` for existing profiles
2. Ask the candidate:
   - What industry are you in?
   - What is your target role/title?
   - Any must-have certifications, tools, or frameworks for this role?
3. If a matching profile exists, confirm it fits or offer to tweak it
4. If no profile exists, generate one:
   - Research 5-10 current job postings for the target role using web search
   - Extract common skills, group into categories
   - Define proficiency levels relevant to the industry
   - Save to `profiles/[role_slug].md`
5. Record the selected profile in the candidate's `discovery.md`

→ Proceed to Phase 1

---

## Phase 1: Initial Review

Read the candidate's existing resume (if provided) and identify:
- Current strengths
- Gaps and weaknesses
- Missing quantification
- Repetition issues
- Section ordering problems
- ATS compatibility issues (tables, columns, non-standard headers)
- Areas that need clarification from the candidate

Write initial observations to `candidates/[name]/discovery.md` under the `## Initial Review` section.

If no existing resume is provided, note "Starting from scratch" and proceed — the discovery interview will gather everything needed.

→ Proceed to Phase 2

---

## Phase 2: Discovery Interview

Conduct the discovery interview following the process in `system/discovery.md`.

**Critical rules:**
- Ask questions ONE AT A TIME
- Save each answer to `candidates/[name]/discovery.md` immediately
- If the session is interrupted, resume from where you left off by reading the discovery file
- Establish the career narrative and differentiator early — these shape everything that follows
- If the candidate lists multiple target roles, establish the primary before continuing

→ Proceed to Phase 3 when all questions are answered

---

## Phase 3: Resume Transformation

Rewrite the resume following the rules in `system/resume_rules.md`.

### 3a. Generate Draft
1. Build the resume in markdown following the **mandatory section order:**
   Header → Summary → Key Achievements → Experience → Certifications → Core Competencies
2. Target the summary and Key Achievements to the **primary target role**
3. Save to `candidates/[name]/output/[Name]_Resume_DRAFT.md`

### 3b. Self-Audit (Before Showing the Candidate)
Run the draft through every item in the Final Checklist from `system/resume_rules.md`. Specifically check:

- [ ] Header includes name + target role title
- [ ] Summary is targeted to primary role (not generic)
- [ ] Key Achievements section exists with 4-6 bullets
- [ ] Every bullet has a number — no exceptions
- [ ] No weak verbs (started, assisted, helped, participated)
- [ ] No task-only bullets (every bullet has an outcome)
- [ ] No repeated achievements across sections
- [ ] Certifications are NOT in a table
- [ ] Education is handled correctly (omitted if no degree and 10+ years)
- [ ] Section order is correct
- [ ] No ATS-hostile formatting

**If any item fails, fix it before presenting the draft.** Do not show a draft that violates the system's own rules.

### 3c. Recruiter Eye Test
Simulate a 7-second recruiter scan. Report to the candidate:
- "In 7 seconds, a recruiter would take away: [summary of impression]"
- "They would identify you as a: [role/level]"
- "The strongest signal is: [what stands out]"
- "The weakest spot is: [what's missing or unclear]"

If the takeaway doesn't match the target role, revise before presenting.

### 3d. Present and Iterate
1. Present the draft with the self-audit results and recruiter eye test
2. Ask for feedback — what sounds right, what doesn't sound like them, what's missing
3. Iterate based on feedback
4. Save final version as `[Name]_Resume_FINAL.md`
5. Convert to DOCX: `pandoc [final].md -o [final].docx --reference-doc="templates/resume_template.docx"`

→ Proceed to Phase 4

---

## Phase 4: Interview Prep Document

Create an interview prep document following the format in `system/output_formats.md`.

1. Select the 5-7 strongest resume bullets
2. Write STAR-format answers for each
3. Include the "biggest mess cleaned up" story from discovery if available
4. Save to `candidates/[name]/output/[Name]_Interview_Prep.md` and `.docx`

→ Proceed to Phase 5

---

## Phase 5: Skills Matrix

Create a skills matrix based on discovery interview answers and the selected profile.

1. Use the proficiency ratings collected during discovery
2. Generate HTML with embedded CSS using the format in `system/output_formats.md`
3. Save to `candidates/[name]/output/[Name]_Skills_Matrix.html`

→ Proceed to Phase 6

---

## Phase 6: Score Card

Generate a score card evaluating the final resume against the 6 criteria.

| Criteria | Score (1-10) | Notes |
|----------|-------------|-------|
| Clarity | | |
| Focus | | |
| Quantification | | |
| Results-Driven | | |
| Cuts Through Noise | | |
| Skimability | | |
| **Overall** | | |

Include:
- What the resume does well
- What could still be improved
- Whether the resume passes the 7-second test for the target role

Save to `candidates/[name]/output/[Name]_Score_Card.md`

→ Done

---

## Resuming a Session

When the user says "continue working on [name]'s resume" or similar:

1. Find the candidate directory under `candidates/[name]/`
2. Read `candidates/[name]/discovery.md`
3. Check the `Status` and `Phase` fields to determine where we left off
4. Resume from that phase/question

---

## Updating an Existing Resume

When the user says "update [name]'s resume" or similar:

1. Load the existing output from `candidates/[name]/output/`
2. Ask what changed (new cert, new role, new achievements, targeting a different position)
3. Update the discovery file with new information
4. Regenerate only the affected deliverables
5. Save as a new version (increment or use new date suffix)

---

## Generating a Variant for a Different Target Role

When the candidate targets a significantly different role:

1. Read the existing discovery file (don't re-interview)
2. Identify which target role this variant is for
3. Rewrite the summary and Key Achievements for that role
4. Re-prioritize experience bullets (same data, different emphasis)
5. Save as `[Name]_Resume_[RoleSlug]_FINAL.md`
