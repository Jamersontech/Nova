"""The application path, end to end, over real HTTP against real PostgreSQL.

test_isolation.py proves the physical layer with hostile SQL. This suite
proves the APPLICATION -> SUBSTRATE integration: that the chain

    HTTP -> session -> Context Token -> Data Access PEP -> boundary -> RLS
         -> audit -> rendered HTML

holds the same properties when driven the way NOVA will actually drive it.
When every test here passes against a live cluster, I-03 is ENFORCED in the
application path, not only in the substrate.

Skips when PostgreSQL is unavailable -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_seam
"""

from __future__ import annotations

import unittest
import urllib.error
import urllib.request

from .. import db
from ..boundary import DataAccessBoundary
from ..seam import Seam, serve
from . import authfixture
from ...core.audit import AuditWriter
from ...core.context_service import ContextService
from ...core.policy import PolicyDecisionPoint
from ...core.scope_tree import ScopeTree
from ...core.store import StoreRegistry
from ...core.types import Risk

A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class SeamTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import psycopg2, tempfile

        db.apply_schema()
        db.reset_data()

        # Real machinery end to end -- the pieces the slices validated,
        # now wired together for the first time.
        tree = ScopeTree()
        tree.add_scope("/business", "domain")
        tree.add_scope("/business/KAIRO", "business")
        tree.add_scope(A, "client")
        tree.add_scope(B, "client")
        # James's grants (I-10): james may read BOTH clients; the second
        # actor may read only client A. The difference is what tests 8/9 use.
        tree.james_grants("james", "read", "*", A, Risk.READ)
        tree.james_grants("james", "read", "*", B, Risk.READ)
        tree.james_grants("assistant", "read", "*", A, Risk.READ)

        context = ContextService(tree, secret=b"seam-test-key")
        audit = AuditWriter(StoreRegistry(tempfile.mkdtemp(prefix="nova-seam-")))
        pdp = PolicyDecisionPoint(tree, context, audit)
        cls.boundary = DataAccessBoundary(db.app_dsn(), context)
        # Real authentication: two enrolled passkeys and two real signed-in
        # sessions. Nothing below this line changed to accommodate it.
        cls.auth = authfixture.service()
        cls.seam = Seam(context, pdp, cls.boundary, cls.auth)

        cls.james_key = authfixture.enrol(cls.auth, "james", "james")
        cls.assistant_key = authfixture.enrol(cls.auth, "assistant", "assistant")
        cls.james_sid = authfixture.sign_in(cls.auth, cls.james_key)
        cls.assistant_sid = authfixture.sign_in(cls.auth, cls.assistant_key)

        # Seed data as the owner, not through the seam.
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO item (item_ref, scope_path, body) VALUES "
                "('a-1',%s,'CLIENT A SECRET'), ('b-1',%s,'CLIENT B SECRET')", (A, B))
        conn.close()

        cls.server, cls.port = serve(cls.seam)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.boundary.close()

    # -- HTTP helper ---------------------------------------------------------

    def get(self, path: str, session: str | None) -> tuple[int, str]:
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}")
        if session:
            req.add_header("Cookie", f"nova_session={session}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def items(self, scope: str, session: str | None) -> tuple[int, str]:
        return self.get(f"/scope{scope}/items", session)

    # -- 1/2. identity and token are server-side -----------------------------

    def test_01_authenticated_request_resolves_the_right_identity(self):
        status, body = self.items(A, self.james_sid)
        self.assertEqual(200, status)
        self.assertIn("CLIENT A SECRET", body)

    def test_02_token_issued_server_side_only(self):
        """The browser sends a cookie; the token exists only behind the seam.
        Proven structurally in test_13 (no token material in any response)."""
        status, _ = self.items(A, self.james_sid)
        self.assertEqual(200, status)

    # -- 3/4. scope comes from the token, not the caller ---------------------

    def test_03_boundary_scope_is_the_token_scope(self):
        """The URL names the scope, but only via token issuance: the page for
        A shows A's items and nothing else, with no app-side predicate."""
        _, body = self.items(A, self.james_sid)
        self.assertIn("CLIENT A SECRET", body)
        self.assertNotIn("CLIENT B SECRET", body)

    def test_04_caller_cannot_widen_past_its_grants(self):
        """assistant has no grant on B: naming B in the URL yields a denial,
        and the denial does not reveal whether B exists."""
        status, body = self.items(B, self.assistant_sid)
        self.assertEqual(403, status)
        self.assertNotIn("CLIENT B SECRET", body)
        # Unknown scope and ungranted scope are the same page (no existence leak).
        status2, body2 = self.items("/business/KAIRO/no-such-client", self.assistant_sid)
        self.assertEqual(403, status2)
        self.assertEqual(body, body2)

    # -- 5/6. no or bad session ----------------------------------------------

    def test_05_invalid_session_gets_401(self):
        status, _ = self.items(A, "forged-session-id")
        self.assertEqual(401, status)

    def test_06_missing_session_gets_401(self):
        status, _ = self.items(A, None)
        self.assertEqual(401, status)

    # -- 7. the PDP is actually consulted ------------------------------------

    def test_07_pdp_denial_blocks_the_read(self):
        """Take the PDP down (I-17 fail-closed): the same request that
        succeeds in test_01 must now fail, proving the PDP is in the path
        rather than decorative."""
        self.seam._pdp.available = False
        try:
            status, body = self.items(A, self.james_sid)
            self.assertEqual(403, status)
            self.assertNotIn("CLIENT A SECRET", body)
        finally:
            self.seam._pdp.available = True

    # -- 8/9. the isolation property, through the application ----------------

    def test_08_client_a_data_is_reachable_in_scope(self):
        status, body = self.items(A, self.assistant_sid)
        self.assertEqual(200, status)
        self.assertIn("CLIENT A SECRET", body)

    def test_09_client_b_data_is_not_reachable_from_a(self):
        _, body = self.items(A, self.james_sid)
        self.assertNotIn("CLIENT B SECRET", body)
        _, body = self.items(A, self.assistant_sid)
        self.assertNotIn("CLIENT B SECRET", body)

    # -- 10/14. RLS holds without application filtering ----------------------

    def test_10_no_application_side_predicate_exists(self):
        """The seam's query has no scope predicate -- by source inspection,
        so a regression reintroducing one (or removing RLS reliance) shows."""
        import inspect
        from .. import seam
        src = inspect.getsource(seam.Seam.items_page)
        self.assertIn("SELECT item_ref, body FROM item ORDER BY item_ref", src)
        self.assertNotIn("WHERE scope_path", src)

    def test_14_rls_is_what_holds_it(self):
        """Negative control at the application level: disable RLS and the
        seam leaks; re-enable and it closes. Same rationale as the substrate
        suite's test_0 -- a green suite must be able to go red."""
        import psycopg2
        admin = psycopg2.connect(db.superuser_dsn()); admin.autocommit = True
        try:
            with admin.cursor() as cur:
                cur.execute("ALTER TABLE item NO FORCE ROW LEVEL SECURITY")
                cur.execute("ALTER TABLE item DISABLE ROW LEVEL SECURITY")
            _, body = self.items(A, self.james_sid)
            self.assertIn("CLIENT B SECRET", body,
                          "RLS off but no leak -- this suite is not testing RLS")
        finally:
            with admin.cursor() as cur:
                cur.execute("ALTER TABLE item ENABLE ROW LEVEL SECURITY")
                cur.execute("ALTER TABLE item FORCE ROW LEVEL SECURITY")
            admin.close()
        _, body = self.items(A, self.james_sid)
        self.assertNotIn("CLIENT B SECRET", body, "RLS did not close the leak")

    # -- 11. pooled connections carry nothing --------------------------------

    def test_11_scope_does_not_leak_across_sequential_requests(self):
        """A then B then A on the same small pool: each response bounded."""
        for scope, present, absent in ((A, "CLIENT A SECRET", "CLIENT B SECRET"),
                                       (B, "CLIENT B SECRET", "CLIENT A SECRET"),
                                       (A, "CLIENT A SECRET", "CLIENT B SECRET")):
            _, body = self.items(scope, self.james_sid)
            self.assertIn(present, body)
            self.assertNotIn(absent, body)

    # -- 12. audit -----------------------------------------------------------

    def test_12_every_read_is_audited_with_actor_and_scope(self):
        import psycopg2
        before = self._audit_count()
        status, _ = self.items(A, self.james_sid)
        self.assertEqual(200, status)
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute(
                "SELECT writer, category, scope_path, actor_ref FROM audit_record"
                " ORDER BY id DESC LIMIT 1")
            writer, category, scope, actor = cur.fetchone()
        conn.close()
        self.assertEqual(("W-1", "data.read", A, "james"),
                         (writer, category, scope, actor))
        self.assertEqual(before + 1, self._audit_count())

    def _audit_count(self) -> int:
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM audit_record")
            n = cur.fetchone()[0]
        conn.close()
        return n

    # -- 13. the browser holds nothing ---------------------------------------

    def test_13_no_token_or_secret_material_in_any_response(self):
        for scope, sid in ((A, self.james_sid), (B, self.james_sid),
                           (A, self.assistant_sid), (B, self.assistant_sid),
                           (A, None)):
            _, body = self.items(scope, sid)
            low = body.lower()
            for marker in ("integrity", "trace_id", "granted_rights",
                           "nova_app", "dbname=", "set_config", "context token"):
                self.assertNotIn(marker, low, f"{marker!r} leaked into a response")
            # The session id itself must never be echoed back into a page.
            if sid:
                self.assertNotIn(sid, body)


if __name__ == "__main__":
    unittest.main()
