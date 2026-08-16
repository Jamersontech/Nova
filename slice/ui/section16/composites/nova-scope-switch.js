// nova-scope-switch -- explicit context switching, and surfaced ambiguity.
//
// Two states, one component, because they are the same moment from NOVA's side:
// it does not know which scope is meant, so it asks.
//
//   "switch"    -- a sibling was requested. There is no path (I-03), so the move
//                  is presented as a deliberate act with a confirm step.
//   "ambiguous" -- an instruction matched more than one scope and the
//                  alternatives differ materially. CONTEXT_ARCHITECTURE.md
//                  section 142: ask, never silently switch.
//
// Confirming a switch changes WHAT IS DISPLAYED and grants nothing. Resolving
// which scope is meant is disambiguation, not authorization -- stated in the
// component because this is exactly the place a user could infer otherwise.
//
// Accessibility: role="alertdialog" with an accessible name and description,
// real buttons, focus moved to the dialog when it appears.

import "../../primitives/nova-text.js";
import "../../primitives/nova-box.js";
import "../../primitives/nova-button.js";
import "../../primitives/nova-badge.js";
import { NovaElement, defineElement, pick } from "../../primitives/base.js";

class NovaScopeSwitch extends NovaElement {
  static observedAttributes = ["mode", "from", "to", "candidates", "reason"];

  render() {
    const mode = pick(this, "mode", ["switch", "ambiguous"], "switch");
    const from = this.getAttribute("from") || "";
    const to = this.getAttribute("to") || "";
    const reason = this.getAttribute("reason") || "";
    const candidates = (this.getAttribute("candidates") || "").split("|").filter(Boolean);

    const body =
      mode === "ambiguous"
        ? `
        <nova-text size="body" tone="secondary">${reason}</nova-text>
        <ul part="candidates">
          ${candidates
            .map(
              (c) => `<li><button type="button" data-choose="${c}"
                        aria-label="Use scope ${c}">${c}</button></li>`
            )
            .join("")}
        </ul>`
        : `
        <nova-text size="body" tone="secondary">${reason}</nova-text>
        <nova-box bare direction="column" gap="tight">
          <nova-text size="caption" tone="muted" tracking="label">leaving</nova-text>
          <nova-text size="body" tone="secondary">${from || "(no active scope)"}</nova-text>
          <nova-text size="caption" tone="muted" tracking="label">entering</nova-text>
          <nova-text size="body">${to}</nova-text>
        </nova-box>
        <div part="actions">
          <nova-button variant="primary" id="confirm">Switch context</nova-button>
          <nova-button variant="quiet" id="cancel">Stay here</nova-button>
        </div>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        /* :host { display: block } is an author style and outranks the user
           agent's [hidden] { display: none }, so the host must opt back in.
           Without this the dialog renders on every load. */
        :host([hidden]) { display: none; }
        ul { list-style: none; margin: 0; padding: 0;
             display: flex; flex-direction: column; gap: var(--nova-space-tight); }
        li button {
          width: 100%; text-align: left; cursor: pointer;
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-body);
          color: var(--nova-color-text-primary);
          background: var(--nova-color-surface-inset);
          border: var(--nova-border-width) solid var(--nova-color-border-strong);
          border-radius: var(--nova-radius-control);
          padding: var(--nova-space-tight) var(--nova-space-snug);
        }
        li button:focus-visible, [part="actions"] :focus-visible {
          outline: var(--nova-border-emphasis) solid var(--nova-color-border-accent);
          outline-offset: var(--nova-space-tight);
        }
        [part="actions"] { display: flex; gap: var(--nova-space-tight); }
      </style>
      <div role="alertdialog" aria-labelledby="t" aria-describedby="d" tabindex="-1">
        <nova-box surface="raised" pad="gutter" radius="card" border="strong"
                  elevation="modal" direction="column" gap="gutter">
          <nova-badge tone="neutral">${mode === "ambiguous" ? "which scope?" : "explicit switch"}</nova-badge>
          <nova-text id="t" size="lead" weight="strong">
            ${mode === "ambiguous" ? "NOVA is not sure which scope you mean." : "This is a different scope."}
          </nova-text>
          <div id="d">${body}</div>
          <nova-text size="caption" tone="muted">
            Switching context changes what you are looking at. It grants no permission in the
            destination and approves nothing.
          </nova-text>
        </nova-box>
      </div>
    `;

    const dialog = this.shadowRoot.querySelector('[role="alertdialog"]');
    if (dialog) dialog.focus();

    const fire = (name, detail) =>
      this.dispatchEvent(new CustomEvent(name, { detail, bubbles: true, composed: true }));

    this.shadowRoot.querySelector("#confirm")?.addEventListener("click", () =>
      fire("switch-confirmed", { to }));
    this.shadowRoot.querySelector("#cancel")?.addEventListener("click", () =>
      fire("switch-cancelled", { to }));
    this.shadowRoot.querySelectorAll("[data-choose]").forEach((b) =>
      b.addEventListener("click", () => fire("scope-chosen", { scope: b.dataset.choose })));
  }
}

defineElement("nova-scope-switch", NovaScopeSwitch);
