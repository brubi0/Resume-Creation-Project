# Resume Chat hardening: validation report (2026-11-27)

Branch `fix/resume-chat-reliability` (18 commits on `fix/open-items` 326b525, which sits on master 0db0ec4 / PR #7). **Local only: nothing pushed, merged, deployed or migrated.** Plan: `.planning/reliability-hardening-2026-11.md`.

Production code: 24 files, +2,445 / −501. Tests and e2e: 32 files, +4,602.

## 1. Confirmed root causes and fixes

| Area | Root cause (before) | Fix |
|---|---|---|
| A. Filenames | `deliverables.py` built paths from `candidate_name.replace(" ", "_")`, so `../` wrote outside the session dir | `storage.py`: UUID-only storage names, `safe_component` for download names (Unicode, RFC 5987), `resolve_inside` on every read/serve; profile slugs validated, exclusive create |
| B. Generation | `_pandoc_convert` swallowed errors and the DOCX row was saved anyway; regeneration duplicated rows; 4 Opus calls ran inside the HTTP request (proxy cuts at 120 s) | Background task with an atomic claim (409 on concurrent), staging dir plus all-or-nothing publish in one transaction, typed `DocumentError` messages, staged text reused on retry, base set replaced (never duplicated) |
| C. Sessions | `new-session` had no lock; `send` had no serialization or idempotency | Shared advisory lock plus `replaces_session_id`; turn protocol (Tx A claim → model call with no lock → Tx B re-lock and validate), `client_message_id` dedupe, `_owns_turn` guard, stale-turn resolution on read |
| D. META | The model's META was `setattr` onto the session unvalidated | `session_state.py`: strips every and truncated META block; schema, type and transition rules; status whitelist; contact merged field by field; size limits; logs carry reason codes only |
| E. Claude | Sync client inside async handlers blocked the event loop; errors surfaced as 500s | `AsyncAnthropic`, typed errors (Unavailable / Config / Truncated / Empty / Refusal), the candidate's answer kept as `failed` with "Try again"; fallback beta and effort preserved |
| F. Journey | Progress counted `len(discovery_data)`; skips/omissions not modelled | `interview.py` question ids per track, `progress()`, `discovery_complete()`; skips accumulate; `contact.omitted` never re-asked; completion needs every id answered or skipped and contact confirmed |
| G. Facts | Generation ignored the approved resume and the transcript, and resent the raw upload (an omitted phone could come back) | `<!--RESUME-->` capture → `approved_resume` becomes the final resume verbatim; `build_fact_snapshot` (contact minus omitted fields; the upload is redacted and excluded once approved); fact rules; post-generation checks for placeholders and unconfirmed contact details, with one regeneration |
| H. Upload | Whole body read into memory, extension-only checks, parser exception text echoed | 5 MB streamed cap, magic-byte sniffing, DOCX zip limits, PDF encrypted/page/no-text handling, 50k character cap, thread plus 20 s timeout, generic messages |
| I. Privacy | **Model-written HTML rendered with `dangerouslySetInnerHTML` in the app origin while the JWT sits in localStorage** (stored XSS reachable from a prompt-injected resume) | `<iframe sandbox="" srcDoc>` plus `CSP: sandbox` and `nosniff`; safe Markdown links; candidate deletion removes files; default-secret warnings; 401 without a token |

### Found during gates and the independent review (all fixed, each with a test that failed first)

- **High:** base regeneration would have deleted legacy targeted documents and their files (migration backfill plus a type-scoped delete).
- **Medium:**
  - A late reply could revert `deliverables_generated` and swap `approved_resume`.
  - A turn left pending by a restart never offered Try again.
  - A message that got 409 while another turn was busy vanished from the thread.
  - A late reply after a stale-turn takeover clobbered the newer turn.
- **Codex review of PR #9 (P2, fixed):**
  - A run orphaned by a restart stayed `running` with no Try again. Runs past the 30-minute window now show as failed in the admin list.
  - Starting a tailored resume didn't refresh the list, so its failure never showed.
  - The omitted-contact check missed Markdown autolinks, `mailto:`/`tel:` links and HTML-entity emails.
- **Low:**
  - Skipped questions replaced earlier skips.
  - Retry after a failed tailoring run reran the full base set.
  - A session deleted mid-turn caused a 500 or an orphan directory.
  - Retry was offered after the session had been replaced.
  - Word resumes showed a raw `resume_docx` label.

## 2. Validation totals (final run, orchestrator)

| Gate | Result |
|---|---|
| Backend (`app/backend/run-tests.sh`, real Postgres, mocked Claude) | **199 passed, 1 xfailed** (known migration/model timestamp drift, below) |
| Baseline before the work | 5 passed, 7 strict xfails describing the bugs; 6 of those xfails now pass as regular tests |
| PostgreSQL concurrency | Parallel first visits = 1 session; 10 concurrent new-session calls = 1 new session; new-session racing first visit; simultaneous sends (one wins, the other 409, nothing lost or duplicated); the same message twice = 1 model call; new interview while a reply is in flight; stale takeover; late reply after generation; other candidates never blocked |
| Mocked provider | Success, timeout, connection error, 429, 500/529, 401/403/404, refusal, max_tokens, empty text, malformed META; a 3 s slow reply leaves `/api/health` at 0.001 s and another candidate's messages at 0.009 s |
| Candidate journeys (10 spec scenarios) | All pass: with and without upload, early career, career changer, new industry profile, omitted phone/email, correction, refresh mid-interview, 503 then retry, new interview after completion |
| Authorization matrix | Candidate gets 403 on every `/api/admin/*` and generate/target route; no token gets 401; A cannot see B's chat, session or documents; admin access works |
| Upload | Valid PDF, DOCX and TXT; 6 MB; mislabelled files; DOCX decompression limits; encrypted, blank and 40-page PDFs; DOCX with an external relationship (no network); prompt-injection TXT stored as data only |
| Frontend | `npm run build` OK |
| Playwright mocked (390×844 and 1280×800) | **58/58**: chat failed, in flight, in progress, replaced and recovered; admin generating and failed; documents; Markdown preview with a long name (no horizontal overflow); HTML sandbox (script, onerror and `javascript:` never run, token unread) |
| Playwright journey (real backend plus fake provider) | **16/16**: login → skip upload → profile → contact → 12 questions → approve → admin generate → DOCX download (valid, candidate name, Word heading styles) |
| Documents | Synthetic sets for two candidates (HVAC manager with a 41-character name; marketing graduate) through real pandoc and the template; selectable text, heading styles, no placeholders |
| `git diff --check` | Clean |

**Not run:**
- Paid live-model tests. They need your approval and should use synthetic candidates.
- The production diagnostics run. It is read-only but needs your approval.
- Codex review: PR #8 clean; PR #9 raised 3 P2s, all fixed above.

## 3. Security and privacy review

- No secrets in git history. The `.env.example` key is a placeholder, and no candidate files are tracked (`candidates/` is gitignored).
- **Public repo contains `examples/Example_Resume_Bruno_Rubio.docx`** (the owner's real resume). Left untouched; decide whether to keep it public.
- **Remaining risks:**
  - The JWT lives in localStorage. Mitigated by removing the only HTML injection path; httpOnly cookies would be the next step.
  - Startup only warns if `JWT_SECRET`/`ADMIN_PASSWORD` are defaults. Compose requires `JWT_SECRET`, but `ADMIN_PASSWORD` falls back to `admin` in compose.
  - Logs carry ids and error class names only.

## 4. Representative outputs

- Rendered samples: `app/backend/tests/_out/` (gitignored; regenerate with `RUN_CMD="python -m tests.render_samples /out" ./run-tests.sh`).
- Screenshots: `app/e2e/screenshots/` (gitignored).

## 5. Read-only legacy-state diagnostics

```
cd ~/resume-chat/app && docker compose exec -T backend python -m app.diagnostics          # text
cd ~/resume-chat/app && docker compose exec -T backend python -m app.diagnostics --json   # machine
```

- Runs in a `READ ONLY` transaction, prints counts and UUIDs only (legacy filenames masked), and exits 0.
- Checks:
  - multiple active sessions
  - invalid phase or status
  - completed sessions with incomplete discovery (legacy sessions predate question ids, so they will show here)
  - rows with missing files
  - duplicate rows
  - files without rows
  - generated sessions missing required types (legacy names mapped)
  - generation running for more than 30 minutes
- Needs the new code deployed first; it repairs nothing.

## 6. Outstanding risks and limitations

1. **Migrations 0006 and 0007 run automatically on container start** (`alembic upgrade head` in the Dockerfile CMD). Deploying the branch migrates production: additive columns plus a backfill. Take a DB backup first.
2. Known pre-existing drift: migrations use `timestamptz` and the models use naive `DateTime`, and `ix_postings_session_id` exists only in the migration (strict xfail). Production is fine because it is built from migrations. Stacks built by `create_all` (the e2e stack) show reply times offset by the server timezone. Worth a follow-up migration.
3. The host nginx `proxy_read_timeout` is 120 s, but a chat reply can take longer (300 s timeout, SDK retries). The UI degrades gracefully (Not sent → Try again → "Still working…" → reply appears). Raising it to 300 s removes the hiccup.
4. Early-career resumes run 2 pages at about 550 words with the current Word template spacing; the rules target one page. The template or word budget needs a decision.
5. Escape doesn't close the preview modal once focus is inside the sandboxed iframe (the Close button works).
6. Behaviour of the real model under the new prompts (question ids, RESUME markers, `omitted`) is verified only with a scripted fake. One paid synthetic run per track is recommended before release.
7. Generation runs in-process: a restart mid-run shows `running` for up to 30 minutes, then the admin list marks it failed with Try again.

## 7. Suggested PR

**Title:** Resume Chat: interview reliability, candidate privacy and document integrity

**Description:**

Hardens the candidate journey end to end.
- **Uploads and storage:** safe document storage and serving; resume uploads are size-, type- and content-checked.
- **Generation:** documents generate in the background with an all-or-nothing contract.
- **Chat:** chat turns are serialized and idempotent and survive provider failures (answers are kept, Try again). The model's state updates are validated, never applied blindly.
- **Interview and facts:** the interview tracks real question ids, accepts skips and omitted contact fields, and the candidate-approved resume becomes the final resume.
- **Privacy:** model-written HTML now renders in a sandboxed iframe (closes a stored-XSS path to the admin token).
- **Tests and tooling:** adds a Postgres-backed test suite (199 tests), Playwright mocked and journey runs, synthetic document checks, and read-only diagnostics.

Migrations 0006 and 0007 are additive and run on deploy.
