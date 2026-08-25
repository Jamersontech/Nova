"""ADR 0048 -- content-visible approval, against real PostgreSQL.

THE ACCEPTED RULE. An approved write may receive elevated provenance/trust
ONLY when the exact bytes to be persisted were identifiable before approval,
James could inspect them before approval, the approval is bound to those bytes
and the plan identity, the elevation is attributable to that approval evidence,
and any post-approval change invalidates the approval.

NON-ELEVATION IS THE DEFAULT. Where any requirement is missing the write still
happens -- at the derived taint. It is not refused. Several tests below exist
specifically to hold that line, because the tempting bug is to turn a missing
requirement into a denial and quietly break working writes.

WHAT THIS SUITE IS FOR. The defect ADR 0048 closed was measured, not theorised:
low-trust content was echoed into a proposed note, approved without the body
ever being displayed, persisted at HIGHEST, and survived deletion of its
source -- returning to model context as high-trust content nobody stated. Every
test here is a face of that, or of the mechanism that now prevents it.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_content_visible_approval
"""

from __future__ import annotations

import os
import tempfile
import unittest

from .. import db, tree_store
from ..approval_flow import ApprovalService
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
from ...core.types import (Classification, Denied, Risk, Taint, Trust)
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

LIFE = "/life"
SCOPES = [(LIFE, "domain", None)]
GRANTS = [("james", LIFE, r) for r in ("read", "write")]
CRED_REF = "control-plane/anthropic"

