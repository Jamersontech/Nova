"""The Policy Decision Point.

AUTHORIZATION_MODEL.md section 3, ten steps, evaluated IN ORDER. Any step may
deny; no step may widen. Step 3 before step 5 is deliberate: scope containment
is checked before permissions exist.

Section 11 amendment (ADR 0037, Proposed): the execution binding is RESOLVED
BEFORE the decision and is an INPUT to steps 5-8. The ten steps are unchanged
and unreordered; the PDP does not select the binding -- it receives the
resolved one.

I-17: PDP unavailability is deny. There is no cached-allow fallback.
"""

from __future__ import annotations

import time
from typing import Optional

from .audit import AuditWriter
from .context_service import ContextService
from .scope_tree import ScopeTree
from .types import (Approval, ArgumentEnvelope, Authorization, Classification,
                    ContextToken, Denied, ExecutionBinding, Plan, Risk)

# DATA_CLASSIFICATION.md section 2, "Transmitted externally" row.
# S13-D1: this is what PDP step 7 consults for an outbound action.
TRANSMIT_EXTERNALLY = {
    Classification.PUBLIC: "allow",
    Classification.INTERNAL: "grant",
    Classification.CONFIDENTIAL: "grant",
    Classification.CLIENT_CONFIDENTIAL: "same-client-only",
    Classification.SENSITIVE_PERSONAL: "never",
    Classification.SECURITY_CRITICAL: "never",
}


