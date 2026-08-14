# 0026 — Model Verification Is Corroboration, Never Evidence

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 05
**Section:** 05

## Decision

A model checking a result **never** promotes epistemic status, **never** satisfies an approval
requirement, and **never** lowers a risk class (`I-102`).

Where a model check gates an action above `PREPARE`, independence is **required**, not preferred:
it is not the same call and not the same instance that produced the result, and it does not
receive the producing call's untrusted inputs unlabelled. A **different provider** is preferred
and **not** required.

## Context

[`MODEL_ARCHITECTURE.md`](../architecture/MODEL_ARCHITECTURE.md) §3 states that a checker
*"should"* not be the same instance and *"preferably"* not the same provider, and that
self-verification in one call is weak evidence.
[`ORCHESTRATION_ARCHITECTURE.md`](../architecture/ORCHESTRATION_ARCHITECTURE.md) §2 makes
Verification a distinct stage; [`AGENT_ARCHITECTURE.md`](../architecture/AGENT_ARCHITECTURE.md) §1
makes review agents permanently read-only.

## Problem

**A security property was written in advisory language and stood behind no invariant.** "Should"
and "preferably" are review guidance; nothing rejected an implementation that verified a result
with the same model, in the same call, holding the same injected content.

The structural controls do not close it. Read-only review agents prevent an agent approving *its
own work* — a control over **capability**. They say nothing about the **model** behind the review
agent being the same model, reading the same poisoned context, and reporting success. Injected
content that reaches the producer typically reaches the checker too, since the checker must see
the material to check it.

Worse, verification success was capable of being read as evidence. Nothing said a verifier's
"looks correct" does not make a `model.generated` item a fact, does not discharge an approval, and
does not lower a class — so an implementer optimising away approvals had a plausible-looking
argument available.

## Options Considered

1. **Leave it advisory.** No cost. Leaves a security property unenforceable and leaves
   verification-as-evidence available to an implementer.
2. **Require a different provider for every model check.** Strongest separation. Makes
   verification **unavailable** whenever only one provider is permitted for a scope
   (`MG-9` can legitimately reduce the permitted set to one). An unavailable check gets skipped,
   and a silently skipped check is worse than a same-provider one.
3. **Require a different instance; prefer a different provider; and cap what any model check can
   establish.** Enforceable in all configurations; states the epistemic limit explicitly.
4. **Abolish model verification.** Honest and wasteful — model checks do catch real errors, and
   removing them removes a cheap filter without replacing it.

## Decision Made

Option 3.

## Reason

**The load-bearing part is the cap, not the independence.** Independence reduces correlated error;
it does not turn model output into evidence, because two models are two low-trust sources and
`PROVENANCE_AND_TRUST.md` §5 already rates the combination as inference at best. Stating the cap
is what prevents verification from being used to erode approvals — which is the failure mode that
actually costs something.

Option 2 was rejected on availability. A requirement that cannot be met in a permitted
configuration becomes a requirement that is quietly dropped, and `MG-9` can legitimately leave one
provider in the set.

## Tradeoffs

**Advantages:** a security property becomes testable; verification cannot be used to reduce
approvals or promote status; works in every provider configuration including single-provider;
`I-09` stays unqualified.

**Disadvantages:** two calls where implementations would prefer one — cost and latency on every
above-`PREPARE` check; correlated failure remains real when the same provider serves both calls,
and this decision accepts that rather than solving it; "not the same instance" is a requirement on
a runtime property NOVA does not yet specify, so it is unverified until Section 31.

**Stated plainly:** NOVA's verification above `PREPARE` rests on declared success criteria,
structural read-only review, and James — not on a model checking a model.

## Consequences

- [`MODEL_ARCHITECTURE.md`](../architecture/MODEL_ARCHITECTURE.md) §3's advisory sentence is
  amended to point at this decision, authorized by
  [ADR 0028](./0028-section-05-amendments-to-accepted-architecture.md).
- Verification cost rises on high-risk work. This is accepted: `SCALE_AND_COST_ARCHITECTURE.md` §4
  already states that risk class overrides the cost preference on high-risk work.
- Correlated verifier capture — same provider, same injected content, both wrong — remains
  possible. Recorded as `T-32`.

Invariants: `I-102` (new). `I-09`, `I-39` untouched.

## What Would Change This

Evidence that model checking reliably catches a class of error that structural review does not —
which would argue for *more* model verification within these limits, not for treating it as
evidence.
