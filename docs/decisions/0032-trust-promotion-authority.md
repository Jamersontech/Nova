# 0032 — Trust Promotion Authority

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 07
**Section:** 07
**Resolves:** `S7-D1`

## Decision

**Raising an item's trust is an explicitly authorized operation. It is never automatic, never
performed by an agent, and never model-mediated (`I-110`).**

The construction is `I-30`'s, reused rather than reinvented: *downward reclassification is never
automatic and never performed by an agent.* Trust promotion is governed identically, and is a **C3**
change.

**Promotion is never inferred** from repetition, model confidence, consensus among model calls,
internal origin, or the fact that an item was produced inside NOVA.

**Every promotion records seven things**, or it does not happen:

```text
1. the item promoted            5. the resulting trust level
2. its immutable provenance     6. the authority responsible
3. the evidence relied on       7. the trace identity
4. the authoritative source
```

**`system.verified` may be assigned only after checking the item against an authoritative source**,
which this ADR defines rather than leaving to an implementer:

| # | Requirement on an authoritative source |
| --- | --- |
| 1 | **External to the model's own output.** A model is never a source for its own claim |
| 2 | **Identifiable.** A named, referenceable source — not "the literature", not "context" |
| 3 | **The verification is reproducible and auditable.** Someone can repeat the check and reach the same answer |
| 4 | **The source itself satisfies the applicable trust and data-policy requirements.** A low-trust source cannot confer high trust |

**Two consequences stated so they cannot be argued around:**

- **A model saying "I verified this" is never evidence of verification.** `I-102` already bars a
  model check from promoting epistemic status; this bars it from promoting **trust**, which is the
  other half of `I-39`'s gate.
- **A model-generated summary of an authoritative source is not the authoritative source.** The
  summary is `model.generated` (`I-99`); the source is what must be checked.

**Enforcement point:** the memory write / revalidation path, **before** the elevated item becomes
eligible for downstream use.

**On uncertainty, missing evidence, an unidentifiable source, or a failed check: the promotion is
denied.** The item retains its existing trust. The requested elevated status is **not** silently
retained, not applied provisionally, and not applied pending review.

## Context

`I-39` gates fact status on *"provenance **and** trust"*. `I-38` makes provenance immutable.
`I-30` owns classification lowering. `I-09`/`I-10` own approval and grants. `I-102` bars a model
check from promoting epistemic status. `I-35` owns scope elevation.

## Problem

**Trust was the one axis in `I-39`'s gate with no owner.**

[`PROVENANCE_AND_TRUST.md`](../architecture/PROVENANCE_AND_TRUST.md) §3 states trust *"may change
without rewriting history."* [`MEMORY_MODEL.md`](../architecture/MEMORY_MODEL.md) §4.1 states
revalidation *"either **promotes** it (a verified source now supports it), leaves it quarantined,
or marks it disputed."* **Neither names who may do it, under what authority, at what change class,
or with what record.** And `system.verified` — the High-trust provenance — was defined as *"NOVA
checked it against an authoritative source"* with **neither "NOVA" nor "authoritative source"
defined anywhere in the repository.**

The attack this permits is precise. Untrusted content enters at Low trust and is correctly
contained — quarantined, `PREPARE`-ceilinged, barred from fact status. Then an unowned promotion
raises its trust or re-provenances it `system.verified`. `I-39`'s gate now passes. **No invariant
is violated, because no invariant governed the operation**, and the audit trail shows a legitimate
revalidation. Everything downstream — planning, tool arguments, risk classification — consumes it
as fact.

**The architecture owned every other lever with unusual care and left this one open.** That
asymmetry is what makes it worth an ADR of its own rather than an amendment.

## Options Considered

1. **Status quo — leave promotion unowned.** Zero cost. Leaves the containment of Sections 03–06
   defeatable by a single unguarded write, invisibly.
