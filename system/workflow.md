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
- Areas that need clarification from the candidate

Write initial observations to `candidates/[name]/discovery.md` under the `## Initial Review` section.

→ Proceed to Phase 2

---

## Phase 2: Discovery Interview

Conduct the discovery interview following the process in `system/discovery.md`.

**Critical rules:**
- Ask questions ONE AT A TIME
- Save each answer to `candidates/[name]/discovery.md` immediately
- If the session is interrupted, resume from where you left off by reading the discovery file

→ Proceed to Phase 3 when all questions are answered

---

## Phase 3: Resume Transformation

Rewrite the resume following the rules in `system/resume_rules.md`.

1. Generate the resume in markdown
2. Save to `candidates/[name]/output/[Name]_Resume_DRAFT.md`
3. Convert to DOCX using pandoc: `pandoc [draft].md -o [draft].docx --reference-doc="templates/resume_template.docx"`
4. Present to the candidate for review
5. Iterate based on feedback
6. Save final version as `[Name]_Resume_FINAL.md` and `.docx`

→ Proceed to Phase 4

---

## Phase 4: Interview Prep Document

Create an interview prep document following the format in `system/output_formats.md`.

1. Select the 5-7 strongest resume points
2. Write STAR-format answers for each
3. Save to `candidates/[name]/output/[Name]_Interview_Prep.md` and `.docx`

→ Proceed to Phase 5

---

## Phase 5: Skills Matrix

Create a skills matrix based on discovery interview answers and the selected profile.

1. Use the proficiency ratings collected during discovery
2. Generate HTML with embedded CSS using the format in `system/output_formats.md`
3. Save to `candidates/[name]/output/[Name]_Skills_Matrix.html`

→ Done

---

## Resuming a Session

When the user says "continue working on [name]'s resume" or similar:

1. Find the candidate directory under `candidates/[name]/`
2. Read `candidates/[name]/discovery.md`
3. Check the `Status` field to determine where we left off
4. Resume from that phase/question

---

## Updating an Existing Resume

When the user says "update [name]'s resume" or similar:

1. Load the existing output from `candidates/[name]/output/`
2. Ask what changed (new cert, new role, new achievements, targeting a different position)
3. Update the discovery file with new information
4. Regenerate only the affected deliverables
5. Save as a new version (increment or use new date suffix)
