# 0033 — Section 07 Amendments to Accepted Architecture

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 07
**Section:** 07
**Purpose:** Implement `S7-D2`–`S7-D5` and authorize every Section 07 amendment to an
Active/Accepted document, in one record, enumerated individually.

## Decision

**Three rules and one labelling requirement**, all extensions of mechanisms that already exist.
None introduces a new concept.

**1. `model.generated` is quarantined (`S7-D2`).** It joins `external.web`, `client.supplied` and
`integration.supplied` in [`MEMORY_MODEL.md`](../architecture/MEMORY_MODEL.md) §4.1's **existing**
quarantine. Model-generated memory is not safe merely because its inputs were internal, because it
carries no external provenance, because a trusted model produced it, or because it was generated
inside NOVA. **No new quarantine concept is created.**

**2. Delegate memory carries its delegation ancestry, and survival is not authority (`S7-D3`).**
A broader ancestor **must not** treat a narrower delegate's memory as more authoritative than the
authority and trust state under which it was created. Ancestry is preserved as provenance metadata,
reusing `I-107`'s `ancestry` field and `I-27`'s strictest-source rule. **Delegate memory is not
invalid** — it is scope-owned and survives the child correctly. **No separate authority hierarchy
for memory is created.**

**3. `I-99`'s union provenance and lowest trust survive persistence (`S7-D4`, `I-111`).**
Persistence must not discard provenance, collapse multiple sources into one, raise trust, remove
taint, or replace the union with the latest writer alone. Retrieval must restore what `I-99`,
`I-100`, `I-101`, `I-27`, `I-29` and the quarantine and elevation rules need in order to be
enforced. **This is a security property, not an implementation detail.**

**4. Retrieval surfaces revoked creating authority (`S7-D5`).** Memory created under an authority
later revoked is **retained** under existing lifecycle rules, and retrieval **exposes the revocation
state**. Nothing is automatically deleted, downgraded, invalidated, promoted, or reclassified. The
consuming authority decides; where fresh authorization is required, the existing rules control.
**This is a retrieval-labelling rule and needs no invariant** — no new property is asserted, only
that an existing fact is not withheld at the point of use.

## Context

Section 07 reconstructed context and memory from five Active documents and found them densely
specified. Four gaps remained after [ADR 0032](./0032-trust-promotion-authority.md) closes the
critical one.

## Problem

**`model.generated` was absent from the quarantine set.** `I-99` partly covered it — model output
inherits its inputs' provenance, so output derived from web content *is* quarantined. But output
derived from purely internal inputs was Low-trust and **unquarantined**: silently mergeable into
general context and eligible for derivation into higher-trust items, both of which quarantine
specifically prevents. Trust alone does not do quarantine's work.

**Nothing bounded what a delegate's residue later means.** Section 06 bounded what a child may
*do*. Memory is scope-owned (`SCOPE_AND_IDENTITY_MODEL.md` §2), so a child's memory correctly
survives it — but no rule stopped an ancestor with broader authority from reading that memory as
though it carried the ancestor's authority.

**`I-99` was stated at execution time, not at persistence.** It says taint survives "whether or not
it is stored" — but nothing required the *storage layer* to persist the union or *retrieval* to
restore it. `MEMORY_MODEL.md` §4 labels retrieved items with singular provenance and trust fields,
not `I-99`'s union. **`I-100`'s untrusted-derived tool-argument ceiling depends on this**, so it
was load-bearing and unstated.

**Revocation was invisible at retrieval.** Correct to retain (`I-38`), silent about disclosure.

## Options Considered

**For `model.generated`:** exclude it (status quo); quarantine only model output with external
ancestry; quarantine all of it. **For delegate memory:** silence; invalidate on child termination;
label and cap authority. **For taint:** rely on `I-99` as written; state persistence explicitly.
**For revocation:** silence; automatic downgrade; label at retrieval.

## Decision Made

Quarantine all model-generated memory · label and cap delegate memory · state persistence
explicitly · label revocation at retrieval.

## Reason

**Quarantining all model-generated memory makes an existing rule enforceable rather than
aspirational.** `MEMORY_MODEL.md` §2 already says Semantic memory is *"created by curation from
verified sources"* — this is what makes that true, by ensuring model output cannot become durable
higher-trust knowledge without passing ADR 0032's promotion. The narrower option — quarantine only
model output with external ancestry — fails because the dangerous case is not where the content
came from but that **no human checked it**, and internal origin is exactly the reason an
implementer would skip the check.

