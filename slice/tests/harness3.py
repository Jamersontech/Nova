"""Third-slice fixture: a three-level delegation tree A -> B -> C with budgets.

Reuses harness2's two agents and adds Agent C, plus a BudgetLedger wired into
the gateway. Nothing else changes.
"""

from __future__ import annotations

import time

from ..agent.registry import AgentDefinition
from ..core.budget import BudgetLedger
from ..core.delegation import Delegation
from ..core.types import Risk
from .harness2 import (PROFILE, SCOPE_A, SCOPE_A_SUB, build as build2,
                       cleanup, coordinator_token, delegate_to_b, items)

SCOPE_A_LEAF = "/business/KAIRO/client-a/research/leaf"


def build(model_behaviour: str = "normal", root_ceiling: int = 10_000):
    rt, gw, provider, tmp = build2(model_behaviour=model_behaviour)

    # A third scope level, and Agent C, narrower again than B.
    rt.tree.add_scope(SCOPE_A_LEAF, "task")
    rt.tree.james_grants("james", "read", "*", SCOPE_A_LEAF, Risk.READ)
    rt.tree.james_grants("james", "research", "*", SCOPE_A_LEAF, Risk.ANALYZE)

    rt.agents.register(AgentDefinition(
        name="summariser", purpose="summarise one document",
        responsibilities=("summarise",),
        non_responsibilities=("never send", "never delegate"),
        allowed_context=SCOPE_A_LEAF,
        allowed_tools=frozenset(),
        permissions=frozenset({"read"}),
        inputs=("document",), outputs=("summary",),
        success_criteria=("summary produced",), failure_conditions=("no document",),
        escalation_rules=("escalate to researcher",), risk_ceiling=Risk.READ))

    ledger = BudgetLedger()
    rt.budget = ledger
    gw._budget = ledger
    return rt, gw, provider, ledger, tmp


def root_with_budget(rt, ledger, ceiling: int, ttl: float = 300.0):
    """Agent A's root execution, with the tree's single budget (AG-13)."""
    a = coordinator_token(rt, ttl=ttl)
    ledger.open_root(a.trace_id, ceiling)
    return a


def delegate_b(rt, ledger, a, carve: int | None = None, **kw):
    b = delegate_to_b(rt, a, **kw) if kw else delegate_to_b(
        rt, a, _valid(a, may_redelegate=True))
    ledger.register_child(b.trace_id, rt.context.facts(b)["ancestry"], carve=carve)
    return b


def delegate_c(rt, ledger, b, carve: int | None = None, ttl: float = 20.0):
    c_def = rt.agents.get("summariser")
    d = Delegation(delegator=b.trace_id, delegate="summariser",
                   scope_path=SCOPE_A_LEAF, rights=frozenset({"read"}),
                   tools=frozenset(), risk_ceiling=Risk.READ,
                   expires_at=time.time() + ttl, may_redelegate=False,
                   ancestry=(), purpose="summarise one document")
    c = rt.context.delegate(b, d,
                            delegate_allowed_context=c_def.allowed_context,
                            delegate_allowed_tools=c_def.allowed_tools,
                            delegate_permissions=c_def.permissions,
                            delegate_risk_ceiling=c_def.risk_ceiling)
    ledger.register_child(c.trace_id, rt.context.facts(c)["ancestry"], carve=carve)
    return c


def _valid(parent, *, may_redelegate=False, ttl=60.0):
    return Delegation(delegator=parent.trace_id, delegate="researcher",
                      scope_path=SCOPE_A_SUB, rights=frozenset({"read"}),
                      tools=frozenset(), risk_ceiling=Risk.ANALYZE,
                      expires_at=time.time() + ttl, may_redelegate=may_redelegate,
                      ancestry=(), purpose="research")


def call(gw, token, cost_items=None, **kw):
    return gw.call(token, cost_items or items(), PROFILE, "acme-llm", "acme-small", **kw)
