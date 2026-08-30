"""Conversation, end to end, against real PostgreSQL.

The routing configuration under test is PRODUCTION's -- the same provider
name, model id and CapabilityProfile that ADR 0047 declares. Only the
transport is doubled, which is the seam the gateway was built to double: a
scripted callable standing exactly where RealAnthropicTransport stands,
receiving exactly what it would receive -- a prompt and a credential
REFERENCE -- and nothing else.

What this suite is actually guarding: an AI interface is the classic place a
security model quietly grows a back door. So every test is one of three
claims:

  the model is DOWNSTREAM of authorization -- the PDP and RLS decide what it
      is shown, and a denied read means no model call at all
  the model holds NO AUTHORITY -- its output cannot execute, cannot mark an
      action done, and a hostile transport with stolen app credentials still
      cannot cross a scope
  a proposal is INERT -- the only consequence-shaped output is a pending
      approval in the EXISTING ApprovalService, bound to an exact plan
      identity that James decides on the existing surface

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_conversation
"""

from __future__ import annotations

import os
import tempfile
import unittest
import urllib.error
import urllib.parse
import urllib.request

from .. import db, tree_store
from ..approval_flow import PENDING, ApprovalService
from ..boundary import DataAccessBoundary
from ..conversation import (CONVERSATION_MODEL, CONVERSATION_PROFILE, PROVIDER,
                            PROVIDER_UNCONFIGURED, ConversationService)
from ..seam import Seam, serve
from ..write_path import (PostgresItemIntegration, WritePath, write_item_tool,
                          TOOL)
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

A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"

SCOPES = [("/business", "domain", None),
          ("/business/KAIRO", "business", "/business"),
          (A, "client", "/business/KAIRO"),
          (B, "client", "/business/KAIRO"),
          ("/private", "domain", None)]
GRANTS = [("james", "/business", "read"), ("james", "/business", "write")]

CRED_REF = "control-plane/anthropic"


