"""The first authorized WRITE, end to end, against real PostgreSQL.

Proves the consequence-producing half of the substrate: a write travels
through the EXISTING plan/approval/PEP/broker architecture and lands under
RLS WITH CHECK. Every control is shown load-bearing by a negative:

  the PDP        -- taken down, the write fails
  the approval   -- absent, step 9 denies (I-09), nothing lands
  the grant      -- an ungranted actor cannot write
  the context    -- no/forged token opens nothing
  WITH CHECK     -- a hostile transport bypassing every application control
                    still cannot plant a row in the sibling scope

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_write_path
"""

from __future__ import annotations

import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

from .. import db
from ..boundary import DataAccessBoundary
from ..seam import Seam, serve
from . import authfixture
from ..write_path import (ApprovalStore, PostgresItemIntegration, WritePath,
                          write_item_tool, TOOL)
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
class WritePathTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        import os
        db.reset_data()

        tree = ScopeTree()
        tree.add_scope("/business", "domain")
        tree.add_scope("/business/KAIRO", "business")
        tree.add_scope(A, "client")
        tree.add_scope(B, "client")
        # james may write A; the assistant may not write anywhere (I-10).
        tree.james_grants("james", "write", "*", A, Risk.EXECUTE)
        tree.james_grants("james", "read", "*", A, Risk.READ)

        tmp = tempfile.mkdtemp(prefix="nova-write-")
        self.context = ContextService(tree, secret=b"write-path-test-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        secrets = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(tree, secrets, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=A,
                              permitted_operations=frozenset({TOOL})),
            secret="integration-credential-" + os.urandom(4).hex(),
        )

        registry = ToolRegistry()
        registry.register(write_item_tool())
        pep = ToolPEP(registry, broker, self.context, audit)

        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")

        self.auth = authfixture.service()
        self.james_sid = authfixture.sign_in(
            self.auth, authfixture.enrol(self.auth, "james", "james"))
        self.assistant_sid = authfixture.sign_in(
            self.auth, authfixture.enrol(self.auth, "assistant", "assistant"))
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, scope=A, rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=rights,
                                       ceiling=ceiling, ttl=60)

    def approve(self, scope=A, item_ref="it-1", body="hello"):
        plan = self.writes.plan_for(scope, item_ref, body)
        return self.writes.approvals.james_approves(plan.identity())

    def rows(self, scope=None):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            if scope:
                cur.execute("SELECT item_ref, body FROM item WHERE scope_path=%s", (scope,))
            else:
                cur.execute("SELECT item_ref, scope_path, body FROM item")
            out = cur.fetchall()
        conn.close()
        return out

    # -- positive ------------------------------------------------------------

    def test_1_approved_write_lands_in_scope(self):
        self.approve()
        outcome = self.writes.execute(self.token(), A, "it-1", "hello")
        self.assertEqual("success_claimed", outcome.state)
        self.assertEqual([("it-1", "hello")], self.rows(A))
        self.assertEqual(1, self.integration.side_effects)

    # -- approval negative (I-09) --------------------------------------------

    def test_2_no_approval_no_write(self):
        with self.assertRaises(Denied) as cm:
            self.writes.execute(self.token(), A, "it-1", "hello")
        self.assertEqual("I-09", cm.exception.invariant)
        self.assertEqual([], self.rows(), "a row landed despite step-9 denial")
        self.assertEqual(0, self.integration.side_effects,
                         "the transport ran before authorization")

    def test_2b_approval_is_bound_to_the_plan_identity(self):
        """An approval for one plan does not cover a materially different one
        (I-109/I-112): approving it-1 does not authorize it-2."""
        self.approve(item_ref="it-1")
        with self.assertRaises(Denied):
            self.writes.execute(self.token(), A, "it-2", "other")
        self.assertEqual([], self.rows())

    # -- authorization negative (grants) -------------------------------------

    def test_3_ungranted_actor_cannot_write(self):
        self.approve()
        with self.assertRaises(Denied) as cm:
            tok = self.context.issue_root(identity="assistant", actor="assistant",
                                          scope_path=A, rights=frozenset({"write"}),
                                          ceiling=Risk.EXECUTE, ttl=60)
            self.writes.execute(tok, A, "it-1", "hello")
        self.assertEqual("I-14", cm.exception.invariant)   # denied at issuance
        self.assertEqual([], self.rows())

    def test_3b_read_ceiling_token_cannot_execute(self):
        self.approve()
        tok = self.context.issue_root(identity="james", actor="james",
                                      scope_path=A, rights=frozenset({"write"}),
                                      ceiling=Risk.READ, ttl=60)
        with self.assertRaises(Denied) as cm:
            self.writes.execute(tok, A, "it-1", "hello")
        self.assertEqual("I-101", cm.exception.invariant)
        self.assertEqual([], self.rows())

    # -- context negative ----------------------------------------------------

    def test_4_forged_token_writes_nothing(self):
        import dataclasses
        self.approve(scope=B)
        forged = dataclasses.replace(self.token(A), scope_path=B)
        with self.assertRaises(Denied) as cm:
            self.writes.execute(forged, B, "it-1", "hello")
        self.assertEqual("I-87", cm.exception.invariant)
        self.assertEqual([], self.rows())

    # -- PDP negative --------------------------------------------------------

    def test_5_pdp_down_blocks_the_write(self):
        """I-17 fail-closed: the same write that succeeds in test_1 fails with
        the PDP unavailable -- the PDP is load-bearing, not decorative."""
        self.approve()
        self.pdp.available = False
        try:
            with self.assertRaises(Denied):
                self.writes.execute(self.token(), A, "it-1", "hello")
            self.assertEqual([], self.rows())
        finally:
            self.pdp.available = True
        # And with it restored, the identical write succeeds.
        self.writes.execute(self.token(), A, "it-1", "hello")
        self.assertEqual([("it-1", "hello")], self.rows(A))

    # -- physical isolation negatives (WITH CHECK) ---------------------------

    def test_6_hostile_transport_cannot_plant_a_row_in_the_sibling_scope(self):
        """THE test. Bypass every application control above the channel:
        a transport that ignores the plan and names scope B directly.
        PostgreSQL WITH CHECK must refuse -- and does."""
        import psycopg2
        tok = self.token()
        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(tok) as ch:
                ch.execute(
                    "INSERT INTO item (item_ref, scope_path, body) VALUES (%s,%s,%s)",
                    ("planted", B, "HOSTILE"))
        self.assertEqual([], self.rows(B), "a cross-scope row landed")

    def test_6b_hostile_update_cannot_move_a_row_across_scopes(self):
        """USING + WITH CHECK together: re-scoping a row to the sibling is
        refused even for a row the channel can see."""
        import psycopg2
        self.approve()
        self.writes.execute(self.token(), A, "it-1", "hello")
        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(self.token()) as ch:
                ch.execute("UPDATE item SET scope_path=%s WHERE item_ref='it-1'", (B,))
        self.assertEqual([], self.rows(B))
        self.assertEqual([("it-1", "hello")], self.rows(A), "the row was damaged")

    def test_6c_raw_connection_bound_to_a_cannot_write_b(self):
        """No boundary at all: a raw nova_app connection with the binding set
        by hand. The engine alone refuses the cross-scope write."""
        import psycopg2
        conn = psycopg2.connect(db.app_dsn())
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                with self.assertRaises(psycopg2.Error):
                    cur.execute(
                        "INSERT INTO item (item_ref, scope_path, body) VALUES ('x',%s,'HOSTILE')",
                        (B,))
        finally:
            conn.rollback(); conn.close()
        self.assertEqual([], self.rows(B))

    # -- audit ---------------------------------------------------------------

    def test_7_authorized_write_is_audited_in_the_same_transaction(self):
        import psycopg2
        self.approve()
        self.writes.execute(self.token(), A, "it-1", "hello")
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT writer, category, scope_path, actor_ref FROM audit_record"
                        " WHERE category='data.write'")
            rows = cur.fetchall()
        conn.close()
        self.assertEqual([("W-1", "data.write", A, "james")], rows)

    def test_7b_denied_write_leaves_no_datastore_audit_but_no_row_either(self):
        """The denial is recorded by the PDP's own decision log (W-2, exercised
        by the 121 suite); the datastore shows neither a row nor a write audit
        -- the transaction never began."""
        with self.assertRaises(Denied):
            self.writes.execute(self.token(), A, "it-1", "hello")
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM audit_record WHERE category='data.write'")
            self.assertEqual(0, cur.fetchone()[0])
        conn.close()

    # -- idempotent retry (S11-D2: provider-enforced dedup) ------------------

    def test_8_retry_is_deduplicated_by_the_provider(self):
        self.approve()
        self.writes.execute(self.token(), A, "it-1", "hello")
        self.writes.execute(self.token(), A, "it-1", "hello")
        self.assertEqual([("it-1", "hello")], self.rows(A), "the upsert duplicated")

    # -- end-to-end HTTP ------------------------------------------------------

    def test_9_http_write_end_to_end(self):
        server, port = serve(self.seam)
        try:
            def post(scope, sid, item_ref="it-http", body="via http"):
                data = urllib.parse.urlencode(
                    {"item_ref": item_ref, "body": body}).encode()
                req = urllib.request.Request(
                    f"http://127.0.0.1:{port}/scope{scope}/items", data=data)
                if sid:
                    req.add_header("Cookie", f"nova_session={sid}")
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        return resp.status, resp.read().decode()
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode()

            # Unauthenticated: nothing.
            status, _ = post(A, None)
            self.assertEqual(401, status)

            # Authenticated but unapproved: step 9 denies, distinguishable
            # as "approval required" -- the caller's next legitimate step.
            status, page = post(A, self.james_sid)
            self.assertEqual(403, status)
            self.assertIn("requires James", page)
            self.assertEqual([], self.rows(A))

            # James approves THIS plan; the same request now lands.
            self.approve(item_ref="it-http", body="via http")
            status, page = post(A, self.james_sid)
            self.assertEqual(200, status)
            self.assertEqual([("it-http", "via http")], self.rows(A))

            # No token material in any response.
            for marker in ("integrity", "trace_id", "set_config", "nova_app"):
                self.assertNotIn(marker, page.lower())
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
