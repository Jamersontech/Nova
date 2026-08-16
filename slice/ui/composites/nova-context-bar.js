// nova-context-bar -- the always-visible active context.
//
// USER_INTERFACE_ARCHITECTURE.md section 5 makes this the one piece of internal
// machinery that MUST be exposed, and Constitution section 7 makes context
// ambiguity a safety problem rather than a usability one. So this composite is
// not decorative: it is the interface's answer to "which scope is NOVA in?".
//
// Composes nova-box, nova-text and nova-badge. Declares no visual value.

import "../primitives/nova-box.js";
import "../primitives/nova-text.js";
import "../primitives/nova-badge.js";
import { NovaElement, defineElement } from "../primitives/base.js";

class NovaContextBar extends NovaElement {
  static observedAttributes = ["area", "path"];

  render() {
    const area = this.getAttribute("area") || "business";
    // The scope path, rendered as discrete segments. Siblings have no path to
    // each other (I-03) -- this shows descent from the active root only.
    const segments = (this.getAttribute("path") || "").split(">").map((s) => s.trim()).filter(Boolean);

    const crumbs = segments
      .map(
        (seg, i) => `
        <nova-text size="body" tone="${i === segments.length - 1 ? "primary" : "secondary"}" inline>
          ${seg}
        </nova-text>
        ${i < segments.length - 1 ? '<nova-text size="body" tone="muted" inline>/</nova-text>' : ""}`
      )
      .join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .row { display: flex; align-items: center; gap: var(--nova-space-snug); flex-wrap: wrap; }
      </style>
      <!-- The context indicator is a safety surface (Constitution section 7), so
           it carries an accessible name and announces changes: a user who cannot
           see the bar must still know which scope NOVA is operating in. -->
      <nova-box surface="raised" pad="snug" radius="panel" border="subtle" direction="row"
                gap="snug" align="center" justify="space-between"
                role="status" aria-live="polite" aria-label="Active context">
        <div class="row">
          <nova-badge area="${area}">${area}</nova-badge>
          <div class="row">${crumbs}</div>
        </div>
        <nova-text size="caption" tone="muted" tracking="label">active context</nova-text>
      </nova-box>
    `;
  }
}

defineElement("nova-context-bar", NovaContextBar);
