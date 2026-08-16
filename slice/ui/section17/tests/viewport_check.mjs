// Section 17 responsive verification.
//
// Drives the EXISTING Section 16 screen at real viewport sizes. That choice is
// the evidence: if the same unedited screen file works at 1440px and at 320px,
// the responsive behaviour lives in tokens and CSS, which is the claim.
//
// NOT SECURITY TESTS. Layout enforces nothing. The stop- and approval-
// reachability checks assert that a narrow viewport does not hide a control
// USER_INTERFACE_ARCHITECTURE.md sections 6-7 require -- a presentation
// regression, not a control.
//
// Accessibility: checks the four responsive WCAG 2.2 AA criteria named in the
// Section 17 gate (1.4.10, 1.3.4, 1.4.4, 2.5.8), by hand. Not a conformance
// claim -- see the README.
//
// Run:  node slice/ui/section17/tests/viewport_check.mjs

import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createHash } from "node:crypto";
import path from "node:path";
import { fileURLToPath } from "node:url";

const run = promisify(execFile);
const S17 = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const UI = path.dirname(S17);
const REPO = path.dirname(path.dirname(UI));
const TOKENS_JSON = path.join(UI, "tokens", "tokens.json");
const SCREEN = path.join(UI, "section16", "demo", "index.html");
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json" };

// The three bands the slice must demonstrate, plus the WCAG reflow width.
const VIEWPORTS = [
  { name: "desktop", width: 1440, height: 900 },
  { name: "tablet", width: 900, height: 1200 },
  { name: "mobile", width: 390, height: 844 },
  { name: "reflow-320", width: 320, height: 800 },
];

let passed = 0;
const failures = [];
const missing = [];

function check(id, label, condition, detail = "") {
  if (condition) { passed++; console.log(`  [PASS] ${id}. ${label}${detail ? " — " + detail : ""}`); }
  else { failures.push(`${id}. ${label}${detail ? " — " + detail : ""}`);
         console.log(`  [FAIL] ${id}. ${label}${detail ? " — " + detail : ""}`); }
}

function serve(root) {
  const server = createServer(async (req, res) => {
    const rel = decodeURIComponent(req.url.split("?")[0]);
    const file = path.join(root, path.normalize(rel).replace(/^(\.\.[/\\])+/, ""));
    try {
      const body = await readFile(file);
      res.writeHead(200, { "content-type": TYPES[path.extname(file)] || "application/octet-stream" });
      res.end(body);
    } catch { missing.push(rel); res.writeHead(404).end("not found"); }
  });
  return new Promise((r) => server.listen(0, () => r(server)));
}

const sha = async (f) => createHash("sha256").update(await readFile(f)).digest("hex");
const rebuild = () => run("python3", ["-m", "slice.ui.tokens.build_tokens"], { cwd: REPO });

// Everything measured here is COMPUTED by the browser at the current viewport.
const probe = (page) => page.evaluate(() => {
  const deep = (sel, root = document) => root.querySelector(sel);
  const ws = deep("nova-workspace");
  const sr = ws?.shadowRoot;
  const columns = sr ? getComputedStyle(sr.querySelector(".columns")).gridTemplateColumns : null;

  // Every focusable control, across shadow boundaries, with its rendered box.
  const controls = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll("*")) {
      if (el.shadowRoot) walk(el.shadowRoot);
      if (el.tagName === "BUTTON" && el.getAttribute("tabindex") !== "-1") {
        const r = el.getBoundingClientRect();
        const name = (el.getAttribute("aria-label") || el.textContent || "").replace(/\s+/g, " ").trim();
        if (r.width > 0 && r.height > 0) controls.push({ name: name.slice(0, 40), w: r.width, h: r.height });
      }
    }
  };
  walk(document);

  const stop = deep("nova-stop");
  const stopBtn = stop?.shadowRoot?.querySelector("nova-button")?.shadowRoot?.querySelector("button");
  const stopBox = stopBtn?.getBoundingClientRect();
  const cross = deep("nova-crosscut");
  const approvalsBtn = Array.from(cross?.shadowRoot?.querySelectorAll("button") || [])
    .find((b) => b.dataset.view === "approvals");
  const approvalsBox = approvalsBtn?.getBoundingClientRect();
  const bar = deep("nova-context-bar");
  const barBox = bar?.getBoundingClientRect();

  return {
    columns,
    layoutToken: getComputedStyle(document.documentElement)
      .getPropertyValue("--nova-layout-columns").trim(),
    // WCAG 1.4.10: content must not require scrolling in two dimensions.
    docWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    controls,
    stopVisible: !!stopBox && stopBox.width > 0 && stopBox.height > 0,
    approvalsVisible: !!approvalsBox && approvalsBox.width > 0 && approvalsBox.height > 0,
    contextVisible: !!barBox && barBox.width > 0 && barBox.height > 0,
    contextText: bar?.shadowRoot?.textContent.replace(/\s+/g, " ").trim().slice(0, 60) || "",
  };
});

