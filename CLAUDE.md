## Project

**Resume Creation Project**

A Claude-powered system for creating and improving resumes through structured discovery interviews. It produces A+ resumes (top 5-10% of applicants), interview prep guides, skills matrices, and score cards. Works for any industry via auto-generated role profiles. Handles both experienced professionals and early-career candidates with dedicated tracks.

**Core Value:** Every resume produced by this system must make a recruiter stop and call the candidate — not just "good enough," but top-tier.

### Constraints

- **No code runtime**: This is a document/prompt system — no server, no database, no build tools. Just markdown, HTML, pandoc, and Claude.
- **Privacy**: Candidate data must never be committed to git. All personal information stays in the gitignored `candidates/` directory.
- **Pandoc dependency**: DOCX generation requires pandoc installed locally.
- **Claude Code dependency**: The workflow is designed to run inside Claude Code, not as a standalone script.
