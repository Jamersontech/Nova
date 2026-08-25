"""F-11 / ADR 0050: a scope name is CONTROL state, and NOVA says so honestly.

THE RULING (ADR 0050, drafted on James's F-11 decision of 2026-08-25). A scope
name is a SCOPE-BEARING IDENTIFIER -- `MT-5` classifies exactly that category as
bound, and `I-100` enumerates it among consequence-determining arguments -- so
it is CONTROL/ADDRESSING state governed by `I-100`'s envelope, NOT content
governed by `I-111`.

So this suite asserts the ruling's NEGATIVES as hard as its positive: `scope`
gains no provenance columns, `scope_name` stays CONSEQUENCE, `add_scope` stays
structurally incapable of elevation, and the envelope still pins the exact name.
Those are what would quietly rot into a CONTENT implementation if nothing
watched them.

THE ONE DEFECT THAT WAS REAL. The model-context block was attributed
`Taint.of("james.stated", CONFIDENTIAL)` -- HIGHEST -- and justified as covering
"the scope path and the pending count, both NOVA's own facts". `add_scope` lets
a MODEL choose a path segment, so that premise is false. `Taint.union` takes the
lowest trust, so any item or task already dominated the base; the case that
mattered is the EMPTY scope, which is the normal state of a freshly created one,
where the block's taint IS the base and NOVA asserted `james.stated`/HIGHEST
over bytes a model chose.

THE CORRECTION IS COARSE ON PURPOSE. Under this ruling `scope` carries no
provenance, so nothing can reconstruct which segment a model chose. Inventing
one is what `I-110` forbids. The base is therefore the `I-99` union with
`UNKNOWN_ORIGIN` -- the term `write_path` already defines for "nobody said where
this came from" -- which says only what is known and lowers trust rather than
raising it (`I-110`: "lowering trust is not governed by this invariant").

WHAT THIS IS NOT. Not a withholding rule: the scope path is ADDRESSING and stays
in the block, because a model that cannot see where it is cannot answer about
where it is. Not an `I-40` change. Not a change to any item or task taint.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_scope_name_attribution
"""

from __future__ import annotations

import dataclasses
import os
import tempfile
import unittest

from .. import db, tree_store
from ..approval_flow import ApprovalService
from ..attention import AttentionService
from ..boundary import DataAccessBoundary
from ..conversation import CONVERSATION_MODEL, PROVIDER, ConversationService
from ..revocation import RevocationRegistry
from ..seam import Seam
from ..write_path import (ADD_SCOPE, ADD_TASK, COMPLETE_TASK,
                          PostgresItemIntegration, TOOL, UNKNOWN_ORIGIN,
                          WritePath, add_scope_tool, add_task_tool,
                          complete_task_tool, write_item_tool)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.budget import BudgetLedger
from ...core.context_service import ContextService
from ...core.gateway import ModelGateway, ModelResponse, ProviderBinding
from ...core.policy import PolicyDecisionPoint
from ...core.store import StoreRegistry
from ...core.types import Classification, Denied, Risk, Taint, Trust
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

