"""Test fixture: one scope, one agent, one tool, one integration.

Deliberately minimal. Everything here represents James acting (creating
scopes, creating grants, registering definitions) -- the operations I-10 and
the C1/C2/C3 model reserve to him.
"""

from __future__ import annotations

import os
import shutil
import tempfile

from ..agent.registry import AgentDefinition, AgentRegistry
from ..core.audit import AuditWriter
from ..core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ..core.capability import CapabilityLayer, IntegrationRecord
from ..core.context_service import ContextService
from ..core.policy import PolicyDecisionPoint
from ..core.scope_tree import ScopeTree
from ..core.store import StoreRegistry
from ..core.types import ArgumentEnvelope, Risk
from ..integrations.local_echo import LocalEchoIntegration
from ..runtime import Runtime
from ..tools.pep import ToolPEP
from ..tools.registry import CONSEQUENCE, EXPRESSIVE, ToolDefinition, ToolRegistry

SCOPE_A = "/business/KAIRO/client-a"
SCOPE_B = "/business/KAIRO/client-b"
TOOL = "send_message"
TOOL_VERSION = "1.0.0"


def build(mode: str = "success", enforces_dedup: bool = False):
    tmp = tempfile.mkdtemp(prefix="nova-slice-")

    tree = ScopeTree()
    tree.add_scope("/business", "domain")
    tree.add_scope("/business/KAIRO", "business")
    tree.add_scope(SCOPE_A, "client")
    tree.add_scope(SCOPE_B, "client")

    # I-10: only James creates grants.
    tree.james_grants("james", "send", "*", SCOPE_A, Risk.EXECUTE)
    tree.james_grants("james", "read", "*", SCOPE_A, Risk.READ)

    stores = StoreRegistry(os.path.join(tmp, "data"))
    audit = AuditWriter(stores)
    context = ContextService(tree, secret=os.urandom(32))
    pdp = PolicyDecisionPoint(tree, context, audit)

    secrets = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
    broker = CredentialBroker(tree, secrets, audit)
    broker.register(
        CredentialBinding(binding_id="cred-a", scope_path=SCOPE_A,
                          permitted_operations=frozenset({"send"})),
        secret="test-token-" + os.urandom(4).hex(),
    )

    capability = CapabilityLayer()
    integration = LocalEchoIntegration("acme-mail", "acct-a", "https://acme/v1",
                                       "2024-01", mode=mode, enforces_dedup=enforces_dedup)
    capability.bind(TOOL, SCOPE_A, IntegrationRecord(
        integration_id="int-a", scope_path=SCOPE_A, provider="acme-mail",
        account="acct-a", endpoint="https://acme/v1", api_version="2024-01",
        credential_binding_id="cred-a"))

    tools = ToolRegistry()
    tools.register(ToolDefinition(
        name=TOOL, version=TOOL_VERSION, purpose="Send one message",
        input_schema={"to": "str", "body": "str", "payload": {"cc": "str"}},
        output_schema={"status": "str"},
        required_rights=frozenset({"send"}),
        auth_requirements="mail-integration",
        risk_class=Risk.EXECUTE,
        context_requirements=frozenset({"client"}),
        error_behaviour="typed", audit_behaviour="reference-only",
        idempotent=False, cost_profile=1,
        consequence_determining={
            "to": CONSEQUENCE,
            "body": EXPRESSIVE,          # prose -- MT-5 says expressive
            "payload.cc": CONSEQUENCE,   # a leaf inside a structured argument
        },
    ))

    pep = ToolPEP(tools, broker, context, audit)

    agents = AgentRegistry()
    agents.register(AgentDefinition(
        name="messenger", purpose="send client messages",
        responsibilities=("send one message",),
        non_responsibilities=("never contact another client",),
        allowed_context=SCOPE_A,
        allowed_tools=frozenset({TOOL}),
        permissions=frozenset({"send", "read"}),
        inputs=("objective",), outputs=("outcome",),
        success_criteria=("provider accepted",),
        failure_conditions=("provider refused",),
        escalation_rules=("escalate to James",),
        risk_ceiling=Risk.EXECUTE,
    ))

    rt = Runtime(tree, context, pdp, capability, tools, pep, broker, audit, agents, stores)
    return rt, integration, secrets, tmp


def envelope(recipients=("client-a@example.com",), cc=("cc-ok@example.com",), max_size=1):
    """MT-8: an envelope, not a literal."""
    return ArgumentEnvelope(
        allowed_values={"to": frozenset(recipients), "payload.cc": frozenset(cc)},
        magnitude_ceilings={"recipients": max_size},
    )


def cleanup(rt: Runtime, tmp: str) -> None:
    rt.stores.close()
    shutil.rmtree(tmp, ignore_errors=True)
