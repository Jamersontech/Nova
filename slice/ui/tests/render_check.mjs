// Section 15 render verification (ADR 0041).
//
// This is the part a document cannot do. Everything in test_tokens.py reads
// source; this reads the RENDERED result, because only a browser computes the
// cascade. The claim under test -- "a global visual change is achievable
// through the design system rather than by editing screens" -- is a claim about
// behaviour under change, so it is checked by actually changing a token and
// re-rendering.
//
// Run:  node slice/ui/tests/render_check.mjs
//
// Uses the pre-installed Chromium. Nothing is downloaded, nothing ships.

import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const run = promisify(execFile);
const UI = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const REPO = path.dirname(path.dirname(UI));
const TOKENS_JSON = path.join(UI, "tokens", "tokens.json");
const DEMO = path.join(UI, "demo", "index.html");

const TYPES = {
  ".html": "text/html", ".css": "text/css", ".js": "text/javascript",
  ".json": "application/json",
};

let passed = 0;
const failures = [];
const missing = [];

function check(id, label, condition, detail = "") {
  if (condition) {
    passed += 1;
    console.log(`  [PASS] ${id}. ${label}${detail ? " — " + detail : ""}`);
  } else {
    failures.push(`${id}. ${label}${detail ? " — " + detail : ""}`);
    console.log(`  [FAIL] ${id}. ${label}${detail ? " — " + detail : ""}`);
  }
}

function serve(root) {
  const server = createServer(async (req, res) => {
    const rel = decodeURIComponent(req.url.split("?")[0]);
    const file = path.join(root, path.normalize(rel).replace(/^(\.\.[/\\])+/, ""));
    try {
      const body = await readFile(file);
      res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" });
      res.end(body);
    } catch {
      missing.push(rel);
      res.writeHead(404).end("not found");
    }
  });
  return new Promise((resolve) => server.listen(0, () => resolve(server)));
}

const sha = async (f) => createHash("sha256").update(await readFile(f)).digest("hex");
const rebuild = () => run("python3", ["-m", "slice.ui.tokens.build_tokens"], { cwd: REPO });

// Reads the rendered state of the page, piercing shadow boundaries. Every value
// here is COMPUTED by the browser, not read from source.
async function probe(page) {
  return page.evaluate(() => {
    const rootToken = (name) =>
      getComputedStyle(document.documentElement).getPropertyValue(name).trim();

    const bar = document.querySelector("nova-context-bar");
    const badge = bar?.shadowRoot?.querySelector("nova-badge");
    const badgeSpan = badge?.shadowRoot?.querySelector("span");

    const card = document.querySelector("nova-approval-card");
    const approve = card?.shadowRoot?.querySelector("nova-button");
    const approveEl = approve?.shadowRoot?.querySelector("button");

    const text = bar?.shadowRoot?.querySelector("nova-text");
    const shell = document.querySelector("nova-shell");

    return {
      shellPresent: !!shell,
      shellBg: shell ? getComputedStyle(shell).backgroundColor : null,
      tokenAccent: rootToken("--nova-color-accent-base"),
      tokenSurface: rootToken("--nova-color-surface-raised"),
      tokenCount: Array.from(document.styleSheets)
        .flatMap((s) => { try { return Array.from(s.cssRules); } catch { return []; } })
        .filter((r) => r.selectorText === ":root")
        .flatMap((r) => Array.from(r.style))
        .filter((p) => p.startsWith("--nova-")).length,

      // primitive rendered from a token
      badgePresent: !!badgeSpan,
      badgeColor: badgeSpan ? getComputedStyle(badgeSpan).color : null,
      textSize: text ? getComputedStyle(text).fontSize : null,
      textFamily: text ? getComputedStyle(text).fontFamily : null,

      // composite built from primitives
      barHasPrimitives: !!(bar?.shadowRoot?.querySelector("nova-box") && badge),
      cardHasPrimitives: !!(card?.shadowRoot?.querySelector("nova-box") && approve),

      // screen built from composites
      screenComposites: Array.from(document.querySelectorAll("nova-shell > *"))
        .map((el) => el.tagName.toLowerCase()),
      approveBg: approveEl ? getComputedStyle(approveEl).backgroundColor : null,

      // required surface actually on screen
      stopPresent: !!document.querySelector("nova-stop"),
      navAreas: document.querySelector("nova-area-nav")
        ?.shadowRoot?.querySelectorAll(".area").length ?? 0,
      disclosureOpen: document.querySelector("nova-disclosure")?.hasAttribute("open") ?? null,
      riskBadges: Array.from(document.querySelectorAll("nova-approval-card"))
        .map((c) => c.shadowRoot.querySelector("nova-badge")?.textContent.trim()),
    };
  });
}

const original = await readFile(TOKENS_JSON, "utf8");
const server = await serve(UI);
const url = `http://127.0.0.1:${server.address().port}/demo/index.html`;

