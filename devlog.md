# Resume Creation Project — Dev Log

Living document. Update this file whenever a meaningful change is made so context can be restored without re-reading the codebase.

---

## Project Purpose

Claude-powered system for creating and improving resumes through structured discovery interviews. Produces A+ resumes (top 5-10% of applicants), interview prep guides, skills matrices, and score cards. Works for any industry via auto-generated role profiles. Handles both experienced professionals and early-career candidates with dedicated tracks.

**Core Value:** Every resume produced by this system must make a recruiter stop and call the candidate — not just "good enough," but top-tier.

---

## Environment

| Environment | Detail |
|-------------|--------|
| Runtime     | None — document/prompt system only |
| Tooling     | Claude Code (CLI), Pandoc (DOCX generation) |
| Repo        | https://github.com/brubi0/Resume-Creation-Project |
| Privacy     | Candidate data gitignored (`candidates/`) — never committed |

---

## Tech Stack

| Layer       | Technology |
|-------------|------------|
| Prompts     | Markdown system files (`system/`) — workflow, discovery, resume rules, output formats |
| Profiles    | Markdown role profiles (`profiles/`) — skill categories, proficiency levels |
| Templates   | Pandoc reference DOCX (`templates/resume_template.docx`) |
| Automation  | Bash (`generate.sh`) — markdown to DOCX conversion |
| Output      | Markdown, DOCX (via Pandoc), HTML (Skills Matrix) |
| Planning    | GSD workflow (`.planning/`) — phases, plans, requirements traceability |

---

## Architecture

### Workflow Engine (`system/workflow.md`)

7-phase pipeline — Claude reads this as the entry point and follows phases in order:

| Phase | Name | Purpose |
|-------|------|---------|
| 0 | Profile Selection | Match/generate/clone industry profile for target role |
| 1 | Initial Review | Read existing resume, detect experience level, route to track |
| 2 | Discovery Interview | Structured interview (12 questions experienced, 9 early-career) |
| 3 | Resume Transformation | Generate draft, self-audit, recruiter eye test, iterate, finalize |
| 4 | Interview Prep | STAR-format answers for 5-7 strongest bullets |
| 5 | Skills Matrix | Color-coded HTML proficiency table from profile categories |
| 6 | Score Card | 6-criteria grading (Clarity, Focus, Quantification, Results-Driven, Noise, Skimability) |

### Two Candidate Tracks

| Track | Criteria | Key Differences |
|-------|----------|-----------------|
| Experienced | 3+ years | 12 discovery questions, 2-page max, every bullet must have a number |
| Early-Career | <3 years | 9 discovery questions, 1-page strict, education first, relaxed quantification |

### Profile System

- **Reference profile:** `profiles/netsuite_administrator.md` (85 lines, 3 skill groups, 20 categories)
- **Auto-generation:** Research 3-5 job postings → extract skills → build profile (`system/profile-generation-guide.md`)
- **Clone-and-tweak:** Copy existing profile if 60%+ overlap, adjust categories
- **Knowledge fallback:** If web search unavailable, generate from training knowledge with disclaimer

### Deliverables (5 types)

| Deliverable | Format | Status |
|-------------|--------|--------|
| Resume | MD → DOCX | Complete |
| Interview Prep | MD → DOCX | Complete |
| Skills Matrix | HTML (embedded CSS) | Complete |
| Score Card | MD | Complete (spec only — never generated for a real candidate) |
| Cover Letter | TBD | Phase 2 — not yet specified |

### Candidate Directory Structure

```
candidates/[name]/
  input/          # Original resume (DOCX, PDF)
  discovery.md    # Interview answers, incrementally saved
  output/         # Generated deliverables (Resume, Interview Prep, Skills Matrix, Score Card)
```

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| No code runtime | Document/prompt system only | Simplicity — just markdown, pandoc, and Claude |
| Candidate data gitignored | Privacy-first | Resumes contain PII |
| Markdown source format | Universal, versionable | No proprietary tools required |
| Self-audit before presenting draft | System enforces its own rules | Catches weak bullets, missing metrics, ATS issues before candidate sees it |
| Weak bullet filter | Auto-cut numberless, task-only, weak-verb bullets | Forces quantification — the #1 differentiator of A+ resumes |
| Industry profiles | Auto-generated per role | Can't manually create profiles for every industry |
| 60% overlap threshold | Clone vs. generate fresh decision rule | Simple enough to apply without deep analysis |
| 3-5 job postings (not 5-10) | Faster, sufficient signal for profile generation | Locked in Phase 1 (D-02) |
| Two candidate tracks | Fundamentally different resume strategies | Experienced and early-career candidates need different section order, rules, and tone |