2. **Forbid promotion entirely.** Maximally safe and wrong: an item that was genuinely unverified
   and is now genuinely verified must be able to say so, or NOVA can never learn. It would also
   make `MEMORY_MODEL.md` §4.1's revalidation mechanism dead text.
3. **Evidence-bound promotion, authorized and recorded, with "authoritative source" defined.**
   Promotion exists, is C3, requires named non-model evidence, records seven fields, and fails
   closed.
4. **Grant-mediated promotion** — a "may promote trust" right granted like any other. Fits the
   existing grant model; and it creates a standing capability to convert untrusted content into
   trusted content, held by something other than James. That is the shape of defect every prior
   section's review has found: a capability that exists, bounded by an instruction not to misuse
   it.

## Decision Made

Option 3.

## Reason

**The dangerous cases are excluded mechanically; only the judgment is human.** An engineer
implementing this does not decide what qualifies as authoritative — they implement four checks
(non-model, identifiable, reproducible, policy-compliant), each of which is mechanical. **Whether a
particular named source is authoritative for a particular claim is decided per promotion by the
authorizing human and recorded**, not configured once in code as a whitelist an attacker could
grow. That split is what makes the phrase implementable rather than decorative.

**Option 4 was rejected on the pattern, not on the mechanics.** A standing promotion right is a
capability spanning the trust boundary, forbidden by rule. Sections 04, 05 and 06 each removed a
capability rather than restricting it — the control-plane audit partition, control-plane
credentials, issuance-time verification. This follows the same discipline.

**Fail-closed matters more here than usual.** A promotion that half-succeeds — status retained
"provisionally", or pending review — is indistinguishable downstream from one that succeeded, and
downstream is where `I-39` reads it.

## Tradeoffs

**Advantages:** the `I-39` gate is fully owned for the first time; `I-30`'s construction is reused
rather than a new one invented; "authoritative source" stops being an undefined phrase; the
promotion record makes every trust increase reconstructible; no new component and no new trust
dependency.

**Disadvantages:** **NOVA learns more slowly.** Every trust increase now needs an authorized
operation with named evidence, so knowledge that would previously have accreted quietly now
requires James. This is friction on the most common benign path in order to close the most
dangerous rare one, and it will be felt. There is also a **new approval-fatigue surface**: if
promotions are frequent, they train exactly the reflexive approval
[`KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) records as a security failure — which argues
for promotions being rare, and for most durable knowledge arriving through curation from sources
that were verified when first recorded rather than promoted afterwards.

**And it does not make memory trustworthy.** It makes *increases* in trust attributable. A source
that was wrongly judged authoritative at promotion time produces a high-trust wrong item, and
nothing detects that.

## Consequences

- [`PROVENANCE_AND_TRUST.md`](../architecture/PROVENANCE_AND_TRUST.md) §3 and
  [`MEMORY_MODEL.md`](../architecture/MEMORY_MODEL.md) §4.1 are amended — authorized by
  [ADR 0033](./0033-section-07-amendments-to-accepted-architecture.md).
- [`IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md) §5 gains a trust-promotion
  row. **No new change class is created.**
- **Trust promotion is auditable under the existing model.** A promotion concerns a client scope,
  so its decision is `W-2` and its write is `W-1` in that scope's partition (ADR 0023). **No new
  audit authority.**
- `I-38` is untouched: **provenance remains immutable.** A promotion adds a verification record and
  a new trust value; it never rewrites where the item came from.
- Lowering trust is deliberately **not** governed here. Restriction is not gated like elevation —
  the same asymmetry `I-93` and ADR 0030 already apply.

Invariants: `I-110` (new). `I-27`, `I-30`, `I-35`, `I-38`, `I-39`, `I-99`, `I-102` untouched.

## What Would Change This

Evidence that promotion is so frequent in practice that C3 governance produces reflexive approval —
which would argue for a narrow, pre-declared class of automatic verifications against a fixed
authoritative source, recorded as a superseding ADR, and **not** for returning promotion to an
unowned state.
