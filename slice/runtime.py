"""The runtime -- wires the vertical slice's execution path.

    caller identity
     -> scope             ScopeTree
     -> Context Token     ContextService  (SOLE issuer, I-106)
     -> agent             AgentRegistry   (13 fields, refuse if incomplete)
     -> plan              Planner         (model.generated, LOW trust, I-112)
     -> binding           CapabilityLayer (RESOLVED FIRST, I-114(a))
     -> authorization     PDP             (ten steps, envelope, I-113/I-114(b))
     -> tool invocation   ToolPEP         (I-100, I-109, I-114(b) re-check)
     -> credential        CredentialBroker(steps 1-7 + 2a)
     -> integration       LocalEcho       (deterministic, no network)
     -> result            Outcome         (taint unioned, I-99/I-111)
     -> audit             AuditWriter     (W-1 / W-2)

ORCHESTRATION_ARCHITECTURE.md section 1: the orchestrator holds NO credentials
and makes NO authorization decisions -- it ASKS Policy. Both are true here:
this module never imports SecretsStore and never decides allow/deny.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from .agent.planner import Planner
from .agent.registry import AgentDefinition, AgentRegistry
from .core.audit import AuditWriter
from .core.broker import CredentialBroker
from .core.capability import CapabilityLayer
from .core.context_service import ContextService
from .core.policy import PolicyDecisionPoint
from .core.scope_tree import ScopeTree
from .core.store import StoreRegistry
from .core.types import (ArgumentEnvelope, Authorization, Classification, ContextToken,
                         Denied, Outcome, Plan, Risk, Taint)
from .tools.pep import ToolPEP
from .tools.registry import ToolRegistry


class Runtime:
    def __init__(self, tree: ScopeTree, context: ContextService, pdp: PolicyDecisionPoint,
                 capability: CapabilityLayer, tools: ToolRegistry, pep: ToolPEP,
                 broker: CredentialBroker, audit: AuditWriter, agents: AgentRegistry,
                 stores: StoreRegistry):
        self.tree = tree
        self.context = context
        self.pdp = pdp
        self.capability = capability
        self.tools = tools
        self.pep = pep
        self.broker = broker
        self.audit = audit
        self.agents = agents
        self.stores = stores
        self.planner = Planner()

    # -- the path ----------------------------------------------------------

    def issue_token(self, identity: str, agent_name: str, scope_path: str,
                    rights: frozenset[str], ceiling: Risk, ttl: float = 300.0) -> ContextToken:
        """I-106: the runtime REQUESTS; Context issues. The agent definition is
        passed so Context can verify against it -- the runtime does not
        pre-trim, because trimming would hide a refusal."""
        agent = self.agents.get(agent_name)
        return self.context.issue_root(
            identity=identity, actor=agent.name, scope_path=scope_path,
            rights=rights, ceiling=ceiling, ttl=ttl,
            agent_allowed_context=agent.allowed_context,
            agent_allowed_rights=agent.permissions,
            agent_risk_ceiling=agent.risk_ceiling,
        )

    def authorize(self, token: ContextToken, agent_name: str, plan: Plan,
                  tool_version: str, argument_envelope: ArgumentEnvelope,
                  cost_ceiling: int = 10, approval_id: Optional[str] = None,
                  is_external_transmission: bool = False) -> Authorization:
        """Resolve-then-decide. I-114(a): the binding exists BEFORE the PDP is
        asked, and is an input to the decision."""
        agent = self.agents.get(agent_name)

        # ---- SCOPE CONTAINMENT PRECEDES EVERYTHING THAT CAN LEAK ----------
        # IMPLEMENTATION FINDING 1 (see slice/FINDINGS.md).
        #
        # I-114(a) requires the binding to be resolved BEFORE the authorization
        # decision. Taken literally that puts capability.resolve() ahead of the
        # PDP's step 3 -- and resolution failure messages name the target scope
        # ("no binding for send_message in /business/KAIRO/client-b").
        #
        # I-03 forbids exactly that: an execution in one scope cannot "read,
        # write, or enumerate" another's resources "BY ANY PATH, INCLUDING
        # ERROR MESSAGES AND TIMING". It also made the denial point depend on
        # whether the target scope happened to have a binding -- unrelated
        # configuration changing which invariant fires.
        #
        # Resolved by the architecture's own reasoning, not by invention:
        # AUTHORIZATION_MODEL.md section 3 says step 3 precedes step 5 because
        # "scope containment is checked before permissions exist". The same
        # reasoning extends to binding resolution. I-114(a) is preserved: the
        # binding is still resolved before the DECISION.
        for step in plan.steps:
            if not token.covers(step.resource):
                raise Denied("runtime.scope", "token does not cover the target scope",
                             "I-03", True)
        if not token.covers(plan.scope_path):
            raise Denied("runtime.scope", "token does not cover the target scope",
                         "I-03", True)

        # Allowed Tools is a CLOSED list.
        for step in plan.steps:
            if step.tool_name not in agent.allowed_tools:
                raise Denied("runtime.allowed_tools",
                             f"{step.tool_name} not in agent's closed tool list",
                             "AGENT_ARCHITECTURE-2", True)

        # ---- I-114(a): RESOLVE FIRST --------------------------------------
        resolved = {}
        for step in plan.steps:
            resolved[step.tool_name] = self.capability.resolve(
                step.tool_name, tool_version, plan.scope_path)

        # ---- then DECIDE ---------------------------------------------------
        return self.pdp.authorize_plan(
            token=token, plan=plan, resolved_bindings=resolved,
            argument_envelope=argument_envelope, cost_ceiling=cost_ceiling,
            approval_id=approval_id, is_external_transmission=is_external_transmission,
        )

    def execute(self, token: ContextToken, plan: Plan, authorization: Authorization,
                tool_version: str,
                transport: Callable[[dict[str, Any], str], Outcome]) -> list[Outcome]:
        """Per-action enforcement. Each step goes through the Tool PEP, which
        re-resolves and re-checks the binding per attempt (I-114(b))."""
        results: list[Outcome] = []
        for step in plan.steps:
            outcome = self.pep.invoke(
                token=token, plan=plan, step=step, authorization=authorization,
                resolve_binding=lambda t, s, v=tool_version: self.capability.resolve(t, v, s),
                transport=transport, tool_version=tool_version,
            )
            results.append(outcome)
        return results

    def persist_result(self, token: ContextToken, item_id: str, outcome: Outcome) -> None:
        """I-111: provenance, taint and classification survive persistence and
        are restored at retrieval. The taint is written as a column, not
        recomputed on read."""
        store = self.stores.for_scope(token.scope_path)
        store.put_item(item_id, token.scope_path, outcome.detail, outcome.taint.to_row())

    def load_result(self, token: ContextToken, item_id: str) -> tuple[str, Taint]:
        store = self.stores.for_scope(token.scope_path)
        row = store.get_item(item_id)
        if row is None:
            raise Denied("runtime.load", f"no item {item_id}", "I-14")
        _scope, body, taint_row = row
        return body, Taint.from_row(taint_row)
