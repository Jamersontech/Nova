"""F-13 / ADR 0051: a revoked creating authority is LABELLED, not withheld.

THE RULING (ADR 0051, on James's F-13 decision of 2026-08-25). `S7-D5` --
ADR 0033 §4 and `MEMORY_MODEL.md` §4 rule 8 -- says a row created under an
authority later revoked is **retained**, its revocation state **exposed at
retrieval**, and that "nothing is automatically deleted, downgraded,
invalidated, promoted, or reclassified... the CONSUMING AUTHORITY decides",
because "revocation happens for many reasons and only some impeach what was
learned".

THE DEFECT IT CLOSES. `_establish` withheld on `author in revoked`, in the SAME
branch as five conditions that mean the security state CANNOT BE ESTABLISHED.
That applied a rule for UNKNOWN state to KNOWN state -- a revoked authority is
established, and established as revoked -- and it made the withheld sentence
objectively FALSE for such a row, because its provenance, trust, classification
and creating authority had all been restored.

THE DISTINCTION IS THE POINT, and this suite asserts it from both sides:

    unestablishable   WITHHELD, with the fail-closed explanation, unchanged
    revoked           RETAINED, and explicitly marked
    both at once      reported SEPARATELY, never collapsed into one counter

WHAT LABELLING IS NOT. Not trust. Not classification. Not provenance --
revocation is a later fact ABOUT an authority, not an ORIGIN, and `I-38` makes
provenance immutable. The row is returned exactly as established plus one
further fact, and the model receives that fact as information: `I-101` and
`I-102` mean the model is never the consuming authority, so it decides nothing
by holding it.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_revoked_authority_labelling
"""

from __future__ import annotations

import dataclasses
import os
import tempfile
import unittest

from .. import db, tree_store
from ..approval_flow import ApprovalService
from ..boundary import DataAccessBoundary
from ..conversation import (CONVERSATION_MODEL, PROVIDER, ConversationService,
                            _REVOKED_MARK)
from ..revocation import RevocationRegistry
from ..seam import Seam
from ..write_path import (ADD_TASK, COMPLETE_TASK, PostgresItemIntegration,
                          TOOL, WritePath, add_task_tool, complete_task_tool,
                          write_item_tool)
from ...core.audit import AuditWriter
from ...core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ...core.budget import BudgetLedger
from ...core.context_service import ContextService
from ...core.gateway import ModelGateway, ModelResponse, ProviderBinding
from ...core.policy import PolicyDecisionPoint
from ...core.store import StoreRegistry
from ...core.types import Classification, Risk, Taint, Trust
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

