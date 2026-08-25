"""ADR 0049 / F-2 -- a task title is CONTENT, against real PostgreSQL.

THE DECISION. `task.title` is expressive content and carries the same
provenance/trust/classification guarantee as `write_item` content. It falls
under `I-111`: the state is persisted with the title, restored at retrieval,
and where it cannot be established the title is withheld FROM MODEL CONTEXT.

THE DEFECT IT CLOSES, measured before this existed. A title can carry a factual
claim in imperative grammar -- "call the supplier, their bank details changed to
X". With no provenance column, an attacker-controlled fact written as a task
survived deletion of its source and came back to the model as
`james.stated`/HIGHEST with its origin erased. Identical text was labelled
honestly as a note and laundered as a task, and whatever produced it got to
choose which.

THREE PROPERTIES, KEPT APART. This suite asserts all three separately because
collapsing them is the likeliest way to get this wrong:

    human visibility   James sees the whole task, always -- attention and the
                       scope page are unchanged, withheld or not
    model visibility   constrained: established state, or withheld
    authorization      unchanged: COMPLETE_TASK stays actionable on a task the
                       model cannot see

ROW-LEVEL PROVENANCE, no history table. The upsert keeps one row and destroys
the previous title, so it must destroy that title's taint in the same statement.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_task_content_provenance
"""

from __future__ import annotations

import datetime
import os
import tempfile
import unittest

