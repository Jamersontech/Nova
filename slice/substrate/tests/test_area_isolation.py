"""Cross-AREA isolation, with data actually present in every area.

`test_conversation.test_04` already proves a sibling client's data cannot
reach the model. It proves it between two clients under one business
(`/business/KAIRO/client-a` and `-b`). This suite makes the same claim at the
level James actually lives at -- the three top-level areas of
USER_INTERFACE_ARCHITECTURE section 2 -- and, more importantly, makes it
NON-VACUOUSLY: the real-provider validation of 2026-08-20 satisfied "no
sibling data leaked" against three EMPTY areas, which is true and worth
nothing. Here every area holds a distinct marker, so an isolation failure has
something to leak.

The claim is deliberately NOT "the prompt was assembled carefully". It is:

    the channel that gathered the context is bound to /life, so /business and
    /wealth rows are unreachable BELOW the query layer (RLS, ADR 0016), and
    therefore CANNOT appear in the prompt regardless of how it is built

The transport is the same double `test_conversation` uses, standing where
RealAnthropicTransport stands under PRODUCTION's provider name, model id and
profile. No provider request leaves this process; the assertion is on what
reached the egress boundary, which is the deterministic thing worth asserting.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_area_isolation
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

LIFE = "/life"
BUSINESS = "/business"
WEALTH = "/wealth"

# The production seeding, exactly: app.DEFAULT_SCOPES / DEFAULT_GRANTS.
SCOPES = [(LIFE, "domain", None),
          (BUSINESS, "domain", None),
          (WEALTH, "domain", None)]
GRANTS = [("james", path, right)
          for path, _, _ in SCOPES
          for right in ("read", "write")]

# Harmless, and chosen so a partial or fuzzy leak still fails the assertion:
# no marker is a substring of another and none occurs in NOVA's own prompt text.
LIFE_MARKER = "MARKER-LIFE-dentist-thursday"
BUSINESS_MARKER = "MARKER-BUSINESS-invoice-numbering"
WEALTH_MARKER = "MARKER-WEALTH-isa-allowance"

CRED_REF = "control-plane/anthropic"


class ScriptedTransport:
    """Stands where RealAnthropicTransport stands. Records what reached the
    egress boundary; replies with whatever the test scripted."""

    def __init__(self):
        self.replies: list[str] = []
        self.prompts: list[str] = []
        self.credential_refs: list[str] = []

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        self.prompts.append(prompt)
        self.credential_refs.append(credential_ref)
        text = self.replies.pop(0) if self.replies else "Nothing is pending here."
        return ModelResponse(text=text,
                             taint=Taint.of("model.generated", Classification.INTERNAL))


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class AreaIsolationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        db.reset_data()
        tree_store.seed(SCOPES, GRANTS)
        self.tree = tree_store.load_tree()

        tmp = tempfile.mkdtemp(prefix="nova-area-isolation-")
        self.context = ContextService(self.tree, secret=b"area-isolation-suite-key")
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

        # Every area holds something. This is the whole point of the suite.
        self.seed_item(LIFE, "life-note", LIFE_MARKER)
        self.seed_item(BUSINESS, "business-note", BUSINESS_MARKER)
        self.seed_item(WEALTH, "wealth-note", WEALTH_MARKER)

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

    def read_token(self, scope_path):
        # `Risk.READ`, which is what this suite's production seeding actually
        # confers for the `read` right -- and what every production read path
        # asks for. This said `ANALYZE` before issuance enforced the grant
        # ceiling (I-07/I-106), which no grant here permits. A read is the
        # lowest class, so every assertion below is unaffected.
        return self.context.issue_root(identity="james", actor="james",
                                       scope_path=scope_path,
                                       rights=frozenset({"read"}),
                                       ceiling=Risk.READ, ttl=60)

    # =======================================================================
    # 1 -- the three areas are genuinely populated
    # =======================================================================

    def test_01_every_area_holds_its_marker(self):
        """The control that makes the rest of this suite mean anything. If
        this fails, a passing isolation assertion below proves only that the
        database is empty -- which is exactly the weakness of the 2026-08-20
        real-provider run this suite exists to correct."""
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute("SELECT scope_path, body FROM item ORDER BY scope_path")
            rows = cur.fetchall()
        conn.close()
        self.assertEqual([(BUSINESS, BUSINESS_MARKER),
                          (LIFE, LIFE_MARKER),
                          (WEALTH, WEALTH_MARKER)], rows)

    # =======================================================================
    # 2 -- what reaches the model carries one area and no other
    # =======================================================================

    def test_02_the_model_sees_life_and_neither_sibling_area(self):
        """One read-only turn in /life, with /business and /wealth populated.
        The assertion is on the prompt at the egress boundary -- the last
        point before the request would leave the process."""
        status, _ = self.seam.talk_post(self.sid, LIFE, "what is here?")
        self.assertEqual(200, status)
        self.assertEqual(1, len(self.transport.prompts),
                         "expected exactly one turn to reach the egress boundary")

        prompt = self.transport.prompts[0]
        self.assertIn(LIFE_MARKER, prompt,
                      "the authorized area's own data did not reach the model")
        self.assertIn(LIFE, prompt)
        self.assertNotIn(BUSINESS_MARKER, prompt,
                         "/business data reached the model during a /life turn")
        self.assertNotIn(WEALTH_MARKER, prompt,
                         "/wealth data reached the model during a /life turn")

    def test_03_the_transport_receives_a_reference_not_a_secret(self):
        """Unchanged claim, re-asserted here because this suite is the one
        that populates every area: a fuller database must not change what the
        transport is handed."""
        self.seam.talk_post(self.sid, LIFE, "what is here?")
        self.assertEqual([CRED_REF], self.transport.credential_refs)

    # =======================================================================
    # 4-5 -- the exclusion is structural, not prompt discipline
    # =======================================================================

    def test_04_a_life_bound_channel_cannot_read_business_rows(self):
        """Below the query layer (ADR 0016). The query names no scope at all;
        RLS decides. A /life-bound channel issuing an unfiltered SELECT over a
        table that demonstrably holds all three areas' rows sees exactly one."""
        token = self.read_token(LIFE)
        self.pdp.authorize_data_read(token, LIFE)
        with self.boundary.open(token) as ch:
            bodies = [b for (b,) in ch.fetch("SELECT body FROM item")]
        self.assertEqual([LIFE_MARKER], bodies,
                         "a /life-bound channel returned another area's rows")

    def test_05_a_life_token_cannot_gather_business_context(self):
        """The Data Access PEP refuses before any channel opens: a token
        issued for /life naming /business as the resource is denied by
        containment, not filtered to nothing."""
        token = self.read_token(LIFE)
        for foreign in (BUSINESS, WEALTH):
            with self.assertRaises(Denied):
                self.conversation._scope_context(token, foreign)
        self.assertEqual([], self.transport.prompts,
                         "a denied context gather still produced a model call")


if __name__ == "__main__":
    unittest.main()
