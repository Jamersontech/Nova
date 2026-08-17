"""Add a place: NOVA's tree grows by conversation -- end to end.

The capability, in one sentence: James mentions a new client, area or
account; NOVA proposes creating a scope for it; he approves the exact
action; the scope exists, is immediately navigable, and every existing
capability works inside it.

What this suite is actually guarding, in order of importance:

  STRUCTURE IS SECURITY. The scope tree is the permission boundary, so
  growing it is the most consequence-laden write NOVA performs. The
  authorization is the ENGINE's: WITH CHECK on the `scope` table refuses a
  child anywhere the channel's binding does not cover -- a sibling's
  subtree, an ungranted root, a brand-new root. Proven with hostile
  channels and a disable/re-enable negative control, because a test that
  cannot fail open proves nothing.

  NO GRANT IS TOUCHED (the hard governance constraint). James's ancestor
  grant covers the new descendant by containment. Asserted directly: the
  grant table is byte-identical before and after creation, and the module
  under test has no path to it.

  THE MODEL PROPOSES, JAMES DECIDES. A marker is a pending approval and
  nothing else; malformed markers are prose; a tampered approval fails
  I-112; approval for one parent covers no other.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_add_scope
"""

from __future__ import annotations

import os
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
from ..write_path import ADD_SCOPE, ADD_TASK
from ...core.gateway import ProviderBinding
from ...core.types import Denied, Risk
from . import authfixture
from .test_conversation import ScriptedTransport

KAIRO = "/business/KAIRO"
OTHER = "/business/other-client"
NEW = f"{KAIRO}/meridian"

SCOPES = [("/life", "domain", None), ("/business", "domain", None),
          ("/wealth", "domain", None), ("/private", "domain", None),
          (KAIRO, "business", "/business"), (OTHER, "client", "/business")]
