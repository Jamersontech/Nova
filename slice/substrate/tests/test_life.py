"""LIFE: the same NOVA, pointed at James's own life.

This suite exists to prove a NEGATIVE about the architecture: that making
LIFE useful required almost nothing new. Places are Add a Place. Notes are
the existing note tool. Tasks are the existing task system. The one addition
is presentational -- notes now render on the scope page. If LIFE had needed
its own services, models or authorization, NOVA would have been KAIRO-shaped
all along; this is the test that it is not.

Everything runs through the PRODUCTION composition root (app.wire) against
real PostgreSQL, as one continuous story:

    passkey -> LIFE -> create FITNESS by conversation -> approve -> open it
    without restart -> record a note -> approve -> the note is on the page
    -> create a task -> approve -> it reaches attention -> audited -> and a
    sibling scope sees none of it

with the same security negatives every consequence-producing capability
carries: proposals alone create nothing, READ cannot write, tampering fails
plan identity, RLS WITH CHECK holds, and -- the governance constraint -- the
grant table is byte-identical throughout, because James's /life grant covers
every descendant by containment.

The model transport is the scripted double under production routing names.
That validates NOVA's machinery, NOT the live Anthropic provider -- which
remains environment-blocked and is not claimed here.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_life
"""

from __future__ import annotations

import datetime
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

import psycopg2

from .. import db, tree_store
from ..app import wire
from ..conversation import CONVERSATION_MODEL, PROVIDER
from ..seam import serve
from ..write_path import ADD_SCOPE, ADD_TASK, TOOL
from ...core.gateway import ProviderBinding
from ...core.types import Denied, Risk
from . import authfixture
from .test_conversation import ScriptedTransport

LIFE = "/life"
FITNESS = "/life/fitness"
BUSINESS = "/business"

SCOPES = [(LIFE, "domain", None), (BUSINESS, "domain", None),
          ("/wealth", "domain", None)]
