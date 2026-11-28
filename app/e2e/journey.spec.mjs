// Full browser journey against the fake-provider API (compose profile `e2e`). Run via run-journey.sh.
// Candidate: login, skip upload, pick a profile, skip JD, answer all 12 questions, approve the resume.
// Admin: generate documents, wait until done, download the resume DOCX and inspect it.
// Env: E2E_API_PORT (host port of the api container), set by run-journey.sh.
import { chromium } from "playwright";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { startPreview, makeAsserts, noHScroll, shotsDir } from "./lib.mjs";

const { check, summary } = makeAsserts();
const API = `http://127.0.0.1:${process.env.E2E_API_PORT ?? "18765"}`;
const NAME = "Maximiliano Alejandro Fernández-Oyelaran";
const shot = (page, name) => page.screenshot({ path: path.join(shotsDir, `journey-${name}.png`) });

async function waitForApi() {
  const deadline = Date.now() + 90000;
  for (;;) {
    const ac = new AbortController();
    const t = setTimeout(() => ac.abort(), 2000); // ref'd on purpose: keeps the loop alive
    try {
      if ((await fetch(API + "/api/health", { signal: ac.signal })).ok) return;
    } catch {} finally {
      clearTimeout(t);
    }
    if (Date.now() > deadline) throw new Error("api did not become healthy");
    await new Promise((r) => setTimeout(r, 1000));
  }
}

