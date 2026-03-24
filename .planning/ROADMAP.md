# Roadmap: Resume Creation Project

## Overview

The foundation is complete (22/31 requirements shipped pre-GSD). Three phases remain: expanding the profile system to work for any role, adding job-targeting and cover letter capabilities driven by real postings, and rounding out the toolkit with LinkedIn optimization and a candidate dashboard. Each phase delivers a coherent, testable capability on top of the existing system.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Profile Expansion** - Any role can be profiled; existing profiles can be forked
- [ ] **Phase 2: Job Targeting + Cover Letter** - Resume and cover letter adapt to a specific posting
- [ ] **Phase 3: LinkedIn + Dashboard** - LinkedIn optimization and a candidate management view

## Phase Details

### Phase 1: Profile Expansion
**Goal**: The profile system works for any role, not just NetSuite Administrator
**Depends on**: Nothing (first phase)
**Requirements**: PROF-03, PROF-04
**Success Criteria** (what must be TRUE):
  1. User can request a profile for a new role and the system researches current job postings and produces a complete profile file without manual data entry
  2. User can clone an existing profile, tweak a few fields, and use it for a related role without starting from scratch
  3. A newly generated profile contains skill categories, proficiency levels, and interview questions that match what real job postings list for that role
**Plans**: 2 plans

Plans:
- [x] 01-01-PLAN.md — Create profile-generation-guide.md and update workflow.md Phase 0 generation step (PROF-03)
- [x] 01-02-PLAN.md — Add clone-and-tweak path to workflow.md Phase 0 and update profiles/README.md (PROF-04)

### Phase 2: Job Targeting + Cover Letter
**Goal**: Users can aim the resume at a specific job posting and generate a matching cover letter
**Depends on**: Phase 1
**Requirements**: TARG-01, TARG-02, TARG-03, DELV-05
**Success Criteria** (what must be TRUE):
  1. User can paste a job posting URL or raw text and the system ingests it without manual keyword extraction
  2. The resume variant produced for a specific posting visibly incorporates keywords and priorities from that posting
  3. User can generate a targeted resume variant without re-running the full discovery interview
  4. User can optionally generate a cover letter that references the specific posting, role, and company
**Plans**: TBD

### Phase 3: LinkedIn + Dashboard
**Goal**: Candidates get LinkedIn guidance and the user can see all candidates at a glance
**Depends on**: Phase 2
**Requirements**: DELV-06, CAND-04
**Success Criteria** (what must be TRUE):
  1. User can generate a LinkedIn optimization guide for a candidate that maps resume content to LinkedIn sections
  2. User can open an HTML file and see all candidates, their status, scores, and available deliverables without touching the file system directly
  3. The dashboard updates when new candidates are added or deliverables are generated
**Plans**: TBD
**UI hint**: yes

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Profile Expansion | 1/2 | In Progress|  |
| 2. Job Targeting + Cover Letter | 0/? | Not started | - |
| 3. LinkedIn + Dashboard | 0/? | Not started | - |
