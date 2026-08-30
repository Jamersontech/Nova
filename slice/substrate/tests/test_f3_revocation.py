"""`F-3` / ADR 0052: James revokes an execution authority, through the ordinary path.

WHAT SHIPPED. `S7-D5` has said since ADR 0033 that a revoked authority's rows
are RETAINED and its revocation state EXPOSED at retrieval, and `F-13` built the
reading half. `RevocationRegistry` built the writing half. What did not exist was
a way for JAMES to decide that an authority is no longer trusted: the registry
had no caller, so nothing was ever revocable in practice.

THE ACT IS AN APPROVAL (ADR 0052 element 1). There is no second consequence
path. James points at a note or a task, NOVA proposes revoking the authority
that wrote it, and the revocation happens -- if it happens -- when he approves,
through `authorize_plan`, the `ToolPEP`, the credential broker and the
Data-Access Boundary, exactly like every other write.

WHAT THIS SUITE IS ACTUALLY FOR. The dangerous part of `F-3` is not the SQL; it
is that NOVA now has an `IRREVERSIBLE` act, and every control that keys on risk
class or on rights had been written while `Risk.EXECUTE` and `{"write"}` were
the only answers. ADR 0052 element 8 is the ruling that closed that:

  8a  `plan_for_action` derives `required_rights` from the tool declaration
  8b  ...and `declared_risk` too, and the execution token follows the approval
  8c  `revoke` is a DISTINCT right conferring `IRREVERSIBLE`; `write` unchanged
  8d  the registry row and its `W-1` record commit in ONE transaction

Each of those is silent when it fails -- every page still renders and every
other suite still passes -- so each is asserted here by CONSEQUENCE and, where
a control could be vacuous, by INVERSION: the same act, one condition changed,
landing.

THE GRANT SHAPE IS PART OF THE SUBJECT. `revoke` is granted at `/business` and
nowhere else, so the suite tests inheritance (`A` and `B` reach it downward) and
absence (`/life` does not) with the real loader -- `tree_store.load_tree` and its
`READ_RIGHTS` derivation -- rather than a tree assembled by hand.

Real PostgreSQL, real WebAuthn step-up against a software authenticator, real
RLS. Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_f3_revocation
"""

from __future__ import annotations

import base64
import dataclasses
import json
import os
import tempfile
import unittest

from .. import db, tree_store, write_path
from ..approval_flow import ApprovalService, PENDING
from ..boundary import DataAccessBoundary
from ..conversation import (CONVERSATION_MODEL, PROVIDER, ConversationService,
                            _REVOKED_MARK)
from ..revocation import RevocationRegistry
from ..seam import APPROVER_IDENTITY, Seam, _requires_step_up
from ..write_path import (ADD_SCOPE, ADD_TASK, COMPLETE_TASK, REVOKE_AUTHORITY,
                          TOOL, UNKNOWN_ORIGIN, PostgresItemIntegration,
                          WritePath, add_scope_tool, add_task_tool,
                          complete_task_tool, revoke_authority_tool,
                          write_item_tool)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.budget import BudgetLedger
from ...core.context_service import ContextService
from ...core.gateway import ModelGateway, ModelResponse, ProviderBinding
from ...core.policy import PolicyDecisionPoint
from ...core.store import StoreRegistry
from ...core.types import (Classification, Denied, Plan, PlanStep, Risk, Taint)
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture
from .authfixture import ORIGIN, RP_ID

BUSINESS = "/business"
A = "/business/client-a"
B = "/business/client-b"
LIFE = "/life"

SCOPES = [(BUSINESS, "domain", None),
          (A, "client", BUSINESS),
          (B, "client", BUSINESS),
          (LIFE, "domain", None)]

# `read` and `write` everywhere; `revoke` at `/business` ONLY.
#
# That asymmetry is deliberate and is itself part of the subject. `A` and `B`
# reach the revoke grant by downward containment, so inheritance is exercised
# rather than assumed (`test_17`); `/life` is a sibling root and reaches it
# never, which is what gives this suite a scope where the act is genuinely
# ungranted (`test_01`) instead of one where it was simply not attempted.
GRANTS = ([("james", path, right) for path, _, _ in SCOPES
           for right in ("read", "write")]
          + [("james", BUSINESS, "revoke")])

CRED_REF = "control-plane/anthropic"

NOTE = "MARKER-NOTE-the-supplier-changed-their-bank-details"
OTHER_NOTE = "MARKER-OTHER-NOTE-the-quarter-closes-friday"

# What `plan_for_action` hardcoded before ADR 0052 element 8a/8b. Kept here so
# `test_06` can rebuild an existing tool's plan the OLD way and compare
# identities, rather than trusting that the derivation happens to agree.
LEGACY_RIGHTS = frozenset({"write"})
LEGACY_RISK = Risk.EXECUTE


class ScriptedTransport:
    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        return ModelResponse(
            text="Noted.",
            taint=Taint.of("model.generated", Classification.INTERNAL))


class ScopedWritePath(WritePath):
    """The production parameterization (`app.py`): per-scope credential
    binding, because `I-24` requires the token's scope to cover the binding's
    and coverage runs downward only."""

    def binding_for(self, scope_path: str, tool_name: str = TOOL):
        return dataclasses.replace(super().binding_for(scope_path, tool_name),
                                   credential_binding_id=f"db-item-write{scope_path}")


