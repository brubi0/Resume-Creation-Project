# Project Milestones: Resume Creation Project

## v1.0 Resume Chat (Shipped: 2026-03-30)

**Delivered:** Full-stack web app for structured resume discovery interviews, producing A+ resumes, interview prep, skills matrices, and score cards — for any role, any experience level.

**Phases completed:** 1–3 (4 plans total)

**Key accomplishments:**
- FastAPI + PostgreSQL + React app deployed at resume.urkuconsulting.com with JWT auth, admin dashboard, and candidate chat interface
- Discovery interview engine — 12-question experienced track and 9-question early-career track, driven by Claude with META block session state protocol
- 5 deliverables generated per candidate: Resume (MD + DOCX via pandoc), Interview Prep, Skills Matrix (HTML), Score Card
- Profile system: auto-generate role profiles via Claude + web search; clone-and-tweak path for related roles
- Phase 0 profile picker UI — candidates select target role before interview starts
- Resume upload (PDF/DOCX/TXT) with text extraction, stored on session for Phase 1 review
- discovery.md written to disk after each answer; used as context for deliverables generation
- Deliverables page grouped by target role (candidate name + role for admin view)
- Admin panel: create/delete candidates, trigger deliverable generation, generate new profiles

**Stats:**
- 88 files changed, 7518 insertions
- 41 commits
- 3 phases, 4 plans
- ~7 days from first commit to ship

**Git range:** `e8cdee8` → `5a2c38e`

**What's next:** Channels integration — `/newcandidate` command in claude-channels Telegram bot to create resume-chat candidates directly from Telegram

---
