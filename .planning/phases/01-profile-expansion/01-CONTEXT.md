# Phase 1: Profile Expansion - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Make the profile system work for any role — not just NetSuite Administrator. Users can request a profile for any role/industry and the system generates one by researching current job postings. Existing profiles can be cloned and tweaked for related roles.

Requirements: PROF-03 (auto-generate profiles via research), PROF-04 (clone and tweak existing profiles)

</domain>

<decisions>
## Implementation Decisions

### Research Approach
- **D-01:** Primary method is web search — Claude searches for current job postings for the target role and extracts common skills/requirements to build the profile
- **D-02:** Research 3-5 job postings per profile (not 5-10 as originally specified — faster, lower cost, sufficient for pattern identification)
- **D-03:** If web search is unavailable or returns <3 relevant postings, fall back to Claude's training knowledge and flag the profile as "knowledge-based" — user validates before proceeding
- **D-04:** User can also paste job posting URLs or text directly as an alternative input method

### Claude's Discretion
- Profile structure: Claude decides whether generated profiles should match the NetSuite format exactly or adapt per industry. Use the NetSuite profile as a reference but adjust categories and depth to fit the role.
- Clone & tweak flow: Claude decides the cloning mechanism. Simple approach preferred — copy the profile, let user/Claude edit fields. No need for interactive diff UI.
- Profile naming: Claude decides naming conventions. Keep it simple and consistent (e.g., `financial_controller.md`, `frontend_engineer.md`).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing Profile System
- `profiles/netsuite_administrator.md` — Reference implementation; shows expected structure, categories, proficiency levels
- `profiles/README.md` — Documents how profiles work and auto-generation process

### Workflow Integration
- `system/workflow.md` §Phase 0 — Profile selection logic that triggers generation
- `system/discovery.md` §Question 12 — Skills Matrix section that consumes profile categories
- `system/discovery_early_career.md` §Question 9 — Early-career skills matrix that also consumes profiles

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `profiles/netsuite_administrator.md` — Complete reference profile with 20 skill categories across 3 groups (Core, Add-On, Other), proficiency level definitions with color coding
- `system/workflow.md` Phase 0 — Already has the 3-question intake (industry, target role, certifications/tools) and the profile generation instructions

### Established Patterns
- Profiles are markdown files with a consistent structure: header with industry/target roles, proficiency level table, and skills organized by category group with descriptions
- Each skill category includes a paragraph describing what it covers — this helps Claude ask informed skills matrix questions during discovery

### Integration Points
- `system/workflow.md` Phase 0 checks `profiles/` for existing profiles before asking
- Discovery files reference the selected profile by filename
- Skills matrix HTML template reads categories from the profile

</code_context>

<specifics>
## Specific Ideas

- The 3-5 posting research target is a deliberate cost/speed tradeoff — user prefers faster generation over exhaustive research
- Knowledge-based fallback profiles should be explicitly marked so the user knows they weren't research-backed

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-profile-expansion*
*Context gathered: 2026-03-23*
