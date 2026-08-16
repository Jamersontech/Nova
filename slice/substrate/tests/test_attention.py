"""What needs my attention: NOVA's first cross-scope capability.

Cross-scope is the highest-risk area in the model, so this suite is written
against the shape the accepted architecture prescribes rather than against the
feature's happy path:

  I-86    serial single-scope channels, aggregated ABOVE the executions --
          asserted by counting the channels the gather actually opened, and by
          proving no query spans scopes
  I-49    recorded per scope touched, not once above them
  I-67    cross-scope AUDIT review needs step-up, which does not exist, so
          audit records are not read here at all
  I-95    the aggregate never reaches a model
  §2      the result is ephemeral -- nothing is written anywhere

Two negative controls, because a test that only proves the happy path cannot
tell whether isolation is holding or whether the data simply is not there:

  test_00  RLS disabled mid-run -- the leak APPEARS at the channel level, then
           closes when it is restored. RLS is what holds the per-scope read
  test_05  the same task is invisible without a grant and visible WITH one, so
           the grant is what decides -- not an accident of the fixture
  test_01  names the control that actually enforces it: token issuance, on
           I-14. The tree pre-filter in `gather` is a cheap skip, and the
           suite says so rather than crediting it

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_attention
"""

from __future__ import annotations

import datetime
import inspect
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

from .. import attention as attention_module
from .. import db, tree_store
from ..approval_flow import ApprovalService
from ..attention import AttentionService
from ..boundary import DataAccessBoundary
from ..conversation import CONVERSATION_MODEL, PROVIDER, ConversationService
from ..seam import Seam, serve
from ..write_path import (ADD_TASK, ALL_TOOLS, PostgresItemIntegration, WritePath)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.budget import BudgetLedger
from ...core.context_service import ContextService
from ...core.gateway import ModelGateway, ProviderBinding
from ...core.policy import PolicyDecisionPoint
from ...core.store import StoreRegistry
from ...core.types import Denied, Risk
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture
from .test_conversation import ScriptedTransport

LIFE = "/life"
BUSINESS = "/business"
KAIRO = "/business/KAIRO"
A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"
WEALTH = "/wealth"
PRIVATE = "/private"          # exists; James is granted nothing on it

SCOPES = [(LIFE, "domain", None), (BUSINESS, "domain", None),
          (WEALTH, "domain", None), (PRIVATE, "domain", None),
          (KAIRO, "business", BUSINESS),
          (A, "client", KAIRO), (B, "client", KAIRO)]
GRANTS = [("james", LIFE, "read"), ("james", WEALTH, "read"),
          ("james", BUSINESS, "read"), ("james", BUSINESS, "write")]

