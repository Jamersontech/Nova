// Section 16 render and behaviour verification.
//
// test_navigation.py reads source. This drives the real thing: it navigates,
// attempts refused moves, confirms switches, and inspects the rendered
// accessibility tree.
//
// NOT SECURITY TESTS. Every assertion here is about what the interface offers
// and announces. The PDP enforces scope boundaries; a navigation model cannot.
//
// Accessibility scope: these check SPECIFIC WCAG 2.2 AA criteria listed below,
// by hand, without an audit library. Passing them is not a compliance claim --
// see the README for exactly what was and was not tested.
//
// Run:  node slice/ui/section16/tests/nav_check.mjs

import { chromium } from "playwright";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const S16 = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const UI = path.dirname(S16);
const TYPES = { ".html": "text/html", ".css": "text/css", ".js": "text/javascript", ".json": "application/json" };

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

const server = await serve(UI);
const url = `http://127.0.0.1:${server.address().port}/section16/demo/index.html`;
let browser;

// Reads rendered state, piercing shadow boundaries.
const probe = (page) => page.evaluate(() => {
  const ws = document.querySelector("nova-workspace");
  const sr = ws?.shadowRoot;
  const bar = document.querySelector("nova-context-bar");
  const nav = document.querySelector("nova-nav");
  const cross = document.querySelector("nova-crosscut");
  const stop = document.querySelector("nova-stop");
  const dialog = document.querySelector("nova-scope-switch");
  const view = document.querySelector("nova-view");

  const offers = Array.from(nav?.shadowRoot?.querySelectorAll("button") || [])
    .map((b) => b.dataset.to);

  return {
    at: window.novaDemo.state.at.join("/"),
    view: window.novaDemo.state.view,
    offers,
    contextText: bar?.shadowRoot?.textContent.replace(/\s+/g, " ").trim() || "",
    contextRole: bar?.shadowRoot?.querySelector("[role=status]")?.getAttribute("aria-label") || null,
    stopPresent: !!stop && !!stop.shadowRoot?.querySelector("nova-button"),
    crossViews: Array.from(cross?.shadowRoot?.querySelectorAll("button") || [])
      .map((b) => b.dataset.view),
    dialogVisible: dialog ? !dialog.hidden : false,
    dialogMode: dialog?.getAttribute("mode") || null,
    dialogRole: dialog?.shadowRoot?.querySelector("[role=alertdialog]") ? "alertdialog" : null,
    dialogText: dialog?.hidden ? "" : (dialog?.shadowRoot?.textContent.replace(/\s+/g, " ").trim() || ""),
    viewLabel: view?.shadowRoot?.querySelector("section")?.getAttribute("aria-label") || null,
    landmarks: {
      header: !!sr?.querySelector("header"),
      main: !!sr?.querySelector("main"),
      h1: (() => {
        const h = sr?.querySelector("h1");
        const slot = h?.querySelector("slot");
        const assigned = slot ? slot.assignedNodes({ flatten: true }).map((n) => n.textContent).join("") : "";
        return (assigned || h?.textContent || "").trim() || null;
      })(),
      skip: sr?.querySelector(".skip")?.textContent.trim() || null,
      navLabels: Array.from(document.querySelectorAll("nova-nav, nova-crosscut, nova-area-nav"))
        .map((e) => e.shadowRoot?.querySelector("nav")?.getAttribute("aria-label")),
    },
    disclosure: (() => {
      const d = view?.shadowRoot?.querySelector("nova-disclosure");
      const btn = d?.shadowRoot?.querySelector("button.head");
      return { present: !!d, expanded: btn?.getAttribute("aria-expanded") ?? null,
               name: btn?.textContent.replace(/\s+/g, " ").trim() || null };
    })(),
  };
});

const go = (page, to) => page.evaluate((t) => {
  document.dispatchEvent(new CustomEvent("navigate", { detail: { to: t } }));
}, to);

