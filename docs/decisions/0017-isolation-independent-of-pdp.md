# 0017 — Isolation Enforcement Is Independent of the Policy Decision Point

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 04
**Section:** 04
**Partially mitigates:** `T-19` (compromised PDP)

## Decision
The layer enforcing storage scope isolation must **not** consult the Policy Decision Point.
Scope restriction derives from the execution's bound scope identity, established at connection
or session establishment. Two independent mechanisms must therefore fail for cross-client
access to occur.

## Context
Section 03's adversarial review found `T-19`: a compromised PDP returns `ALLOW` and every
enforcement point obeys. James accepted this as unmitigated residual risk. Section 04 owns the
enforcement mechanism (`D-33`) and can address part of it.

## Problem
The architecture concentrates authorization in one trusted component. Concentration is correct
— scattered authorization is how isolation rots (ADR 0001) — but it creates a single component
whose compromise defeats everything, including client isolation.

## Options Considered
1. **Accept `T-19` as-is.** No new complexity; the most important invariant in NOVA depends on
   one component's integrity.
2. **Independent enforcement layer.** Client isolation survives PDP compromise; requires the
   enforcement layer never to consult policy, which forbids expressing isolation as policy
   rules.
3. **Independent verification of PDP decisions** — quorum, second opinion, attestation.
   Addresses `T-19` more completely; substantial complexity and latency on every decision, and
   the verifier becomes a second trusted component.
4. **Both 2 and 3.** Strongest; option 3's cost is not justified at NOVA's scale today.

## Decision Made
Option 2. Option 3 is explicitly **not** adopted and remains available if `T-19` proves more
serious in practice.

## Reason
The two defenses fail for different reasons: the PDP is compromised by defeating one
component's logic, the enforcement layer by forging a connection-level scope binding. Making
them independent means one compromise is not sufficient, and the cost is a constraint on how
isolation is expressed rather than new machinery.

## Tradeoffs
**Advantages:** cross-client isolation survives PDP compromise; no added latency; no second
trusted component; a hostile query still returns nothing.
**Disadvantages:** isolation cannot be expressed as policy rules, so it cannot be adjusted
without changing infrastructure — a cost that is also a benefit; two enforcement models to
reason about; `D-34` engine selection must not also become the storage enforcement mechanism.

## Consequences
**`T-19` is reduced in blast radius, not resolved.** A compromised PDP can still authorize
destructive, irreversible, and unapproved actions within an execution's own scope, and can
deny legitimate work. The mitigation assumes the attacker cannot forge the scope binding; an
attacker controlling connection establishment defeats it. Independent decision verification
remains undesigned. Invariants `I-61`, `I-62`.

## What Would Change This
Evidence of PDP compromise being more likely or more damaging than assessed, which would make
option 3's cost worth paying — recorded then as a superseding ADR, not an amendment here.
