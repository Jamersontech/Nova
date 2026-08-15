"""The capability layer -- binding resolution.

I-114(a): the execution binding is RESOLVED BEFORE the authorization decision
and is an input to it. An action whose binding cannot be resolved is DENIED,
never executed against a default or a last-known binding.

TOOL_AND_INTEGRATION_ARCHITECTURE.md section 1: one tool, many bindings. The
tool is defined once at root; the integration and credential are per scope.

I-114(d): there is NO binding substitution and NO provider equivalence. This
module deliberately offers no fallback, no "equivalent provider" lookup, and
no default. An unresolvable binding raises.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Denied, ExecutionBinding


@dataclass(frozen=True)
class IntegrationRecord:
    """I-114(c): identity is consequence-bearing. Changing provider, account,
    endpoint or api_version produces a DIFFERENT binding, not the same binding
    reconfigured."""
    integration_id: str
    scope_path: str
    provider: str
    account: str
    endpoint: str
    api_version: str
    credential_binding_id: str


class CapabilityLayer:
    def __init__(self) -> None:
        # (tool_name, scope_path) -> integration
        self._bindings: dict[tuple[str, str], IntegrationRecord] = {}

    def bind(self, tool_name: str, scope_path: str, record: IntegrationRecord) -> None:
        self._bindings[(tool_name, scope_path)] = record

    def rebind(self, tool_name: str, scope_path: str, record: IntegrationRecord) -> None:
        """Repointing. I-114(c) makes this produce a DIFFERENT binding
        identity, which is what invalidates authorizations naming the old one."""
        self._bindings[(tool_name, scope_path)] = record

    def resolve(self, tool_name: str, tool_version: str, scope_path: str) -> ExecutionBinding:
        rec = self._bindings.get((tool_name, scope_path))
        if rec is None:
            # I-114(a) / I-14: unresolvable is a DENIAL. There is deliberately
            # no walk up the scope tree to find an ancestor's binding, and no
            # default -- either would silently change which provider acts.
            raise Denied("capability.resolve",
                         f"no binding for {tool_name} in {scope_path}", "I-114", True)
        return ExecutionBinding(
            tool_name=tool_name,
            tool_version=tool_version,
            integration_id=rec.integration_id,
            provider=rec.provider,
            account=rec.account,
            endpoint=rec.endpoint,
            api_version=rec.api_version,
            credential_binding_id=rec.credential_binding_id,
            scope_path=scope_path,
        )
