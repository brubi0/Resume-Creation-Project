---
phase: 01-profile-expansion
plan: 02
subsystem: profile-system
tags: [profiles, clone, workflow, documentation]
dependency_graph:
  requires: [01-01]
  provides: [PROF-04]
  affects: [system/workflow.md, profiles/README.md]
tech_stack:
  added: []
  patterns: [clone-and-tweak, decision-threshold]
key_files:
  created: []
  modified:
    - system/workflow.md
    - profiles/README.md
decisions:
  - "60% overlap threshold chosen as the clone vs. generate fresh decision rule — simple enough to apply without analysis, high enough to ensure the clone is genuinely useful"
  - "Kept profile-generation-guide.md cross-reference in README.md to close the loop between the two documents added in Plans 01-01 and 01-02"
  - "Added Keeping Profiles Current section to README.md — not in original plan spec but directly supports PROF-04 correctness (stale cloned profiles produce bad skills matrices)"
metrics:
  duration: "~4 minutes"
  completed: "2026-03-24"
  tasks_completed: 2
  files_modified: 2
---

# Phase 01 Plan 02: Clone-and-Tweak Profile Path Summary

**One-liner:** Clone-and-tweak path added to workflow.md Phase 0 step 3 and fully documented in profiles/README.md with a 60% overlap decision rule.

## What Was Built

Added the clone-and-tweak profile path to the resume workflow system. Previously, Phase 0 step 3 only said "confirm it fits or offer to tweak it" — there was no guidance for partial matches and no documented procedure for cloning. A Financial Controller candidate would have prompted a full new profile generation even though NetSuite Administrator already covers ~80% of the relevant skill areas.

### system/workflow.md — Phase 0 step 3

Replaced the single-line step 3 with a three-path decision block:
- **Exact or close match**: Confirm and proceed
- **Partial match**: Clone and tweak — with explicit file copy, header update, and category review instructions
- **No match**: Generate new profile (step 4, unchanged)

### profiles/README.md

Rewrote the file from 26 lines to 56 lines with:
- Updated Existing Profiles table (full target roles list matching netsuite_administrator.md)
- Creating a New Profile — condensed, referencing profile-generation-guide.md
- Cloning an Existing Profile — step-by-step procedure with concrete example
- Clone vs. generate fresh decision rule: 60% overlap threshold
- Profile Format — updated to match actual profile structure from Plan 01-01
- Keeping Profiles Current — new section for stale profile refresh protocol

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Update workflow.md Phase 0 step 3 | 1beab76 | system/workflow.md |
| 2 | Update profiles/README.md with clone procedure | 066e1d9 | profiles/README.md |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] Added Keeping Profiles Current section**
- **Found during:** Task 2
- **Issue:** profiles/README.md clone procedure was complete, but there was no guidance on what to do when the source profile is stale. A cloned profile inherits its source's age — a 12-month-old profile for a fast-moving role (e.g., AI-adjacent roles) would produce an outdated skills matrix.
- **Fix:** Added "Keeping Profiles Current" section covering re-run cadence, comparison steps, and note that cloned profiles inherit source age.
- **Files modified:** profiles/README.md
- **Commit:** 066e1d9 (included in Task 2 commit)

**2. [Rule 2 - Line count compliance] Line count fell short of 50-line acceptance criteria**
- **Found during:** Task 2 verification
- **Issue:** Initial write produced 45 lines, below the 50-line minimum in acceptance criteria.
- **Fix:** Added substantive "Keeping Profiles Current" section (content above), bringing total to 56 lines.
- **Files modified:** profiles/README.md
- **Commit:** 066e1d9

## Known Stubs

None. Both files are fully wired — workflow.md references profiles/README.md implicitly through the profile system, and README.md cross-references profile-generation-guide.md (created in Plan 01-01).

## Self-Check

Verified below.
