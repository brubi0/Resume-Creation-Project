// Mocked-API browser checks against the BUILT frontend (app/frontend/dist), at 390x844 and 1280x800.
// Run: (cd ../frontend && npm run build) && node mocked.spec.mjs      (exit 1 on any failed check)
import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { here, VIEWPORTS, startPreview, makeAsserts, noHScroll, shotsDir } from "./lib.mjs";

const { check, summary } = makeAsserts();
const FIXTURE_MD = fs.readFileSync(
  path.resolve(here, "../backend/tests/fixtures/documents/experienced/resume.md"), "utf8");
const LONG_NAME = "Maximiliano Alejandro Fernández-Oyelaran";
const NOW = new Date().toISOString();
const uuid = (n) => `00000000-0000-4000-8000-${String(n).padStart(12, "0")}`;

const CANDIDATE = { id: uuid(1), name: LONG_NAME, username: "max_long", role: "candidate", created_at: NOW };
const ADMIN = { id: uuid(2), name: "Admin", username: "admin", role: "admin", created_at: NOW };
const SESSION = {
  id: uuid(10), phase: 2, experience_level: "experienced", profile_slug: "hvac", job_description: null,
  resume_text: null, status: "active", version: 3, turn_state: "idle", created_at: NOW,
};
const msg = (n, role, content, extra = {}) => ({
  id: uuid(100 + n), role, content, phase: 2, status: "ok", client_message_id: null,
  created_at: NOW, ...extra,
});
const BASE_MESSAGES = [
  msg(1, "assistant", "Welcome. **Question 3 of 12:** which achievement are you proudest of at work?"),
  msg(2, "user", "Cutting callbacks by 31% in 18 months."),
  msg(3, "assistant", "That is a strong result. What changed in your process to get there?"),
];

const json = (route, status, body) =>
  route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

/** Route-mock /api/**: handlers[`METHOD /path`] = (req, route, call) => fulfilled. Unknown calls fail the run. */
async function mockApi(page, handlers) {
  const calls = [];
  const unmocked = [];
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const url = new URL(req.url());
    const key = `${req.method()} ${url.pathname.replace(/^\/api/, "")}`;
    let body = null;
    try { body = req.postDataJSON(); } catch {}
    const call = { key, body, url: url.pathname + url.search };
    calls.push(call);
    const h = handlers[key] ?? Object.entries(handlers).find(([k]) => k.endsWith("*") && key.startsWith(k.slice(0, -1)))?.[1];
    if (!h) { unmocked.push(key); return json(route, 404, { detail: "unmocked " + key }); }
    return h(req, route, call);
  });
  return { calls, unmocked };
}

async function open(browser, vp, user, path_, handlers) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  const m = await mockApi(page, {
    "GET /auth/me": (_r, route) => json(route, 200, user),
    ...handlers,
  });
  await page.goto(base + "/login");
  // seed AFTER first navigation: addInitScript would also run in sandboxed iframes
  await page.evaluate(() => localStorage.setItem("token", "mock-token"));
  await page.goto(base + path_);
  return { ctx, page, errors, ...m };
}

const shot = (page, vp, name) =>
  page.screenshot({ path: path.join(shotsDir, `mocked-${vp.name}-${name}.png`), fullPage: false });

const chatHandlers = (over = {}) => ({
  "GET /chat/session": (_r, route) => json(route, 200, SESSION),
  "GET /chat/messages": (_r, route) => json(route, 200, BASE_MESSAGES),
  "GET /chat/status": (_r, route) => json(route, 200, SESSION),
  ...over,
});

let base;

async function loginFlow(browser, vp) {
  const ctx = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });
  const page = await ctx.newPage();
  await mockApi(page, {
    "POST /auth/login": (_r, route) => json(route, 200, { access_token: "mock-token", token_type: "bearer" }),
    "GET /auth/me": (_r, route) => json(route, 200, CANDIDATE),
    ...chatHandlers(),
  });
  await page.goto(base + "/login");
  await shot(page, vp, "login");
  await page.fill("#username", "max_long");
  await page.fill("#password", "pw");
  await page.click("button[type=submit]");
  await page.waitForURL("**/chat");
  await page.getByText("which achievement are you proudest of").waitFor({ timeout: 10000 });
  const h = await noHScroll(page);
  check(`[${vp.name}] login -> chat renders, no horizontal overflow`, h.ok, JSON.stringify(h));
  await shot(page, vp, "chat");
  await ctx.close();
}

