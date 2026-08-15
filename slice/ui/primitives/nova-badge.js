// nova-badge -- the status/classification primitive.
//
// Carries the risk-class and area tones. The tone vocabulary maps to
// PERMISSION_ARCHITECTURE.md section 5's approval policies (autonomous /
// contextual approval / explicit approval) rather than inventing a scale --
// a badge that invented its own severity words would drift from the class the
// PDP actually assigned.

import { NovaElement, defineElement, pick } from "./base.js";

const TONES = ["autonomous", "contextual", "explicit", "neutral"];
const AREAS = ["life", "business", "wealth"];

class NovaBadge extends NovaElement {
  static observedAttributes = ["tone", "area"];

  render() {
    const area = this.getAttribute("area");
    const isArea = AREAS.includes(area);
    const tone = pick(this, "tone", TONES, "neutral");

    let fg;
    let bg;
    if (isArea) {
      fg = `var(--nova-color-area-${area})`;
      bg = "var(--nova-color-surface-inset)";
    } else if (tone === "neutral") {
      fg = "var(--nova-color-text-secondary)";
      bg = "var(--nova-color-surface-inset)";
    } else {
      fg = `var(--nova-color-risk-${tone})`;
      bg = `var(--nova-color-risk-${tone}-soft)`;
    }

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: inline-flex; }
        span {
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-caption);
          font-weight: var(--nova-type-weight-strong);
          letter-spacing: var(--nova-type-tracking-label);
          text-transform: uppercase;
          color: ${fg};
          background: ${bg};
          border: var(--nova-border-width) solid ${fg};
          border-radius: var(--nova-radius-pill);
          padding: var(--nova-space-tight) var(--nova-space-snug);
          white-space: nowrap;
        }
      </style>
      <span part="badge"><slot></slot></span>
    `;
  }
}

defineElement("nova-badge", NovaBadge);
