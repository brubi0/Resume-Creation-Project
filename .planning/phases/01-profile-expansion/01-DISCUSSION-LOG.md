# Phase 1: Profile Expansion - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-23
**Phase:** 01-profile-expansion
**Areas discussed:** Research depth

---

## Research Depth

### Q1: How should Claude research job postings when generating a new profile?

| Option | Description | Selected |
|--------|-------------|----------|
| Web search (Recommended) | Claude searches for current job postings using web search tools, extracts common skills/requirements, synthesizes into a profile. Most accurate but requires search access. | ✓ |
| Claude's knowledge + user input | Claude drafts a profile from its training knowledge of the role, then asks the user to validate/adjust. No web search needed. Faster but may miss current trends. | |
| Hybrid | Try web search first. If unavailable or results are thin, fall back to Claude's knowledge + user validation. | |

**User's choice:** Web search (Recommended)
**Notes:** None

### Q2: What if web search isn't available or returns weak results for a niche role?

| Option | Description | Selected |
|--------|-------------|----------|
| Fall back to knowledge (Recommended) | If search fails or returns <3 relevant postings, Claude drafts from knowledge and flags it as 'knowledge-based' — user validates before proceeding | ✓ |
| Block until search works | Refuse to generate a profile without real posting data. Ensures accuracy but blocks progress. | |
| Ask user for postings | Ask the user to paste 2-3 job posting URLs or text directly. Claude extracts from those. | |

**User's choice:** Fall back to knowledge (Recommended)
**Notes:** None

### Q3: How many job postings should Claude analyze when building a profile?

| Option | Description | Selected |
|--------|-------------|----------|
| 5-10 postings (Recommended) | Good balance — enough to identify patterns without burning too many tokens. Already specified in workflow.md. | |
| 3-5 postings | Faster, cheaper. Might miss less common requirements. | ✓ |
| 10-15 postings | Most thorough. Higher cost but catches edge cases and niche skills. | |

**User's choice:** 3-5 postings
**Notes:** User preferred faster/cheaper over exhaustive. Overrides the original 5-10 specified in workflow.md.

## Claude's Discretion

- Profile structure (match NetSuite format vs adapt per industry)
- Clone & tweak flow (mechanism for forking profiles)
- Profile naming conventions
- All remaining gray areas not selected for discussion

## Deferred Ideas

None