# Chosen so a partial or fuzzy leak still fails: neither is a substring of the
# other and neither occurs in NOVA's own prompt or page text.
BODY = "MARKER-BODY-the-dentist-is-on-thursday"
WEB = "MARKER-WEB-something-off-the-internet"


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
class ContentVisibleApprovalTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-adr0048-")
        self.context = ContextService(self.tree, secret=b"adr-0048-suite-key")
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
                         tree=self.tree, conversation=self.conversation)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=LIFE, rights=rights,
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

    def state(self, ref="it-1"):
        """The persisted I-111 security state of one item."""
        return self.sql("SELECT provenance, trust, classification,"
                        " delegation_ancestry, creating_authority"
                        " FROM item WHERE item_ref=%s", (ref,))[0]

    def approve_write(self, ref="it-1", body=BODY, taint=None):
        """The production route end to end, with a recorded origin."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, ref, body, taint=taint)
        self.approvals.decide(token, approval_id, True, decided_by="james")
        return approval_id

    def a_model_taint(self, classification=Classification.INTERNAL):
        """What a proposal drawn from ordinary scope content carries."""
        return Taint.of("james.stated", classification).derive("model.generated")

    # =======================================================================
    # POSITIVE -- elevation happens, and only where it is earned
    # =======================================================================

    def test_01_content_visible_approval_elevates(self):
        """Invariant 1. The whole decision, in one assertion."""
        self.approve_write(taint=self.a_model_taint())
        provenance, trust, _cls, _anc, _auth = self.state()
        self.assertIn(APPROVED_PROVENANCE, provenance)
        self.assertEqual(int(Trust.HIGHEST), trust)

    def test_02_elevation_is_additive_and_never_rewrites_origin(self):
        """I-38/I-110: a promotion RECORDS a judgement, it does not erase how
        the content came to exist. An approved item stays distinguishable from
        something James typed."""
        self.approve_write(taint=self.a_model_taint())
        provenance, _t, _c, _a, _au = self.state()
        self.assertIn("model.generated", provenance,
                      "elevation erased the fact that a model wrote this")
        self.assertIn("james.stated", provenance,
                      "elevation dropped a contributing source")

    def test_03_elevation_touches_exactly_one_item(self):
        """A second, unapproved row in the same scope is unaffected."""
        self.sql("INSERT INTO item (item_ref, scope_path, body, provenance,"
                 " trust, classification, delegation_ancestry, creating_authority)"
                 " VALUES ('other',%s,'other body','{external.web}',%s,%s,'{}','tr-x')",
                 (LIFE, int(Trust.LOW), int(Classification.INTERNAL)))
        self.approve_write(taint=self.a_model_taint())
        other = self.state("other")
        self.assertEqual(["external.web"], other[0])
        self.assertEqual(int(Trust.LOW), other[1])

    def test_04_classification_is_inherited_never_elevated(self):
        """Invariant 9. Approval is evidence about TRUSTWORTHINESS, not about
        sensitivity. I-27's strictest-wins result carries through untouched."""
        self.approve_write(
            taint=self.a_model_taint(Classification.SENSITIVE_PERSONAL))
        _p, trust, classification, _a, _au = self.state()
        self.assertEqual(int(Trust.HIGHEST), trust, "the control failed")
        self.assertEqual(int(Classification.SENSITIVE_PERSONAL), classification,
                         "approval raised the classification")

    def test_05_delegation_ancestry_is_unchanged_by_elevation(self):
        """Invariant 10. Elevation is about trust; lineage is not its business."""
        self.approve_write(taint=self.a_model_taint())
        _p, _t, _c, ancestry, authority = self.state()
        self.assertEqual([], ancestry, "a root execution grew an ancestry")
        self.assertTrue(authority, "creating authority was lost")

    def test_06_the_elevated_item_survives_persistence_and_reaches_the_model(self):
        """The round trip. `_establish` restores what was written, and the
        restored taint reaches the model request rather than being
        re-synthesized on the way out."""
        self.approve_write(taint=self.a_model_taint())
        read = self.context.issue_root(identity="james", actor="james",
                                       scope_path=LIFE,
                                       rights=frozenset({"read"}),
                                       ceiling=Risk.READ, ttl=60)
        text, taint = self.conversation._scope_context(read, LIFE)
        self.assertIn(BODY, text)
        self.assertIn(APPROVED_PROVENANCE, taint.provenance)
        # The ROW's elevation is what this test is about, and it survives: the
        # restored `james.approved` reaches the block above. The BLOCK's trust
        # is now LOW because ADR 0050 (F-11) lowered the base -- `I-99` union
        # takes the lowest contributor, and a lower block trust can only
        # tighten downstream gates, never loosen one. The row itself is still
        # HIGHEST; test_04 asserts that directly.
        self.assertEqual(Trust.LOW, taint.trust)
        self.assertEqual(
            [(int(Trust.HIGHEST),)],
            self.sql("SELECT trust FROM item WHERE item_ref='it-1'"),
            "the elevated ROW lost its trust")

    def test_07_the_elevation_is_audited(self):
        """I-110 requires a promotion to RECORD or not happen. Same table, same
        transaction as the write -- no second audit system."""
        approval_id = self.approve_write(taint=self.a_model_taint())
        rows = self.sql("SELECT detail FROM audit_record"
                        " WHERE category='trust.elevation'")
        self.assertEqual(1, len(rows), "no elevation audit record")
        detail = rows[0][0]
        for expected in (approval_id, "approved_by=james", "james.stated",
                         "HIGHEST", "inspected="):
            self.assertIn(expected, detail, f"audit omits {expected!r}")

    # =======================================================================
    # F-8 -- the elevation audit describes a row, or it does not exist
    # =======================================================================

    def elevation_audits(self, tool=None):
        rows = self.sql("SELECT detail FROM audit_record"
                        " WHERE category='trust.elevation' ORDER BY id")
        return [d for (d,) in rows if tool is None or d.startswith(tool)]

    def approve_action(self, tool, arguments, taint=None):
        """One approved action of any tool, through the production route."""
        token = self.token()
        approval_id = self.approvals.propose_action(
            token, LIFE, tool, arguments,
            action_text=f"{tool} in this scope.", if_wrong_text="x", taint=taint)
        self.approvals.decide(token, approval_id, True, decided_by="james")
        return approval_id

    def test_07b_add_task_audits_its_elevation_because_it_now_persists_one(self):
        """F-8's invariant, under ADR 0049.

        F-8's rule is unchanged and is the only rule here: AN ELEVATION AUDIT
        EXISTS IF AND ONLY IF A ROW CARRIES THE ELEVATED TAINT. What changed is
        which rows can. Before ADR 0049 a task had no trust column, so the
        elevation was computed and discarded and the audit asserted a promotion
        that reached nothing -- that was the F-8 defect. Now the task row
        stores it, so the record is accurate and I-110's "records or does not
        happen" requires it.

        The assertion is deliberately paired: the audit must exist AND the row
        must actually carry HIGHEST. Either alone would let the spurious case
        back in."""
        self.approve_action(ADD_TASK,
                            {"task_ref": "t1", "title": BODY, "due_on": ""},
                            taint=self.a_model_taint())
        row = self.sql("SELECT title, trust, provenance FROM task"
                       " WHERE task_ref='t1'")[0]
        self.assertEqual(BODY, row[0], "the control failed: the task was not written")
        self.assertEqual(int(Trust.HIGHEST), row[1],
                         "no elevation was persisted, so the audit below would lie")
        self.assertIn(APPROVED_PROVENANCE, row[2])
        audits = self.elevation_audits()
        self.assertEqual(1, len(audits), "the persisted elevation was not recorded")
        self.assertTrue(audits[0].startswith(ADD_TASK))

    def test_07b2_a_task_write_that_did_not_elevate_writes_no_audit(self):
        """The F-8 defect's exact shape, held closed from the other side: an
        elevation that did not happen is never recorded."""
        self.approve_action(ADD_TASK,
                            {"task_ref": "t1", "title": BODY, "due_on": ""},
                            taint=None)
        self.assertEqual([(BODY,)],
                         self.sql("SELECT title FROM task WHERE task_ref='t1'"),
                         "the control failed: the task was not written")
        self.assertEqual([], self.elevation_audits(),
                         "a task write with no evidence claimed an elevation")

    def test_07c_complete_task_writes_no_elevation_audit(self):
        """No EXPRESSIVE content, so nothing to inspect, nothing to elevate and
        nothing to record -- regardless of what the task it closes carried."""
        self.approve_action(ADD_TASK,
                            {"task_ref": "t1", "title": BODY, "due_on": ""},
                            taint=self.a_model_taint())
        self.approve_action(COMPLETE_TASK, {"task_ref": "t1"},
                            taint=self.a_model_taint())
        self.assertEqual([], self.elevation_audits(COMPLETE_TASK),
                         "complete_task claimed an elevation it cannot carry")

    def test_07d_add_scope_writes_no_elevation_audit(self):
        """Both its arguments are CONSEQUENCE-determining -- there is no prose
        to inspect, so no elevation and no record of one."""
        self.approve_action(ADD_SCOPE, {"scope_name": "gym", "kind": "place"},
                            taint=self.a_model_taint())
        self.assertEqual([("/life/gym",)],
                         self.sql("SELECT scope_path FROM scope"
                                  " WHERE scope_path='/life/gym'"),
                         "the control failed: the scope was not created")
        self.assertEqual([], self.elevation_audits())

    def test_07e_a_write_that_did_not_elevate_writes_no_audit(self):
        """`persisted == plan.taint` means nothing was promoted, so there is
        nothing to record. Covers the non-content-visible case."""
        self.approve_write(taint=None)
        _p, trust, _c, _a, _au = self.state()
        self.assertEqual(int(Trust.LOW), trust, "the control failed: it elevated")
        self.assertEqual([], self.elevation_audits())

    def test_07f_a_legacy_approval_writes_no_elevation_audit(self):
        """`proposed_taint = NULL` is unknown, so no elevation and no audit."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", BODY,
                                             taint=self.a_model_taint())
        self.sql("UPDATE approval SET proposed_taint=NULL WHERE approval_id=%s",
                 (approval_id,))
        self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual([], self.elevation_audits())

    def test_07g_exactly_one_audit_per_elevated_write(self):
        """One row, one elevation, one record -- not zero, and not two."""
        self.approve_write(ref="a", taint=self.a_model_taint())
        self.approve_write(ref="b", taint=self.a_model_taint())
        audits = self.elevation_audits()
        self.assertEqual(2, len(audits))
        self.assertTrue(all(d.startswith(TOOL) for d in audits),
                        f"a tool that stores no taint emitted an audit: {audits}")

    def test_07h_only_taint_storing_tools_can_ever_audit(self):
        """The structural half of F-8, restated for ADR 0049. `write_item` and
        `add_task` store a taint and may record one; `complete_task` and
        `add_scope` store none and must never appear in this trail, whatever
        else happens in the scope."""
        self.approve_write(taint=self.a_model_taint())
        self.approve_action(ADD_TASK, {"task_ref": "t1", "title": BODY, "due_on": ""},
                            taint=self.a_model_taint())
        self.approve_action(COMPLETE_TASK, {"task_ref": "t1"},
                            taint=self.a_model_taint())
        self.approve_action(ADD_SCOPE, {"scope_name": "gym", "kind": "place"},
                            taint=self.a_model_taint())
        self.assertEqual([], self.elevation_audits(COMPLETE_TASK))
        self.assertEqual([], self.elevation_audits(ADD_SCOPE))
        self.assertEqual(2, len(self.elevation_audits()),
                         "exactly the two taint-storing writes should be recorded")

    # =======================================================================
    # NEGATIVE -- the default, and the ways elevation must not happen
    # =======================================================================

    def test_08_approval_without_recorded_evidence_does_not_elevate(self):
        """Invariant 2, and the single most important test here.

        The approval is real, James decided it, the write happens -- and the
        row is NOT trusted, because nothing recorded what the content was
        derived from. This is the legacy shape and the fail-open that ADR 0048
        exists to forbid."""
        self.approve_write(taint=None)
        provenance, trust, _c, _a, _au = self.state()
        self.assertNotIn(APPROVED_PROVENANCE, provenance,
                         "an approval with no evidence elevated anyway")
        self.assertEqual(int(Trust.LOW), trust)

    def test_09_a_write_without_evidence_still_happens(self):
        """Non-elevation is the DEFAULT, not a refusal. The tempting bug is to
        deny here, which would break every legacy approval."""
        self.approve_write(taint=None)
        self.assertEqual([(BODY,)],
                         self.sql("SELECT body FROM item WHERE item_ref='it-1'"),
                         "a write was refused merely for lacking evidence")

    def test_10_legacy_null_proposed_taint_never_elevates(self):
        """Invariant 6, at the storage layer: a row written before ADR 0048 has
        no `proposed_taint`, and NULL is UNKNOWN -- never a licence."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", BODY,
                                             taint=self.a_model_taint())
        # Erase the evidence exactly as a pre-ADR-0048 row would lack it.
        self.sql("UPDATE approval SET proposed_taint=NULL WHERE approval_id=%s",
                 (approval_id,))
        self.approvals.decide(token, approval_id, True, decided_by="james")
        provenance, trust, _c, _a, _au = self.state()
        self.assertNotIn(APPROVED_PROVENANCE, provenance)
        self.assertEqual(int(Trust.LOW), trust)

    def test_11_changing_the_body_after_approval_is_refused(self):
        """Invariant 3 / ADR 0048 property 5. I-112's reconstruct-and-compare
        already delivers this; the test proves it still does."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", BODY,
                                             taint=self.a_model_taint())
        self.sql("UPDATE approval SET body=%s WHERE approval_id=%s",
                 ("SOMETHING ELSE ENTIRELY", approval_id))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item WHERE item_ref='it-1'"),
                         "a substituted body was written anyway")

    def test_12_changing_a_consequence_argument_is_refused(self):
        """Invariant 4. The identifier is CONSEQUENCE-determining, so it is in
        the plan identity as surely as the prose is."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", BODY,
                                             taint=self.a_model_taint())
        self.sql("UPDATE approval SET item_ref='somewhere-else'"
                 " WHERE approval_id=%s", (approval_id,))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)

    def test_13_changing_the_tool_is_refused(self):
        """Invariant 4, other face: an approval for one tool never covers
        another."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", BODY,
                                             taint=self.a_model_taint())
        self.sql("UPDATE approval SET tool_name=%s, arguments=%s"
                 " WHERE approval_id=%s",
                 (ADD_TASK, '{"task_ref": "it-1", "title": "x", "due_on": ""}',
                  approval_id))
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-112", cm.exception.invariant)

    def test_14_a_reused_approval_is_refused(self):
        """Invariant 5. Single use is durable (`consumed_at`), claimed
        atomically, and unchanged by ADR 0048."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "it-1", BODY,
                                             taint=self.a_model_taint())
        self.approvals.decide(token, approval_id, True, decided_by="james")
        with self.assertRaises(Denied) as cm:
            self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual("I-09", cm.exception.invariant)

    def test_15_a_tool_with_no_prose_has_no_elevation_path(self):
        """Invariant 12, structurally. `complete_task` and `add_scope` persist
        no EXPRESSIVE content, so there is nothing to inspect and nothing an
        inspection could vouch for. This is a property of the tool declaration
        (ADR 0036), not a check somebody could forget to write."""
        self.assertEqual(frozenset(), self.writes.content_leaves(COMPLETE_TASK))
        self.assertEqual(frozenset(), self.writes.content_leaves(ADD_SCOPE))
        self.assertEqual(frozenset({"body"}), self.writes.content_leaves(TOOL))
        self.assertEqual(frozenset({"title"}), self.writes.content_leaves(ADD_TASK))

    def test_16_elevate_refuses_rather_than_silently_returning_the_input(self):
        """Invariant 12, the guard's own guard. If the caller's check ever rots
        into a no-op, `elevate` must fail loudly rather than hand back an
        unelevated taint that looks like it was considered."""
        from ..write_path import ApprovalEvidence, elevate
        empty = ApprovalEvidence(approval_id="ap-x", approved_by="james",
                                 proposed_taint=self.a_model_taint(),
                                 content_leaves=frozenset())
        with self.assertRaises(Denied) as cm:
            elevate(self.a_model_taint(), empty)
        self.assertEqual("I-110", cm.exception.invariant)

    # =======================================================================
    # I-40 -- live again, because the taint is no longer synthetic
    # =======================================================================

    def test_17_ordinary_content_does_not_trip_i40(self):
        """Invariant 7, the control. `model.generated` is NOT external
        provenance (resolved 2026-08-15), so an ordinary proposal is
        unaffected and writes keep working."""
        taint = self.a_model_taint()
        self.assertFalse(taint.is_untrusted_derived())
        self.approve_write(taint=taint)
        self.assertEqual([(BODY,)],
                         self.sql("SELECT body FROM item WHERE item_ref='it-1'"))

    def test_18_externally_derived_content_needs_an_approval_naming_the_source(self):
        """Invariant 7. With the synthetic constant gone, a plan drawn from
        `external.web` reaches step 9 as untrusted-derived and is denied
        unless the approval names that source -- which the durable evidence
        now lets `james_approves` do."""
        external = Taint.of("external.web").derive("model.generated")
        self.assertTrue(external.is_untrusted_derived())
        self.approve_write(taint=external)
        provenance, _t, _c, _a, _au = self.state()
        self.assertIn("external.web", provenance,
                      "the external source vanished from the record")

    def test_19_an_approval_naming_no_source_cannot_satisfy_i40(self):
        """Invariant 8. The mechanism is I-40's own: an approval that names
        nothing cannot cover a plan that requires a source to be named."""
        external = Taint.of("external.web").derive("model.generated")
        plan = self.writes.plan_for(LIFE, "it-1", BODY, external)
        # James's act, recorded WITHOUT naming any source -- the pre-ADR-0048
        # shape of `james_approves`.
        self.writes.approvals.james_approves(plan.identity())
        with self.assertRaises(Denied) as cm:
            self.writes.execute_action(self.token(), LIFE, TOOL,
                                       {"item_ref": "it-1", "body": BODY},
                                       external)
        self.assertEqual("I-40", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM item WHERE item_ref='it-1'"))

    # =======================================================================
    # The approval surface -- what James can actually see
    # =======================================================================

    def test_20_every_content_leaf_appears_in_the_rendered_card(self):
        """Invariant 11. The test that keeps "was shown" from drifting away
        from "counts as content": whatever `content_leaves` names, the page
        must actually contain, verbatim."""
        token = self.token()
        self.approvals.propose(token, LIFE, "it-1", BODY,
                               taint=self.a_model_taint())
        status, page = self.seam.approvals_page(self.sid, LIFE)
        self.assertEqual(200, status)
        for leaf in self.writes.content_leaves(TOOL):
            self.assertIn(BODY, page,
                          f"the card does not show the {leaf} being approved")

    def test_21_the_card_shows_a_task_title_through_the_same_mechanism(self):
        """`add_task` used to show its title only by accident of how its
        action_text was phrased. It is now rendered as a content leaf like any
        other, so the property is structural rather than a coincidence."""
        token = self.token()
        self.approvals.propose_action(
            token, LIFE, ADD_TASK,
            {"task_ref": "t1", "title": BODY, "due_on": ""},
            action_text="Add a task.", if_wrong_text="x",
            taint=self.a_model_taint())
        status, page = self.seam.approvals_page(self.sid, LIFE)
        self.assertEqual(200, status)
        self.assertIn(BODY, page)

    def test_22_the_card_names_the_outside_sources_being_relied_on(self):
        """I-40 requires the approval to NAME the source. James is told which
        -- naming a source he was never shown would satisfy the policy while
        defeating it."""
        token = self.token()
        self.approvals.propose(token, LIFE, "it-1", BODY,
                               taint=Taint.of("external.web").derive("model.generated"))
        _status, page = self.seam.approvals_page(self.sid, LIFE)
        self.assertIn("external.web", page,
                      "the card hid the outside source it draws on")

    # =======================================================================
    # End to end -- the defect ADR 0048 was accepted to close
    # =======================================================================

    def test_23_the_silent_laundering_cycle_is_closed(self):
        """The measured defect, re-run -- and the precise thing ADR 0048 fixed.

        Low-trust `external.web` content in scope; the model proposes a note
        echoing it; James approves; the source is deleted.

        BEFORE: the copy came back as provenance `['james.stated']` at HIGHEST.
        The origin was GONE. Nothing downstream could tell the content had ever
        touched the internet, `external_sources()` was empty, and I-40 had
        nothing left to name.

        AFTER: the copy carries `external.web` in its provenance permanently.
        Trust may well be HIGHEST -- James read these exact bytes and vouched
        for them, which is what Option C means and is not a bug -- but the
        ORIGIN survives, so `is_untrusted_derived()` stays true and every
        downstream plan drawn from this row still needs an approval naming the
        source.

        The laundering that is closed is the SILENT kind: content reaching
        trusted status without a human ever seeing it, and shedding its history
        on the way. Content James actually inspected becoming trusted is the
        accepted decision working, not a leak."""
        self.sql("INSERT INTO item (item_ref, scope_path, body, provenance,"
                 " trust, classification, delegation_ancestry, creating_authority)"
                 " VALUES ('web',%s,%s,'{external.web}',%s,%s,'{}','tr-web')",
                 (LIFE, WEB, int(Trust.LOW), int(Classification.INTERNAL)))

        read = self.context.issue_root(identity="james", actor="james",
                                       scope_path=LIFE, rights=frozenset({"read"}),
                                       ceiling=Risk.READ, ttl=60)
        _text, context_taint = self.conversation._scope_context(read, LIFE)
        self.assertEqual(Trust.LOW, context_taint.trust, "the control failed")

        # The model's proposal, carrying what it actually read.
        self.approve_write(ref="laundered", body=WEB,
                           taint=context_taint.derive("model.generated"))

        self.sql("DELETE FROM item WHERE item_ref='web'")
        provenance, _t, _c, _a, _au = self.state("laundered")
        self.assertIn("external.web", provenance,
                      "the copy shed its origin when the source was deleted")

        # The origin survives INTO model context, which is what keeps I-40
        # enforceable against anything derived from this row later.
        _text2, after = self.conversation._scope_context(read, LIFE)
        self.assertIn("external.web", after.provenance,
                      "the block forgot the content had an outside source")
        self.assertTrue(after.is_untrusted_derived(),
                        "I-40 lost its grip on externally-derived content")
        self.assertEqual(frozenset({"external.web"}), after.external_sources(),
                         "there is no source left for an approval to name")


if __name__ == "__main__":
    unittest.main()
