"""F-9 and F-10: two scopes that were derived from the wrong evidence.

Both defects are the same shape -- a statement that names a row by too little
-- on opposite sides of the write path, and both were measured against real
PostgreSQL before this suite existed.

F-9 -- THE AUTHORITY'S SCOPE WAS DERIVED FROM `item` ALONE
----------------------------------------------------------
`RevocationRegistry.revoke` establishes where an execution identity ran by
looking for rows it created, and looked only at `item`. ADR 0049 gave `task`
the same `creating_authority` column and made `_establish` check a task's
authority against this registry -- but nothing could put a task authority INTO
it. Every approval decision mints its own execution token, so a task-writing
authority writes exactly one task and zero items: the derivation returned
nothing, the guard refused, and the authority was unrevocable FOREVER.

The withholding check downstream still ran. It simply answered "not revoked"
every time, because the set it consults could never contain the identity it was
asking about. A fail-closed reader defaulting open, silently, for exactly the
content ADR 0049 exists to protect (`S7-D5`, `I-111`).

F-10 -- `complete_task` NAMED THE ROW BY `task_ref` ALONE
---------------------------------------------------------
`task_ref` is unique only per `(scope_path, task_ref)`, and a bound channel
reaches its own scope AND every descendant. So one approval closed every task
sharing that ref anywhere beneath it -- an approval for one resource executing
against several (`I-109`, `I-112`), with a single audit record naming only the
approved scope, leaving the other scope mutated with no record in it (`I-49`).

Every other branch of the transport pins the row to `ch.scope_path`. This one
did not.

WHAT NEITHER FIX CHANGES. RLS is still what makes another scope unreachable;
neither of these statements was ever the isolation control, and neither becomes
one. Human visibility is unchanged (ADR 0049): a revoked task is withheld from
the MODEL and stays on James's surfaces. Asserted below in both directions.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_authority_scope_and_completion_scope
"""

from __future__ import annotations

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
from ...core.types import Classification, Denied, Risk, Taint, Trust
from ...tools.pep import ToolPEP
from ...tools.registry import ToolRegistry
from . import authfixture

