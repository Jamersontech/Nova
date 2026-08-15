"""Third vertical slice: delegation-tree budgets and runaway-spend controls.

I-105, I-108, AG-13, AG-14, AG-15 across a three-level tree A -> B -> C.

NOT provider billing. This validates NOVA's own AUTHORIZATION budget. A
provider's account balance is an external system and is not observable here;
the architecture does not claim otherwise.
"""

from __future__ import annotations

import time
import unittest

from ..core.budget import BudgetLedger
from ..core.delegation import Delegation
from ..core.gateway import ModelRequestItem
from ..core.types import Classification, Denied, Risk, Taint, Trust
from .harness2 import PROFILE, SCOPE_A_SUB, items
from .harness3 import (SCOPE_A_LEAF, build, call, cleanup, delegate_b,
                       delegate_c, root_with_budget)


def big(n_chars: int, scope=SCOPE_A_SUB):
    """A request whose COST is proportional to its size."""
    return [ModelRequestItem(label="doc", content="x" * n_chars, scope_path=scope,
                             taint=Taint.of("james.stated", Classification.CLIENT_CONFIDENTIAL))]


class Slice3(unittest.TestCase):
    behaviour = "normal"
    ceiling = 10_000

    def setUp(self):
        self.rt, self.gw, self.provider, self.ledger, self.tmp = build(
            model_behaviour=self.behaviour)
        self.a = root_with_budget(self.rt, self.ledger, self.ceiling)

    def tearDown(self):
        cleanup(self.rt, self.tmp)


# ===========================================================================
# 1-2. Delegating within / beyond the budget
# ===========================================================================
class Test01BudgetDelegation(Slice3):
    def test_delegate_within_budget_passes(self):
        """1. A has a budget and delegates within it -> PASS. AG-14 carve."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=4_000)
        self.assertEqual(self.ledger.root_for(b.trace_id).ceiling, self.ceiling)
        self.assertEqual(self.ledger.effective_cap(b.trace_id), 4_000)
        # AG-13: it is the SAME root budget, not a new one.
        self.assertEqual(self.ledger.root_for(b.trace_id).root_trace_id, self.a.trace_id)

    def test_carve_larger_than_parent_denied(self):
        """2. A delegates more budget than it possesses -> DENY. AG-14 is
        AG-7 applied to a consumable: NARROWING only."""
        with self.assertRaises(Denied) as ctx:
            delegate_b(self.rt, self.ledger, self.a, carve=self.ceiling + 1)
        self.assertEqual(ctx.exception.step, "budget.carve")
        self.assertEqual(ctx.exception.invariant, "AG-14")

    def test_carve_is_optional(self):
        """AG-14 is deliberately NOT mandatory -- requiring it would force an
        allocation policy the architecture does not decide."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=None)
        self.assertEqual(self.ledger.effective_cap(b.trace_id), self.ceiling)

    def test_child_cannot_open_a_second_root(self):
        """AG-13: 'cannot receive a fresh budget'. Enforced by ABSENCE -- there
        is no API that opens a root for a descendant, and registering a child
        without ancestry is refused."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=1_000)
        with self.assertRaises(Denied) as ctx:
            self.ledger.register_child(b.trace_id, ancestry=(), carve=None)
        self.assertEqual(ctx.exception.invariant, "AG-13")


# ===========================================================================
# 3-5. Spending inside and outside the delegated envelope
# ===========================================================================
class Test02SpendingBounds(Slice3):
    def test_child_cannot_spend_beyond_its_carve(self):
        """3. B cannot spend outside its delegated budget -> DENY."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        call(self.gw, b, big(200))                       # 200 units, fits
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 200)
        with self.assertRaises(Denied) as ctx:
            call(self.gw, b, big(400))                   # 200+400 > 500
        self.assertEqual(ctx.exception.step, "budget.exhausted")
        self.assertEqual(ctx.exception.invariant, "I-105")
        # AG-15: terminate and escalate, never silent degradation.
        self.assertIn("terminate and escalate", ctx.exception.reason)
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 200)   # not charged

    def test_grandchild_carve_cannot_exceed_parents(self):
        """4. B cannot give C more budget than B possesses -> DENY."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        with self.assertRaises(Denied) as ctx:
            delegate_c(self.rt, self.ledger, b, carve=900)
        self.assertEqual(ctx.exception.step, "budget.carve")

    def test_grandchild_cannot_reach_the_roots_unused_budget(self):
        """5. C cannot spend against A's unused budget directly.

        The root has 10,000 free. B's carve is 300. C is bounded by B's carve,
        NOT by what the root happens to have left."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=300)
        c = delegate_c(self.rt, self.ledger, b, carve=None)
        self.assertGreater(self.ledger.root_for(c.trace_id).remaining, 9_000)
        self.assertEqual(self.ledger.remaining_for(c.trace_id), 300)
        with self.assertRaises(Denied) as ctx:
            call(self.gw, c, big(500, scope=SCOPE_A_LEAF))
        self.assertEqual(ctx.exception.step, "budget.exhausted")


