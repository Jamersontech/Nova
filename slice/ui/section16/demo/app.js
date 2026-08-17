// Section 16 demonstration wiring.
//
// This is deliberately ~90 lines of explicit code and NOT a state-management
// layer: one plain object, one render function, and event listeners. There is
// no store, no reducer, no subscription, no reactivity and no router. The cap
// James set for Section 16 is that Web Components must not become NOVA's
// application framework by accretion, and the moment this file grows a generic
// abstraction, that is what has happened.
//
// All navigation decisions come from navigation.js. This file never decides
// whether a move is allowed -- it asks, and renders the answer.

import "../../composites/nova-context-bar.js";
import "../../composites/nova-area-nav.js";
import "../../composites/nova-stop.js";
import "../composites/nova-workspace.js";
import "../composites/nova-nav.js";
import "../composites/nova-crosscut.js";
import "../composites/nova-scope-switch.js";
import "../composites/nova-view.js";

import {
  requestNavigation, explicitSwitch, resolveIntent, parsePath, pathString,
  labelFor, OUTCOME, INTENT,
} from "../nav/navigation.js";

const map = await fetch("../ia/ia_map.json").then((r) => r.json());

// The entire application state. Three fields.
const state = { at: ["business", "kairo", "client-a"], view: "scope", pending: null };

const $ = (sel) => document.querySelector(sel);

function areaOf(at) {
  return map.areas.includes(at[0]) ? at[0] : "business";
}

function contextPath(at) {
  return ["NOVA", ...at.map((_, i) => labelFor(map, at.slice(0, i + 1)))].join(" > ");
}

function render() {
  const { at, view, pending } = state;

  $("nova-context-bar").setAttribute("area", areaOf(at));
  $("nova-context-bar").setAttribute("path", contextPath(at));

  const nav = $("nova-nav");
  nav.map = map;
  nav.setAttribute("at", pathString(at));

  $("nova-area-nav").setAttribute("active", areaOf(at));
  $("nova-crosscut").setAttribute("active", view === "scope" ? "" : view);

  const v = $("nova-view");
  v.setAttribute("view", view);
  v.setAttribute("at", pathString(at));
  v.setAttribute("label", at.length ? labelFor(map, at) : "NOVA");

  const dialog = $("nova-scope-switch");
  if (pending) {
    dialog.hidden = false;
    dialog.setAttribute("mode", pending.mode);
    dialog.setAttribute("reason", pending.reason);
    if (pending.mode === "ambiguous") {
      dialog.setAttribute("candidates", pending.candidates.join("|"));
    } else {
      dialog.setAttribute("from", contextPath(at));
      dialog.setAttribute("to", contextPath(parsePath(pending.to)));
    }
  } else {
    dialog.hidden = true;
  }
}

// Ordinary navigation: ancestors and children only. Anything else comes back as
// needing an explicit switch, and is shown as one rather than performed.
document.addEventListener("navigate", (e) => {
  const to = parsePath(e.detail.to);
  const result = requestNavigation(map, state.at, to);

  if (result.outcome === OUTCOME.ALLOWED) {
    state.at = to;
    state.pending = null;
  } else if (result.outcome === OUTCOME.NEEDS_EXPLICIT_SWITCH) {
    state.pending = { mode: "switch", to: pathString(to), reason: result.reason };
  }
  render();
});

// Area switching is the explicit act. It still confirms before changing context.
document.addEventListener("area-change", (e) => {
  const to = [e.detail.area];
  const request = explicitSwitch(map, state.at, to);
  if (request.outcome !== OUTCOME.ALLOWED) return;
  state.pending = {
    mode: "switch",
    to: pathString(to),
    reason: "Switching to a different area. This changes what you are looking at.",
  };
  render();
});

document.addEventListener("switch-confirmed", (e) => {
  state.at = parsePath(e.detail.to);
  state.pending = null;
  render();
});

document.addEventListener("switch-cancelled", () => {
  state.pending = null;
  render();
});

document.addEventListener("view-change", (e) => {
  state.view = e.detail.view;
  render();
});

document.addEventListener("scope-chosen", (e) => {
  state.at = parsePath(e.detail.scope);
  state.pending = null;
  render();
});

// A worked ambiguity, exposed for the demonstration and the tests: an
// instruction that matches Production and Staging must be asked about, never
// guessed (CONTEXT_ARCHITECTURE.md section 142).
window.novaDemo = {
  state,
  map,
  render,
  ambiguousIntent() {
    const candidates = [
      "business/kairo/client-a/website/production",
      "business/kairo/client-a/website/staging",
    ];
    const result = resolveIntent(map, candidates);
    if (result.status === INTENT.AMBIGUOUS) {
      state.pending = { mode: "ambiguous", candidates, reason: result.reason };
      render();
    }
    return result;
  },
};

render();
