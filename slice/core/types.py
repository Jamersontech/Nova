"""Core security objects for the NOVA vertical slice.

Every type here corresponds to an object the architecture already defines.
Nothing is invented; where a field exists, the governing document is cited.

SLICE-LOCAL: this is validation code, not a production implementation, and
selects no deferred technology decision.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Optional


# --------------------------------------------------------------------------
# Risk classes — PERMISSION_ARCHITECTURE.md section 4
# --------------------------------------------------------------------------

class Risk(IntEnum):
    """Ordered so a ceiling comparison is a single <=. IRREVERSIBLE is never
    autonomous (PERMISSION_ARCHITECTURE.md section 5)."""
    READ = 0
    ANALYZE = 1
    PREPARE = 2
    EXECUTE = 3
    HIGH_IMPACT = 4
    IRREVERSIBLE = 5


# --------------------------------------------------------------------------
# Classification — DATA_CLASSIFICATION.md section 1
# --------------------------------------------------------------------------

class Classification(IntEnum):
    PUBLIC = 0
    INTERNAL = 1
    CONFIDENTIAL = 2
    CLIENT_CONFIDENTIAL = 3
    SENSITIVE_PERSONAL = 4
    SECURITY_CRITICAL = 5


# --------------------------------------------------------------------------
# Provenance / trust — PROVENANCE_AND_TRUST.md sections 2-3
# --------------------------------------------------------------------------

class Trust(IntEnum):
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    HIGHEST = 3


PROVENANCE_DEFAULT_TRUST = {
    "james.stated": Trust.HIGHEST,
    "james.approved": Trust.HIGHEST,
    "nova.inferred": Trust.MEDIUM,
    "agent.generated": Trust.MEDIUM,
    "model.generated": Trust.LOW,
    "client.supplied": Trust.MEDIUM,
    "integration.supplied": Trust.MEDIUM,
    "external.web": Trust.LOW,
    "system.verified": Trust.HIGH,
    "system.unverified": Trust.LOW,
}


@dataclass(frozen=True)
class Taint:
    """I-99: a derivation carries the UNION of its inputs' provenance and the
    LOWEST trust among them. I-27: and the STRICTEST classification.

    I-111: this survives persistence and is restored at retrieval -- which is
    why it is a value object with explicit serialization, not ambient state.
    """
    provenance: frozenset[str]
    trust: Trust
    classification: Classification

    @staticmethod
    def of(provenance: str, classification: Classification = Classification.INTERNAL) -> "Taint":
        return Taint(
            provenance=frozenset({provenance}),
            trust=PROVENANCE_DEFAULT_TRUST[provenance],
            classification=classification,
        )

    @staticmethod
    def union(*parts: "Taint") -> "Taint":
        """I-99 union + lowest trust; I-27 strictest classification."""
        if not parts:
            raise ValueError("union of no taint is undefined -- fail closed rather than default")
        prov: set[str] = set()
        for p in parts:
            prov |= set(p.provenance)
        return Taint(
            provenance=frozenset(prov),
            trust=min(p.trust for p in parts),
            classification=max(p.classification for p in parts),
        )

    def derive(self, own_provenance: str) -> "Taint":
        """Model output carries its inputs' union PLUS its own model.generated
        provenance (I-99), and never a higher trust than its inputs."""
        return Taint(
            provenance=self.provenance | {own_provenance},
            trust=min(self.trust, PROVENANCE_DEFAULT_TRUST[own_provenance]),
            classification=self.classification,
        )

    # I-40's first clause is about EXTERNAL content. These are the provenance
    # classes that are external to NOVA's trust boundary.
    EXTERNAL_PROVENANCE = frozenset({"external.web", "client.supplied", "integration.supplied"})

    def is_untrusted_derived(self) -> bool:
        """MT-7 row 3 / I-100 / I-40: "derived from untrusted content".

        RESOLVED 2026-08-15 by James: this is a PROVENANCE-CLASS property, not
        a trust-level one. See slice/FINDINGS.md finding 2.

        I-40 reads: "EXTERNAL content may inform a plan but never escalate one;
        a plan influenced by UNTRUSTED content cannot exceed PREPARE without
        approval naming the source." One sentence, one rule -- so "untrusted
        content" IS "external content". This reading makes I-40 internally
        consistent; the trust reading makes its two clauses disagree.

        Why the trust reading fails: the Planner is a model, so I-99 gives
        EVERY plan model.generated provenance at LOW trust, and
        min(anything, LOW) = LOW. Gating on trust would ceiling every action
        NOVA ever takes and make standing approvals unreachable, because a
        James-stated objective has no external source to name.

        NOT A TRUST DOWNGRADE. A LOW-trust plan remains LOW trust. This governs
        ONLY whether the "derived from untrusted content" gates apply. Trust,
        classification, approval, scope, binding and PREPARE-ceiling rules are
        all untouched and are evaluated independently.
        """
        return bool(self.provenance & Taint.EXTERNAL_PROVENANCE)

    def external_sources(self) -> frozenset[str]:
        """I-40 requires the approval to NAME THE SOURCE. This is the set an
        approval must name; empty means there is no source to name, which is
        why a James-stated objective cannot require a source-naming approval."""
        return frozenset(self.provenance & Taint.EXTERNAL_PROVENANCE)

    def to_row(self) -> str:
        return "|".join(sorted(self.provenance)) + f"#{int(self.trust)}#{int(self.classification)}"

    @staticmethod
    def from_row(row: str) -> "Taint":
        prov, trust, cls = row.rsplit("#", 2)
        return Taint(frozenset(prov.split("|")), Trust(int(trust)), Classification(int(cls)))


# --------------------------------------------------------------------------
# Context Token — MASTER_ARCHITECTURE.md section 2.2
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ContextToken:
    """Scoped, time-bound, verifiable. Issued ONLY by the Context service
    (I-106). `integrity` stands in for I-87's detection requirement -- see the
    slice README for what is and is not proven here."""
    identity: str
    actor: str
    scope_path: str
    granted_rights: frozenset[str]
    risk_ceiling: Risk
    issued_at: float
    expires_at: float
    trace_id: str
    integrity: str

    def covers(self, resource_scope: str) -> bool:
        """Scope containment: a token covers its own scope and everything
        below it. Siblings have no path (I-03)."""
        return resource_scope == self.scope_path or resource_scope.startswith(self.scope_path + "/")

    def expired(self, now: Optional[float] = None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at


# --------------------------------------------------------------------------
# Execution binding — I-114, AUTHORIZATION_MODEL.md section 2
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ExecutionBinding:
    """I-114: the concrete substrate a tool action will use.

    I-114(c): identity is consequence-bearing. Provider, account/tenant,
    endpoint and api_version are part of the identity precisely so that
    repointing any of them produces a DIFFERENT binding rather than the same
    binding reconfigured.
    """
    tool_name: str
    tool_version: str
    integration_id: str
    provider: str
    account: str
    endpoint: str
    api_version: str
    credential_binding_id: str
    scope_path: str

    def identity(self) -> str:
        """Deterministic identity, by the construction I-93 establishes and
        I-109 reuses. No cryptography is introduced."""
        raw = "|".join([
            self.tool_name, self.tool_version, self.integration_id, self.provider,
            self.account, self.endpoint, self.api_version,
            self.credential_binding_id, self.scope_path,
        ])
        return hashlib.sha256(raw.encode()).hexdigest()[:32]


# --------------------------------------------------------------------------
# Plan — I-112, ORCHESTRATION_ARCHITECTURE.md section 2.1
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PlanStep:
    action: str
    resource: str
    tool_name: str
    required_rights: frozenset[str]
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Plan:
    """I-112: deterministic identity, immutable after authorization. Any
    material change produces a NEW plan with a NEW identity."""
    steps: tuple[PlanStep, ...]
    required_rights: frozenset[str]
    declared_risk: Risk
    scope_path: str
    taint: Taint
    cost_estimate: int

    def identity(self) -> str:
        parts = [self.scope_path, str(int(self.declared_risk)), str(self.cost_estimate),
                 ",".join(sorted(self.required_rights))]
        for s in self.steps:
            parts.append("|".join([
                s.action, s.resource, s.tool_name,
                ",".join(sorted(s.required_rights)),
                ",".join(f"{k}={v!r}" for k, v in sorted(s.arguments.items())),
            ]))
        return hashlib.sha256("::".join(parts).encode()).hexdigest()[:32]


# --------------------------------------------------------------------------
# Envelopes — MT-8 / I-100 / I-113 / I-114(b)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ArgumentEnvelope:
    """MT-8: authorization is over an envelope, not a literal."""
    allowed_values: dict[str, frozenset[str]]
    magnitude_ceilings: dict[str, int]

    def covers(self, arg: str, value: Any) -> bool:
        if arg in self.magnitude_ceilings:
            try:
                size = len(value) if isinstance(value, (list, tuple, set)) else int(value)
            except (TypeError, ValueError):
                return False  # unmeasurable magnitude fails closed
            return size <= self.magnitude_ceilings[arg]
        if arg in self.allowed_values:
            values = value if isinstance(value, (list, tuple, set)) else [value]
            return all(str(v) in self.allowed_values[arg] for v in values)
        # MT-9 / I-14: an argument the envelope does not fix is not covered.
        return False


@dataclass(frozen=True)
class Approval:
    """PERMISSION_ARCHITECTURE.md section 5. I-09: only James creates one.

    `names_sources` is what distinguishes a STANDING approval ("deploy Client
    A's staging without asking" -- names nothing) from the source-naming
    approval I-40 demands for a plan influenced by external content. An
    approval that names no source cannot satisfy I-40; an approval naming a
    source it was not given for cannot either.
    """
    approval_id: str
    names_sources: frozenset[str] = frozenset()
    standing: bool = False

    def covers_sources(self, required: frozenset[str]) -> bool:
        return required <= self.names_sources


@dataclass(frozen=True)
class Authorization:
    """The authorization decision's product.

    I-113: a plan-level ENVELOPE (scope, risk ceiling, tool set, cost ceiling)
    plus the per-action check. I-114(b): the binding envelope lives here too.
    I-109: what an approval binds.
    """
    plan_identity: str
    scope_path: str
    risk_ceiling: Risk
    tool_set: frozenset[str]
    cost_ceiling: int
    argument_envelope: ArgumentEnvelope
    binding_envelope: frozenset[str]      # I-114(b): binding identities
    effective_rights: frozenset[str]
    delegation_ancestry: tuple[str, ...]
    granted_at: float
    approval: Optional["Approval"] = None

    def binding_identity(self) -> str:
        """I-109's ten bound properties, as a deterministic identity.

        Order is fixed and documented: the nine accepted properties in
        PERMISSION_ARCHITECTURE.md section 5's order, then the tenth
        (execution binding) added by Section 11.
        """
        parts = [
            self.plan_identity,                                   # 1 action (the plan's steps)
            "|".join(sorted(t for t in self.tool_set)),           # 2 resource+6 tool set
            self.scope_path,                                      # 3 scope
            "|".join(sorted(self.effective_rights)),              # 4 effective rights
            str(int(self.risk_ceiling)),                          # 5 risk class
            self._argument_envelope_identity(),                   # 7 argument envelope
            "|".join(self.delegation_ancestry),                   # 8 delegation ancestry
            str(self.cost_ceiling),                               # 9 cost ceiling
            "|".join(sorted(self.binding_envelope)),              # 10 execution binding
        ]
        return hashlib.sha256("::".join(parts).encode()).hexdigest()[:32]

    def _argument_envelope_identity(self) -> str:
        av = ";".join(f"{k}={','.join(sorted(v))}"
                      for k, v in sorted(self.argument_envelope.allowed_values.items()))
        mc = ";".join(f"{k}<={v}" for k, v in sorted(self.argument_envelope.magnitude_ceilings.items()))
        return av + "#" + mc


# --------------------------------------------------------------------------
# Denial — SECURITY_BOUNDARIES.md section 6, I-14
# --------------------------------------------------------------------------

class Denied(Exception):
    """Every deny path raises this. It is never caught internally: a denial
    that a component can swallow is not a denial.

    `security_event` distinguishes a boundary violation (recorded as a
    security event, not a retryable error -- MT-7 row 2, I-100) from an
    ordinary refusal.
    """

    def __init__(self, step: str, reason: str, invariant: str, security_event: bool = False):
        self.step = step
        self.reason = reason
        self.invariant = invariant
        self.security_event = security_event
        super().__init__(f"DENIED at {step}: {reason} [{invariant}]")


@dataclass
class Outcome:
    """RELIABILITY_ARCHITECTURE.md section 2 as amended by Section 11:
    UNKNOWN is a distinct state and is never collapsed into FAILURE."""
    state: str                      # "success_claimed" | "failure_claimed" | "unknown"
    detail: str
    taint: Taint
    observed: bool = False          # True only if independently read back

    def is_retryable_automatically(self, provider_enforces_dedup: bool) -> bool:
        """S11-D2: automatic retry requires PROVIDER-enforced deduplication,
        not merely a tool that declares idempotency. UNKNOWN never auto-retries
        without it."""
        if self.state == "unknown":
            return provider_enforces_dedup
        return False
