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

    const items = AREAS.map(
      (area) => `
      <nova-box class="area" data-area="${area}"
                surface="${area === active ? "inset" : "raised"}"
                border="${area === active ? "accent" : "subtle"}"
                pad="snug" radius="panel" direction="row" gap="snug" align="center">
        <nova-badge area="${area}">${area}</nova-badge>
        <nova-text size="body" tone="${area === active ? "primary" : "secondary"}">
          ${area === active ? "active" : "switch"}
        </nova-text>
      </nova-box>`
    ).join("");

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .areas { display: flex; flex-direction: column; gap: var(--nova-space-tight); }
        .area { cursor: pointer; }
      </style>
      <div class="areas" part="areas">${items}</div>
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
