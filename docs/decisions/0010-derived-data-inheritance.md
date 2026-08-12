# 0010 — Derived Data Inherits the Strictest Source

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 03
**Section:** 03

## Decision
Any derived item — summary, aggregate, embedding, index entry, report, conclusion —
inherits the **strictest classification and narrowest scope** among its sources, and records
complete lineage. Weakening those restrictions requires an explicit, reviewed
transformation. Unknown lineage is treated as the strictest classification present.

## Context
Section 02 found in self-critique that cross-scope aggregation could leak on write. Section
03 generalizes that finding: derivation is the universal leak path, not just aggregation.

## Problem
A summary of Client A's work is a new object. Without a rule, it looks like fresh
NOVA-generated content and may be written anywhere — carrying Client A's content with it.

## Options Considered
1. **Derived data is new data, classified independently.** Simple; the leak path is wide
   open, and it is the leak path most likely to be taken innocently.
2. **Strictest-source inheritance with lineage.** Closes the path structurally; requires
   lineage tracking on every derivation and can over-restrict legitimately generic output.
3. **Case-by-case human classification.** Accurate; unscalable, and fails exactly when
   volume is high.

## Decision Made
Option 2, with reviewed transformation as the escape hatch for genuinely generic material
(procedural knowledge stripped of identifying content).

## Reason
**A summary is a copy.** Any model treating derivation as creating something new will leak,
because the leak requires no malice — only a summarizer doing its job.

## Tradeoffs
**Advantages:** aggregates, embeddings, indexes, caches, and reports are covered by one rule;
lineage enables deletion cascade and leak diagnosis; over-restriction fails safe.
**Disadvantages:** genuinely generic knowledge is over-restricted by default and needs
review to generalize; lineage must be recorded at every derivation, adding overhead;
long derivation chains accumulate restriction.

## Consequences
Lineage is not optional metadata — it is the precondition for deletion being real
(ADR 0013). Invariants `I-27`, `I-28`, `I-31`, `I-45`.

## What Would Change This
A demonstrated method for automatically proving a derived item carries no source-identifying
content. Absent that, review remains the escape hatch.