BUSINESS = "/business"
A = "/business/client-a"
SCOPES = [(BUSINESS, "domain", None), (A, "client", BUSINESS)]
GRANTS = [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")]
CRED_REF = "control-plane/anthropic"

REVOKED_NOTE = "MARKER-REVOKED-NOTE-their-bank-details-changed"
REVOKED_TASK = "MARKER-REVOKED-TASK-call-the-supplier"
GOOD_NOTE = "MARKER-GOOD-NOTE-the-quarter-closes-friday"
GOOD_TASK = "MARKER-GOOD-TASK-review-the-pipeline"
LEGACY_NOTE = "MARKER-LEGACY-NOTE-no-security-state"
LEGACY_TASK = "MARKER-LEGACY-TASK-no-security-state"
WEB_NOTE = "MARKER-WEB-NOTE-from-a-web-page"

UNESTABLISHABLE = "cannot be established"


class ScriptedTransport:
    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        return ModelResponse(text="Noted.",
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
class RevokedAuthorityLabellingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-f13-")
        self.context = ContextService(self.tree, secret=b"f13-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        for scope in (BUSINESS, A):
            broker.register(
                CredentialBinding(
                    binding_id=f"db-item-write{scope}", scope_path=scope,
                    permitted_operations=frozenset({TOOL, ADD_TASK, COMPLETE_TASK})),
                secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        for factory in (write_item_tool, add_task_tool, complete_task_tool):
            registry.register(factory())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = ScopedWritePath(self.pdp, registry, pep, broker,
                                      self.integration, "unused-see-subclass")
        self.approvals = ApprovalService(self.boundary, self.writes)
        self.revocations = RevocationRegistry(self.boundary, self.context)

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
                         revocations=self.revocations)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

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

    def note(self, ref, body, scope=BUSINESS, taint=None):
        return self.run_action(scope, TOOL, {"item_ref": ref, "body": body}, taint)

    def task(self, ref, title, scope=BUSINESS, taint=None):
        return self.run_action(
            scope, ADD_TASK, {"task_ref": ref, "title": title, "due_on": ""}, taint)

    def block(self, scope=BUSINESS):
        return self.conversation._scope_context(
            self.token(scope, frozenset({"read"}), Risk.READ), scope)

    def seed_legacy(self):
        """Rows with NULL security state -- genuinely unestablishable, and the
        control this suite must never weaken."""
        self.sql("INSERT INTO item (item_ref, scope_path, body)"
                 " VALUES ('legacy-note',%s,%s)", (BUSINESS, LEGACY_NOTE))
        self.sql("INSERT INTO task (task_ref, scope_path, title)"
                 " VALUES ('legacy-task',%s,%s)", (BUSINESS, LEGACY_TASK))

    def line_for(self, context, marker):
        for line in context.splitlines():
            if marker in line:
                return line
        self.fail(f"{marker} does not appear in the block at all")

    # =======================================================================
    # 1-3 -- retained, and explicitly marked
    # =======================================================================

    def test_01_a_revoked_authoritys_item_remains_in_model_context(self):
        """THE DEFECT, directly, for `item`. `S7-D5` says the row is RETAINED
        and its revocation state exposed. It used to disappear."""
        authority = self.note("n1", REVOKED_NOTE)
        self.assertIn(REVOKED_NOTE, self.block()[0], "control: never arrived")

        self.revocations.revoke(self.token(), authority, revoked_by="james")

        context, _ = self.block()
        self.assertIn(REVOKED_NOTE, context,
                      "a revoked authority's item was withheld -- S7-D5 requires"
                      " it retained and labelled")

    def test_02_a_revoked_authoritys_task_remains_in_model_context(self):
        """The same for `task`. ADR 0049 made a title content, and it travels
        the same establishment path, so it must be labelled the same way."""
        authority = self.task("t1", REVOKED_TASK)
        self.revocations.revoke(self.token(), authority, revoked_by="james")

        context, _ = self.block()
        self.assertIn(REVOKED_TASK, context,
                      "a revoked authority's task title was withheld")

    def test_03_both_carry_an_explicit_per_row_revocation_marker(self):
        """Per row, deterministic, and on the row itself -- not a block-level
        aside that leaves the model guessing WHICH row is affected."""
        revoked_authority = self.note("n1", REVOKED_NOTE)
        self.task("t1", REVOKED_TASK)
        self.note("n2", GOOD_NOTE)
        self.task("t2", GOOD_TASK)
        # Revoke the two authorities that wrote the marked rows.
        for ref, table in (("n1", "item"), ("t1", "task")):
            author = self.sql(
                f"SELECT creating_authority FROM {table}"
                f" WHERE {'item_ref' if table == 'item' else 'task_ref'} = %s",
                (ref,))[0][0]
            self.revocations.revoke(self.token(), author, revoked_by="james")

        context, _ = self.block()
        self.assertIn(_REVOKED_MARK.strip(),
                      self.line_for(context, REVOKED_NOTE))
        self.assertIn(_REVOKED_MARK.strip(),
                      self.line_for(context, REVOKED_TASK))
        # ...and the untouched rows are NOT marked.
        self.assertNotIn(_REVOKED_MARK.strip(),
                         self.line_for(context, GOOD_NOTE))
        self.assertNotIn(_REVOKED_MARK.strip(),
                         self.line_for(context, GOOD_TASK))
        self.assertIsNotNone(revoked_authority)

    # =======================================================================
    # 4-6 -- the row's security state is NOT altered
    # =======================================================================

    def test_04_revocation_is_not_recorded_as_provenance(self):
        """Revocation is a later fact ABOUT an authority, not an ORIGIN.
        Putting it in provenance would make a set `I-38` calls immutable change
        after the fact. The stored row must be untouched, and the block's
        provenance union must gain no revocation term."""
        authority = self.note("n1", REVOKED_NOTE)
        before = self.sql("SELECT provenance, trust, classification FROM item"
                          " WHERE item_ref='n1'")
        self.revocations.revoke(self.token(), authority, revoked_by="james")

        self.assertEqual(before,
                         self.sql("SELECT provenance, trust, classification"
                                  " FROM item WHERE item_ref='n1'"),
                         "revoking rewrote the stored row")
        _, taint = self.block()
        for term in taint.provenance:
            self.assertNotIn("revok", term.lower(),
                             "revocation leaked into the provenance vocabulary")

    def test_05_revocation_does_not_change_trust(self):
        """`S7-D5` "deliberately does not re-weight"; rule 8 forbids
        downgrading. The block's taint must be identical before and after."""
        authority = self.note("n1", REVOKED_NOTE)
        _, before = self.block()
        self.revocations.revoke(self.token(), authority, revoked_by="james")
        _, after = self.block()

        self.assertEqual(before.trust, after.trust,
                         "revocation re-weighted the block's trust")
        self.assertEqual(before.provenance, after.provenance)

    def test_06_revocation_does_not_change_classification(self):
        """The other half of rule 8's "nothing... reclassified"."""
        authority = self.note("n1", REVOKED_NOTE,
                              taint=Taint.of("james.stated",
                                             Classification.CLIENT_CONFIDENTIAL))
        _, before = self.block()
        self.revocations.revoke(self.token(), authority, revoked_by="james")
        _, after = self.block()

        self.assertEqual(before.classification, after.classification)
        self.assertEqual(Classification.CLIENT_CONFIDENTIAL, after.classification)

    # =======================================================================
    # 7-9 -- REVOKED and UNESTABLISHABLE never collapse
    # =======================================================================

    def test_07_unestablishable_rows_are_still_withheld(self):
        """The control this ruling must not weaken. NULL security state is
        UNKNOWN, unknown is not recoverable by inference, and `I-110` forbids
        guessing it. Nothing about F-13 touches this."""
        self.seed_legacy()
        context, _ = self.block()

        self.assertNotIn(LEGACY_NOTE, context, "a legacy note reached the model")
        self.assertNotIn(LEGACY_TASK, context, "a legacy task reached the model")
        self.assertIn(UNESTABLISHABLE, context,
                      "the fail-closed explanation disappeared")

    def test_08_revoked_and_unestablishable_coexist_and_are_reported_apart(self):
        """The case that proves they are two facts and not one. A scope holding
        one of each must produce BOTH statements, each about the right rows."""
        authority = self.note("n1", REVOKED_NOTE)
        self.task("t1", REVOKED_TASK)
        task_author = self.sql("SELECT creating_authority FROM task"
                               " WHERE task_ref='t1'")[0][0]
        self.revocations.revoke(self.token(), authority, revoked_by="james")
        self.revocations.revoke(self.token(), task_author, revoked_by="james")
        self.seed_legacy()

        context, _ = self.block()

        # Revoked: present and marked.
        self.assertIn(_REVOKED_MARK.strip(), self.line_for(context, REVOKED_NOTE))
        self.assertIn(_REVOKED_MARK.strip(), self.line_for(context, REVOKED_TASK))
        # Unestablishable: absent, and explained.
        self.assertNotIn(LEGACY_NOTE, context)
        self.assertNotIn(LEGACY_TASK, context)
        self.assertIn(UNESTABLISHABLE, context)
        # And the counts do not borrow from each other: 1 note + 1 task each.
        self.assertIn("1 note(s) and 1 task(s) above are marked", context)
        self.assertIn("1 note(s) and 1 task(s) in this scope are withheld",
                      context)

    def test_09_a_revoked_authority_is_never_called_unestablishable(self):
        """The message was objectively FALSE for a revoked row: its provenance,
        trust, classification and creating authority were all established --
        the authority established AS REVOKED. With only revoked rows present,
        the fail-closed sentence must not appear at all."""
        authority = self.note("n1", REVOKED_NOTE)
        self.revocations.revoke(self.token(), authority, revoked_by="james")

        context, _ = self.block()
        self.assertNotIn(UNESTABLISHABLE, context,
                         "NOVA said a revoked authority could not be"
                         " established -- it can, and it was")
        self.assertIn("was later revoked", context,
                      "the block does not say what the marker means")

    def test_10_the_read_audit_records_the_two_states_separately(self):
        """`W-1`/`I-49`: the record must not say the opposite of what happened.
        A retained row counted as `withheld` would do exactly that."""
        authority = self.note("n1", REVOKED_NOTE)
        self.revocations.revoke(self.token(), authority, revoked_by="james")
        self.seed_legacy()
        self.block()

        detail = self.sql("SELECT detail FROM audit_record"
                          " WHERE category='data.read'"
                          " AND detail LIKE 'conversation context%'")[-1][0]
        self.assertIn("revoked_authority=1", detail)
        self.assertIn("withheld=2", detail)
        self.assertIn("items=1", detail, "the retained row was not counted as"
                                         " an item")

    # =======================================================================
    # 11-15 -- every other control is untouched
    # =======================================================================

    def test_11_i40_still_fires_on_external_content(self):
        """A retained row contributes its taint to the `I-99` union exactly as
        before -- so `I-40`'s source-naming gate still sees external content,
        and in fact sees it where the old drop suppressed it."""
        authority = self.note("n1", WEB_NOTE,
                              taint=Taint.of("external.web",
                                             Classification.CONFIDENTIAL))
        self.revocations.revoke(self.token(), authority, revoked_by="james")

        _, taint = self.block()
        self.assertTrue(taint.is_untrusted_derived(),
                        "a revoked external-web row stopped tripping I-40")
        self.assertIn("external.web", taint.external_sources())

    def test_12_i100_untrusted_derived_labelling_survives_the_round_trip(self):
        """`I-111`'s stated purpose: `I-100`'s untrusted-derived ceiling is
        evaluated against the RESTORED labelling. Retaining the row is what
        lets that labelling reach it."""
        authority = self.note("n1", WEB_NOTE,
                              taint=Taint.of("external.web",
                                             Classification.CONFIDENTIAL))
        self.revocations.revoke(self.token(), authority, revoked_by="james")
        _, taint = self.block()
        # The row's own persisted origin came back, unchanged and un-elevated.
        self.assertIn("external.web", taint.provenance)
        self.assertEqual(
            [(["external.web", "james.approved"], int(Trust.HIGHEST))],
            self.sql("SELECT provenance, trust FROM item WHERE item_ref='n1'"),
            "the stored row was altered by revocation")

    def test_13_f9_revocation_still_records_at_the_authoritys_own_scope(self):
        """F-9 intact: the WRITE half is untouched by this ruling. A task-only
        authority is still revocable and still files at its own scope."""
        authority = self.task("t1", REVOKED_TASK, scope=A)
        self.assertEqual([], self.sql("SELECT 1 FROM item"))
        self.revocations.revoke(self.token(), authority, revoked_by="james")
        self.assertEqual([(A,)], self.sql(
            "SELECT scope_path FROM authority_revocation"
            " WHERE execution_identity = %s", (authority,)))
        # ...and the label reaches the reader bound at that scope.
        self.assertIn(_REVOKED_MARK.strip(),
                      self.line_for(self.block(A)[0], REVOKED_TASK))

    def test_14_f10_and_f12_are_intact(self):
        """F-10: one approval closes one task, in one scope. F-12: a parent
        conversation carries one scope's content."""
        self.task("invoice", GOOD_TASK)
        self.task("invoice", REVOKED_TASK, scope=A)
        self.run_action(BUSINESS, COMPLETE_TASK, {"task_ref": "invoice"})

        self.assertEqual([(BUSINESS,)], self.sql(
            "SELECT scope_path FROM task WHERE done_at IS NOT NULL"))
        self.assertNotIn(REVOKED_TASK, self.block(BUSINESS)[0],
                         "F-12 sibling/descendant isolation regressed")

    def test_15_f11_base_attribution_is_intact(self):
        """F-11 / ADR 0050: the block's base is still the union with
        UNKNOWN_ORIGIN at LOW, and labelling did not disturb it."""
        _, taint = self.block()
        self.assertEqual(frozenset({"james.stated", "model.generated"}),
                         taint.provenance)
        self.assertEqual(Trust.LOW, taint.trust)

    def test_16_human_visibility_is_unchanged(self):
        """No human surface was added or removed by this ruling. James saw the
        row before revocation and still sees it -- unlabelled, because ADR 0051
        is confined to retrieval and model context."""
        authority = self.note("n1", REVOKED_NOTE)
        self.revocations.revoke(self.token(), authority, revoked_by="james")

        status, page = self.seam.scope_page(self.sid, BUSINESS)
        self.assertEqual(200, status)
        self.assertIn(REVOKED_NOTE, page,
                      "revocation removed the row from James's own surface")


if __name__ == "__main__":
    unittest.main()
