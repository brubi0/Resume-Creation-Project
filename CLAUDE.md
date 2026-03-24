<!-- GSD:project-start source:PROJECT.md -->
## Project

**Resume Creation Project**

A Claude-powered system for creating and improving resumes through structured discovery interviews. It produces A+ resumes (top 5-10% of applicants), interview prep guides, skills matrices, and score cards. Works for any industry via auto-generated role profiles. Handles both experienced professionals and early-career candidates with dedicated tracks.

**Core Value:** Every resume produced by this system must make a recruiter stop and call the candidate — not just "good enough," but top-tier.

### Constraints

- **No code runtime**: This is a document/prompt system — no server, no database, no build tools. Just markdown, HTML, pandoc, and Claude.
- **Privacy**: Candidate data must never be committed to git. All personal information stays in the gitignored `candidates/` directory.
- **Pandoc dependency**: DOCX generation requires pandoc installed locally.
- **Claude Code dependency**: The workflow is designed to run inside Claude Code, not as a standalone script.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->
## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd:quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd:debug` for investigation and bug fixing
- `/gsd:execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd:profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
