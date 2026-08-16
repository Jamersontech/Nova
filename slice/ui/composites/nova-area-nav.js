// nova-area-nav -- the three top-level areas.
//
// USER_INTERFACE_ARCHITECTURE.md section 2: three areas, and adding businesses,
// clients, projects, agents, tools or integrations "never adds a fourth".
// The area list is therefore fixed here rather than passed in -- a composite
// that accepted an arbitrary list would make the fourth area a one-line change.
//
// Composes nova-box, nova-text and nova-badge. Declares no visual value.

import "../primitives/nova-box.js";
import "../primitives/nova-text.js";
import "../primitives/nova-badge.js";
import { NovaElement, defineElement } from "../primitives/base.js";

const AREAS = ["life", "business", "wealth"];

class NovaAreaNav extends NovaElement {
  static observedAttributes = ["active"];

  render() {
    const active = AREAS.includes(this.getAttribute("active"))
      ? this.getAttribute("active")
      : "business";

    // Real buttons, not clickable boxes: an area switch must be reachable and
    // operable from the keyboard (WCAG 2.2 AA, ADR 0042 Proposed), and the
    // active area must be conveyed to assistive technology rather than by
    // border colour alone.
    const items = AREAS.map(
      (area) => `
      <li>
        <button type="button" class="area" data-area="${area}"
                ${area === active ? 'aria-current="true"' : ""}
                aria-label="${area === active ? `${area}, active area` : `Switch to ${area}`}">
          <nova-badge area="${area}">${area}</nova-badge>
          <nova-text size="body" tone="${area === active ? "primary" : "secondary"}">
            ${area === active ? "active" : "switch"}
          </nova-text>
        </button>
      </li>`
    ).join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ul.areas { list-style: none; margin: 0; padding: 0;
                   display: flex; flex-direction: column; gap: var(--nova-space-tight); }
        .area {
          display: flex; align-items: center; gap: var(--nova-space-snug);
          width: 100%; text-align: left; cursor: pointer;
          background: var(--nova-color-surface-raised);
          border: var(--nova-border-width) solid var(--nova-color-border-subtle);
          border-radius: var(--nova-radius-panel);
          padding: var(--nova-space-snug);
          min-height: var(--nova-control-target);
        }
        .area[aria-current="true"] {
          background: var(--nova-color-surface-inset);
          border-color: var(--nova-color-border-accent);
        }
        .area:focus-visible {
          outline: var(--nova-border-emphasis) solid var(--nova-color-border-accent);
          outline-offset: var(--nova-space-tight);
        }
      </style>
      <nav aria-label="Top-level areas">
        <ul class="areas" part="areas">${items}</ul>
      </nav>
    `;

    // Switching is explicit and obvious (USER_INTERFACE_ARCHITECTURE.md section 5).
    // It changes what is displayed. It grants nothing -- resolving which scope is
    // meant is not authorization in it.
    this.shadowRoot.querySelectorAll(".area").forEach((el) => {
      el.addEventListener("click", () => {
        this.setAttribute("active", el.dataset.area);
        this.dispatchEvent(
          new CustomEvent("area-change", { detail: { area: el.dataset.area }, bubbles: true })
        );
      });
    });
  }
}

defineElement("nova-area-nav", NovaAreaNav);