GRANTS = [("james", p, r) for p in ("/life", "/business", "/wealth")
          for r in ("read", "write")]


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class AddScopeTest(unittest.TestCase):
    """Wired through the PRODUCTION composition root (app.wire), because the
    post-commit hook that makes a new scope immediately usable lives there,
    and a suite that bypassed it would prove a path James never runs."""

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.seam = wire(tempfile.mkdtemp(prefix="nova-addscope-"),
                         "nova.local", "https://nova.local")
        self.tree = self.seam._tree
        self.context = self.seam._context
        self.approvals = self.seam._approvals
        self.writes = self.seam._writes
        self.boundary = self.seam._boundary

        # The gateway double: production routing names, scripted transport.
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

    def token(self, scope=KAIRO, ceiling=Risk.EXECUTE):
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

    def propose(self, name="meridian", kind="client", parent=KAIRO):
        return self.approvals.propose_action(
            self.token(parent), parent, ADD_SCOPE,
            {"scope_name": name, "kind": kind},
            action_text=f"Create “{name}” as a new place in this scope.",
            if_wrong_text="An empty place exists that you can simply ignore.")

    def talk(self, message, reply=None, sid=None, scope=KAIRO):
        if reply is not None:
            self.transport.replies.append(reply)
        return self.seam.talk_post(sid or self.sid, scope, message)

    def http(self, method, path, form=None):
        data = urllib.parse.urlencode(form).encode() if method == "POST" else None
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data, method=method)
        req.add_header("Cookie", f"nova_session={self.sid}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    # =======================================================================
    # 00 -- negative control: WITH CHECK on `scope` is load-bearing
    # =======================================================================

    def test_00_negative_control_with_check_is_what_refuses_hostile_creation(self):
        """Disable RLS on `scope` mid-run: the hostile creation SUCCEEDS.
        Restore it: refused again. Without this, every refusal below could be
        an accident of the fixture rather than the engine deciding."""
        hostile = f"{OTHER}/planted"
        self.sql("ALTER TABLE scope DISABLE ROW LEVEL SECURITY")
        try:
            with self.boundary.open(self.token(KAIRO)) as ch:
                ch.execute("INSERT INTO scope (scope_path, kind) VALUES (%s,'x')",
                           (hostile,))
            self.assertEqual(1, self.sql("SELECT count(*) FROM scope"
                                         " WHERE scope_path=%s", (hostile,))[0][0],
                             "RLS disabled and nothing leaked -- this control "
                             "is not testing what it claims")
        finally:
            self.sql("DELETE FROM scope WHERE scope_path=%s", (hostile,))
            self.sql("ALTER TABLE scope ENABLE ROW LEVEL SECURITY")
            self.sql("ALTER TABLE scope FORCE ROW LEVEL SECURITY")

        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(self.token(KAIRO)) as ch:
                ch.execute("INSERT INTO scope (scope_path, kind) VALUES (%s,'x')",
                           (hostile,))
        self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                      (hostile,)))

    # =======================================================================
    # 1-3 -- propose, then approve, and only then create
    # =======================================================================

    def test_01_conversation_produces_a_scope_proposal(self):
        status, page = self.talk(
            "we just signed a new client, Meridian",
            'Congratulations. I can set up a place for them. '
            '[[PROPOSE_SCOPE name="meridian" kind="client"]]')
        self.assertEqual(200, status)
        self.assertIn("I need your approval", page)
        rows = self.sql("SELECT tool_name, status, arguments->>'scope_name'"
                        " FROM approval")
        self.assertEqual([(ADD_SCOPE, "pending", "meridian")], rows)

    def test_02_a_proposal_alone_creates_nothing(self):
        self.talk("new client meridian",
                  'Noted. [[PROPOSE_SCOPE name="meridian" kind="client"]]')
        self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                      (NEW,)))
        self.assertNotIn(NEW, self.tree.paths())

    def test_03_approval_creates_the_exact_requested_child(self):
        approval_id = self.propose()
        status, outcome = self.approvals.decide(self.token(), approval_id, True,
                                                decided_by="james")
        self.assertEqual("approved", status)
        self.assertEqual([(NEW, "client", KAIRO)],
                         self.sql("SELECT scope_path, kind, parent_path FROM scope"
                                  " WHERE scope_path=%s", (NEW,)))

    # =======================================================================
    # 4-6 -- the decision binds one exact action, made with enough strength
    # =======================================================================

    def test_04_an_approval_for_one_parent_covers_no_other(self):
        """Approve creating 'meridian' under KAIRO; executing the same name
        under /life is a DIFFERENT plan and is denied on I-09."""
        approval_id = self.propose(parent=KAIRO)
        self.approvals.decide(self.token(KAIRO), approval_id, True, decided_by="james")
        with self.assertRaises(Denied) as cm:
            self.writes.execute_action(self.token("/life"), "/life", ADD_SCOPE,
                                       {"scope_name": "meridian", "kind": "client"})
        self.assertEqual("I-09", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM scope"
                                      " WHERE scope_path=%s", ("/life/meridian",)))

    def test_05_a_tampered_approval_is_rejected_by_plan_identity(self):
        """Swap the stored name for a hostile one; the reconstructed plan no
        longer hashes to what James saw (I-112)."""
        approval_id = self.propose()
        self.sql("UPDATE approval SET arguments = %s WHERE approval_id = %s",
                 ('{"scope_name": "evil", "kind": "client"}', approval_id))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        for path in (NEW, f"{KAIRO}/evil"):
            self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                          (path,)))

    def test_06_a_read_level_session_cannot_create_a_scope(self):
        """Two halves. A READ-ceiling token is denied by the PDP (I-101), and
        a single-factor session cannot even record the proposal (A-1)."""
        approval_id = self.propose()
        self.approvals._writes.approvals.james_approves(  # approval exists...
            self.writes.plan_for_action(KAIRO, ADD_SCOPE,
                                        {"scope_name": "meridian",
                                         "kind": "client"}).identity())
        with self.assertRaises(Denied) as cm:
            self.writes.execute_action(self.token(ceiling=Risk.READ), KAIRO,
                                       ADD_SCOPE, {"scope_name": "meridian",
                                                   "kind": "client"})
        self.assertEqual("I-101", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s", (NEW,)))

        weak = authfixture.sign_in(self.seam._auth, self.key, user_verified=False)
        _, page = self.talk("new client meridian",
                            'Sure. [[PROPOSE_SCOPE name="m2" kind="client"]]',
                            sid=weak)
        self.assertIn("cannot record", page)
        self.assertEqual([], self.sql("SELECT 1 FROM approval"
                                      " WHERE arguments->>'scope_name'='m2'"))

    # =======================================================================
    # 7-9 -- the engine is the authority over where the tree may grow
    # =======================================================================

    def test_07_hostile_channel_cannot_create_a_child_beneath_a_sibling(self):
        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(self.token(KAIRO)) as ch:
                ch.execute("INSERT INTO scope (scope_path, kind) VALUES (%s,'x')",
                           (f"{OTHER}/planted",))
        self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                      (f"{OTHER}/planted",)))

    def test_08_hostile_channel_cannot_create_an_unrelated_root(self):
        for hostile in ("/wealth2", "/private/planted"):
            with self.assertRaises(psycopg2.Error, msg=hostile):
                with self.boundary.open(self.token(KAIRO)) as ch:
                    ch.execute("INSERT INTO scope (scope_path, kind) VALUES (%s,'x')",
                               (hostile,))
            self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                          (hostile,)))

    def test_09_the_transport_cannot_be_pointed_at_another_parent(self):
        """Structural, not behavioural: the transport derives the child from
        the CHANNEL's scope. There is no payload field that names a parent,
        so there is nothing for a compromised caller to override."""
        import inspect
        from .. import write_path
        source = inspect.getsource(write_path.PostgresItemIntegration.transport_for)
        self.assertIn('f"{ch.scope_path}/{ref}"', source)
        self.assertNotIn('payload["parent', source)

    # =======================================================================
    # 10-12 -- names, idempotency, audit, and the grant table untouched
    # =======================================================================

    def test_10_malformed_names_are_rejected_at_both_layers(self):
        # Marker layer: hostile names are prose, no approval exists.
        for hostile in ('[[PROPOSE_SCOPE name="../../etc" kind="client"]]',
                        '[[PROPOSE_SCOPE name="a/b" kind="client"]]',
                        '[[PROPOSE_SCOPE name="UPPER" kind="client"]]',
                        '[[PROPOSE_SCOPE name="x" kind="anything"]]',
                        '[[PROPOSE_SCOPE name="" kind="client"]]'):
            self.talk("make it", hostile)
        self.assertEqual([], self.sql("SELECT 1 FROM approval"))

        # Transport layer: a directly proposed hostile name is refused even
        # WITH approval -- "the marker was strict" is not this layer's excuse.
        approval_id = self.propose(name="evil/child")
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        self.assertEqual("I-100", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM scope"
                                      " WHERE scope_path LIKE %s", (f"{KAIRO}/evil%",)))

    def test_11_duplicate_creation_is_idempotent(self):
        for _ in range(2):
            approval_id = self.propose()
            self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        self.assertEqual(1, self.sql("SELECT count(*) FROM scope"
                                     " WHERE scope_path=%s", (NEW,))[0][0])

    def test_12_creation_is_audited_in_the_parent_scope(self):
        approval_id = self.propose()
        self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        rows = self.sql("SELECT writer, category, scope_path, actor_ref, detail"
                        " FROM audit_record WHERE category='data.write'")
        self.assertEqual(1, len(rows))
        self.assertEqual(("W-1", "data.write", KAIRO, "james"), rows[0][:4])
        self.assertIn(f"scope={NEW}", rows[0][4])

    def test_12b_no_grant_is_created_or_modified(self):
        """THE governance constraint. The grant table is identical before and
        after, and the new scope is reachable anyway -- because James's
        ancestor grant covers it by containment, not because anything was
        widened."""
        before = self.sql('SELECT actor_ref, scope_path, right_name FROM "grant"'
                          " ORDER BY id")
        approval_id = self.propose()
        self.approvals.decide(self.token(), approval_id, True, decided_by="james")
        after = self.sql('SELECT actor_ref, scope_path, right_name FROM "grant"'
                         " ORDER BY id")
        self.assertEqual(before, after, "scope creation touched the grant table")
        self.assertIsNotNone(self.tree.find_grant("james", "write", "*", NEW))

    # =======================================================================
    # 13-16 -- the new scope is immediately REAL
    # =======================================================================

    def create_meridian(self):
        approval_id = self.propose()
        self.approvals.decide(self.token(), approval_id, True, decided_by="james")

    def test_13_the_new_scope_is_navigable_without_restart(self):
        self.create_meridian()
        self.assertIn(NEW, self.tree.paths())
        _, kairo_page = self.seam.scope_page(self.sid, KAIRO)
        self.assertIn("MERIDIAN", kairo_page)
        status, page = self.seam.scope_page(self.sid, NEW)
        self.assertEqual(200, status)
        self.assertIn("Nothing to do here", page)

    def test_14_conversation_works_inside_the_new_scope_immediately(self):
        self.create_meridian()
        status, page = self.talk("what is going on here?",
                                 "Nothing yet -- this place was just created.",
                                 scope=NEW)
        self.assertEqual(200, status)
        self.assertIn("just created", page)
        # And the prompt was bound to the NEW scope, not the parent.
        self.assertIn(f"Scope: {NEW}", self.transport.prompts[-1])

    def test_15_tasks_work_inside_the_new_scope(self):
        self.create_meridian()
        self.talk("remind me to send the onboarding pack friday",
                  'Will do. [[PROPOSE_TASK ref="onboarding" '
                  'title="Send the onboarding pack" due="2026-08-21"]]',
                  scope=NEW)
        approval_id = self.sql("SELECT approval_id FROM approval"
                               " WHERE status='pending' AND tool_name=%s",
                               (ADD_TASK,))[0][0]
        status, _ = self.seam.decide_page(self.sid, NEW, approval_id, True)
        self.assertEqual(200, status)
        self.assertEqual([("onboarding", NEW)],
                         self.sql("SELECT task_ref, scope_path FROM task"))

    def test_16_the_whole_walk_over_http(self):
        """James's actual experience, through the production wiring: mention
        the client, review the exact action, approve, open the door, use it."""
        self.transport.replies = [
            'Congratulations. I can set up a place for Meridian under KAIRO. '
            '[[PROPOSE_SCOPE name="meridian" kind="client"]]',
            'Nothing here yet. What should we set up first?',
        ]
        server, self.port = serve(self.seam)
        try:
            # Mention the client in conversation.
            status, page = self.http("POST", f"/scope{KAIRO}/talk",
                                     {"message": "we just signed a new client, Meridian"})
            self.assertEqual(200, status)
            self.assertIn("I need your approval", page)
            self.assertNotIn("PROPOSE_SCOPE", page)     # marker never shown

            # The approval card states the exact action, and nothing exists yet.
            _, approvals_page = self.http("GET", f"/scope{KAIRO}/approvals")
            self.assertIn("Create “meridian” as a new place", approvals_page)
            self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                          (NEW,)))

            # Approve. The response offers a door into the new place.
            approval_id = self.sql("SELECT approval_id FROM approval")[0][0]
            status, decided = self.http("POST",
                                        f"/scope{KAIRO}/approvals/{approval_id}",
                                        {"decision": "approve"})
            self.assertEqual(200, status)
            self.assertIn(f'href="/scope{NEW}"', decided)
            self.assertIn("Open MERIDIAN", decided)

            # KAIRO lists it under Inside; the new scope opens; talking works.
            _, kairo = self.http("GET", f"/scope{KAIRO}")
            self.assertIn("MERIDIAN", kairo)
            status, _ = self.http("GET", f"/scope{NEW}")
            self.assertEqual(200, status)
            status, page = self.http("POST", f"/scope{NEW}/talk",
                                     {"message": "what needs doing here?"})
            self.assertEqual(200, status)
            self.assertIn("What should we set up first", page)

            # No machinery leaked anywhere in the walk.
            for marker in ("integrity", "set_config", "nova_app", "credential"):
                for body in (page, decided, kairo):
                    self.assertNotIn(marker, body)
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
