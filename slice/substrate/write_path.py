"""The first authorized WRITE: plan -> approval -> PEP -> boundary -> WITH CHECK.

A write is a consequence-producing tool action, so unlike the read path
(ADR 0045) nothing here is a new decision sequence -- it is the EXISTING
tool-action architecture, driven for the first time against the real
datastore:

    proposed write
      -> Plan (I-112 deterministic identity)
      -> PolicyDecisionPoint.authorize_plan   -- the full ten steps;
         step 9 DENIES an EXECUTE-class plan with no approval (I-09)
      -> James's approval, held server-side, bound to the plan identity
      -> ToolPEP.invoke                       -- I-100 envelope, I-114(b)
         binding re-check, I-109 re-check, broker injection
      -> transport = the Postgres integration: a scope-bound channel from
         the Data-Access Boundary; INSERT under RLS WITH CHECK
      -> audit row in the same transaction    (I-93, W-1)

WHY THE TRANSPORT GOES THROUGH THE BOUNDARY
-------------------------------------------
The tool's side effect lands in NOVA's own datastore, so the integration is
subject to the same physical isolation as every other access: the channel is
bound to the token's scope and WITH CHECK rejects any row outside it -- even
if every application-side control above this line were bypassed. The hostile
tests drive exactly that bypass.

WHAT IS A STAND-IN
------------------
Approval CAPTURE. `ApprovalStore.james_approves` records James's act; the
surface that presents and captures approvals is Section 26's scope. I-09 is
preserved: nothing in this module can create an approval except that method,
and the PDP denies without one. The stand-in is one method, replaced when the
approval surface exists.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from ..core.broker import CredentialBroker
from ..core.policy import PolicyDecisionPoint
from ..core.types import (Approval, ArgumentEnvelope, ContextToken, Denied,
                          ExecutionBinding, Outcome, Plan, PlanStep, Risk, Taint)
from ..tools.pep import ToolPEP
from ..tools.registry import ToolRegistry, ToolDefinition, CONSEQUENCE, EXPRESSIVE
from .boundary import DataAccessBoundary

TOOL = "write_item"
TOOL_VERSION = "1.0.0"


def write_item_tool() -> ToolDefinition:
    """The tool declaration, complete per ADR 0036 (totality)."""
    return ToolDefinition(
        name=TOOL, version=TOOL_VERSION, purpose="Create or update one scoped item",
        input_schema={"item_ref": "str", "body": "str"},
        output_schema={"status": "str"},
        required_rights=frozenset({"write"}),
        auth_requirements="datastore",
        risk_class=Risk.EXECUTE,
        context_requirements=frozenset({"client"}),
        error_behaviour="typed", audit_behaviour="reference-only",
        # ON CONFLICT upsert by (scope_path, item_ref): the DEDUPLICATION is
        # enforced by the provider (PostgreSQL's unique constraint), which is
        # what S11-D2 requires before declaring idempotency.
        idempotent=True, cost_profile=1,
        consequence_determining={
            "item_ref": CONSEQUENCE,   # addresses the record
            "body": EXPRESSIVE,        # prose -- MT-5, same ruling as harness
        },
    )


class ApprovalStore:
    """Approvals by plan identity. I-09: only James's act creates one."""

    def __init__(self) -> None:
        self._by_plan: dict[str, Approval] = {}

    def james_approves(self, plan_identity: str) -> Approval:
        """James's approval of ONE plan -- not standing, names no source.
        Capture surface is Section 26's scope; this records the act."""
        a = Approval(approval_id=f"appr-{plan_identity[:12]}", standing=False)
        self._by_plan[plan_identity] = a
        return a

    def for_plan(self, plan_identity: str) -> Optional[Approval]:
        return self._by_plan.get(plan_identity)


