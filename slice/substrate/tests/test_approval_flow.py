"""The approval experience, end to end, against real PostgreSQL.

James sees what an action will do and decides. This suite proves the decision
is REAL -- that it is his alone, that it is bound to one exact action, and
that granting it authorizes nothing by itself.

Every control is shown load-bearing by a negative:

  the approver identity -- the assistant's session cannot decide (I-09)
  the plan binding      -- an approval edited after the fact cannot execute
                           (I-109, I-112)
  the scope             -- an approval in the sibling scope is unreachable
                           (I-03, RLS)
  the PDP               -- consulted AFTER approval, and fails closed
  the denial            -- produces no side effect at all

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_approval_flow
"""

from __future__ import annotations

import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

from .. import db
from ..approval_flow import (APPROVED, DENIED, EXECUTED, PENDING,
                             ApprovalService)
from ..boundary import DataAccessBoundary
from ..seam import Seam, serve
from . import authfixture
from ..write_path import (PostgresItemIntegration, WritePath, write_item_tool,
                          TOOL)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.context_service import ContextService
from ...core.policy import PolicyDecisionPoint
from ...core.scope_tree import ScopeTree
from ...core.store import StoreRegistry
from ...core.types import Denied, Risk
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry

A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class ApprovalFlowTest(unittest.TestCase):

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
        # James may act in BOTH client scopes. The isolation tests below must
        # fail on scope containment, not on a missing grant -- otherwise they
        # would prove the grant check and say nothing about RLS.
        for scope in (A, B):
            tree.james_grants("james", "write", "*", scope, Risk.EXECUTE)
            tree.james_grants("james", "read", "*", scope, Risk.READ)

        tmp = tempfile.mkdtemp(prefix="nova-approval-")
        self.context = ContextService(tree, secret=b"approval-flow-test-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(tree, vault, audit)
        for scope in (A, B):
            broker.register(
                CredentialBinding(binding_id=f"db-item-write{scope}", scope_path=scope,
                                  permitted_operations=frozenset({TOOL})),
                secret="integration-credential-" + os.urandom(4).hex(),
            )

        registry = ToolRegistry()
        registry.register(write_item_tool())
        pep = ToolPEP(registry, broker, self.context, audit)

        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, f"db-item-write{A}")
        self.approvals = ApprovalService(self.boundary, self.writes)

        # A second wiring for scope B. The credential binding is per-scope
        # (I-62), so acting in B is a different binding, not a wider one.
        self.writes_b = WritePath(self.pdp, registry, pep, broker,
                                  self.integration, f"db-item-write{B}")
        self.approvals_b = ApprovalService(self.boundary, self.writes_b)

        self.auth = authfixture.service()
        self.james_key = authfixture.enrol(self.auth, "james", "james")
        self.james_sid = authfixture.sign_in(self.auth, self.james_key)
        self.assistant_sid = authfixture.sign_in(
            self.auth, authfixture.enrol(self.auth, "assistant", "assistant"))
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, scope=A, ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=frozenset({"write"}),
                                       ceiling=ceiling, ttl=60)

    def propose(self, scope=A, item_ref="it-1", body="hello") -> str:
        return self.approvals.propose(self.token(scope), scope, item_ref, body)

    def rows(self, scope=None):
        """Read items OUT OF BAND, as the superuser -- the suite must not
        depend on the mechanism it is testing to observe the result."""
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            if scope:
                cur.execute("SELECT item_ref, body FROM item WHERE scope_path=%s"
                            " ORDER BY item_ref", (scope,))
            else:
                cur.execute("SELECT item_ref, scope_path, body FROM item ORDER BY item_ref")
            out = cur.fetchall()
        conn.close()
        return out

    def approval_row(self, approval_id):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT status, decided_by, decided_at, scope_path, plan_identity"
                        " FROM approval WHERE approval_id=%s", (approval_id,))
            row = cur.fetchone()
        conn.close()
        return row

    def http(self, method, path, sid=None, form=None):
        data = urllib.parse.urlencode(form or {}).encode() if method == "POST" else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data, method=method)
        if sid:
            req.add_header("Cookie", f"nova_session={sid}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    # -- 1. the pending approval is presented -------------------------------

    def test_1_pending_approval_states_the_five_things(self):
        """USER_INTERFACE_ARCHITECTURE section 6: what will happen, in which
        scope, why approval is needed, what it costs, what happens if wrong."""
        self.propose()
        status, page = self.seam.approvals_page(self.james_sid, A)
        self.assertEqual(200, status)
        for required in ("Write item", A, "why approval is needed",
                         "what it costs", "if this is wrong"):
            self.assertIn(required, page)
        # And the statement that NOVA is not the authority.
        self.assertIn("it cannot approve it", page)
        self.assertIn("EXECUTE", page)

    def test_1b_the_page_carries_no_token_or_credential_material(self):
        self.propose()
        _, page = self.seam.approvals_page(self.james_sid, A)
        for marker in ("integrity", "trace_id", "set_config", "nova_app",
                       "integration-credential", "plan_identity"):
            self.assertNotIn(marker, page.lower())

    def test_1c_proposing_writes_nothing_but_the_request(self):
        """A proposal is not an action. Nothing lands until James decides."""
        self.propose()
        self.assertEqual([], self.rows())
        self.assertEqual(0, self.integration.side_effects)

    # -- 2. only James decides (I-09) ---------------------------------------

    def test_2_the_assistants_session_cannot_approve(self):
        approval_id = self.propose()
        status, page = self.seam.decide_page(self.assistant_sid, A, approval_id, True)
        self.assertEqual(403, status)
        self.assertIn("Only James", page)
        self.assertEqual(PENDING, self.approval_row(approval_id)[0])
        self.assertEqual([], self.rows(), "the assistant produced a side effect")

    def test_2b_an_unauthenticated_request_cannot_approve(self):
        approval_id = self.propose()
        status, _ = self.seam.decide_page(None, A, approval_id, True)
        self.assertEqual(401, status)
        self.assertEqual(PENDING, self.approval_row(approval_id)[0])
        self.assertEqual([], self.rows())

    def test_2c_the_browser_cannot_assert_who_is_deciding(self):
        """The approver is read from the server-side session. A request that
        claims to be James over the assistant's session is still the
        assistant -- the handler never reads an identity from the form."""
        approval_id = self.propose()
        self.server, self.port = serve(self.seam)
        try:
            status, page = self.http(
                "POST", f"/scope{A}/approvals/{approval_id}",
                sid=self.assistant_sid,
                form={"decision": "approve", "decided_by": "james",
                      "identity": "james", "approver": "james"})
            self.assertEqual(403, status)
            self.assertIn("Only James", page)
        finally:
            self.server.shutdown()
        self.assertEqual(PENDING, self.approval_row(approval_id)[0])
        self.assertEqual([], self.rows())

    # -- 3. the approval is bound to ONE action (I-109, I-112) --------------

    def test_3_approving_one_request_does_not_execute_another(self):
        first = self.propose(item_ref="it-1", body="hello")
        self.propose(item_ref="it-2", body="other")
        status, _ = self.seam.decide_page(self.james_sid, A, first, True)
        self.assertEqual(200, status)
        self.assertEqual([("it-1", "hello")], self.rows(A),
                         "a request James did not approve was executed")

    def test_3b_a_request_edited_after_approval_cannot_execute(self):
        """THE binding test. The stored arguments are swapped underneath the
        approval -- as a compromised handler or a tampered row would. The plan
        is reconstructed at execution and no longer hashes to what James saw,
        so it does not run."""
        import psycopg2
        approval_id = self.propose(item_ref="it-1", body="hello")
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("UPDATE approval SET item_ref='it-evil', body='HOSTILE'"
                        " WHERE approval_id=%s", (approval_id,))
        conn.close()

        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.rows(), "a substituted action executed")
        self.assertEqual(PENDING, self.approval_row(approval_id)[0])

    def test_3c_an_approval_cannot_be_decided_twice(self):
        approval_id = self.propose()
        self.seam.decide_page(self.james_sid, A, approval_id, True)
        status, _ = self.seam.decide_page(self.james_sid, A, approval_id, True)
        self.assertEqual(409, status)
        self.assertEqual([("it-1", "hello")], self.rows(A))

    # -- 4. an approval cannot widen scope (I-03) ---------------------------

    def test_4_an_approval_in_the_sibling_scope_is_unreachable(self):
        """James is granted in BOTH scopes, so nothing here turns on a grant.
        A channel bound to A cannot see -- or decide -- B's approval."""
        approval_id = self.propose(scope=B, item_ref="it-b", body="b body")
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(A), approval_id, True, decided_by="james")
        self.assertEqual("I-03", cm.exception.invariant)
        self.assertEqual(PENDING, self.approval_row(approval_id)[0])
        self.assertEqual([], self.rows())

        # And the page bound to A never lists it.
        _, page = self.seam.approvals_page(self.james_sid, A)
        self.assertNotIn("it-b", page)
        self.assertIn("Nothing needs your decision", page)

    def test_4b_deciding_in_scope_b_writes_only_in_scope_b(self):
        """The positive half of the isolation claim: B's approval, decided
        from B, lands in B and nowhere else."""
        approval_id = self.approvals_b.propose(self.token(B), B, "it-b", "b body")
        status, _ = self.approvals_b.decide(self.token(B), approval_id, True,
                                            decided_by="james")
        self.assertEqual(APPROVED, status)
        self.assertEqual([("it-b", "b body")], self.rows(B))
        self.assertEqual([], self.rows(A), "the write leaked into the sibling scope")

    # -- 5. approval is an INPUT to the PDP, not a substitute ---------------

    def test_5_an_approved_action_still_faces_the_risk_ceiling(self):
        """I-101. The approval exists and is James's; the token cannot carry
        EXECUTE. The PDP denies anyway -- approval did not bypass it."""
        approval_id = self.propose()
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(A, ceiling=Risk.READ), approval_id,
                                  True, decided_by="james")
        self.assertEqual("I-101", cm.exception.invariant)
        self.assertEqual([], self.rows(), "approval bypassed the PDP")

    def test_6_pdp_unavailable_fails_closed_even_with_approval(self):
        """I-17. The identical approved action succeeds once the PDP is back,
        so the denial is the PDP's absence and not a defect in the fixture."""
        approval_id = self.propose()
        self.pdp.available = False
        try:
            with self.assertRaises(Denied):
                self.approvals.decide(self.token(), approval_id, True, decided_by="james")
            self.assertEqual([], self.rows())
        finally:
            self.pdp.available = True

        second = self.propose(item_ref="it-2", body="second")
        status, _ = self.approvals.decide(self.token(), second, True, decided_by="james")
        self.assertEqual(APPROVED, status)
        self.assertEqual([("it-2", "second")], self.rows(A))

    # -- 7. a denial does nothing -------------------------------------------

    def test_7_a_denied_approval_produces_no_side_effect(self):
        approval_id = self.propose()
        status, page = self.seam.decide_page(self.james_sid, A, approval_id, False)
        self.assertEqual(200, status)
        self.assertIn("Nothing was done", page)
        self.assertEqual([], self.rows())
        self.assertEqual(0, self.integration.side_effects)

        row = self.approval_row(approval_id)
        self.assertEqual(DENIED, row[0])
        self.assertEqual("james", row[1])
        self.assertIsNotNone(row[2], "the decision was not timestamped")

        # A denied request cannot then be executed by the write path: the
        # denial never created an approval for the plan.
        with self.assertRaises(Denied) as cm:
            self.writes.execute(self.token(), A, "it-1", "hello")
        self.assertEqual("I-09", cm.exception.invariant)

    # -- 8. an approval produces EXACTLY the approved side effect -----------

    def test_8_the_approved_action_is_the_one_that_happens(self):
        approval_id = self.propose(item_ref="it-1", body="hello")
        status, page = self.seam.decide_page(self.james_sid, A, approval_id, True)
        self.assertEqual(200, status)
        self.assertIn("wrote it-1", page)
        self.assertEqual([("it-1", "hello")], self.rows(A))
        self.assertEqual(1, self.integration.side_effects,
                         "more than the approved action ran")

        row = self.approval_row(approval_id)
        # EXECUTED: a completed execution is terminal (Phase 2 lifecycle).
        self.assertEqual(EXECUTED, row[0])
        self.assertEqual("james", row[1])
        self.assertIsNotNone(row[2])

    # -- 9. the result is physically isolated -------------------------------

    def test_9_the_written_row_is_unreachable_from_the_sibling_scope(self):
        approval_id = self.propose()
        self.approvals.decide(self.token(), approval_id, True, decided_by="james")

        with self.boundary.open(self.token(B)) as ch:
            visible = ch.fetch("SELECT item_ref FROM item")
        self.assertEqual([], visible, "the sibling scope could read the result")

        # And the approval itself is equally isolated -- inherited, not designed.
        with self.boundary.open(self.token(B)) as ch:
            approvals_visible = ch.fetch("SELECT approval_id FROM approval")
        self.assertEqual([], approvals_visible)

    def test_9b_a_hostile_channel_cannot_plant_an_approval_in_the_sibling(self):
        """WITH CHECK covers `approval` exactly as it covers `item`: even
        bypassing every application control, a channel bound to A cannot
        manufacture an approval that appears in B."""
        import psycopg2
        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(self.token(A)) as ch:
                ch.execute(
                    "INSERT INTO approval (approval_id, actor_ref, scope_path,"
                    " binding_identity, risk_class) VALUES ('ap-x','james',%s,'x','EXECUTE')",
                    (B,))
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM approval WHERE scope_path=%s", (B,))
            self.assertEqual(0, cur.fetchone()[0])
        conn.close()

    # -- 10. the decision and the action are both recorded ------------------

    def test_10_the_approval_and_the_write_are_both_audited(self):
        import psycopg2
        approval_id = self.propose()
        self.approvals.decide(self.token(), approval_id, True, decided_by="james")

        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT writer, category, scope_path, actor_ref FROM audit_record"
                        " WHERE category='data.write'")
            self.assertEqual([("W-1", "data.write", A, "james")], cur.fetchall())
        conn.close()

        status, decided_by, decided_at, scope_path, plan_identity = \
            self.approval_row(approval_id)
        self.assertEqual((EXECUTED, "james", A), (status, decided_by, scope_path))
        self.assertIsNotNone(decided_at)
        self.assertEqual(self.writes.plan_for(A, "it-1", "hello").identity(),
                         plan_identity, "the recorded plan is not the one executed")

    # -- 11. idempotence ----------------------------------------------------

    def test_11_a_second_approval_of_the_same_action_does_not_duplicate(self):
        """S11-D2: dedup is the provider's unique constraint, not a claim.
        Two separately approved identical writes leave one row."""
        first = self.propose(item_ref="it-1", body="hello")
        self.approvals.decide(self.token(), first, True, decided_by="james")
        second = self.propose(item_ref="it-1", body="hello")
        self.approvals.decide(self.token(), second, True, decided_by="james")
        self.assertEqual([("it-1", "hello")], self.rows(A))

    # -- the whole path over HTTP -------------------------------------------

    def test_12_the_complete_user_path_over_http(self):
        approval_id = self.propose(item_ref="it-http", body="via http")
        self.server, self.port = serve(self.seam)
        try:
            # Signed out: no listing.
            self.assertEqual(401, self.http("GET", f"/scope{A}/approvals")[0])

            # James sees the request.
            status, page = self.http("GET", f"/scope{A}/approvals", self.james_sid)
            self.assertEqual(200, status)
            self.assertIn("it-http", page)
            self.assertIn("Approve", page)

            # Section 15's tokens are served, not inlined -- the page consumes
            # the design system rather than restating it.
            self.assertIn("/static/tokens.css", page)
            css_status, css = self.http("GET", "/static/tokens.css")
            self.assertEqual(200, css_status)
            self.assertIn("--nova-color-surface-base", css)

            # Nothing has happened yet.
            self.assertEqual([], self.rows())

            # He approves. The action runs through the full path.
            status, page = self.http("POST", f"/scope{A}/approvals/{approval_id}",
                                     self.james_sid, {"decision": "approve"})
            self.assertEqual(200, status)
            self.assertEqual([("it-http", "via http")], self.rows(A))

            # The queue is empty afterwards.
            _, page = self.http("GET", f"/scope{A}/approvals", self.james_sid)
            self.assertIn("Nothing needs your decision", page)
        finally:
            self.server.shutdown()


if __name__ == "__main__":
    unittest.main()
