# Resume Creation Project

A Claude-powered system for creating and improving resumes through structured discovery interviews. Produces A+ resumes that land in the top 5-10% of applicants, plus interview prep guides and visual skills matrices.

Works for any industry — the system auto-generates role-specific profiles by researching current job postings.

---

## How It Works

1. **Profile Selection** — Pick an existing industry profile or generate one on the fly
2. **Discovery Interview** — Claude asks questions one at a time to uncover metrics, achievements, and skills
3. **Resume Transformation** — Generates a quantified, results-focused resume
4. **Interview Prep** — STAR-format answers for the strongest resume bullets
5. **Skills Matrix** — Color-coded proficiency breakdown

All progress is saved incrementally — sessions can be interrupted and resumed.

---

## Quick Start

### New Resume
```
> Run the resume workflow
```
Place a resume in `input/` first, or Claude will ask for one. Claude handles everything from there.

### Continue a Session
```
> Continue working on [name]'s resume
```
Picks up where you left off using the saved discovery file.

### Update an Existing Resume
```
> Update [name]'s resume — she got a new certification
```
Loads the previous output, asks what changed, regenerates.

---

## Project Structure

```
Resume Creation Project/
│
├── system/                          # Workflow engine
│   ├── workflow.md                  # Master orchestrator — phases and decision logic
│   ├── discovery.md                 # Interview process and probing techniques
│   ├── resume_rules.md             # The 6 evaluation criteria and formatting rules
│   └── output_formats.md           # Specs for each deliverable
│
├── profiles/                        # Industry/role profiles (reusable)
│   ├── README.md                    # How profiles work
│   └── netsuite_administrator.md   # Example: NetSuite/Finance roles
│
├── candidates/                      # Per-candidate data (gitignored)
│   └── [name]/
│       ├── input/                   # Original resume
│       ├── discovery.md             # Interview answers and progress
│       └── output/                  # Generated deliverables
│
├── templates/                       # Pandoc reference templates
│   └── resume_template.docx        # Styling template for DOCX output
│
├── examples/                        # Reference examples (A+ quality)
│   ├── Example_Resume_Bruno_Rubio.docx
│   ├── Example_Interview_Prep.docx
│   └── Example_Skills_Matrix.pdf
│
├── input/                           # Quick-start landing zone for new resumes
├── output/                          # Quick-start output (moved to candidates/ on session start)
├── generate.sh                      # Pandoc automation script
└── .gitignore                       # Excludes candidates/ and tool files
```

---

## The 6 Evaluation Criteria

Every resume is evaluated against:

1. **Clarity** — Logical structure, clear headers, no jargon
2. **Focus** — Targeted to the role, no filler content
3. **Quantification** — Every bullet has a number ($, %, time, volume)
4. **Results-Driven** — Show outcomes, not duties
5. **Cuts Through Noise** — Top third hooks reader in 7-10 seconds
6. **Skimability** — Bold metrics, consistent formatting, 1-2 line bullets

---

## Industry Profiles

Profiles define the skills categories, proficiency levels, and interview questions for a specific role. The system ships with a NetSuite Administrator profile and can generate new ones automatically.

**To generate a new profile**, Claude will:
1. Ask about industry, target role, and key tools/certifications
2. Research 5-10 current job postings for that role
3. Extract and group common skill requirements
4. Save the profile to `profiles/` for future candidates

---

## Pandoc Commands

### With the script
```bash
./generate.sh Jane_Smith FINAL
```

### Manual
```bash
pandoc content.md -o "output/[Name]_Resume_FINAL.docx" --reference-doc="templates/resume_template.docx"
```

### Skills Matrix
Generated as HTML with embedded CSS. Open in browser and print to PDF if needed.

---

## Resume Length Guidelines

| Experience Level | Target Length |
|------------------|---------------|
| Entry-level (< 5 years) | 1 page |
| Mid-level (5-15 years) | 2 pages |
| Senior/Executive (15+ years) | 2 pages (3 max if justified) |

---

## Tips for Best Results

1. **Be honest about gaps** — Claude can help frame them positively
2. **Dig for numbers** — Even estimates are better than no numbers
3. **Think about impact** — What changed because of your work?
4. **Do not rush the interview** — The discovery phase makes the resume stronger
5. **Push back on Claude** — If something does not sound like you, say so