class PolicyDecisionPoint:
    def __init__(self, tree: ScopeTree, context: ContextService, audit: AuditWriter):
        self._tree = tree
        self._context = context
        self._audit = audit
        self.available = True          # I-17 test hook

    def authorize_plan(self, token: ContextToken, plan: Plan,
                       resolved_bindings: dict[str, ExecutionBinding],
                       argument_envelope: ArgumentEnvelope,
                       cost_ceiling: int,
                       delegation_ancestry: tuple[str, ...] = (),
                       approval: Optional[Approval] = None,
                       is_external_transmission: bool = False) -> Authorization:
        """Runs the ten-step sequence, then fixes the envelope (I-113, I-114(b)).

        `resolved_bindings` maps tool_name -> binding and MUST already be
        resolved: I-114(a) requires the substrate to exist before the decision.
        An empty or missing entry is a denial, never a default.
        """
        if not self.available:
            self._deny(token, "step0.pdp", "PDP unavailable", "I-17")

        # ---- 1. Is the context valid? -----------------------------------
        try:
            self._context.verify(token)
        except Denied as d:
            self._record_denial(token, d)
            raise

        # ---- 2. Is the subject known? -----------------------------------
        if not token.identity or not token.actor:
            self._deny(token, "step2.subject", "unrecognized execution identity", "I-66")

        # ---- 3. Does the token cover the resource's owning scope? --------
        # Before step 5, deliberately: a grant cannot rescue a resource
        # outside the token's scope.
        if not token.covers(plan.scope_path):
            self._deny(token, "step3.scope", f"token does not cover {plan.scope_path}",
                       "I-03", security_event=True)
        for step in plan.steps:
            if not token.covers(step.resource):
                self._deny(token, "step3.scope", f"token does not cover {step.resource}",
                           "I-03", security_event=True)

        # ---- I-114(a): the binding must be resolved and in-scope ---------
        # Placed here because the binding is an INPUT to steps 5-8 below.
        for step in plan.steps:
            binding = resolved_bindings.get(step.tool_name)
            if binding is None:
                self._deny(token, "step3a.binding", f"no binding resolved for {step.tool_name}",
                           "I-114", security_event=True)
            if binding.scope_path != plan.scope_path:
                self._deny(token, "step3a.binding", "binding resolved in a different scope",
                           "I-114", security_event=True)

        # ---- 4. Is there an explicit denial? -----------------------------
        for step in plan.steps:
            if self._tree.explicit_denial(token.identity, step.action, step.resource):
                self._deny(token, "step4.denial", "explicit denial overrides any grant", "I-15")

        # ---- 5. Is there a grant for (subject, action, resource type, scope)?
        effective_rights: set[str] = set()
        for step in plan.steps:
            for right in step.required_rights:
                grant = self._tree.find_grant(token.identity, right, "*", step.resource)
                if grant is None:
                    self._deny(token, "step5.grant",
                               f"no grant for {right} on {step.resource}", "I-14")
                effective_rights.add(right)
        # I-07: intersection, never union.
        effective_rights &= set(token.granted_rights)
        if not effective_rights >= set(plan.required_rights):
            self._deny(token, "step5.grant", "plan requires rights outside the intersection", "I-07")

        # ---- 6. Is the action's risk class within the token's ceiling? ---
        if plan.declared_risk > token.risk_ceiling:
            self._deny(token, "step6.risk",
                       f"risk {plan.declared_risk.name} exceeds ceiling {token.risk_ceiling.name}",
                       "I-101")

        # ---- 7. Does classification permit this action here? -------------
        # S13-D1: for an outbound action the classification that governs is
        # the classification of the CONTENT LEAVING, which the plan's taint
        # carries under I-99 + I-27.
        if is_external_transmission:
            rule = TRANSMIT_EXTERNALLY[plan.taint.classification]
            if rule == "never":
                self._deny(token, "step7.classification",
                           f"{plan.taint.classification.name} is never transmitted externally",
                           "S13-D1/DATA_CLASSIFICATION-2", security_event=True)

        # ---- 8. Are conditions satisfied? time / rate / sensitivity ------
        if plan.cost_estimate > cost_ceiling:
            self._deny(token, "step8.conditions", "cost estimate exceeds ceiling", "I-105")

        # ---- 9. Does the risk class require approval? --------------------
        # PERMISSION_ARCHITECTURE.md section 5. I-09: only James approves;
        # nothing in this module can create an approval.
        if plan.declared_risk >= Risk.EXECUTE and approval is None:
            self._deny(token, "step9.approval",
                       f"{plan.declared_risk.name} requires approval", "I-09")

        # I-40 / MT-7 row 3: a plan influenced by EXTERNAL content cannot
        # exceed PREPARE without an approval NAMING THE SOURCE.
        #
        # Resolved 2026-08-15: "untrusted content" is a PROVENANCE CLASS, not
        # a trust level (slice/FINDINGS.md finding 2). A standing approval --
        # which names no source -- therefore CANNOT satisfy this, while a
        # James-stated objective never reaches it, because there is no
        # external source in its provenance to name.
        if plan.taint.is_untrusted_derived() and plan.declared_risk > Risk.PREPARE:
            required = plan.taint.external_sources()
            if approval is None or not approval.covers_sources(required):
                self._deny(token, "step9.approval",
                           f"externally-influenced plan needs approval naming {sorted(required)}",
                           "I-40", security_event=True)

        # ---- 10. Otherwise ALLOW ----------------------------------------
        auth = Authorization(
            plan_identity=plan.identity(),
            scope_path=plan.scope_path,
            risk_ceiling=plan.declared_risk,
            tool_set=frozenset(s.tool_name for s in plan.steps),
            cost_ceiling=cost_ceiling,
            argument_envelope=argument_envelope,
            binding_envelope=frozenset(b.identity() for b in resolved_bindings.values()),
            effective_rights=frozenset(effective_rights),
            delegation_ancestry=delegation_ancestry,
            granted_at=time.time(),
            approval=approval,
        )
        self._audit.decision(plan.scope_path, token.trace_id, "allow",
                             f"plan={auth.plan_identity} binding_id={auth.binding_identity()}")
        return auth

    # -- denial helpers ----------------------------------------------------

    def _deny(self, token: ContextToken, step: str, reason: str,
              invariant: str, security_event: bool = False) -> None:
        d = Denied(step, reason, invariant, security_event)
        self._record_denial(token, d)
        raise d

    def _record_denial(self, token: ContextToken, d: Denied) -> None:
        """W-2: the record of a decision is written under the authority of
        that decision -- denials included. Every outcome is recorded."""
        try:
            self._audit.decision(token.scope_path, token.trace_id, "deny",
                                 f"step={d.step} reason={d.reason} inv={d.invariant}")
        except Denied:
            # I-93: if the denial record cannot be written we are already
            # denying, which is the fail-closed direction. Do not mask.
            pass
