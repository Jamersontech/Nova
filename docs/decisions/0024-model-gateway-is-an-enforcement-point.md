# 0024 — The Model Gateway Is a Policy Enforcement Point

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 05
**Section:** 05
**Partially resolves:** `D-20` — routing constraints; thresholds deferred

## Decision

**Model egress is the sixth Policy Enforcement Point.** Every model call is an authorization
decision evaluated by the PDP against the Context Token, the classification of every item in the
request, and the **destination provider**, per call. There is no path to a provider without a
decision; PDP unavailability is deny (`I-17`).

Three constraints follow at that point:

1. **One scope per request.** No model request carries content from more than one scope, and
   model context is discarded at scope change (`I-95`).
2. **Provider selection is constrained, not weighted.** Data policy filters the candidate set
   before cost, latency and quality optimise within it — **including on fallback**, which fails
   closed rather than reaching an unpermitted provider (`I-97`).
3. **The profile is declared, never generated.** Capability profile, provider and model are never
   selected by model output (`I-98`).

## Context

Section 02 established the gateway ([ADR 0007](./0007-model-gateway-provider-neutrality.md)) and
correctly assigned it redaction, per-scope data policy, and routing — while stating that it does
*not* own whether a request is permitted, because "Policy decides."

## Problem

**Accepted documents contradicted each other.** Stated precisely, because the imprecise version —
"model egress had no Policy involvement" — is false.
[`MODEL_ARCHITECTURE.md`](../architecture/MODEL_ARCHITECTURE.md) §1 **does** draw an arrow from the
gateway to `Policy — what may be sent where`. But **four documents that exist to enumerate
enforcement omit it**: `PERMISSION_ARCHITECTURE.md` §2's five enforcement points;
`SYSTEM_LAYERS.md` §5's list of the places *"where enforcement is mandatory"*;
`MASTER_ARCHITECTURE.md` §4's Policy arrows, which come from orchestration, agent runtime,
capability and broker and not from the gateway; and `SECURITY_BOUNDARIES.md` §2, which claims to
enumerate **every** boundary and has no model-provider row.

So a model call was a Policy concern in the document about models and an enforcement point in no
document about enforcement — and an implementer reading the canonical enforcement lists, which is
what they are for, would have built egress with no decision on it. Redaction and data policy were
duties a component judged for itself.

**Three consequences were concretely unhandled.** Emergency stop did not reach model egress and
revocation did not take effect there, because `I-19` and `I-74` are both defined as taking effect
*at enforcement points*. And failover carried no data-policy constraint at all, so a degraded
system could reach a provider a scope was never permitted to reach.

## Options Considered

1. **Leave it to the calling PEP.** The orchestration or agent-runtime PEP authorizes the work,
   and the gateway trusts it. Cheapest; but the authorizing decision happens before the request
   content and the destination provider exist, so the thing being enforced is not the thing being
   decided. This is the same per-request-vs-per-access error Section 04 corrected at the Data
   Access PEP.
2. **Gateway self-enforces against configured policy.** Gateway holds the data-policy
   configuration and applies it. Avoids a hop; makes the gateway a second decision point, which
   is exactly the "one decides, many enforce" property `PERMISSION_ARCHITECTURE.md` §2 exists to
   protect. Two policy evaluators drift.
3. **Model egress is a sixth enforcement point.** The gateway asks the PDP per call and can only
   deny. One decision authority, six enforcement points. Costs a decision per model call.
4. **Route model calls through the tool PEP.** Treat a model call as a tool call. Superficially
   economical; a model call is not a tool call — it has no credential binding, no external
   idempotency, and its risk is about *what is disclosed* rather than *what is done*. Overloading
   the tool PEP obscures both.

## Decision Made

Option 3.

## Reason

**Enforcement belongs where the boundary is crossed, and this is a boundary crossing.** The
architecture already applies that principle everywhere else — the Data Access PEP evaluates per
access rather than per request, the Credential Broker asks per issue, the tool PEP asks per call.
Model egress was the one boundary where the principle had not been applied, and the reason it had
not was historical rather than reasoned: Section 02 wrote the gateway as an abstraction layer for
provider independence and did not revisit it as a security boundary.

Option 3 also makes `I-19` and `I-74` reach model egress **without a new mechanism** — they are
already defined as taking effect at enforcement points, so naming a sixth one is all that is
required.

## Tradeoffs

**Advantages:** egress is decided and recorded rather than assumed; emergency stop and revocation
reach the model path for free; failover cannot escape data policy; `SECURITY-CRITICAL` never
reaching a model becomes an enforced denial rather than a documented intention; one decision
authority preserved.

**Disadvantages:** a PDP decision per model call on a hot path — latency and PDP load, and the
PDP becomes a dependency of every model call rather than of every plan; more audit volume
(`I-18` produces a record per decision, and model calls are frequent); a compromised gateway is
now a named concentration (`T-29`); "one scope per request" forbids some genuinely convenient
cross-scope prompting, forcing N calls plus aggregation.

**The audit-volume tradeoff is real and is accepted.** `SCALE_AND_COST_ARCHITECTURE.md` §2 already
names audit volume as a pressure point with tiered retention as the direction. A high-frequency
decision that is not recorded is not a decision.

## Consequences

- [`PERMISSION_ARCHITECTURE.md`](../architecture/PERMISSION_ARCHITECTURE.md) §2 and
  [`MASTER_ARCHITECTURE.md`](../architecture/MASTER_ARCHITECTURE.md) §4 are amended to show six
  enforcement points — authorized by
  [ADR 0028](./0028-section-05-amendments-to-accepted-architecture.md).
- Cross-scope model work is N single-scope calls aggregated above them, matching
  [`CROSS_SCOPE_DATA_RULES.md`](../architecture/CROSS_SCOPE_DATA_RULES.md) §6 exactly.
- **A compromised PDP returns `ALLOW` here as it does at the other five points.** `T-19` and
  `I-85` are unchanged; nothing about a sixth enforcement point is independent evidence.
- Redaction remains containment, not prevention: it removes what NOVA can identify. `T-15`'s
  residual — provider behaviour after egress — is untouched.

Invariants: `I-94`–`I-98` (new). `I-17`, `I-19`, `I-74`, `I-77`, `I-85`, `I-86` untouched.

## What Would Change This

A demonstration that per-call PDP evaluation on the model path is unworkable in practice. That
would be a reason to change *how* the decision is obtained — for example an envelope evaluated
once and checked cheaply per call, the pattern
[`MODEL_TRUST_AND_AUTHORITY.md`](../architecture/MODEL_TRUST_AND_AUTHORITY.md) `MT-8` already uses
for tool arguments — not a reason to return egress to an unenforced state.
