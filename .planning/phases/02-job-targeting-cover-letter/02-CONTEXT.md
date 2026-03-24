# Phase 2: Job Targeting + Cover Letter - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can paste a job posting, the system extracts keywords, generates a targeted resume variant (summary rewrite), and optionally generates a cover letter — all without re-running the full discovery interview.

Requirements: TARG-01 (ingest job posting), TARG-02 (extract and weave keywords), TARG-03 (generate targeted variant), DELV-05 (cover letter)

</domain>

<decisions>
## Implementation Decisions

### Job Posting Input
- **D-01:** User pastes job posting text directly (no URL fetching — keeps it simple and reliable)
- **D-02:** Posting text saved to `candidates/[name]/postings/[company]_[role].md` for reference, retargeting, and cover letter generation
- **D-03:** Claude extracts keywords, required skills, and priorities from the posting automatically — no manual keyword extraction by the user

### Keyword Integration
- **D-04:** Natural weave approach — use exact phrases from the posting where they fit naturally, paraphrase others. Should read like the candidate wrote it, not keyword stuffing.
- **D-05:** Only the Summary section is adjusted for the targeted variant. Key Achievements, experience bullets, and Core Competencies remain unchanged from the base resume.
- **D-06:** The targeted variant is a lightweight overlay — not a full rewrite. This makes it fast to generate for multiple postings.

### Cover Letter
- **D-07:** 3-4 paragraphs: opening hook, 1-2 body paragraphs connecting candidate to role, closing with call to action. Fits on one page.
- **D-08:** Professional + personal tone — confident but warm. References the specific company and role by name. Uses candidate's discovery data (career narrative, differentiator, biggest win) to make it genuine.
- **D-09:** Cover letter is optional — user can skip it and just get the targeted resume variant.

### Claude's Discretion
- File organization for variants: Claude decides naming convention for targeted files (e.g., `[Name]_Resume_[Company].md`)
- How many keywords to extract from a posting (recommend 10-15 key terms)
- Whether to flag keywords that the candidate's resume doesn't naturally support (potential gap alert)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Resume System
- `system/workflow.md` — Master orchestrator; "Generating a Variant" section already exists for different target roles
- `system/resume_rules.md` — Resume standards including ATS compatibility rules (keywords must follow these)
- `system/output_formats.md` — Current deliverable specs; cover letter format needs to be added here

### Existing Variant Support
- `system/workflow.md` §Generating a Variant — Already defines how to rewrite summary and Key Achievements for a different target role. Job targeting extends this pattern.

### Discovery Data
- `system/discovery.md` — Career narrative, differentiator, and "biggest mess cleaned up" feed into the cover letter

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `system/workflow.md` "Generating a Variant" section — already has the pattern for creating alternate versions without re-interviewing
- `system/resume_rules.md` ATS section — keyword rules that apply to targeted variants
- `generate.sh` — Pandoc automation that could be extended for cover letter DOCX generation

### Established Patterns
- Deliverables follow markdown → DOCX (via pandoc) pattern
- Output formats are defined in `system/output_formats.md`
- Per-candidate directory structure under `candidates/[name]/`

### Integration Points
- New `postings/` subdirectory under each candidate
- Cover letter format added to `system/output_formats.md`
- Workflow.md needs a new "Job Targeting" section or extension to the variant flow

</code_context>

<specifics>
## Specific Ideas

- The summary-only approach is deliberate — minimal changes, fast to generate, lets you target 5 postings in 5 minutes instead of rewriting the whole resume each time
- Cover letter must reference discovery data (career narrative, differentiator) — this is what makes it feel genuine vs. templated
- Posting text is saved so you can retarget later or generate a cover letter after the fact

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-job-targeting-cover-letter*
*Context gathered: 2026-03-23*