# ===========================================================================
# 6-8. Accounting
# ===========================================================================
class Test03Accounting(Slice3):
    def test_parent_and_child_spend_both_hit_the_root(self):
        """6. Parent and child spending is accounted correctly. AG-13: every
        descendant consumes from the SAME budget."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=5_000)
        c = delegate_c(self.rt, self.ledger, b, carve=1_000)
        call(self.gw, self.a, big(100))
        call(self.gw, b, big(200))
        call(self.gw, c, big(300, scope=SCOPE_A_LEAF))

        root = self.ledger.root_for(self.a.trace_id)
        self.assertEqual(root.spent, 600)                       # 100+200+300
        self.assertEqual(self.ledger.subtree_spent(self.a.trace_id), 600)
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 500)   # 200+300
        self.assertEqual(self.ledger.subtree_spent(c.trace_id), 300)

    def test_siblings_cannot_collectively_exceed_the_parents_carve(self):
        """7. Multiple children cannot collectively exceed the parent's
        permitted budget. Each is individually within the carve; together they
        are not."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        c1 = delegate_c(self.rt, self.ledger, b, carve=400)
        c2 = delegate_c(self.rt, self.ledger, b, carve=400)   # 400+400 > 500
        call(self.gw, c1, big(350, scope=SCOPE_A_LEAF))
        with self.assertRaises(Denied) as ctx:
            call(self.gw, c2, big(350, scope=SCOPE_A_LEAF))   # 350+350 > 500
        self.assertEqual(ctx.exception.step, "budget.exhausted")
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 350)

    def test_repeated_delegation_manufactures_no_budget(self):
        """8. Repeated delegation cannot manufacture additional budget.
        AG-13: 'a duplicate or replayed delegation request creates no capacity
        either -- both draw on the same budget.'"""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        before = self.ledger.root_for(self.a.trace_id).ceiling
        chain = [delegate_c(self.rt, self.ledger, b, carve=500) for _ in range(5)]
        self.assertEqual(self.ledger.root_for(self.a.trace_id).ceiling, before)
        # All five draw on the SAME 500.
        call(self.gw, chain[0], big(300, scope=SCOPE_A_LEAF))
        with self.assertRaises(Denied):
            call(self.gw, chain[1], big(300, scope=SCOPE_A_LEAF))
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 300)


# ===========================================================================
# 9-11. Retries and unknown outcomes
# ===========================================================================
class Test04RetriesAndUnknown(Slice3):
    def test_retry_creates_no_budget_and_is_charged_per_attempt(self):
        """9. Retry cannot create additional budget.
        AG-15/I-104: retries consume the same budget, accounted PER ATTEMPT."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        for _ in range(2):
            call(self.gw, b, big(200))
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 400)   # 2 attempts
        with self.assertRaises(Denied):
            call(self.gw, b, big(200))                                 # 600 > 500
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 400)


class Test05UnknownOutcomeCosts(Slice3):
    behaviour = "timeout"

    def test_unknown_outcome_is_not_free(self):
        """10. An unknown model outcome cannot be treated as free.
        I-104: 'cost accounting records ATTEMPTS, not outcomes.'"""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        r = call(self.gw, b, big(200))
        self.assertEqual(r.outcome, "unknown")
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 200)   # charged anyway

    def test_retry_after_unknown_obeys_reliability_and_budget(self):
        """11. Retry after unknown follows the existing rules: each attempt is
        separately authorized (I-104) AND separately charged."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        call(self.gw, b, big(200))
        call(self.gw, b, big(200))
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 400)
        with self.assertRaises(Denied) as ctx:
            call(self.gw, b, big(200))
        self.assertEqual(ctx.exception.invariant, "I-105")