async function chatRetry(browser, vp) {
  let n = 0;
  const reply = msg(4, "assistant", "Thanks. Next: which tools did you use to track callbacks?");
  const { ctx, page, calls } = await open(browser, vp, CANDIDATE, "/chat", chatHandlers({
    "POST /chat/send": async (_r, route) => {
      n += 1;
      if (n === 1) return json(route, 503, { detail: "The AI service is unavailable." });
      await new Promise((r) => setTimeout(r, 1200));
      return json(route, 200, reply);
    },
  }));
  await page.getByPlaceholder("Type your answer").fill("A shared spreadsheet and the dispatch board.");
  await page.keyboard.press("Enter");
  await page.getByText("Not sent.").waitFor({ timeout: 8000 });
  check(`[${vp.name}] failed send shows "Not sent." and a retry`, await page.getByRole("button", { name: "Try again" }).isVisible());
  await shot(page, vp, "chat-failed");
  await page.getByRole("button", { name: "Try again" }).click();
  await page.getByText("Your interviewer is writing…").waitFor({ timeout: 5000 });
  await shot(page, vp, "chat-in-flight");
  await page.getByText("which tools did you use to track callbacks").waitFor({ timeout: 8000 });
  const sends = calls.filter((c) => c.key === "POST /chat/send");
  check(`[${vp.name}] retry reuses the same client_message_id`,
    sends.length === 2 && sends[0].body.client_message_id && sends[0].body.client_message_id === sends[1].body.client_message_id);
  check(`[${vp.name}] retry replaced the failed state`, (await page.getByText("Not sent.").count()) === 0);
  const h = await noHScroll(page);
  check(`[${vp.name}] chat thread has no horizontal overflow`, h.ok, JSON.stringify(h));
  await shot(page, vp, "chat-recovered");
  await ctx.close();
}

async function chatInProgress(browser, vp) {
  let polls = 0;
  const reply = msg(5, "assistant", "Thanks for waiting. Here is the next question about your team.");
  const { ctx, page } = await open(browser, vp, CANDIDATE, "/chat", chatHandlers({
    "POST /chat/send": (_r, route) => json(route, 409, { code: "turn_in_progress", detail: "busy", message: "busy" }),
    "GET /chat/session": (_r, route) => {
      polls += 1;
      return json(route, 200, { ...SESSION, turn_state: polls <= 2 ? "pending" : "idle" });
    },
    "GET /chat/messages": (_r, route) =>
      json(route, 200, polls >= 3 ? [...BASE_MESSAGES, msg(6, "user", "Six technicians."), reply] : BASE_MESSAGES),
  }));
  await page.getByPlaceholder("Type your answer").fill("Six technicians.");
  await page.keyboard.press("Enter");
  await page.getByText("Still working on your last message").waitFor({ timeout: 8000 });
  await shot(page, vp, "chat-in-progress");
  check(`[${vp.name}] in-progress notice shown while the turn is pending`, true);
  await page.getByText("Thanks for waiting. Here is the next question").waitFor({ timeout: 20000 });
  check(`[${vp.name}] reply appears once the turn is idle`, (await page.getByText("Still working on your last message").count()) === 0);
  await ctx.close();
}

async function chatNewMessage409(browser, vp) {
  // The server never stores the message (409 before it is saved): the text must survive the poll.
  let polls = 0;
  let sends = 0;
  const reply = msg(7, "assistant", "Got it. What was the biggest obstacle along the way?");
  const { ctx, page, calls } = await open(browser, vp, CANDIDATE, "/chat", chatHandlers({
    "POST /chat/send": (_r, route) => {
      sends += 1;
      if (sends === 1) return json(route, 409, { code: "turn_in_progress", detail: "busy", message: "busy" });
      return json(route, 200, reply);
    },
    "GET /chat/session": (_r, route) => {
      polls += 1;
      return json(route, 200, { ...SESSION, turn_state: polls <= 2 ? "pending" : "idle" });
    },
  }));
  const text = "We trained two apprentices on the dispatch board.";
  await page.getByPlaceholder("Type your answer").fill(text);
  await page.keyboard.press("Enter");
  await page.getByText("Still working on your last message").waitFor({ timeout: 8000 });
  check(`[${vp.name}] unsent message stays visible while polling`, (await page.getByText(text).count()) === 1);
  await page.getByText("Still working on your last message").waitFor({ state: "detached", timeout: 20000 });
  check(`[${vp.name}] unsent message still visible after the poll, with Try again`,
    (await page.getByText(text).count()) === 1 && (await page.getByRole("button", { name: "Try again" }).isVisible()));
  const getsAtIdle = calls.filter((c) => c.key === "GET /chat/session").length;
  await page.waitForTimeout(4000);
  check(`[${vp.name}] polling stops once the server reports idle`,
    calls.filter((c) => c.key === "GET /chat/session").length === getsAtIdle);
  await shot(page, vp, "chat-unsent-409");
  await page.getByRole("button", { name: "Try again" }).click();
  await page.getByText("biggest obstacle along the way").waitFor({ timeout: 8000 });
  const sent = calls.filter((c) => c.key === "POST /chat/send");
  check(`[${vp.name}] Try again resends the same client_message_id`,
    sent.length === 2 && sent[0].body.client_message_id === sent[1].body.client_message_id);
  await ctx.close();
}