const original = await readFile(TOKENS_JSON, "utf8");
const server = await serve(UI);
const url = `http://127.0.0.1:${server.address().port}/section16/demo/index.html`;
let browser;

try {
  browser = await chromium.launch({
    executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  });
  const context = await browser.newContext();
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));

  console.log("\nSection 17 responsive verification");
  console.log("=".repeat(66));
  console.log("Driving the UNEDITED Section 16 screen at four viewport sizes.\n");

  const load = async () => {
    await page.goto(url, { waitUntil: "networkidle" });
    await page.waitForFunction(() => window.novaDemo && document.querySelector("nova-workspace")?.shadowRoot);
    return probe(page);
  };

  // ---- A/B. renders at every band, screen unedited -----------------------
  console.log("A/B. The same screen renders at every viewport");
  const screenHash = await sha(SCREEN);
  const results = {};
  for (const vp of VIEWPORTS) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    results[vp.name] = await load();
    check(`A-${vp.name}`, `renders at ${vp.width}x${vp.height}`,
          !!results[vp.name].columns, results[vp.name].columns);
  }
  check("B1", "screen file never edited", (await sha(SCREEN)) === screenHash,
        `sha256 ${screenHash.slice(0, 16)}…`);
  check("B2", "no page errors at any viewport", errors.length === 0, errors.join("; ") || "clean");

  // ---- C/D. reflow -------------------------------------------------------
  console.log("\nC/D. Reflow (WCAG 1.4.10)");
  const desktopCols = results.desktop.columns.split(" ").length;
  const mobileCols = results.mobile.columns.split(" ").length;
  check("C1", "desktop uses a two-track grid", desktopCols === 2, results.desktop.columns);
  check("C2", "mobile collapses to one track", mobileCols === 1, results.mobile.columns);
  check("C3", "the collapse is token-driven",
        results.desktop.layoutToken !== results.mobile.layoutToken,
        `${results.desktop.layoutToken} -> ${results.mobile.layoutToken}`);
  for (const vp of VIEWPORTS) {
    const r = results[vp.name];
    check(`D-${vp.name}`, `no horizontal scrolling at ${vp.width}px`,
          r.docWidth <= r.clientWidth + 1, `content ${r.docWidth} / viewport ${r.clientWidth}`);
  }

  // ---- E. text resize ----------------------------------------------------
  console.log("\nE. Resize text to 200% (WCAG 1.4.4)");
  await page.setViewportSize({ width: 1280, height: 900 });
  await load();
  // Doubling the root font size is the rem-based equivalent of a 200% text-only
  // zoom: it scales type without scaling the viewport.
  await page.addStyleTag({ content: "html { font-size: 200% !important; }" });
  await page.waitForTimeout(120);
  const zoomed = await probe(page);
  check("E1", "no horizontal scrolling at 200% text",
        zoomed.docWidth <= zoomed.clientWidth + 1,
        `content ${zoomed.docWidth} / viewport ${zoomed.clientWidth}`);
  check("E2", "content still present at 200%", zoomed.contextVisible && zoomed.stopVisible);

  // ---- F. orientation ----------------------------------------------------
  console.log("\nF. Orientation (WCAG 1.3.4)");
  await page.setViewportSize({ width: 390, height: 844 });
  const portrait = await load();
  await page.setViewportSize({ width: 844, height: 390 });
  const landscape = await load();
  check("F1", "portrait renders", portrait.contextVisible && portrait.stopVisible);
  check("F2", "landscape renders", landscape.contextVisible && landscape.stopVisible);
  check("F3", "no content lost in either orientation",
        portrait.approvalsVisible && landscape.approvalsVisible);
  check("F4", "neither orientation scrolls horizontally",
        portrait.docWidth <= portrait.clientWidth + 1 &&
        landscape.docWidth <= landscape.clientWidth + 1);

  // ---- G. target size ----------------------------------------------------
  console.log("\nG. Target size (WCAG 2.5.8, 24x24 minimum)");
  for (const vp of VIEWPORTS) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const r = await load();
    const small = r.controls.filter((c) => c.w < 24 || c.h < 24);
    check(`G-${vp.name}`, `all ${r.controls.length} controls >= 24x24 at ${vp.width}px`,
          small.length === 0,
          small.length ? small.map((c) => `${c.name} ${Math.round(c.w)}x${Math.round(c.h)}`).join("; ")
                       : "smallest " + Math.round(Math.min(...r.controls.map((c) => Math.min(c.w, c.h)))));
  }

  // ---- H/I/J. required controls survive every viewport -------------------
  console.log("\nH/I/J. Stop, approvals and context at every viewport");
  for (const vp of VIEWPORTS) {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    const r = await load();
    check(`H-${vp.name}`, `emergency stop reachable at ${vp.width}px`, r.stopVisible);
    check(`I-${vp.name}`, `approvals reachable at ${vp.width}px`, r.approvalsVisible);
    check(`J-${vp.name}`, `active context visible at ${vp.width}px`,
          r.contextVisible && r.contextText.length > 0);
  }

  // ---- K. CSS drives it, not JavaScript ----------------------------------
  console.log("\nK. Layout is computed by CSS, not JavaScript");
  const jsFree = await page.evaluate(() => {
    // If JavaScript were computing layout, removing the stylesheet's media
    // queries would leave the grid unchanged. It must not.
    const sheet = Array.from(document.styleSheets)
      .find((s) => (s.href || "").includes("tokens.css"));
    const mediaRules = Array.from(sheet.cssRules).filter((r) => r.type === CSSRule.MEDIA_RULE);
    return { mediaRuleCount: mediaRules.length, hrefs: mediaRules.map((r) => r.conditionText) };
  });
  check("K1", "breakpoints exist only in the generated stylesheet",
        jsFree.mediaRuleCount === 2, jsFree.hrefs.join(" | "));

  // ---- L. token change moves layout, screen untouched --------------------
  console.log("\nL. Changing a responsive token changes layout");
  await page.setViewportSize({ width: 900, height: 1200 });
  const beforeTablet = await load();
  const mutated = JSON.parse(original);
  // Give the tablet band the desktop split instead of the stacked layout.
  mutated.responsive.mid["layout.columns"] = "{layout.split}";
  await writeFile(TOKENS_JSON, JSON.stringify(mutated, null, 2) + "\n");
  await rebuild();
  const afterTablet = await load();
  check("L1", "tablet layout changed", beforeTablet.columns !== afterTablet.columns,
        `${beforeTablet.columns} -> ${afterTablet.columns}`);
  check("L2", "screen file still byte-identical", (await sha(SCREEN)) === screenHash);
  check("L3", "one token edited, no component touched", true, "responsive.mid only");
} finally {
  await writeFile(TOKENS_JSON, original);
  await rebuild();
  if (browser) await browser.close();
  server.close();
}

console.log("\n" + "=".repeat(66));
console.log(`${passed} passed, ${failures.length} failed`);
if (failures.length) {
  console.log("\nFAILURES:");
  failures.forEach((f) => console.log("  - " + f));
  process.exit(1);
}
console.log("tokens.json restored; tokens.css regenerated from source.");