# ===========================================================================
# 12-13. Revocation
# ===========================================================================
class Test06Revocation(Slice3):
    def test_revocation_prevents_subsequent_spending(self):
        """12. Revocation prevents subsequent spending."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        call(self.gw, b, big(100))
        spent = self.ledger.subtree_spent(b.trace_id)
        self.rt.context.revoke(b.trace_id)
        with self.assertRaises(Denied) as ctx:
            call(self.gw, b, big(100))
        self.assertEqual(ctx.exception.invariant, "I-74")
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), spent)   # nothing charged

    def test_revocation_mid_chain_enforced_at_next_enforcement_point(self):
        """13. Revocation during a delegation chain is enforced at the next
        required enforcement point. AG-11 / V-2 -- not retroactively."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=1_000)
        c = delegate_c(self.rt, self.ledger, b, carve=500)
        call(self.gw, c, big(100, scope=SCOPE_A_LEAF))
        spent = self.ledger.root_for(self.a.trace_id).spent

        self.rt.context.end_execution(b.trace_id)     # B, the middle link, ends
        with self.assertRaises(Denied) as ctx:
            call(self.gw, c, big(100, scope=SCOPE_A_LEAF))
        self.assertEqual(ctx.exception.invariant, "I-107")
        self.assertEqual(self.ledger.root_for(self.a.trace_id).spent, spent)
        # The completed call is NOT refunded or undone.
        self.assertGreater(spent, 0)


# ===========================================================================
# 14-15. Cost cannot be manipulated
# ===========================================================================
class Test07CostIntegrity(Slice3):
    def test_declared_cost_is_ignored_for_charging(self):
        """14. A model cannot manipulate cost metadata to bypass the budget.
        The gateway COMPUTES cost from the actual request; `declared_cost` is
        accepted and deliberately ignored."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        call(self.gw, b, big(300), declared_cost=1)
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 300)   # not 1

    def test_cheap_declaration_with_expensive_request_still_denies(self):
        """15. A model cannot declare a cheap cost while actually requesting a
        more expensive operation."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        with self.assertRaises(Denied) as ctx:
            call(self.gw, b, big(5_000), declared_cost=1)
        self.assertEqual(ctx.exception.step, "budget.exhausted")
        self.assertEqual(self.ledger.subtree_spent(b.trace_id), 0)

    def test_uncomputable_cost_fails_closed(self):
        """20. A missing/uncomputable cost fails closed rather than becoming
        free. I-52's pattern."""
        from ..core.gateway import ProviderBinding
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        broken = ProviderBinding(provider="acme-llm", model="acme-small",
                                 endpoint="e", api_version="v", credential_ref="ref",
                                 cost_per_unit=None)
        self.gw._providers["acme-llm"] = broken
        with self.assertRaises(Denied) as ctx:
            call(self.gw, b, big(10))
        self.assertEqual(ctx.exception.step, "gateway.cost")
        self.assertEqual(ctx.exception.invariant, "I-105")
        self.assertTrue(ctx.exception.security_event)


# ===========================================================================
# 16-17. A child cannot alter ceilings
# ===========================================================================
class Test08ChildCannotAlterCeilings(Slice3):
    def test_child_cannot_raise_its_own_cap(self):
        """16. A child cannot alter its own ceiling.

        FINDING 5 (see slice/FINDINGS.md): re-registering with a LARGER carve
        initially SUCCEEDED, because the check compared against the parent's
        cap (10,000) rather than the child's existing carve (500). Raising
        500 -> 9,000 is "receiving a fresh budget" under I-108 even though the
        root ceiling is untouched. A carve may now only NARROW."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        with self.assertRaises(Denied) as ctx:
            self.ledger.register_child(b.trace_id,
                                       self.rt.context.facts(b)["ancestry"],
                                       carve=9_000)
        self.assertEqual(ctx.exception.invariant, "I-108")
        self.assertEqual(self.ledger.effective_cap(b.trace_id), 500)

    def test_carve_may_still_be_narrowed(self):
        """Narrowing an existing carve remains permitted -- AG-14 is a
        narrowing rule, and this is narrowing."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        self.ledger.register_child(b.trace_id,
                                   self.rt.context.facts(b)["ancestry"], carve=200)
        self.assertEqual(self.ledger.effective_cap(b.trace_id), 200)

    def test_child_cannot_alter_the_parents_remaining_budget(self):
        """17. A child cannot alter its parent's remaining budget -- other than
        by spending it, which is the point of a shared budget."""
        b = delegate_b(self.rt, self.ledger, self.a, carve=500)
        root = self.ledger.root_for(self.a.trace_id)
        before = root.remaining
        call(self.gw, b, big(100))
        self.assertEqual(root.remaining, before - 100)   # only spending moves it
        # There is no method by which a child credits, resets or transfers.
        self.assertFalse(any(m for m in dir(self.ledger)
                             if m.startswith(("credit", "refund", "reset", "transfer"))))

    def test_carve_does_not_create_an_independent_pool(self):
        """AG-13: 'cannot transfer capacity into an independent budget.'
        A carve is a CAP on drawing from the root, never a separate pool: when
        the ROOT is exhausted the carve is worthless."""
        rt, gw, prov, ledger, tmp = build()
        try:
            a = root_with_budget(rt, ledger, 300)
            b = delegate_b(rt, ledger, a, carve=250)
            call(gw, a, big(300))                       # root fully spent by A
            self.assertEqual(ledger.root_for(a.trace_id).remaining, 0)
            self.assertEqual(ledger.remaining_for(b.trace_id), 0)   # carve is worthless
            with self.assertRaises(Denied):
                call(gw, b, big(10))
        finally:
            cleanup(rt, tmp)