---

## Candidate History

| Candidate | Track | Profile | Deliverables | Status |
|-----------|-------|---------|-------------|--------|
| Bruno Rubio | Experienced | NetSuite Administrator | Resume, Interview Prep, Skills Matrix, Score Card | Complete |
| Cindy Rubio | Experienced | NetSuite Administrator | Resume | Complete |
| Alex Martinez (synthetic) | Early-Career | NetSuite Administrator | Resume, Score Card | Test candidate |

---

## Change Log

### 2026-03-29 — Gap closure sprint (17/17 gaps closed)
Comprehensive project review, devlog creation, and gap closure:
- **Housekeeping:** Phase 1 verification confirmed, ROADMAP.md and STATE.md updated
- **Score Card:** Generated for Bruno Rubio (9/10), example DOCX added to `examples/`
- **generate.sh:** Pandoc check added, Score Card + Cover Letter + Skills Matrix handling
- **Early-career validation:** Synthetic candidate Alex Martinez tested full pipeline (discovery → resume → score card 8.7/10)
- **Profile clone:** `financial_controller.md` cloned from NetSuite admin with 4 new categories (FP&A, Controls, Treasury, Team Leadership)
- **Phase 2 complete:** Job targeting workflow added to `workflow.md` (4-step process), cover letter spec added to `output_formats.md`
- **Web search resolved:** GSD config flags don't affect Claude Code tool availability
- Marked Cindy Rubio complete, Phase 2 requirements (TARG-01/02/03, DELV-05) all satisfied
- **Phase 3 complete:** LinkedIn optimization guide (7-section spec + Phase 7 workflow), candidate dashboard (HTML template + generation workflow)
- **All 17/17 gaps closed. All 3 phases complete. 31/31 v1 requirements satisfied.**

### 2026-03-23 — Phase 2 context gathered
Captured 9 decisions (D-01 through D-09) for Job Targeting + Cover Letter phase. Context document and discussion log created. Phase 2 ready for planning.

### 2026-03-23 — Phase 1: Profile Expansion (COMPLETE)
Two plans executed:
- **Plan 01-01:** Created `system/profile-generation-guide.md` (176 lines) — standalone protocol for auto-generating profiles from 3-5 job postings with knowledge-based fallback. Updated `workflow.md` Phase 0 step 4.
- **Plan 01-02:** Added clone-and-tweak path to `workflow.md` Phase 0 step 3 and updated `profiles/README.md` with clone procedure and 60% overlap threshold.
- PROJECT.md evolved after phase completion.

### 2026-03-23 — GSD initialization and planning
Retroactive GSD setup:
- `.planning/PROJECT.md` — project definition with requirements, constraints, key decisions
- `.planning/REQUIREMENTS.md` — 31 v1 requirements (22 pre-GSD complete, 9 mapped to 3 phases)
- `.planning/ROADMAP.md` — 3-phase roadmap (Profile Expansion → Job Targeting → LinkedIn + Dashboard)
- `.planning/config.json` — balanced mode, no web search enabled

### 2026-03-23 — Early-career track added
Complete second track for new grads and career changers:
- `system/discovery_early_career.md` — 9 discovery questions, encouragement-focused
- `system/resume_rules_early_career.md` — 1-page strict, education first, relaxed quantification

### 2026-03-23 — Resume methodology hardened
Quality controls added to reach recruiter-grade standard:
- Weak bullet filter (no numberless, no weak verbs, no task-only)
- Self-audit checklist run before presenting draft
- Recruiter eye test (7-second scan simulation)
- ATS compatibility rules
- Multi-target role strategy

