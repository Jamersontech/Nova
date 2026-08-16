"""The first real NOVA capability, end to end.

    open NOVA -> see the three areas -> drill into one -> see what needs your
    decision and what NOVA did there

Every layer is the real one: a real WebAuthn session, a real Context Token, the
real PDP, the real Data-Access Boundary, real PostgreSQL with RLS, and a scope
tree loaded from the database rather than built by this file.

WHAT THIS SUITE IS ACTUALLY GUARDING
------------------------------------
Navigation is the easiest place in any product to leak. A menu that lists what
exists is an enumeration; a link that works because it was rendered is an
authorization decision made by a template. So the tests below insist on both
halves separately:

  what is OFFERED  -- only scopes a grant already permits
  what is REACHABLE -- re-decided on entry, so a hand-typed URL gains nothing

And on the one product rule that is a security rule: A-3a puts cross-scope
activity review behind step-up, so activity here is pinned to one scope.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_product
"""

from __future__ import annotations

import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

from .. import db, tree_store
from ..approval_flow import ApprovalService
from ..boundary import DataAccessBoundary
from ..seam import Seam, serve
from ..write_path import (PostgresItemIntegration, WritePath, write_item_tool,
                          TOOL)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.context_service import ContextService
from ...core.policy import PolicyDecisionPoint
from ...core.store import StoreRegistry
from ...core.types import Risk
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

KAIRO = "/business/KAIRO"
A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"

