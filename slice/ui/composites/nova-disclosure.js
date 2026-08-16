// nova-disclosure -- progressive disclosure.
//
// DESIGN_PRINCIPLES.md section 4: "Advanced capability is reached, not
// displayed." USER_INTERFACE_ARCHITECTURE.md section 4 puts inspection at
// levels 4-5, available but never imposed.
//
// Closed by default, and the summary states what is underneath rather than
// saying "more" -- depth that does not announce what it holds is not
// discoverable, it is just hidden.

import "../primitives/nova-box.js";
import "../primitives/nova-text.js";
import { NovaElement, defineElement } from "../primitives/base.js";

class NovaDisclosure extends NovaElement {
  static observedAttributes = ["summary", "level", "open"];

  render() {
    const open = this.hasAttribute("open");
    const summary = this.getAttribute("summary") || "";
    const level = this.getAttribute("level") || "";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .head {
          display: flex; align-items: center; gap: var(--nova-space-snug);
          width: 100%; text-align: left; cursor: pointer;
          background: none; border: none; padding: 0;
        }
        .head:focus-visible {
          outline: var(--nova-border-emphasis) solid var(--nova-color-border-accent);
          outline-offset: var(--nova-space-tight);
        }
        .body { display: ${open ? "block" : "none"}; }
        .marker { transition: transform var(--nova-motion-duration) var(--nova-motion-ease); }
      </style>
      <nova-box surface="raised" pad="snug" radius="panel" border="subtle"
                direction="column" gap="tight">
        <!-- A real button with aria-expanded: the open/closed state must be
             announced, not inferred from a "+" glyph (WCAG 2.2 AA). -->
        <button type="button" class="head" part="head"
                aria-expanded="${open}" aria-controls="body">
          <nova-text class="marker" size="body" tone="muted" inline>${open ? "−" : "+"}</nova-text>
          <nova-text size="body" tone="secondary">${summary}</nova-text>
          ${level ? `<nova-text size="caption" tone="muted" tracking="label">${level}</nova-text>` : ""}
        </button>
        <div class="body" id="body" part="body"><slot></slot></div>
      </nova-box>
    `;

    this.shadowRoot.querySelector(".head").addEventListener("click", () => {
      this.toggleAttribute("open");
    });
  }
}

defineElement("nova-disclosure", NovaDisclosure);