TODAY = datetime.date(2026, 8, 16)


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class AttentionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-attention-")
        self.context = ContextService(self.tree, secret=b"attention-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)
        self.attention = AttentionService(self.tree, self.context, self.pdp,
                                          self.boundary)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=BUSINESS,
                              permitted_operations=frozenset(t().name for t in ALL_TOOLS)),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        for tool in ALL_TOOLS:
            registry.register(tool())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                PostgresItemIntegration(self.boundary), "db-item-write")
        self.approvals = ApprovalService(self.boundary, self.writes)

        self.transport = ScriptedTransport()
        budget = BudgetLedger()
        gateway = ModelGateway(lambda: self.pdp.available, self.context, audit,
                               budget=budget)
        gateway.register_provider(
            ProviderBinding(provider=PROVIDER, model=CONVERSATION_MODEL,
                            endpoint="test://anthropic", api_version="test",
                            credential_ref="control-plane/anthropic", cost_per_unit=1),
            self.transport)
        self.conversation = ConversationService(gateway, self.pdp, self.boundary,
                                                self.approvals, budget)

        self.auth = authfixture.service()
        self.key = authfixture.enrol(self.auth, "james", "james", "laptop")
        self.sid = authfixture.sign_in(self.auth, self.key)
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals,
                         tree=self.tree, conversation=self.conversation,
                         attention=self.attention)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def sql(self, query, args=()):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, args or None)
            rows = cur.fetchall() if cur.description else []
        conn.close()
        return rows

    def seed_task(self, scope, ref, title, due):
        self.sql("INSERT INTO task (task_ref, scope_path, title, due_on)"
                 " VALUES (%s,%s,%s,%s)", (ref, scope, title, due))

    def seed_approval(self, scope, approval_id, action_text):
        self.sql("INSERT INTO approval (approval_id, actor_ref, scope_path,"
                 " binding_identity, risk_class, status, action_text, tool_name)"
                 " VALUES (%s,'james',%s,'b','EXECUTE','pending',%s,'add_task')",
                 (approval_id, scope, action_text))

    def gather(self):
        return self.attention.gather("james", "james", today=TODAY)

    # =======================================================================
    # 00 -- the negative control. Is RLS what holds the per-scope read?
    # =======================================================================

    def test_00_negative_control_rls_is_what_bounds_each_scope_read(self):
        """Every other test asserts a sibling's rows are absent; none of them
        can tell whether that is because RLS enforces it or because the data
        simply is not reachable another way. This disables RLS mid-run,
        asserts the leak APPEARS on a bound channel, then restores it."""
        self.seed_task(B, "b-task", "SIBLING-MATERIAL", "2026-08-17")
        token = self.context.issue_root(identity="james", actor="james",
                                        scope_path=A, rights=frozenset({"read"}),
                                        ceiling=Risk.READ, ttl=60)
        with self.boundary.open(token) as ch:
            self.assertEqual([], ch.fetch("SELECT task_ref FROM task"))

        self.sql("ALTER TABLE task DISABLE ROW LEVEL SECURITY")
        try:
            with self.boundary.open(token) as ch:
                leaked = ch.fetch("SELECT task_ref FROM task")
            self.assertEqual([("b-task",)], leaked,
                             "RLS disabled and nothing leaked -- this control "
                             "is not testing what it claims")
        finally:
            self.sql("ALTER TABLE task ENABLE ROW LEVEL SECURITY")
            self.sql("ALTER TABLE task FORCE ROW LEVEL SECURITY")

        with self.boundary.open(token) as ch:
            self.assertEqual([], ch.fetch("SELECT task_ref FROM task"))

    # =======================================================================
    # 1-4 -- what appears, and what does not
    # =======================================================================

    def test_01_an_unauthorized_scope_never_appears(self):
        self.seed_task(PRIVATE, "secret", "PRIVATE-MATERIAL", "2026-08-10")
        self.seed_approval(PRIVATE, "ap-private", "PRIVATE-APPROVAL")
        result = self.gather()
        self.assertEqual((), result.overdue)
        self.assertEqual((), result.approvals)
        self.assertNotIn(PRIVATE, result.scopes_read)

        _, page = self.seam.home_page(self.sid)
        for marker in ("PRIVATE-MATERIAL", "PRIVATE-APPROVAL", "/private"):
            self.assertNotIn(marker, page)

        # WHICH control holds this? Not the tree pre-filter in `gather` --
        # deleting that changes no result. Token issuance is the enforcement,
        # and it refuses on I-14 before any channel could be opened.
        with self.assertRaises(Denied) as cm:
            self.context.issue_root(identity="james", actor="james",
                                    scope_path=PRIVATE,
                                    rights=frozenset({"read"}),
                                    ceiling=Risk.READ, ttl=60)
        self.assertEqual("I-14", cm.exception.invariant)

    def test_02_a_pending_approval_in_an_authorized_scope_appears(self):
        self.seed_approval(A, "ap-1", "Add task “Send the revised quote”, due 2026-08-21.")
        result = self.gather()
        self.assertEqual(1, len(result.approvals))
        self.assertEqual((A, "ap-1"), (result.approvals[0].scope_path,
                                       result.approvals[0].approval_id))

        _, page = self.seam.home_page(self.sid)
        self.assertIn("Send the revised quote", page)
        self.assertIn("BUSINESS / KAIRO / CLIENT A", page)
        self.assertIn(f'href="/scope{A}/approvals"', page)   # routes to the real surface

    def test_03_an_open_dated_task_appears_and_a_decided_or_undated_one_does_not(self):
        self.seed_task(A, "soon", "Due in three days", "2026-08-19")
        self.seed_task(A, "someday", "No date at all", None)
        self.seed_task(A, "far", "Well beyond the horizon", "2026-12-01")
        self.sql("INSERT INTO task (task_ref, scope_path, title, due_on, done_at)"
                 " VALUES ('done', %s, 'Already finished', '2026-08-17', now())", (A,))

        result = self.gather()
        self.assertEqual(["soon"], [t.task_ref for t in result.due_soon])
        self.assertEqual((), result.overdue)

    def test_04_an_overdue_task_is_identified_as_overdue(self):
        self.seed_task(A, "late", "Chase the invoice", "2026-08-10")
        self.seed_task(A, "soon", "Due in three days", "2026-08-19")
        result = self.gather()
        self.assertEqual(["late"], [t.task_ref for t in result.overdue])
        self.assertEqual(["soon"], [t.task_ref for t in result.due_soon])
        self.assertTrue(result.overdue[0].overdue)

        _, page = self.seam.home_page(self.sid)
        self.assertIn("1 overdue", page)
        self.assertIn("1 due soon", page)
        self.assertIn("Chase the invoice", page)

    def test_05_the_filter_is_the_grant_negative_control(self):
        """The same row, twice: invisible with no grant, visible with one. So
        its absence above is the grant deciding, not the fixture."""
        self.seed_task(PRIVATE, "p", "NOW-YOU-SEE-IT", "2026-08-17")
        self.assertEqual((), self.gather().due_soon)

        tree_store.seed([], [("james", PRIVATE, "read")])
        self.attention._tree = self.context._tree = self.pdp._tree = \
            tree_store.load_tree()
        self.assertEqual(["p"], [t.task_ref for t in self.gather().due_soon])

    # =======================================================================
    # 5-8 -- the cross-scope SHAPE, which is the actual security claim
    # =======================================================================

    def test_06_one_scope_does_not_leak_into_another(self):
        self.seed_task(A, "a-task", "Client A work", "2026-08-17")
        self.seed_task(B, "b-task", "Client B work", "2026-08-17")
        result = self.gather()
        by_scope = {t.scope_path: t.title for t in result.due_soon}
        self.assertEqual({A: "Client A work", B: "Client B work"}, by_scope)
        # Each task is attributed to exactly one scope, and appears once.
        self.assertEqual(2, len(result.due_soon))

    def test_07_each_scope_is_read_through_its_own_bound_channel(self):
        """I-86: serial single-scope channels. One channel per authorized
        scope -- not one channel reused, and not one query spanning them."""
        self.gather()
        authorized = [p for p in self.tree.paths()
                      if self.tree.find_grant("james", "read", "*", p) is not None]
        self.assertEqual(6, len(authorized))          # everything but /private
        self.assertEqual(len(authorized), self.attention.channels_opened)
        self.assertEqual(tuple(sorted(authorized)), self.gather().scopes_read)

    def test_08_a_parents_read_does_not_double_count_its_children(self):
        """A token covers descendants, so without per-scope decomposition the
        same task would be counted under /business, /business/KAIRO and the
        client. I-86 requires one scope per execution."""
        self.seed_task(A, "once", "Counted exactly once", "2026-08-17")
        result = self.gather()
        self.assertEqual(1, len(result.due_soon))
        self.assertEqual(A, result.due_soon[0].scope_path)

    def test_09_no_query_in_the_attention_path_is_unbound(self):
        """Structural: every read is inside a `with self._boundary.open(...)`
        block, and every one names exactly one scope. Asserted by source
        inspection because it is a property of the CODE, not of one run."""
        source = inspect.getsource(attention_module)
        self.assertIn("with self._boundary.open(token) as ch:", source)
        # No connection is opened outside the boundary.
        for forbidden in ("psycopg2.connect", "app_dsn", "superuser_dsn",
                          "control_dsn", "owner_dsn"):
            self.assertNotIn(forbidden, source,
                             f"attention.py reaches the database via {forbidden}")
        # Every SELECT pins one scope.
        for line in source.splitlines():
            if "FROM approval" in line or "FROM task" in line:
                self.assertIn("scope_path = %s", source)

    def test_10_there_is_no_scope_parameter_to_attack(self):
        """A hostile path cannot expand a result set it cannot address:
        `gather` takes an identity, never a scope. Query strings and form
        fields on the home route change nothing."""
        self.seed_task(PRIVATE, "p", "PRIVATE-MATERIAL", "2026-08-17")
        self.assertNotIn("scope_path", inspect.signature(
            self.attention.gather).parameters)

        server, port = serve(self.seam)
        try:
            for query in ("", "?scope=/private", "?scope_path=/private",
                          "?scopes=/private,/business", "?identity=root"):
                req = urllib.request.Request(f"http://127.0.0.1:{port}/{query}")
                req.add_header("Cookie", f"nova_session={self.sid}")
                with urllib.request.urlopen(req, timeout=10) as r:
                    body = r.read().decode()
                self.assertNotIn("PRIVATE-MATERIAL", body, f"{query} widened the set")
        finally:
            server.shutdown()

    # =======================================================================
    # 9-11 -- what the view must NOT do
    # =======================================================================

    def test_11_the_model_is_never_called(self):
        """I-95: no model request carries more than one scope, and this
        aggregate is several by definition. It is a page, not an answer."""
        self.seed_task(A, "a", "Client A work", "2026-08-17")
        self.seed_approval(B, "ap-b", "Something in B")
        self.seam.home_page(self.sid)
        self.gather()
        self.assertEqual([], self.transport.prompts,
                         "the attention view reached the model")
        # Structural: the module cannot reach a gateway -- it imports none and
        # holds none. (The word appears in its docstring, saying exactly that.)
        self.assertFalse(hasattr(self.attention, "_gateway"))
        for line in inspect.getsource(attention_module).splitlines():
            if line.startswith(("import ", "from ")):
                self.assertNotIn("gateway", line)

    def test_12_the_aggregate_is_never_persisted(self):
        """CROSS_SCOPE_DATA_RULES §2/§3: ephemeral, and no client-identifying
        content written above the client scope. The only rows the gather adds
        anywhere are its per-scope audit records (I-49)."""
        self.seed_task(A, "a", "CLIENT-A-IDENTIFYING", "2026-08-17")
        before = self.sql("SELECT count(*) FROM item")[0][0]
        self.seam.home_page(self.sid)

        self.assertEqual(before, self.sql("SELECT count(*) FROM item")[0][0])
        # Nothing carrying the client's content was written to an ancestor.
        self.assertEqual([], self.sql(
            "SELECT scope_path, detail FROM audit_record"
            " WHERE detail LIKE %s", ("%CLIENT-A-IDENTIFYING%",)))
        # No aggregate table came into existence.
        self.assertEqual([], self.sql(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'"
            " AND tablename LIKE %s", ("%attention%",)))

    def test_13_each_scope_touched_is_recorded_in_its_own_partition(self):
        """I-49: recorded per scope touched -- N records in N scopes, never
        one record above them."""
        self.gather()
        rows = self.sql("SELECT scope_path FROM audit_record"
                        " WHERE detail LIKE 'attention%' ORDER BY scope_path")
        authorized = sorted(p for p in self.tree.paths()
                            if self.tree.find_grant("james", "read", "*", p))
        self.assertEqual([(p,) for p in authorized], rows)
        self.assertNotIn(PRIVATE, [r[0] for r in rows])

    def test_14_audit_records_are_not_aggregated_across_scopes(self):
        """I-67/I-89: cross-scope audit review requires step-up, which does
        not exist. The view must not read audit_record at all, and must say
        so rather than silently omitting it."""
        source = inspect.getsource(attention_module)
        self.assertNotIn("SELECT", source.split("INSERT INTO audit_record")[1]
                         if "INSERT INTO audit_record" in source else "SELECT")
        self.assertNotIn("FROM audit_record", source)

        self.seed_task(A, "a", "Something", "2026-08-17")
        _, page = self.seam.home_page(self.sid)
        self.assertIn("stronger sign-in", page)

    # =======================================================================
    # The page itself
    # =======================================================================

    def test_15_the_home_page_requires_a_session(self):
        self.assertEqual(401, self.seam.home_page(None)[0])
        self.assertEqual(401, self.seam.home_page("forged")[0])

    def test_16_a_quiet_nova_says_so(self):
        _, page = self.seam.home_page(self.sid)
        self.assertIn("Needs your attention", page)
        self.assertIn("Nothing right now", page)
        for area in ("LIFE", "BUSINESS", "WEALTH"):
            self.assertIn(area, page)

    def test_17_the_page_leaks_no_machinery(self):
        self.seed_approval(A, "ap-1", "Add a task")
        self.seed_task(A, "late", "Chase it", "2026-08-10")
        _, page = self.seam.home_page(self.sid)
        for marker in ("integrity", "trace_id", "set_config", "nova_app",
                       "nova_control", "session_ref", "select "):
            self.assertNotIn(marker, page.lower())

    def test_18_james_opens_nova_and_sees_what_matters(self):
        """The walk, over HTTP: one glance, then one click to the surface that
        can actually do something about it."""
        self.seed_approval(A, "ap-1", "Add task “Send the revised quote”, due 2026-08-21.")
        self.seed_task(B, "late", "Chase the overdue invoice", "2026-08-10")
        self.seed_task(LIFE, "dentist", "Book the dentist", "2026-08-18")

        server, port = serve(self.seam)
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/")
            req.add_header("Cookie", f"nova_session={self.sid}")
            with urllib.request.urlopen(req, timeout=10) as r:
                page = r.read().decode()

            self.assertIn("Needs your attention", page)
            self.assertIn("1 approval", page)
            self.assertIn("1 overdue", page)
            self.assertIn("1 due soon", page)
            # Each item says what, and where.
            self.assertIn("Send the revised quote", page)
            self.assertIn("BUSINESS / KAIRO / CLIENT A", page)
            self.assertIn("Chase the overdue invoice", page)
            self.assertIn("BUSINESS / KAIRO / CLIENT B", page)
            self.assertIn("Book the dentist", page)
            self.assertIn("LIFE", page)
            # Each routes to an existing surface.
            self.assertIn(f'href="/scope{A}/approvals"', page)
            self.assertIn(f'href="/scope{B}"', page)

            # And the link works: the approval is really there.
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/scope{A}/approvals")
            req.add_header("Cookie", f"nova_session={self.sid}")
            with urllib.request.urlopen(req, timeout=10) as r:
                self.assertIn("Send the revised quote", r.read().decode())
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
