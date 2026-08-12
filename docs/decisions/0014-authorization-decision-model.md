# 0014 — Ordered Authorization Decision, Fail-Closed

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 03
**Section:** 03

## Decision
Authorization answers *"can this actor perform this action on this resource in this context
right now?"* through a fixed ordered sequence in which **scope containment is checked before
permissions are evaluated**. Default deny; explicit denial overrides any grant; PDP
unavailability means deny; every outcome is audited. Read decisions may be cached within one
context's lifetime, keyed to its token; nothing else is cached.

## Context
ADR 0001 established a single Policy Decision Point and ADR 0003 the Context Token. Section
03 must specify what the PDP evaluates and in what order.

## Problem
Order matters more than it appears. If permissions are evaluated before scope containment, a
misconfigured broad grant could authorize access to a resource in another client's scope —
the grant would answer "yes" before anything asked "is this even your data?"

## Options Considered
1. **Permission-first evaluation.** Conventional in most systems; a broad grant can reach
   across scopes, so isolation depends on grant hygiene.
2. **Containment-first evaluation.** Isolation holds regardless of how permissions are
   configured; slightly less flexible, since no grant can ever reach outside its scope.
3. **Unordered policy evaluation.** Expressive; unpredictable, and unpredictability in
   authorization is a defect.

## Decision Made
Option 2, fail-closed.

## Reason
Containment-first makes `I-03` — Client A's execution cannot reach Client B — true **by
construction rather than by configuration**. Under option 1 that property depends on nobody
ever writing an over-broad grant, which is not a property, it is a hope.

## Tradeoffs
**Advantages:** isolation is independent of grant correctness; deterministic and testable in
isolation; fail-closed prevents unauthorized action during outages.
**Disadvantages:** no grant can ever span scopes, so legitimate cross-scope work must be
decomposed; fail-closed means PDP unavailability stops NOVA; the PDP is on every hot path.

## Consequences
Cross-scope work is always N authorized executions aggregated above them, never one wide
execution. The PDP must be simple and fast enough to sit on every path. Invariants
`I-14`–`I-20`.

## What Would Change This
Performance data showing the PDP cannot meet interactive latency — the answer would be a
faster PDP or wider read caching within a context, never permission-first evaluation.
