"""What needs doing: tasks in a scope, end to end.

USER_INTERFACE_ARCHITECTURE section 3 names three views that cut across the
tree "because they answer questions James actually asks": what needs my
decision, what did NOVA do, and what needs doing. The first two were built.
This is the third.

The capability, in one sentence: **James asks NOVA what needs doing in the
scope he is standing in, asks for a task to be added or closed, sees exactly
what NOVA proposes, approves it, and the change lands through the same
authorization path as every other write.**

This suite adds only what the second and third consequence-producing tools
make newly provable:

  one approval does not cover another TOOL -- not just other arguments
  the envelope pins a task's DUE DATE, because a date is a commitment
  completion is EXECUTE-class: NOVA cannot close James's commitments alone
  task rows are isolated by RLS exactly as items are, including WITH CHECK
  a model naming a tool directly is prose, not a tool call

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_tasks
"""

from __future__ import annotations

import datetime
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

from .. import db, tree_store
from ..approval_flow import APPROVED, PENDING, ApprovalService
from ..boundary import DataAccessBoundary
from ..conversation import CONVERSATION_MODEL, PROVIDER, ConversationService
from ..seam import Seam, serve
from ..write_path import (ADD_TASK, COMPLETE_TASK, TOOL, ALL_TOOLS,
                          PostgresItemIntegration, WritePath)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.budget import BudgetLedger
from ...core.context_service import ContextService
from ...core.gateway import ModelGateway, ModelResponse, ProviderBinding
from ...core.policy import PolicyDecisionPoint
from ...core.store import StoreRegistry
from ...core.types import Classification, Denied, Risk, Taint
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture
from .test_conversation import ScriptedTransport

A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"
SCOPES = [("/business", "domain", None),
          ("/business/KAIRO", "business", "/business"),
          (A, "client", "/business/KAIRO"),
          (B, "client", "/business/KAIRO")]
