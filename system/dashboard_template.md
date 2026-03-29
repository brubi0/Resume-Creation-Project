# Candidate Dashboard Template

Instructions for Claude to generate a candidate dashboard as a standalone HTML file.

---

## Purpose

A single HTML file that shows all candidates at a glance: their status, scores, available deliverables, and key metadata. Opens in any browser with no dependencies.

## When to Generate

- The user explicitly asks for a dashboard ("generate dashboard", "show me the dashboard", "update the dashboard")
- After completing all deliverables for any candidate (Phase 6 done)

## How to Generate

1. Scan all subdirectories under `candidates/` (each subdirectory is one candidate)
2. Skip `dashboard.html` if it exists at the candidates root level
3. For each candidate directory, read `discovery.md` and extract:
   - **Name**: from the `# Discovery` heading or `**Candidate:**` field
   - **Target Role**: from `**Target Role:**` or `**Primary Target Role:**`
   - **Experience Level**: from `**Experience Level:**` (Experienced or Early Career)
   - **Profile**: from `**Profile:**` or `**Selected Profile:**`
   - **Status**: from `**Status:**` (In Progress or Complete)
   - **Last Updated**: from `**Last Updated:**` or `**Date:**`, or use the file modification date
4. Check `candidates/[name]/output/` for each deliverable:
   - **Resume**: any file matching `*_Resume_FINAL.md` or `*_Resume_FINAL.docx`
   - **Interview Prep**: any file matching `*_Interview_Prep.md` or `*_Interview_Prep.docx`
   - **Skills Matrix**: any file matching `*_Skills_Matrix.html`
   - **Score Card**: any file matching `*_Score_Card.md`
   - **Cover Letter**: any file matching `*_Cover_Letter_*.md`
   - **LinkedIn Guide**: any file matching `*_LinkedIn*.md`
5. If a Score Card exists, read it and extract the **Overall** score from the criteria table
6. Compute summary stats:
   - Total candidates count
   - Complete vs In Progress counts
   - Average Overall score (across candidates that have a Score Card)
7. Fill in the HTML template below with the extracted data
8. Save to `candidates/dashboard.html`

## Output

`candidates/dashboard.html` — a standalone HTML file at the candidates root, not inside any individual candidate folder.

---

## HTML Template