**Invalidating delegate memory on child termination was rejected** because it contradicts
scope ownership: the agent never owned it, so terminating the agent orphans nothing. The defect was
never survival; it was that survival was being read as inherited authority. Labelling fixes what is
actually wrong.

**Automatic re-weighting on revocation was rejected** for the reason `DATA_LIFECYCLE.md` §4 already
gives about contradictions: silent resolution is how poisoning succeeds. Revocation happens for
many reasons, and only some of them impeach what was learned. Surfacing it lets the consuming
authority decide; downgrading it automatically would be NOVA deciding.

## Tradeoffs

**Advantages:** every rule extends a mechanism that already exists; no new concept, component,
authority, or audit category; `I-100`'s ceiling gains the substrate it depends on; the
scope-ownership model is preserved rather than qualified.

**Disadvantages:** **quarantining all model-generated memory is a real operational cost** — durable
knowledge now arrives predominantly through curation and verified sources, and the convenient path
of letting an agent's good summary become durable knowledge is closed. Combined with ADR 0032, more
work lands in front of James. **Union provenance grows with derivation depth**, so a
much-derived item carries a long ancestry, with storage and retrieval cost that
`SCALE_AND_COST_ARCHITECTURE.md` §2 does not currently model. And **revocation labelling adds a
judgment at every retrieval** where a revoked authority is in an item's history — surfaced honestly,
but surfaced often.

## The amendments

**Every amendment listed here is Proposed and is marked in place. If this ADR is rejected, every
one of them is removed and the accepted text is restored verbatim.**

### 1. `MEMORY_MODEL.md` (Section 03 · Active) — §4, §4.1, §4.3

**Amended:** `model.generated` added to §4.1's quarantine set; a new §4.3 states the trust-promotion
operation (ADR 0032); §4's retrieval rules gain union-taint restoration, delegation ancestry, and
revoked-authority labelling. **Why required:** ADR 0032 and `S7-D2`–`S7-D5`.
**Amendment status:** **Proposed**, marked in place.

### 2. `PROVENANCE_AND_TRUST.md` (Section 03 · Active) — §2, §3

**Amended:** §3's *"trust… may change"* gains its authority (ADR 0032); §2's provenance content
gains delegation ancestry and the persistence requirement. **Why required:** §3 as accepted names a
mutable axis with no owner — the critical finding. **Amendment status:** **Proposed**, marked in
place.

### 3. `MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md` (Section 02 · Active) — §5, §7

**Amended:** hygiene gains the promotion rule; retrieval discipline gains taint restoration.
**Why required:** §7 is the canonical retrieval list a model-call assembler works from; leaving it
silent on taint would let an implementer satisfy §7 while dropping what `I-100` needs.
**Amendment status:** **Proposed**, marked in place.

### 4. `IDENTITY_AND_AUTHORITY.md` (Section 02 · Active) — §5

**Amended:** a trust-promotion row. **Why required:** ADR 0032 makes it C3; §5 is where specific
authorities live. **No new change class.** **Amendment status:** **Proposed**, marked in place.

### 5. `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` (Section 03 · Active) — §5.1

**Amended:** the Memory category gains trust promotion and promotion refusal. **Why required:**
§5.1 is the canonical auditable list. **No new audit authority** — ADR 0023's three cover it.
**Amendment status:** **Proposed**, marked in place.

### 6. `INVARIANTS.md` (Section 03 · Active)

**Amended:** `I-110`–`I-111` added. **`I-01`–`I-109` unmodified.** **Amendment status:**
**Proposed**, marked in place.

### 7. `THREAT_MODEL.md` (Section 03 · Active)

**Amended:** `T-35` (trust-promotion abuse) added; `T-10`'s residual is **not reduced**.
**Amendment status:** **Proposed**, marked in place.

### 8. `KNOWN_RISKS.md` (Section 03 · Active) — §3.7

**Amended:** Section 07's residual risks recorded. **Amendment status:** **Proposed**, marked in
place.

## Consequences

Accepting `0032`–`0033` accepts these eight amendments. **`DATA_LIFECYCLE.md` and
`CONTEXT_ARCHITECTURE.md` are deliberately not amended** — the lifecycle stages are unchanged by a
trust operation, and Section 07 found **no context decision to make**: `CONTEXT_ARCHITECTURE.md`
already answers every context question Section 07 raised.

Invariants: `I-110`–`I-111` (new). Threats: `T-35`.

## What Would Change This

Evidence that universal quarantine of model-generated memory makes durable knowledge accumulation
impractical — which would argue for a defined, pre-authorized curation path rather than for
un-quarantining model output.
