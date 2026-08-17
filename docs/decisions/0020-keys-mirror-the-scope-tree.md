# 0020 — Encryption Keys Mirror the Scope Tree

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 04
**Accepted:** 2026-08-13 by James
**Section:** 04
**Partially resolves:** `D-35` — requirements; mechanism deferred to 38

## Decision
Encryption in transit everywhere and at rest wherever data lives. **Key material is
partitioned to follow the scope tree**: a key sufficient to read Client A's data at rest is not
sufficient for Client B's. The secrets store is keyed separately from the data store. Keys are
never in the data model, rotate without re-architecture, and preserve partitioning through
backup and restore. **No algorithm, library, or key-management technology is selected.**

## Context
`D-35` is shared between Sections 04 and 38. Section 04 owns what must be protected; Section 38
owns hardening and mechanism.

## Problem
A single key for everything at rest means at-rest protection has one failure point: an attacker
who obtains it gets every client. It also creates a boundary mismatch — runtime access is
partitioned by scope while at-rest access is not.

## Options Considered
1. **Single key for all data at rest.** Simplest to operate; compromise yields everything;
   at-rest and runtime boundaries disagree.
2. **Keys mirroring the scope tree.** At-rest compromise bounded by the same boundary as
   runtime; more keys to manage and rotate; cross-scope aggregation decrypts per scope.
3. **Per-item keys.** Finest granularity; unmanageable key volume with no proportionate gain
   over per-scope.

## Decision Made
Option 2, with the secrets store on a separate hierarchy.

## Reason
One boundary, tested once. Mirroring the scope tree means at-rest protection fails along the
same line as runtime isolation, so there is a single mental model rather than two that can
disagree. Per-scope decryption for aggregation adds no new pattern, since aggregation is
already decomposed per scope.

## Tradeoffs
**Advantages:** at-rest compromise is bounded by client scope; backups inherit partitioning;
one boundary to reason about; supports per-client offboarding by destroying that scope's
**data** keys, rendering at-rest copies and pre-deletion backups undecryptable.
**Disadvantages:** more keys, more rotation surface; key custody becomes load-bearing — `E-10`
means a key-recovery path weaker than the encryption is the encryption's real strength;
constrains `D-02` further (`C-9`); cross-scope reads carry decryption cost per scope.

## Consequences
The storage choice must support per-scope keys. Key custody and recovery become a Section 04
concern handed to Section 36. **Encryption is explicitly not a substitute for isolation
enforcement** — it protects stolen media, not runtime access.

**The audit key hierarchy is separate from client-data keys and is itself scope-partitioned.**
*(Amended 2026-08-12, M-3; partitioning added F-4.)* There is no single global audit key: audit
key material follows the scope tree as an independent hierarchy, so no scope's key material yields
a sibling's audit records at rest ([`ENCRYPTION_REQUIREMENTS.md`](../architecture/ENCRYPTION_REQUIREMENTS.md)
§3.2, `E-11`). **Partitioning holds on the write path too** *(added 2026-08-13, N-4; bootstrap
resolved `S4-P6`)*: audit **write** capability is **authorized by construction** — an execution
that has been authorized, and whose scope binding is therefore established, may write audit records
for **that scope only** and for **that execution's lifetime only**. There is no separate release
decision, no grant class, and no second authorization authority. It is **not** read capability, so
no audit writer — including the PDP (`I-18`, `I-85`) and the Observability responsibility — holds
blanket cross-scope write capability or broad read access (`E-12`, `I-88`). **`I-18` is unaffected
and not exempted:** the execution's own authorization is a decision and produces a record; audit
emission is a consequence of it, not a new authorization request. Append-only (`I-47`) is
unaffected. **No
mechanism, algorithm, or product is selected.** Separation is what lets audit survive client key destruction: audit is
SECURITY-CRITICAL, not CLIENT-CONFIDENTIAL, and contains references
rather than client content — so destroying a client's data keys does not destroy the evidence
that data existed and was deleted. `I-47` is preserved unweakened. Key destruction supplements
deletion; it does not replace the lineage cascade.

**Descendants do not hold ancestor keys ambiently.** *(Amended 2026-08-12, M-2.)* Access to an
ancestor-scope shared resource requires an explicit grant over that resource; key access follows
authorization per resource and per operation, and is audited.

**`I-82` is a data-key rule and governs nothing in the audit hierarchy.** *(Corrected 2026-08-13,
`S4-P5` and Decision 1.)* It covers ancestor-scope **decryption/data-key** access only. It does
**not** govern audit writes, audit-key access, or audit-key hierarchy semantics, and `E-11`/`E-12`
no longer cite it for any of them. What bounds audit-key access is stated directly: audit keys are
scope-bound and partitioned (`E-11`, `I-83`); no audit-key capability spans siblings; write is
execution-scoped (`E-12`, `I-88`); read is held by no component (`E-13`, `I-89`). **Authorization
over a scope's data keys confers no audit-key access.** James's audit access is per scope and is
not grant-mediated — `I-09`/`I-10` unchanged. Invariants `I-71`–`I-72`, `I-82`, `I-83`,
`I-88`–`I-90`.

## What Would Change This
A storage or platform choice unable to support per-scope keys — which would be a reason to
reject that choice, not to abandon this decision.