async function chatReplaced(browser, vp) {
  const { ctx, page } = await open(browser, vp, CANDIDATE, "/chat", chatHandlers({
    "POST /chat/send": (_r, route) => json(route, 409, { code: "session_replaced", detail: "replaced", message: "replaced" }),
  }));
  await page.getByPlaceholder("Type your answer").fill("Hello again.");
  await page.keyboard.press("Enter");
  await page.getByText("This interview was replaced in another tab.").waitFor({ timeout: 8000 });
  check(`[${vp.name}] replaced state offers Reload and hides the input`,
    (await page.getByRole("button", { name: "Reload" }).isVisible()) && (await page.getByPlaceholder("Type your answer").count()) === 0);
  await shot(page, vp, "chat-replaced");
  await ctx.close();
}

const adminCandidates = (phase) => [
  { id: uuid(21), name: LONG_NAME, username: "max_long_username_example", created_at: NOW, session_id: uuid(31),
    session_status: "interview_complete", session_phase: 3, completed_sets: 0,
    generation_status: phase === "poll" ? "running" : "running", generation_error: null },
  { id: uuid(22), name: "Tessa Okonkwo-Bell", username: "tessa", created_at: NOW, session_id: uuid(32),
    session_status: "interview_complete", session_phase: 3, completed_sets: 0,
    generation_status: "failed", generation_error: "The AI service was unavailable. Try again in a few minutes.",
    generation_kind: "targeted", generation_posting_id: uuid(41) },
  { id: uuid(23), name: "Rosa Delgado", username: "rosa", created_at: NOW, session_id: uuid(33),
    session_status: "interview_complete", session_phase: 3, completed_sets: 0, generation_status: "idle", generation_error: null },
  { id: uuid(24), name: "Hector Vance", username: "hector", created_at: NOW, session_id: uuid(34),
    session_status: "deliverables_generated", session_phase: 7, completed_sets: 2, generation_status: "done", generation_error: null },
];

async function adminStates(browser, vp) {
  let loads = 0;
  const { ctx, page, calls } = await open(browser, vp, ADMIN, "/admin", {
    "POST /deliverables/target/*": (_r, route) => json(route, 202, { generation_status: "running" }),
    "GET /admin/candidates": (_r, route) => {
      loads += 1;
      const list = adminCandidates();
      if (loads >= 2) {
        list[0] = { ...list[0], session_status: "deliverables_generated", session_phase: 7,
                    generation_status: "done", completed_sets: 1 };
      }
      return json(route, 200, list);
    },
  });
  await page.locator("p[role=status]:visible", { hasText: "Generating documents…" }).waitFor({ timeout: 8000 });
  check(`[${vp.name}] admin shows the generating state`, true);
  check(`[${vp.name}] admin shows the failed state with its message and Try again`,
    (await page.locator("p[role=alert]:visible", { hasText: "The AI service was unavailable" }).count()) === 1 &&
    (await page.locator("button:visible", { hasText: "Try again" }).count()) === 1);
  await page.locator("button:visible", { hasText: "Try again" }).click();
  await page.waitForTimeout(500);
  check(`[${vp.name}] a failed tailoring run retries the targeted posting, not base generation`,
    calls.some((c) => c.key === `POST /deliverables/target/${uuid(41)}/retry`) &&
    !calls.some((c) => c.key === "POST /deliverables/generate"));
  check(`[${vp.name}] admin shows Generate documents and Tailor to a job`,
    (await page.locator("button:visible", { hasText: "Generate documents" }).count()) === 1 &&
    (await page.locator("button:visible", { hasText: "Tailor to a job" }).count()) >= 1);
  const h = await noHScroll(page);
  check(`[${vp.name}] admin dashboard has no horizontal overflow (long name)`, h.ok, JSON.stringify(h));
  await shot(page, vp, "admin-generating");
  // the dashboard polls every 5 s while something runs; the second load flips it to done
  await page.locator("p[role=status]:visible", { hasText: "Generating documents…" }).waitFor({ state: "detached", timeout: 15000 });
  check(`[${vp.name}] admin poll moves a run from generating to done`, true);
  await shot(page, vp, "admin-done");
  await ctx.close();
}

