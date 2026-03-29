# Resume Creation Project

## What This Is

A Claude-powered system for creating and improving resumes through structured discovery interviews. It produces A+ resumes (top 5-10% of applicants), interview prep guides, skills matrices, and score cards. Works for any industry via auto-generated role profiles. Handles both experienced professionals and early-career candidates with dedicated tracks.

## Core Value

Every resume produced by this system must make a recruiter stop and call the candidate — not just "good enough," but top-tier.

## Requirements

### Validated

- ✓ Modular workflow engine (workflow, discovery, rules, output formats) — v1.0
- ✓ Industry profile system with NetSuite Administrator profile — v1.0
- ✓ Per-candidate directory structure with session persistence — v1.0
- ✓ Experienced candidate discovery process (12 question areas) — v1.0
- ✓ Early-career candidate track (education-first, project-focused) — v1.0
- ✓ Resume transformation with 6 evaluation criteria — v1.0
- ✓ Self-audit and recruiter eye test before presenting drafts — v1.0
- ✓ ATS compatibility rules — v1.0
- ✓ Weak bullet filter — v1.0
- ✓ Multi-target role strategy (primary + variants) — v1.0
- ✓ Pandoc automation script (generate.sh) — v1.0
- ✓ Interview prep guide output format (STAR) — v1.0
- ✓ Skills matrix output format (HTML with color coding) — v1.0
- ✓ Score card output format (6-criteria grading) — v1.0
- ✓ Auto-generated profile from job posting research (3-5 postings, knowledge fallback) — Phase 1
- ✓ Clone-and-tweak path for related role profiles — Phase 1

### Active

- [ ] Candidate dashboard (HTML) — view all candidates, status, scores, deliverables at a glance
- [ ] Cover letter as optional deliverable — targeted to specific job postings
- [ ] LinkedIn profile optimization as optional deliverable
- [ ] Job description targeting — pull keywords from specific postings into the resume

### Out of Scope

- Web application / hosted service — this is a local Claude Code workflow, not a SaaS product
- Resume parsing / OCR — candidates provide their own resume files
- Job board integration — this system creates resumes, not job applications
- Payment / billing — free tool for personal use

## Context

- Built and refined in a single session with extensive resume consultant analysis
- Two complete candidate examples exist: Bruno Rubio (all 3 deliverables) and Cindy Rubio (resume — complete, no additional deliverables needed)
- The NetSuite Administrator profile was the first and serves as the reference implementation
- All documents are markdown-based, converted to DOCX via pandoc with a reference template
- Skills matrices are standalone HTML files with embedded CSS
- Candidate data is gitignored (personal information)
- Project is hosted at https://github.com/brubi0/Resume-Creation-Project

## Constraints

- **No code runtime**: This is a document/prompt system — no server, no database, no build tools. Just markdown, HTML, pandoc, and Claude.
- **Privacy**: Candidate data must never be committed to git. All personal information stays in the gitignored `candidates/` directory.
- **Pandoc dependency**: DOCX generation requires pandoc installed locally.
- **Claude Code dependency**: The workflow is designed to run inside Claude Code, not as a standalone script.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Split monolithic prompt into system/ modules | Easier to maintain, each file has one job | ✓ Good |
| Industry profiles auto-generated via web search | Can't manually create profiles for every role | — Pending (not yet tested) |
| Two tracks (experienced / early-career) | Fundamentally different resume strategies | ✓ Good |
| Candidate data gitignored | Privacy — resumes contain PII | ✓ Good |
| Markdown as source format, pandoc for DOCX | Universal, versionable, no proprietary tools | ✓ Good |
| Self-audit + recruiter eye test before draft | System must enforce its own rules | — Pending (not yet tested in live workflow) |
| Score card as 4th deliverable | Quality assurance + candidate confidence | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-23 after GSD initialization (retroactive)*
