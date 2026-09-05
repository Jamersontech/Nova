"""Real authentication (D-09), end to end, against real PostgreSQL.

The last stand-in in NOVA's security path was a dictionary that handed out
session ids. This suite proves it is gone, and that what replaced it is a real
WebAuthn ceremony whose failures are decided by `py_webauthn`'s verifier and
not by anything written here.

The software authenticator (`softauthn.py`) plays the security key and holds a
real P-256 key. It cannot make a bad assertion verify -- every hostile case
below is produced by making the AUTHENTICATOR misbehave and asserting the real
verifier refuses:

  wrong origin        -- A-2's whole point: a phished assertion does not verify
  wrong relying party -- a signature for another site is not a signature here
  replayed challenge  -- single-use, server-side
  tampered signature  -- the key is not the attacker's
  regressed counter   -- what a cloned authenticator looks like
  no user verification-- one factor, so READ only (A-1)

And the session half:

  forged/modified session reference, expiry, revocation, privilege separation,
  and the fact that no request parameter anywhere can name an identity.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_auth
"""

from __future__ import annotations

import base64
import datetime
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request

from .. import db
from ..approval_flow import ApprovalService
from ..auth import (MULTI_FACTOR, SINGLE_FACTOR, AuthenticationFailed,
                    AuthenticationService, _ref)