# ===========================================================================
# 18-19. Concurrency and the zero budget
# ===========================================================================
class Test09ConcurrencyAndZero(Slice3):
    def test_concurrent_children_overrun_boundedly_and_never_mint(self):
        """18. Concurrent children cannot collectively exceed the authorized
        aggregate budget.

        AG-13 SPECIFIES this outcome rather than leaving it open: 'concurrent
        descendants may each observe remaining budget and proceed, so
        consumption can exceed the ceiling by at most the in-flight calls'
        worth. THIS IS AN OVERRUN, NOT CAPACITY CREATION -- every one of those
        calls still drew on the root budget, and the next check finds it
        exhausted.' A serialized counter is deliberately NOT required.

        This test asserts the SPECIFIED property: bounded overrun, then hard
        stop. It does not assert perfect serialization, which the architecture
        explicitly does not require."""
        import threading
        rt, gw, prov, ledger, tmp = build()
        try:
            a = root_with_budget(rt, ledger, 1_000)
            kids = [delegate_c(rt, ledger, delegate_b(rt, ledger, a, carve=1_000))
                    for _ in range(4)]
            errors = []

            def spend(tok):
                try:
                    call(gw, tok, big(400, scope=SCOPE_A_LEAF))
                except Denied:
                    errors.append(1)

            threads = [threading.Thread(target=spend, args=(k,)) for k in kids]
            for t in threads: t.start()
            for t in threads: t.join()

            root = ledger.root_for(a.trace_id)
            in_flight_worth = 4 * 400
            # Never mints: consumption is bounded by ceiling + in-flight worth.
            self.assertLessEqual(root.spent, root.ceiling + in_flight_worth)
            # And afterwards the budget is hard-stopped.
            with self.assertRaises(Denied):
                call(gw, kids[0], big(400, scope=SCOPE_A_LEAF))
        finally:
            cleanup(rt, tmp)

    def test_zero_budget_is_representable_and_fails_safely(self):
        """19. A zero/empty budget is represented correctly and fails safely.
        Zero is a VALID ceiling, not an absent one -- and it denies everything."""
        rt, gw, prov, ledger, tmp = build()
        try:
            a = root_with_budget(rt, ledger, 0)
            self.assertEqual(ledger.root_for(a.trace_id).ceiling, 0)
            self.assertTrue(ledger.root_for(a.trace_id).exhausted)
            with self.assertRaises(Denied) as ctx:
                call(gw, a, big(1))
            self.assertEqual(ctx.exception.step, "budget.exhausted")
        finally:
            cleanup(rt, tmp)

    def test_execution_with_no_budget_denies_rather_than_running_unlimited(self):
        """I-105: EVERY execution carries a ceiling. An unbudgeted execution
        must not be treated as unlimited."""
        rt, gw, prov, ledger, tmp = build()
        try:
            from .harness2 import coordinator_token
            orphan = coordinator_token(rt)          # deliberately no open_root
            with self.assertRaises(Denied) as ctx:
                call(gw, orphan, big(10))
            self.assertEqual(ctx.exception.step, "budget.lookup")
            self.assertEqual(ctx.exception.invariant, "I-105")
        finally:
            cleanup(rt, tmp)


# ===========================================================================
# Finding 2 resolution still holds under budget accounting
# ===========================================================================
class Test10ProvenanceStillHolds(Slice3):
    def test_trust_and_provenance_remain_distinct_across_the_tree(self):
        b = delegate_b(self.rt, self.ledger, self.a, carve=5_000)
        c = delegate_c(self.rt, self.ledger, b, carve=1_000)
        stated = call(self.gw, c, big(50, scope=SCOPE_A_LEAF))
        self.assertEqual(stated.taint.trust, Trust.LOW)
        self.assertFalse(stated.taint.is_untrusted_derived())

        web = [ModelRequestItem(label="page", content="x" * 50, scope_path=SCOPE_A_LEAF,
                                taint=Taint.of("external.web", Classification.INTERNAL))]
        tainted = call(self.gw, c, web)
        self.assertTrue(tainted.taint.is_untrusted_derived())
        self.assertEqual(tainted.taint.trust, Trust.LOW)


if __name__ == "__main__":
    unittest.main()
