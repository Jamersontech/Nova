"""The Model Gateway — the sixth Policy Enforcement Point.

MODEL_GATEWAY_ARCHITECTURE.md; I-94..I-98.

  I-94  Model egress is a PEP. Every model call is an authorization decision
        evaluated by the PDP PER CALL, against the Context Token, the
        classification of EVERY item in the request, and the DESTINATION
        PROVIDER. There is no path to a provider without a decision.
        The gateway DECIDES NOTHING -- like every enforcement point it can
        only deny (I-77).
  I-95  No model request carries content from more than one scope.
  I-96  Content whose classification forbids model exposure never reaches a
        provider. If classification cannot be established, DENY (I-52 pattern).
  I-97  Provider selection is authorization-CONSTRAINED, not weighted.
        Fallback/failover/reroute/retry select only WITHIN the permitted set;
        empty set = fail closed. Degradation never widens the set.
  I-98  Capability profile, provider and model are NEVER selected by model
        output at call time. They are declared by the agent definition or
        fixed in the authorized plan.

The gateway holds the provider credential (I-103, control-plane) and never
hands it to an agent, tool or model context.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from .audit import AuditWriter
from .context_service import ContextService
from .types import (Classification, ContextToken, Denied, Outcome, Taint, Trust)


@dataclass(frozen=True)
class ModelRequestItem:
    """One item placed into a model request. Carries its OWN taint -- I-94
    requires the decision to see the classification of EVERY item."""
    label: str
    content: str
    scope_path: str
    taint: Taint


@dataclass(frozen=True)
class ProviderBinding:
    """The model provider's execution binding. Distinct from a tool binding
    (I-114) but the same shape of question: which concrete substrate."""
    provider: str
    model: str
    endpoint: str
    api_version: str
    credential_ref: str          # control-plane credential (I-103), by reference


@dataclass(frozen=True)
class CapabilityProfile:
    """I-98: declared by the AGENT DEFINITION or fixed in the authorized plan.
    Never selected by model output at call time."""
    name: str
    permitted_providers: frozenset[str] = frozenset()
    permitted_models: frozenset[str] = frozenset()


@dataclass
class ModelResponse:
    text: str
    taint: Taint
    outcome: str = "success_claimed"      # success_claimed | unknown | failure_claimed


class ModelGateway:
    def __init__(self, pdp_available_check: Callable[[], bool],
                 context: ContextService, audit: AuditWriter):
        self._pdp_ok = pdp_available_check
        self._context = context
        self._audit = audit
        self._providers: dict[str, ProviderBinding] = {}
        self._transports: dict[str, Callable[[str, str], ModelResponse]] = {}
        self.emergency_stop = False       # I-19 / X-7

    def register_provider(self, binding: ProviderBinding,
                          transport: Callable[[str, str], ModelResponse]) -> None:
        self._providers[binding.provider] = binding
        self._transports[binding.provider] = transport

    # ------------------------------------------------------------------
    # The single entry point. There is deliberately no other way to reach a
    # provider: `_transports` is private and nothing else calls it.
    # ------------------------------------------------------------------
    def call(self, token: ContextToken, items: list[ModelRequestItem],
             profile: CapabilityProfile, requested_provider: str,
             requested_model: str,
             sensitive_personal_approval: Optional[str] = None,
             model_requested_provider: Optional[str] = None) -> ModelResponse:
        """`requested_provider` / `requested_model` come from the AGENT
        DEFINITION or the AUTHORIZED PLAN.

        `model_requested_provider` exists ONLY so I-98 can be tested: it
        represents a provider named by MODEL OUTPUT. It is never honoured.
        """
        # ---- I-98: model output never selects routing --------------------
        # Checked FIRST so that a model-named provider can never influence any
        # later step, not even by being evaluated.
        if model_requested_provider is not None:
            self._deny(token, "gateway.i98",
                       "model output named a provider; routing is fixed by the "
                       "agent definition or the authorized plan",
                       "I-98", security_event=True)

        # ---- I-94: emergency stop / PDP availability ---------------------
        # "A gateway that cannot confirm a stop refuses to call."
        if self.emergency_stop:
            self._deny(token, "gateway.stop", "emergency stop in effect", "I-19", True)
        if not self._pdp_ok():
            self._deny(token, "gateway.pdp", "PDP unavailable", "I-17")

        # ---- I-94: the token is verified at this enforcement point --------
        # Revocation (I-74) and AG-11 take effect here as at every other PEP.
        self._context.verify(token)

        # ---- I-95: one scope per request ---------------------------------
        # PUBLIC and INTERNAL material is not a second scope.
        foreign = [
            i for i in items
            if not token.covers(i.scope_path)
            and i.taint.classification > Classification.INTERNAL
        ]
        if foreign:
            self._deny(token, "gateway.i95",
                       "request carries content from outside the bound scope",
                       "I-95", security_event=True)
        scopes = {i.scope_path for i in items
                  if i.taint.classification > Classification.INTERNAL}
        if len(scopes) > 1:
            self._deny(token, "gateway.i95",
                       "request carries content from more than one scope",
                       "I-95", security_event=True)

        # ---- I-96: classification gates egress ---------------------------
        for i in items:
            if i.taint.classification in (Classification.SECURITY_CRITICAL,):
                self._deny(token, "gateway.i96",
                           f"{i.label}: SECURITY-CRITICAL never crosses under any "
                           "grant, approval or profile", "I-96", security_event=True)
            if i.taint.classification == Classification.SENSITIVE_PERSONAL:
                if sensitive_personal_approval is None:
                    self._deny(token, "gateway.i96",
                               f"{i.label}: SENSITIVE-PERSONAL requires explicit "
                               "per-call approval", "I-96", security_event=True)
            if not i.taint.provenance:
                # I-52's pattern: classification that cannot be established denies.
                self._deny(token, "gateway.i96",
                           f"{i.label}: classification could not be established",
                           "I-96", security_event=True)

        # ---- I-97: routing is authorization-constrained ------------------
        permitted = profile.permitted_providers
        if not permitted:
            # Empty permitted set -> fail closed and SAY SO. I-14 default deny.
            self._deny(token, "gateway.i97",
                       "no provider permitted for this profile", "I-97", True)
        if requested_provider not in permitted:
            self._deny(token, "gateway.i97",
                       f"provider {requested_provider} not in the permitted set",
                       "I-97", security_event=True)
        if requested_model not in profile.permitted_models:
            self._deny(token, "gateway.i97",
                       f"model {requested_model} not in the permitted set",
                       "I-97", security_event=True)

        binding = self._providers.get(requested_provider)
        if binding is None:
            self._deny(token, "gateway.binding",
                       "no provider binding registered", "I-14", True)
        if binding.model != requested_model:
            self._deny(token, "gateway.binding",
                       "provider binding does not serve the requested model",
                       "I-97", security_event=True)

        # ---- egress ------------------------------------------------------
        prompt = "\n".join(i.content for i in items)
        transport = self._transports[requested_provider]
        try:
            response = transport(prompt, binding.credential_ref)
        except TimeoutError:
            # RELIABILITY section 2 (Section 11): UNKNOWN, never "failure".
            self._audit.execution(token.scope_path, token.trace_id, "model_interaction",
                                  f"provider={binding.provider} model={binding.model} "
                                  f"outcome=unknown")
            return ModelResponse(text="", outcome="unknown",
                                 taint=self._response_taint(items))

        # ---- I-99: the response is a DERIVATION of every request item -----
        # Union of provenance, LOWEST trust, STRICTEST classification, plus its
        # own model.generated provenance. The model cannot alter this: taint is
        # computed from the REQUEST, never read from the response text.
        response.taint = self._response_taint(items)

        self._audit.execution(token.scope_path, token.trace_id, "model_interaction",
                              f"provider={binding.provider} model={binding.model} "
                              f"profile={profile.name} outcome={response.outcome}")
        return response

    def _response_taint(self, items: list[ModelRequestItem]) -> Taint:
        """I-99. Computed structurally from the request. A response CANNOT
        supply, alter, or launder its own provenance -- there is no code path
        that reads provenance out of response text."""
        if not items:
            # No inputs is not "no taint": fail closed to model.generated at
            # LOW trust rather than inventing a trusted empty union.
            return Taint.of("model.generated", Classification.INTERNAL)
        return Taint.union(*(i.taint for i in items)).derive("model.generated")

    def _deny(self, token: ContextToken, step: str, reason: str,
              invariant: str, security_event: bool = False) -> None:
        d = Denied(step, reason, invariant, security_event)
        try:
            self._audit.decision(token.scope_path, token.trace_id, "deny",
                                 f"step={d.step} reason={d.reason} inv={d.invariant}")
        except Denied:
            pass
        raise d