from ..boundary import DataAccessBoundary
from ..seam import Seam, serve
from ..write_path import (PostgresItemIntegration, WritePath, write_item_tool,
                          TOOL)
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
B = "/business/KAIRO/client-b"


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class AuthenticationTest(unittest.TestCase):

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
        tree.james_grants("james", "read", "*", A, Risk.READ)
        tree.james_grants("james", "write", "*", A, Risk.EXECUTE)

        tmp = tempfile.mkdtemp(prefix="nova-auth-")
        self.context = ContextService(tree, secret=b"auth-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(tree, vault, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=A,
                              permitted_operations=frozenset({TOOL})),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        registry.register(write_item_tool())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")
        self.approvals = ApprovalService(self.boundary, self.writes)

        self.auth = authfixture.service()
        self.key = authfixture.enrol(self.auth, "james", "james", "laptop")
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def sign_in(self, **kw) -> str:
        return authfixture.sign_in(self.auth, self.key, **kw)

    def login_challenge(self):
        ceremony, options = self.auth.login_options()
        raw = json.loads(options)["challenge"]
        return ceremony, base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))

    def sql(self, query, args=()):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, args)
            rows = cur.fetchall() if cur.description else []
        conn.close()
        return rows

    def http(self, method, path, sid=None, body=None, form=None):
        data = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
        elif body is not None:
            data = body.encode()
        elif method == "POST":
            data = b""
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}{path}",
                                     data=data, method=method)
        if sid:
            req.add_header("Cookie", f"nova_session={sid}")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.status, resp.read().decode(), dict(resp.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(), dict(e.headers)

    # =======================================================================
    # A-2 -- the primary factor resists replay. These are the tests that
    # decide whether "phishing-resistant" is a claim or a property.
    # =======================================================================

    def test_01_an_assertion_produced_at_another_origin_does_not_verify(self):
        """THE phishing test. James is induced to authenticate against
        evil.example; the authenticator signs over THAT origin, and the
        signature is then replayed here. It does not verify."""
        ceremony, challenge = self.login_challenge()
        phished = self.key.authenticate(challenge, RP_ID, "https://evil.example")
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_login(ceremony, phished)
        self.assertEqual([], self.sql("SELECT 1 FROM auth_session"))

    def test_02_an_assertion_for_another_relying_party_does_not_verify(self):
        ceremony, challenge = self.login_challenge()
        wrong_rp = self.key.authenticate(challenge, "evil.example", ORIGIN)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_login(ceremony, wrong_rp)

    def test_03_a_challenge_is_single_use(self):
        """A captured assertion cannot be replayed: the challenge it answers
        was consumed by the first attempt."""
        ceremony, challenge = self.login_challenge()
        assertion = self.key.authenticate(challenge, RP_ID, ORIGIN)
        self.assertIsNotNone(self.auth.verify_login(ceremony, assertion))
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_login(ceremony, assertion)
        self.assertEqual(1, len(self.sql("SELECT 1 FROM auth_session")))

    def test_04_an_assertion_answering_a_different_challenge_is_refused(self):
        ceremony, _ = self.login_challenge()
        assertion = self.key.authenticate(os.urandom(32), RP_ID, ORIGIN)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_login(ceremony, assertion)

    def test_05_a_tampered_signature_is_refused(self):
        ceremony, challenge = self.login_challenge()
        payload = json.loads(self.key.authenticate(challenge, RP_ID, ORIGIN))
        signature = bytearray(base64.urlsafe_b64decode(
            payload["response"]["signature"] + "=="))
        signature[-1] ^= 0xFF
        payload["response"]["signature"] = base64.urlsafe_b64encode(
            bytes(signature)).decode().rstrip("=")
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_login(ceremony, json.dumps(payload))

    def test_06_an_unknown_credential_is_refused(self):
        stranger = SoftAuthenticator()
        ceremony, challenge = self.login_challenge()
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_login(
                ceremony, stranger.authenticate(challenge, RP_ID, ORIGIN))

    def test_07_a_regressed_signature_counter_is_refused(self):
        """What a cloned authenticator looks like: a valid signature whose
        counter did not advance."""
        self.sign_in()
        ceremony, challenge = self.login_challenge()
        cloned = self.key.authenticate(challenge, RP_ID, ORIGIN,
                                       advance_counter=False)
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_login(ceremony, cloned)

    # =======================================================================
    # A-1 -- strength comes from the signature, not from the client
    # =======================================================================

    def test_08_user_verification_decides_the_session_strength(self):
        strong = self.auth.resolve(self.sign_in())
        weak = self.auth.resolve(self.sign_in(user_verified=False))
        self.assertEqual(MULTI_FACTOR, strong.strength)
        self.assertEqual(SINGLE_FACTOR, weak.strength)

    def test_09_a_single_factor_session_may_read_but_not_act(self):
        """The A-1 line, enforced at the seam. The SAME passkey, the same
        person -- only the factor count differs."""
        weak = self.sign_in(user_verified=False)
        self.assertEqual(200, self.seam.items_page(weak, A)[0])

        for status, page in (self.seam.write_item(weak, A, "it-1", "x"),
                             self.seam.approvals_page(weak, A),
                             self.seam.decide_page(weak, A, "ap-any", True)):
            self.assertEqual(403, status)
            self.assertIn("second factor", page)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

        # And the identical action succeeds with two factors, so the refusal
        # above is the factor count and nothing else.
        strong = self.sign_in()
        self.assertEqual(200, self.seam.approvals_page(strong, A)[0])

    # =======================================================================
    # Sessions -- forgery, expiry, revocation
    # =======================================================================

    def test_10_the_session_value_is_never_stored(self):
        """A dump of auth_session yields no usable session: the column is a
        verifier, not a credential."""
        token = self.sign_in()
        stored = self.sql("SELECT session_ref FROM auth_session")[0][0]
        self.assertNotEqual(token, stored)
        self.assertEqual(_ref(token), stored)
        self.assertNotIn(token, str(self.sql("SELECT * FROM auth_session")))

    def test_11_a_forged_or_modified_session_reference_resolves_to_nothing(self):
        token = self.sign_in()
        self.assertIsNotNone(self.auth.resolve(token))
        for forged in (token[:-1] + ("A" if token[-1] != "A" else "B"),
                       token + "x", token.upper(), _ref(token),
                       "", None, "../../etc/passwd", "' OR 1=1 --"):
            self.assertIsNone(self.auth.resolve(forged), f"accepted {forged!r}")

    def test_12_an_expired_session_is_refused(self):
        """Expiry is absolute and is not extended by activity."""
        token = self.sign_in()
        self.assertEqual(200, self.seam.items_page(token, A)[0])
        self.sql("UPDATE auth_session SET expires_at = now() - interval '1 second'")
        self.assertIsNone(self.auth.resolve(token))
        self.assertEqual(401, self.seam.items_page(token, A)[0])

    def test_13_a_revoked_session_is_refused_at_the_next_request(self):
        """I-65: revocation takes effect at the next decision, because every
        request resolves the session afresh."""
        token = self.sign_in()
        session = self.auth.resolve(token)
        self.assertEqual(200, self.seam.items_page(token, A)[0])
        self.auth.revoke(session.session_ref)
        self.assertEqual(401, self.seam.items_page(token, A)[0])

    def test_14_sessions_are_enumerable_and_all_revocable(self):
        """A-6: James can see and end every active session."""
        laptop, phone = self.sign_in(surface="laptop"), self.sign_in(surface="phone")
        self.assertEqual({"laptop", "phone"},
                         {s.surface for s in self.auth.active_sessions("james")})
        self.auth.revoke_all("james")
        self.assertEqual([], self.auth.active_sessions("james"))
        for token in (laptop, phone):
            self.assertIsNone(self.auth.resolve(token))

    def test_15_one_surface_is_not_the_others(self):
        """Compromise of one surface does not hand over the rest."""
        laptop, phone = self.sign_in(surface="laptop"), self.sign_in(surface="phone")
        self.auth.revoke(self.auth.resolve(laptop).session_ref)
        self.assertIsNone(self.auth.resolve(laptop))
        self.assertIsNotNone(self.auth.resolve(phone))

    # =======================================================================
    # Identity is never supplied by the request
    # =======================================================================

    def test_16_no_request_parameter_can_name_an_identity(self):
        """The seam reads identity ONLY from the resolved session. Nothing in
        the query string, the form or a header is consulted."""
        assistant_key = authfixture.enrol(self.auth, "assistant", "assistant")
        assistant = authfixture.sign_in(self.auth, assistant_key)

        # The assistant holds no grant in A, so a genuine session still fails.
        self.assertEqual(403, self.seam.items_page(assistant, A)[0])

        self.server, self.port = serve(self.seam)
        try:
            for attempt in ("?identity=james", "?actor=james",
                            "?identity=james&strength=multi_factor"):
                status, _, _ = self.http("GET", f"/scope{A}/items{attempt}",
                                         sid=assistant)
                self.assertIn(status, (403, 404), f"{attempt} changed the answer")

            # And a POST that names James in the body is still the assistant.
            status, page, _ = self.http(
                "POST", f"/scope{A}/approvals/ap-anything", sid=assistant,
                form={"decision": "approve", "identity": "james",
                      "actor": "james", "decided_by": "james"})
            self.assertEqual(403, status)
        finally:
            self.server.shutdown()
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

    def test_17_enrolling_a_second_passkey_requires_a_strong_session(self):
        """Bootstrap is open only while no credential exists. After that,
        adding a device is itself a consequential act."""
        with self.assertRaises(AuthenticationFailed):
            self.auth.enrolment_options("james", "james")          # no session
        with self.assertRaises(AuthenticationFailed):
            self.auth.enrolment_options(
                "james", "james",
                authorized_by=self.auth.resolve(self.sign_in(user_verified=False)))

        second = authfixture.enrol(
            self.auth, "james", "james", "phone",
            authorized_by=self.auth.resolve(self.sign_in()))
        self.assertIsNotNone(self.auth.resolve(authfixture.sign_in(self.auth, second)))

    def test_18_one_actors_session_cannot_enrol_a_key_for_another(self):
        """James's session is strong, but it is HIS. It cannot add a passkey
        for another actor -- otherwise a session would be an identity factory."""
        authfixture.enrol(self.auth, "assistant", "assistant")
        james_session = self.auth.resolve(self.sign_in())
        self.assertTrue(james_session.is_multi_factor)
        with self.assertRaises(AuthenticationFailed):
            self.auth.enrolment_options("assistant", "assistant",
                                        authorized_by=james_session)

    def test_18a_a_bootstrap_ceremony_cannot_be_spent_once_bootstrap_closes(self):
        """`F-4`. Two callers reach the enrolment route while an actor has no
        passkey, so BOTH are legitimately handed a ceremony -- that much is
        limitation 1 working as written. The first completes, and
        trust-on-first-use is over.

        The second is now an unauthenticated request to add a passkey to an
        established actor, which limitation 1 says must fail. It has to fail
        HERE, when the ceremony is redeemed, and not merely at the moment it
        was minted: `CEREMONY_LIFETIME` is five minutes, and the authorization
        was a fact about the world that stopped being true in between.

        Before the fix this call SUCCEEDED, and the resulting passkey was a
        full peer of James's -- multi-factor, EXECUTE-capable, and sufficient
        for the `I-67` step-up, whose binding compares the actor.
        """
        actor = "newcomer"
        self.assertFalse(self.auth.has_credential(actor))

        first_c, first_o = self.auth.enrolment_options(actor, actor)
        second_c, second_o = self.auth.enrolment_options(actor, actor)

        first_key = SoftAuthenticator()
        self.auth.verify_enrolment(
            first_c, first_key.register(authfixture._challenge(first_o),
                                        RP_ID, ORIGIN),
            actor, actor, "first")
        self.assertTrue(self.auth.has_credential(actor))

        second_key = SoftAuthenticator()
        with self.assertRaises(AuthenticationFailed):
            self.auth.verify_enrolment(
                second_c, second_key.register(authfixture._challenge(second_o),
                                              RP_ID, ORIGIN),
                actor, actor, "held over")

        # Refused, and nothing was written: one passkey, and the rejected
        # authenticator cannot sign in.
        self.assertEqual(
            [(1,)], self.sql("SELECT count(*) FROM auth_credential"
                             " WHERE actor_ref=%s", (actor,)))
        with self.assertRaises(AuthenticationFailed):
            authfixture.sign_in(self.auth, second_key)

    def test_18b_the_bootstrap_guard_does_not_touch_the_add_a_device_path(self):
        """The guard is scoped to the authorization that can perish. A ceremony
        minted against a strong session was authorized by something no later
        enrolment can retract, so it stays redeemable even though another
        passkey appeared while it was in flight.

        Without this, the fix for `F-4` would have broken the legitimate
        add-a-device path instead -- refusing every enrolment after the first
        is not a security property, it is an outage.
        """
        ceremony, options = self.auth.enrolment_options(
            "james", "james", authorized_by=self.auth.resolve(self.sign_in()))

        # A different device is enrolled while that ceremony is still open.
        authfixture.enrol(self.auth, "james", "james", "tablet",
                          authorized_by=self.auth.resolve(self.sign_in()))

        phone = SoftAuthenticator()
        self.auth.verify_enrolment(
            ceremony, phone.register(authfixture._challenge(options),
                                     RP_ID, ORIGIN),
            "james", "james", "phone")
        self.assertIsNotNone(
            self.auth.resolve(authfixture.sign_in(self.auth, phone)))

    def test_18c_a_registration_ceremony_carries_which_rule_authorized_it(self):
        """The mechanism, asserted directly. A ceremony minted with no
        credential present is a BOOTSTRAP ceremony; one minted against a strong
        session is an ADDITIONAL ceremony. `verify_enrolment` re-checks only the
        first, so the distinction has to be real and not incidental.

        Deciding at mint time and never recording the decision is what made
        `F-4` invisible: both ceremonies said `register`, so redemption had
        nothing to re-check against.
        """
        from ..auth import ENROL_ADDITIONAL, ENROL_BOOTSTRAP

        fresh, _ = self.auth.enrolment_options("newcomer", "newcomer")
        added, _ = self.auth.enrolment_options(
            "james", "james", authorized_by=self.auth.resolve(self.sign_in()))

        self.assertEqual(ENROL_BOOTSTRAP,
                         self.auth._ceremonies._open[fresh][1])
        self.assertEqual(ENROL_ADDITIONAL,
                         self.auth._ceremonies._open[added][1])

        # Asserted against each other, not only against the constants. Mutation
        # testing caught the two assertions above passing VACUOUSLY when the
        # constants were collapsed to one string: a value compared to itself
        # agrees no matter what it is. The property is that the two ceremonies
        # are DISTINGUISHABLE.
        self.assertNotEqual(ENROL_BOOTSTRAP, ENROL_ADDITIONAL)
        self.assertNotEqual(self.auth._ceremonies._open[fresh][1],
                            self.auth._ceremonies._open[added][1])

        # And the namespaces do not interchange: a registration ceremony is
        # not spendable as a login or a step-up, and never was.
        with self.assertRaises(AuthenticationFailed):
            self.auth._ceremonies.take(fresh, "authenticate")

    def test_18d_concurrent_bootstrap_redemptions_yield_exactly_one_credential(self):
        """`F-4`, the half a sequential test cannot reach.

        `WHERE NOT EXISTS` refuses a bootstrap ceremony redeemed AFTER a rival
        committed. It does not refuse one redeemed AT THE SAME TIME: under
        `READ COMMITTED` the subquery reads a snapshot that does not contain
        the rival's uncommitted row, and `actor_ref` has no unique constraint
        to fall back on. Measured before the advisory lock was added, 196 of
        200 concurrent trials produced TWO credentials for one actor.

        Each worker mints its own ceremony and generates its key BEFORE the
        barrier, so the only work left inside the contended window is the
        server-side verification and the write.

        ON DETERMINISM, HONESTLY. With the lock in place this test is
        deterministic: exactly one worker can win, every run. In the DETECTION
        direction it is statistical, because the workers cannot be made to
        arrive at the write in perfect lockstep from outside the API --
        `verify_registration_response` runs inside `verify_enrolment` and takes
        a few milliseconds that vary per worker. Measured with the advisory
        lock removed, one round of eight caught the race in 18 of 20 runs. So
        this runs several INDEPENDENT rounds and requires the invariant in
        every one of them, which takes the chance of an unlocked build slipping
        through from about one in ten to about one in a hundred thousand.

        Exactly one may win, in every round. That is the invariant -- not
        "usually one".
        """
        rounds, workers = 5, 8

        for round_index in range(rounds):
            actor = f"racer-{round_index}"
            self.assertFalse(self.auth.has_credential(actor))

            prepared = []
            for _ in range(workers):
                ceremony, options = self.auth.enrolment_options(actor, actor)
                key = SoftAuthenticator()
                # Keygen happens HERE, before the barrier. Left inside the
                # contended window it would stagger the workers and quietly
                # turn this back into a sequential test.
                prepared.append((ceremony, key,
                                 key.register(authfixture._challenge(options),
                                              RP_ID, ORIGIN)))

            barrier = threading.Barrier(workers)
            outcomes: list = [None] * workers

            def redeem(index: int, actor=actor, prepared=prepared,
                       outcomes=outcomes, barrier=barrier) -> None:
                ceremony, _, attestation = prepared[index]
                barrier.wait()
                try:
                    self.auth.verify_enrolment(ceremony, attestation,
                                               actor, actor, f"worker-{index}")
                    outcomes[index] = "accepted"
                except AuthenticationFailed:
                    outcomes[index] = "refused"

            threads = [threading.Thread(target=redeem, args=(i,))
                       for i in range(workers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            self.assertFalse(
                any(t.is_alive() for t in threads),
                f"round {round_index}: a redemption never returned "
                f"-- deadlock or lost lock")

            where = f"round {round_index}, outcomes={outcomes}"

            # 1. Exactly one succeeded, and every other failed CLOSED.
            self.assertEqual(1, outcomes.count("accepted"), where)
            self.assertEqual(workers - 1, outcomes.count("refused"), where)

            # 2. The database agrees -- no rejected credential was persisted.
            self.assertEqual(
                [(1,)], self.sql("SELECT count(*) FROM auth_credential"
                                 " WHERE actor_ref=%s", (actor,)), where)

            # 3. And a loser's authenticator is worthless, not merely
            #    unrecorded.
            for index, outcome in enumerate(outcomes):
                if outcome == "refused":
                    with self.assertRaises(AuthenticationFailed):
                        authfixture.sign_in(self.auth, prepared[index][1])

    def test_18e_the_bootstrap_lock_key_is_stable_and_actor_scoped(self):
        """The lock is only a control if two processes derive the SAME key for
        the same actor and DIFFERENT keys for different actors.

        `hash()` would satisfy neither: it is salted per process, so two
        workers would take two different locks and serialize nothing at all.
        """
        from ..auth import _bootstrap_lock_key

        self.assertEqual(_bootstrap_lock_key("james"),
                         _bootstrap_lock_key("james"))
        self.assertNotEqual(_bootstrap_lock_key("james"),
                            _bootstrap_lock_key("assistant"))

        # Stable across processes, not merely within this one.
        out = subprocess.run(
            [sys.executable, "-c",
             "from slice.substrate.auth import _bootstrap_lock_key as k;"
             "print(k('james'))"],
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(__file__))))),
            capture_output=True, text=True)
        self.assertEqual(str(_bootstrap_lock_key("james")), out.stdout.strip())

        # And it fits the bigint pg_advisory_xact_lock accepts.
        self.assertTrue(-2**63 <= _bootstrap_lock_key("james") < 2**63)

    # =======================================================================
    # Privilege separation -- authentication cannot reach scoped data
    # =======================================================================

    def test_19_the_auth_role_cannot_read_scoped_data(self):
        """Authentication runs before a Context Token exists, so it cannot go
        through the Data-Access Boundary. It is confined by PRIVILEGE instead:
        `nova_auth` reaches the two auth tables and nothing else."""
        import psycopg2
        conn = psycopg2.connect(db.auth_dsn())
        try:
            for table in ("item", "approval", "audit_record", "scope", '"grant"'):
                with conn.cursor() as cur:
                    with self.assertRaises(psycopg2.Error, msg=f"reached {table}"):
                        cur.execute(f"SELECT * FROM {table}")
                conn.rollback()
        finally:
            conn.close()

    def test_20_the_application_role_cannot_read_authentication_state(self):
        """And the reverse: session material is not application data."""
        import psycopg2
        conn = psycopg2.connect(db.app_dsn())
        try:
            for table in ("auth_session", "auth_credential"):
                with conn.cursor() as cur:
                    with self.assertRaises(psycopg2.Error, msg=f"reached {table}"):
                        cur.execute(f"SELECT * FROM {table}")
                conn.rollback()
        finally:
            conn.close()

    # =======================================================================
    # The whole path, over HTTP, with a real ceremony
    # =======================================================================

    def test_21_browser_to_rls_through_a_real_login(self):
        """browser -> WebAuthn -> session -> Context Token -> PDP -> boundary
        -> RLS -> response, with nothing faked in between."""
        self.server, self.port = serve(self.seam)
        try:
            # Unauthenticated: nothing.
            self.assertEqual(401, self.http("GET", f"/scope{A}/items")[0])

            # The real ceremony over HTTP.
            status, options, headers = self.http("GET", "/auth/login/options")
            self.assertEqual(200, status)
            ceremony = headers["Set-Cookie"].split("nova_ceremony=")[1].split(";")[0]
            raw = json.loads(options)["challenge"]
            challenge = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))

            req = urllib.request.Request(
                f"http://127.0.0.1:{self.port}/auth/login",
                data=self.key.authenticate(challenge, RP_ID, ORIGIN).encode(),
                method="POST")
            req.add_header("Cookie", f"nova_ceremony={ceremony}")
            with urllib.request.urlopen(req, timeout=10) as resp:
                set_cookie = resp.headers["Set-Cookie"]
            token = set_cookie.split("nova_session=")[1].split(";")[0]

            # The cookie is not readable by script, not sent cross-site, and
            # marked Secure because the origin is https.
            for flag in ("HttpOnly", "SameSite=Strict", "Secure"):
                self.assertIn(flag, set_cookie)

            # The session now reaches the application, and the read is really
            # bounded by RLS: the sibling scope is refused.
            status, page, _ = self.http("GET", f"/scope{A}/items", sid=token)
            self.assertEqual(200, status)
            self.assertEqual(403, self.http("GET", f"/scope{B}/items", sid=token)[0])

            # No token, credential or scope material reaches the browser.
            for marker in ("integrity", "trace_id", "set_config", "nova_app",
                           "nova_auth", "session_ref"):
                self.assertNotIn(marker, page.lower())

            # Signing out ends it, at the next request.
            self.assertEqual(200, self.http("POST", "/auth/logout", sid=token)[0])
            self.assertEqual(401, self.http("GET", f"/scope{A}/items", sid=token)[0])
        finally:
            self.server.shutdown()

    def test_22_a_failed_login_over_http_says_only_that_it_failed(self):
        """One answer for every failure: no enumeration oracle."""
        self.server, self.port = serve(self.seam)
        try:
            status, options, headers = self.http("GET", "/auth/login/options")
            ceremony = headers["Set-Cookie"].split("nova_ceremony=")[1].split(";")[0]
            raw = json.loads(options)["challenge"]
            challenge = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))

            for hostile in (
                self.key.authenticate(challenge, RP_ID, "https://evil.example"),
                SoftAuthenticator().authenticate(challenge, RP_ID, ORIGIN),
                '{"id":"nope","response":{}}',
            ):
                req = urllib.request.Request(
                    f"http://127.0.0.1:{self.port}/auth/login",
                    data=hostile.encode(), method="POST")
                req.add_header("Cookie", f"nova_ceremony={ceremony}")
                try:
                    with urllib.request.urlopen(req, timeout=10) as resp:
                        self.fail("a hostile assertion was accepted")
                except urllib.error.HTTPError as e:
                    self.assertEqual(401, e.code)
                    self.assertEqual('{"ok":false}', e.read().decode())
        finally:
            self.server.shutdown()
        self.assertEqual([], self.sql("SELECT 1 FROM auth_session"))

    def test_23_the_login_page_holds_no_authority(self):
        """The one scripted page in NOVA. It moves bytes; it decides nothing."""
        self.server, self.port = serve(self.seam)
        try:
            _, page, _ = self.http("GET", "/auth/login")
        finally:
            self.server.shutdown()
        self.assertIn("navigator.credentials", page)
        # A-5: one human identity is James's, so the page has no username
        # field -- and no field of any kind. Nothing is typed, so nothing
        # typed can be captured.
        self.assertNotIn("<input", page.lower())
        # No identity, scope, right or session material anywhere in it.
        for marker in ("james", "scope", "grant", "nova_session"):
            self.assertNotIn(marker, page.lower())


if __name__ == "__main__":
    unittest.main()
