"""WEALTH: the third area, and the strongest boundary proof yet.

LIFE needed one presentational addition. WEALTH needs ZERO production code
-- this suite is the entire deliverable, and that absence is the finding.
Three materially different categories of James's world (a business with
clients, his personal life, his financial life) now run on one unchanged
platform:

    BUSINESS -> KAIRO -> clients
    LIFE     -> FITNESS
    WEALTH   -> INVESTMENTS / BANKING / GOALS

all through the same Add a Place, the same note tool, the same task system,
the same approval flow, the same RLS.

FINANCIAL GOALS, RESOLVED PER THE STATED PREFERENCE: "I want to save
$10,000 for a car" is a NOTE. The existing generic infrastructure represents
it fully, because what NOVA stores today is the intention, not the progress
-- balances, transactions and progress calculations are explicitly out of
scope, and without them a Goal model would be a table with one prose column
wearing a costume. No goal system was built, and no stop condition fired.

NO INTEGRATIONS, VERIFIED NOT ASSERTED: nothing in this suite -- or in the
substrate it exercises -- connects a bank, brokerage or financial API, and
no balance, holding or account number is stored anywhere. WEALTH's data is
what James says it is: scopes, notes, tasks.

Everything runs through the PRODUCTION composition root (app.wire) against
real PostgreSQL. The model transport is the scripted double under production
routing names -- NOVA's machinery validated, the live Anthropic provider
explicitly NOT claimed (environment-blocked, unchanged).

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_wealth
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
from ..write_path import TOOL
from ...core.gateway import ProviderBinding
from ...core.types import Denied, Risk
from . import authfixture
from .test_conversation import ScriptedTransport

WEALTH = "/wealth"
INVESTMENTS = "/wealth/investments"
LIFE = "/life"
BUSINESS = "/business"

SCOPES = [(LIFE, "domain", None), (BUSINESS, "domain", None),
          (WEALTH, "domain", None)]
GRANTS = [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")]


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class WealthTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.seam = wire(tempfile.mkdtemp(prefix="nova-wealth-"),
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

    def token(self, scope=WEALTH, ceiling=Risk.EXECUTE):
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

    def talk(self, message, reply, scope=WEALTH, sid=None):
        self.transport.replies.append(reply)
        return self.seam.talk_post(sid or self.sid, scope, message)

    def approve_pending(self, scope):
        approval_id = self.sql("SELECT approval_id FROM approval"
                               " WHERE status='pending'")[0][0]
        return self.seam.decide_page(self.sid, scope, approval_id, True)

    def create_investments(self):
        self.talk("create a place for my investments",
                  'I can set that up. [[PROPOSE_SCOPE name="investments" kind="account"]]')
        self.approve_pending(WEALTH)

    # =======================================================================
    # Structure grows as James wants it -- nothing is mandatory
    # =======================================================================

    def test_01_wealth_starts_with_no_mandated_children(self):
        """No financial hierarchy was seeded or migrated into existence. The
        area is empty until James grows it."""
        self.assertEqual([], self.tree.children(WEALTH))
        _, page = self.seam.scope_page(self.sid, WEALTH)
        self.assertEqual(200, self.seam.scope_page(self.sid, WEALTH)[0])
        for imposed in ("INVESTMENTS", "BANKING", "GOALS"):
            self.assertNotIn(imposed, page)

    def test_02_places_grow_under_wealth_by_conversation(self):
        self.create_investments()
        self.assertEqual([(INVESTMENTS, "account", WEALTH)],
                         self.sql("SELECT scope_path, kind, parent_path FROM scope"
                                  " WHERE scope_path=%s", (INVESTMENTS,)))
        # Immediately navigable; WEALTH lists it under Inside.
        _, page = self.seam.scope_page(self.sid, WEALTH)
        self.assertIn("INVESTMENTS", page)
        self.assertEqual(200, self.seam.scope_page(self.sid, INVESTMENTS)[0])

    # =======================================================================
    # Financial notes and goals are the existing note tool
    # =======================================================================

    def test_03_a_financial_note_lands_and_renders(self):
        self.create_investments()
        self.talk("remember that I want to review my portfolio every Friday",
                  'I will propose recording that. [[PROPOSE_NOTE ref="review-cadence" '
                  'body="Review the portfolio every Friday"]]', scope=INVESTMENTS)
        self.approve_pending(INVESTMENTS)
        self.assertEqual([("review-cadence", "Review the portfolio every Friday",
                           INVESTMENTS)],
                         self.sql("SELECT item_ref, body, scope_path FROM item"))
        _, page = self.seam.scope_page(self.sid, INVESTMENTS)
        self.assertIn("Review the portfolio every Friday", page)

    def test_04_a_goal_is_a_note_not_a_model(self):
        """The section-5 decision, exercised: the intention is stored fully by
        the existing tool, and no Goal table exists to check."""
        self.create_investments()
        self.talk("I want to save $10,000 for a car",
                  'That is a clear goal. [[PROPOSE_NOTE ref="goal-car" '
                  'body="Goal: save $10,000 for a car"]]', scope=INVESTMENTS)
        self.approve_pending(INVESTMENTS)
        self.assertIn(("goal-car",),
                      self.sql("SELECT item_ref FROM item"))
        # No goal/balance/transaction table came into existence.
        tables = [r[0] for r in self.sql(
            "SELECT tablename FROM pg_tables WHERE schemaname='public'")]
        for forbidden in ("goal", "balance", "transaction", "account", "holding"):
            self.assertNotIn(forbidden, tables)

    # =======================================================================
    # Financial tasks are the existing task system, reaching attention
    # =======================================================================

    def test_05_a_wealth_task_reaches_attention(self):
        self.create_investments()
        due = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        self.talk("remind me to review my investments this Friday",
                  f'Will do. [[PROPOSE_TASK ref="review-investments" '
                  f'title="Review investments" due="{due}"]]', scope=INVESTMENTS)
        self.assertEqual([], self.sql("SELECT 1 FROM task"))        # pending only
        self.approve_pending(INVESTMENTS)
        self.assertEqual([("review-investments", INVESTMENTS)],
                         self.sql("SELECT task_ref, scope_path FROM task"))
        _, home = self.seam.home_page(self.sid)
        self.assertIn("Review investments", home)
        self.assertIn("WEALTH / INVESTMENTS", home)

    # =======================================================================
    # Security, re-proven in the third area
    # =======================================================================

    def test_06_proposal_alone_creates_nothing_and_weak_sessions_cannot_propose(self):
        self.talk("create an investments place",
                  'Sure. [[PROPOSE_SCOPE name="investments" kind="account"]]')
        self.assertEqual([], self.sql("SELECT 1 FROM scope WHERE scope_path=%s",
                                      (INVESTMENTS,)))
        weak = authfixture.sign_in(self.seam._auth, self.key, user_verified=False)
        _, page = self.talk("remember my goal",
                            'Ok. [[PROPOSE_NOTE ref="x" body="y"]]', sid=weak)
        self.assertIn("cannot record", page)

    def test_07_read_token_cannot_write_and_tampering_fails_identity(self):
        self.create_investments()
        with self.assertRaises(Denied) as cm:
            self.seam._writes.execute_action(
                self.token(INVESTMENTS, ceiling=Risk.READ), INVESTMENTS, TOOL,
                {"item_ref": "x", "body": "y"})
        self.assertEqual("I-101", cm.exception.invariant)

        self.talk("remember my plan",
                  'Noted. [[PROPOSE_NOTE ref="plan" body="Max out the TFSA"]]',
                  scope=INVESTMENTS)
        approval_id = self.sql("SELECT approval_id FROM approval"
                               " WHERE status='pending'")[0][0]
        self.sql("UPDATE approval SET body='wire everything to evil.example'"
                 " WHERE approval_id=%s", (approval_id,))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(self.token(INVESTMENTS), approval_id, True,
                                  decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

    def test_08_wealth_is_unreachable_from_life_and_business(self):
        """I-03 across all three areas: channels bound to /life and /business
        can neither read nor plant rows in WEALTH."""
        self.create_investments()
        self.talk("remember my plan",
                  'Noted. [[PROPOSE_NOTE ref="plan" body="TFSA-PRIVATE-PLAN"]]',
                  scope=INVESTMENTS)
        self.approve_pending(INVESTMENTS)

        for sibling in (LIFE, BUSINESS):
            with self.boundary.open(self.token(sibling)) as ch:
                self.assertEqual([], ch.fetch("SELECT item_ref FROM item"),
                                 f"{sibling} read WEALTH's notes")
            with self.assertRaises(psycopg2.Error, msg=sibling):
                with self.boundary.open(self.token(sibling)) as ch:
                    ch.execute("INSERT INTO item (item_ref, scope_path, body)"
                               " VALUES ('planted', %s, 'HOSTILE')", (INVESTMENTS,))
        self.assertEqual(1, self.sql("SELECT count(*) FROM item")[0][0])

    def test_09_audited_in_scope_and_no_grant_mutation(self):
        """The governance constraint across the whole area: place + note +
        task, grant table byte-identical, everything audited where it lives."""
        before = self.sql('SELECT actor_ref, scope_path, right_name FROM "grant"'
                          " ORDER BY id")
        self.create_investments()
        self.talk("remember my plan",
                  'Noted. [[PROPOSE_NOTE ref="plan" body="Max out the TFSA"]]',
                  scope=INVESTMENTS)
        self.approve_pending(INVESTMENTS)
        after = self.sql('SELECT actor_ref, scope_path, right_name FROM "grant"'
                         " ORDER BY id")
        self.assertEqual(before, after, "a WEALTH operation touched the grant table")
        self.assertIsNotNone(self.tree.find_grant("james", "write", "*", INVESTMENTS))

        audits = self.sql("SELECT scope_path FROM audit_record"
                          " WHERE category='data.write' ORDER BY id")
        self.assertEqual([(WEALTH,), (INVESTMENTS,)], audits)

    # =======================================================================
    # The section-8 walk, over HTTP, through production wiring
    # =======================================================================

    def test_10_james_organizes_his_financial_life(self):
        due = (datetime.date.today() + datetime.timedelta(days=2)).isoformat()
        self.transport.replies = [
            'I can set up an investments place under WEALTH. '
            '[[PROPOSE_SCOPE name="investments" kind="account"]]',
            'I will propose recording that. [[PROPOSE_NOTE ref="review-cadence" '
            'body="Review the portfolio every Friday"]]',
            f'Will do. [[PROPOSE_TASK ref="review-investments" '
            f'title="Review investments" due="{due}"]]',
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
            row = self.sql("SELECT approval_id, scope_path FROM approval"
                           " WHERE status='pending'")[0]
            return http("POST", f"/scope{row[1]}/approvals/{row[0]}",
                        {"decision": "approve"})

        try:
            # 1-2. Signed in, WEALTH on the front door.
            status, home = http("GET", "/")
            self.assertEqual(200, status)
            self.assertIn("WEALTH", home)

            # 3-6. Create INVESTMENTS by conversation; approve; open it.
            _, page = http("POST", f"/scope{WEALTH}/talk",
                           {"message": "create a place for my investments"})
            self.assertIn("I need your approval", page)
            _, decided = approve()
            self.assertIn("Open INVESTMENTS", decided)
            self.assertEqual(200, http("GET", f"/scope{INVESTMENTS}")[0])

            # 7-8. Record the note; approve; it is on the page.
            http("POST", f"/scope{INVESTMENTS}/talk",
                 {"message": "remember that I want to review my portfolio every Friday"})
            approve()
            _, inv_page = http("GET", f"/scope{INVESTMENTS}")
            self.assertIn("Review the portfolio every Friday", inv_page)

            # 9-11. Create the task; approve; it reaches attention.
            http("POST", f"/scope{INVESTMENTS}/talk",
                 {"message": "remind me to review my investments this Friday"})
            approve()
            _, home = http("GET", "/")
            self.assertIn("Review investments", home)
            self.assertIn("WEALTH / INVESTMENTS", home)

            # 12-13. Note visible where recorded; activity shows the writes.
            _, inv_page = http("GET", f"/scope{INVESTMENTS}")
            self.assertIn("Notes", inv_page)
            self.assertIn("write_item", inv_page)
            self.assertIn("add_task", inv_page)

            # 14. LIFE and BUSINESS see none of it.
            for sibling in (LIFE, BUSINESS):
                _, sib_page = http("GET", f"/scope{sibling}")
                for private in ("Review the portfolio", "Review investments",
                                "INVESTMENTS"):
                    self.assertNotIn(private, sib_page)

            # No machinery leaked anywhere in the walk.
            for marker in ("integrity", "set_config", "nova_app", "credential",
                           "PROPOSE_"):
                for body in (home, inv_page, decided):
                    self.assertNotIn(marker, body)
        finally:
            server.shutdown()
        # 15. Grant table unchanged across the entire walk.
        self.assertEqual(
            [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")],
            [tuple(r) for r in self.sql(
                'SELECT actor_ref, scope_path, right_name FROM "grant" ORDER BY id')])


if __name__ == "__main__":
    unittest.main()
