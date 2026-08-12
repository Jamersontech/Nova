# 0020 — Encryption Keys Mirror the Scope Tree

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 04
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
one boundary to reason about; supports per-client offboarding by destroying that scope's keys.
**Disadvantages:** more keys, more rotation surface; key custody becomes load-bearing — `E-10`
means a key-recovery path weaker than the encryption is the encryption's real strength;
constrains `D-02` further (`C-9`); cross-scope reads carry decryption cost per scope.

## Consequences
The storage choice must support per-scope keys. Key custody and recovery become a Section 04
concern handed to Section 36. **Encryption is explicitly not a substitute for isolation
enforcement** — it protects stolen media, not runtime access. Invariants `I-71`–`I-72`.

## What Would Change This
A storage or platform choice unable to support per-scope keys — which would be a reason to
reject that choice, not to abandon this decision.
