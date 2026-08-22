"""I-111: the security state survives the authoritative persistence boundary.

Before this, the substrate persisted an item's body and nothing about how it
came to exist -- and `_scope_context` handed the model `Taint.of("james.stated")`
for everything it read back. That is trust SYNTHESIZED at read time from the
fact that a row was in NOVA's own database, which is precisely what `I-110`
forbids and what `I-111` exists to make impossible.

The claim now:

    what reaches the model carries the provenance, trust and classification
    that were RECORDED when it was written -- and anything whose security
    state cannot be established does not reach the model at all

THE HARD PART IS THE SECOND HALF. Five separate things can be unknown, and each
one withholds independently: provenance, trust, classification, delegation
ancestry, creating authority. A sixth withholds too -- a non-empty ancestry --
because a delegate's ancestors may have executed in BROADER scopes whose
revocation records this channel cannot see (`I-03`, `I-86`). "Could not check"
must never become "not revoked", so it withholds rather than guesses.

Legacy rows are the ordinary case of all this, not a special case: they have
NULL throughout and are withheld by the same rule, with no backfill, no assumed
`james.stated`, and no invented authority.

Every test uses the real PostgreSQL boundary. Mocking the store here would
prove the mock behaved.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_provenance_persistence
"""

from __future__ import annotations

import os
import tempfile
import unittest

from .. import db, tree_store
from ..approval_flow import ApprovalService
from ..boundary import DataAccessBoundary
from ..conversation import (CONVERSATION_MODEL, PROVIDER, ConversationService)
from ..revocation import RevocationRegistry
from ..seam import Seam
from ..write_path import (PostgresItemIntegration, WritePath, write_item_tool,
                          TOOL)
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
BUSINESS = "/business"
SCOPES = [(LIFE, "domain", None), (BUSINESS, "domain", None)]
GRANTS = [("james", p, r) for p, _, _ in SCOPES for r in ("read", "write")]
CRED_REF = "control-plane/anthropic"

MARKER = "MARKER-the-dentist-on-thursday"


