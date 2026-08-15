"""Second-slice fixture: two agents, delegation, and a model gateway.

Agent A (`coordinator`) — broader authority, may delegate.
Agent B (`researcher`) — narrower, receives only what A delegates.

Reuses the first slice's harness for everything already validated; this adds
only what slice 2 exercises.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time

from ..agent.registry import AgentDefinition, AgentRegistry
from ..core.audit import AuditWriter
from ..core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ..core.capability import CapabilityLayer, IntegrationRecord
from ..core.context_service import ContextService
from ..core.delegation import Delegation
from ..core.gateway import (CapabilityProfile, ModelGateway, ModelRequestItem,
                            ProviderBinding)
from ..core.policy import PolicyDecisionPoint
from ..core.scope_tree import ScopeTree
from ..core.store import StoreRegistry
from ..core.types import Classification, Risk, Taint
from ..models.local_provider import LocalModelProvider
from ..runtime import Runtime
from ..tools.pep import ToolPEP
from ..tools.registry import CONSEQUENCE, EXPRESSIVE, ToolDefinition, ToolRegistry

SCOPE_A = "/business/KAIRO/client-a"
SCOPE_A_SUB = "/business/KAIRO/client-a/research"
SCOPE_B = "/business/KAIRO/client-b"
TOOL = "send_message"
TOOL_VERSION = "1.0.0"

PROFILE = CapabilityProfile(
    name="research-profile",
    permitted_providers=frozenset({"acme-llm"}),
    permitted_models=frozenset({"acme-small"}),
)
# I-97: an empty permitted set fails closed. Used to test that directly.
EMPTY_PROFILE = CapabilityProfile(name="no-providers")


def build(model_behaviour: str = "normal"):
    tmp = tempfile.mkdtemp(prefix="nova-slice2-")

    tree = ScopeTree()
    for p, k in (("/business", "domain"), ("/business/KAIRO", "business"),
                 (SCOPE_A, "client"), (SCOPE_A_SUB, "project"), (SCOPE_B, "client")):
        tree.add_scope(p, k)

    # I-10: only James creates grants.
    for scope in (SCOPE_A, SCOPE_A_SUB):
        tree.james_grants("james", "send", "*", scope, Risk.EXECUTE)
        tree.james_grants("james", "read", "*", scope, Risk.READ)
        tree.james_grants("james", "research", "*", scope, Risk.ANALYZE)

    stores = StoreRegistry(os.path.join(tmp, "data"))
    audit = AuditWriter(stores)
    context = ContextService(tree, secret=os.urandom(32))
    pdp = PolicyDecisionPoint(tree, context, audit)

    secrets = SecretsStore(os.path.join(tmp, "secrets", "vault.json"))
    broker = CredentialBroker(tree, secrets, audit)
    broker.register(
        CredentialBinding(binding_id="cred-a", scope_path=SCOPE_A,
                          permitted_operations=frozenset({"send"})),
        secret="test-token-" + os.urandom(4).hex())

    capability = CapabilityLayer()
    capability.bind(TOOL, SCOPE_A, IntegrationRecord(
        integration_id="int-a", scope_path=SCOPE_A, provider="acme-mail",
        account="acct-a", endpoint="https://acme/v1", api_version="2024-01",
        credential_binding_id="cred-a"))

    tools = ToolRegistry()
    tools.register(ToolDefinition(
        name=TOOL, version=TOOL_VERSION, purpose="Send one message",
        input_schema={"to": "str", "body": "str", "payload": {"cc": "str"}},
        output_schema={"status": "str"},
        required_rights=frozenset({"send"}), auth_requirements="mail-integration",
        risk_class=Risk.EXECUTE, context_requirements=frozenset({"client"}),
        error_behaviour="typed", audit_behaviour="reference-only",
        idempotent=False, cost_profile=1,
        consequence_determining={"to": CONSEQUENCE, "body": EXPRESSIVE,
                                 "payload.cc": CONSEQUENCE}))

    pep = ToolPEP(tools, broker, context, audit)

    agents = AgentRegistry()
    # -- Agent A: broader, may delegate --------------------------------------
    agents.register(AgentDefinition(
        name="coordinator", purpose="coordinate client work",
        responsibilities=("plan and delegate",),
        non_responsibilities=("never act in another client's scope",),
        allowed_context=SCOPE_A,
        allowed_tools=frozenset({TOOL}),
        permissions=frozenset({"send", "read", "research"}),
        inputs=("objective",), outputs=("result",),
        success_criteria=("objective met",), failure_conditions=("blocked",),
        escalation_rules=("escalate to James",), risk_ceiling=Risk.EXECUTE))
    # -- Agent B: narrower. Its DEFINITION caps it independently of the
    #    delegation -- I-07's intersection has both inputs.
    agents.register(AgentDefinition(
        name="researcher", purpose="research a narrow question",
        responsibilities=("read and summarise",),
        non_responsibilities=("never send", "never delegate"),
        allowed_context=SCOPE_A_SUB,
        allowed_tools=frozenset(),          # closed list: NO tools
        permissions=frozenset({"read", "research"}),
        inputs=("question",), outputs=("summary",),
        success_criteria=("question answered",), failure_conditions=("no sources",),
        escalation_rules=("escalate to coordinator",), risk_ceiling=Risk.ANALYZE))

    # -- Model gateway --------------------------------------------------------
    gateway = ModelGateway(lambda: pdp.available, context, audit)
    provider = LocalModelProvider("acme-llm", "acme-small", behaviour=model_behaviour)
    gateway.register_provider(
        ProviderBinding(provider="acme-llm", model="acme-small",
                        endpoint="https://acme-llm/v1", api_version="2024-05",
                        credential_ref="control-plane/acme-llm"),
        provider.transport)
    # A second, NOT-permitted provider, so I-97 can be tested against a
    # provider that genuinely exists rather than a typo.
    other = LocalModelProvider("cheap-llm", "unbounded-v9")
    gateway.register_provider(
        ProviderBinding(provider="cheap-llm", model="unbounded-v9",
                        endpoint="https://cheap/v1", api_version="2020-01",
                        credential_ref="control-plane/cheap-llm"),
        other.transport)

    rt = Runtime(tree, context, pdp, capability, tools, pep, broker, audit, agents, stores)
    rt.gateway = gateway
    return rt, gateway, provider, tmp


def coordinator_token(rt, ttl: float = 300.0):
    """Agent A's root token, with its tools and may_redelegate registered."""
    agent = rt.agents.get("coordinator")
    return rt.context.issue_root_tracked(
        identity="james", actor=agent.name, scope_path=SCOPE_A,
        rights=frozenset({"send", "read", "research"}), ceiling=Risk.EXECUTE, ttl=ttl,
        agent_allowed_context=agent.allowed_context,
        agent_allowed_rights=agent.permissions,
        agent_risk_ceiling=agent.risk_ceiling,
        tools=agent.allowed_tools, may_redelegate=True)


