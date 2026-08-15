"""The Planner.

I-112: a plan is a security object with a declared schema and a deterministic
identity. The Planner is a MODEL, so its output is `model.generated` at LOW
trust (I-99), and producing a plan confers nothing (I-20). A plan becomes
authoritative only when authorized -- never before, and never by assertion.

SLICE-LOCAL: no model provider is used. The plan is constructed
deterministically and LABELLED `model.generated` so the taint machinery is
exercised exactly as it would be with a real Planner. Substituting a real
model would change where the text comes from, not what the labels are.

ORCHESTRATION_ARCHITECTURE.md section 1: the Planner NEVER owns "authorizing
the plan it produced" -- there is deliberately no authorize() here.
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.types import Classification, Plan, PlanStep, Risk, Taint


class Planner:
    def plan(self, objective: str, scope_path: str, tool_name: str, action: str,
             resource: str, required_rights: frozenset[str], arguments: dict[str, Any],
             declared_risk: Risk, cost_estimate: int = 1,
             input_taint: Optional[Taint] = None,
             classification: Classification = Classification.INTERNAL) -> Plan:
        """`input_taint` is the union of everything the Planner read. A plan
        that read untrusted content carries that fact to the authorization
        boundary -- which is what makes I-40 enforceable."""
        base = input_taint or Taint.of("james.stated", classification)
        # I-99: the Planner's output is a derivation of its inputs PLUS its own
        # model.generated provenance, at the lowest trust among them.
        plan_taint = base.derive("model.generated")

        return Plan(
            steps=(PlanStep(action=action, resource=resource, tool_name=tool_name,
                            required_rights=frozenset(required_rights),
                            arguments=dict(arguments)),),
            required_rights=frozenset(required_rights),
            declared_risk=declared_risk,
            scope_path=scope_path,
            taint=plan_taint,
            cost_estimate=cost_estimate,
        )