class PostgresItemIntegration:
    """The integration: writes land through the Data-Access Boundary.

    The injected secret arrives at the call boundary per the broker protocol
    and goes no further; the datastore credential itself is held by the
    boundary's pool, never by this class and never by the tool.
    """

    def __init__(self, boundary: DataAccessBoundary):
        self._boundary = boundary
        self.side_effects = 0

    def transport_for(self, token: ContextToken):
        def transport(payload: dict[str, Any], secret: str) -> Outcome:
            with self._boundary.open(token) as ch:
                # The row's scope is the CHANNEL's scope -- the transport
                # cannot name another one, and WITH CHECK would refuse it.
                ch.execute(
                    "INSERT INTO item (item_ref, scope_path, body)"
                    " VALUES (%s, %s, %s)"
                    " ON CONFLICT (scope_path, item_ref)"
                    " DO UPDATE SET body = EXCLUDED.body",
                    (payload["item_ref"], ch.scope_path, payload["body"]),
                )
                event_identity = hashlib.sha256(
                    f"data_write:{token.trace_id}:{ch.scope_path}:{payload['item_ref']}".encode()
                ).hexdigest()[:32]
                ch.execute(
                    "INSERT INTO audit_record"
                    " (event_identity, writer, category, scope_path, trace_id, actor_ref, detail)"
                    " VALUES (%s,'W-1','data.write',%s,%s,%s,%s)"
                    " ON CONFLICT (event_identity) DO NOTHING",
                    (event_identity, ch.scope_path, token.trace_id, token.actor,
                     f"item_ref={payload['item_ref']}"),
                )
            self.side_effects += 1
            return Outcome("success_claimed", f"wrote {payload['item_ref']}",
                           Taint.of("integration.supplied"))
        return transport


class WritePath:
    """Wires the EXISTING authorization machinery to the real datastore."""

    def __init__(self, pdp: PolicyDecisionPoint, registry: ToolRegistry,
                 pep: ToolPEP, broker: CredentialBroker,
                 integration: PostgresItemIntegration,
                 credential_binding_id: str):
        self._pdp = pdp
        self._registry = registry
        self._pep = pep
        self._integration = integration
        self._cred_id = credential_binding_id
        self.approvals = ApprovalStore()

    # -- the proposed execution, deterministic (I-112) ----------------------

    def plan_for(self, scope_path: str, item_ref: str, body: str) -> Plan:
        return Plan(
            steps=(PlanStep(action=TOOL, resource=scope_path, tool_name=TOOL,
                            required_rights=frozenset({"write"}),
                            arguments={"item_ref": item_ref, "body": body}),),
            required_rights=frozenset({"write"}),
            declared_risk=Risk.EXECUTE,
            scope_path=scope_path,
            taint=Taint.of("james.stated"),
            cost_estimate=1,
        )

    def binding_for(self, scope_path: str) -> ExecutionBinding:
        """I-114: the concrete substrate, resolved before the decision."""
        return ExecutionBinding(
            tool_name=TOOL, tool_version=TOOL_VERSION,
            integration_id="int-postgres-items", provider="postgresql",
            account="nova_substrate", endpoint="local:5433", api_version="16",
            credential_binding_id=self._cred_id, scope_path=scope_path,
        )

    # -- the full authorized execution --------------------------------------

    def execute(self, token: ContextToken, scope_path: str,
                item_ref: str, body: str) -> Outcome:
        """Authorize, then execute. No database write occurs before
        authorize_plan has succeeded -- the transport is not even constructed
        until the PEP, and the PEP requires the authorization object."""
        plan = self.plan_for(scope_path, item_ref, body)
        binding = self.binding_for(scope_path)
        envelope = ArgumentEnvelope(
            allowed_values={"item_ref": frozenset({item_ref})},
            magnitude_ceilings={},
        )
        approval = self.approvals.for_plan(plan.identity())

        # The full ten steps. Step 9 denies EXECUTE with no approval (I-09).
        authorization = self._pdp.authorize_plan(
            token, plan, {TOOL: binding}, envelope,
            cost_ceiling=10, approval=approval,
        )

        return self._pep.invoke(
            token, plan, plan.steps[0], authorization,
            resolve_binding=lambda name, scope: self.binding_for(scope),
            transport=self._integration.transport_for(token),
            tool_version=TOOL_VERSION,
            provider_enforces_dedup=True,
        )