def valid_delegation(parent, *, scope=SCOPE_A_SUB, rights=frozenset({"read"}),
                     tools=frozenset(), ceiling=Risk.ANALYZE,
                     delegate="researcher", may_redelegate=False, ttl=60.0):
    """A delegation that is strictly narrower in scope, rights, tools AND
    ceiling, expiring earlier -- AG-7 satisfied several times over."""
    return Delegation(
        delegator=parent.trace_id, delegate=delegate, scope_path=scope,
        rights=rights, tools=tools, risk_ceiling=ceiling,
        expires_at=time.time() + ttl, may_redelegate=may_redelegate,
        ancestry=(), purpose="research a narrow question")


def delegate_to_b(rt, parent, delegation=None):
    d = delegation or valid_delegation(parent)
    b = rt.agents.get("researcher")
    return rt.context.delegate(
        parent, d,
        delegate_allowed_context=b.allowed_context,
        delegate_allowed_tools=b.allowed_tools,
        delegate_permissions=b.permissions,
        delegate_risk_ceiling=b.risk_ceiling)


def items(scope=SCOPE_A_SUB, classification=Classification.CLIENT_CONFIDENTIAL,
          provenance="james.stated", label="brief", content="summarise the tasks"):
    return [ModelRequestItem(label=label, content=content, scope_path=scope,
                             taint=Taint.of(provenance, classification))]


def cleanup(rt, tmp):
    rt.stores.close()
    shutil.rmtree(tmp, ignore_errors=True)
