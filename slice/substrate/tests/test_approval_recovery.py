"""An interrupted execution is RESOLVED from evidence, never re-run.

Phase 1 made an approval single use. That closed replay and opened one gap:
an approval spent at the claim, on a process that then died before the write,
leaves the action undone. The approval is correctly unusable -- but nothing
said so, and nothing could tell that case apart from one where the write DID
land and the crash came after.

What makes the two distinguishable is a property of the write path rather
than anything added here: `write_path.transport` writes the row and its
`audit_record` entry in ONE transaction, so the audit row exists if and only
if the side effect committed. The missing piece was the KEY -- an event
identity derives from the token's `trace_id`, a uuid4 that lived only in
memory. `approval.execution_trace_id`, written in the same statement as the
claim, is what makes the identity rebuildable after a restart.

So recovery reads evidence and writes a terminal status:

    evidence present    -> executed    (never re-run)
    evidence absent     -> failed      (fresh human approval required)
    evidence unreadable -> unresolved  (untouched; "probably ran" is not a state)

WHAT RECOVERY CANNOT DO, asserted here rather than asserted in prose: execute,
retry, un-spend an approval, or see another scope. It reaches the write path
not at all, and everything it reads goes through the one scope-bound channel
its token opens -- so a global sweep is not merely absent, it is unbuildable
without the cross-scope read I-86 forbids.

Crashes are simulated by driving the real transaction boundaries and stopping
between them -- never by mocking the database, which would prove only that
the mock behaved.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_approval_recovery
"""

from __future__ import annotations

import os
import tempfile
import unittest

from .. import db
from ..approval_flow import (APPROVED, EXECUTED, EXECUTING, FAILED, PENDING,
                             ApprovalService)
from ..boundary import DataAccessBoundary
from ..seam import Seam
from ..write_path import (PostgresItemIntegration, WritePath, write_item_tool,
                          execution_event_identity, TOOL)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.context_service import ContextService
from ...core.policy import PolicyDecisionPoint
from ...core.scope_tree import ScopeTree
from ...core.store import StoreRegistry
from ...core.types import Denied, Risk
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