# The structure James is assumed to have. LIFE / BUSINESS / WEALTH is the
# accepted primary structure (USER_INTERFACE_ARCHITECTURE section 2); the rest
# is ordinary test data, not a domain model.
SCOPES = [
    ("/life", "domain", None),
    ("/business", "domain", None),
    ("/wealth", "domain", None),
    (KAIRO, "business", "/business"),
    (A, "client", KAIRO),
    (B, "client", KAIRO),
    ("/private", "domain", None),      # exists, and James is granted nothing on it
]
GRANTS = [("james", "/life", "read"),
          ("james", "/business", "read"),
          ("james", "/business", "write"),
          ("james", "/wealth", "read")]


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class ProductTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        # THE POINT: the tree is read out of PostgreSQL, not constructed here.
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-product-")
        self.context = ContextService(self.tree, secret=b"product-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=A,
                              permitted_operations=frozenset({TOOL})),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        registry.register(write_item_tool())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                PostgresItemIntegration(self.boundary), "db-item-write")
        self.approvals = ApprovalService(self.boundary, self.writes)

        self.auth = authfixture.service()
        self.key = authfixture.enrol(self.auth, "james", "james", "laptop")
        self.sid = authfixture.sign_in(self.auth, self.key)
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals,
                         tree=self.tree)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, scope, ceiling=Risk.EXECUTE, rights=frozenset({"write"})):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=rights,
                                       ceiling=ceiling, ttl=60)

    def audit_in(self, scope_path: str, detail: str) -> None:
        """Write one audit record, through the boundary, in that scope."""
        with self.boundary.open(self.token(scope_path)) as ch:
            ch.execute(
                "INSERT INTO audit_record (event_identity, writer, category,"
                " scope_path, trace_id, actor_ref, detail)"
                " VALUES (%s,'W-1','data.write',%s,'t-1','james',%s)",
                (os.urandom(16).hex(), scope_path, detail))

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

    # =======================================================================
    # The tree is real
    # =======================================================================

    def test_01_the_scope_tree_comes_out_of_the_database(self):
        """It was a fixture; now it is data. Nothing in this test constructs
        a scope -- `seed` wrote them and `load_tree` read them back."""
        self.assertEqual(["/business", "/life", "/private", "/wealth"],
                         self.tree.roots())
        self.assertEqual([A, B], self.tree.children(KAIRO))
        self.assertEqual([KAIRO], self.tree.children("/business"))
        # And the grants came with it.
        self.assertIsNotNone(self.tree.find_grant("james", "read", "*", A))
        self.assertIsNone(self.tree.find_grant("james", "read", "*", "/private"))

    def test_02_a_scope_added_to_the_database_appears_on_reload(self):
        tree_store.seed([("/business/NEWCO", "business", "/business")], [])
        self.assertNotIn("/business/NEWCO", self.tree.paths())
        self.assertIn("/business/NEWCO", tree_store.load_tree().paths())

    # =======================================================================
    # Level 2 -- the three areas
    # =======================================================================

    def test_03_home_shows_the_areas_james_holds_and_no_others(self):
        status, page = self.seam.home_page(self.sid)
        self.assertEqual(200, status)
        for area in ("LIFE", "BUSINESS", "WEALTH"):
            self.assertIn(area, page)
        # `/private` exists in the tree and James has no grant on it.
        self.assertNotIn("PRIVATE", page)
        self.assertNotIn("/private", page)

    def test_04_home_never_grows_a_fourth_area(self):
        """Section 2: businesses, clients and projects grow INSIDE, never
        beside. The home page enumerates roots, not subsystems."""
        _, page = self.seam.home_page(self.sid)
        for subsystem in ("KAIRO", "client-a", "agent", "tool", "integration",
                          "memory", "workflow", "orchestrat"):
            self.assertNotIn(subsystem.lower(), page.lower())

    def test_05_home_requires_a_session(self):
        self.assertEqual(401, self.seam.home_page(None)[0])
        self.assertEqual(401, self.seam.home_page("not-a-session")[0])

    # =======================================================================
    # Navigation is not authorization
    # =======================================================================

    def test_06_a_scope_absent_from_navigation_is_also_unreachable(self):
        """The link is not what authorizes. Typing the URL re-decides from
        scratch and refuses -- at issuance, before anything is rendered."""
        status, page = self.seam.scope_page(self.sid, "/private")
        self.assertEqual(403, status)
        self.assertIn("not available", page.lower())

    def test_07_an_unknown_scope_and_a_forbidden_one_answer_identically(self):
        """A requester without access must not learn which it was."""
        forbidden = self.seam.scope_page(self.sid, "/private")
        unknown = self.seam.scope_page(self.sid, "/no-such-area")
        self.assertEqual(forbidden, unknown)

    def test_08_children_are_filtered_by_grant_too(self):
        """James holds /business, so KAIRO's clients are offered. Remove the
        grant and the same page offers nothing -- the filter is the grant."""
        _, page = self.seam.scope_page(self.sid, KAIRO)
        self.assertIn("CLIENT A", page)
        self.assertIn("CLIENT B", page)

        bare = ContextService(tree_store.load_tree(), secret=b"k")
        for grant in list(bare._tree._grants):
            grant.revoked = True
        seam = Seam(bare, PolicyDecisionPoint(bare._tree, bare, self.pdp._audit),
                    self.boundary, self.auth, tree=bare._tree)
        self.assertEqual(403, seam.scope_page(self.sid, KAIRO)[0])
        self.assertNotIn("CLIENT A", seam.home_page(self.sid)[1])

    # =======================================================================
    # Level 3 -- what needs my decision, what did NOVA do
    # =======================================================================

    def test_09_the_scope_page_answers_the_two_questions(self):
        self.audit_in(A, "item_ref=notes")
        self.approvals.propose(self.token(A), A, "it-1", "hello")

        status, page = self.seam.scope_page(self.sid, A)
        self.assertEqual(200, status)
        self.assertIn("1 action need", page)          # what needs my decision
        self.assertIn("item_ref=notes", page)         # what did NOVA do
        self.assertIn(f"/scope{A}/approvals", page)   # ...and how to act on it

    def test_10_a_quiet_scope_says_so_rather_than_showing_nothing(self):
        _, page = self.seam.scope_page(self.sid, B)
        self.assertIn("Nothing needs your decision", page)
        self.assertIn("Nothing has happened here yet", page)

    def test_11_activity_is_pinned_to_one_scope(self):
        """A-3a: reviewing activity across MORE than one scope requires
        step-up, which does not exist yet. The parent's page must therefore
        not aggregate its children -- even though the token covers them."""
        self.audit_in(A, "child-record")
        self.audit_in(KAIRO, "parent-record")

        _, parent = self.seam.scope_page(self.sid, KAIRO)
        self.assertIn("parent-record", parent)
        self.assertNotIn("child-record", parent, "activity aggregated across scopes")

        _, child = self.seam.scope_page(self.sid, A)
        self.assertIn("child-record", child)
        self.assertNotIn("parent-record", child)
        # And the cap is stated to James, not merely implemented.
        self.assertIn("more than one scope", parent)

    def test_12_activity_is_still_bounded_by_rls_underneath(self):
        """The scope pin is an A-3a rule, not the isolation control. Prove the
        isolation control is still there: a hostile channel bound to B cannot
        read A's records at all."""
        self.audit_in(A, "secret-a")
        with self.boundary.open(self.token(B)) as ch:
            self.assertEqual([], ch.fetch(
                "SELECT detail FROM audit_record WHERE detail = 'secret-a'"))

    # =======================================================================
    # A-1 still governs what can be done from here
    # =======================================================================

    def test_13_a_single_factor_session_can_look_but_not_decide(self):
        self.approvals.propose(self.token(A), A, "it-1", "hello")
        weak = authfixture.sign_in(self.auth, self.key, user_verified=False)

        self.assertEqual(200, self.seam.home_page(weak)[0])
        status, page = self.seam.scope_page(weak, A)
        self.assertEqual(200, status)
        self.assertIn("1 action need", page)
        # ...and following the link refuses.
        status, page = self.seam.approvals_page(weak, A)
        self.assertEqual(403, status)
        self.assertIn("second factor", page)

    # =======================================================================
    # The control-plane role did not widen anything
    # =======================================================================

    def test_14_the_control_role_reads_the_tree_and_nothing_else(self):
        import psycopg2
        conn = psycopg2.connect(db.control_dsn())
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM scope")
                self.assertEqual(len(SCOPES), cur.fetchone()[0])
            for table in ("item", "approval", "audit_record", "auth_session"):
                with conn.cursor() as cur:
                    with self.assertRaises(psycopg2.Error, msg=f"reached {table}"):
                        cur.execute(f"SELECT * FROM {table}")
                conn.rollback()
        finally:
            conn.close()

    def test_15_the_control_policy_did_not_widen_the_application_role(self):
        """The policy names one role. `nova_app` must still see only its own
        scope in `scope` and `grant` -- with no binding it sees nothing."""
        import psycopg2
        conn = psycopg2.connect(db.app_dsn())
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM scope")
                self.assertEqual(0, cur.fetchone()[0], "nova_app read the tree unbound")
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                cur.execute("SELECT scope_path FROM scope")
                self.assertEqual([(A,)], cur.fetchall(),
                                 "nova_app saw scopes outside its binding")
        finally:
            conn.rollback(); conn.close()

    def test_16_the_control_role_cannot_write_the_tree(self):
        """I-10: only James creates grants. The application's startup reader is
        read-only, so no running code path can add one."""
        import psycopg2
        conn = psycopg2.connect(db.control_dsn())
        try:
            with conn.cursor() as cur:
                with self.assertRaises(psycopg2.Error):
                    cur.execute("INSERT INTO \"grant\" (actor_ref, scope_path,"
                                " right_name) VALUES ('james','/private','read')")
        finally:
            conn.rollback(); conn.close()
        self.assertIsNone(tree_store.load_tree().find_grant(
            "james", "read", "*", "/private"))

    # =======================================================================
    # The whole thing, over HTTP, from a cold start
    # =======================================================================

    def test_17_james_opens_nova(self):
        self.audit_in(A, "item_ref=notes")
        self.approvals.propose(self.token(A), A, "it-1", "hello")
        self.server, self.port = serve(self.seam)
        try:
            # Signed out, the front door is shut.
            self.assertEqual(401, self.http("GET", "/")[0])

            # Signed in: the three areas.
            status, home = self.http("GET", "/", self.sid)
            self.assertEqual(200, status)
            for area in ("LIFE", "BUSINESS", "WEALTH"):
                self.assertIn(area, home)
            self.assertIn('href="/scope/business"', home)

            # Drill: BUSINESS -> KAIRO -> client-a.
            _, business = self.http("GET", "/scope/business", self.sid)
            self.assertIn("KAIRO", business)
            _, kairo = self.http("GET", f"/scope{KAIRO}", self.sid)
            self.assertIn("CLIENT A", kairo)
            status, client = self.http("GET", f"/scope{A}", self.sid)
            self.assertEqual(200, status)
            self.assertIn("1 action need", client)
            self.assertIn("item_ref=notes", client)

            # The forbidden area is not offered and not reachable.
            self.assertNotIn("/private", home)
            self.assertEqual(403, self.http("GET", "/scope/private", self.sid)[0])

            # Follow the decision link and the approval is really there.
            status, approvals = self.http("GET", f"/scope{A}/approvals", self.sid)
            self.assertEqual(200, status)
            self.assertIn("Write item", approvals)

            # Nothing anywhere in the walk leaked machinery to the browser.
            for marker in ("integrity", "trace_id", "set_config", "nova_app",
                           "nova_control", "session_ref"):
                for page in (home, business, kairo, client, approvals):
                    self.assertNotIn(marker, page.lower())
        finally:
            self.server.shutdown()


if __name__ == "__main__":
    unittest.main()