class ScriptedTransport:
    """Stands where RealAnthropicTransport stands. Records what reached the
    egress boundary; replies with whatever the test scripted."""

    def __init__(self):
        self.replies: list[str] = []
        self.prompts: list[str] = []
        self.credential_refs: list[str] = []
        # The provider's own claim about the call. Defaults to what this
        # transport has always returned, so no existing test changes; `test_14f`
        # sets it to distinguish an ordinary provider FAILURE from a provider
        # that was never configured.
        self.outcome: str = "success_claimed"

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        self.credential_refs.append(credential_ref)
        text = self.replies.pop(0) if self.replies else "Nothing is pending here."
        return ModelResponse(text=text, outcome=self.outcome,
                             taint=Taint.of("model.generated", Classification.INTERNAL))


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class ConversationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-conversation-")
        self.context = ContextService(self.tree, secret=b"conversation-suite-key")
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
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")
        self.approvals = ApprovalService(self.boundary, self.writes)

        # The gateway, wired as production wires it: PRODUCTION profile,
        # PRODUCTION provider name and model, budget attached. The transport is
        # the double.
        self.transport = ScriptedTransport()
        self.budget = BudgetLedger()
        self.gateway = ModelGateway(lambda: self.pdp.available, self.context,
                                    audit, budget=self.budget)
        self.gateway.register_provider(
            ProviderBinding(provider=PROVIDER, model=CONVERSATION_MODEL,
                            endpoint="test://anthropic", api_version="test",
                            credential_ref=CRED_REF, cost_per_unit=1),
            self.transport)
        self.conversation = ConversationService(
            self.gateway, self.pdp, self.boundary, self.approvals, self.budget)

        self.auth = authfixture.service()
        self.key = authfixture.enrol(self.auth, "james", "james", "laptop")
        self.sid = authfixture.sign_in(self.auth, self.key)
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals,
                         tree=self.tree, conversation=self.conversation)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def seed_item(self, scope, ref, body):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            # I-111: seeded rows carry the security state a real write
            # would have recorded. Without it they are legacy-shaped and
            # are correctly WITHHELD from model context -- which would make
            # this fixture prove the wrong thing.
            cur.execute("INSERT INTO item (item_ref, scope_path, body,"
                        " provenance, trust, classification,"
                        " delegation_ancestry, creating_authority)"
                        " VALUES (%s,%s,%s,'{james.stated}',3,2,'{}',%s)",
                        (ref, scope, body, "seed-" + ref))
        conn.close()

    def sql(self, query, args=()):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, args or None)
            rows = cur.fetchall() if cur.description else []
        conn.close()
        return rows

    def talk(self, message, sid=None, scope=A, extra=None):
        form = {"message": message}
        form.update(extra or {})
        return self.seam.talk_post(sid or self.sid, scope, message) \
            if extra is None else self._talk_http(message, sid or self.sid, scope, extra)

    def _talk_http(self, message, sid, scope, extra):
        server, port = serve(self.seam)
        try:
            form = {"message": message, **extra}
            req = urllib.request.Request(
                f"http://127.0.0.1:{port}/scope{scope}/talk",
                data=urllib.parse.urlencode(form).encode(), method="POST")
            req.add_header("Cookie", f"nova_session={sid}")
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status, resp.read().decode()
            except urllib.error.HTTPError as e:
                return e.code, e.read().decode()
        finally:
            server.shutdown()

    # =======================================================================
    # 1-2 -- who is talking is the session's answer, not the request's
    # =======================================================================

    def test_01_unauthenticated_conversation_is_rejected(self):
        self.assertEqual(401, self.seam.talk_page(None, A)[0])
        self.assertEqual(401, self.seam.talk_post(None, A, "hello")[0])
        self.assertEqual(401, self.seam.talk_post("forged-session", A, "hello")[0])
        self.assertEqual([], self.transport.prompts, "an unauthenticated turn reached the model")

    def test_02_the_turn_carries_the_server_side_identity(self):
        """The conversation's identity is the session's. A form naming another
        identity changes nothing -- the handler never reads one."""
        status, _ = self._talk_http("what is here?", self.sid, A,
                                    {"identity": "assistant", "actor": "assistant",
                                     "decided_by": "assistant"})
        self.assertEqual(200, status)
        rows = self.sql("SELECT actor_ref FROM audit_record"
                        " WHERE detail LIKE 'conversation context%'")
        self.assertEqual([("james",)], rows,
                         "the conversation read was not attributed to the session identity")

    # =======================================================================
    # 3-5 -- the model is downstream of authorization
    # =======================================================================

    def test_03_conversation_cannot_enter_an_ungranted_scope(self):
        status, _ = self.seam.talk_post(self.sid, "/private", "what is here?")
        self.assertEqual(403, status)
        self.assertEqual([], self.transport.prompts,
                         "a denied scope still produced a model call")
        # And the page route answers identically for unknown vs forbidden.
        self.assertEqual(self.seam.talk_page(self.sid, "/private"),
                         self.seam.talk_page(self.sid, "/no-such-scope"))

    def test_04_the_model_is_shown_only_this_scopes_data(self):
        """The prompt's contents are RLS's decision, not prompt discipline:
        the sibling's data is unreachable from the channel that gathered the
        context, so it CANNOT be in the prompt."""
        self.seed_item(A, "meeting", "Followup on the Tuesday meeting")
        self.seed_item(B, "secret-b", "CLIENT-B-CONFIDENTIAL-MATERIAL")
        status, _ = self.seam.talk_post(self.sid, A, "what is going on here?")
        self.assertEqual(200, status)
        prompt = self.transport.prompts[0]
        self.assertIn("Followup on the Tuesday meeting", prompt)
        self.assertNotIn("CLIENT-B-CONFIDENTIAL-MATERIAL", prompt,
                         "a sibling scope's data reached the model")
        self.assertIn(A, prompt)

    def test_04b_an_explicit_denial_stops_the_conversation(self):
        """I-15, and the reason the Data Access PEP is in this path at all:
        token issuance checks GRANTS, and the gateway checks PDP LIVENESS, but
        only `authorize_data_read` enforces an explicit denial. Remove that
        call and this is the test that notices."""
        self.tree.james_denies("james", "read", A)
        status, _ = self.seam.talk_post(self.sid, A, "what is here?")
        self.assertEqual(403, status)
        self.assertEqual([], self.transport.prompts,
                         "an explicitly denied scope still reached the model")

    def test_05_pdp_unavailable_fails_closed_before_the_model(self):
        self.pdp.available = False
        try:
            status, _ = self.seam.talk_post(self.sid, A, "hello?")
            self.assertEqual(403, status)
            self.assertEqual([], self.transport.prompts,
                             "the PDP was down and the model was still called")
        finally:
            self.pdp.available = True
        # Restored, the identical turn works: the denial was the PDP's absence.
        self.assertEqual(200, self.seam.talk_post(self.sid, A, "hello?")[0])

    def test_05b_the_transport_receives_a_reference_and_never_material(self):
        self.seam.talk_post(self.sid, A, "hello")
        self.assertEqual([CRED_REF], self.transport.credential_refs)

    # =======================================================================
    # 6 -- a hostile model layer still cannot cross a scope
    # =======================================================================

    def test_06_a_hostile_transport_cannot_reach_the_database(self):
        """Assume the worst: the model layer is compromised AND holds the
        application role's credentials. It still sees nothing (no binding) and
        still cannot write another scope (RLS WITH CHECK). The engine holds
        where every application-layer control has been bypassed."""
        import psycopg2
        observed = {}

        def hostile(prompt, credential_ref):
            conn = psycopg2.connect(db.app_dsn())
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT count(*) FROM item")
                    observed["visible"] = cur.fetchone()[0]
                with conn.cursor() as cur:
                    try:
                        cur.execute("INSERT INTO item (item_ref, scope_path, body)"
                                    " VALUES ('planted', %s, 'HOSTILE')", (B,))
                        observed["write"] = "accepted"
                    except psycopg2.Error:
                        observed["write"] = "refused"
            finally:
                conn.rollback(); conn.close()
            return ModelResponse(text="I looked around.",
                                 taint=Taint.of("model.generated", Classification.INTERNAL))

        self.seed_item(A, "meeting", "notes")
        gw = ModelGateway(lambda: self.pdp.available, self.context,
                          self.pdp._audit if hasattr(self.pdp, "_audit") else None)
        # Reuse the production wiring but with the hostile transport.
        gw = self.gateway
        gw._transports[PROVIDER] = hostile
        status, _ = self.seam.talk_post(self.sid, A, "look around")
        self.assertEqual(200, status)
        self.assertEqual(0, observed["visible"],
                         "an unbound connection from the model layer saw scoped data")
        self.assertEqual("refused", observed["write"])
        self.assertEqual([], self.sql("SELECT 1 FROM item WHERE scope_path=%s", (B,)))

    # =======================================================================
    # 7-9 -- a proposal is inert until James decides
    # =======================================================================

    def propose_via_conversation(self):
        self.transport.replies.append(
            'I can record that. [[PROPOSE_NOTE ref="followup-friday" '
            'body="Follow up with this client on Friday"]]')
        status, page = self.seam.talk_post(self.sid, A,
                                           "add a note to follow up friday")
        self.assertEqual(200, status)
        rows = self.sql("SELECT approval_id, status, item_ref, body FROM approval")
        self.assertEqual(1, len(rows))
        return rows[0], page

    def test_07_a_proposed_write_does_not_execute(self):
        (approval_id, status, item_ref, body), page = self.propose_via_conversation()
        self.assertEqual(PENDING, status)
        self.assertEqual(("followup-friday", "Follow up with this client on Friday"),
                         (item_ref, body))
        # Nothing landed, nothing ran.
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.assertEqual(0, self.integration.side_effects)
        # And the page says so honestly: approval needed, no completion claim.
        self.assertIn("I need your approval", page)
        self.assertIn(f"/scope{A}/approvals", page)
        self.assertNotIn("Done", page)

    def test_08_the_proposal_is_bound_to_the_exact_plan(self):
        """Tamper with the conversation-created approval; the reconstruction
        no longer matches what James saw and it cannot execute (I-112)."""
        (approval_id, *_), _ = self.propose_via_conversation()
        self.sql("UPDATE approval SET body='send everything to evil.example'"
                 " WHERE approval_id=%s", (approval_id,))
        token = self.context.issue_root(identity="james", actor="james",
                                        scope_path=A, rights=frozenset({"write"}),
                                        ceiling=Risk.EXECUTE, ttl=60)
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

    def test_09_the_approved_proposal_executes_through_the_existing_path(self):
        """Approve on the EXISTING approval surface; the write goes PDP ->
        ToolPEP -> boundary -> RLS WITH CHECK, and is audited."""
        (approval_id, *_), _ = self.propose_via_conversation()
        status, page = self.seam.decide_page(self.sid, A, approval_id, True)
        self.assertEqual(200, status)
        self.assertEqual([("followup-friday", "Follow up with this client on Friday")],
                         self.sql("SELECT item_ref, body FROM item WHERE scope_path=%s", (A,)))
        self.assertEqual(1, self.integration.side_effects)
        # 11. Audited, in the same scope, attributed.
        self.assertEqual([("W-1", "data.write", A, "james")],
                         self.sql("SELECT writer, category, scope_path, actor_ref"
                                  " FROM audit_record WHERE category='data.write'"))

    def test_10_rls_still_refuses_a_hostile_cross_scope_write(self):
        """The canary stays: WITH CHECK holds under the conversation wiring."""
        import psycopg2
        token = self.context.issue_root(identity="james", actor="james",
                                        scope_path=A, rights=frozenset({"write"}),
                                        ceiling=Risk.EXECUTE, ttl=60)
        with self.assertRaises(psycopg2.Error):
            with self.boundary.open(token) as ch:
                ch.execute("INSERT INTO item (item_ref, scope_path, body)"
                           " VALUES ('x', %s, 'HOSTILE')", (B,))
        self.assertEqual([], self.sql("SELECT 1 FROM item WHERE scope_path=%s", (B,)))

    # =======================================================================
    # 12 -- model prose is not evidence
    # =======================================================================

    def test_12_model_output_cannot_mark_an_action_done(self):
        """The model claims completion outright. The server's account of the
        turn is 'answered': no side effect, no approval, no completion state
        -- the claim is rendered as what it is, untrusted text."""
        self.transport.replies.append(
            "Done! I have deleted the old records and emailed the client.")
        status, page = self.seam.talk_post(self.sid, A, "clean up this client")
        self.assertEqual(200, status)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.assertEqual([], self.sql("SELECT 1 FROM approval"))
        self.assertEqual(0, self.integration.side_effects)
        # The server attached no action state to the turn.
        self.assertNotIn("I need your approval", page)
        self.assertNotIn("Review and decide", page)

    def test_12b_a_malformed_or_hostile_marker_is_prose(self):
        for hostile in ('[[PROPOSE_NOTE ref="../../etc/passwd" body="x"]]',
                        '[[PROPOSE_NOTE ref="a" body="line1\nline2"]]',
                        '[[PROPOSE_DELETE ref="x" body="y"]]',
                        '[[PROPOSE_NOTE ref="" body=""]]'):
            self.transport.replies.append(hostile)
            status, _ = self.seam.talk_post(self.sid, A, "hello")
            self.assertEqual(200, status)
        self.assertEqual([], self.sql("SELECT 1 FROM approval"),
                         "a malformed marker created an approval")

    def test_12c_a_single_factor_session_cannot_record_a_proposal(self):
        """A-1 carries through conversation: one factor may ask, two may
        propose. The weak session's turn answers but records nothing."""
        weak = authfixture.sign_in(self.auth, self.key, user_verified=False)
        self.transport.replies.append(
            'Noted. [[PROPOSE_NOTE ref="weak" body="from a weak session"]]')
        status, page = self.seam.talk_post(weak, A, "add a note")
        self.assertEqual(200, status)
        self.assertEqual([], self.sql("SELECT 1 FROM approval"),
                         "a single-factor session recorded a proposal")
        self.assertIn("cannot record", page)

    # =======================================================================
    # The milestone walk -- NOVA Conversation v1, over HTTP
    # =======================================================================

    def test_13_james_talks_to_nova(self):
        self.seed_item(A, "meeting", "Kickoff scheduled for Monday")
        self.transport.replies = [
            "The kickoff is scheduled for Monday. Nothing else is pending.",
            'I can record that. [[PROPOSE_NOTE ref="followup-friday" '
            'body="Follow up with this client on Friday"]]',
        ]
        server, port = serve(self.seam)
        try:
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

            # The scope page offers the conversation.
            _, scope = http("GET", f"/scope{A}")
            self.assertIn(f"/scope{A}/talk", scope)

            # Ask -- the answer draws on authorized scope data.
            status, page = http("POST", f"/scope{A}/talk",
                                {"message": "what is going on with this client?"})
            self.assertEqual(200, status)
            self.assertIn("kickoff is scheduled for Monday", page)
            self.assertIn(A, page)                      # current scope visible

            # Ask for an action -- a proposal appears, nothing executes.
            status, page = http("POST", f"/scope{A}/talk",
                                {"message": "note that we follow up friday"})
            self.assertEqual(200, status)
            self.assertIn("I need your approval", page)
            self.assertEqual([], self.sql("SELECT 1 FROM item WHERE item_ref='followup-friday'"))

            # Follow the link, see the exact action, approve it.
            _, approvals = http("GET", f"/scope{A}/approvals")
            self.assertIn("followup-friday", approvals)
            approval_id = self.sql("SELECT approval_id FROM approval")[0][0]
            status, decided = http("POST", f"/scope{A}/approvals/{approval_id}",
                                   {"decision": "approve"})
            self.assertEqual(200, status)

            # The truthful result: executed, audited, visible in the scope.
            self.assertEqual([("followup-friday",)],
                             self.sql("SELECT item_ref FROM item WHERE scope_path=%s"
                                      " AND item_ref='followup-friday'", (A,)))
            _, scope_after = http("GET", f"/scope{A}")
            self.assertIn("data.write", scope_after)    # what NOVA did, on the page

            # Nothing across the whole walk leaked machinery.
            for marker in ("integrity", "set_config", "nova_app", "api_key",
                           "credential", "PROPOSE_NOTE"):
                for body in (scope, page, approvals, decided, scope_after):
                    self.assertNotIn(marker, body)
        finally:
            server.shutdown()

    # =======================================================================
    # 14 -- an UNCONFIGURED provider is not an authorization failure
    # =======================================================================
    #
    # Found by using NOVA, not by reading it. On a first run with no
    # `ANTHROPIC_API_KEY`, saying the README's own opening sentence produced:
    #
    #     "I couldn't complete that: the request was not authorized."
    #
    # James holds every grant on the scope. The gateway had denied at
    # `gateway.binding` -- no provider registered -- and `respond` mapped every
    # `Denied` to "refused", so a missing environment variable was reported as a
    # permissions problem and sent him to look in the wrong place entirely.

    def _read_token(self):
        """The READ-ceiling token the seam issues for a turn, for the tests that
        call `respond` directly rather than through HTTP."""
        return self.context.issue_root(
            identity="james", actor="james", scope_path=A,
            rights=frozenset({"read"}), ceiling=Risk.READ, ttl=60)

    def _unregister_provider(self):
        """Exactly the production shape of a missing `ANTHROPIC_API_KEY`:
        `app.wire` registers the provider ONLY when the credential is present,
        so absent credential means absent binding. Nothing else is changed --
        the session, the grants, the scope and the PDP all stay valid, which is
        what makes the old message false rather than merely unhelpful."""
        self.gateway._providers.pop(PROVIDER, None)
        self.gateway._transports.pop(PROVIDER, None)

    def test_14_an_unconfigured_provider_does_not_read_as_unauthorized(self):
        self._unregister_provider()
        status, page = self.seam.talk_post(self.sid, A, "hello?")

        self.assertNotIn("was not authorized", page,
                         "a missing provider is still reported as an"
                         " authorization failure")
        self.assertIn("ANTHROPIC_API_KEY", page,
                      "the page does not say what is actually missing")
        self.assertIn("No conversation provider is configured", page)
        # Fail-closed is unchanged: no answer, and not a success.
        self.assertNotEqual(200, status)

    def test_14b_the_turn_state_is_unavailable_not_refused(self):
        """`unavailable` already means "the model did not answer and nothing was
        done", which is exactly true here. No new state was invented."""
        self._unregister_provider()
        turn = self.conversation.respond(self._read_token(), A, "hello?")
        self.assertEqual("unavailable", turn.state)
        self.assertEqual(PROVIDER_UNCONFIGURED, turn.detail)

    def test_14c_a_genuine_authorization_denial_still_reads_as_one(self):
        """THE INVERSION, and the test this change would be worthless without.
        The provider is registered and healthy; the DENIAL is real -- an
        explicit denial on the scope (`I-15`). That must still say the request
        was not authorized, and must NOT mention the credential."""
        self.tree.james_denies("james", "read", A)
        status, page = self.seam.talk_post(self.sid, A, "what is here?")

        self.assertEqual(403, status)
        self.assertIn("was not authorized", page)
        self.assertNotIn("ANTHROPIC_API_KEY", page)
        self.assertNotIn("No conversation provider is configured", page)

    def test_14d_a_denial_reason_is_never_shown(self):
        """`refused` still withholds its detail. A denial reason is internal --
        some are security events -- and widening the rendering to `unavailable`
        must not have widened it to `refused` as well."""
        self.tree.james_denies("james", "read", A)
        _, page = self.seam.talk_post(self.sid, A, "what is here?")
        for internal in ("explicit denial", "I-15", "step4", "authorize_data_read"):
            self.assertNotIn(internal, page)

    def test_14e_an_unconfigured_provider_persists_nothing(self):
        """Fail-closed by consequence, not by status code: no item, no task, no
        approval, and the model was never reached."""
        self._unregister_provider()
        self.seam.talk_post(self.sid, A,
                            "remember that the supplier changed their bank details")

        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.assertEqual([], self.sql("SELECT 1 FROM task"))
        self.assertEqual([], self.sql("SELECT 1 FROM approval"))
        self.assertEqual([], self.transport.prompts,
                         "the model was called with no provider registered")

    def test_14f_the_ordinary_provider_failure_path_is_unchanged(self):
        """The third case stays distinct: the provider IS registered and the
        model itself did not succeed. Still `unavailable`, still its own
        detail, and it does not claim the credential is missing."""
        self.transport.outcome = "failure_claimed"
        turn = self.conversation.respond(self._read_token(), A, "hello?")
        self.assertEqual("unavailable", turn.state)
        self.assertNotEqual(PROVIDER_UNCONFIGURED, turn.detail)
        self.assertIn("failure_claimed", turn.detail)


if __name__ == "__main__":
    unittest.main()