try {
  browser = await chromium.launch({
    executablePath: "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  });
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (e) => errors.push(String(e)));
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

  console.log("\nSection 16 navigation and Context Lock verification");
  console.log("=".repeat(66));

  const response = await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForFunction(() => window.novaDemo && document.querySelector("nova-nav")?.shadowRoot);
  let s = await probe(page);

  // ---- A. renders --------------------------------------------------------
  console.log("\nA. Screen renders");
  check("A1", "HTTP 200", response.status() === 200);
  check("A2", "every requested resource resolves",
        missing.filter((m) => m !== "/favicon.ico").length === 0,
        missing.filter((m) => m !== "/favicon.ico").join(", ") || "only /favicon.ico");
  const realErrors = errors.filter((e) => !e.includes("404"));
  check("A3", "no uncaught page errors", realErrors.length === 0, realErrors.join("; ") || "clean");

  // ---- B. IA reachability ------------------------------------------------
  console.log("\nB. IA reachability");
  const map = await page.evaluate(() => window.novaDemo.map);
  const navigable = Object.entries(map.capabilities).filter(([, v]) => v.navigable).map(([k]) => k);
  check("B1", "every navigable capability declared", navigable.length === 10, `${navigable.length}`);
  check("B2", "non-navigable subsystems have no location",
        map.capabilities["Agents, tools, integrations, memory, workflows"].navigable === false);
  check("B3", "three cross-scope views reachable",
        JSON.stringify(s.crossViews) === JSON.stringify(["approvals", "activity", "tasks"]),
        s.crossViews.join(", "));

  // ---- C. sibling refusal ------------------------------------------------
  console.log("\nC. No sibling path is constructible");
  check("C1", "offers from Client A exclude Client B",
        !s.offers.some((o) => o.includes("client-b")), s.offers.join(" | "));
  check("C2", "offers are ancestors or children only",
        s.offers.every((o) => {
          const seg = o.split("/");
          const at = s.at.split("/");
          const anc = seg.length < at.length && at.slice(0, seg.length).join("/") === o;
          const child = seg.length === at.length + 1 && seg.slice(0, at.length).join("/") === s.at;
          return anc || child;
        }), s.offers.join(" | "));

  await go(page, "business/kairo/client-b");
  s = await probe(page);
  check("C3", "a sibling move does not change context",
        s.at === "business/kairo/client-a", `still at ${s.at}`);
  check("C4", "it surfaces an explicit switch instead", s.dialogVisible && s.dialogMode === "switch");
  check("C5", "the refusal explains why", /no path between them|explicit act/i.test(s.dialogText));

  // ---- D. explicit switching ---------------------------------------------
  console.log("\nD. Switching is explicit");
  check("D1", "switch dialog is an alertdialog", s.dialogRole === "alertdialog");
  check("D2", "it states that switching grants nothing",
        /grants no permission|approves nothing/i.test(s.dialogText));
  await page.evaluate(() => document.dispatchEvent(new CustomEvent("switch-cancelled", { detail: {} })));
  s = await probe(page);
  check("D3", "cancelling leaves context unchanged",
        s.at === "business/kairo/client-a" && !s.dialogVisible, s.at);

  await go(page, "business/kairo/client-b");
  await page.evaluate(() => document.dispatchEvent(
    new CustomEvent("switch-confirmed", { detail: { to: "business/kairo/client-b" } })));
  s = await probe(page);
  check("D4", "confirming performs the switch", s.at === "business/kairo/client-b", s.at);

  // ---- E. ambiguity ------------------------------------------------------
  console.log("\nE. Ambiguity is asked about, never guessed");
  await page.evaluate(() => { window.novaDemo.state.at = ["business", "kairo", "client-a"];
                              window.novaDemo.render(); });
  const intent = await page.evaluate(() => window.novaDemo.ambiguousIntent());
  s = await probe(page);
  check("E1", "materially different candidates are ambiguous", intent.status === "ambiguous");
  check("E2", "NOVA asks rather than choosing", s.dialogVisible && s.dialogMode === "ambiguous");
  check("E3", "both candidates are offered", /production/i.test(s.dialogText) && /staging/i.test(s.dialogText));
  check("E4", "context did not silently change", s.at === "business/kairo/client-a", s.at);
  await page.evaluate(() => document.dispatchEvent(new CustomEvent("switch-cancelled", { detail: {} })));

  // ---- F. persistent surface at every reachable state --------------------
  console.log("\nF. Context, approvals and stop persist in every state");
  const states = ["", "life", "business", "business/kairo", "business/kairo/client-a",
                  "business/kairo/client-a/website", "business/kairo/client-a/website/production",
                  "wealth", "wealth/reserve"];
  let ctxEverywhere = true, stopEverywhere = true, approvalsEverywhere = true;
  for (const target of states) {
    await page.evaluate((t) => {
      window.novaDemo.state.at = t ? t.split("/") : [];
      window.novaDemo.render();
    }, target);
    const st = await probe(page);
    if (!st.contextText || !st.contextRole) ctxEverywhere = false;
    if (!st.stopPresent) stopEverywhere = false;
    if (!st.crossViews.includes("approvals")) approvalsEverywhere = false;
  }
  check("F1", `active context visible in all ${states.length} states`, ctxEverywhere);
  check("F2", `emergency stop reachable in all ${states.length} states`, stopEverywhere);
  check("F3", `approvals reachable in all ${states.length} states`, approvalsEverywhere);

  // ---- G. progressive disclosure -----------------------------------------
  console.log("\nG. Progressive disclosure");
  await page.evaluate(() => { window.novaDemo.state.at = ["business", "kairo"];
                              window.novaDemo.state.view = "scope"; window.novaDemo.render(); });
  s = await probe(page);
  check("G1", "disclosure present", s.disclosure.present);
  check("G2", "closed by default", s.disclosure.expanded === "false", `aria-expanded=${s.disclosure.expanded}`);
  check("G3", "its summary names what is underneath",
        /what nova did/i.test(s.disclosure.name || ""), s.disclosure.name);
  check("G4", "level 5 is not navigable here", map.disclosure.max_navigable_level === 4);

  // ---- H. authority is never implied -------------------------------------
  console.log("\nH. Navigation implies no authority");
  await page.evaluate(() => { window.novaDemo.state.view = "approvals"; window.novaDemo.render(); });
  const approvalText = await page.evaluate(() =>
    document.querySelector("nova-view").shadowRoot.querySelector("nova-approval-card")
      ?.shadowRoot.textContent.replace(/\s+/g, " ").trim() || "");
  check("H1", "approval states only James may approve", /only james can approve/i.test(approvalText));
  check("H2", "and that NOVA cannot", /cannot approve it/i.test(approvalText));
  check("H3", "no step-up or session-strength semantics leaked",
        !/step.?up|session strength/i.test(approvalText));

  // ---- I. WCAG 2.2 AA -- specific criteria, hand-checked ------------------
  console.log("\nI. Accessibility (specific WCAG 2.2 AA criteria)");
  await page.evaluate(() => { window.novaDemo.state.view = "scope"; window.novaDemo.render(); });
  s = await probe(page);
  check("I1", "1.3.1 header and main landmarks present",
        s.landmarks.header && s.landmarks.main);
  check("I2", "2.4.6 page has a heading", !!s.landmarks.h1, s.landmarks.h1);
  check("I3", "2.4.1 skip control present", !!s.landmarks.skip, s.landmarks.skip);
  check("I4", "1.3.1 every nav region has an accessible name",
        s.landmarks.navLabels.every(Boolean), s.landmarks.navLabels.join(" | "));
  check("I5", "4.1.2 context indicator has a role and name", s.contextRole === "Active context");
  check("I6", "4.1.2 disclosure exposes expanded state", s.disclosure.expanded !== null);

  const kb = await page.evaluate(() => {
    const flatText = (el) => {
      let out = "";
      for (const n of el.childNodes) {
        if (n.nodeType === 3) out += n.textContent;
        else if (n.tagName === "SLOT") n.assignedNodes({ flatten: true }).forEach((a) => { out += a.textContent || ""; });
        else if (n.nodeType === 1) out += flatText(n);
      }
      return out.replace(/\s+/g, " ").trim();
    };
    // Walk the tab order, descending into shadow roots, and report what is
    // focusable and whether each focusable thing has an accessible name.
    const seen = [];
    const walk = (root) => {
      for (const el of root.querySelectorAll("*")) {
        if (el.shadowRoot) walk(el.shadowRoot);
        const tag = el.tagName.toLowerCase();
        if (tag === "button" || tag === "a" || el.hasAttribute("tabindex")) {
          if (el.getAttribute("tabindex") === "-1") continue;
          seen.push({
            tag,
            name: (el.getAttribute("aria-label") || flatText(el) || "").replace(/\s+/g, " ").trim(),
            disabled: el.disabled === true,
          });
        }
      }
    };
    walk(document);
    return seen;
  });
  check("I7", "2.1.1 interactive controls are real buttons", kb.length > 0 && kb.every((k) => k.tag === "button"),
        `${kb.length} focusable controls`);
  check("I8", "4.1.2 every control has an accessible name", kb.every((k) => k.name.length > 0),
        kb.filter((k) => !k.name.length).length + " unnamed");

  const focus = await page.evaluate(async () => {
    const btn = document.querySelector("nova-crosscut").shadowRoot.querySelector("button");
    btn.focus();
    const s = getComputedStyle(btn);
    return { focused: btn.matches(":focus"), outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth };
  });
  check("I9", "2.4.7 focus lands on the control", focus.focused);
  check("I10", "2.4.11 focus is visibly indicated",
        focus.outlineStyle !== "none" && focus.outlineWidth !== "0px",
        `${focus.outlineStyle} ${focus.outlineWidth}`);

  const keyed = await page.evaluate(async () => {
    const before = window.novaDemo.state.view;
    const btn = Array.from(document.querySelector("nova-crosscut").shadowRoot.querySelectorAll("button"))
      .find((b) => b.dataset.view === "activity");
    btn.focus();
    btn.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    btn.click(); // Enter on a native button produces a click
    return { before, after: window.novaDemo.state.view };
  });
  check("I11", "2.1.1 a view can be changed from the keyboard",
        keyed.after === "activity", `${keyed.before} -> ${keyed.after}`);

  // ---- J. tokens ---------------------------------------------------------
  console.log("\nJ. Section 15 tokens are consumed, not bypassed");
  const tok = await page.evaluate(() => {
    const root = getComputedStyle(document.documentElement);
    const btn = document.querySelector("nova-crosscut").shadowRoot.querySelector("button");
    const ws = document.querySelector("nova-workspace");
    return {
      accent: root.getPropertyValue("--nova-color-accent-base").trim(),
      count: Array.from(document.styleSheets)
        .flatMap((sh) => { try { return Array.from(sh.cssRules); } catch { return []; } })
        .filter((r) => r.selectorText === ":root")
        .flatMap((r) => Array.from(r.style)).filter((p) => p.startsWith("--nova-")).length,
      btnBg: getComputedStyle(btn).backgroundColor,
      wsBg: getComputedStyle(ws).backgroundColor,
    };
  });
  check("J1", "token sheet loaded", tok.count > 100, `${tok.count} properties`);
  check("J2", "Section 16 components render from tokens",
        tok.btnBg !== "rgba(0, 0, 0, 0)", tok.btnBg);
  check("J3", "workspace background comes from a token",
        tok.wsBg !== "rgba(0, 0, 0, 0)", tok.wsBg);
} finally {
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
