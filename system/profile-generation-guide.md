# Profile Generation Guide

This guide provides the complete protocol for generating a role profile when `system/workflow.md` Phase 0 finds no matching profile for the target role.

---

## 1. When This Guide Applies

Run this guide when:
- The user has specified a target role/industry
- No matching profile file exists in `profiles/`
- Phase 0 intake questions (industry, target role, must-have tools/certs) have already been answered

Do not re-ask intake questions — all required input comes from the Phase 0 intake.

---

## 2. Input Checklist

Before researching, confirm you have all three inputs from the Phase 0 intake:

| Input | Source |
|-------|--------|
| Target role/title | Phase 0 question: "What is your target role/title?" |
| Industry or domain | Phase 0 question: "What industry are you in?" |
| Must-have tools/certs | Phase 0 question: "Any must-have certifications, tools, or frameworks?" |

If any input is missing, ask for it before proceeding.

---

## 3. Research Step (D-01, D-02)

**Primary method: search for 3-5 current job postings.**

Use the following queries — adjust role name and industry as needed:

1. `"[target role]" job posting requirements site:linkedin.com OR site:indeed.com`
2. `"[target role]" "required skills" OR "qualifications" -resume`
3. `[target role] [industry] skills responsibilities 2024 OR 2025`

**For each of the 3-5 postings found, extract:**
- Required technical skills and tools
- Required soft skills or domain knowledge
- Certifications or qualifications listed
- Common job responsibilities (responsibilities reveal which skills matter most)

**Target:** 3-5 postings minimum. Fewer than 3 means insufficient pattern signal — see Section 4 (Fallback).

---

## 4. Fallback When Search Is Unavailable or Returns Fewer Than 3 Relevant Postings (D-03)

If web search is unavailable, or if fewer than 3 relevant postings are returned:

1. Use Claude's training knowledge to construct the profile
2. Add the following line to the profile header, immediately after **Target Roles**:
   `**Source:** Knowledge-based (not research-backed — validate before use)`
3. Inform the user before proceeding:
   > "This profile was generated from training knowledge, not live job postings. Please review the skill categories and proficiency definitions before we continue — they reflect general knowledge of the role, not verified current market requirements."

Do not proceed to the extraction and grouping step without acknowledging this limitation.

---

## 5. Paste-URL or Paste-Text Alternative (D-04)

If the user has provided job posting URLs or raw posting text directly:

- Use those postings as your 3-5 sources instead of searching
- No web search needed — proceed directly to Section 6 (Extraction)
- This method is treated as equivalent to search-backed; do NOT add the Knowledge-based flag

Example triggers: user says "here are some job postings," pastes URLs, or pastes raw job description text.

---

## 6. Extraction and Grouping

After gathering postings (via search, fallback, or user-provided), identify **8-20 distinct skill categories** from the combined signal across all postings.

**Grouping rules:**
- Create 2-4 logical groups (e.g., "Core Skills", "Technical Tools", "Soft Skills / Domain Knowledge")
- For roles centered on a software product (like NetSuite), name the core group after the product
- For generalist roles, use domain-area groupings (e.g., "Financial Operations", "Technology Tools", "Leadership & Communication")

**Each category must include:**
- A clear, role-appropriate name (2-5 words)
- A one-paragraph description (2-4 sentences) explaining what knowledge, tools, and tasks this category covers

**Why descriptions matter:** These paragraphs are used by Claude during the skills matrix discovery interview (see `system/discovery.md` Question 12 and `system/discovery_early_career.md` Question 9). They must be specific enough to guide informed questions — avoid vague language like "various tasks" or "general knowledge."

**Reference implementation:** See `profiles/netsuite_administrator.md` for an example of well-defined categories with substantive descriptions. All generated profiles must match that structural format.

---

## 7. Proficiency Level Definitions

Use the standard four-level system in all generated profiles unless the role clearly requires different terminology (e.g., a clinical role where "Expert" has a specific professional meaning).

| Level | Code | Color | Hex | Meaning |
|-------|------|-------|-----|---------|
| Expert | E | Dark Blue | #3d5a80 | Deep expertise, can teach others, handles complex scenarios |
| Advanced | A | Gold | #e9c46a | Strong working knowledge, independent problem-solving |
| Intermediate | I | Green | #52b788 | Functional knowledge, can handle routine tasks |
| Novice | N | Coral | #e76f51 | Basic familiarity, still learning |

For highly specialized roles (e.g., surgeon, pilot, licensed engineer), you may adapt the label terminology while keeping the same 4 levels and hex codes. Document any adaptations in the profile.

---

## 8. Output Format

Save the generated profile to `profiles/[role_slug].md` where:
- `role_slug` is lowercase with underscores for spaces
- Examples: `financial_controller.md`, `frontend_engineer.md`, `marketing_manager.md`

The file must use the exact structure from `profiles/netsuite_administrator.md`:

```
# Profile: [Role Name]

**Industry:** [Industry]
**Target Roles:** [Role 1], [Role 2], [Role 3...]
<!-- Add this line ONLY for knowledge-based profiles: -->
**Source:** Knowledge-based (not research-backed — validate before use)

---

## Proficiency Levels

| Level | Code | Color | Hex | Meaning |
|-------|------|-------|-----|---------|
| Expert | E | Dark Blue | #3d5a80 | Deep expertise, can teach others, handles complex scenarios |
| Advanced | A | Gold | #e9c46a | Strong working knowledge, independent problem-solving |
| Intermediate | I | Green | #52b788 | Functional knowledge, can handle routine tasks |
| Novice | N | Coral | #e76f51 | Basic familiarity, still learning |

---

## Skills Categories

### [Group Name]

**[Category Name]**
[Description paragraph — 2-4 sentences]

**[Category Name]**
[Description paragraph — 2-4 sentences]

### [Group Name 2]

**[Category Name]**
[Description paragraph — 2-4 sentences]
...
```

Do not omit the Proficiency Levels table — it is referenced by the skills matrix HTML template.

---

## 9. Confirm With User

After generating and saving the profile, display a summary:

```
Profile saved to: profiles/[role_slug].md
Skill categories: [N] categories across [M] groups
Source: [web search / knowledge-based / user-provided postings]
Groups: [Group 1 name] ([n] categories), [Group 2 name] ([n] categories), ...
```

Then ask:
> "Does this profile look right, or should I adjust any categories before we continue?"

**Do not proceed to Phase 1 of the workflow until the user confirms or requests changes.** If the user requests changes, update the profile file and re-display the summary.
