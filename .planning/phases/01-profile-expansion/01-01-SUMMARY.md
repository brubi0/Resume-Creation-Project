---
phase: 01-profile-expansion
plan: "01"
subsystem: profile-system
tags: [profile-generation, workflow, instructions, fallback]
dependency_graph:
  requires: []
  provides: [profile-auto-generation-protocol]
  affects: [system/workflow.md, system/profile-generation-guide.md]
tech_stack:
  added: []
  patterns: [knowledge-based-fallback-flag, paste-url-alternative, role-slug-naming]
key_files:
  created:
    - system/profile-generation-guide.md
  modified:
    - system/workflow.md
decisions:
  - "Use 3-5 postings (not 5-10) per D-02 — faster, lower cost, sufficient signal"
  - "Knowledge-based flag added inline in profile header so users can immediately see provenance"
  - "profile-generation-guide.md is standalone — any Claude instance can follow it without prior context"
metrics:
  duration: "2 minutes"
  completed: "2026-03-24T03:54:15Z"
  tasks_completed: 2
  files_modified: 2
requirements_satisfied: [PROF-03]
---

# Phase 01 Plan 01: Profile Auto-Generation Protocol Summary

## One-Liner

New `system/profile-generation-guide.md` provides a complete, 9-section protocol for generating role profiles via 3-5 job posting research, knowledge-based fallback with inline flag, and paste-URL alternative; `workflow.md` Phase 0 step 4 updated to reference the guide and document all three paths.

## What Was Built

### Task 1 — Create system/profile-generation-guide.md

A 176-line standalone generation protocol covering:

1. When the guide applies (Phase 0 no-profile condition)
2. Input checklist (role, industry, must-have tools from Phase 0 intake — no re-asking)
3. Research step (3-5 postings, three specific query templates, D-01/D-02)
4. Fallback with knowledge-based flag (D-03) — user-visible warning built into the confirmation step
5. Paste-URL/paste-text alternative (D-04) — treated as search-equivalent, no flag added
6. Extraction and grouping rules (8-20 categories, 2-4 groups, description paragraph requirements)
7. Standard four-level proficiency system with hex codes
8. Output format with exact structure matching `profiles/netsuite_administrator.md`
9. User confirmation step with summary display before proceeding to Phase 1

### Task 2 — Update system/workflow.md Phase 0 Step 4

Replaced the vague "Research 5-10 current job postings" block with a 5-bullet step that:
- References `system/profile-generation-guide.md` explicitly
- Specifies 3-5 postings (not 5-10)
- Documents the Knowledge-based fallback
- Documents the paste-URL alternative
- Requires user confirmation before proceeding

All other phases in workflow.md remain unchanged.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| 1 | 096f2d4 | feat(01-01): create system/profile-generation-guide.md |
| 2 | 6b174be | feat(01-01): update workflow.md Phase 0 step 4 with precise generation instructions |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — both files are complete and actionable. No hardcoded placeholders or TODO markers.
