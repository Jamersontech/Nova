"""Delegation-tree budget — I-105, I-108, AG-13, AG-14, AG-15.

AG-13: the cost/token ceiling is a property of the ROOT EXECUTION, and EVERY
       DESCENDANT CONSUMES FROM THAT SAME BUDGET. A child cannot mint
       capacity, receive a fresh budget, raise the root ceiling, or transfer
       capacity into an independent budget.
AG-14: a parent MAY carve a smaller child ceiling — optional and narrowing.
       This is AG-7 applied to a consumable. Deliberately NOT mandatory: the
       architecture does not decide an allocation policy.
AG-15: exhaustion terminates and escalates; never silent degradation; above
       PREPARE it fails closed. Retries and fallback consume the same budget
       and are accounted PER ATTEMPT (I-104).

Concurrency, exactly as AG-13 specifies: concurrent descendants may each
observe remaining budget and proceed, so consumption can exceed the ceiling by
at most the in-flight calls' worth. THIS IS AN OVERRUN, NOT CAPACITY CREATION
— every such call still drew on the root budget, and the next check finds it
exhausted. A strictly serialized counter is deliberately NOT required.

NOT provider billing. This is NOVA's own authorization budget. The provider's
account balance is an external system and is not observable here — the
architecture does not claim otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import Denied, Risk


@dataclass
class RootBudget:
    """One per delegation tree. AG-13: not per agent (instances are ephemeral,
    so the budget would be meaningless) and not per client scope (too coarse —
    one runaway execution would consume a client's whole allowance)."""
    root_trace_id: str
    ceiling: int
    spent: int = 0

    @property
    def remaining(self) -> int:
        return max(self.ceiling - self.spent, 0)

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.ceiling


class BudgetLedger:
    """Holds root budgets and AG-14 subtree carves.

    A carve is a CAP ON WHAT A SUBTREE MAY DRAW from the root budget — never a
    separate pool. That distinction is what makes AG-13's "cannot transfer
    capacity into an independent budget" true rather than merely stated.
    """

    def __init__(self) -> None:
        self._roots: dict[str, RootBudget] = {}
        self._root_of: dict[str, str] = {}          # trace_id -> root trace_id
        self._ancestry: dict[str, tuple[str, ...]] = {}
        self._carve: dict[str, int] = {}            # trace_id -> AG-14 cap
        self._subtree_spend: dict[str, int] = {}    # trace_id -> drawn by it+descendants

    # -- registration ------------------------------------------------------

    def open_root(self, trace_id: str, ceiling: int) -> RootBudget:
        """I-105: EVERY execution carries a ceiling. A root opened without one
        is not representable — `ceiling` is required, and 0 is a valid (and
        immediately-exhausted) value, not an absent one."""
        if ceiling < 0:
            raise Denied("budget.open", "negative ceiling is not a budget", "I-105", True)
        b = RootBudget(root_trace_id=trace_id, ceiling=ceiling)
        self._roots[trace_id] = b
        self._root_of[trace_id] = trace_id
        self._ancestry[trace_id] = ()
        self._subtree_spend[trace_id] = 0
        return b

    def register_child(self, child_trace_id: str, ancestry: tuple[str, ...],
                       carve: int | None = None) -> None:
        """AG-13: the child joins the EXISTING tree. There is deliberately no
        method that opens a second root for a descendant — that is what
        "cannot receive a fresh budget" means, enforced by absence.

        AG-14: `carve` is optional. None means "no separate cap"; the subtree
        is bounded by the root budget alone.
        """
        if not ancestry:
            raise Denied("budget.register", "a child must name its ancestry", "AG-13", True)
        root = self._root_of.get(ancestry[0])
        if root is None:
            raise Denied("budget.register", "no root budget for this tree", "I-105", True)
        self._root_of[child_trace_id] = root
        self._ancestry[child_trace_id] = ancestry
        self._subtree_spend.setdefault(child_trace_id, 0)

        if carve is not None:
            if carve < 0:
                raise Denied("budget.carve", "negative carve", "AG-14", True)
            # AG-14 is AG-7 applied to a consumable: NARROWING only. A carve
            # may not exceed the parent's own effective cap.
            parent = ancestry[-1]
            parent_cap = self.effective_cap(parent)
            if carve > parent_cap:
                raise Denied("budget.carve",
                             f"carve {carve} exceeds parent's effective cap {parent_cap}",
                             "AG-14", True)
            # A carve, once set, may only NARROW. Raising an existing carve is
            # "receiving a fresh budget" (I-108) even when it stays under the
            # root ceiling -- found by the third slice, see FINDINGS.md 5.
            existing = self._carve.get(child_trace_id)
            if existing is not None and carve > existing:
                raise Denied("budget.carve",
                             f"carve may only narrow: {existing} -> {carve} refused",
                             "I-108", True)
            self._carve[child_trace_id] = carve

    # -- inspection --------------------------------------------------------

    def root_for(self, trace_id: str) -> RootBudget:
        root = self._root_of.get(trace_id)
        if root is None:
            # I-105: an execution with no budget does not run. Fail closed
            # rather than treating "unbudgeted" as "unlimited".
            raise Denied("budget.lookup", "execution has no budget", "I-105", True)
        return self._roots[root]

    def effective_cap(self, trace_id: str) -> int:
        """The most restrictive of: the root ceiling, and every carve on the
        path down to this execution."""
        cap = self.root_for(trace_id).ceiling
        chain = self._ancestry.get(trace_id, ()) + (trace_id,)
        for node in chain:
            if node in self._carve:
                cap = min(cap, self._carve[node])
        return cap

    def subtree_spent(self, trace_id: str) -> int:
        return self._subtree_spend.get(trace_id, 0)

    def remaining_for(self, trace_id: str) -> int:
        """What this execution may still draw: bounded by the ROOT budget and
        by every carve above it. Never by a pool of its own."""
        root = self.root_for(trace_id)
        allowance = root.remaining
        chain = self._ancestry.get(trace_id, ()) + (trace_id,)
        for node in chain:
            if node in self._carve:
                allowance = min(allowance, self._carve[node] - self.subtree_spent(node))
        return max(allowance, 0)

    # -- charging ----------------------------------------------------------

    def charge(self, trace_id: str, cost: int, risk: Risk) -> None:
        """AG-15 / I-105: exhaustion TERMINATES AND ESCALATES. Never silent
        degradation — there is deliberately no path here that reduces the
        request to fit, downgrades the model, or truncates context.

        Charged PER ATTEMPT (I-104): the caller invokes this for every attempt,
        including retries and failovers, and including attempts whose OUTCOME
        is unknown. Cost accounting records attempts, not outcomes.
        """
        if cost is None:
            raise Denied("budget.charge", "cost could not be computed", "I-105", True)
        if cost < 0:
            raise Denied("budget.charge", "negative cost is not a cost", "I-105", True)

        root = self.root_for(trace_id)

        # Check BEFORE charging. Above PREPARE this fails closed; at or below
        # it the same denial applies -- I-105 says a high-risk action does not
        # complete on a degraded basis, and nothing here degrades at all.
        if cost > self.remaining_for(trace_id):
            raise Denied(
                "budget.exhausted",
                f"cost {cost} exceeds remaining {self.remaining_for(trace_id)} "
                f"(root ceiling {root.ceiling}, root spent {root.spent}); "
                f"terminate and escalate",
                "I-105", risk > Risk.PREPARE)

        # Charge the ROOT (AG-13: every descendant consumes the same budget)
        # and every subtree on the path (AG-14 caps).
        root.spent += cost
        for node in self._ancestry.get(trace_id, ()) + (trace_id,):
            self._subtree_spend[node] = self._subtree_spend.get(node, 0) + cost
