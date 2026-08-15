// nova-approval-card -- risk-classified approval presentation.
//
// Built against the ACCEPTED text of USER_INTERFACE_ARCHITECTURE.md section 6
// only. That text requires an approval request to state, in plain language:
// what will happen, in which scope, why it needs approval, what it costs, and
// what happens if it is wrong -- approvable in one action, never buried.
//
// Deliberately NOT implemented here: the reachability-versus-authentication-
// strength distinction, session strength ceilings and voice step-up. Those
// exist only under ADR 0040, which is Proposed. This component therefore makes
// no claim about which surface may COMPLETE an approval -- it presents one.
//
// I-09: only James approves. Nothing in this component may imply that a model,
// an agent or an automation is the approving authority, which is why the
// requester is labelled as the requester and the authority line is fixed text.

import "../primitives/nova-box.js";
import "../primitives/nova-text.js";
import "../primitives/nova-badge.js";
import "../primitives/nova-button.js";
import { NovaElement, defineElement, pick } from "../primitives/base.js";

// PERMISSION_ARCHITECTURE.md section 4's classes, mapped to section 5's
// approval policies. The mapping lives here rather than in the badge so the
// badge stays a presentation primitive.
const RISK = {
  READ: "autonomous",
  ANALYZE: "autonomous",
  RECOMMEND: "autonomous",
  PREPARE: "autonomous",
  EXECUTE: "contextual",
  "HIGH-IMPACT EXECUTE": "explicit",
  IRREVERSIBLE: "explicit",
};

class NovaApprovalCard extends NovaElement {
  static observedAttributes = ["risk", "scope", "action", "why", "cost", "if-wrong", "requested-by"];

  render() {
    const riskClass = this.getAttribute("risk") in RISK ? this.getAttribute("risk") : "EXECUTE";
    const tone = RISK[riskClass];
    const needsExplicit = tone === "explicit";

    const field = (label, value) => `
      <nova-box bare direction="column" gap="tight">
        <nova-text size="caption" tone="muted" tracking="label">${label}</nova-text>
        <nova-text size="body" tone="secondary">${value}</nova-text>
      </nova-box>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        .head { display: flex; align-items: center; gap: var(--nova-space-snug); flex-wrap: wrap; }
        .actions { display: flex; gap: var(--nova-space-tight); }
      </style>
      <!-- Emphasis for explicit-approval risk is weight, not hue. Bordering it
           with the accent token would make the most dangerous card change
           colour whenever the brand accent changes, which says "selected"
           rather than "irreversible". Risk colour stays on the badge. -->
      <nova-box surface="raised" pad="gutter" radius="card"
                border="${needsExplicit ? "strong" : "subtle"}"
                elevation="${needsExplicit ? "modal" : "panel"}"
                direction="column" gap="gutter">

        <div class="head">
          <nova-badge tone="${tone}">${riskClass}</nova-badge>
          <nova-badge area="${this.getAttribute("area") || "business"}">
            ${this.getAttribute("area") || "business"}
          </nova-badge>
        </div>

        <nova-text size="lead" weight="strong">${this.getAttribute("action") || ""}</nova-text>

        ${field("in scope", this.getAttribute("scope") || "")}
        ${field("why approval is needed", this.getAttribute("why") || "")}
        ${field("what it costs", this.getAttribute("cost") || "")}
        ${field("if this is wrong", this.getAttribute("if-wrong") || "")}
        ${field("requested by", this.getAttribute("requested-by") || "")}

        <nova-box bare direction="column" gap="tight">
          <nova-text size="caption" tone="muted">
            Only James can approve this. NOVA prepared the request; it cannot approve it.
          </nova-text>
          <div class="actions">
            <nova-button variant="primary">Approve</nova-button>
            <nova-button variant="quiet">Decline</nova-button>
          </div>
        </nova-box>
      </nova-box>
    `;
  }
}

defineElement("nova-approval-card", NovaApprovalCard);