class ScriptedTransport:
    def __init__(self):
        self.prompts: list[str] = []

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        return ModelResponse(text="Noted.",
                             taint=Taint.of("model.generated", Classification.INTERNAL))


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class ProvenancePersistenceTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-i111-")
        self.context = ContextService(self.tree, secret=b"i111-suite-key")
        audit = AuditWriter(StoreRegistry(os.path.join(tmp, "data")))
        self.pdp = PolicyDecisionPoint(self.tree, self.context, audit)
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)

        vault = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
        broker = CredentialBroker(self.tree, vault, audit)
        broker.register(
            CredentialBinding(binding_id="db-item-write", scope_path=LIFE,
                              permitted_operations=frozenset({TOOL})),
            secret="integration-credential-" + os.urandom(4).hex())
        registry = ToolRegistry()
        registry.register(write_item_tool())
        pep = ToolPEP(registry, broker, self.context, audit)
        self.integration = PostgresItemIntegration(self.boundary)
        self.writes = WritePath(self.pdp, registry, pep, broker,
                                self.integration, "db-item-write")
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
                         tree=self.tree, conversation=self.conversation)

    def tearDown(self):
        self.boundary.close()

    # -- helpers -------------------------------------------------------------

    def token(self, scope=LIFE, rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
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

    def write_through_the_real_path(self, ref="it-1", body=MARKER, scope=LIFE):
        """The production route: propose, James decides, the write executes."""
        token = self.token(scope)
        approval_id = self.approvals.propose(token, scope, ref, body)
        self.approvals.decide(token, approval_id, True, decided_by="james")
        return token

    def seed_raw(self, ref, body, scope=LIFE, **security):
        """A row written straight to the table, with whatever security state
        the test wants -- including none, which is a legacy row."""
        cols = "item_ref, scope_path, body"
        vals = [ref, scope, body]
        for k, v in security.items():
            cols += f", {k}"
            vals.append(v)
        placeholders = ",".join(["%s"] * len(vals))
        self.sql(f"INSERT INTO item ({cols}) VALUES ({placeholders})", tuple(vals))

    def prompt_after_a_turn(self, scope=LIFE):
        token = self.context.issue_root(identity="james", actor="james",
                                        scope_path=scope,
                                        rights=frozenset({"read"}),
                                        ceiling=Risk.READ, ttl=60)
        self.conversation.respond(token, scope, "what is here?")
        return self.transport.prompts[-1]

    # =======================================================================
    # 1-4 -- the state is written, and comes back as it was written
    # =======================================================================

    def test_01_a_real_write_persists_its_security_state(self):
        """The control. If this fails, everything below is testing nothing."""
        self.write_through_the_real_path()
        row = self.sql("SELECT provenance, trust, classification,"
                       " delegation_ancestry, creating_authority IS NOT NULL"
                       " FROM item WHERE item_ref='it-1'")[0]
        self.assertEqual((["james.stated"], int(Trust.HIGHEST),
                          int(Classification.INTERNAL), [], True), row)

    def test_02_multiple_provenance_values_survive_as_a_union(self):
        """I-99: the union, not the latest writer. Stored as a set-valued
        column precisely so it cannot be collapsed to one value."""
        self.seed_raw("multi", "body",
                      provenance=["james.stated", "external.web"],
                      trust=int(Trust.LOW), classification=int(Classification.INTERNAL),
                      delegation_ancestry=[], creating_authority="tr-multi")
        self.assertEqual([(["james.stated", "external.web"],)],
                         self.sql("SELECT provenance FROM item WHERE item_ref='multi'"))

    def test_03_lowest_trust_and_classification_survive(self):
        """Persisted, not recomputed: a reader restores what was recorded."""
        self.seed_raw("low", "body", provenance=["external.web"],
                      trust=int(Trust.LOW),
                      classification=int(Classification.SENSITIVE_PERSONAL),
                      delegation_ancestry=[], creating_authority="tr-low")
        kept, withheld = ConversationService._establish(
            self.sql("SELECT item_ref, body, provenance, trust, classification,"
                     " delegation_ancestry, creating_authority FROM item"
                     " WHERE item_ref='low'"), set())
        self.assertEqual(0, withheld)
        taint = kept[0][2]
        self.assertEqual(Trust.LOW, taint.trust)
        self.assertEqual(Classification.SENSITIVE_PERSONAL, taint.classification)
        self.assertEqual(frozenset({"external.web"}), taint.provenance)

    def test_04_populated_ancestry_preserves_order(self):
        """An ordered array, not a set: the delegation chain is a sequence."""
        chain = ["tr-root", "tr-middle", "tr-leaf"]
        self.seed_raw("deep", "body", provenance=["agent.generated"],
                      trust=int(Trust.MEDIUM), classification=int(Classification.INTERNAL),
                      delegation_ancestry=chain, creating_authority="tr-child")
        self.assertEqual([(chain,)],
                         self.sql("SELECT delegation_ancestry FROM item"
                                  " WHERE item_ref='deep'"))

    # =======================================================================
    # 5-11 -- every unknown withholds, independently
    # =======================================================================

    def _withheld(self, **security):
        self.seed_raw("subject", MARKER, **security)
        prompt = self.prompt_after_a_turn()
        self.assertNotIn(MARKER, prompt, "an unestablishable item reached the model")
        self.assertIn("withheld", prompt, "the withholding was not reported")
        return prompt

    def test_05_unknown_provenance_withholds(self):
        self._withheld(trust=int(Trust.HIGHEST),
                       classification=int(Classification.INTERNAL),
                       delegation_ancestry=[], creating_authority="tr-1")

    def test_06_unknown_trust_withholds(self):
        self._withheld(provenance=["james.stated"],
                       classification=int(Classification.INTERNAL),
                       delegation_ancestry=[], creating_authority="tr-1")

    def test_07_unknown_classification_withholds(self):
        self._withheld(provenance=["james.stated"], trust=int(Trust.HIGHEST),
                       delegation_ancestry=[], creating_authority="tr-1")

    def test_08_unknown_ancestry_withholds(self):
        """NULL ancestry is NOT the same as `[]`. One is 'we never recorded
        whether this was delegated', the other is 'it was not'."""
        self._withheld(provenance=["james.stated"], trust=int(Trust.HIGHEST),
                       classification=int(Classification.INTERNAL),
                       creating_authority="tr-1")

    def test_09_unknown_creating_authority_withholds(self):
        """Without the author, its revocation state cannot be looked up at
        all -- so S7-D5 cannot be satisfied and the item does not go."""
        self._withheld(provenance=["james.stated"], trust=int(Trust.HIGHEST),
                       classification=int(Classification.INTERNAL),
                       delegation_ancestry=[])

    def test_10_a_populated_ancestry_withholds(self):
        """The subtle one. An ancestor may have executed in a BROADER scope
        whose revocation record this channel cannot see (I-03/I-86), so the
        lookup is incomplete and the item fails closed rather than guessing."""
        self._withheld(provenance=["agent.generated"], trust=int(Trust.MEDIUM),
                       classification=int(Classification.INTERNAL),
                       delegation_ancestry=["tr-ancestor"],
                       creating_authority="tr-child")

    def test_11_a_legacy_row_is_withheld_and_never_backfilled(self):
        """The ordinary case of all the above. No assumed `james.stated`, no
        invented authority -- and the row is NOT modified by being read."""
        self.seed_raw("legacy", MARKER)
        prompt = self.prompt_after_a_turn()
        self.assertNotIn(MARKER, prompt)
        self.assertEqual([(None, None, None, None, None)],
                         self.sql("SELECT provenance, trust, classification,"
                                  " delegation_ancestry, creating_authority"
                                  " FROM item WHERE item_ref='legacy'"),
                         "reading a legacy row backfilled it")

    # =======================================================================
    # 12-15 -- revocation, and its durability
    # =======================================================================

    def test_12_a_revoked_creating_authority_withholds(self):
        token = self.write_through_the_real_path()
        self.assertIn(MARKER, self.prompt_after_a_turn(),
                      "the control failed: the item never reached the model")

        self.revocations.revoke(self.token(), token.trace_id, revoked_by="james")
        self.assertNotIn(MARKER, self.prompt_after_a_turn(),
                         "a revoked authority's item still reached the model")

    def test_13_revocation_survives_restart(self):
        """The whole reason the registry is durable. A fresh ContextService --
        an empty in-memory revoked set, exactly as after a restart -- must
        still withhold, because the TABLE is the authority."""
        token = self.write_through_the_real_path()
        self.revocations.revoke(self.token(), token.trace_id, revoked_by="james")

        self.context = ContextService(self.tree, secret=b"i111-suite-key")
        self.boundary = DataAccessBoundary(db.app_dsn(), self.context)
        self.conversation = ConversationService(
            self.gateway, self.pdp, self.boundary, self.approvals,
            budget=self.budget)
        self.assertEqual(set(), self.context._revoked,
                         "the fixture did not actually simulate a restart")

        prompt = self.prompt_after_a_turn()
        self.assertNotIn(MARKER, prompt,
                         "revocation did not survive restart")

    def test_14_deleting_the_item_does_not_erase_the_revocation(self):
        """Revocation is AUTHORITY state, not item lineage (ADR 0013). An
        authority must not become clean because its output was deleted."""
        token = self.write_through_the_real_path()
        self.revocations.revoke(self.token(), token.trace_id, revoked_by="james")
        self.sql("DELETE FROM item WHERE item_ref='it-1'")
        self.assertEqual([(1,)],
                         self.sql("SELECT count(*) FROM authority_revocation"
                                  " WHERE execution_identity=%s", (token.trace_id,)))

    def test_15_the_application_role_cannot_delete_a_revocation(self):
        """Enforced by PRIVILEGE, not by the application declining to ask.
        This registry signals by presence, so a DELETE would turn a revoked
        authority back into a clean one."""
        granted = {r[0] for r in self.sql(
            "SELECT privilege_type FROM information_schema.role_table_grants"
            " WHERE grantee='nova_app' AND table_name='authority_revocation'")}
        self.assertEqual({"SELECT", "INSERT"}, granted,
                         "nova_app holds more than append-only on the registry")

    # =======================================================================
    # 16-20 -- what must not have changed
    # =======================================================================

    def test_16_restored_taint_reaches_the_model_request(self):
        """The defect this suite exists for, asserted as BEHAVIOUR rather than
        as the absence of a string in the source.

        A note stored as `external.web` at LOW trust must arrive at the model
        request as LOW. If the read path synthesized `james.stated` -- as it
        used to -- this block would be HIGHEST, and `I-100`'s untrusted-derived
        ceiling would be evaluated against a trust level nothing ever earned.

        The union also drags the WHOLE block down: the block is a derivation of
        its inputs (I-99), so one untrusted note taints the context it is part
        of. That is the intended behaviour, not a rounding error."""
        self.seed_raw("web", "something off the internet",
                      provenance=["external.web"], trust=int(Trust.LOW),
                      classification=int(Classification.INTERNAL),
                      delegation_ancestry=[], creating_authority="tr-web")
        token = self.context.issue_root(identity="james", actor="james",
                                        scope_path=LIFE,
                                        rights=frozenset({"read"}),
                                        ceiling=Risk.READ, ttl=60)
        _text, taint = self.conversation._scope_context(token, LIFE)

        self.assertEqual(Trust.LOW, taint.trust,
                         "the read path raised trust above what was persisted")
        self.assertIn("external.web", taint.provenance,
                      "persisted provenance did not reach the model request")

    def test_16b_an_empty_scope_does_not_borrow_trust_from_nothing(self):
        """The base case, so 16's union cannot pass by accident: with no items
        the block carries NOVA's own reading of its own records."""
        token = self.context.issue_root(identity="james", actor="james",
                                        scope_path=LIFE,
                                        rights=frozenset({"read"}),
                                        ceiling=Risk.READ, ttl=60)
        _text, taint = self.conversation._scope_context(token, LIFE)
        self.assertEqual(Trust.HIGHEST, taint.trust)
        self.assertEqual(frozenset({"james.stated"}), taint.provenance)

    def test_17_a_client_cannot_supply_authoritative_security_metadata(self):
        """The write path takes the security state from the PLAN, which is what
        authorization was decided against -- never from the payload."""
        token = self.token()
        approval_id = self.approvals.propose(token, LIFE, "hostile", "body")
        self.approvals.decide(token, approval_id, True, decided_by="james")
        self.assertEqual([(["james.stated"], int(Trust.HIGHEST))],
                         self.sql("SELECT provenance, trust FROM item"
                                  " WHERE item_ref='hostile'"))

    def test_18_scope_isolation_still_holds_for_the_new_columns(self):
        """The security state is on a scoped row, so RLS governs it like the
        body. A sibling's provenance is as unreachable as its content."""
        self.seed_raw("elsewhere", "business body", scope=BUSINESS,
                      provenance=["james.stated"], trust=int(Trust.HIGHEST),
                      classification=int(Classification.INTERNAL),
                      delegation_ancestry=[], creating_authority="tr-b")
        token = self.context.issue_root(identity="james", actor="james",
                                        scope_path=LIFE, rights=frozenset({"read"}),
                                        ceiling=Risk.READ, ttl=60)
        self.pdp.authorize_data_read(token, LIFE)
        with self.boundary.open(token) as ch:
            rows = ch.fetch("SELECT item_ref, provenance FROM item")
        self.assertEqual([], [r for r in rows if r[0] == "elsewhere"])

    def test_19_the_revocation_registry_is_scope_isolated(self):
        """No unrelated-authority enumeration: the registry is a scoped table
        under the same policy, so a scope sees only its own revocations."""
        self.revocations.revoke(
            self.context.issue_root(identity="james", actor="james",
                                    scope_path=BUSINESS, rights=frozenset({"write"}),
                                    ceiling=Risk.EXECUTE, ttl=60),
            "tr-business", revoked_by="james")
        token = self.token(LIFE)
        with self.boundary.open(token) as ch:
            seen = ch.fetch("SELECT execution_identity FROM authority_revocation")
        self.assertEqual([], seen, "a sibling scope's revocations were visible")

    def test_20_the_withheld_item_is_still_visible_on_the_page(self):
        """Fail-closed applies to MODEL CONTEXT, not to James's own eyes. The
        UI path is unchanged -- he can still see what he wrote."""
        self.seed_raw("legacy", MARKER)
        status, page = self.seam.scope_page(self.sid, LIFE)
        self.assertEqual(200, status)
        self.assertIn(MARKER, page, "fail-closed leaked into the UI path")


if __name__ == "__main__":
    unittest.main()
