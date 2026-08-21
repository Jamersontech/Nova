"""An approval authorizes ONE execution, and then it is spent.

The defect this suite exists for: a plan's identity is deterministic over
(scope, tool, arguments), so the SAME identity is re-derived every time the
same action is requested. `ApprovalStore` recorded approvals by that identity
and never expired them, and `Seam.write_item` reaches `execute_action`
directly. So after James approved writing `it-1` in a scope, ANY later call
with those same arguments -- in the same process, through the direct write
route, with no new human act -- found the approval still sitting there and
satisfied PDP step 9 with it.

Process restart cleared it, which meant restarting NOVA was the only thing
enforcing single use. That is not an enforcement mechanism.

The claim now:

    once an approval has authorized an execution, it can never authorize
    another one -- not the same plan, not a different plan, not from another
    scope, not after a restart, and not through a different route

Enforced in two places that cannot disagree: `approval.consumed_at` is the
durable record, claimed by a single atomic `UPDATE ... WHERE consumed_at IS
NULL ... RETURNING` so concurrent decisions cannot both win; and
`ApprovalStore.consume` spends the identity at the object the PDP actually
reads. Every denial below comes from the ordinary ten steps -- step 9 with no
approval -- not from a special case bolted on for replay.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_approval_single_use
"""

from __future__ import annotations

import os
import tempfile
import unittest

from .. import db
from ..approval_flow import APPROVED, DENIED, PENDING, ApprovalService
from ..boundary import DataAccessBoundary
from ..seam import Seam
from ..write_path import (PostgresItemIntegration, WritePath, write_item_tool,
                          TOOL)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.context_service import ContextService
