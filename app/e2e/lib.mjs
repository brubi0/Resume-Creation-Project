// Shared helpers for the e2e scripts. No test framework: plain asserts, one process per spec.
import { spawn } from "node:child_process";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import fs from "node:fs";

export const here = path.dirname(fileURLToPath(import.meta.url));
export const frontendDir = path.resolve(here, "../frontend");
export const shotsDir = path.join(here, "screenshots");
fs.mkdirSync(shotsDir, { recursive: true });

export const VIEWPORTS = [
  { name: "mobile", width: 390, height: 844 },
  { name: "desktop", width: 1280, height: 800 },
];

export function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.listen(0, "127.0.0.1", () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
    s.on("error", reject);
  });
}

/** Serve app/frontend/dist with `vite preview` (SPA fallback, optional /api proxy). Returns {url, stop}. */
export async function startPreview(apiUrl) {
  const port = await freePort();
  const env = { ...process.env };
  if (apiUrl) env.E2E_API_URL = apiUrl;
  const child = spawn(
    process.execPath,
    ["node_modules/vite/bin/vite.js", "preview", "--config", "vite.e2e.config.ts",
     "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
    { cwd: frontendDir, env, stdio: ["ignore", "pipe", "pipe"] },
  );
  let log = "";
  child.stdout.on("data", (d) => (log += d));
  child.stderr.on("data", (d) => (log += d));
  const url = `http://127.0.0.1:${port}`;
  const deadline = Date.now() + 30000;
  for (;;) {
    try {
      const r = await fetch(url + "/");
      if (r.ok) break;
    } catch {}
    if (Date.now() > deadline || child.exitCode !== null) {
      child.kill();
      throw new Error("vite preview did not start:\n" + log);
    }
    await new Promise((r) => setTimeout(r, 200));
  }
  return { url, pid: child.pid, stop: () => child.kill() };
}

export function makeAsserts() {
  const results = [];
  return {
    results,
    check(name, cond, detail = "") {
      results.push({ name, ok: !!cond, detail });
      console.log(`${cond ? "PASS" : "FAIL"}  ${name}${!cond && detail ? "  -> " + detail : ""}`);
    },
    summary() {
      const failed = results.filter((r) => !r.ok);
      console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
      return failed.length;
    },
  };
}

/** True when nothing on the page forces horizontal scrolling. */
export async function noHScroll(page) {
  return page.evaluate(() => {
    const d = document.documentElement;
    return { sw: d.scrollWidth, cw: d.clientWidth, ok: d.scrollWidth <= d.clientWidth };
  });
}
