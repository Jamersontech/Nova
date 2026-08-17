// nova-view -- what is shown at the current location.
//
// One composite per cross-cutting view rather than four screens, because
// Section 16 owns the navigation model and NOT screen design -- designing four
// real screens would be Section 18's Command Center arriving early. Each view
// here shows the minimum that proves it is reachable and correctly scoped.
//
// The approval view reuses Section 15's nova-approval-card unchanged, including
// its statement that only James approves (I-09). Nothing here implies that a
// model, an agent or an automation is the approving authority.

import "../../primitives/nova-text.js";
import "../../primitives/nova-box.js";
import "../../composites/nova-approval-card.js";
import "../../composites/nova-disclosure.js";
import { NovaElement, defineElement, pick } from "../../primitives/base.js";

const VIEWS = ["scope", "approvals", "activity", "tasks"];

class NovaView extends NovaElement {
  static observedAttributes = ["view", "at", "label"];

  render() {
    const view = pick(this, "view", VIEWS, "scope");
    const at = this.getAttribute("at") || "";
    const label = this.getAttribute("label") || "NOVA";

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        section { display: flex; flex-direction: column; gap: var(--nova-space-gutter); }
      </style>
      <section aria-label="${view} view">${this[view](at, label)}</section>
    `;
  }

  heading(text, sub) {
    return `
      <nova-box bare direction="column" gap="tight">
        <nova-text size="title" weight="strong">${text}</nova-text>
        <nova-text size="body" tone="muted">${sub}</nova-text>
      </nova-box>`;
  }

  // Level 2-3: see current state, drill in. Depth available, never imposed.
  scope(at, label) {
    return `
      ${this.heading(label, at ? `Scope ${at}` : "Three areas. Growth happens inside them, never beside them.")}
      <nova-disclosure summary="What NOVA did to prepare this" level="level 4">
        <nova-text size="body" tone="secondary">
          Activity, traces and decisions live here. Reached, not displayed.
        </nova-text>
      </nova-disclosure>`;
  }

  // "What needs my decision." Never buried, reachable from every state.
  approvals(at) {
    return `
      ${this.heading("Approvals", "What needs your decision")}
      <nova-approval-card
        risk="EXECUTE"
        area="business"
        action="Send the drafted onboarding email to Client A's primary contact."
        scope="${at || "BUSINESS / KAIRO / Client A"}"
        why="Sending leaves NOVA and reaches a person outside it."
        cost="One outbound email. No spend."
        if-wrong="The recipient receives an email they did not expect. It cannot be unsent."
        requested-by="Orchestrator, from a plan James stated"
      ></nova-approval-card>`;
  }

  // "What did NOVA do." Level 4, filterable by scope.
  activity(at) {
    return `
      ${this.heading("Activity", `What NOVA did${at ? ` in ${at}` : " — all scopes"}`)}
      <nova-disclosure summary="Plan, binding and budget" level="level 4">
        <nova-text size="body" tone="secondary">
          A chronological account, filtered to the active scope.
        </nova-text>
      </nova-disclosure>`;
  }

  // "What needs doing." In scope, and aggregated across scopes.
  tasks(at) {
    return `
      ${this.heading("Tasks", `What needs doing${at ? ` in ${at}` : " — across every scope"}`)}
      <nova-text size="body" tone="secondary">
        Tasks live inside their scope and aggregate into this view.
      </nova-text>`;
  }
}

defineElement("nova-view", NovaView);