GRANTS = [("james", "/business", "read"), ("james", "/business", "write")]


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class TaskTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-tasks-")
        self.context = ContextService(self.tree, secret=b"task-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=A,
                              permitted_operations=frozenset(t().name for t in ALL_TOOLS)),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        for tool in ALL_TOOLS:
            registry.register(tool())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")
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
                         tree=self.tree, conversation=self.conversation)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, scope=A, ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=frozenset({"write"}),
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

    def approve_only_pending(self):
        approval_id = self.sql("SELECT approval_id FROM approval"
                               " WHERE status='pending'")[0][0]
        return self.seam.decide_page(self.sid, A, approval_id, True)

    def add_task(self, ref="follow-up", title="Follow up on the proposal",
                 due="2026-08-21", scope=A):
        approval_id = self.approvals.propose_action(
            self.token(scope), scope, ADD_TASK,
            {"task_ref": ref, "title": title, "due_on": due},
            action_text=f"Add task “{title}”, due {due}.",
            if_wrong_text="A task you did not want appears in this scope.")
        self.approvals.decide(self.token(scope), approval_id, True, decided_by="james")

    # =======================================================================
    # The capability
    # =======================================================================

    def test_01_an_approved_task_lands_in_scope(self):
        self.add_task()
        self.assertEqual(
            [("follow-up", "Follow up on the proposal",
              datetime.date(2026, 8, 21), None, A)],
            self.sql("SELECT task_ref, title, due_on, done_at, scope_path FROM task"))

    def test_02_an_unapproved_task_does_not_land(self):
        """I-09 governs the new tools exactly as it governs the old one."""
        with self.assertRaises(Denied) as cm:
            self.writes.execute_action(self.token(), A, ADD_TASK,
                                       {"task_ref": "x", "title": "t", "due_on": ""})
        self.assertEqual("I-09", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM task"))
        self.assertEqual(0, self.integration.side_effects)

    def test_03_completion_is_execute_class_and_needs_approval(self):
        """NOVA does not get to quietly close James's commitments."""
        self.add_task()
        with self.assertRaises(Denied) as cm:
            self.writes.execute_action(self.token(), A, COMPLETE_TASK,
                                       {"task_ref": "follow-up"})
        self.assertEqual("I-09", cm.exception.invariant)
        self.assertEqual([(None,)], self.sql("SELECT done_at FROM task"))

        approval_id = self.approvals.propose_action(
            self.token(), A, COMPLETE_TASK, {"task_ref": "follow-up"},
            action_text="Mark task done.", if_wrong_text="Still outstanding.")
        status, _ = self.approvals.decide(self.token(), approval_id, True,
                                          decided_by="james")
        self.assertEqual(APPROVED, status)
        self.assertIsNotNone(self.sql("SELECT done_at FROM task")[0][0])

    def test_04_completing_twice_does_not_reclose(self):
        """`idempotent=True` is the provider's conditional UPDATE, not a claim:
        the second completion leaves the original timestamp alone."""
        self.add_task()
        for _ in range(2):
            approval_id = self.approvals.propose_action(
                self.token(), A, COMPLETE_TASK, {"task_ref": "follow-up"},
                action_text="Mark done.", if_wrong_text="x")
            self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        self.assertEqual(1, len(self.sql("SELECT 1 FROM task")))

    # =======================================================================
    # What the SECOND tool makes newly provable
    # =======================================================================

    def test_05_an_approval_for_one_tool_does_not_cover_another(self):
        """Previously only arguments could differ; now the TOOL can. Approving
        a note about 'follow-up' must not authorize completing a task called
        'follow-up' (I-109/I-112)."""
        self.add_task()
        note = self.approvals.propose(self.token(), A, "follow-up", "some prose")
        self.approvals.decide(self.token(), note, True, decided_by="james")

        # The note landed; the task is untouched.
        self.assertEqual([("follow-up",)],
                         self.sql("SELECT item_ref FROM item"))
        self.assertEqual([(None,)], self.sql("SELECT done_at FROM task"))

        # And executing the other tool with the same ref is still denied.
        with self.assertRaises(Denied) as cm:
            self.writes.execute_action(self.token(), A, COMPLETE_TASK,
                                       {"task_ref": "follow-up"})
        self.assertEqual("I-09", cm.exception.invariant)

    def test_06a_the_argument_envelope_pins_the_due_date(self):
        """A date is a commitment, so `due_on` is declared
        CONSEQUENCE-DETERMINING (ADR 0036 rule 2 makes that the default) and
        the envelope is built FROM THAT DECLARATION -- so I-100 pins the date
        to the approved value rather than leaving it free.

        Asserted on the envelope itself: the tamper test below is caught by
        I-112 first, so it would pass whatever the declaration said."""
        from ...core.types import ArgumentEnvelope
        captured = {}
        original = self.pdp.authorize_plan

        def spy(token, plan, bindings, envelope, **kw):
            captured["envelope"] = envelope
            return original(token, plan, bindings, envelope, **kw)

        self.pdp.authorize_plan = spy
        try:
            with self.assertRaises(Denied):      # unapproved: I-09
                self.writes.execute_action(
                    self.token(), A, ADD_TASK,
                    {"task_ref": "t", "title": "Follow up", "due_on": "2026-08-21"})
        finally:
            self.pdp.authorize_plan = original

        allowed = captured["envelope"].allowed_values
        self.assertEqual(frozenset({"2026-08-21"}), allowed.get("due_on"),
                         "the due date was not pinned by the envelope")
        self.assertEqual(frozenset({"t"}), allowed.get("task_ref"))
        # Prose is deliberately NOT pinned -- MT-5, same ruling as write_item.
        self.assertNotIn("title", allowed)

    def test_06b_a_tampered_due_date_cannot_execute(self):
        """And the stored arguments ARE the plan: changing the date after the
        fact no longer hashes to what James approved (I-112)."""
        approval_id = self.approvals.propose_action(
            self.token(), A, ADD_TASK,
            {"task_ref": "t", "title": "Follow up", "due_on": "2026-08-21"},
            action_text="Add task.", if_wrong_text="x")
        self.sql("UPDATE approval SET arguments = %s WHERE approval_id = %s",
                 ('{"task_ref": "t", "title": "Follow up", "due_on": "2026-12-25"}',
                  approval_id))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM task"))

    def test_07_task_rows_are_isolated_by_rls(self):
        self.add_task()
        with self.boundary.open(self.token(B)) as ch:
            self.assertEqual([], ch.fetch("SELECT task_ref FROM task"))
        with self.boundary.open(self.token(A)) as ch:
            self.assertEqual([("follow-up",)], ch.fetch("SELECT task_ref FROM task"))

    def test_08_a_hostile_channel_cannot_plant_a_task_in_the_sibling(self):
        import psycopg2
        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(self.token(A)) as ch:
                ch.execute("INSERT INTO task (task_ref, scope_path, title)"
                           " VALUES ('planted', %s, 'HOSTILE')", (B,))
        self.assertEqual([], self.sql("SELECT 1 FROM task WHERE scope_path=%s", (B,)))

    def test_09_the_task_write_is_audited(self):
        self.add_task()
        self.assertEqual(
            [("W-1", "data.write", A, "james", "add_task task_ref=follow-up")],
            self.sql("SELECT writer, category, scope_path, actor_ref, detail"
                     " FROM audit_record WHERE category='data.write'"))

    # =======================================================================
    # Through conversation, which is how James will actually use it
    # =======================================================================

    def test_10_nova_proposes_a_task_and_it_needs_approval(self):
        self.transport.replies.append(
            'I will note that down. [[PROPOSE_TASK ref="call-back" '
            'title="Call the client back" due="2026-08-21"]]')
        status, page = self.seam.talk_post(self.sid, A, "remind me to call them back friday")
        self.assertEqual(200, status)
        self.assertIn("I need your approval", page)
        self.assertEqual([], self.sql("SELECT 1 FROM task"))

        rows = self.sql("SELECT tool_name, action_text, status FROM approval")
        self.assertEqual([(ADD_TASK, "Add task “Call the client back”, due 2026-08-21.",
                           PENDING)], rows)

        # James approves on the existing surface; the task lands.
        self.approve_only_pending()
        self.assertEqual([("call-back", datetime.date(2026, 8, 21))],
                         self.sql("SELECT task_ref, due_on FROM task"))

    def test_11_nova_proposes_completion_from_a_task_it_can_see(self):
        self.add_task(ref="call-back", title="Call the client back")
        self.transport.replies.append('Marking it. [[COMPLETE_TASK ref="call-back"]]')
        status, page = self.seam.talk_post(self.sid, A, "i called them, mark it done")
        self.assertEqual(200, status)
        self.assertIn("I need your approval", page)
        self.assertEqual([(None,)], self.sql("SELECT done_at FROM task"))

        self.approve_only_pending()
        self.assertIsNotNone(self.sql("SELECT done_at FROM task")[0][0])

    def test_12_open_tasks_reach_the_model_and_the_sibling_s_do_not(self):
        self.add_task(ref="mine", title="Mine to do")
        # Seeded out of band: the credential binding is per-scope (I-24), so
        # writing into B would need B's own binding. The claim under test is
        # what reaches the PROMPT, not how the row got there.
        self.sql("INSERT INTO task (task_ref, scope_path, title)"
                 " VALUES ('theirs', %s, 'SIBLING-TASK-MATERIAL')", (B,))
        self.seam.talk_post(self.sid, A, "what needs doing?")
        prompt = self.transport.prompts[-1]
        self.assertIn("Mine to do", prompt)
        self.assertNotIn("SIBLING-TASK-MATERIAL", prompt)

    def test_13_a_model_naming_a_tool_directly_is_prose(self):
        """The markers are the ONLY structured thing read from model output.
        A model writing what looks like a tool call is text."""
        for hostile in ('[[COMPLETE_TASK ref="../../admin"]]',
                        '[[PROPOSE_TASK ref="x" title="t" due="whenever"]]',
                        '[[EXECUTE tool="complete_task" ref="follow-up"]]',
                        '{"tool":"complete_task","task_ref":"follow-up"}'):
            self.transport.replies.append(hostile)
            self.assertEqual(200, self.seam.talk_post(self.sid, A, "do it")[0])
        self.assertEqual([], self.sql("SELECT 1 FROM approval"))
        self.assertEqual([], self.sql("SELECT 1 FROM task"))

    def test_14_marker_text_is_never_shown_to_james(self):
        self.transport.replies.append(
            'Noted. [[PROPOSE_TASK ref="a" title="Do it" due=""]]')
        _, page = self.seam.talk_post(self.sid, A, "add a task")
        self.assertNotIn("PROPOSE_TASK", page)
        self.assertIn("Noted.", page)

    # =======================================================================
    # The scope page
    # =======================================================================

    def test_15_the_scope_page_shows_what_needs_doing(self):
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        self.add_task(ref="late", title="Overdue thing", due=yesterday)
        self.add_task(ref="undated", title="Someday thing", due="")

        _, page = self.seam.scope_page(self.sid, A)
        self.assertIn("What needs doing", page)
        self.assertIn("Overdue thing", page)
        self.assertIn("overdue", page)
        self.assertIn("Someday thing", page)
        self.assertIn("no date", page)

    def test_16_a_completed_task_leaves_the_list(self):
        self.add_task()
        self.assertIn("Follow up on the proposal", self.seam.scope_page(self.sid, A)[1])
        approval_id = self.approvals.propose_action(
            self.token(), A, COMPLETE_TASK, {"task_ref": "follow-up"},
            action_text="Mark done.", if_wrong_text="x")
        self.approvals.decide(self.token(), approval_id, True, decided_by="james")

        _, page = self.seam.scope_page(self.sid, A)
        self.assertNotIn("Follow up on the proposal", page)
        self.assertIn("Nothing to do here", page)

    def test_17_an_empty_scope_says_so(self):
        _, page = self.seam.scope_page(self.sid, B)
        self.assertIn("Nothing to do here", page)

    # =======================================================================
    # The walk
    # =======================================================================

    def test_18_james_asks_nova_to_remember_something_and_closes_it(self):
        self.transport.replies = [
            'Nothing is outstanding here yet.',
            'I will track that. [[PROPOSE_TASK ref="send-quote" '
            'title="Send the revised quote" due="2026-08-21"]]',
            'Marking it done. [[COMPLETE_TASK ref="send-quote"]]',
        ]
        server, port = serve(self.seam)
        try:
            def http(method, path, form=None):
                data = urllib.parse.urlencode(form).encode() if form else None
                req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                             data=data, method=method)
                req.add_header("Cookie", f"nova_session={self.sid}")
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status, r.read().decode()
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode()

            _, page = http("POST", f"/scope{A}/talk", {"message": "what needs doing?"})
            self.assertIn("Nothing is outstanding", page)

            _, page = http("POST", f"/scope{A}/talk",
                           {"message": "remind me to send the revised quote friday"})
            self.assertIn("I need your approval", page)

            _, approvals = http("GET", f"/scope{A}/approvals")
            self.assertIn("Send the revised quote", approvals)
            self.assertIn("2026-08-21", approvals)
            approval_id = self.sql("SELECT approval_id FROM approval"
                                   " WHERE status='pending'")[0][0]
            http("POST", f"/scope{A}/approvals/{approval_id}", {"decision": "approve"})

            _, scope = http("GET", f"/scope{A}")
            self.assertIn("What needs doing", scope)
            self.assertIn("Send the revised quote", scope)

            # ...and closing it is its own approved action.
            _, page = http("POST", f"/scope{A}/talk", {"message": "sent it"})
            self.assertIn("I need your approval", page)
            approval_id = self.sql("SELECT approval_id FROM approval"
                                   " WHERE status='pending'")[0][0]
            http("POST", f"/scope{A}/approvals/{approval_id}", {"decision": "approve"})

            _, scope = http("GET", f"/scope{A}")
            self.assertIn("Nothing to do here", scope)
            self.assertIn("add_task", scope)        # both actions in the activity log
            self.assertIn("complete_task", scope)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