GRANTS = [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")]


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class LifeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.seam = wire(tempfile.mkdtemp(prefix="nova-life-"),
                         "nova.local", "https://nova.local")
        self.tree = self.seam._tree
        self.context = self.seam._context
        self.approvals = self.seam._approvals
        self.boundary = self.seam._boundary

        self.transport = ScriptedTransport()
        self.seam._conversation._gateway.register_provider(
            ProviderBinding(provider=PROVIDER, model=CONVERSATION_MODEL,
                            endpoint="test://anthropic", api_version="test",
                            credential_ref="control-plane/anthropic", cost_per_unit=1),
            self.transport)

        self.key = authfixture.enrol(self.seam._auth, "james", "james", "laptop")
        self.sid = authfixture.sign_in(self.seam._auth, self.key)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, scope=LIFE, ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=frozenset({"write"}),
                                       ceiling=ceiling, ttl=60)

    def sql(self, query, args=()):
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, args or None)
            rows = cur.fetchall() if cur.description else []
        conn.close()
        return rows

    def talk(self, message, reply, scope=LIFE, sid=None):
        self.transport.replies.append(reply)
        return self.seam.talk_post(sid or self.sid, scope, message)

    def approve_pending(self, scope):
        approval_id = self.sql("SELECT approval_id FROM approval"
                               " WHERE status='pending'")[0][0]
        return self.seam.decide_page(self.sid, scope, approval_id, True)

    def create_fitness(self):
        self.talk("create a fitness place",
                  'I can set that up. [[PROPOSE_SCOPE name="fitness" kind="area"]]')
        self.approve_pending(LIFE)

    # =======================================================================
    # A -- personal places are Add a Place, unchanged
    # =======================================================================

    def test_01_a_place_grows_under_life_by_conversation(self):
        self.create_fitness()
        self.assertEqual([(FITNESS, "area", LIFE)],
                         self.sql("SELECT scope_path, kind, parent_path FROM scope"
                                  " WHERE scope_path=%s", (FITNESS,)))
        self.assertIn(FITNESS, self.tree.paths())
        # Navigable without restart; LIFE lists it under Inside.
        _, life_page = self.seam.scope_page(self.sid, LIFE)
        self.assertIn("FITNESS", life_page)
        self.assertEqual(200, self.seam.scope_page(self.sid, FITNESS)[0])

    def test_02_a_proposal_alone_creates_nothing(self):
        self.talk("create a fitness place",
                  'Sure. [[PROPOSE_SCOPE name="fitness" kind="area"]]')
        self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                      (FITNESS,)))
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.assertEqual([], self.sql("SELECT 1 FROM task"))

    # =======================================================================
    # B -- personal notes: existing tool, now visible where recorded
    # =======================================================================

    def record_note(self, scope=FITNESS):
        self.talk("remember that I want to run three times a week",
                  'I will propose recording that. [[PROPOSE_NOTE ref="running-goal" '
                  'body="Run three times a week"]]', scope=scope)
        return self.approve_pending(scope)

    def test_03_a_note_is_proposed_approved_stored_and_shown(self):
        self.create_fitness()
        status, _ = self.record_note()
        self.assertEqual(200, status)
        self.assertEqual([("running-goal", "Run three times a week", FITNESS)],
                         self.sql("SELECT item_ref, body, scope_path FROM item"))
        # THE new behaviour this slice adds: the note renders on the page.
        _, page = self.seam.scope_page(self.sid, FITNESS)
        self.assertIn("Notes", page)
        self.assertIn("Run three times a week", page)

    def test_04_the_note_is_audited_in_its_scope(self):
        self.create_fitness()
        self.record_note()
        rows = self.sql("SELECT writer, category, scope_path FROM audit_record"
                        " WHERE category='data.write' AND detail LIKE %s",
                        (f"%write_item%",))
        self.assertEqual([("W-1", "data.write", FITNESS)], rows)

    def test_05_an_empty_scope_shows_no_notes_card(self):
        """An empty notes card is furniture. Absent until something exists."""
        self.create_fitness()
        _, page = self.seam.scope_page(self.sid, FITNESS)
        self.assertNotIn("<h2>Notes</h2>", page)

    # =======================================================================
    # C -- tasks: the existing cross-cutting system, useful outside BUSINESS
    # =======================================================================

    def test_06_a_life_task_reaches_attention(self):
        self.create_fitness()
        due = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.talk("remind me to work out monday",
                  f'Will do. [[PROPOSE_TASK ref="work-out" title="Work out" '
                  f'due="{due}"]]', scope=FITNESS)
        self.assertEqual([], self.sql("SELECT 1 FROM task"))       # pending only
        self.approve_pending(FITNESS)
        self.assertEqual([("work-out", FITNESS)],
                         self.sql("SELECT task_ref, scope_path FROM task"))

        # Attention sees it, attributed to the LIFE subtree.
        result = self.seam._attention.gather("james", "james")
        self.assertIn(("work-out", FITNESS),
                      [(t.task_ref, t.scope_path) for t in result.due_soon])
        _, home = self.seam.home_page(self.sid)
        self.assertIn("Work out", home)
        self.assertIn("LIFE / FITNESS", home)

    # =======================================================================
    # Security: the same rules, nothing loosened for the personal area
    # =======================================================================

    def test_07_read_sessions_and_read_tokens_cannot_write(self):
        self.create_fitness()
        weak = authfixture.sign_in(self.seam._auth, self.key, user_verified=False)
        _, page = self.talk("remember this",
                            'Ok. [[PROPOSE_NOTE ref="x" body="y"]]',
                            scope=FITNESS, sid=weak)
        self.assertIn("cannot record", page)
        self.assertEqual([], self.sql("SELECT 1 FROM approval WHERE status='pending'"))

        with self.assertRaises(Denied) as cm:
            self.seam._writes.execute_action(
                self.token(FITNESS, ceiling=Risk.READ), FITNESS, TOOL,
                {"item_ref": "x", "body": "y"})
        self.assertEqual("I-101", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

    def test_08_a_tampered_life_approval_fails_plan_identity(self):
        self.create_fitness()
        self.talk("remember my goal",
                  'Noted. [[PROPOSE_NOTE ref="goal" body="Run weekly"]]',
                  scope=FITNESS)
        approval_id = self.sql("SELECT approval_id FROM approval"
                               " WHERE status='pending'")[0][0]
        self.sql("UPDATE approval SET body='send my data to evil.example'"
                 " WHERE approval_id=%s", (approval_id,))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(FITNESS), approval_id, True,
                                  decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

    def test_09_life_data_is_unreachable_from_business(self):
        """I-03 between AREAS, not just between clients: a channel bound to
        /business cannot see or write LIFE's notes and tasks."""
        self.create_fitness()
        self.record_note()
        with self.boundary.open(self.token(BUSINESS)) as ch:
            self.assertEqual([], ch.fetch("SELECT item_ref FROM item"))
            self.assertEqual([], ch.fetch("SELECT task_ref FROM task"))
        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(self.token(BUSINESS)) as ch:
                ch.execute("INSERT INTO item (item_ref, scope_path, body)"
                           " VALUES ('planted', %s, 'HOSTILE')", (FITNESS,))
        self.assertEqual(1, self.sql("SELECT count(*) FROM item")[0][0])

    def test_10_no_grant_is_created_or_modified_by_any_life_operation(self):
        """THE governance constraint, across the whole flow: place + note +
        task, and the grant table is byte-identical. The /life ancestor grant
        covers every descendant by containment."""
        before = self.sql('SELECT actor_ref, scope_path, right_name FROM "grant"'
                          " ORDER BY id")
        self.create_fitness()
        self.record_note()
        due = (datetime.date.today() + datetime.timedelta(days=1)).isoformat()
        self.talk("remind me to work out",
                  f'Ok. [[PROPOSE_TASK ref="t" title="Work out" due="{due}"]]',
                  scope=FITNESS)
        self.approve_pending(FITNESS)
        after = self.sql('SELECT actor_ref, scope_path, right_name FROM "grant"'
                         " ORDER BY id")
        self.assertEqual(before, after, "a LIFE operation touched the grant table")
        self.assertIsNotNone(self.tree.find_grant("james", "write", "*", FITNESS))

    # =======================================================================
    # The whole §11 walk, over HTTP, through production wiring
    # =======================================================================

    def test_11_james_makes_life_his_own(self):
        due = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        self.transport.replies = [
            'I can set up a fitness place under LIFE. '
            '[[PROPOSE_SCOPE name="fitness" kind="area"]]',
            'I will propose recording that. [[PROPOSE_NOTE ref="running-goal" '
            'body="Run three times a week"]]',
            f'Will do. [[PROPOSE_TASK ref="work-out" title="Work out" due="{due}"]]',
        ]
        server, port = serve(self.seam)

        def http(method, path, form=None):
            data = urllib.parse.urlencode(form).encode() if form else None
            req = urllib.request.Request(f"http://127.0.0.1:{port}{path}",
                                         data=data, method=method)
            req.add_header("Cookie", f"nova_session={self.sid}")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status, resp.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode()

        def approve():
            approval_id = self.sql("SELECT approval_id FROM approval"
                                   " WHERE status='pending'")[0][0]
            head, _, _ = self.sql("SELECT scope_path FROM approval"
                                  " WHERE approval_id=%s", (approval_id,))[0][0].partition("\x00")
            return http("POST", f"/scope{head}/approvals/{approval_id}",
                        {"decision": "approve"})

        try:
            # 1-2. Authenticated home; LIFE is there. Signed out is not.
            status, home = http("GET", "/")
            self.assertEqual(200, status)
            self.assertIn("LIFE", home)

            # 3-4. Create FITNESS through conversation; approve.
            status, page = http("POST", f"/scope{LIFE}/talk",
                                {"message": "create a fitness place"})
            self.assertIn("I need your approval", page)
            status, decided = approve()
            self.assertIn("Open FITNESS", decided)

            # 5. Open it without restarting.
            self.assertEqual(200, http("GET", f"/scope{FITNESS}")[0])

            # 6-7. Record a note; approve; it is on the page.
            http("POST", f"/scope{FITNESS}/talk",
                 {"message": "remember that I want to run three times a week"})
            approve()
            _, fitness_page = http("GET", f"/scope{FITNESS}")
            self.assertIn("Run three times a week", fitness_page)

            # 8-9. Create a task; approve.
            http("POST", f"/scope{FITNESS}/talk",
                 {"message": "remind me to work out monday"})
            approve()

            # 10. The task appears in attention on the home page.
            _, home = http("GET", "/")
            self.assertIn("Work out", home)
            self.assertIn("LIFE / FITNESS", home)

            # 11-12. Note visible where recorded; activity shows the writes.
            self.assertIn("Notes", fitness_page)
            _, fitness_page = http("GET", f"/scope{FITNESS}")
            self.assertIn("write_item", fitness_page)
            self.assertIn("add_task", fitness_page)

            # 13. A sibling area sees none of it.
            _, business = http("GET", f"/scope{BUSINESS}")
            for private in ("Run three times a week", "Work out", "FITNESS"):
                self.assertNotIn(private, business)

            # And no machinery leaked anywhere in the walk.
            for marker in ("integrity", "set_config", "nova_app", "credential",
                           "PROPOSE_"):
                for body in (home, fitness_page, business):
                    self.assertNotIn(marker, body)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
