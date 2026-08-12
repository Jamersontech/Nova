# 0011 — Provenance, Trust, and Epistemic Status Are Three Axes

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 03
**Section:** 03

## Decision
Record three independent properties on every significant item: **provenance** (where it came
from — immutable), **trust** (how much weight the source earns — revisable), and **epistemic
status** (fact, inference, assumption, unknown). Never collapse them. An item may be treated
as fact only if provenance and trust support it; model confidence never promotes status.

## Context
Constitution §14 requires distinguishing fact, inference, assumption, and unknown. Section 03
must represent that in the data model, alongside the Section 02 rule that external
information is readable without being trustworthy.

## Problem
Systems that record only *what* they know eventually treat "the model said it" as
equivalent to "it is true." The two ideas merge silently and are then impossible to separate
retroactively.

## Options Considered
1. **One "confidence" score.** Simple and familiar; conflates three different things, and a
   number cannot express "high-trust source, but this is an inference."
2. **Provenance plus epistemic status (two axes).** Better; leaves no way to downgrade a
   source that became unreliable without rewriting history.
3. **Three separate axes.** Expresses every real combination; more metadata on every item.

## Decision Made
Option 3.

## Reason
The three vary independently in practice. A trusted integration can supply a stale value —
high trust, high provenance, but epistemically an assumption. Only a three-axis model
represents that, and only a separate mutable trust axis allows re-weighting a source without
falsifying history.

## Tradeoffs
**Advantages:** "AI-generated" can never silently become "fact"; sources can be re-weighted
without rewriting history; audit can reconstruct what NOVA believed and why; stale facts
degrade to assumptions automatically.
**Disadvantages:** three fields on every item; propagation through derivation must be
defined (union of provenance, minimum of trust); more judgment at the boundaries.

## Consequences
Derived items carry the union of source provenance and the *lowest* source trust. Untrusted
content may inform a plan but never escalate it. Invariants `I-37`–`I-41`.

## What Would Change This
Evidence that a two-axis model captures every distinction that matters in practice — which
would require showing trust never changes independently of provenance.