BUSINESS = "/business"
A = "/business/client-a"
B = "/business/client-b"
SCOPES = [(BUSINESS, "domain", None), (A, "client", BUSINESS), (B, "client", BUSINESS)]
GRANTS = [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")]
CRED_REF = "control-plane/anthropic"

# A name a model might choose that reads like a claim. One lowercase segment --
# the marker grammar allows nothing else -- which is the whole of the channel.
MODEL_NAME = "wire-to-acct-99182-urgent"
JAMES_NOTE = "MARKER-NOTE-the-quarter-closes-friday"
A_NOTE = "MARKER-A-NOTE-margin-is-38-percent"
B_NOTE = "MARKER-B-NOTE-they-are-late-on-payment"
WEB_NOTE = "MARKER-WEB-their-bank-details-changed"


class ScriptedTransport:
    def __init__(self):
        self.prompts: list[str] = []
        self.replies: list[str] = []

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        text = self.replies.pop(0) if self.replies else "Noted."
        return ModelResponse(
            text=text, taint=Taint.of("model.generated", Classification.INTERNAL))


class ScopedWritePath(WritePath):
    """The production parameterization (`app.py`): the datastore credential
    binding is per-scope, because `I-24` requires a token's scope to COVER its
    binding's scope and coverage runs downward only."""

    def binding_for(self, scope_path: str, tool_name: str = TOOL):
        return dataclasses.replace(super().binding_for(scope_path, tool_name),
                                   credential_binding_id=f"db-item-write{scope_path}")


@unittest.skipUnless(db.available(),
                     "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class ScopeNameAttributionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-f11-")
        self.context = ContextService(self.tree, secret=b"f11-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        self.broker = CredentialBroker(self.tree, vault, audit)
        for scope in (BUSINESS, A, B):
            self._bind(scope)
        self.registry = ToolRegistry()
        for factory in (write_item_tool, add_task_tool, complete_task_tool,
                        add_scope_tool):
            self.registry.register(factory())
        pep = ToolPEP(self.registry, self.broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)

        # The production post-commit hook (`app.py`): a new scope joins the
        # in-process tree and gets its own credential binding. Without it a
        # scope the model just created could not be entered at all.
        def on_scope_created(path, kind):
            self.tree.add_scope(path, kind)
            self._bind(path)

        self.integration.on_scope_created = on_scope_created

        self.writes = ScopedWritePath(self.pdp, self.registry, pep, self.broker,
                                      self.integration, "unused-see-subclass")
        self.approvals = ApprovalService(self.boundary, self.writes)
        self.revocations = RevocationRegistry(self.boundary, self.context)
        self.attention = AttentionService(self.tree, self.context, self.pdp,
                                          self.boundary)

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
            self.gateway, self.pdp, self.boundary, self.approvals,
            budget=self.budget)

        self.auth = authfixture.service()
        self.sid = authfixture.sign_in(
            self.auth, authfixture.enrol(self.auth, "james", "james"))
        self.seam = Seam(self.context, self.pdp, self.boundary, self.auth,
                         write_path=self.writes, approvals=self.approvals,
                         tree=self.tree, conversation=self.conversation,
                         attention=self.attention, revocations=self.revocations)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def _bind(self, scope):
        self.broker.register(
            CredentialBinding(
                binding_id=f"db-item-write{scope}", scope_path=scope,
                permitted_operations=frozenset({TOOL, ADD_TASK, COMPLETE_TASK,
                                                ADD_SCOPE})),
            secret="integration-credential-" + os.urandom(4).hex())

    def token(self, scope=BUSINESS, rights=frozenset({"write"}),
              ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=rights,
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

    def run_action(self, scope, tool_name, arguments, taint=None):
        approval_id = self.approvals.propose_action(
            self.token(scope), scope, tool_name, arguments,
            action_text=f"{tool_name} here.", if_wrong_text="Wrong thing.",
            taint=taint or Taint.of("james.stated", Classification.CONFIDENTIAL))
        executor = self.token(scope)
        self.approvals.decide(executor, approval_id, True, decided_by="james")
        return executor.trace_id

    def note(self, scope, ref, body, taint=None):
        return self.run_action(scope, TOOL, {"item_ref": ref, "body": body}, taint)

    def task(self, scope, ref, title, taint=None):
        return self.run_action(
            scope, ADD_TASK, {"task_ref": ref, "title": title, "due_on": ""}, taint)

    def model_creates_a_scope(self, name=MODEL_NAME, parent=BUSINESS):
        """The production route, end to end: the MODEL emits the marker, the
        server records a proposal, James approves, the scope exists."""
        self.transport.replies = [
            f'I can make a place for that.\n'
            f'[[PROPOSE_SCOPE name="{name}" kind="client"]]']
        turn = self.conversation.respond(
            self.token(parent, frozenset({"read"}), Risk.READ), parent,
            "make a place for that",
            execute_token=self.token(parent))
        self.assertEqual("proposed", turn.state,
                         "the model's PROPOSE_SCOPE marker was not recorded")
        self.approvals.decide(self.token(parent), turn.approval_id, True,
                              decided_by="james")
        return f"{parent}/{name}"

    def block(self, scope):
        """The scope-context block and its taint, as the gateway would receive
        them."""
        return self.conversation._scope_context(
            self.token(scope, frozenset({"read"}), Risk.READ), scope)

    # =======================================================================
    # 1-3 -- the line-325 correction
    # =======================================================================

    def test_01_a_model_named_empty_scope_is_not_attributed_to_james(self):
        """THE DEFECT, directly. A freshly created scope is EMPTY, so the
        block's taint IS the base -- there is no item or task to drag it down.
        Before the correction NOVA asserted `james.stated`/HIGHEST over a path
        segment a model chose."""
        path = self.model_creates_a_scope()
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.assertEqual([], self.sql("SELECT 1 FROM task"))

        _, taint = self.block(path)

        self.assertNotEqual(Trust.HIGHEST, taint.trust,
                            "NOVA asserted HIGHEST trust over a block whose"
                            " scope path a model chose")
        self.assertEqual(Trust.LOW, taint.trust)
        self.assertIn(UNKNOWN_ORIGIN, taint.provenance,
                      "the block does not record that some of it is of unknown"
                      " origin")
        self.assertNotEqual(frozenset({"james.stated"}), taint.provenance,
                            "the block still claims James stated all of it")

    def test_02_the_scope_path_is_still_shown_to_the_model(self):
        """ADR 0050 lowered the ATTRIBUTION; it did not withhold the path. A
        scope name is ADDRESSING, and a model that cannot see where it is
        cannot answer about where it is. This is the line that separates this
        ruling from the CONTENT one."""
        path = self.model_creates_a_scope()
        context, _ = self.block(path)
        self.assertIn(f"Scope: {path}", context,
                      "the scope path was withheld -- that is the CONTENT"
                      " ruling's behaviour, not this one")
        self.assertIn(MODEL_NAME, context)

    def test_03_the_correction_does_not_reclassify_or_trip_i40(self):
        """Two properties the lowering must not disturb: the block stays
        CONFIDENTIAL so the gateway's `I-95` still sees scoped material rather
        than ambient INTERNAL text, and `is_untrusted_derived()` stays False
        because neither base term is external."""
        path = self.model_creates_a_scope()
        _, taint = self.block(path)

        self.assertEqual(Classification.CONFIDENTIAL, taint.classification)
        self.assertFalse(taint.is_untrusted_derived(),
                         "the base taint began tripping I-40 on its own")
        self.assertEqual(frozenset(), taint.external_sources())

    # =======================================================================
    # 4-6 -- content attribution is untouched
    # =======================================================================

    def test_04_james_stated_content_keeps_its_own_attribution(self):
        """The correction is to the BASE, not to content. A note James stated
        and approved still persists exactly what ADR 0048 gives it -- origin
        retained, `james.approved` added, HIGHEST because he read the exact
        bytes -- and still reaches the model. F-11 touches none of that."""
        self.note(BUSINESS, "n1", JAMES_NOTE)
        row = self.sql("SELECT provenance, trust FROM item WHERE item_ref='n1'")
        self.assertEqual([(["james.approved", "james.stated"], int(Trust.HIGHEST))],
                         row, "the item's own persisted attribution changed")
        self.assertNotIn(UNKNOWN_ORIGIN, row[0][0],
                         "the base correction leaked into a content row")
        context, _ = self.block(BUSINESS)
        self.assertIn(JAMES_NOTE, context)

    def test_05_an_approved_elevation_is_unchanged(self):
        """ADR 0048 is untouched: content James read and approved still
        elevates to `james.approved`/HIGHEST on its own row."""
        self.note(BUSINESS, "n1", WEB_NOTE,
                  Taint.of("external.web", Classification.CONFIDENTIAL))
        row = self.sql("SELECT provenance, trust FROM item WHERE item_ref='n1'")
        self.assertEqual([(["external.web", "james.approved"], int(Trust.HIGHEST))],
                         row, "ADR 0048's elevation changed")

    def test_06_external_content_still_trips_i40_through_the_block(self):
        """`I-40` still fires on external content and only on external content.
        The base cannot mask it: union keeps every contributing provenance."""
        self.note(BUSINESS, "n1", WEB_NOTE,
                  Taint.of("external.web", Classification.CONFIDENTIAL))
        _, taint = self.block(BUSINESS)
        self.assertTrue(taint.is_untrusted_derived(),
                        "an external-web note stopped tripping I-40")
        self.assertEqual(frozenset({"external.web"}), taint.external_sources())

    # =======================================================================
    # 7-9 -- the B ruling's NEGATIVES, asserted so they cannot rot
    # =======================================================================

    def test_07_scope_carries_no_i111_provenance_columns(self):
        """ADR 0050 consequence 3. If a later change adds these columns, the
        ruling has been reversed without a decision."""
        columns = {r[0] for r in self.sql(
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_name = 'scope' AND table_schema = 'public'")}
        self.assertEqual(
            {"id", "scope_path", "kind", "parent_path", "created_at"}, columns,
            "the scope table gained columns -- F-11 was ruled"
            " CONTROL/ADDRESSING, so it carries no provenance")
        for forbidden in ("provenance", "trust", "classification",
                          "delegation_ancestry", "creating_authority"):
            self.assertNotIn(forbidden, columns)

    def test_08_scope_name_remains_consequence_determining(self):
        """ADR 0050 consequences 1 and 4, and the reason for both: `MT-5` bounds
        a scope-bearing identifier, and an EXPRESSIVE argument is NOT policed by
        `I-100`'s envelope. Reclassifying would trade the pinning away."""
        definition = self.registry.get(ADD_SCOPE, "1.0.0")
        self.assertTrue(definition.is_consequence_determining("scope_name"))
        self.assertTrue(definition.is_consequence_determining("kind"))
        self.assertEqual(frozenset(), self.writes.content_leaves(ADD_SCOPE),
                         "add_scope gained a content leaf -- that is the"
                         " CONTENT ruling, which was rejected")

    def test_09_add_scope_cannot_elevate_and_records_no_elevation(self):
        """ADR 0050 consequence 4 and `F-8`, together. With no content leaf
        there is nothing for James to inspect, so no elevation is possible --
        a property of the tool, not a check that could be forgotten."""
        self.model_creates_a_scope()
        self.assertEqual([], self.sql(
            "SELECT 1 FROM audit_record WHERE category = 'trust.elevation'"),
            "add_scope emitted a trust elevation")

    def test_10_the_envelope_still_binds_the_exact_scope_name(self):
        """`I-100`, which is what the B ruling relies on INSTEAD of provenance.
        An approval for one name does not authorize another."""
        approval_id = self.approvals.propose_action(
            self.token(BUSINESS), BUSINESS, ADD_SCOPE,
            {"scope_name": "alpha", "kind": "client"},
            action_text="Create alpha.", if_wrong_text="Wrong place.",
            taint=Taint.of("james.stated", Classification.CONFIDENTIAL))
        self.approvals.decide(self.token(BUSINESS), approval_id, True,
                              decided_by="james")

        # The approval was spent on `alpha`; `beta` is a different plan and has
        # no approval of its own.
        with self.assertRaises(Denied) as cm:
            self.writes.execute_action(
                self.token(BUSINESS), BUSINESS, ADD_SCOPE,
                {"scope_name": "beta", "kind": "client"},
                Taint.of("james.stated", Classification.CONFIDENTIAL))
        self.assertEqual("I-09", cm.exception.invariant)
        created = {r[0] for r in self.sql(
            "SELECT scope_path FROM scope WHERE parent_path = %s", (BUSINESS,))}
        self.assertIn("/business/alpha", created, "the approved scope is missing")
        self.assertNotIn("/business/beta", created,
                         "a scope the approval did not name was created")

    # =======================================================================
    # 11-14 -- nothing else moved
    # =======================================================================

    def test_11_f12_sibling_isolation_is_intact(self):
        """F-12: a parent conversation still carries one scope's content."""
        self.note(A, "a1", A_NOTE)
        self.note(B, "b1", B_NOTE)
        context, _ = self.block(BUSINESS)
        self.assertNotIn(A_NOTE, context)
        self.assertNotIn(B_NOTE, context)
        self.assertIn(A_NOTE, self.block(A)[0])
        self.assertNotIn(B_NOTE, self.block(A)[0])

    def test_12_containment_is_intact(self):
        """A token still covers its descendants, and a descendant row is still
        readable through the parent's channel."""
        parent_token = self.token(BUSINESS)
        self.assertTrue(parent_token.covers(A))
        self.assertFalse(self.token(A).covers(B))

        self.note(A, "a1", A_NOTE)
        with self.boundary.open(self.token(BUSINESS, frozenset({"read"}),
                                           Risk.READ)) as ch:
            rows = ch.fetch("SELECT scope_path FROM item WHERE item_ref='a1'")
        self.assertEqual([(A,)], rows)

    def test_13_f9_task_authority_revocation_is_intact(self):
        """F-9: a task-only authority is still revocable, and revocation still
        withholds the title from model context."""
        authority = self.task(BUSINESS, "t1", "MARKER-TASK-call-the-supplier")
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.revocations.revoke(self.token(BUSINESS), authority,
                                revoked_by="james")
        self.assertEqual([(BUSINESS,)], self.sql(
            "SELECT scope_path FROM authority_revocation"
            " WHERE execution_identity = %s", (authority,)))
        context, _ = self.block(BUSINESS)
        self.assertNotIn("MARKER-TASK-call-the-supplier", context)

    def test_14_f10_completion_is_still_scope_pinned(self):
        """F-10: one approval closes one task, in one scope."""
        self.task(BUSINESS, "invoice", "MARKER-PARENT-invoice")
        self.task(A, "invoice", "MARKER-CHILD-invoice")
        self.run_action(BUSINESS, COMPLETE_TASK, {"task_ref": "invoice"})
        self.assertEqual([(BUSINESS,)], self.sql(
            "SELECT scope_path FROM task WHERE done_at IS NOT NULL"))
        self.assertEqual([(A,)], self.sql(
            "SELECT scope_path FROM task WHERE done_at IS NULL"))


if __name__ == "__main__":
    unittest.main()