LIFE = "/life"
BUSINESS = "/business"
WEALTH = "/wealth"


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class ApprovalRecoveryTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()

        tree = ScopeTree()
        for path in (LIFE, BUSINESS, WEALTH):
            tree.add_scope(path, "domain")
            tree.james_grants("james", "write", "*", path, Risk.EXECUTE)
            tree.james_grants("james", "read", "*", path, Risk.READ)
        self.tree = tree

        tmp = tempfile.mkdtemp(prefix="nova-recovery-")
        self.context = ContextService(tree, secret=b"recovery-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(tree, vault, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=LIFE,
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

    def token(self, scope=LIFE, rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
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

    def strand(self, scope=LIFE, item_ref="it-1", body="hello", wrote=False):
        """A crash, reproduced at the real boundaries.

        The approval is proposed and CLAIMED exactly as `decide` claims it --
        same statement, same columns, same trace -- and then we stop. That is
        precisely the state a process leaves behind when it dies after the
        claim. `wrote=True` additionally commits the write and its audit row
        through the real transport, reproducing a crash AFTER the execution
        landed instead of before it.
        """
        token = self.token(scope)
        approval_id = self.approvals.propose(token, scope, item_ref, body)
        with self.boundary.open(token) as ch:
            ch.execute(
                "UPDATE approval SET status=%s, decided_at=now(), decided_by=%s,"
                " consumed_at=now(), execution_trace_id=%s"
                " WHERE approval_id=%s AND status=%s AND consumed_at IS NULL",
                (EXECUTING, "james", token.trace_id, approval_id, PENDING))
        if wrote:
            self.integration.transport_for(token, TOOL)(
                {"item_ref": item_ref, "body": body}, "unused-secret")
        return approval_id, token

    def status_of(self, approval_id):
        return self.sql("SELECT status FROM approval WHERE approval_id=%s",
                        (approval_id,))[0][0]

    # =======================================================================
    # 1-2 -- the key that makes recovery possible at all
    # =======================================================================

    def test_01_the_claim_persists_the_execution_trace(self):
        """Without this column the audit identity is unrecomputable after a
        restart, and every crash would be ambiguous."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", "hello")
        self.approvals.decide(token, approval_id, True, decided_by="james")
        stored = self.sql("SELECT execution_trace_id FROM approval"
                          " WHERE approval_id=%s", (approval_id,))[0][0]
        self.assertEqual(token.trace_id, stored)

    def test_02_the_audit_identity_rebuilds_from_stored_fields_alone(self):
        """The restart case: nothing in memory, only the row. The identity
        rebuilt from it must be the one the write actually recorded."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", "hello")
        self.approvals.decide(token, approval_id, True, decided_by="james")

        trace, scope, tool, ref = self.sql(
            "SELECT execution_trace_id, scope_path, tool_name, item_ref"
            " FROM approval WHERE approval_id=%s", (approval_id,))[0]
        rebuilt = execution_event_identity(trace, scope, tool, ref)
        self.assertEqual(
            [(rebuilt,)],
            self.sql("SELECT event_identity FROM audit_record"
                     " WHERE category='data.write'"),
            "the rebuilt identity does not match what the write recorded")

    # =======================================================================
    # 3-5 -- the two decidable crash outcomes, and the terminal happy path
    # =======================================================================

    def test_03_a_completed_execution_settles_as_executed(self):
        """No crash: the ordinary path ends terminal, not in flight."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", "hello")
        status, outcome = self.approvals.decide(token, approval_id, True,
                                                decided_by="james")
        self.assertEqual(APPROVED, status)          # the DECISION
        self.assertIsNotNone(outcome)
        self.assertEqual(EXECUTED, self.status_of(approval_id))
        self.assertEqual([], self.approvals.recover(self.token()),
                         "a settled approval was still treated as in flight")

    def test_04_a_write_that_committed_is_reconciled_as_executed(self):
        """Crash AFTER the write. Evidence exists, so the action happened --
        recovery records that and must not run it again."""
        approval_id, _ = self.strand(wrote=True)
        self.assertEqual(EXECUTING, self.status_of(approval_id))
        before = self.sql("SELECT count(*) FROM item")[0][0]

        self.assertEqual([(approval_id, EXECUTED)],
                         self.approvals.recover(self.token()))
        self.assertEqual(EXECUTED, self.status_of(approval_id))
        self.assertEqual(before, self.sql("SELECT count(*) FROM item")[0][0],
                         "recovery executed the action")

    def test_05_a_write_that_never_committed_is_reconciled_as_failed(self):
        """Crash BEFORE the write. No evidence, so the action did not happen
        -- and recovery still must not run it. A fresh decision is required."""
        approval_id, _ = self.strand(wrote=False)

        self.assertEqual([(approval_id, FAILED)],
                         self.approvals.recover(self.token()))
        self.assertEqual(FAILED, self.status_of(approval_id))
        self.assertEqual([], self.sql("SELECT 1 FROM item"),
                         "recovery executed the action")

    # =======================================================================
    # 6-8 -- what recovery must never become
    # =======================================================================

    def test_06_recovery_never_retries_and_never_un_spends_an_approval(self):
        """The failure mode this whole design exists to avoid: an approval
        that survives its own failure as a retry token."""
        approval_id, _ = self.strand(wrote=False)
        self.approvals.recover(self.token())

        self.assertIsNotNone(
            self.sql("SELECT consumed_at FROM approval WHERE approval_id=%s",
                     (approval_id,))[0][0],
            "recovery cleared consumed_at")
        # Running it again changes nothing: the row is terminal.
        self.assertEqual([], self.approvals.recover(self.token()))
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

    def test_07_a_failed_approval_requires_a_fresh_human_decision(self):
        """And the fresh decision works -- recovery closes the door without
        wedging the action shut."""
        approval_id, _ = self.strand(wrote=False)
        self.approvals.recover(self.token())

        with self.assertRaises(Denied):
            self.approvals.decide(self.token(), approval_id, True,
                                  decided_by="james")
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

        token = self.token()
        fresh = self.approvals.propose(token, LIFE, "it-1", "hello")
        self.approvals.decide(token, fresh, True, decided_by="james")
        self.assertEqual([("it-1", "hello")],
                         self.sql("SELECT item_ref, body FROM item"))

    def test_08_a_tampered_plan_cannot_be_reconciled(self):
        """I-109 / I-112 hold in recovery too. If the row no longer describes
        the action it was approved for, we cannot say what its evidence would
        look like -- so it is left alone rather than guessed at."""
        approval_id, _ = self.strand(wrote=True)
        self.sql("UPDATE approval SET body='something else'"
                 " WHERE approval_id=%s", (approval_id,))

        self.assertEqual([(approval_id, "unresolved")],
                         self.approvals.recover(self.token()))
        self.assertEqual(EXECUTING, self.status_of(approval_id),
                         "a tampered approval was reconciled anyway")

    def test_09_a_missing_execution_trace_fails_closed(self):
        """A row claimed before this column existed. The identity cannot be
        rebuilt honestly, so the answer is 'unknown', not a guess."""
        approval_id, _ = self.strand(wrote=True)
        self.sql("UPDATE approval SET execution_trace_id=NULL"
                 " WHERE approval_id=%s", (approval_id,))

        self.assertEqual([(approval_id, "unresolved")],
                         self.approvals.recover(self.token()))
        self.assertEqual(EXECUTING, self.status_of(approval_id))

    def test_10_unreadable_evidence_leaves_the_approval_untouched(self):
        """The database itself unavailable. Recovery must fail closed -- no
        terminal status invented, no action taken."""
        approval_id, _ = self.strand(wrote=True)
        self.boundary.close()
        with self.assertRaises(Exception):
            self.approvals.recover(self.token())
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)
        self.approvals = ApprovalService(self.boundary, self.writes)
        self.assertEqual(EXECUTING, self.status_of(approval_id),
                         "an unreadable evidence store still moved the row")

    # =======================================================================
    # 11 -- scope isolation, in recovery as everywhere else
    # =======================================================================

    def test_11_recovery_in_life_cannot_see_business_or_wealth(self):
        """I-03 / I-86. Three areas each hold a stranded approval; recovering
        /life reconciles exactly one. There is no sweep, and RLS is why."""
        life_id, _ = self.strand(LIFE, "it-life", "life body")
        business_id, _ = self.strand(BUSINESS, "it-business", "business body")
        wealth_id, _ = self.strand(WEALTH, "it-wealth", "wealth body")

        settled = self.approvals.recover(self.token(LIFE))
        self.assertEqual([life_id], [a for a, _ in settled],
                         "recovery reached outside its bound scope")
        self.assertEqual(EXECUTING, self.status_of(business_id))
        self.assertEqual(EXECUTING, self.status_of(wealth_id))

    # =======================================================================
    # 12 -- concurrency, forced rather than hoped for
    # =======================================================================

    def test_12_concurrent_recovery_cannot_settle_the_same_approval_twice(self):
        """Two recovery workers, one stranded approval, the read/write window
        held open deliberately.

        The interleaving is forced the way Phase 1 forces it: the window that
        matters is between reading `status='executing'` and writing the
        terminal status, so the barrier goes there -- inside the fetch -- and
        not at the entry to `recover`, which would prove nothing. Every worker
        therefore sees the row as in-flight before any worker settles it,
        which is exactly the condition a read-then-write implementation loses.
        """
        import threading

        approval_id, _ = self.strand(wrote=True)

        looked = threading.Barrier(2)
        real_recover = ApprovalService.recover

        def recover_with_forced_overlap(service, token):
            # Hold every worker at the point where it has SELECTed the
            # in-flight rows, until all of them have.
            from ..boundary import ScopedChannel
            real_fetch = ScopedChannel.fetch
            seen = {"held": False}

            def fetch(ch, sql, params=()):
                rows = real_fetch(ch, sql, params)
                if not seen["held"] and "FROM approval" in sql and "status" in sql:
                    seen["held"] = True
                    try:
                        looked.wait(timeout=20)
                    except threading.BrokenBarrierError:
                        pass
                return rows

            ScopedChannel.fetch = fetch
            try:
                return real_recover(service, token)
            finally:
                ScopedChannel.fetch = real_fetch

        outcomes: list[object] = []
        lock = threading.Lock()

        def worker():
            try:
                result = recover_with_forced_overlap(self.approvals, self.token())
            except Exception as exc:
                result = exc
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(2, len(outcomes), "a recovery worker did not finish")
        settled_executed = [o for o in outcomes
                            if isinstance(o, list) and (approval_id, EXECUTED) in o]
        self.assertEqual(1, len(settled_executed),
                         f"expected exactly one worker to settle it, got {outcomes}")
        self.assertEqual(EXECUTED, self.status_of(approval_id))
        self.assertEqual(1, self.sql("SELECT count(*) FROM item")[0][0],
                         "concurrent recovery produced a duplicate side effect")

    # =======================================================================
    # 13-14 -- Phase 1's guarantees, still standing
    # =======================================================================

    def test_13_a_consumed_approval_is_still_unusable(self):
        approval_id, _ = self.strand(wrote=True)
        self.approvals.recover(self.token())
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(), approval_id, True,
                                  decided_by="james")
        self.assertIn(cm.exception.invariant, ("I-09", "I-03"))

    def test_14_event_identity_remains_unique(self):
        """I-93 unchanged: recovery reads identities, it never writes one."""
        self.strand(wrote=True)
        self.approvals.recover(self.token())
        total, distinct = self.sql(
            "SELECT count(*), count(DISTINCT event_identity) FROM audit_record")[0]
        self.assertGreater(total, 0)
        self.assertEqual(total, distinct)

    # =======================================================================
    # 15-18 -- scope entry actually runs it
    # =======================================================================

    def test_15_entering_a_scopes_approvals_runs_recovery_for_that_scope(self):
        """The wiring, proven by effect rather than by inspection: a stranded
        approval is still in flight before the page is opened and terminal
        after, with no other call in between.

        `approvals_page` and not the scope page: reconciling WRITES to the
        approval, and this route already holds a write-capable token from an
        EXECUTE-strength session. The scope page holds a read token.
        """
        approval_id, _ = self.strand(LIFE, "it-1", "hello", wrote=True)
        self.assertEqual(EXECUTING, self.status_of(approval_id))

        status, _ = self.seam.approvals_page(self.sid, LIFE)

        self.assertEqual(200, status)
        self.assertEqual(EXECUTED, self.status_of(approval_id),
                         "scope entry did not run recovery")

    def test_16_entering_life_cannot_reconcile_business_or_wealth(self):
        """I-03 / I-86 through the real route. Three areas stranded, one
        entered, one reconciled."""
        life_id, _ = self.strand(LIFE, "it-life", "life", wrote=True)
        business_id, _ = self.strand(BUSINESS, "it-business", "business", wrote=True)
        wealth_id, _ = self.strand(WEALTH, "it-wealth", "wealth", wrote=True)

        self.assertEqual(200, self.seam.approvals_page(self.sid, LIFE)[0])

        self.assertEqual(EXECUTED, self.status_of(life_id))
        self.assertEqual(EXECUTING, self.status_of(business_id),
                         "entering /life reconciled /business")
        self.assertEqual(EXECUTING, self.status_of(wealth_id),
                         "entering /life reconciled /wealth")

    def test_17_scope_entry_never_executes_the_stranded_action(self):
        """The one thing recovery must never become. Entering the page twice
        -- evidence absent -- still writes nothing, and the approval stays
        spent rather than becoming a retry."""
        approval_id, _ = self.strand(LIFE, "it-1", "hello", wrote=False)

        self.seam.approvals_page(self.sid, LIFE)
        self.seam.approvals_page(self.sid, LIFE)

        self.assertEqual(FAILED, self.status_of(approval_id))
        self.assertEqual([], self.sql("SELECT 1 FROM item"),
                         "scope entry executed the stranded action")
        self.assertIsNotNone(
            self.sql("SELECT consumed_at FROM approval WHERE approval_id=%s",
                     (approval_id,))[0][0],
            "recovery cleared consumed_at")
        # And it is genuinely finished: a fresh decision is the only way on.
        with self.assertRaises(Denied):
            self.approvals.decide(self.token(), approval_id, True,
                                  decided_by="james")

    def test_18_an_unresolved_approval_survives_scope_entry_untouched(self):
        """A row whose plan no longer matches cannot be reconciled, and the
        page must not quietly resolve it anyway."""
        approval_id, _ = self.strand(LIFE, "it-1", "hello", wrote=True)
        self.sql("UPDATE approval SET body='something else'"
                 " WHERE approval_id=%s", (approval_id,))

        self.assertEqual(200, self.seam.approvals_page(self.sid, LIFE)[0])
        self.assertEqual(EXECUTING, self.status_of(approval_id))

    def test_19_scope_entry_is_unchanged_when_nothing_is_stranded(self):
        """The ordinary case: no in-flight approvals, page behaves exactly as
        before, and a genuinely pending approval is still offered."""
        self.assertEqual(200, self.seam.approvals_page(self.sid, LIFE)[0])

        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", "hello")
        status, page = self.seam.approvals_page(self.sid, LIFE)
        self.assertEqual(200, status)
        self.assertIn(approval_id, page, "a pending approval stopped being offered")
        self.assertEqual(PENDING, self.status_of(approval_id),
                         "recovery touched a pending approval")


if __name__ == "__main__":
    unittest.main()