@unittest.skipUnless(db.available(),
                     "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class F3RevocationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        # Through the REAL loader, so `READ_RIGHTS` -- the one place a right
        # name becomes a risk ceiling (element 8c) -- is what this suite tests
        # against rather than a hand-built tree that could disagree with it.
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-f3-")
        self.context = ContextService(self.tree, secret=b"f3-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        for scope, _, _ in SCOPES:
            broker.register(
                CredentialBinding(
                    binding_id=f"db-item-write{scope}", scope_path=scope,
                    permitted_operations=frozenset(
                        {TOOL, ADD_TASK, COMPLETE_TASK, REVOKE_AUTHORITY})),
                secret="integration-credential-" + os.urandom(4).hex())

        registry = ToolRegistry()
        for factory in (write_item_tool, add_task_tool, complete_task_tool,
                        add_scope_tool, revoke_authority_tool):
            registry.register(factory())
        self.registry = registry
        pep = ToolPEP(registry, broker, self.context, audit)

        self.revocations = RevocationRegistry(self.boundary, self.context)
        self.integration = PostgresItemIntegration(self.boundary,
                                                   revocations=self.revocations)
        self.writes = ScopedWritePath(self.pdp, registry, pep, broker,
                                      self.integration, "unused-see-subclass")
        self.approvals = ApprovalService(self.boundary, self.writes)

        self.budget = BudgetLedger()
        self.gateway = ModelGateway(lambda: self.pdp.available, self.context,
                                    audit, budget=self.budget)
        self.gateway.register_provider(
            ProviderBinding(provider=PROVIDER, model=CONVERSATION_MODEL,
                            endpoint="test://anthropic", api_version="test",
                            credential_ref=CRED_REF, cost_per_unit=1),
            ScriptedTransport())
        self.conversation = ConversationService(
            self.gateway, self.pdp, self.boundary, self.approvals,
            budget=self.budget)

        self.auth = authfixture.service()
        self.key = authfixture.enrol(self.auth, "james", "james", "laptop")
        self.sid = authfixture.sign_in(self.auth, self.key)
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals,
                         tree=self.tree, conversation=self.conversation,
                         revocations=self.revocations)

        # Every token this process issues, recorded as (rights, ceiling). The
        # seam derives both from the approval it is about to execute (element
        # 8b) and nothing else observes that from outside, so `test_07` reads
        # it here rather than inferring it from an outcome.
        self.issued: list[tuple[frozenset[str], Risk]] = []
        real_issue = self.context.issue_root

        def recording_issue(*args, **kwargs):
            token = real_issue(*args, **kwargs)
            self.issued.append((token.granted_rights, token.risk_ceiling))
            return token

        self.context.issue_root = recording_issue

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

    def token(self, scope=A, rights=frozenset({"read", "write"}),
              ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=frozenset(rights),
                                       ceiling=ceiling, ttl=60)

    def revoke_token(self, scope=A):
        """What element 8 says an irreversible act needs: the `revoke` right, at
        the `IRREVERSIBLE` ceiling that right confers."""
        return self.token(scope, frozenset({"revoke"}), Risk.IRREVERSIBLE)

    # -- seeding real authorities -------------------------------------------

    def run_action(self, scope, tool_name, arguments, taint=None):
        """One authorized action, through the whole path. Returns the executing
        token's `trace_id` -- which `I-111` persists as the row's
        `creating_authority` and which is therefore the authority `F-3` revokes.
        """
        approval_id = self.approvals.propose_action(
            self.token(scope), scope, tool_name, arguments,
            action_text=f"{tool_name} here.", if_wrong_text="Wrong thing.",
            taint=taint or Taint.of("james.stated", Classification.CONFIDENTIAL))
        executor = self.token(scope)
        self.approvals.decide(executor, approval_id, True, decided_by="james")
        return executor.trace_id

    def note(self, ref, body, scope=A):
        return self.run_action(scope, TOOL, {"item_ref": ref, "body": body})

    def task(self, ref, title, scope=A):
        return self.run_action(scope, ADD_TASK,
                               {"task_ref": ref, "title": title, "due_on": ""})

    # -- observing the registry ---------------------------------------------

    def revocation_rows(self):
        return self.sql("SELECT execution_identity, scope_path, revoked_by"
                        " FROM authority_revocation ORDER BY execution_identity")

    def assert_no_revocation(self, message="an authority was revoked"):
        self.assertEqual([], self.revocation_rows(), message)

    def assert_revoked(self, authority, scope):
        self.assertEqual(
            [(scope,)],
            self.sql("SELECT scope_path FROM authority_revocation"
                     " WHERE execution_identity = %s", (authority,)),
            "the revocation is missing, or filed at the wrong scope")

    def assert_pending(self, approval_id):
        row = self.sql("SELECT status, consumed_at FROM approval"
                       " WHERE approval_id = %s", (approval_id,))[0]
        self.assertEqual(PENDING, row[0], "the approval was consumed")
        self.assertIsNone(row[1], "the approval was claimed")

    # -- the write path, directly -------------------------------------------

    def execute_revoke(self, token, scope, authority, target="n1"):
        """One revocation attempt at the write path, with the in-memory approval
        the PDP's step 9 requires already recorded.

        Recorded deliberately: these tests are about the RIGHT and the CEILING,
        so the absence of an approval must not be what decides them. Every
        refusal below therefore happens at the step it names, not at step 9.
        """
        arguments = {"execution_identity": authority, "target_ref": target}
        plan = self.writes.plan_for_action(scope, REVOKE_AUTHORITY, arguments)
        self.writes.approvals.james_approves(plan.identity(), frozenset())
        return self.writes.execute_action(token, scope, REVOKE_AUTHORITY,
                                          arguments)

    # -- the seam, end to end ------------------------------------------------

    def step_up(self, approval_id, key=None, session_id=None):
        session = self.auth.resolve(session_id or self.sid)
        ceremony, options = self.auth.step_up_options(session, approval_id)
        raw = json.loads(options)["challenge"]
        challenge = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
        return ceremony, (key or self.key).authenticate(challenge, RP_ID, ORIGIN)

    def revocation_approvals(self):
        """Only the revocation proposals. Seeding a note or a task goes through
        the approval machinery too, so a bare count of `approval` would be
        asserting against the fixture rather than against the subject."""
        return self.sql("SELECT approval_id, status FROM approval"
                        " WHERE tool_name = %s ORDER BY created_at",
                        (REVOKE_AUTHORITY,))

    def pending_revocation_id(self):
        rows = [r for r in self.revocation_approvals() if r[1] == PENDING]
        self.assertTrue(rows, "no revocation approval is pending")
        return rows[-1][0]

    def propose_through_seam(self, scope, kind, ref, session_id=None):
        return self.seam.propose_revocation(session_id or self.sid, scope,
                                            kind, ref)

    def revoke_through_seam(self, scope, kind, ref):
        """The whole human path: propose, step up, approve. Returns
        (approval_id, status, page)."""
        status, page = self.propose_through_seam(scope, kind, ref)
        self.assertEqual(200, status, page)
        approval_id = self.pending_revocation_id()
        ceremony, assertion = self.step_up(approval_id)
        status, page = self.seam.decide_page(self.sid, scope, approval_id, True,
                                             ceremony_id=ceremony,
                                             assertion=assertion)
        return approval_id, status, page

    def block(self, scope=A):
        return self.conversation._scope_context(
            self.token(scope, frozenset({"read"}), Risk.READ), scope)

    # =======================================================================
    # 1-2 -- the right is what authorizes the act (element 8a/8c)
    # =======================================================================

    def test_01_without_a_revoke_grant_nothing_can_be_revoked(self):
        """`/life` has `read` and `write` and no `revoke`, at any ancestor.

        Refused at BOTH enforcement points, because they are different controls
        and either alone could be removed silently:

          issuance   `I-14` -- no grant for the right, so no token exists
          the PDP    `I-14` at step 5 -- no grant for the right on the resource

        And refused BEFORE `decide()`: the approval is untouched and still
        pending, which is what makes this a fail-closed denial rather than a
        half-performed act.
        """
        authority = self.note("n1", NOTE, scope=LIFE)

        with self.assertRaises(Denied) as issued:
            self.revoke_token(LIFE)
        self.assertEqual("I-14", issued.exception.invariant)

        with self.assertRaises(Denied) as decided:
            self.execute_revoke(self.token(LIFE), LIFE, authority)
        self.assertEqual("I-14", decided.exception.invariant)

        # ...and the same refusal through the human path.
        status, page = self.propose_through_seam(LIFE, "item", "n1")
        self.assertEqual(200, status, "proposing is not the irreversible act")
        approval_id = self.pending_revocation_id()
        self.assertEqual(403, self.seam.decide_page(self.sid, LIFE, approval_id,
                                                    True)[0])
        self.assert_pending(approval_id)
        self.assert_no_revocation()
        self.assertIsNotNone(page)

    def test_02_the_write_right_does_not_substitute_for_revoke(self):
        """THE POINT OF A SEPARATE RIGHT (element 8c). In `A` the `revoke` grant
        DOES exist -- inherited from `/business` -- so this is not a test about
        an absent grant. It is a test that a token carrying `write` cannot spend
        it: `I-07`'s intersection leaves nothing to satisfy the plan's
        `{"revoke"}`, and step 5 denies.

        INVERTED IMMEDIATELY BELOW: the same authority, the same scope, the same
        approval -- one right changed -- and it lands. Without that, "denied"
        could mean the act simply never works.
        """
        authority = self.note("n1", NOTE)

        with self.assertRaises(Denied) as denied:
            self.execute_revoke(self.token(A, frozenset({"read", "write"})),
                                A, authority)
        self.assertEqual("I-07", denied.exception.invariant)
        self.assert_no_revocation()

        # INVERSION.
        self.execute_revoke(self.revoke_token(A), A, authority)
        self.assert_revoked(authority, A)

    # =======================================================================
    # 3-6 -- the declarations, and what they leave untouched
    # =======================================================================

    def test_03_a_revoke_grant_confers_irreversible(self):
        """Element 8c, at the ONE place a right name becomes a ceiling. The
        `grant` table has no ceiling column -- `(actor_ref, scope_path,
        right_name)` and nothing else -- so `READ_RIGHTS` in `tree_store` is the
        whole of it, and this reads back through the real loader."""
        self.assertEqual(Risk.IRREVERSIBLE, tree_store.READ_RIGHTS["revoke"])
        self.assertEqual(
            Risk.IRREVERSIBLE,
            self.tree.find_grant("james", "revoke", "*", A).max_risk)
        # ...and `write` was NOT widened to carry it. Raising `write` would
        # have raised every write grant on every scope at once, which is the
        # reason element 8 chose a distinct right.
        self.assertEqual(Risk.EXECUTE, tree_store.READ_RIGHTS["write"])
        self.assertEqual(Risk.EXECUTE,
                         self.tree.find_grant("james", "write", "*", A).max_risk)
        self.assertEqual(Risk.READ, tree_store.READ_RIGHTS["read"])
        self.assertEqual(Risk.READ,
                         self.tree.find_grant("james", "read", "*", A).max_risk)

    def test_04_the_revoke_plan_declares_revoke_and_irreversible(self):
        """Element 8a/8b at the plan, which is what the PDP and the approval row
        both read. The tool's declaration is the source; `plan_for_action`
        carries it rather than restating it."""
        definition = self.registry.get(REVOKE_AUTHORITY, write_path.TOOL_VERSION)
        self.assertEqual(frozenset({"revoke"}), definition.required_rights)
        self.assertEqual(Risk.IRREVERSIBLE, definition.risk_class)

        plan = self.writes.plan_for_action(
            A, REVOKE_AUTHORITY,
            {"execution_identity": "x", "target_ref": "n1"})
        self.assertEqual(frozenset({"revoke"}), plan.required_rights)
        self.assertEqual(frozenset({"revoke"}), plan.steps[0].required_rights)
        self.assertEqual(Risk.IRREVERSIBLE, plan.declared_risk)
        # And the seam's single source for the token it must issue.
        self.assertEqual(frozenset({"revoke"}),
                         self.writes.required_rights_for(REVOKE_AUTHORITY))

    def test_05_every_existing_tool_still_declares_write_and_execute(self):
        """The derivation must not have MOVED anything, only stopped assuming
        it. `revoke_authority` is the only tool that differs, and it is the only
        `IRREVERSIBLE` tool NOVA has."""
        for tool_name in (TOOL, ADD_TASK, COMPLETE_TASK, ADD_SCOPE):
            with self.subTest(tool=tool_name):
                self.assertEqual(
                    LEGACY_RIGHTS, self.writes.required_rights_for(tool_name))
                plan = self.writes.plan_for_action(A, tool_name, {})
                self.assertEqual(LEGACY_RIGHTS, plan.required_rights)
                self.assertEqual(LEGACY_RISK, plan.declared_risk)

        irreversible = [t for t in write_path.ALL_TOOLS
                        if t().risk_class is Risk.IRREVERSIBLE]
        self.assertEqual([REVOKE_AUTHORITY], [t().name for t in irreversible])

    def test_06_existing_plan_identities_are_byte_for_byte_unchanged(self):
        """`I-112` hashes BOTH `declared_risk` and `required_rights`, so a
        derivation that produced a different answer for an existing tool would
        invalidate every approval already stored against it -- silently, at
        `decide()`, as "plan identity differs".

        Asserted by REBUILDING each plan the old way, with the constants
        `plan_for_action` used to hardcode, and comparing identities.
        """
        cases = [
            (TOOL, {"item_ref": "n1", "body": NOTE}),
            (ADD_TASK, {"task_ref": "t1", "title": "Call them", "due_on": ""}),
            (COMPLETE_TASK, {"task_ref": "t1"}),
            (ADD_SCOPE, {"scope_name": "acme", "kind": "client"}),
        ]
        for tool_name, arguments in cases:
            with self.subTest(tool=tool_name):
                legacy = Plan(
                    steps=(PlanStep(action=tool_name, resource=A,
                                    tool_name=tool_name,
                                    required_rights=LEGACY_RIGHTS,
                                    arguments=dict(arguments)),),
                    required_rights=LEGACY_RIGHTS,
                    declared_risk=LEGACY_RISK,
                    scope_path=A,
                    taint=Taint.of(UNKNOWN_ORIGIN),
                    cost_estimate=1)
                self.assertEqual(
                    legacy.identity(),
                    self.writes.plan_for_action(A, tool_name, arguments).identity(),
                    "an existing tool's plan identity changed -- every approval"
                    " already stored against it would stop matching")

        # ...and the new tool is NOT the same plan as any of them.
        revoke = self.writes.plan_for_action(
            A, REVOKE_AUTHORITY, {"execution_identity": "x", "target_ref": "n1"})
        self.assertNotIn(revoke.identity(),
                         {self.writes.plan_for_action(A, t, a).identity()
                          for t, a in cases})

    # =======================================================================
    # 7-9 -- the token follows the approval, and cannot exceed the grant
    # =======================================================================

    def test_07_the_execution_token_follows_the_approved_risk_class(self):
        """Element 8b. The decision route re-issues the execution token with the
        rights the approved plan requires and a ceiling equal to the approved
        risk class -- BOTH read from the durable approval row, never from the
        browser and never assumed to be `write`/EXECUTE.

        Observed at issuance rather than inferred from the outcome: a token that
        happened to be wider would still succeed, and this must fail if it is.
        """
        authority = self.note("n1", NOTE)
        _, status, page = self.revoke_through_seam(A, "item", "n1")
        self.assertEqual(200, status, page)
        self.assertIn((frozenset({"revoke"}), Risk.IRREVERSIBLE), self.issued,
                      "no IRREVERSIBLE/{revoke} token was issued -- the"
                      " execution token did not follow the approval")
        self.assert_revoked(authority, A)

        # ...and an ORDINARY approval still gets the ordinary token. The
        # derivation must not have widened the default for everything else.
        self.issued.clear()
        approval_id = self.approvals.propose_action(
            self.token(A), A, ADD_TASK,
            {"task_ref": "t1", "title": "Ordinary", "due_on": ""},
            action_text="Ordinary.", if_wrong_text="Wrong.")
        self.seam.decide_page(self.sid, A, approval_id, True)
        self.assertNotIn(Risk.IRREVERSIBLE, [c for _, c in self.issued],
                         "an EXECUTE approval was given an IRREVERSIBLE token")
        self.assertIn((frozenset({"write"}), Risk.EXECUTE), self.issued)

    def test_08_an_execution_cannot_exceed_the_ceiling_it_was_issued(self):
        """`I-101` at the PDP's step 6, which is the check the whole risk-class
        propagation exists to feed. The token carries the RIGHT -- so step 5
        passes -- and is still refused, because its ceiling is `EXECUTE` and the
        plan declares `IRREVERSIBLE`."""
        authority = self.note("n1", NOTE)
        token = self.token(A, frozenset({"revoke"}), Risk.EXECUTE)
        with self.assertRaises(Denied) as denied:
            self.execute_revoke(token, A, authority)
        self.assertEqual("I-101", denied.exception.invariant)
        self.assert_no_revocation()

    def test_09_i106_still_refuses_a_ceiling_no_grant_confers(self):
        """The prerequisite `36b4dee` shipped, still load-bearing here. Without
        it, element 8c would be decorative: anything could ask for an
        `IRREVERSIBLE` token while holding only `write`, and the separate right
        would gate nothing at issuance."""
        for rights in (frozenset({"write"}), frozenset({"read", "write"}),
                       frozenset({"read"})):
            with self.subTest(rights=sorted(rights)):
                with self.assertRaises(Denied) as denied:
                    self.token(A, rights, Risk.IRREVERSIBLE)
                self.assertEqual("I-106", denied.exception.invariant)

        # INVERSION: the right that DOES confer it is issued without complaint.
        token = self.revoke_token(A)
        self.assertEqual(Risk.IRREVERSIBLE, token.risk_ceiling)
        self.assertEqual(frozenset({"revoke"}), token.granted_rights)

    # =======================================================================
    # 10-11 -- proposing, and approving
    # =======================================================================

    def test_10_proposing_revokes_nothing(self):
        """ADR 0052 element 1: the act is an approval. The proposal surface has
        no path to `RevocationRegistry` at all -- asserted by tripwire, not by
        reading the code -- and leaves a pending approval and nothing else."""
        self.note("n1", NOTE)
        touched = []
        self.revocations.revoke = lambda *a, **kw: touched.append("revoke")
        self.revocations.revoke_on = lambda *a, **kw: touched.append("revoke_on")

        status, page = self.propose_through_seam(A, "item", "n1")
        self.assertEqual(200, status, page)
        self.assertEqual([], touched, "proposing reached the registry")
        self.assert_no_revocation("proposing performed the act")
        self.assert_pending(self.pending_revocation_id())

    def test_11_the_identity_is_derived_from_the_row_and_the_approval_lands(self):
        """The whole human path, and the two properties that make it safe.

        THE BROWSER NEVER NAMES AN AUTHORITY. It sends a row kind and a ref; the
        server reads `creating_authority` off that row through a scope-bound
        channel and PINS it into the approval's arguments, so `I-109`/`I-112`
        bind the authority James was SHOWN.

        AND IT LANDS AT THE AUTHORITY'S OWN SCOPE (`F-9`), with the `W-1` record
        the recovery path depends on.
        """
        authority = self.note("n1", NOTE)
        status, page = self.propose_through_seam(A, "item", "n1")
        self.assertEqual(200, status, page)

        approval_id = self.pending_revocation_id()
        stored = self.sql("SELECT arguments FROM approval"
                          " WHERE approval_id = %s", (approval_id,))[0][0]
        self.assertEqual(authority, stored["execution_identity"],
                         "the pinned identity is not the row's own author")
        self.assertEqual("n1", stored["target_ref"])

        ceremony, assertion = self.step_up(approval_id)
        status, page = self.seam.decide_page(self.sid, A, approval_id, True,
                                             ceremony_id=ceremony,
                                             assertion=assertion)
        self.assertEqual(200, status, page)
        self.assert_revoked(authority, A)
        self.assertEqual([(authority, A, "james")], self.revocation_rows())

        # `W-1`, in the scope it happened in (`I-49`), naming what a HUMAN
        # pointed at rather than the opaque identity (element 2).
        records = self.sql("SELECT scope_path, detail FROM audit_record"
                           " WHERE category = 'data.write'"
                           " AND detail LIKE %s", (REVOKE_AUTHORITY + "%",))
        self.assertEqual([(A, f"{REVOKE_AUTHORITY} target_ref=n1")], records)

    # =======================================================================
    # 12-15 -- the approval binding
    # =======================================================================

    def test_12_an_approval_edited_to_name_another_authority_does_not_execute(self):
        """`I-112`. The approval James saw named ONE authority. Editing the
        stored arguments afterwards -- the only way to point a decided approval
        somewhere else -- changes the plan identity, and `decide()` refuses
        before anything executes."""
        self.note("n1", NOTE)
        other = self.note("n2", OTHER_NOTE)
        status, _ = self.propose_through_seam(A, "item", "n1")
        self.assertEqual(200, status)
        approval_id = self.pending_revocation_id()

        self.sql("UPDATE approval SET arguments = %s WHERE approval_id = %s",
                 (json.dumps({"execution_identity": other, "target_ref": "n1"}),
                  approval_id))

        ceremony, assertion = self.step_up(approval_id)
        status, _ = self.seam.decide_page(self.sid, A, approval_id, True,
                                          ceremony_id=ceremony,
                                          assertion=assertion)
        self.assertEqual(403, status)
        self.assert_no_revocation("a tampered approval revoked an authority")

    def test_13_another_actor_can_neither_propose_nor_decide_nor_step_up(self):
        """`I-09`: only James approves, and only James proposes here. Checked
        server-side from the SESSION -- never from anything a browser asserts --
        and the passkey binding is checked against that same session, so an
        enrolled credential belonging to someone else proves nothing about
        James being present."""
        authority = self.note("n1", NOTE)
        mallory_key = authfixture.enrol(self.auth, "mallory", "mallory", "other")
        mallory = authfixture.sign_in(self.auth, mallory_key)

        self.assertEqual(403, self.propose_through_seam(
            A, "item", "n1", session_id=mallory)[0])
        self.assert_no_revocation()

        # James proposes; Mallory tries to decide it.
        self.assertEqual(200, self.propose_through_seam(A, "item", "n1")[0])
        approval_id = self.pending_revocation_id()
        self.assertEqual(403, self.seam.decide_page(mallory, A, approval_id,
                                                    True)[0])
        self.assert_pending(approval_id)

        # ...and Mallory's credential cannot satisfy JAMES's step-up either.
        ceremony, assertion = self.step_up(approval_id, key=mallory_key)
        status, _ = self.seam.decide_page(self.sid, A, approval_id, True,
                                          ceremony_id=ceremony,
                                          assertion=assertion)
        self.assertEqual(401, status)
        self.assert_pending(approval_id)
        self.assert_no_revocation()
        self.assertIsNotNone(authority)

    def test_14_an_approval_and_a_row_are_reachable_only_from_their_own_scope(self):
        """`I-03`/`I-86`, inherited from RLS rather than re-implemented, plus
        `F-10`'s rule that the statement is pinned to the CHANNEL's scope.

        Three refusals, all fail-closed and all indistinguishable from
        "nonexistent", which is the correct answer rather than a leak:
          * a sibling cannot see the row
          * the PARENT cannot reach a child's row either -- reachability runs
            downward, but the proposal is pinned to `scope_path = ch.scope_path`
          * an approval created in `A` cannot be decided from `B`
        """
        self.note("n1", NOTE)
        self.assertEqual(404, self.propose_through_seam(B, "item", "n1")[0],
                         "a sibling reached the row")
        self.assertEqual(404, self.propose_through_seam(BUSINESS, "item", "n1")[0],
                         "the parent's proposal reached a child's row")
        self.assertEqual([], self.revocation_approvals(),
                         "an unreachable row still produced a proposal")

        self.assertEqual(200, self.propose_through_seam(A, "item", "n1")[0])
        approval_id = self.pending_revocation_id()
        ceremony, assertion = self.step_up(approval_id)
        status, _ = self.seam.decide_page(self.sid, B, approval_id, True,
                                          ceremony_id=ceremony,
                                          assertion=assertion)
        self.assertEqual(403, status, "an approval was decided from another scope")
        self.assert_pending(approval_id)
        self.assert_no_revocation()

    def test_15_a_revocation_approval_is_single_use(self):
        """`I-09`. A second decision on the same approval is refused even with a
        second, entirely valid step-up ceremony -- and leaves ONE row."""
        authority = self.note("n1", NOTE)
        approval_id, status, page = self.revoke_through_seam(A, "item", "n1")
        self.assertEqual(200, status, page)

        ceremony, assertion = self.step_up(approval_id)
        status, _ = self.seam.decide_page(self.sid, A, approval_id, True,
                                          ceremony_id=ceremony,
                                          assertion=assertion)
        self.assertEqual(409, status)
        self.assertEqual([(authority, A, "james")], self.revocation_rows())

    # =======================================================================
    # 16 -- one transaction (element 8d)
    # =======================================================================

    def test_16_the_registry_row_and_its_audit_record_commit_together(self):
        """ELEMENT 8d, ASSERTED BY INVERSION.

        `DataAccessBoundary.open` takes a SEPARATE pooled connection and starts
        a SEPARATE transaction, so a transport that called `revoke()` would put
        the registry row in one transaction and its `W-1` record in another.
        `ApprovalService.recover()` decides an interrupted execution by whether
        that record exists -- an answer worth nothing if the two can commit
        apart.

        CONTROL: a successful revocation leaves both.
        INVERSION: interrupt the audit write, in the same `with` block, and the
        registry row must be GONE. If it survives, the two are not one
        transaction and `recover()` is reading a fiction.
        """
        first = self.note("n1", NOTE)
        second = self.note("n2", OTHER_NOTE)

        # CONTROL.
        self.execute_revoke(self.revoke_token(A), A, first)
        self.assert_revoked(first, A)
        self.assertEqual(
            1, self.sql("SELECT count(*) FROM audit_record"
                        " WHERE category='data.write' AND detail LIKE %s",
                        (REVOKE_AUTHORITY + "%",))[0][0])

        # INVERSION -- the audit write fails, after the registry row is in.
        original = write_path.execution_event_identity

        def interrupted(*args, **kwargs):
            raise RuntimeError("audit write interrupted")

        write_path.execution_event_identity = interrupted
        try:
            with self.assertRaises(RuntimeError):
                self.execute_revoke(self.revoke_token(A), A, second, target="n2")
        finally:
            write_path.execution_event_identity = original

        self.assertEqual(
            [], self.sql("SELECT 1 FROM authority_revocation"
                         " WHERE execution_identity = %s", (second,)),
            "the registry row survived a failed audit write -- the revocation"
            " and its W-1 record are NOT in one transaction")

    def test_16b_the_transport_does_not_open_a_second_channel(self):
        """The same property from the other side. `revoke()` opens its own
        channel; `revoke_on()` uses the caller's. The transport must call the
        latter, so a tripwire on the former stays untouched -- and the
        revocation must still land, or the tripwire would be proving nothing."""
        authority = self.note("n1", NOTE)
        opened = []
        self.revocations.revoke = lambda *a, **kw: opened.append("revoke")

        self.execute_revoke(self.revoke_token(A), A, authority)

        self.assertEqual([], opened,
                         "the transport opened a second channel to revoke")
        self.assert_revoked(authority, A)

    # =======================================================================
    # 17-18 -- scope
    # =======================================================================

    def test_17_a_revoke_grant_on_the_parent_reaches_the_child(self):
        """Grants flow DOWNWARD by containment. `revoke` is granted at
        `/business` only, and that is what authorizes a revocation in
        `/business/client-a` -- no per-scope grant, and no widening."""
        self.assertEqual(
            [(BUSINESS,)],
            self.sql("SELECT scope_path FROM \"grant\" WHERE right_name='revoke'"))
        grant = self.tree.find_grant("james", "revoke", "*", A)
        self.assertIsNotNone(grant)
        self.assertEqual(BUSINESS, grant.scope_path)
        self.assertEqual(Risk.IRREVERSIBLE, grant.max_risk)
        # ...and it is not reachable sideways: `/life` is not below `/business`.
        self.assertIsNone(self.tree.find_grant("james", "revoke", "*", LIFE))

        authority = self.note("n1", NOTE)
        _, status, page = self.revoke_through_seam(A, "item", "n1")
        self.assertEqual(200, status, page)
        self.assert_revoked(authority, A)

    def test_18_siblings_have_no_path_to_each_others_revocations(self):
        """`I-03`. Two halves, and both matter:

        WRITING -- an authority whose work lies in `A` cannot be revoked from
        `B`. `F-9` derives the authority's scope from the rows that name it,
        reads through the revoker's OWN channel, finds none, and FAILS CLOSED
        rather than filing the record at the revoker's scope.

        READING -- once revoked in `A`, the record is visible from `A` and from
        its ancestor, and INVISIBLE from `B`. That invisibility is exactly why
        `_establish` must never read a missing record as "not revoked": here
        absence is a scope boundary, not an answer.
        """
        authority = self.note("n1", NOTE)

        with self.assertRaises(Denied) as denied:
            self.execute_revoke(self.revoke_token(B), B, authority)
        self.assertEqual("I-111", denied.exception.invariant)
        self.assertTrue(denied.exception.security_event)
        self.assert_no_revocation()

        self.execute_revoke(self.revoke_token(A), A, authority)
        self.assertTrue(self.revocations.is_revoked(
            self.token(A, frozenset({"read"}), Risk.READ), authority))
        self.assertTrue(self.revocations.is_revoked(
            self.token(BUSINESS, frozenset({"read"}), Risk.READ), authority))
        self.assertFalse(self.revocations.is_revoked(
            self.token(B, frozenset({"read"}), Risk.READ), authority),
            "a sibling could see another scope's revocation")

    # =======================================================================
    # 19 -- the step-up gate fires because the class propagated
    # =======================================================================

    def test_19_the_irreversible_class_reaches_the_step_up_gate(self):
        """`I-67`/`A-3`, and the reason element 8b exists at all.

        `_requires_step_up` reads the APPROVAL ROW's `risk_class` column, which
        is written from the plan, which is written from the tool declaration.
        Had `plan_for_action` kept its `Risk.EXECUTE` constant, this column
        would say EXECUTE, the gate would never engage, and an irreversible act
        would be decided by a session established hours earlier -- silently.

        Asserted at the column, at the predicate, and by consequence.
        """
        self.note("n1", NOTE)
        self.assertEqual(200, self.propose_through_seam(A, "item", "n1")[0])
        approval_id = self.pending_revocation_id()

        self.assertEqual("IRREVERSIBLE",
                         self.sql("SELECT risk_class FROM approval"
                                  " WHERE approval_id = %s", (approval_id,))[0][0])
        request = self.approvals.get(self.token(A), approval_id)
        self.assertTrue(_requires_step_up(request))

        status, _ = self.seam.decide_page(self.sid, A, approval_id, True)
        self.assertEqual(401, status, "an irreversible act was decided without"
                                      " fresh authentication")
        self.assert_pending(approval_id)
        self.assert_no_revocation()

        # INVERSION: an ordinary approval, same route, same absent assertion.
        ordinary = self.approvals.propose_action(
            self.token(A), A, ADD_TASK,
            {"task_ref": "t1", "title": "Ordinary", "due_on": ""},
            action_text="Ordinary.", if_wrong_text="Wrong.")
        self.assertEqual("EXECUTE",
                         self.sql("SELECT risk_class FROM approval"
                                  " WHERE approval_id = %s", (ordinary,))[0][0])
        self.assertFalse(_requires_step_up(
            self.approvals.get(self.token(A), ordinary)))
        self.assertEqual(200, self.seam.decide_page(self.sid, A, ordinary, True)[0])

    # =======================================================================
    # 20 -- end to end, into F-13
    # =======================================================================

    def test_20_a_revocation_through_the_seam_reaches_the_f13_label(self):
        """THE WHOLE POINT, end to end. James points at a note, approves with
        his passkey, and the next time that note is assembled into model context
        it arrives RETAINED and MARKED -- `S7-D5`, via `F-13`/ADR 0051.

        Nothing here bypasses authorization: the marker appears because a
        registry row exists, and the registry row exists because
        `authorize_plan` allowed an `IRREVERSIBLE` plan under a `revoke` grant.
        The note beside it, written by an untouched authority, is not marked --
        so the label is about THIS authority and not about the reader's mood.
        """
        self.note("n1", NOTE)
        self.note("n2", OTHER_NOTE)
        context, _ = self.block(A)
        self.assertIn(NOTE, context, "control: the note never arrived")
        self.assertNotIn(_REVOKED_MARK.strip(), context)

        _, status, page = self.revoke_through_seam(A, "item", "n1")
        self.assertEqual(200, status, page)

        context, _ = self.block(A)
        marked = [line for line in context.splitlines() if NOTE in line]
        self.assertTrue(marked, "the revoked authority's note was WITHHELD --"
                                " S7-D5 requires it retained and labelled")
        self.assertIn(_REVOKED_MARK.strip(), marked[0])
        untouched = [line for line in context.splitlines() if OTHER_NOTE in line]
        self.assertTrue(untouched)
        self.assertNotIn(_REVOKED_MARK.strip(), untouched[0])

    def test_21_a_task_is_revocable_the_same_way(self):
        """ADR 0049 made a task title CONTENT and gave `task` the same `I-111`
        columns, and `F-9`'s derivation covers both tables in one union. The
        selection surface must therefore offer both -- a task-writing authority
        that could not be revoked would be every approval-decided authority
        NOVA has."""
        authority = self.task("t1", "MARKER-TASK-call-the-supplier")
        self.assertEqual([], self.sql("SELECT 1 FROM item"))

        _, status, page = self.revoke_through_seam(A, "task", "t1")
        self.assertEqual(200, status, page)
        self.assert_revoked(authority, A)

    def test_22_a_row_with_no_recorded_authority_revokes_nothing(self):
        """`I-110`: unknown is not recoverable by inference. A legacy row
        predating `I-111` names no authority, so there is nothing to revoke and
        nothing to guess -- 404, and no approval created."""
        self.sql("INSERT INTO item (item_ref, scope_path, body)"
                 " VALUES ('legacy', %s, %s)", (A, "MARKER-LEGACY"))
        status, _ = self.propose_through_seam(A, "item", "legacy")
        self.assertEqual(404, status)
        self.assertEqual([], self.revocation_approvals())
        self.assert_no_revocation()

    def test_23_revoking_twice_is_one_record_and_keeps_the_first_time(self):
        """`idempotent=True` is a claim about the PROVIDER, and this is what
        makes it true: `UNIQUE (execution_identity)` with `ON CONFLICT DO
        NOTHING`. Moving the timestamp forward on a re-revoke would quietly
        narrow the window in which an authority counts as revoked."""
        authority = self.note("n1", NOTE)
        self.execute_revoke(self.revoke_token(A), A, authority)
        first = self.sql("SELECT revoked_at FROM authority_revocation"
                         " WHERE execution_identity = %s", (authority,))[0][0]

        self.execute_revoke(self.revoke_token(A), A, authority)
        rows = self.sql("SELECT revoked_at FROM authority_revocation"
                        " WHERE execution_identity = %s", (authority,))
        self.assertEqual(1, len(rows))
        self.assertEqual(first, rows[0][0])

    def test_24_the_approver_identity_is_still_the_only_one(self):
        """Guard against the constant drifting. `I-09` names one approver, and
        `F-3` did not add a second."""
        self.assertEqual("james", APPROVER_IDENTITY)

    # =======================================================================
    # 25 -- over HTTP, because a surface nobody can reach revokes nothing
    # =======================================================================

    def test_25_the_surface_and_the_route_exist_over_real_http(self):
        """Every test above calls seam methods directly, which proves the logic
        and NOTHING about the entry point. A `/scope/<path>/revoke` path that
        fell through to another handler -- or a control that never rendered --
        would leave `F-3` unreachable while all of this still passed.

        So: real server, real page, real form POST. And the POST still only
        PROPOSES, which is the one property the route must not quietly change.
        """
        import urllib.error
        import urllib.parse
        import urllib.request
        from ..seam import serve

        self.note("n1", NOTE)
        self.task("t1", "MARKER-TASK-call-the-supplier")

        server, port = serve(self.seam)
        try:
            base = f"http://127.0.0.1:{port}/scope{A}"

            def request(url, data=None):
                req = urllib.request.Request(
                    url, data=data, method="POST" if data else "GET")
                req.add_header("Cookie", f"nova_session={self.sid}")
                try:
                    with urllib.request.urlopen(req, timeout=10) as r:
                        return r.status, r.read().decode()
                except urllib.error.HTTPError as e:
                    return e.code, e.read().decode()

            status, page = request(base)
            self.assertEqual(200, status)
            self.assertIn(f"action=\"/scope{A}/revoke\"", page,
                          "the scope page offers no way to revoke anything")
            self.assertIn("value=\"item\"", page)
            self.assertIn("value=\"task\"", page)

            status, page = request(
                base + "/revoke",
                urllib.parse.urlencode({"kind": "item", "ref": "n1"}).encode())
            self.assertEqual(200, status, page)
            self.assertIn("Nothing has been revoked yet", page)
            self.assert_no_revocation("the route revoked without an approval")
            self.assert_pending(self.pending_revocation_id())
        finally:
            server.shutdown()


if __name__ == "__main__":
    unittest.main()