### 2026-03-23 — Initial commit
Reusable resume creation system:
- `system/workflow.md` — 7-phase pipeline
- `system/discovery.md` — 12-question experienced interview
- `system/resume_rules.md` — resume standards and section order
- `system/output_formats.md` — Resume, Interview Prep, Skills Matrix, Score Card specs
- `profiles/netsuite_administrator.md` — reference profile
- `generate.sh` — pandoc automation
- `templates/resume_template.docx` — DOCX styling
- Example deliverables for Bruno Rubio
- 2 candidate sessions (Bruno Rubio complete, Cindy Rubio resume only)

---

## Gap Closure Checklist

Gaps identified 2026-03-29. Ordered by impact to the core purpose: helping individuals create or improve a resume.

### Housekeeping

- [x] **Create Phase 1 verification doc** — already existed with full 7/7 verification; confirmed 2026-03-29
- [x] **Update ROADMAP.md progress table** — Phase 1 now shows 2/2 Complete with date
- [x] **Update STATE.md** — Metrics populated, focus updated to Phase 02

### Validate Existing Deliverables

- [x] **Generate a Score Card for Bruno Rubio** — Overall 9/10, 3 weak bullets flagged, full audit completed
- [x] **Add Score Card example to `examples/`** — `Example_Score_Card.docx` generated via pandoc

### generate.sh Fixes

- [x] **Add pandoc availability check** — Script now exits with install URL if pandoc missing
- [x] **Add Skills Matrix / Score Card handling** — Score Card added to pandoc loop; Skills Matrix confirmed as HTML with user guidance

### Track & Profile Validation

- [x] **Test early-career track end-to-end** — Synthetic candidate Alex Martinez (B.S. Accounting, UH 2025): discovery, resume, and score card (8.7/10) all generated following early-career rules
- [x] **Generate or clone a second profile** — `financial_controller.md` cloned from NetSuite admin; 4 new categories added (FP&A, Controls, Treasury, Team Leadership)
- [x] **Resolve web search availability** — config.json flags are GSD harness config, not Claude Code tools. `WebSearch` is available natively in Claude Code; profile generation works as designed. No action needed.

### Phase 2: Job Targeting + Cover Letter (TARG-01, TARG-02, TARG-03, DELV-05)

- [x] **Add cover letter spec to `output_formats.md`** — Section 5 added: 3-4 paragraph structure, tone rules, discovery data sources, optional per D-09
- [x] **Build job posting ingestion** — Step 1-2 in workflow.md: paste text, save to `postings/`, extract 10-15 keywords with gap alerts
- [x] **Build keyword weaving logic** — Step 3 rules: exact phrases where natural, paraphrase when forced, never fabricate
- [x] **Build resume variant generation** — Summary-only rewrite as lightweight overlay; Key Achievements and bullets unchanged
- [x] **Build cover letter generation** — Step 4: optional, pulls from discovery data, spec in output_formats.md Section 5
- [x] **Write and execute Phase 2 plans** — Implemented directly: workflow.md + output_formats.md + generate.sh all updated

### Phase 3: LinkedIn + Dashboard (DELV-06, CAND-04)

- [x] **Build LinkedIn optimization guide** — Section 6 in output_formats.md (7 LinkedIn sections), Phase 7 in workflow.md, generate.sh updated
- [x] **Build candidate dashboard (HTML)** — `dashboard_template.md` with full HTML/CSS template, dashboard generation section in workflow.md
- [x] **Write and execute Phase 3 plans** — Implemented directly: all system files updated, DELV-06 and CAND-04 satisfied

---

## Known Issues / Watch List

All previously identified issues have been resolved:
- ~~Score Card never produced~~ — Bruno Rubio scored 9/10
- ~~Early-career track untested~~ — Alex Martinez validated full pipeline
- ~~Web search disabled~~ — GSD flags don't affect Claude Code tools
- ~~Single profile~~ — `financial_controller.md` validates clone protocol
- ~~generate.sh limited~~ — All deliverable types handled

**No open issues.** v1 milestone complete (31/31 requirements).

---
*Created: 2026-03-29*