from .. import db, tree_store
from ..approval_flow import ApprovalService
from ..attention import AttentionService
from ..boundary import DataAccessBoundary
from ..conversation import (CONVERSATION_MODEL, PROVIDER, ConversationService)
from ..seam import Seam
from ..write_path import (APPROVED_PROVENANCE, ADD_SCOPE, ADD_TASK,
                          COMPLETE_TASK, PostgresItemIntegration, TOOL,
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

LIFE = "/life"
SCOPES = [(LIFE, "domain", None)]
GRANTS = [("james", LIFE, r) for r in ("read", "write")]
CRED_REF = "control-plane/anthropic"

TITLE = "MARKER-TITLE-chase-the-invoice"
WEB = "MARKER-WEB-their-bank-details-changed"
NEW_TITLE = "MARKER-TITLE-REPLACED-book-the-dentist"


class ScriptedTransport:
    def __init__(self):
        self.replies: list[str] = []
        self.prompts: list[str] = []

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        text = self.replies.pop(0) if self.replies else "Nothing is pending here."
        return ModelResponse(
            text=text, taint=Taint.of("model.generated", Classification.INTERNAL))


@unittest.skipUnless(db.available(),
                     "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class TaskContentProvenanceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-adr0049-")
        self.context = ContextService(self.tree, secret=b"adr-0049-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        broker.register(
            CredentialBinding(
                binding_id="db-item-write", scope_path=LIFE,
                permitted_operations=frozenset({TOOL, ADD_TASK, COMPLETE_TASK,
                                                ADD_SCOPE})),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        for factory in (write_item_tool, add_task_tool, complete_task_tool,
                        add_scope_tool):
            registry.register(factory())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")
        self.approvals = ApprovalService(self.boundary, self.writes)
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
                         attention=self.attention)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=LIFE, rights=rights,
                                       ceiling=ceiling, ttl=60)

    def read_token(self):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=LIFE,
                                       rights=frozenset({"read"}),
                                       ceiling=Risk.READ, ttl=60)

    def sql(self, query, args=()):
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(query, args or None)
            rows = cur.fetchall() if cur.description else []
        conn.close()
        return rows

    def a_model_taint(self, provenance="james.stated",
                      classification=Classification.INTERNAL):
        """What a proposal drawn from scope content carries: the block's own
        taint, derived through the model's `model.generated` provenance."""
        return Taint.of(provenance, classification).derive("model.generated")

    def add_task(self, ref="t1", title=TITLE, due="", taint=None):
        token = self.token()
        approval_id = self.approvals.propose_action(
            token, LIFE, ADD_TASK,
            {"task_ref": ref, "title": title, "due_on": due},
            action_text=f"Add task “{title}”.", if_wrong_text="x",
            taint=taint)
        self.approvals.decide(token, approval_id, True, decided_by="james")
        return approval_id

    def task_state(self, ref="t1"):
        return self.sql("SELECT title, provenance, trust, classification,"
                        " delegation_ancestry, creating_authority"
                        " FROM task WHERE task_ref=%s", (ref,))[0]

    def model_context(self):
        return self.conversation._scope_context(self.read_token(), LIFE)

    def seed_legacy_task(self, ref="legacy", title=TITLE):
        """A row as it existed before ADR 0049: no security state at all."""
        self.sql("INSERT INTO task (task_ref, scope_path, title) VALUES (%s,%s,%s)",
                 (ref, LIFE, title))

    # =======================================================================
    # PERSISTENCE -- the state is written with the title
    # =======================================================================

    def test_01_an_approved_task_persists_its_security_state(self):
        """The control. If this fails everything below is testing nothing."""
        self.add_task(taint=self.a_model_taint())
        title, provenance, trust, classification, ancestry, authority = self.task_state()
        self.assertEqual(TITLE, title)
        self.assertIn("model.generated", provenance)
        self.assertIn(APPROVED_PROVENANCE, provenance)
        self.assertEqual(int(Trust.HIGHEST), trust)
        self.assertEqual(int(Classification.INTERNAL), classification)
        self.assertEqual([], ancestry)
        self.assertTrue(authority)

    def test_02_the_state_is_server_derived_not_payload_supplied(self):
        """The same guarantee items have: a forged security field in the tool
        arguments changes the plan identity, so I-112 refuses before the write
        path is reached at all."""
        token = self.token()
        forged = {"task_ref": "t1", "title": TITLE, "due_on": "",
                  "provenance": ["system.verified"], "trust": int(Trust.HIGHEST)}
        approval_id = self.approvals.propose_action(
            token, LIFE, ADD_TASK, forged, action_text="x", if_wrong_text="x",
            taint=self.a_model_taint())
        self.sql("UPDATE approval SET arguments=%s WHERE approval_id=%s",
                 ('{"task_ref": "t1", "title": "%s", "due_on": ""}' % TITLE,
                  approval_id))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM task WHERE task_ref='t1'"))

    def test_03_classification_is_inherited_never_elevated(self):
        """Approval is evidence about trustworthiness, not sensitivity."""
        self.add_task(taint=self.a_model_taint(
            classification=Classification.SENSITIVE_PERSONAL))
        _t, _p, trust, classification, _a, _au = self.task_state()
        self.assertEqual(int(Trust.HIGHEST), trust, "the control failed")
        self.assertEqual(int(Classification.SENSITIVE_PERSONAL), classification)

    # =======================================================================
    # RETRIEVAL -- restored, or withheld
    # =======================================================================

    def test_04_the_stored_provenance_is_restored_into_model_context(self):
        """I-111's read half, for a task. The block's taint carries what the
        title actually derived from -- it is not re-synthesized here."""
        self.add_task(taint=self.a_model_taint(provenance="external.web"))
        text, taint = self.model_context()
        self.assertIn(TITLE, text)
        self.assertIn("external.web", taint.provenance,
                      "the title's origin did not survive into model context")

    def test_05_untrusted_task_content_drags_the_block_down(self):
        """I-99: the block is a derivation of its inputs, tasks included."""
        low = Taint(frozenset({"external.web"}), Trust.LOW, Classification.INTERNAL)
        self.sql("INSERT INTO task (task_ref, scope_path, title, provenance,"
                 " trust, classification, delegation_ancestry, creating_authority)"
                 " VALUES ('t-low',%s,%s,'{external.web}',%s,%s,'{}','tr-x')",
                 (LIFE, TITLE, int(low.trust), int(low.classification)))
        _text, taint = self.model_context()
        self.assertEqual(Trust.LOW, taint.trust,
                         "a LOW-trust task title did not lower the block")

    def test_06_a_legacy_task_row_is_withheld_from_the_model(self):
        """NULL security state is UNKNOWN, and unknown is never trusted. Not
        backfilled, not assumed `james.stated`."""
        self.seed_legacy_task()
        text, taint = self.model_context()
        self.assertNotIn(TITLE, text, "a legacy task reached the model")
        self.assertIn("withheld", text, "the withholding was not reported")
        # The property is that WITHHOLDING removes the row rather than dragging
        # the block's taint down -- so the block reads exactly the base and no
        # lower. ADR 0050 (F-11) lowered that base from `james.stated`/HIGHEST
        # to the union with `UNKNOWN_ORIGIN` at LOW; the withheld row still
        # contributes nothing, which is what this asserts.
        self.assertEqual(Trust.LOW, taint.trust,
                         "withholding should remove the row, not taint the block")
        self.assertEqual(frozenset({"james.stated", "model.generated"}),
                         taint.provenance,
                         "the withheld row's provenance leaked into the block")

    def test_07_a_legacy_task_is_not_backfilled_by_being_read(self):
        """Reading must not repair a row it refused to trust."""
        self.seed_legacy_task()
        self.model_context()
        self.assertEqual([(None, None, None, None, None)],
                         self.sql("SELECT provenance, trust, classification,"
                                  " delegation_ancestry, creating_authority"
                                  " FROM task WHERE task_ref='legacy'"))

    def test_08_a_delegate_written_task_is_withheld(self):
        """Non-empty ancestry withholds, exactly as it does for an item: an
        ancestor's revocation state is not establishable from this scope."""
        self.sql("INSERT INTO task (task_ref, scope_path, title, provenance,"
                 " trust, classification, delegation_ancestry, creating_authority)"
                 " VALUES ('t-del',%s,%s,'{james.stated}',%s,%s,'{tr-ancestor}','tr-child')",
                 (LIFE, TITLE, int(Trust.HIGHEST), int(Classification.INTERNAL)))
        text, _taint = self.model_context()
        self.assertNotIn(TITLE, text)

    # =======================================================================
    # MUTATION -- title and provenance move together
    # =======================================================================

    def test_09_replacing_a_title_replaces_its_provenance_atomically(self):
        """Row-level provenance is only sound if the upsert destroys the old
        taint with the old title. An inherited taint would be a laundering path
        of its own: write something trusted, then replace the text."""
        self.add_task(title=TITLE, taint=self.a_model_taint())
        first = self.task_state()
        self.assertEqual(int(Trust.HIGHEST), first[2], "the control failed")

        self.add_task(title=NEW_TITLE, taint=None)   # no evidence this time
        title, provenance, trust, _c, _a, _au = self.task_state()
        self.assertEqual(NEW_TITLE, title)
        self.assertEqual(int(Trust.LOW), trust,
                         "a replacement title inherited its predecessor's trust")
        self.assertNotIn(APPROVED_PROVENANCE, provenance,
                         "a replacement title inherited an approval it never had")
        self.assertEqual(1, self.sql("SELECT count(*) FROM task"
                                     " WHERE task_ref='t1'")[0][0],
                         "a history row appeared -- ADR 0049 introduces none")

    def test_10_a_changed_title_is_a_new_plan_and_needs_fresh_approval(self):
        """I-112, unchanged: the identity hashes every argument, so editing the
        stored title after approval no longer matches what James saw."""
        token = self.token()
        approval_id = self.approvals.propose_action(
            token, LIFE, ADD_TASK, {"task_ref": "t1", "title": TITLE, "due_on": ""},
            action_text="x", if_wrong_text="x", taint=self.a_model_taint())
        self.sql("UPDATE approval SET arguments=%s WHERE approval_id=%s",
                 ('{"task_ref": "t1", "title": "%s", "due_on": ""}' % NEW_TITLE,
                  approval_id))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM task WHERE task_ref='t1'"))

    def test_11_deleting_the_source_does_not_make_the_title_trusted(self):
        """F-2's measured defect, re-run. The origin is carried by the row, so
        it survives the disappearance of what it came from."""
        self.sql("INSERT INTO item (item_ref, scope_path, body, provenance,"
                 " trust, classification, delegation_ancestry, creating_authority)"
                 " VALUES ('web',%s,%s,'{external.web}',%s,%s,'{}','tr-web')",
                 (LIFE, WEB, int(Trust.LOW), int(Classification.INTERNAL)))
        _t, before = self.model_context()
        self.assertEqual(Trust.LOW, before.trust, "the control failed")

        self.add_task(title=WEB, taint=before.derive("model.generated"))
        self.sql("DELETE FROM item WHERE item_ref='web'")

        text, after = self.model_context()
        self.assertIn(WEB, text, "the task itself should still be present")
        self.assertIn("external.web", after.provenance,
                      "the title shed its origin when the source was deleted")
        self.assertTrue(after.is_untrusted_derived(),
                        "I-40 lost its grip on externally-derived task content")

    # =======================================================================
    # THE THREE PROPERTIES, KEPT APART
    # =======================================================================

    def test_12_a_withheld_task_is_still_shown_to_james_on_the_scope_page(self):
        """HUMAN VISIBILITY. Fail-closed applies to model context, not to
        James's eyes -- the same rule items already follow."""
        self.seed_legacy_task()
        status, page = self.seam.scope_page(self.sid, LIFE)
        self.assertEqual(200, status)
        self.assertIn(TITLE, page, "a withheld task vanished from James's page")

    def test_13_a_withheld_task_still_appears_on_attention(self):
        """HUMAN VISIBILITY, on the surface whose whole purpose is surfacing.
        Attention never touches the gateway (I-95), so withholding has no
        business changing it."""
        due = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        self.sql("INSERT INTO task (task_ref, scope_path, title, due_on)"
                 " VALUES ('legacy',%s,%s,%s)", (LIFE, TITLE, due))
        result = self.attention.gather("james", "james")
        titles = [t.title for t in result.overdue]
        self.assertIn(TITLE, titles,
                      "a withheld task disappeared from the attention surface")

    def test_14_complete_task_still_works_on_a_withheld_task(self):
        """AUTHORIZATION. Withholding a title from the model must never become
        a covert authorization change -- COMPLETE_TASK acts on the ref."""
        self.seed_legacy_task(ref="t1")
        token = self.token()
        approval_id = self.approvals.propose_action(
            token, LIFE, COMPLETE_TASK, {"task_ref": "t1"},
            action_text="Mark it done.", if_wrong_text="x",
            taint=self.a_model_taint())
        self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual([(True,)],
                         self.sql("SELECT done_at IS NOT NULL FROM task"
                                  " WHERE task_ref='t1'"),
                         "a withheld task could not be completed")

    def test_15_completing_a_task_needs_no_new_provenance_write(self):
        """COMPLETE_TASK writes no content, so it neither sets nor disturbs the
        security state of the title it closes."""
        self.add_task(taint=self.a_model_taint())
        before = self.task_state()
        token = self.token()
        approval_id = self.approvals.propose_action(
            token, LIFE, COMPLETE_TASK, {"task_ref": "t1"},
            action_text="x", if_wrong_text="x", taint=self.a_model_taint())
        self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual(before, self.task_state(),
                         "completing a task altered its content provenance")

    # =======================================================================
    # NO SECOND TRUST MODEL
    # =======================================================================

    def test_16_a_task_without_evidence_does_not_reach_highest(self):
        """The same rule items follow: no elevation without ADR 0048's
        content-visible evidence. An approval row is not evidence."""
        self.add_task(taint=self.a_model_taint())     # evidence present
        self.assertEqual(int(Trust.HIGHEST), self.task_state()[2])
        self.add_task(ref="t2", taint=None)           # evidence absent
        title, provenance, trust, _c, _a, _au = self.task_state("t2")
        self.assertEqual(int(Trust.LOW), trust)
        self.assertNotIn(APPROVED_PROVENANCE, provenance)

    def test_17_items_are_unaffected_by_this_change(self):
        """I-111's existing item behaviour is untouched."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", "note body",
                                             taint=self.a_model_taint())
        self.approvals.decide(token, approval_id, True, decided_by="james")
        row = self.sql("SELECT provenance, trust, classification,"
                       " delegation_ancestry FROM item WHERE item_ref='it-1'")[0]
        self.assertIn(APPROVED_PROVENANCE, row[0])
        self.assertIn("model.generated", row[0])
        self.assertEqual(int(Trust.HIGHEST), row[1])
        self.assertEqual([], row[3])


if __name__ == "__main__":
    unittest.main()
