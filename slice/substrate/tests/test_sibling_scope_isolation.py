"""F-12: sibling content is never correlated in one model request (`I-95`).

THE DECISION. Sibling isolation governs INDEPENDENTLY of ancestor containment.
A token bound to a parent scope may legitimately cover and read descendant
scopes -- that is containment, and it is unchanged -- but covering two sibling
scopes does not authorize their content to be COMBINED into one provider
request.

THE DEFECT IT CLOSES, measured before this existed. `_scope_context` read
`item` and `task` with no scope predicate, relying on RLS alone. RLS admits the
bound scope AND every descendant, and the assembled block was then labelled with
the CONVERSATION's scope -- which is what the gateway's `I-95` check compares.
So a conversation at `/business` put `/business/client-a`'s and
`/business/client-b`'s CLIENT-CONFIDENTIAL content into ONE prompt, sent to one
third party, under one request, and the check passed because every item carried
the same label. `CROSS_SCOPE_DATA_RULES` §2 names that object exactly: "a join
point of exactly the same kind as a shared index or a cross-scope cache".

CONTAINMENT AND ISOLATION ARE DIFFERENT PROPERTIES. This suite asserts both,
separately, because collapsing them is what produced the defect:

    containment   unchanged -- the parent token still covers descendants, and
                  human surfaces still show James descendant content
    isolation     the model request carries ONE scope's content

NOT AN RLS FIX. RLS was doing its job throughout: a conversation at client-a
could never see client-b, before or after. The defect was one layer up, in what
the model-context constructor chose to assemble from what RLS correctly allowed
it to see. No policy, grant, role or schema is touched.

TWO PREDICATES, INDEPENDENTLY LOAD-BEARING. `item` and `task` are separate
queries and each leaked on its own, so the sibling tests below are split by
entity: removing either predicate alone must fail its own test.

UNIFORM ACROSS SIBLINGS. `I-95` says "sibling content", not "client content",
and these scopes are `client`-kind only because the fixture says so -- nothing
in the production path reads `kind`.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_sibling_scope_isolation
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
from ...core.types import Classification, Risk, Taint
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

PARENT = "/business"
A = "/business/client-a"
B = "/business/client-b"
SCOPES = [(PARENT, "domain", None), (A, "client", PARENT), (B, "client", PARENT)]
GRANTS = [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")]
CRED_REF = "control-plane/anthropic"

# Distinctive enough that finding one in a prompt is not a coincidence.
A_NOTE = "MARKER-A-NOTE-margin-is-38-percent"
B_NOTE = "MARKER-B-NOTE-they-are-late-on-payment"
A_TASK = "MARKER-A-TASK-send-the-revised-quote"
B_TASK = "MARKER-B-TASK-chase-the-overdue-invoice"
PARENT_NOTE = "MARKER-PARENT-NOTE-the-quarter-closes-friday"
PARENT_TASK = "MARKER-PARENT-TASK-review-the-pipeline"


class ScriptedTransport:
    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        return ModelResponse(text="Noted.",
                             taint=Taint.of("model.generated", Classification.INTERNAL))


class ScopedWritePath(WritePath):
    """The production parameterization (`app.py`): the datastore credential
    binding is per-scope, because `I-24` requires a token's scope to COVER its
    binding's scope and coverage runs downward only. A single fixed binding
    cannot serve sibling scopes, so the fixture must mirror production here or
    it could not write to two siblings at all."""

    def binding_for(self, scope_path: str, tool_name: str = TOOL):
        return dataclasses.replace(super().binding_for(scope_path, tool_name),
                                   credential_binding_id=f"db-item-write{scope_path}")


@unittest.skipUnless(db.available(),
                     "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class SiblingScopeIsolationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-f12-")
        self.context = ContextService(self.tree, secret=b"f12-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        for scope in (PARENT, A, B):
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

    def token(self, scope, rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope, rights=rights,
                                       ceiling=ceiling, ttl=60)

    def through_the_real_path(self, scope, tool_name, arguments):
        """Propose, James decides, the action executes. CLIENT-CONFIDENTIAL,
        because that is the classification the cross-scope rules are about."""
        approval_id = self.approvals.propose_action(
            self.token(scope), scope, tool_name, arguments,
            action_text=f"{tool_name} in this scope.",
            if_wrong_text="The wrong thing is recorded.",
            taint=Taint.of("james.stated", Classification.CLIENT_CONFIDENTIAL))
        self.approvals.decide(self.token(scope), approval_id, True,
                              decided_by="james")

    def note(self, scope, ref, body):
        self.through_the_real_path(scope, TOOL, {"item_ref": ref, "body": body})

    def task(self, scope, ref, title):
        self.through_the_real_path(
            scope, ADD_TASK, {"task_ref": ref, "title": title, "due_on": ""})

    def prompt_at(self, scope):
        """What the gateway ACTUALLY received. The provider's view of the
        request, not a convenient projection of it -- the whole finding was
        about what leaves NOVA in one buffer."""
        token = self.token(scope, rights=frozenset({"read"}), ceiling=Risk.READ)
        self.conversation.respond(token, scope, "what is here?")
        return self.transport.prompts[-1]

    def seed_both_clients(self):
        self.note(A, "a-note", A_NOTE)
        self.note(B, "b-note", B_NOTE)
        self.task(A, "a-task", A_TASK)
        self.task(B, "b-task", B_TASK)

    # =======================================================================
    # 1-3 -- the request carries one scope's content
    # =======================================================================

    def test_01_a_parent_conversation_does_not_combine_two_clients_notes(self):
        """THE DEFECT, directly, for `item`. Both clients' notes reached one
        prompt because the item query had no scope predicate. This test fails
        if the ITEM predicate alone is removed."""
        self.seed_both_clients()
        prompt = self.prompt_at(PARENT)

        self.assertNotIn(A_NOTE, prompt,
                         "client-a's note reached a model request made at the"
                         " parent scope")
        self.assertNotIn(B_NOTE, prompt,
                         "client-b's note reached a model request made at the"
                         " parent scope")
        self.assertFalse(A_NOTE in prompt and B_NOTE in prompt,
                         "two sibling clients' CLIENT-CONFIDENTIAL notes were"
                         " correlated in ONE provider request (I-95)")

    def test_02_a_parent_conversation_does_not_combine_two_clients_tasks(self):
        """The same defect for `task`, which is a SEPARATE query and leaked on
        its own. This test fails if the TASK predicate alone is removed --
        which is what makes the two predicates independently load-bearing."""
        self.seed_both_clients()
        prompt = self.prompt_at(PARENT)

        self.assertNotIn(A_TASK, prompt,
                         "client-a's task title reached a model request made at"
                         " the parent scope")
        self.assertNotIn(B_TASK, prompt,
                         "client-b's task title reached a model request made at"
                         " the parent scope")
        self.assertFalse(A_TASK in prompt and B_TASK in prompt,
                         "two sibling clients' task content was correlated in"
                         " ONE provider request (I-95)")

    def test_03_client_a_sees_its_own_content_and_not_client_b(self):
        """The narrow conversation is the one that must keep working. Sibling
        invisibility here was NEVER broken -- RLS refuses it -- and is asserted
        so the fix is known to have narrowed the parent rather than to have
        changed what a client scope can see."""
        self.seed_both_clients()
        prompt = self.prompt_at(A)

        self.assertIn(A_NOTE, prompt, "client-a lost its own note")
        self.assertIn(A_TASK, prompt, "client-a lost its own task")
        self.assertNotIn(B_NOTE, prompt, "client-a's request carried client-b's note")
        self.assertNotIn(B_TASK, prompt, "client-a's request carried client-b's task")

    def test_04_client_b_sees_its_own_content_and_not_client_a(self):
        """The mirror. Asserted separately because a predicate bound from the
        wrong side would pass one direction and fail the other."""
        self.seed_both_clients()
        prompt = self.prompt_at(B)

        self.assertIn(B_NOTE, prompt, "client-b lost its own note")
        self.assertIn(B_TASK, prompt, "client-b lost its own task")
        self.assertNotIn(A_NOTE, prompt, "client-b's request carried client-a's note")
        self.assertNotIn(A_TASK, prompt, "client-b's request carried client-a's task")

    # =======================================================================
    # 5-6 -- the predicate NARROWS; it does not empty
    # =======================================================================

    def test_05_a_parent_conversation_still_sees_its_own_content(self):
        """The fix must not have turned the parent into a blind scope. A
        business-level conversation still answers from the business's OWN notes
        and tasks -- what it no longer does is speak for its children."""
        self.seed_both_clients()
        self.note(PARENT, "p-note", PARENT_NOTE)
        self.task(PARENT, "p-task", PARENT_TASK)

        prompt = self.prompt_at(PARENT)
        self.assertIn(PARENT_NOTE, prompt, "the parent lost its own note")
        self.assertIn(PARENT_TASK, prompt, "the parent lost its own task")
        self.assertNotIn(A_NOTE, prompt)
        self.assertNotIn(B_NOTE, prompt)

    def test_06_the_scope_line_and_counts_are_unchanged(self):
        """Scope identification and the subtree-wide pending count are
        DELIBERATELY untouched by this decision: a count in which no scope is
        identifiable is permitted aggregation (CROSS_SCOPE_DATA_RULES §3), and
        narrowing it is not part of the decomposition rule."""
        self.seed_both_clients()
        # One pending approval in a DESCENDANT, left undecided.
        self.approvals.propose_action(
            self.token(A), A, ADD_TASK,
            {"task_ref": "pending-one", "title": "MARKER-PENDING", "due_on": ""},
            action_text="x", if_wrong_text="y",
            taint=Taint.of("james.stated", Classification.CLIENT_CONFIDENTIAL))

        prompt = self.prompt_at(PARENT)
        self.assertIn(f"Scope: {PARENT}", prompt)
        self.assertIn("Pending approvals awaiting James: 1", prompt,
                      "the subtree-wide pending count changed -- it was not in"
                      " scope for this decision")
        self.assertNotIn("MARKER-PENDING", prompt,
                         "the pending approval's CONTENT reached the model;"
                         " only the count may cross")

    # =======================================================================
    # 7-8 -- containment, and the human surfaces, are unchanged
    # =======================================================================

    def test_07_human_surfaces_still_show_descendant_content(self):
        """CONTAINMENT IS UNCHANGED. This is the property that distinguishes
        the fix from an RLS change: James standing at the parent still sees his
        clients' notes and tasks on screen. Model visibility narrowed; human
        visibility did not -- the same separation ADR 0049 already established
        for withheld content."""
        self.seed_both_clients()

        status, page = self.seam.scope_page(self.sid, PARENT)
        self.assertEqual(200, status)
        self.assertIn(A_NOTE, page, "the parent's page lost client-a's note")
        self.assertIn(B_NOTE, page, "the parent's page lost client-b's note")
        self.assertIn(A_TASK, page, "the parent's page lost client-a's task")
        self.assertIn(B_TASK, page, "the parent's page lost client-b's task")

    def test_08_the_attention_surface_still_reaches_every_scope(self):
        """The other human surface, and the one that is cross-scope by design.
        It composes above N independently authorized single-scope reads and
        never touches the gateway, so this decision does not reach it."""
        self.seed_both_clients()
        gathered = self.attention.gather("james", "james")
        self.assertEqual({PARENT, A, B}, set(gathered.scopes_read),
                         "the attention surface stopped reaching every scope")

    def test_09_the_token_still_covers_descendants(self):
        """Containment at the type level, asserted so a later reader cannot
        mistake this suite for a narrowing of `covers()`. The parent token
        covers both clients; what changed is only what the model request is
        assembled FROM."""
        parent_token = self.token(PARENT)
        self.assertTrue(parent_token.covers(A))
        self.assertTrue(parent_token.covers(B))
        # ...and a client token still covers neither its sibling nor its parent.
        client_token = self.token(A)
        self.assertFalse(client_token.covers(B))
        self.assertFalse(client_token.covers(PARENT))

    def test_10_a_descendant_write_from_the_parent_still_works(self):
        """Ancestor-to-descendant AUTHORIZATION is untouched. Only the model
        request narrowed; the write path did not, and proving so is what keeps
        this decision from being read as a containment change."""
        self.note(A, "written-from-a", A_NOTE)
        with self.boundary.open(self.token(PARENT, frozenset({"read"}),
                                           Risk.READ)) as ch:
            rows = ch.fetch("SELECT scope_path FROM item WHERE item_ref=%s",
                            ("written-from-a",))
        self.assertEqual([(A,)], rows,
                         "the parent channel could no longer even READ the"
                         " descendant row -- that would be a containment change")


if __name__ == "__main__":
    unittest.main()