async function adminTargetStartRefreshes(browser, vp) {
  // Nothing running before targeting starts: the list must reload so polling picks the run up.
  let loads = 0;
  let targeted = false;
  const idle = () => adminCandidates().map((c) => (c.generation_status === "running" || c.generation_status === "failed")
    ? { ...c, generation_status: "idle", generation_error: null } : c);
  const { ctx, page } = await open(browser, vp, ADMIN, "/admin", {
    "POST /deliverables/target": (_r, route) => { targeted = true; return json(route, 202, { generation_status: "running" }); },
    "GET /admin/candidates": (_r, route) => {
      loads += 1;
      const list = idle();
      if (targeted) list[3] = { ...list[3], generation_status: "running", generation_kind: "targeted" };
      return json(route, 200, list);
    },
  });
  await page.locator("button:visible", { hasText: "Tailor to a job" }).first().waitFor({ timeout: 8000 });
  const before = loads;
  await page.locator("button:visible", { hasText: "Tailor to a job" }).last().click();
  await page.getByPlaceholder("Acme Corp").fill("Gulf Air Systems");
  await page.getByPlaceholder("NetSuite Administrator").fill("Service Manager");
  await page.getByPlaceholder("Paste the full job posting here").fill("Service Manager at Gulf Air Systems. Lead HVAC technicians.");
  await page.getByRole("button", { name: "Generate tailored resume" }).click();
  await page.locator("p[role=status]:visible", { hasText: "Generating documents…" }).waitFor({ timeout: 8000 });
  check(`[${vp.name}] starting a tailored resume reloads the list and shows it generating`, targeted && loads > before);
  await ctx.close();
}

const DELIVERABLES = [
  ["resume_md", "Maximiliano_Alejandro_Fernandez-Oyelaran_Resume_FINAL.md"],
  ["resume_docx", "Maximiliano_Alejandro_Fernandez-Oyelaran_Resume_FINAL.docx"],
  ["interview_prep_md", "Maximiliano_Alejandro_Fernandez-Oyelaran_Interview_Prep.md"],
  ["skills_matrix_html", "Maximiliano_Alejandro_Fernandez-Oyelaran_Skills_Matrix.html"],
  ["score_card_md", "Maximiliano_Alejandro_Fernandez-Oyelaran_Score_Card.md"],
].map(([type, filename], i) => ({
  id: uuid(200 + i), session_id: SESSION.id, type, filename, created_at: NOW,
  candidate_name: LONG_NAME, target_role: "HVAC Service Manager",
}));

const EVIL_HTML = `<!DOCTYPE html><html><body><h1>Skills</h1>
<script>window.__pwned = 1; try { window.top.__pwned = 2; window.parent.__pwned = 3; } catch (e) {}</script>
<img src="x" onerror="try { window.top.__pwned = 4 } catch (e) {}"></body></html>`;