async function apiJson(base, method, url, token, body) {
  const r = await fetch(base + url, {
    method,
    headers: { "content-type": "application/json", ...(token ? { authorization: `Bearer ${token}` } : {}) },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!r.ok) throw new Error(`${method} ${url} -> ${r.status} ${await r.text()}`);
  return r.json();
}

const ANSWERS = [
  "HVAC Service Manager for a commercial contractor.",
  "Apprentice, lead technician, dispatch supervisor, then service manager over 14 years.",
  "I fix the process, not just the unit: callbacks fell by about 31 percent.",
  "Moved 38 vans to standardized stock lists and cut restock time to 15 minutes.",
  "Callbacks down 31 percent, certified techs from 35 to 85 percent, agreements 820 to 1,950.",
  "I trained 22 technicians to NATE certification.",
  "Dispatch, maintenance agreements, flat-rate pricing, heat pumps.",
  "No gaps in employment.",
  "EPA 608 Universal, NATE heat pump service, OSHA 30.",
  "A.A.S. HVAC Technology, Austin Community College.",
  "Commercial and residential service in Central Texas, no relocation.",
  "Expert in dispatch and heat pumps; advanced in refrigerant tracking.",
];

async function sendAndWait(page, text, expectReply) {
  await page.getByPlaceholder("Type your answer").fill(text);
  await page.keyboard.press("Enter");
  await page.getByText(expectReply).first().waitFor({ timeout: 20000 });
}

let finished = false;

async function main() {
  await waitForApi();
  const preview = await startPreview(API);
  const base = preview.url; // vite preview proxies /api -> the fake-provider API
  const browser = await chromium.launch();
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "resume-e2e-"));
  try {
    // Provision the candidate through the admin API
    const admin = (await apiJson(base, "POST", "/api/auth/login", null, { username: "admin", password: "test-admin-pw" })).access_token;
    await apiJson(base, "POST", "/api/admin/candidates", admin, { name: NAME, password: "candidate-pw-1" });
    const cands = await apiJson(base, "GET", "/api/admin/candidates", admin);
    const created = cands.find((c) => c.name === NAME);
    check("candidate created via the admin API", !!created);
    const candUsername = created.username;

    // ---------------------------------------------------------- candidate, phone
    const cctx = await browser.newContext({ viewport: { width: 390, height: 844 } });
    const page = await cctx.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(base + "/login");
    await page.fill("#username", candUsername);
    await page.fill("#password", "candidate-pw-1");
    await page.click("button[type=submit]");
    await page.waitForURL("**/chat");
    // onboarding: skip upload, pick the first profile, skip the job description
    await page.getByRole("button", { name: "Skip for now" }).click();
    await page.locator("button[aria-pressed]").first().waitFor({ timeout: 10000 });
    await page.locator("button[aria-pressed]").first().click();
    await shot(page, "01-profile");
    await page.getByRole("button", { name: "Use this profile" }).click();
    await page.getByRole("button", { name: "Skip for now" }).click();
    await page.getByText("Is this contact info current?").waitFor({ timeout: 20000 });
    check("kickoff reached the interviewer (contact question shown)", true);
    await shot(page, "02-contact-question");

    await sendAndWait(page, "Austin, TX, max.fernandez@example.test, (512) 555-0147.", "Question 1 of 12 is next");
    for (let i = 0; i < 12; i++) {
      const expect = i < 11 ? `Question ${i + 2} of 12 is next` : "That is all twelve questions";
      await sendAndWait(page, ANSWERS[i], expect);
      if (i === 5) await shot(page, "03-mid-interview");
    }
    check("all 12 answers accepted", true);
    await sendAndWait(page, "Yes, please draft my resume.", "Any changes before I finalize?");
    const body = await page.locator("body").innerText();
    check("resume drafted in chat with the long name", body.includes("FERNÁNDEZ-OYELARAN"));
    check("RESUME/META markers are not shown", !body.includes("RESUME") || !body.includes("<!--"), body.match(/.{20}<!--.{20}/)?.[0] ?? "");
    const h = await noHScroll(page);
    check("chat has no horizontal overflow at 390px with the resume shown", h.ok, JSON.stringify(h));
    await shot(page, "04-resume-draft");
    await sendAndWait(page, "It looks perfect. It is final.", "your interview is complete");
    await page.getByRole("button", { name: "Your documents" }).first().waitFor({ timeout: 10000 });
    check("interview complete: Your documents offered, input hidden",
      (await page.getByPlaceholder("Type your answer").count()) === 0);
    await shot(page, "05-complete");
    check("candidate side: no page errors", errors.length === 0, errors.join(" | "));
    await cctx.close();

    // ---------------------------------------------------------- admin, desktop
    const actx = await browser.newContext({ viewport: { width: 1280, height: 800 }, acceptDownloads: true });
    const ap = await actx.newPage();
    await ap.goto(base + "/login");
    await ap.fill("#username", "admin");
    await ap.fill("#password", "test-admin-pw");
    await ap.click("button[type=submit]");
    await ap.waitForURL("**/admin");
    await ap.locator("span:visible", { hasText: "Ready for documents" }).first().waitFor({ timeout: 10000 });
    await shot(ap, "06-admin-ready");
    await ap.locator("button:visible", { hasText: "Generate documents" }).click();
    await ap.locator("span:visible", { hasText: "Documents ready" }).first().waitFor({ timeout: 90000 });
    check("admin generation finished: Documents ready", true);
    await shot(ap, "07-admin-done");
    await ap.locator("button:visible", { hasText: "Documents" }).first().click();
    await ap.waitForURL("**/deliverables");
    await ap.getByRole("button", { name: "Download" }).first().waitFor({ timeout: 10000 });
    const n = await ap.getByRole("button", { name: "Download" }).count();
    check("five base documents listed", n === 5, `count=${n}`);
    await shot(ap, "08-documents");

    // the Word resume: the row tagged "Word"
    const row = ap.locator("div.divide-y > div", { hasText: "Word" }).first();
    const [dl] = await Promise.all([
      ap.waitForEvent("download", { timeout: 15000 }),
      row.getByRole("button", { name: "Download" }).click(),
    ]);
    const dest = path.join(tmp, dl.suggestedFilename());
    await dl.saveAs(dest);
    check("downloaded file is a .docx named for the candidate",
      dl.suggestedFilename().endsWith(".docx") && dl.suggestedFilename().includes("Resume_FINAL"), dl.suggestedFilename());
    const listing = execFileSync("unzip", ["-l", dest], { encoding: "utf8" });
    check("DOCX is a valid zip with word/document.xml", listing.includes("word/document.xml"));
    const xml = execFileSync("unzip", ["-p", dest, "word/document.xml"], { encoding: "utf8", maxBuffer: 20 * 1024 * 1024 });
    const text = xml.replace(/<[^>]+>/g, "");
    check("DOCX text contains the candidate name", text.toUpperCase().includes(NAME.toUpperCase()), text.slice(0, 120));
    check("DOCX text contains resume content", text.includes("Professional Summary") && text.includes("Lone Star Comfort Systems"));
    check("DOCX has Word heading styles", /w:pStyle w:val="Heading[0-9]"/.test(xml));
    await ap.getByRole("button", { name: "Preview" }).first().click();
    await ap.locator(".fixed.inset-0 .md").waitFor({ timeout: 10000 });
    check("admin preview modal renders Markdown", true);
    await shot(ap, "09-preview");
    await actx.close();
  } finally {
    await browser.close();
    preview.stop();
    fs.rmSync(tmp, { recursive: true, force: true });
  }
  finished = true;
  process.exit(summary() ? 1 : 0);
}

// A silently drained event loop must never look like success.
process.on("exit", (code) => {
  if (!finished && code === 0) {
    console.error("FAIL  journey exited before finishing");
    process.exitCode = 1;
  }
});

main().catch((e) => {
  console.error("FAIL  journey crashed:", e);
  process.exit(1);
});
