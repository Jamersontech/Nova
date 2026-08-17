"""Tool definitions and the registry.

TOOL_AND_INTEGRATION_ARCHITECTURE.md section 2. A tool is defined ONCE at
root; its integration and credential binding are per scope (section 1).

ADR 0036 (Proposed) -- declaration totality:
  1. The consequence-determining declaration must classify EVERY LEAF the
     input schema exposes. An unmentioned argument makes the definition
     incomplete, and an incomplete definition IS NOT REGISTERED (MT-6).
  2. The default is CONSEQUENCE-DETERMINING, not expressive.
  3. A structured argument cannot be expressive by aggregation.
  4. A schema change re-opens the question.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from ..core.types import Denied, Risk


CONSEQUENCE = "consequence-determining"
EXPRESSIVE = "expressive"


@dataclass(frozen=True)
class ToolDefinition:
    """The thirteen declared fields, plus Section 05's fourteenth."""
    name: str
    version: str
    purpose: str
    input_schema: dict[str, Any]              # leaf name -> type, or nested dict
    output_schema: dict[str, str]
    required_rights: frozenset[str]
    auth_requirements: str
    risk_class: Risk
    context_requirements: frozenset[str]
    error_behaviour: str
    audit_behaviour: str
    idempotent: Optional[bool]                # None => NOT idempotent (ADR 0036 rule 3)
    cost_profile: int
    consequence_determining: dict[str, str]   # leaf path -> CONSEQUENCE | EXPRESSIVE

    def leaves(self) -> set[str]:
        """Every leaf the schema exposes, dotted. ADR 0036: totality reaches
        every leaf, not only top-level arguments."""
        out: set[str] = set()

        def walk(node: Any, prefix: str) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{prefix}.{k}" if prefix else k)
            else:
                out.add(prefix)

        walk(self.input_schema, "")
        return out

    def is_consequence_determining(self, leaf: str) -> bool:
        """ADR 0036 rule 2: present-but-unclassified, or unparseable, is
        CONSEQUENCE-DETERMINING. Expressive is the exception that must be
        declared."""
        declared = self.consequence_determining.get(leaf)
        if declared == EXPRESSIVE:
            return False
        return True   # includes declared==CONSEQUENCE and declared is None

    def retry_is_safe(self, provider_enforces_dedup: bool) -> bool:
        """ADR 0036 rule 3: an absent idempotency claim means NOT idempotent.
        ADR 0037: and the guarantee belongs to the PROVIDER, not the tool."""
        if self.idempotent is not True:
            return False
        return provider_enforces_dedup


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """MT-6 / ADR 0036: an incomplete definition is NOT REGISTERED. This
        is a refusal, not a warning."""
        if tool.risk_class is None:
            raise Denied("tool.register", "no risk class declared", "I-101", True)
        if not tool.required_rights:
            raise Denied("tool.register", "no required rights declared", "ADR-0036", True)

        leaves = tool.leaves()
        unclassified = leaves - set(tool.consequence_determining)
        if unclassified:
            # Rule 1: totality. The default in rule 2 governs how an
            # unclassified argument is TREATED at call time; registration
            # still refuses, because silence must not be a way to author a
            # definition without deciding.
            raise Denied("tool.register",
                         f"declaration not total; unclassified leaves: {sorted(unclassified)}",
                         "ADR-0036/MT-6", True)

        stray = set(tool.consequence_determining) - leaves
        if stray:
            raise Denied("tool.register",
                         f"declaration names leaves absent from schema: {sorted(stray)}",
                         "ADR-0036", True)

        for leaf, value in tool.consequence_determining.items():
            if value not in (CONSEQUENCE, EXPRESSIVE):
                raise Denied("tool.register",
                             f"unparseable classification for {leaf}", "ADR-0036", True)

        self._tools[f"{tool.name}@{tool.version}"] = tool

    def get(self, name: str, version: str) -> ToolDefinition:
        key = f"{name}@{version}"
        if key not in self._tools:
            raise Denied("tool.lookup", f"tool {key} not registered", "I-14", True)
        return self._tools[key]

    def is_registered(self, name: str, version: str) -> bool:
        return f"{name}@{version}" in self._tools