Claude should generate the following HTML, filling in the placeholder sections with real candidate data. The styling follows the same embedded-CSS pattern used by the Skills Matrix.

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Candidate Dashboard</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }

  body {
    font-family: 'Segoe UI', Arial, sans-serif;
    max-width: 1100px;
    margin: 40px auto;
    padding: 20px;
    background: #f8f9fa;
    color: #333;
  }

  h1 {
    text-align: center;
    color: #3d5a80;
    margin-bottom: 5px;
    font-size: 28px;
  }

  .subtitle {
    text-align: center;
    color: #666;
    font-size: 14px;
    margin-bottom: 30px;
  }

  /* Summary cards */
  .summary {
    display: flex;
    gap: 16px;
    justify-content: center;
    margin-bottom: 36px;
    flex-wrap: wrap;
  }

  .summary-card {
    background: white;
    border-radius: 8px;
    padding: 20px 32px;
    text-align: center;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    min-width: 160px;
  }

  .summary-card .value {
    font-size: 36px;
    font-weight: bold;
    color: #3d5a80;
  }

  .summary-card .label {
    font-size: 13px;
    color: #888;
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .summary-card.complete .value { color: #52b788; }
  .summary-card.in-progress .value { color: #e9c46a; }
  .summary-card.score .value { color: #e76f51; }

  /* Candidate table */
  .candidates-table {
    width: 100%;
    border-collapse: collapse;
    background: white;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 2px 8px rgba(0,0,0,0.08);
  }

  .candidates-table thead {
    background: #3d5a80;
    color: white;
  }

  .candidates-table th {
    padding: 12px 14px;
    text-align: left;
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
  }

  .candidates-table td {
    padding: 12px 14px;
    border-bottom: 1px solid #eee;
    font-size: 14px;
    vertical-align: middle;
  }

  .candidates-table tbody tr:last-child td {
    border-bottom: none;
  }

  .candidates-table tbody tr:hover {
    background: #f0f4f8;
  }

  /* Status badges */
  .status {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }

  .status.complete {
    background: #d4edda;
    color: #276749;
  }

  .status.in-progress {
    background: #fff3cd;
    color: #856404;
  }

  /* Track badges */
  .track {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-weight: 600;
  }

  .track.experienced {
    background: #dbe4ee;
    color: #3d5a80;
  }

  .track.early-career {
    background: #fde8e1;
    color: #e76f51;
  }

  /* Score display */
  .score {
    font-weight: bold;
    font-size: 16px;
  }

  .score.high { color: #52b788; }
  .score.mid { color: #e9c46a; }
  .score.low { color: #e76f51; }

  /* Deliverables checklist */
  .deliverables {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
  }

  .deliverable {
    display: inline-flex;
    align-items: center;
    gap: 3px;
    font-size: 11px;
    padding: 2px 7px;
    border-radius: 4px;
    background: #f0f0f0;
    color: #999;
  }

  .deliverable.done {
    background: #d4edda;
    color: #276749;
  }

  .deliverable .icon {
    font-size: 12px;
  }

  /* Responsive */
  @media (max-width: 900px) {
    .candidates-table { font-size: 12px; }
    .candidates-table th, .candidates-table td { padding: 8px 6px; }
    .summary-card { padding: 14px 20px; min-width: 120px; }
    .summary-card .value { font-size: 28px; }
  }

  @media (max-width: 600px) {
    body { padding: 10px; margin: 10px auto; }
    .summary { flex-direction: column; align-items: center; }
    .candidates-table th:nth-child(4),
    .candidates-table td:nth-child(4),
    .candidates-table th:nth-child(7),
    .candidates-table td:nth-child(7) { display: none; }
  }

  .footer {
    text-align: center;
    color: #aaa;
    font-size: 12px;
    margin-top: 24px;
  }
</style>
</head>
<body>

<h1>Candidate Dashboard</h1>
<p class="subtitle">Resume Creation Project — Generated [DATE]</p>

<!-- SUMMARY SECTION -->
<div class="summary">
  <div class="summary-card">
    <div class="value">[TOTAL]</div>
    <div class="label">Total Candidates</div>
  </div>
  <div class="summary-card complete">
    <div class="value">[COMPLETE_COUNT]</div>
    <div class="label">Complete</div>
  </div>
  <div class="summary-card in-progress">
    <div class="value">[IN_PROGRESS_COUNT]</div>
    <div class="label">In Progress</div>
  </div>
  <div class="summary-card score">
    <div class="value">[AVG_SCORE]</div>
    <div class="label">Avg Score</div>
  </div>
</div>

<!-- CANDIDATE TABLE -->
<table class="candidates-table">
  <thead>
    <tr>
      <th>Name</th>
      <th>Target Role</th>
      <th>Track</th>
      <th>Profile</th>
      <th>Status</th>
      <th>Score</th>
      <th>Deliverables</th>
      <th>Updated</th>
    </tr>
  </thead>
  <tbody>
    <!-- Repeat this <tr> block for each candidate -->
    <tr>
      <td>[CANDIDATE_NAME]</td>
      <td>[TARGET_ROLE]</td>
      <td><span class="track [TRACK_CLASS]">[TRACK_LABEL]</span></td>
      <td>[PROFILE_NAME]</td>
      <td><span class="status [STATUS_CLASS]">[STATUS_LABEL]</span></td>
      <td><span class="score [SCORE_CLASS]">[SCORE_VALUE]</span></td>
      <td>
        <div class="deliverables">
          <!-- For each deliverable, use class "done" if it exists, omit if not -->
          <span class="deliverable [RESUME_CLASS]"><span class="icon">[RESUME_ICON]</span> Resume</span>
          <span class="deliverable [INTERVIEW_CLASS]"><span class="icon">[INTERVIEW_ICON]</span> Interview</span>
          <span class="deliverable [MATRIX_CLASS]"><span class="icon">[MATRIX_ICON]</span> Matrix</span>
          <span class="deliverable [SCORECARD_CLASS]"><span class="icon">[SCORECARD_ICON]</span> Score</span>
          <span class="deliverable [COVER_CLASS]"><span class="icon">[COVER_ICON]</span> Cover</span>
          <span class="deliverable [LINKEDIN_CLASS]"><span class="icon">[LINKEDIN_ICON]</span> LinkedIn</span>
        </div>
      </td>
      <td>[LAST_UPDATED]</td>
    </tr>
    <!-- End repeat -->
  </tbody>
</table>

<p class="footer">Generated by Resume Creation Project</p>

</body>
</html>
```

---

## Placeholder Reference

When filling the template, Claude replaces each placeholder as follows:

| Placeholder | Value |
|-------------|-------|
| `[DATE]` | Current date (e.g., "March 29, 2026") |
| `[TOTAL]` | Total number of candidate directories |
| `[COMPLETE_COUNT]` | Count of candidates with Status: Complete |
| `[IN_PROGRESS_COUNT]` | Count of candidates with Status: In Progress |
| `[AVG_SCORE]` | Average Overall score across scored candidates, or "—" if none |
| `[CANDIDATE_NAME]` | Candidate's full name |
| `[TARGET_ROLE]` | Primary target role |
| `[TRACK_CLASS]` | `experienced` or `early-career` |
| `[TRACK_LABEL]` | `Experienced` or `Early Career` |
| `[PROFILE_NAME]` | Name of the selected profile (e.g., "NetSuite Administrator") |
| `[STATUS_CLASS]` | `complete` or `in-progress` |
| `[STATUS_LABEL]` | `Complete` or `In Progress` |
| `[SCORE_CLASS]` | `high` (7+), `mid` (5-6), or `low` (1-4) — omit class if no score |
| `[SCORE_VALUE]` | Overall score number, or "—" if no Score Card |
| `[*_CLASS]` | `done` if the deliverable exists, empty string if not |
| `[*_ICON]` | checkmark character if done, dash character if not |
| `[LAST_UPDATED]` | Date from discovery.md or "—" if unavailable |

## Rules

- If there are no candidates yet, generate the HTML with the summary showing all zeros and an empty table body
- Sort candidates alphabetically by name
- Score coloring: 7-10 = high (green), 5-6 = mid (gold), 1-4 = low (coral)
- The average score in the summary should be rounded to one decimal place
- Use the checkmark character for done deliverables and an em dash for missing ones
