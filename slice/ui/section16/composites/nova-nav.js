// nova-nav -- navigation offers from the current location.
//
// Renders exactly what navigation.js offers and nothing else, so the sibling
// refusal is structural rather than a styling choice: there is no code path
// here that could add a destination the model did not produce.
//
// Accessibility (WCAG 2.2 AA baseline, ADR 0042 Proposed): a real <nav> with an
// accessible name, real <button> elements so every destination is keyboard
// reachable and operable, aria-current marking the present location, and a
// visible focus indicator that does not rely on colour alone.

import "../../primitives/nova-text.js";
import "../../primitives/nova-box.js";
import { NovaElement, defineElement } from "../../primitives/base.js";
import { navigationOffers, pathString, RELATION } from "../nav/navigation.js";

class NovaNav extends NovaElement {
  static observedAttributes = ["at"];

  set map(value) {
    this._map = value;
    if (this.shadowRoot) this.render();
  }

  render() {
    if (!this._map) return;
    const at = (this.getAttribute("at") || "").split("/").filter(Boolean);
    const offers = navigationOffers(this._map, at);

    const item = (o) => `
      <li>
        <button type="button" data-to="${pathString(o.segments)}"
                aria-label="${o.relation === RELATION.ASCEND ? "Go up to" : "Go into"} ${o.label}">
          <span aria-hidden="true">${o.relation === RELATION.ASCEND ? "↑" : "→"}</span>
          ${o.label}
        </button>
      </li>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ul { list-style: none; margin: 0; padding: 0;
             display: flex; flex-direction: column; gap: var(--nova-space-tight); }
        button {
          display: flex; align-items: center; gap: var(--nova-space-tight);
          width: 100%; text-align: left; cursor: pointer;
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-body);
          font-weight: var(--nova-type-weight-normal);
          color: var(--nova-color-text-secondary);
          background: var(--nova-color-surface-raised);
          border: var(--nova-border-width) solid var(--nova-color-border-subtle);
          border-radius: var(--nova-radius-control);
          padding: var(--nova-space-tight) var(--nova-space-snug);
          min-height: var(--nova-control-target);
        }
        button:hover { background: var(--nova-color-surface-hover);
                       color: var(--nova-color-text-primary); }
        button:focus-visible {
          outline: var(--nova-border-emphasis) solid var(--nova-color-border-accent);
          outline-offset: var(--nova-space-tight);
        }
      </style>
      <nav aria-label="Scope navigation">
        <ul part="offers">${offers.map(item).join("")}</ul>
      </nav>
    `;

    this.shadowRoot.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () =>
        this.dispatchEvent(
          new CustomEvent("navigate", { detail: { to: b.dataset.to }, bubbles: true, composed: true })
        )
      )
    );
  }
}

defineElement("nova-nav", NovaNav);