async function documents(browser, vp) {
  const downloads = [];
  const { ctx, page, calls, errors } = await open(browser, vp, ADMIN, "/deliverables", {
    "GET /deliverables": (_r, route) => json(route, 200, DELIVERABLES),
    "GET /deliverables/*": (req, route) => {
      const m = new URL(req.url()).pathname.match(/deliverables\/([^/]+)\/(preview|download)/);
      const d = DELIVERABLES.find((x) => x.id === m?.[1]);
      if (!d) return json(route, 404, { detail: "nope" });
      if (m[2] === "download") {
        downloads.push(d.id);
        return route.fulfill({
          status: 200, contentType: "application/octet-stream",
          headers: { "content-disposition": `attachment; filename="${d.filename}"` },
          body: Buffer.from("downloaded:" + d.type),
        });
      }
      if (d.type === "skills_matrix_html") {
        return json(route, 200, { content: EVIL_HTML, content_type: "text/html", filename: d.filename });
      }
      return json(route, 200, {
        content: FIXTURE_MD, content_type: "text/markdown", filename: d.filename,
      });
    },
  });
  await page.getByText("All documents").first().waitFor({ timeout: 8000 });
  const groupTitle = page.getByRole("heading", { level: 3 }).first();
  check(`[${vp.name}] document list shows the long-name group`, (await groupTitle.innerText()).includes("Fernández-Oyelaran"));
  check(`[${vp.name}] five base documents listed`, (await page.getByRole("button", { name: "Download" }).count()) === 5);
  let h = await noHScroll(page);
  check(`[${vp.name}] document list has no horizontal overflow`, h.ok, JSON.stringify(h));
  await shot(page, vp, "documents");

  // Markdown preview
  await page.getByRole("button", { name: "Preview" }).nth(0).click();
  await page.getByRole("heading", { name: /FERNÁNDEZ-OYELARAN/ }).waitFor({ timeout: 8000 });
  const m = await page.evaluate(() => {
    const o = document.querySelector(".fixed.inset-0");
    const out = {};
    for (const [k, el] of Object.entries({
      overlay: o, scroller: o.querySelector(".overflow-y-auto"), md: o.querySelector(".md"),
      page: document.documentElement,
    })) out[k] = { sw: el.scrollWidth, cw: el.clientWidth, ok: el.scrollWidth <= el.clientWidth };
    return out;
  });
  check(`[${vp.name}] markdown preview (long name) has no horizontal overflow`,
    Object.values(m).every((x) => x.ok), JSON.stringify(m));
  await shot(page, vp, "preview-markdown");
  await page.keyboard.press("Escape");

  // HTML preview must stay inert
  await page.getByRole("button", { name: "Preview" }).nth(2).click();
  await page.locator("iframe").waitFor({ timeout: 8000 });
  await page.waitForTimeout(800);
  const sandbox = await page.locator("iframe").getAttribute("sandbox");
  const topPwned = await page.evaluate(() => window.__pwned);
  const frame = page.frames().find((f) => f !== page.mainFrame());
  const framePwned = frame ? await frame.evaluate(() => window.__pwned).catch(() => "unreachable") : "no-frame";
  check(`[${vp.name}] HTML preview iframe has sandbox="" (no allowances)`, sandbox === "", `sandbox=${JSON.stringify(sandbox)}`);
  check(`[${vp.name}] preview scripts did not run in the app page`, topPwned === undefined, `window.__pwned=${topPwned}`);
  check(`[${vp.name}] preview scripts did not run inside the frame`, framePwned === undefined || framePwned === "unreachable", String(framePwned));
  await shot(page, vp, "preview-html-sandboxed");
  await page.keyboard.press("Escape");

  // Download link
  const [dl] = await Promise.all([
    page.waitForEvent("download", { timeout: 8000 }),
    page.getByRole("button", { name: "Download" }).nth(1).click(),
  ]);
  const text = fs.readFileSync(await dl.path(), "utf8");
  check(`[${vp.name}] Download saves the file under its filename`,
    dl.suggestedFilename() === DELIVERABLES[1].filename && text === "downloaded:resume_docx",
    `${dl.suggestedFilename()} / ${text}`);
  check(`[${vp.name}] download used the authenticated API route`,
    calls.some((c) => c.key === "GET /deliverables/" + DELIVERABLES[1].id + "/download") && downloads.length === 1);
  check(`[${vp.name}] no page errors`, errors.length === 0, errors.join(" | "));
  await ctx.close();
}

const main = async () => {
  const preview = await startPreview(null);
  base = preview.url;
  const browser = await chromium.launch();
  try {
    for (const vp of VIEWPORTS) {
      for (const fn of [loginFlow, chatRetry, chatInProgress, chatNewMessage409, chatReplaced, adminStates, adminTargetStartRefreshes, documents]) {
        try {
          await fn(browser, vp);
        } catch (e) {
          check(`[${vp.name}] ${fn.name} ran to completion`, false, String(e).split("\n")[0]);
        }
      }
    }
  } finally {
    await browser.close();
    preview.stop();
  }
  process.exit(summary() ? 1 : 0);
};
main();
