"""`I-67` / `A-3`: an IRREVERSIBLE approval requires FRESH authentication.

`ADR 0018` (Accepted 2026-08-13) decided this: *"IRREVERSIBLE actions and
changes to grants, policy, or credentials require FRESH authentication, not
merely a valid session"*. `A-3` states it, `I-67` mints it, `ADR 0046` selected
WebAuthn as the mechanism. Until now the requirement had no implementation --
`auth.py`'s limitation 3 and `seam.py`'s one-shot strength check were the whole
of it -- so the first irreversible action NOVA grows would have been decided by
a session established hours earlier.

WHAT FRESH MEANS HERE, and what this suite is actually asserting: a new
assertion, verified now, over a challenge THIS server minted for THIS approval,
consumed on use. Four independent bindings, each tested on its own because each
one alone is defeatable:

    single-use   a challenge consumed cannot be consumed again
    purpose      a ceremony for approval A cannot decide approval B
    expiry       a challenge older than the ceremony lifetime is refused
    actor        a credential belonging to someone else is refused

The actor binding is the one that does not exist in `verify_login`, and the one
this suite would be worthless without: login DERIVES the actor from whichever
credential signed, because at login there is nobody to compare against. At
step-up there is. Without that comparison ANY enrolled credential would satisfy
ANY session -- `test_12` is the test that proves it does not.

FAIL-CLOSED IS PROVEN BY CONSEQUENCE, NOT BY STATUS CODE. Every refusal test
below also asserts that the approval is still `pending`, that nothing was
written, and that no execution audit record exists. A 401 with the side effect
already committed would be worse than no gate at all.

AND THE GATE IS PROVEN LOAD-BEARING BY INVERSION (`test_27`): the same approval,
decided through the same route with the step-up requirement removed, executes.
The gate is what makes the difference.

The routes are exercised over real HTTP too (`test_25`, `test_26`), because a
`/stepup/options` path that fell through to another handler would disable the
gate while every direct-call test above still passed.

NO IRREVERSIBLE TOOL EXISTS YET, so the fixture promotes one approval's declared
risk class to `IRREVERSIBLE` directly. That is honest rather than convenient:
the column is the approval's own durable declaration, `plan_for_action` derives
`Risk.EXECUTE` for every tool NOVA currently has, and `I-112`'s identity is
re-derived from the arguments -- so promoting the column exercises the gate
exactly as the first irreversible tool will, without inventing that tool here.

Real PostgreSQL, and a real `py_webauthn` verification against a software
authenticator. Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_step_up
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import tempfile
import unittest

from .. import db
from ..approval_flow import ApprovalService, PENDING
from ..auth import AuthenticationFailed
from ..boundary import DataAccessBoundary
from ..seam import APPROVER_IDENTITY, Seam, _requires_step_up
from ..write_path import (ADD_TASK, PostgresItemIntegration, WritePath,
                          add_task_tool, write_item_tool, TOOL)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.context_service import ContextService
from ...core.policy import PolicyDecisionPoint
from ...core.scope_tree import ScopeTree
from ...core.store import StoreRegistry
from ...core.types import Risk
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture
from .authfixture import ORIGIN, RP_ID
from .softauthn import SoftAuthenticator

A = "/business/KAIRO/client-a"


@unittest.skipUnless(db.available(),
                     "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class StepUpTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()

        tree = ScopeTree()
        tree.add_scope("/business", "domain")
        tree.add_scope("/business/KAIRO", "business")
        tree.add_scope(A, "client")
        tree.james_grants("james", "read", "*", A, Risk.READ)
        tree.james_grants("james", "write", "*", A, Risk.EXECUTE)

        tmp = tempfile.mkdtemp(prefix="nova-stepup-")
        self.context = ContextService(tree, secret=b"stepup-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(tree, vault, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=A,
                              permitted_operations=frozenset({TOOL, ADD_TASK})),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        registry.register(write_item_tool())
        registry.register(add_task_tool())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                PostgresItemIntegration(self.boundary),
                                "db-item-write")
        self.approvals = ApprovalService(self.boundary, self.writes)

        self.auth = authfixture.service()
        self.key = authfixture.enrol(self.auth, "james", "james", "laptop")
        self.sid = authfixture.sign_in(self.auth, self.key)
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def sql(self, query, args=()):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, args)
            rows = cur.fetchall() if cur.description else []
        conn.close()
        return rows

    def token(self):
        return self.context.issue_root(
            identity="james", actor="james", scope_path=A,
            rights=frozenset({"write"}), ceiling=Risk.EXECUTE, ttl=60)

    def propose(self, ref: str = "t-1", irreversible: bool = True) -> str:
        """One pending approval, optionally declared IRREVERSIBLE.

        Promoting the column is what stands in for the tool that does not exist
        yet. `plan_identity` is unaffected: `decide()` rebuilds the plan from
        the stored ARGUMENTS, and `plan_for_action` declares `Risk.EXECUTE` for
        every tool NOVA has -- so the approval still matches itself, and only
        the gate's input changes.
        """
        approval_id = self.approvals.propose_action(
            self.token(), A, ADD_TASK,
            {"task_ref": ref, "title": "Something consequential", "due_on": ""},
            action_text="Do the irreversible thing.",
            if_wrong_text="It cannot be undone.")
        if irreversible:
            self.sql("UPDATE approval SET risk_class=%s WHERE approval_id=%s",
                     (Risk.IRREVERSIBLE.name, approval_id))
        return approval_id

    def session(self):
        return self.auth.resolve(self.sid)

    def step_up(self, approval_id: str, key: SoftAuthenticator = None,
                user_verified: bool = True, advance_counter: bool = True,
                origin: str = ORIGIN, rp_id: str = RP_ID):
        """A complete step-up ceremony. Returns (ceremony_id, assertion)."""
        ceremony, options = self.auth.step_up_options(self.session(), approval_id)
        raw = json.loads(options)["challenge"]
        challenge = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        assertion = (key or self.key).authenticate(
            challenge, rp_id, origin, user_verified=user_verified,
            advance_counter=advance_counter)
        return ceremony, assertion

    def decide(self, approval_id: str, approve: bool = True,
               ceremony=None, assertion: str = ""):
        return self.seam.decide_page(self.sid, A, approval_id, approve,
                                     ceremony_id=ceremony, assertion=assertion)

    # -- what must NOT have happened ----------------------------------------

    def assert_nothing_happened(self, approval_id: str, ref: str = "t-1"):
        """Fail-closed, asserted by consequence rather than by status code."""
        status = self.sql("SELECT status, consumed_at FROM approval"
                          " WHERE approval_id=%s", (approval_id,))[0]
        self.assertEqual(status[0], PENDING, "the approval was consumed")
        self.assertIsNone(status[1], "the approval was claimed")
        self.assertEqual(
            self.sql("SELECT count(*) FROM task WHERE task_ref=%s", (ref,))[0][0], 0,
            "the consequential action was written")
        # Scoped to THIS ref: `test_08` legitimately decides another approval
        # first, so a global count would assert against that one's honest
        # record rather than against the refused one.
        self.assertEqual(
            self.sql("SELECT count(*) FROM audit_record"
                     " WHERE category='data.write' AND detail LIKE %s",
                     ("%" + ref + "%",))[0][0], 0,
            "an execution audit record was written")

    # =======================================================================
    # The predicate: what requires fresh authentication at all
    # =======================================================================

    def test_01_an_execute_class_approval_does_not_require_step_up(self):
        """`I-67` names IRREVERSIBLE. Everything NOVA can currently propose is
        EXECUTE, so nothing existing changes behaviour -- the property the rest
        of the regression suite depends on."""
        request = self.approvals.get(self.token(), self.propose(irreversible=False))
        self.assertEqual(request.risk_class, Risk.EXECUTE.name)
        self.assertFalse(_requires_step_up(request))

    def test_02_an_irreversible_approval_requires_step_up(self):
        request = self.approvals.get(self.token(), self.propose())
        self.assertTrue(_requires_step_up(request))

    # =======================================================================
    # Happy path
    # =======================================================================

    def test_03_a_valid_step_up_lets_the_approval_proceed(self):
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        status, page = self.decide(approval_id, True, ceremony, assertion)
        self.assertEqual(status, 200)
        self.assertEqual(
            self.sql("SELECT count(*) FROM task WHERE task_ref='t-1'")[0][0], 1)

    def test_04_the_primitive_mints_no_session(self):
        """Step-up proves presence; it does not create authority. `I-13`."""
        before = self.sql("SELECT count(*) FROM auth_session")[0][0]
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)
        self.assertEqual(self.sql("SELECT count(*) FROM auth_session")[0][0], before)

    def test_05_no_freshness_state_is_persisted(self):
        """There is nowhere for a step-up to go stale, because there is nowhere
        for one to be recorded. Asserted against the session row itself."""
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        before = self.sql("SELECT * FROM auth_session")
        self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)
        self.assertEqual(self.sql("SELECT * FROM auth_session"), before)

    def test_06_an_ordinary_approval_still_needs_no_assertion(self):
        """The existing flow is untouched: no ceremony, no assertion, decided."""
        approval_id = self.propose(irreversible=False)
        status, _ = self.decide(approval_id, True)
        self.assertEqual(status, 200)
        self.assertEqual(
            self.sql("SELECT count(*) FROM task WHERE task_ref='t-1'")[0][0], 1)

    # =======================================================================
    # Replay
    # =======================================================================

    def test_07_a_ceremony_cannot_be_consumed_twice(self):
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)

    def test_08_a_replayed_assertion_does_not_decide_a_second_approval(self):
        """The end-to-end version of `test_07`: the whole point of single use."""
        first, second = self.propose("t-1"), self.propose("t-2")
        ceremony, assertion = self.step_up(first)
        self.decide(first, True, ceremony, assertion)
        status, _ = self.decide(second, True, ceremony, assertion)
        self.assertEqual(status, 401)
        self.assert_nothing_happened(second, "t-2")

    # =======================================================================
    # Purpose binding -- a ceremony names ONE approval
    # =======================================================================

    def test_09_a_ceremony_for_one_approval_cannot_authorize_another(self):
        first, second = self.propose("t-1"), self.propose("t-2")
        ceremony, assertion = self.step_up(first)
        status, _ = self.decide(second, True, ceremony, assertion)
        self.assertEqual(status, 401)
        self.assert_nothing_happened(second, "t-2")

    def test_10_a_login_ceremony_is_not_a_step_up(self):
        """The namespaces are disjoint on purpose: `authenticate` and
        `stepup:<id>` are different strings, so a fresh LOGIN challenge cannot
        be spent as a step-up even though the assertion would verify."""
        approval_id = self.propose()
        ceremony, options = self.auth.login_options()
        raw = json.loads(options)["challenge"]
        challenge = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        assertion = self.key.authenticate(challenge, RP_ID, ORIGIN)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)

    # =======================================================================
    # Expiry
    # =======================================================================

    def test_11_an_expired_ceremony_is_refused(self):
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        # Reach into the in-memory store and age the entry past its lifetime.
        challenge, purpose, _ = self.auth._ceremonies._open[ceremony]
        self.auth._ceremonies._open[ceremony] = (
            challenge, purpose,
            datetime.datetime.now(datetime.timezone.utc)
            - datetime.timedelta(seconds=1))
        status, _ = self.decide(approval_id, True, ceremony, assertion)
        self.assertEqual(status, 401)
        self.assert_nothing_happened(approval_id)

    # =======================================================================
    # Cross-user -- the check `verify_login` does not have
    # =======================================================================

    def test_12_another_actors_credential_cannot_step_up_this_session(self):
        """THE test. A perfectly valid assertion, correctly signed, answering
        the right challenge for the right purpose -- from a credential enrolled
        to somebody else. Without the actor comparison this passes, and any
        enrolled passkey anywhere authorizes any session's irreversible act."""
        other = authfixture.enrol(self.auth, "mallory", "mallory", "other laptop")
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id, key=other)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)

    def test_13_another_actors_credential_decides_nothing(self):
        other = authfixture.enrol(self.auth, "mallory", "mallory", "other laptop")
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id, key=other)
        status, _ = self.decide(approval_id, True, ceremony, assertion)
        self.assertEqual(status, 401)
        self.assert_nothing_happened(approval_id)

    # =======================================================================
    # WebAuthn verification -- the existing machinery, still doing its job
    # =======================================================================

    def test_14_an_assertion_from_another_origin_is_refused(self):
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id, origin="https://evil.example")
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)

    def test_15_an_assertion_for_another_relying_party_is_refused(self):
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id, rp_id="evil.example")
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)

    def test_16_a_tampered_signature_is_refused(self):
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        payload = json.loads(assertion)
        sig = payload["response"]["signature"]
        payload["response"]["signature"] = ("B" if sig[0] != "B" else "C") + sig[1:]
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, json.dumps(payload),
                                     self.session(), approval_id)

    def test_17_an_assertion_without_user_verification_is_refused(self):
        """`I-67` asks for a fresh STRONG proof. Login deliberately accepts a
        UV-less assertion and reads the flag to set strength; step-up has no
        weaker outcome to fall back to, so it requires UV outright."""
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id, user_verified=False)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)

    def test_18_a_regressed_signature_counter_is_refused(self):
        """Clone detection, inherited from the existing verification path."""
        approval_id = self.propose()
        # Advance the stored counter first, so the next assertion regresses.
        first, first_assertion = self.step_up(approval_id)
        self.auth.verify_step_up(first, first_assertion, self.session(), approval_id)
        ceremony, assertion = self.step_up(approval_id, advance_counter=False)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)

    def test_19_a_single_factor_session_cannot_even_start_a_step_up(self):
        weak = self.auth.resolve(
            authfixture.sign_in(self.auth, self.key, user_verified=False))
        with self.assertRaises(AuthenticationFailed):
            self.auth.step_up_options(weak, "ap-anything")

    # =======================================================================
    # Fail closed
    # =======================================================================

    def test_20_approving_with_no_assertion_at_all_is_refused(self):
        approval_id = self.propose()
        status, _ = self.decide(approval_id, True)
        self.assertEqual(status, 401)
        self.assert_nothing_happened(approval_id)

    def test_21_a_refused_step_up_leaves_the_approval_decidable(self):
        """Not merely pending -- still usable. A gate that bricked the approval
        would be a denial-of-service dressed as a control."""
        approval_id = self.propose()
        self.assertEqual(self.decide(approval_id, True)[0], 401)
        ceremony, assertion = self.step_up(approval_id)
        self.assertEqual(self.decide(approval_id, True, ceremony, assertion)[0], 200)
        self.assertEqual(
            self.sql("SELECT count(*) FROM task WHERE task_ref='t-1'")[0][0], 1)

    def test_22_declining_needs_no_step_up(self):
        """Declining writes a status and nothing else. Friction on the safe
        answer is how a gate teaches people to take the unsafe one."""
        approval_id = self.propose()
        status, _ = self.decide(approval_id, approve=False)
        self.assertEqual(status, 200)
        self.assertEqual(
            self.sql("SELECT status FROM approval WHERE approval_id=%s",
                     (approval_id,))[0][0], "denied")

    def test_23_the_ceremony_route_refuses_an_approval_that_needs_no_step_up(self):
        """It is a gate, not a general re-authentication oracle."""
        ordinary = self.propose(irreversible=False)
        status, _, _, _ = self.seam.approval_step_up_options(self.sid, A, ordinary)
        self.assertEqual(status, 403)

    def test_24_the_ceremony_route_refuses_an_unknown_approval(self):
        status, _, _, _ = self.seam.approval_step_up_options(self.sid, A, "ap-nope")
        self.assertEqual(status, 403)

    # =======================================================================
    # Over HTTP -- because a misrouted gate is a disabled gate
    # =======================================================================

    def test_25_the_whole_flow_works_over_http(self):
        """The seam-level tests above call the methods directly, which proves
        the logic and nothing about the ROUTES. A `/stepup/options` path that
        fell through to the catch-all `/scope/<path>` handler would return a
        page instead of a challenge, the script would fail, and the gate would
        look like a bug rather than a control. So: real server, real URLs.
        """
        import urllib.error
        import urllib.parse
        import urllib.request
        from ..seam import serve

        server, port = serve(self.seam)
        try:
            approval_id = self.propose()
            base = f"http://127.0.0.1:{port}/scope{A}/approvals/{approval_id}"

            def get(path):
                req = urllib.request.Request(path)
                req.add_header("Cookie", f"nova_session={self.sid}")
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status, r.read().decode(), dict(r.headers)
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode(), dict(e.headers)

            # The ceremony route resolves, and hands back a challenge plus the
            # ceremony cookie -- exactly as the login route does.
            status, body, headers = get(base + "/stepup/options")
            self.assertEqual(status, 200)
            challenge_b64 = json.loads(body)["challenge"]
            self.assertIn("nova_ceremony=", headers.get("Set-Cookie", ""))
            ceremony = headers["Set-Cookie"].split("nova_ceremony=")[1].split(";")[0]

            challenge = base64.urlsafe_b64decode(
                challenge_b64 + "=" * (-len(challenge_b64) % 4))
            assertion = self.key.authenticate(challenge, RP_ID, ORIGIN)

            # And the decision route reads the ceremony from the COOKIE and the
            # assertion from the form, which is what the page actually posts.
            data = urllib.parse.urlencode(
                {"decision": "approve", "assertion": assertion}).encode()
            req = urllib.request.Request(base, data=data, method="POST")
            req.add_header("Cookie",
                           f"nova_session={self.sid}; nova_ceremony={ceremony}")
            with urllib.request.urlopen(req, timeout=10) as r:
                self.assertEqual(r.status, 200)
            self.assertEqual(
                self.sql("SELECT count(*) FROM task WHERE task_ref='t-1'")[0][0], 1)
        finally:
            server.shutdown()

    def test_26_over_http_approving_without_the_assertion_is_refused(self):
        """The same route, the same session, no assertion. Fails closed."""
        import urllib.error
        import urllib.parse
        import urllib.request
        from ..seam import serve

        server, port = serve(self.seam)
        try:
            approval_id = self.propose()
            data = urllib.parse.urlencode({"decision": "approve"}).encode()
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/scope{A}/approvals/{approval_id}",
                data=data, method="POST")
            req.add_header("Cookie", f"nova_session={self.sid}")
            try:
                with urllib.request.urlopen(req, timeout=10) as r:
                    self.fail(f"expected refusal, got {r.status}")
            except urllib.error.HTTPError as e:
                self.assertEqual(e.code, 401)
            self.assert_nothing_happened(approval_id)
        finally:
            server.shutdown()

    # =======================================================================
    # INVERSION -- the gate is what makes the difference
    # =======================================================================

    def test_27_INVERSION_without_the_gate_the_same_approval_executes(self):
        """Same approval, same session, same absent assertion. The ONLY change
        is that the approval is not declared IRREVERSIBLE, so the gate does not
        engage -- and the action lands. If this ever stops executing, the gate
        is no longer what refuses `test_20` and this suite proves nothing."""
        approval_id = self.propose(irreversible=False)
        status, _ = self.decide(approval_id, True)
        self.assertEqual(status, 200)
        self.assertEqual(
            self.sql("SELECT count(*) FROM task WHERE task_ref='t-1'")[0][0], 1,
            "the ungated approval did not execute -- the inversion proves nothing")

    # =======================================================================
    # `I-09` and the approval machinery, unchanged underneath
    # =======================================================================

    def test_28_step_up_does_not_replace_the_approver_identity_check(self):
        """`I-09` is not softened by adding a factor in front of it."""
        self.assertEqual(APPROVER_IDENTITY, "james")
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        self.auth.verify_step_up(ceremony, assertion, self.session(), approval_id)
        # A verified step-up proves presence; it grants nothing on its own.
        self.assertEqual(
            self.sql("SELECT status FROM approval WHERE approval_id=%s",
                     (approval_id,))[0][0], PENDING)

    def test_29_an_approval_is_still_single_use_after_a_step_up(self):
        """`I-09`'s single-use claim is untouched: a second decision on the same
        approval is refused even with a fresh, valid ceremony."""
        approval_id = self.propose()
        ceremony, assertion = self.step_up(approval_id)
        self.assertEqual(self.decide(approval_id, True, ceremony, assertion)[0], 200)
        again, again_assertion = self.step_up(approval_id)
        status, _ = self.decide(approval_id, True, again, again_assertion)
        self.assertEqual(status, 409)
        self.assertEqual(
            self.sql("SELECT count(*) FROM task WHERE task_ref='t-1'")[0][0], 1)


if __name__ == "__main__":
    unittest.main()