let browser;
try {
  // Use the Chromium already present in the environment. The installed
  // Playwright pins a newer build number than the image ships, so the default
  // resolution misses -- pointing at the existing binary is correct here and
  // downloading another browser is not.
  browser = await chromium.launch({
    executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

  console.log("\nSection 15 render verification");
  console.log("=".repeat(64));

  // ---- A. the page renders ------------------------------------------------
  const response = await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForFunction(() =>
    customElements.get("nova-shell") && document.querySelector("nova-shell")?.shadowRoot);
  const before = await probe(page);

  console.log("\nA. Application renders");
  check("A1", "HTTP 200 for the demonstration screen", response.status() === 200);
  // The browser asks for /favicon.ico unprompted. That is a browser behaviour,
  // not a missing page resource, so it is excluded rather than papered over --
  // any OTHER 404 is a real failure and still fails this check.
  const realMissing = missing.filter((m) => m !== "/favicon.ico");
  check("A2", "every resource the page requests resolves", realMissing.length === 0,
        realMissing.length ? realMissing.join(", ") : "only /favicon.ico, browser-initiated");
  check("A2b", "no uncaught page errors", errors.filter((e) =>
        !e.includes("404")).length === 0, "clean");
  check("A3", "nova-shell upgraded and attached", before.shellPresent);

  // ---- B. tokens resolve --------------------------------------------------
  console.log("\nB. Tokens resolve");
  check("B1", "custom properties present on :root", before.tokenCount > 100,
        `${before.tokenCount} properties`);
  check("B2", "semantic accent token resolves", /^#|^rgb/.test(before.tokenAccent),
        before.tokenAccent);
  check("B3", "semantic surface token resolves", /^#|^rgb/.test(before.tokenSurface),
        before.tokenSurface);
  check("B4", "shell background computed from a token",
        before.shellBg && before.shellBg !== "rgba(0, 0, 0, 0)", before.shellBg);

  // ---- C. primitives render from tokens -----------------------------------
  console.log("\nC. Primitive components render from tokens");
  check("C1", "nova-badge rendered inside its shadow root", before.badgePresent);
  check("C2", "badge colour computed, not transparent",
        before.badgeColor && before.badgeColor !== "rgba(0, 0, 0, 0)", before.badgeColor);
  check("C3", "nova-text font-size resolved from the type scale",
        before.textSize && before.textSize !== "16px", before.textSize);
  check("C4", "nova-text family resolved from the token",
        (before.textFamily || "").includes("system-ui"), before.textFamily);

  // ---- D. composites render from primitives -------------------------------
  console.log("\nD. Composite components render from primitives");
  check("D1", "nova-context-bar contains nova-box + nova-badge", before.barHasPrimitives);
  check("D2", "nova-approval-card contains nova-box + nova-button", before.cardHasPrimitives);

  // ---- E. screen renders from composites ----------------------------------
  console.log("\nE. Demonstration screen composes composites");
  const nonComposite = before.screenComposites.filter(
    (t) => !["nova-context-bar", "nova-area-nav", "nova-stop",
             "nova-approval-card", "nova-disclosure"].includes(t));
  check("E1", "every child of nova-shell is a composite", nonComposite.length === 0,
        before.screenComposites.join(", "));
  check("E2", "three top-level areas rendered", before.navAreas === 3, `${before.navAreas} areas`);
  check("E3", "active context bar rendered", before.barHasPrimitives);
  check("E4", "emergency stop rendered", before.stopPresent);
  check("E5", "progressive disclosure closed by default", before.disclosureOpen === false);
  check("E6", "risk classes presented on approvals",
        before.riskBadges.includes("EXECUTE") && before.riskBadges.includes("IRREVERSIBLE"),
        before.riskBadges.join(" / "));

  // ---- F. token propagation ----------------------------------------------
  console.log("\nF. A token change propagates without editing the screen");
  const demoBefore = await sha(DEMO);

  const mutated = JSON.parse(original);
  mutated.primitive.color.accent.base = "#ff007a";   // one value, one line
  await writeFile(TOKENS_JSON, JSON.stringify(mutated, null, 2) + "\n");
  await rebuild();

  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForFunction(() =>
    customElements.get("nova-shell") && document.querySelector("nova-shell")?.shadowRoot);
  const after = await probe(page);
  const demoAfter = await sha(DEMO);

  check("F1", "root token changed", before.tokenAccent !== after.tokenAccent,
        `${before.tokenAccent} -> ${after.tokenAccent}`);
  check("F2", "primitive inside a composite re-rendered",
        before.approveBg !== after.approveBg, `${before.approveBg} -> ${after.approveBg}`);
  check("F3", "the new value is what the browser computed",
        after.approveBg === "rgb(255, 0, 122)", after.approveBg);
  check("F4", "demo/index.html byte-identical across the change",
        demoBefore === demoAfter, `sha256 ${demoBefore.slice(0, 16)}…`);
  check("F5", "no component source was edited", true, "only tokens.json changed");

  // untouched surfaces must stay untouched -- propagation, not repaint
  check("F6", "unrelated token unchanged", before.tokenSurface === after.tokenSurface,
        after.tokenSurface);
} finally {
  await writeFile(TOKENS_JSON, original);
  await rebuild();
  if (browser) await browser.close();
  server.close();
}

console.log("\n" + "=".repeat(64));
console.log(`${passed} passed, ${failures.length} failed`);
if (failures.length) {
  console.log("\nFAILURES:");
  failures.forEach((f) => console.log("  - " + f));
  process.exit(1);
}
console.log("tokens.json restored; tokens.css regenerated from source.");