BUSINESS = "/business"
CLIENT = "/business/client-a"
SCOPES = [(BUSINESS, "domain", None), (CLIENT, "client", BUSINESS)]
GRANTS = [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")]
CRED_REF = "control-plane/anthropic"

# Distinctive enough that finding it in a prompt is not a coincidence.
TASK_TITLE = "MARKER-TASK-call-the-supplier-about-the-invoice"
NOTE_BODY = "MARKER-NOTE-the-quote-was-sent-on-tuesday"
SHARED_REF = "invoice"
PARENT_TITLE = "MARKER-PARENT-chase-the-business-invoice"
CHILD_TITLE = "MARKER-CHILD-chase-the-client-invoice"


class ScriptedTransport:
    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        return ModelResponse(text="Noted.",
                             taint=Taint.of("model.generated", Classification.INTERNAL))


@unittest.skipUnless(db.available(),
                     "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class AuthorityScopeAndCompletionScopeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-f9-f10-")
        self.context = ContextService(self.tree, secret=b"f9-f10-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        # Both scopes: F-10 is only observable when a parent and a descendant
        # can each be written to through the real path.
        for scope in (BUSINESS, CLIENT):
            broker.register(
                CredentialBinding(
                    binding_id="db-item-write", scope_path=scope,
                    permitted_operations=frozenset({TOOL, ADD_TASK, COMPLETE_TASK})),
                secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        for factory in (write_item_tool, add_task_tool, complete_task_tool):
            registry.register(factory())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")
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

    def through_the_real_path(self, scope, tool_name, arguments, taint=None):
        """Propose, James decides, the action executes -- the production route.

        Returns the EXECUTION token's trace id, which is what the transport
        persists as `creating_authority`. Each decision mints its own token,
        so this is a fresh authority every time: exactly the shape that made
        F-9 universal rather than an edge case.
        """
        approval_id = self.approvals.propose_action(
            self.token(scope), scope, tool_name, arguments,
            action_text=f"{tool_name} in this scope.",
            if_wrong_text="The wrong thing is recorded.", taint=taint)
        executor = self.token(scope)
        self.approvals.decide(executor, approval_id, True, decided_by="james")
        return executor.trace_id

    def add_task(self, scope, ref, title, taint=None):
        return self.through_the_real_path(
            scope, ADD_TASK, {"task_ref": ref, "title": title, "due_on": ""},
            taint=taint or Taint.of("james.stated", Classification.CONFIDENTIAL))

    def prompt_after_a_turn(self, scope):
        """What the gateway actually received. The model's own view, not a
        convenient projection of it."""
        token = self.token(scope, rights=frozenset({"read"}), ceiling=Risk.READ)
        self.conversation.respond(token, scope, "what is here?")
        return self.transport.prompts[-1]

    def open_tasks(self):
        return self.sql("SELECT scope_path, task_ref, title FROM task"
                        " WHERE done_at IS NULL ORDER BY scope_path")

    # =======================================================================
    # F-9 -- 1-6: the authority's scope is derived from every table that
    #             records one
    # =======================================================================

    def test_01_a_task_only_authority_is_revocable(self):
        """THE DEFECT, directly. This authority wrote one task and no item --
        which is what EVERY task-writing authority does, because each approval
        decision mints its own execution token. Before the union it could not
        be revoked at all."""
        authority = self.add_task(BUSINESS, "t-1", TASK_TITLE)

        self.assertEqual([], self.sql("SELECT 1 FROM item"),
                         "the fixture wrote an item, so this is not the"
                         " task-only case the defect was about")
        self.assertEqual(
            [(authority,)],
            self.sql("SELECT creating_authority FROM task WHERE task_ref='t-1'"),
            "the task did not record the executing authority")

        self.revocations.revoke(self.token(BUSINESS), authority,
                                revoked_by="james")

        self.assertEqual(
            [(BUSINESS,)],
            self.sql("SELECT scope_path FROM authority_revocation"
                     " WHERE execution_identity=%s", (authority,)),
            "the revocation was not filed at the authority's own scope")

    def test_02_a_revoked_task_authority_withholds_the_title(self):
        """Revocation has to REACH the reader, not merely be recorded. The
        title is content (ADR 0049), so a revoked authority withholds it from
        model context exactly as it withholds an item's body."""
        authority = self.add_task(BUSINESS, "t-1", TASK_TITLE)
        self.assertIn(TASK_TITLE, self.prompt_after_a_turn(BUSINESS),
                      "the title never reached the model, so withholding it"
                      " later would prove nothing")

        self.revocations.revoke(self.token(BUSINESS), authority,
                                revoked_by="james")

        prompt = self.prompt_after_a_turn(BUSINESS)
        self.assertNotIn(TASK_TITLE, prompt,
                         "a revoked authority's task title reached the model")
        self.assertIn("withheld", prompt,
                      "the withholding was silent -- NOVA must say it cannot"
                      " vouch for something rather than answer as though the"
                      " scope were emptier than it is")
        self.assertIsNotNone(authority)

    def test_03_a_revoked_task_is_still_visible_to_james(self):
        """ADR 0049's three properties stay apart. Withholding is a MODEL
        CONTEXT property; James still sees the whole task, and it is still
        completable. This fix must not have quietly changed that."""
        authority = self.add_task(BUSINESS, "t-1", TASK_TITLE)
        self.revocations.revoke(self.token(BUSINESS), authority,
                                revoked_by="james")

        status, page = self.seam.scope_page(self.sid, BUSINESS)
        self.assertEqual(200, status)
        self.assertIn(TASK_TITLE, page,
                      "revocation removed the task from James's own surface")

    def test_04_an_item_only_authority_is_still_revocable(self):
        """The control. The union must not have broken the case that always
        worked -- and this is what proves the mechanism itself was sound and
        only its evidence was too narrow."""
        approval_id = self.approvals.propose(
            self.token(BUSINESS), BUSINESS, "n-1", NOTE_BODY,
            taint=Taint.of("james.stated", Classification.CONFIDENTIAL))
        executor = self.token(BUSINESS)
        self.approvals.decide(executor, approval_id, True, decided_by="james")

        self.assertEqual([], self.sql("SELECT 1 FROM task"))
        self.revocations.revoke(self.token(BUSINESS), executor.trace_id,
                                revoked_by="james")
        self.assertEqual(
            [(BUSINESS,)],
            self.sql("SELECT scope_path FROM authority_revocation"
                     " WHERE execution_identity=%s", (executor.trace_id,)))
        self.assertNotIn(NOTE_BODY, self.prompt_after_a_turn(BUSINESS))

    def test_05_one_authority_across_both_tables_resolves_to_one_scope(self):
        """A token binds ONE scope, so both halves of the union can only ever
        agree. Seeded rather than driven, because the production path gives
        each decision its own token and cannot produce one identity writing
        twice -- the point is that the union DEDUPLICATES rather than
        producing two rows and tripping the guard."""
        authority = "shared-authority-0000000000000001"
        self.sql("INSERT INTO item (item_ref, scope_path, body, provenance,"
                 " trust, classification, delegation_ancestry, creating_authority)"
                 " VALUES ('i-1',%s,%s,%s,%s,%s,%s,%s)",
                 (BUSINESS, NOTE_BODY, ["james.stated"], int(Trust.HIGHEST),
                  int(Classification.INTERNAL), [], authority))
        self.sql("INSERT INTO task (task_ref, scope_path, title, provenance,"
                 " trust, classification, delegation_ancestry, creating_authority)"
                 " VALUES ('t-1',%s,%s,%s,%s,%s,%s,%s)",
                 (BUSINESS, TASK_TITLE, ["james.stated"], int(Trust.HIGHEST),
                  int(Classification.INTERNAL), [], authority))

        self.revocations.revoke(self.token(BUSINESS), authority,
                                revoked_by="james")

        self.assertEqual(
            [(BUSINESS,)],
            self.sql("SELECT scope_path FROM authority_revocation"
                     " WHERE execution_identity=%s", (authority,)))
        prompt = self.prompt_after_a_turn(BUSINESS)
        self.assertNotIn(NOTE_BODY, prompt)
        self.assertNotIn(TASK_TITLE, prompt)

    def test_06_an_authority_that_wrote_nothing_still_fails_closed(self):
        """The guard is UNCHANGED. With no evidence in either table there is
        still no honest scope to file at, and refusing is still the answer --
        widening the evidence must not have widened the conclusion."""
        stranger = self.token(BUSINESS)
        with self.assertRaises(Denied) as cm:
            self.revocations.revoke(self.token(BUSINESS), stranger.trace_id,
                                    revoked_by="james")
        self.assertEqual("I-111", cm.exception.invariant)
        self.assertTrue(cm.exception.security_event)
        self.assertEqual([], self.sql("SELECT 1 FROM authority_revocation"),
                         "a refused revocation still wrote a row")

    def test_07_a_contradictory_authority_is_refused(self):
        """The guard's OTHER half, which the production path cannot reach.

        One token binds one scope, so an identity recorded at two scopes is
        impossible through the write path -- it can only arrive by corruption
        or by a future change that breaks the one-token-one-scope property.
        The guard must still refuse rather than pick one, and this is the only
        way to observe it doing so."""
        authority = "contradictory-authority-000000001"
        self.sql("INSERT INTO item (item_ref, scope_path, body,"
                 " creating_authority) VALUES ('i-1',%s,%s,%s)",
                 (BUSINESS, NOTE_BODY, authority))
        self.sql("INSERT INTO task (task_ref, scope_path, title,"
                 " creating_authority) VALUES ('t-1',%s,%s,%s)",
                 (CLIENT, TASK_TITLE, authority))

        with self.assertRaises(Denied) as cm:
            self.revocations.revoke(self.token(BUSINESS), authority,
                                    revoked_by="james")
        self.assertEqual("I-111", cm.exception.invariant)
        self.assertEqual([], self.sql("SELECT 1 FROM authority_revocation"))

    # =======================================================================
    # F-10 -- 8-12: a completion mutates the approved scope and no other
    # =======================================================================

    def test_08_the_same_task_ref_exists_in_a_parent_and_a_descendant(self):
        """The precondition, and it is ordinary rather than contrived: refs
        come from the model's PROPOSE_TASK marker and `UNIQUE (scope_path,
        task_ref)` makes them unique PER SCOPE, so the same ref repeating
        across a scope and its child is expected, not a collision."""
        self.add_task(BUSINESS, SHARED_REF, PARENT_TITLE)
        self.add_task(CLIENT, SHARED_REF, CHILD_TITLE)

        self.assertEqual(
            [(BUSINESS, SHARED_REF, PARENT_TITLE),
             (CLIENT, SHARED_REF, CHILD_TITLE)],
            self.open_tasks(),
            "the two tasks did not coexist, so nothing below is testing F-10")

    def test_09_completing_the_parent_task_leaves_the_descendant_open(self):
        """THE DEFECT, directly. James decides ONE task in /business. Before
        the scope predicate, the descendant's task of the same ref was closed
        in the same statement -- a commitment in a client scope silently
        finished by a decision about a different scope's task."""
        self.add_task(BUSINESS, SHARED_REF, PARENT_TITLE)
        self.add_task(CLIENT, SHARED_REF, CHILD_TITLE)

        self.through_the_real_path(BUSINESS, COMPLETE_TASK,
                                   {"task_ref": SHARED_REF})

        self.assertEqual([(CLIENT, SHARED_REF, CHILD_TITLE)], self.open_tasks(),
                         "one approval closed a task in another scope")
        self.assertEqual(
            [(BUSINESS,)],
            self.sql("SELECT scope_path FROM task WHERE done_at IS NOT NULL"),
            "the wrong row -- or more than one row -- was closed")

    def test_10_completing_the_descendant_task_leaves_the_parent_open(self):
        """The other direction. Containment runs downward only, so this was
        never broken -- asserted so the fix is known to bound the statement
        rather than merely to have changed its direction."""
        self.add_task(BUSINESS, SHARED_REF, PARENT_TITLE)
        self.add_task(CLIENT, SHARED_REF, CHILD_TITLE)

        self.through_the_real_path(CLIENT, COMPLETE_TASK,
                                   {"task_ref": SHARED_REF})

        self.assertEqual([(BUSINESS, SHARED_REF, PARENT_TITLE)],
                         self.open_tasks())

    def test_11_the_audit_names_only_the_scope_actually_mutated(self):
        """`I-49`: recorded per scope touched. The record was never the
        problem -- it always named one scope. The problem was that TWO were
        mutated, so the descendant's own activity surface showed nothing at
        all. With the statement bounded, the record and the mutation agree."""
        self.add_task(BUSINESS, SHARED_REF, PARENT_TITLE)
        self.add_task(CLIENT, SHARED_REF, CHILD_TITLE)
        self.through_the_real_path(BUSINESS, COMPLETE_TASK,
                                   {"task_ref": SHARED_REF})

        completions = self.sql(
            "SELECT scope_path, detail FROM audit_record"
            " WHERE category='data.write' AND detail LIKE 'complete_task%%'")
        self.assertEqual([(BUSINESS, f"complete_task task_ref={SHARED_REF}")],
                         completions,
                         "the completion audit does not match what was mutated")

        mutated = self.sql("SELECT scope_path FROM task WHERE done_at IS NOT NULL")
        self.assertEqual([(BUSINESS,)], mutated)
        self.assertEqual({r[0] for r in completions}, {r[0] for r in mutated},
                         "a scope was mutated with no record in it (I-49)")

    def test_12_the_descendant_task_is_still_live_on_both_surfaces(self):
        """The consequence James would actually notice. After the parent's
        task is completed the client's task must still reach the model AND
        still be on his attention surface -- a task silently closed disappears
        from the only place he would have seen it."""
        self.add_task(BUSINESS, SHARED_REF, PARENT_TITLE)
        self.add_task(CLIENT, SHARED_REF, CHILD_TITLE)
        self.through_the_real_path(BUSINESS, COMPLETE_TASK,
                                   {"task_ref": SHARED_REF})

        self.assertIn(CHILD_TITLE, self.prompt_after_a_turn(CLIENT),
                      "the client's open task vanished from model context")
        status, page = self.seam.scope_page(self.sid, CLIENT)
        self.assertEqual(200, status)
        self.assertIn(CHILD_TITLE, page,
                      "the client's open task vanished from James's surface")

    def test_13_completion_still_works_and_is_still_idempotent(self):
        """The narrowing must not have broken the tool. One task, no
        descendant involved: it closes, and a second completion of the same
        ref is a no-op at the provider rather than a second completion."""
        self.add_task(BUSINESS, "solo", PARENT_TITLE)
        self.through_the_real_path(BUSINESS, COMPLETE_TASK, {"task_ref": "solo"})
        first = self.sql("SELECT done_at FROM task WHERE task_ref='solo'")
        self.assertIsNotNone(first[0][0], "the task was not completed at all")

        self.through_the_real_path(BUSINESS, COMPLETE_TASK, {"task_ref": "solo"})
        self.assertEqual(first,
                         self.sql("SELECT done_at FROM task WHERE task_ref='solo'"),
                         "a repeat completion moved the completion time")


if __name__ == "__main__":
    unittest.main()
