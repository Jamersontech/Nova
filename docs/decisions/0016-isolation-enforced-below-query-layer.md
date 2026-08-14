# 0016 — Isolation Is Enforced Below the Query Layer

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 04
**Accepted:** 2026-08-13 by James
**Section:** 04
**Resolves:** `D-33` — as a requirement, not a technology

## Decision
Scope isolation must be enforced by a layer beneath query construction, deriving restriction
from an execution's bound scope identity that the executing code cannot modify. A query
lacking a scope constraint must return nothing, not unrestricted data. Enforcement covers
enumeration, counts, and existence; applies to every access path; denies when scope is
indeterminate; and must be independently testable with deliberately hostile queries.
**No storage technology is selected** — `D-02` remains deferred.

## Context
Section 03 marked `I-03` and `I-33` `[PHYS]`: they cannot be satisfied by the conceptual model
alone. James assigned `D-33` to Section 04 as a security decision.

## Problem
If isolation is enforced only by application code adding a scope filter to each query, `I-03`
holds exactly as long as every query — forever, written by humans and by agents — is correct.
That is a coding convention with a security label, not a structural property.

## Options Considered
1. **Application-layer filtering.** Cheapest; works with any store; one missed predicate is a
   cross-client disclosure, and correctness must hold in perpetuity across code nobody has
   written yet.
2. **Enforcement below the query layer, technology-neutral requirement.** Structural; costs
   operational complexity and constrains the `D-02` choice.
3. **Select a specific mechanism now.** Removes ambiguity; violates the technology-deferment
   constraint and pre-empts `D-02`, which depends on runtime and hosting decisions not yet
   made.

## Decision Made
Option 2. Three mechanism families are recorded as candidates with tradeoffs — per-scope
physical separation, per-scope namespace separation, engine-enforced **record** restriction —
and none is selected. *(Wording aligned 2026-08-13, N-13: "row" was a relational term and is
replaced by "record", which commits to no storage model. No decision changes.)*

## Reason
`I-03` is the invariant the entire architecture rests on. Making it depend on query-writing
discipline means it will eventually fail, quietly, in a way nobody notices until a client sees
another client's data. Enforcement beneath the application makes hostile or broken queries
return nothing.

## Tradeoffs
**Advantages:** isolation survives buggy, confused, and hostile application code; testable by
attacking it directly; constrains `D-02` toward stores that can actually deliver `I-03`;
enables the PDP-independence in [ADR 0017](./0017-isolation-independent-of-pdp.md).
**Disadvantages:** operational cost per client scope; cross-scope aggregation becomes N
connections; disqualifies otherwise attractive storage options; adds provisioning work when
onboarding a client.

## Consequences
`D-02` acquires hard qualification criteria. **The authoritative list of criteria is
[`ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) §5, `C-1`–`C-11`.**
*(Range corrected 2026-08-13, N-5: this ADR previously said `C-1`–`C-9`, predating `C-10` and
`C-11`.)*

**The approved disqualification set is unchanged: `C-1`, `C-2`, `C-5`, `C-6`.** A candidate
failing any of those four is rejected regardless of other merits. **James decided 2026-08-13
(`S4-P4`) that `C-3`, `C-4`, `C-8`, `C-9`, `C-10` and `C-11` are NOT ratified as disqualifying**
— they are evaluated and recorded, and a failure is a flagged concern for James rather than an
automatic rejection. §5 marks each accordingly.

`I-03` and `I-33` remain `[PHYS]` and unverified until a mechanism is chosen and tested.
Invariants `I-60`–`I-63`, `I-86`.

## What Would Change This
Evidence that no available mechanism can meet the requirement at acceptable cost — in which
case the honest response is to narrow the isolation frontier explicitly and record the reduced
guarantee, not to quietly fall back to application-layer filtering.