from ...core.policy import PolicyDecisionPoint
from ...core.store import StoreRegistry
from ...core.scope_tree import ScopeTree
from ...core.types import Denied, Risk
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class ApprovalSingleUseTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()

        tree = ScopeTree()
        tree.add_scope("/business", "domain")
        tree.add_scope("/business/KAIRO", "business")
        tree.add_scope(A, "client")
        tree.add_scope(B, "client")
        for scope in (A, B):
            tree.james_grants("james", "write", "*", scope, Risk.EXECUTE)
            tree.james_grants("james", "read", "*", scope, Risk.READ)

        tmp = tempfile.mkdtemp(prefix="nova-single-use-")
        self.context = ContextService(tree, secret=b"single-use-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(tree, vault, audit)
        # One binding, scope A -- as `test_write_path` wires it. B deliberately
        # has none: a write there must be refused by step 9 (no approval)
        # BEFORE any binding is resolved, which is itself worth asserting.
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=A,
                              permitted_operations=frozenset({TOOL})),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        registry.register(write_item_tool())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")
        self.approvals = ApprovalService(self.boundary, self.writes)

        self.auth = authfixture.service()
        self.sid = authfixture.sign_in(
            self.auth, authfixture.enrol(self.auth, "james", "james"))
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, scope=A, rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=rights,
                                       ceiling=ceiling, ttl=60)

    def sql(self, query, args=()):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, args or None)
            rows = cur.fetchall() if cur.description else []
        conn.close()
        return rows

    def propose_and_approve(self, scope=A, item_ref="it-1", body="hello"):
        """The whole legitimate path: propose, then James decides."""
        token = self.token(scope)
        approval_id = self.approvals.propose(token, scope, item_ref, body)
        status, outcome = self.approvals.decide(token, approval_id, True,
                                                decided_by="james")
        return approval_id, status, outcome

    # =======================================================================
    # 1-2 -- the approval works exactly once, and is then spent
    # =======================================================================

    def test_01_an_approval_authorizes_its_intended_plan(self):
        """The control. If this fails, the rest proves only that nothing works."""
        _, status, outcome = self.propose_and_approve()
        self.assertEqual(APPROVED, status)
        self.assertIsNotNone(outcome)
        self.assertEqual([("it-1", "hello")],
                         self.sql("SELECT item_ref, body FROM item"))

    def test_02_the_approval_is_consumed_by_the_execution(self):
        """Durably, in the same statement that recorded the decision."""
        approval_id, _, _ = self.propose_and_approve()
        rows = self.sql("SELECT status, consumed_at IS NOT NULL FROM approval"
                        " WHERE approval_id=%s", (approval_id,))
        self.assertEqual([(APPROVED, True)], rows)

    # =======================================================================
    # 3-4 -- the replay, by both routes
    # =======================================================================

    def test_03_the_same_plan_cannot_reuse_the_approval(self):
        """The identical action, re-requested through the write path. The
        plan identity is the same by construction -- that is the whole
        problem -- and it must no longer find an approval."""
        self.propose_and_approve()
        with self.assertRaises(Denied) as cm:
            self.writes.execute(self.token(), A, "it-1", "hello")
        self.assertEqual("I-09", cm.exception.invariant,
                         "the denial did not come from step 9")
        self.assertEqual([("it-1", "hello")],
                         self.sql("SELECT item_ref, body FROM item"),
                         "a second write landed")

    def test_04_the_direct_write_route_cannot_ride_a_spent_approval(self):
        """seam.write_item -- the route that made this exploitable. Same
        session, same scope, same arguments, no new approval."""
        self.propose_and_approve()
        before = self.sql("SELECT count(*) FROM item")[0][0]

        status, page = self.seam.write_item(self.sid, A, "it-1", "hello")

        self.assertEqual(403, status)
        self.assertIn("Approval required", page)
        self.assertEqual(before, self.sql("SELECT count(*) FROM item")[0][0],
                         "the direct write route produced a second write")
        self.assertEqual(1, self.sql("SELECT count(*) FROM approval")[0][0],
                         "a replay silently created another approval")

    # =======================================================================
    # 5-6 -- a spent approval covers nothing else either
    # =======================================================================

    def test_05_a_different_plan_cannot_use_the_consumed_approval(self):
        """I-112 already made a different plan a different identity; this
        asserts consumption did not accidentally widen anything."""
        self.propose_and_approve()
        with self.assertRaises(Denied) as cm:
            self.writes.execute(self.token(), A, "it-2", "something else")
        self.assertEqual("I-09", cm.exception.invariant)
        self.assertEqual([("it-1",)], self.sql("SELECT item_ref FROM item"))

    def test_06_another_scope_cannot_use_the_approval(self):
        """The same arguments in a sibling scope are a different plan (the
        scope is in the identity) AND unreachable by RLS. Both must hold."""
        self.propose_and_approve()
        with self.assertRaises(Denied) as cm:
            self.writes.execute(self.token(B), B, "it-1", "hello")
        self.assertEqual("I-09", cm.exception.invariant)
        self.assertEqual([(A,)], self.sql("SELECT scope_path FROM item"))

    def test_07_deciding_the_same_approval_twice_is_refused(self):
        """The durable claim, exercised directly: the second decision finds
        the row no longer PENDING and no longer unspent."""
        approval_id, _, _ = self.propose_and_approve()
        with self.assertRaises(Denied):
            self.approvals.decide(self.token(), approval_id, True,
                                  decided_by="james")
        self.assertEqual(1, self.sql("SELECT count(*) FROM item")[0][0])

    # =======================================================================
    # 8-10 -- nothing that already worked stopped working
    # =======================================================================

    def test_08_plan_reconstruction_still_binds_the_decision(self):
        """I-109 / I-112 unchanged: editing the stored request after James
        saw it still fails the identity comparison, and now cannot even
        reach execution."""
        token = self.token()
        approval_id = self.approvals.propose(token, A, "it-1", "hello")
        self.sql("UPDATE approval SET body='something else'"
                 " WHERE approval_id=%s", (approval_id,))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.assertEqual([(None,)],
                         self.sql("SELECT consumed_at FROM approval"
                                  " WHERE approval_id=%s", (approval_id,)),
                         "a rejected decision spent the approval")

    def test_09_denial_still_produces_no_side_effect_and_no_consumption(self):
        """A denied approval executes nothing. It is also not 'spent': there
        was no execution to spend it on, and the row is terminal by status."""
        token = self.token()
        approval_id = self.approvals.propose(token, A, "it-1", "hello")
        status, outcome = self.approvals.decide(token, approval_id, False,
                                                decided_by="james")
        self.assertEqual(DENIED, status)
        self.assertIsNone(outcome)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.assertEqual([(DENIED, None)],
                         self.sql("SELECT status, consumed_at FROM approval"
                                  " WHERE approval_id=%s", (approval_id,)))

    def test_10_an_unapproved_plan_is_still_denied_by_step_nine(self):
        """The baseline I-09 behaviour, unchanged by any of this."""
        with self.assertRaises(Denied) as cm:
            self.writes.execute(self.token(), A, "fresh", "never approved")
        self.assertEqual("I-09", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

    def test_11_pending_still_lists_only_undecided_approvals(self):
        """A consumed approval must not be re-offered for decision."""
        token = self.token()
        self.approvals.propose(token, A, "it-9", "still waiting")
        approval_id, _, _ = self.propose_and_approve()
        refs = [r.approval_id for r in self.approvals.pending(token)]
        self.assertNotIn(approval_id, refs)
        self.assertEqual(1, len(refs))

    def test_12_audit_event_identity_behaviour_is_unchanged(self):
        """I-93: the execution still writes its audit records, and they are
        still unique by event identity."""
        self.propose_and_approve()
        total, distinct = self.sql(
            "SELECT count(*), count(DISTINCT event_identity) FROM audit_record")[0]
        self.assertGreater(total, 0, "the execution wrote no audit record")
        self.assertEqual(total, distinct, "event identity is no longer unique")

    # =======================================================================
    # 13 -- concurrency: two decisions, one execution
    # =======================================================================

    def test_13_two_concurrent_decisions_cannot_both_execute(self):
        """The race the durable claim exists for. Two threads decide the same
        approval at once; PostgreSQL admits exactly one UPDATE, so exactly one
        execution happens. Serialised by the database, not by our timing."""
        import threading

        token = self.token()
        approval_id = self.approvals.propose(token, A, "it-race", "once only")

        barrier = threading.Barrier(2)
        results: list[object] = []
        lock = threading.Lock()

        def decide():
            barrier.wait()
            try:
                # Each thread issues its own token: a ContextToken is not a
                # thread-shared object and sharing one would test the wrong thing.
                t = self.token()
                outcome = self.approvals.decide(t, approval_id, True,
                                                decided_by="james")
            except Exception as exc:      # Denied, or a serialisation failure
                outcome = exc
            with lock:
                results.append(outcome)

        threads = [threading.Thread(target=decide) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(2, len(results), "a decision thread did not finish")
        succeeded = [r for r in results if not isinstance(r, Exception)]
        self.assertEqual(1, len(succeeded),
                         f"expected exactly one winner, got {results}")
        self.assertEqual(1, self.sql("SELECT count(*) FROM item"
                                     " WHERE item_ref='it-race'")[0][0],
                         "the same approval executed twice")


    def test_14_concurrent_direct_writes_cannot_share_one_approval(self):
        """The race that a look-then-spend pair actually lost.

        Four threads reach `execute_action` with the SAME plan and one
        approval between them. The window between obtaining the approval and
        spending it is deliberately widened here, because that window is the
        bug: with a separate `for_plan` + `consume` this returned FOUR
        executions from one approval, and passed only because the scheduler
        happened to be kind. `take` closes it -- `dict.pop` is atomic, so
        exactly one caller receives the approval and the rest are denied by
        step 9.

        WHERE THE FORCING HAS TO GO. Synchronising at the ENTRY to `take` is
        not enough: released together, a look-then-spend pair still completes
        too fast to interleave, and a racy implementation passes. Measured --
        an entry barrier missed the defect three times out of three. The
        window that has to be held open is the one BETWEEN the look and the
        spend, so the instrumentation goes on the store's mapping: every
        concurrent `get` must return before any caller may act on what it got.

        An implementation that only ever calls `pop` never touches that
        barrier and is unaffected. One that looks first is caught, every time
        and without a sleep -- so this test also adds no wall-clock load to
        the suite, which a sleep-based version measurably did.
        """
        import threading

        class InterleavingMap(dict):
            """Test instrumentation. Holds every concurrent `get` until all of
            them have happened, which is exactly the interleaving a
            look-then-spend implementation must survive and cannot."""

            def __init__(self, source, parties):
                super().__init__(source)
                self._looked = threading.Barrier(parties)

            def get(self, key, default=None):
                value = super().get(key, default)
                try:
                    self._looked.wait(timeout=10)
                except threading.BrokenBarrierError:
                    pass          # fewer lookers than parties: nothing to force
                return value

        plan = self.writes.plan_for(A, "it-race-2", "once only")
        self.writes.approvals.james_approves(plan.identity())
        store = self.writes.approvals
        store._by_plan = InterleavingMap(store._by_plan, 4)

        barrier = threading.Barrier(4)
        outcomes: list[object] = []
        lock = threading.Lock()

        def attempt():
            barrier.wait()
            try:
                result = self.writes.execute(self.token(), A, "it-race-2", "once only")
            except Exception as exc:
                result = exc
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=attempt) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(4, len(outcomes), "an attempting thread did not finish")
        succeeded = [o for o in outcomes if not isinstance(o, Exception)]
        self.assertEqual(1, len(succeeded),
                         f"{len(succeeded)} executions from ONE approval")
        for denial in (o for o in outcomes if isinstance(o, Denied)):
            self.assertEqual("I-09", denial.invariant,
                             "a loser was denied by something other than step 9")
        self.assertEqual(1, self.sql("SELECT count(*) FROM item"
                                     " WHERE item_ref='it-race-2'")[0][0])


if __name__ == "__main__":
    unittest.main()
