// nova-crosscut -- the three views that cut across the scope tree.
//
// USER_INTERFACE_ARCHITECTURE.md section 3: approvals, activity and tasks exist
// as cross-cutting views "because they answer questions James actually asks":
// what needs my decision, what did NOVA do, what needs doing.
//
// They are reachable from every state -- that is what "never buried" means for
// approvals (section 6), and the reachability test asserts it at every location
// the navigation model can produce.
//
// Accessibility: a named navigation landmark, real buttons, aria-current for
// the active view, and a text count rather than colour alone for pending work.

import "../../primitives/nova-text.js";
import "../../primitives/nova-badge.js";
import { NovaElement, defineElement } from "../../primitives/base.js";

const VIEWS = [
  { id: "approvals", label: "Approvals", question: "what needs my decision" },
  { id: "activity", label: "Activity", question: "what did NOVA do" },
  { id: "tasks", label: "Tasks", question: "what needs doing" },
];

class NovaCrosscut extends NovaElement {
  static observedAttributes = ["active", "pending"];

  render() {
    const active = this.getAttribute("active") || "";
    const pending = this.getAttribute("pending") || "0";

    const item = (v) => `
      <li>
        <button type="button" data-view="${v.id}"
                ${active === v.id ? 'aria-current="page"' : ""}
                aria-label="${v.label} — ${v.question}${
                  v.id === "approvals" ? `, ${pending} pending` : ""
                }">
          <span>${v.label}</span>
          ${v.id === "approvals" ? `<nova-badge tone="contextual">${pending} pending</nova-badge>` : ""}
        </button>
      </li>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ul { list-style: none; margin: 0; padding: 0;
             display: flex; gap: var(--nova-space-tight); flex-wrap: wrap; }
        button {
          display: flex; align-items: center; gap: var(--nova-space-tight);
          cursor: pointer;
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-body);
          color: var(--nova-color-text-secondary);
          background: var(--nova-color-surface-raised);
          border: var(--nova-border-width) solid var(--nova-color-border-subtle);
          border-radius: var(--nova-radius-control);
          padding: var(--nova-space-tight) var(--nova-space-snug);
          min-height: var(--nova-control-target);
        }
        button[aria-current="page"] {
          color: var(--nova-color-text-primary);
          border-color: var(--nova-color-border-accent);
          background: var(--nova-color-surface-inset);
        }
        button:focus-visible {
          outline: var(--nova-border-emphasis) solid var(--nova-color-border-accent);
          outline-offset: var(--nova-space-tight);
        }
      </style>
      <nav aria-label="Cross-scope views">
        <ul part="views">${VIEWS.map(item).join("")}</ul>
      </nav>
    `;

    this.shadowRoot.querySelectorAll("button").forEach((b) =>
      b.addEventListener("click", () =>
        this.dispatchEvent(
          new CustomEvent("view-change", { detail: { view: b.dataset.view }, bubbles: true, composed: true })
        )
      )
    );
  }
}

defineElement("nova-crosscut", NovaCrosscut);
