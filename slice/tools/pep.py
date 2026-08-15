"""The Tool call Policy Enforcement Point.

One of the six PEPs (PERMISSION_ARCHITECTURE.md section 2). This is where:

  I-100 / MT-5-MT-9  every consequence-determining argument is checked against
                     the envelope the authorization fixed
  I-114(b)           the RESOLVED binding is checked against the authorized
                     binding envelope
  I-109              the authorization's ten-property binding is re-checked
                     against current state before execution
  MT-7               three outcomes and only three:
                       covered                    -> proceed
                       not covered                -> deny + security event
                       covered but untrusted-derived -> PREPARE ceiling

The tool NEVER self-authorizes: nothing in integrations/ is reachable except
through this module, and this module holds no credential.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ..core.audit import AuditWriter
from ..core.broker import CredentialBroker
from ..core.context_service import ContextService
from ..core.types import (Authorization, ContextToken, Denied, ExecutionBinding,
                          Outcome, Plan, PlanStep, Risk, Taint)
from .registry import ToolRegistry


class ToolPEP:
    def __init__(self, registry: ToolRegistry, broker: CredentialBroker,
                 context: ContextService, audit: AuditWriter):
        self._registry = registry
        self._broker = broker
        self._context = context
        self._audit = audit

    def invoke(self, token: ContextToken, plan: Plan, step: PlanStep,
               authorization: Authorization,
               resolve_binding: Callable[[str, str], ExecutionBinding],
               transport: Callable[[dict[str, Any], str], Outcome],
               tool_version: str,
               provider_enforces_dedup: bool = False) -> Outcome:

        # ---- context is re-verified at every enforcement point ------------
        # V-2: an execution holding a revoked token fails closed HERE, at its
        # next enforcement point -- not at the moment of revocation.
        self._context.verify(token)

        # ---- the plan must be the one that was authorized (I-112) ---------
        if plan.identity() != authorization.plan_identity:
            self._deny(token, "pep.plan", "plan identity differs from the authorized plan",
                       "I-112", True)

        # ---- tool must be in the authorized tool set (I-113 envelope) -----
        if step.tool_name not in authorization.tool_set:
            self._deny(token, "pep.toolset", f"{step.tool_name} outside authorized tool set",
                       "I-113", True)

        tool = self._registry.get(step.tool_name, tool_version)

        # ---- I-114(b): RE-RESOLVE the binding, then check it --------------
        # Re-resolved per attempt, not carried from the authorization: a
        # retry, resumption or failover is a fresh CHOICE of substrate, and a
        # second choice is not covered by the first decision.
        binding = resolve_binding(step.tool_name, token.scope_path)
        if binding.identity() not in authorization.binding_envelope:
            self._deny(token, "pep.binding", "resolved binding outside authorized envelope",
                       "I-114", True)

        # ---- I-109: the ten bound properties must still hold --------------
        # Re-checked against CURRENT state before the step runs.
        if authorization.scope_path != token.scope_path:
            self._deny(token, "pep.i109", "scope changed since authorization", "I-109", True)
        if authorization.risk_ceiling > token.risk_ceiling:
            self._deny(token, "pep.i109", "risk ceiling no longer covered by token",
                       "I-109", True)
        if not authorization.effective_rights <= token.granted_rights:
            self._deny(token, "pep.i109", "effective rights changed since authorization",
                       "I-109", True)

        # ---- I-100 / MT-5: consequence-determining arguments --------------
        ceiling_applies = False
        for leaf, value in _flatten(step.arguments):
            if not tool.is_consequence_determining(leaf):
                continue    # expressive: the envelope does not police prose
            if not authorization.argument_envelope.covers(leaf, value):
                # MT-7 row 2: a boundary violation, recorded as a SECURITY
                # EVENT, not a retryable error.
                self._deny(token, "pep.argument",
                           f"argument {leaf}={value!r} outside envelope", "I-100", True)
            # MT-7 row 3: covered but untrusted-derived -> PREPARE ceiling.
            if plan.taint.is_untrusted_derived():
                ceiling_applies = True

        if ceiling_applies and tool.risk_class > Risk.PREPARE and authorization.approval_id is None:
            self._deny(token, "pep.taint",
                       "untrusted-derived argument cannot execute above PREPARE without approval",
                       "I-40", True)

        # ---- execute through the broker; the PEP never holds a secret -----
        result = self._broker.inject_and_call(
            token=token, binding=binding, authorization=authorization,
            operation=step.action, payload=dict(step.arguments), transport=transport,
        )

        # ---- I-99 / I-111: the result is a derivation and carries taint ---
        # integration.supplied, unioned with the plan's taint. Trust is the
        # LOWEST among them; classification the STRICTEST.
        result.taint = Taint.union(plan.taint, Taint.of("integration.supplied",
                                                        plan.taint.classification))

        self._audit.execution(
            token.scope_path, token.trace_id, "external_transmission",
            f"tool={step.tool_name}@{tool.version} binding={binding.identity()} "
            f"envelope={authorization.binding_identity()} outcome={result.state}",
        )
        return result

    def _deny(self, token: ContextToken, step: str, reason: str,
              invariant: str, security_event: bool = False) -> None:
        d = Denied(step, reason, invariant, security_event)
        try:
            self._audit.decision(token.scope_path, token.trace_id, "deny",
                                 f"step={d.step} reason={d.reason} inv={d.invariant}")
        except Denied:
            pass
        raise d


def _flatten(args: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    """Leaf paths, matching ToolDefinition.leaves(). A structured argument is
    checked leaf by leaf -- it cannot be expressive by aggregation."""
    out: list[tuple[str, Any]] = []
    for k, v in args.items():
        path = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            out.extend(_flatten(v, path))
        else:
            out.append((path, v))
    return out
