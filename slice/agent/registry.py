"""Agent definitions.

AGENT_ARCHITECTURE.md section 2 / ai/AGENT_PRINCIPLES.md section 2: thirteen
required fields. The runtime REFUSES to instantiate an agent whose definition
is incomplete -- enforced, not advisory.

Three fields carry weight at runtime:
  Allowed Context -- the maximum scope an instance may EVER hold
  Allowed Tools   -- a CLOSED list; a tool not named cannot be called even if
                     it exists and the context would permit it
  Permissions     -- with Allowed Context and Allowed Tools, this is what
                     I-106 verifies at token issuance
"""

from __future__ import annotations

from dataclasses import dataclass

from ..core.types import Denied, Risk

REQUIRED_FIELDS = (
    "name", "purpose", "responsibilities", "non_responsibilities",
    "allowed_context", "allowed_tools", "permissions", "inputs", "outputs",
    "success_criteria", "failure_conditions", "escalation_rules", "risk_ceiling",
)


@dataclass(frozen=True)
class AgentDefinition:
    name: str
    purpose: str
    responsibilities: tuple[str, ...]
    non_responsibilities: tuple[str, ...]
    allowed_context: str
    allowed_tools: frozenset[str]
    permissions: frozenset[str]
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]
    success_criteria: tuple[str, ...]
    failure_conditions: tuple[str, ...]
    escalation_rules: tuple[str, ...]
    risk_ceiling: Risk


class AgentRegistry:
    def __init__(self) -> None:
        self._agents: dict[str, AgentDefinition] = {}

    def register(self, agent: AgentDefinition) -> None:
        for f in REQUIRED_FIELDS:
            value = getattr(agent, f, None)
            if value is None or (hasattr(value, "__len__") and len(value) == 0):
                raise Denied("agent.register", f"incomplete definition: {f} missing",
                             "AGENT_ARCHITECTURE-2", True)
        self._agents[agent.name] = agent

    def get(self, name: str) -> AgentDefinition:
        if name not in self._agents:
            raise Denied("agent.lookup", f"agent {name} not registered", "I-14", True)
        return self._agents[name]
