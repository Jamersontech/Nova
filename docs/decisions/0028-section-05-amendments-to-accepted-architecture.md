# 0028 — Section 05 Amendments to Accepted Architecture

**Status:** **Accepted**
**Proposed:** 2026-08-14 — Section 05
**Accepted:** 2026-08-14 by James
**Section:** 05
**Purpose:** Formally authorize every Section 05 amendment to an Active/Accepted document, in one
record, enumerated individually.

## Decision

Section 05 amends **thirteen** Active/Accepted documents. ADRs `0024`–`0027` require those
amendments but do not individually authorize them, and both
[ADR 0008](./0008-architectural-governance-model.md) and
[`INVARIANTS.md`](../architecture/INVARIANTS.md) require an ADR for a C3 change.

**Every amendment listed here was accepted by James on 2026-08-14 together with this ADR.** They
were marked Proposed in place while this ADR was pending; that marking was cleared on acceptance.
Had this ADR been rejected, every one of them would have been removed and the accepted text
restored verbatim.

## Context

Section 04 closed the same gap with [ADR 0022](./0022-section-04-amendments-to-accepted-architecture.md)
after its final review found amendments accumulating inside Active documents with no recorded
authority. Section 05 records the authority up front rather than discovering the gap at the end.

## Problem

An amendment sitting inside an Active document is indistinguishable from accepted architecture
unless something records otherwise. Accepting `0024`–`0027` without enumerating what they change
would ratify thirteen documents' worth of edits silently.

## The amendments

### 1. `PERMISSION_ARCHITECTURE.md` (Section 02 · Active) — §2

**Amended:** the enforcement-point diagram and text show **six** enforcement points; model egress
is added. **Why required:** ADR 0024's entire decision. Leaving §2 at five would make the canonical
enforcement list contradict `I-94`. **Amendment status:** **Accepted** 2026-08-14.

### 2. `MASTER_ARCHITECTURE.md` (Section 02 · Active) — §4 and §5

**Amended:** the system diagram gains a Policy arrow from the Model Gateway; the §5 Model Gateway
row gains egress authorization enforcement and provider-credential custody, and loses nothing.
**Why required:** §4's arrows are the canonical statement of what consults Policy, and §5's table
is the canonical statement of what each service owns. **Amendment status:** **Accepted** 2026-08-14.

### 3. `MODEL_ARCHITECTURE.md` (Section 02 · Active) — §2, §3, §4

**Amended:** §2's "does not own — whether the request is permitted" gains where that is enforced;
§3's data-policy row is marked a **constraint on the candidate set** rather than one factor among
eight, and the advisory verification sentence points at ADR 0026; §4's fallback rows are bounded by
the permitted provider set. **Why required:** ADRs 0024 and 0026. §4 as accepted permits failover
to "an equivalent-profile provider" with no data-policy qualification — read literally it permits
egress to an unpermitted provider during degradation. **Amendment status:** **Accepted** 2026-08-14.

### 4. `TOOL_AND_INTEGRATION_ARCHITECTURE.md` (Section 02 · Active) — §2, §5

**Amended:** §2's tool-definition fields gain a declaration of which arguments are
consequence-determining; §5 names the control-plane credential class. **Why required:** ADR 0025
(`I-100` is unenforceable if tools do not declare which arguments it governs) and ADR 0027 (§5 as
accepted has no place for a credential that is not scope-bound). **Amendment status:** **Accepted** 2026-08-14.

### 5. `SECURITY_BOUNDARIES.md` (Section 02 · Active) — §2, §5

**Amended:** the boundary table gains a **model-provider boundary** row; the assumed-compromise
table gains a Model Gateway row. **Why required:** §2 claims to enumerate *every* boundary and what
authorization each crossing requires. Model egress is a boundary crossing to a third party and was
absent. **Amendment status:** **Accepted** 2026-08-14.

### 6. `PROVENANCE_AND_TRUST.md` (Section 03 · Active) — §6

**Amended:** requirement 2 ("never let provenance be lost in derivation") is extended to model
output whether or not it is stored. **Why required:** ADR 0025 rule 1. As accepted, the
requirement reads on stored derived items, leaving the transient model-output path — the path
injection actually travels — unlabelled. **Amendment status:** **Accepted** 2026-08-14.

### 7. `CROSS_SCOPE_DATA_RULES.md` (Section 03 · Active)

**Amended:** the model prompt is named as a cross-scope join point, governed by the same
decompose-and-aggregate rule as storage and output. **Why required:** ADR 0024's `I-95`. As
accepted the document governs storage, aggregation, derived data, side channels and cross-domain
flow, and does not mention the model request — a buffer holding two clients' content sent to one
third party. **Amendment status:** **Accepted** 2026-08-14.

### 8. `RELIABILITY_ARCHITECTURE.md` (Section 02 · Active) — §4

**Amended:** retry discipline gains model-call semantics: a retried or rerouted model call
re-issues no side effect, and every attempt is separately authorized and accounted. **Why
required:** §4's idempotency discipline is written about tools. A model call is idempotent in
itself and not in its consequences. **Amendment status:** **Accepted** 2026-08-14.

### 9. `SCALE_AND_COST_ARCHITECTURE.md` (Section 02 · Active) — §4

**Amended:** cost ceilings on the model path terminate and escalate rather than degrade, and fail
closed above `PREPARE`. **Why required:** §4 as accepted requires ceilings that "terminate and
escalate rather than continue" for sandboxes, agent loops and workflows; the model path's ceiling
behaviour and its interaction with risk class were unstated. **Amendment status:** **Accepted** 2026-08-14.

### 10. `SYSTEM_LAYERS.md` (Section 02 · Active)

**Amended:** the Identity & Policy spine reaches the Model Gateway. **Why required:** the spine
table lists which layers each spine is consulted by; ADR 0024 adds one. **Amendment status:** **Accepted** 2026-08-14.

### 11. `INVARIANTS.md` (Section 03 · Active)

**Amended:** `I-94`–`I-105` added under a Section 05 heading. **Why required:** every ADR above states invariants. `I-01`–`I-93` are
**unmodified**. **Amendment status:** **Accepted** 2026-08-14.

### 12. `THREAT_MODEL.md` (Section 03 · Active)

**Amended:** `T-28`–`T-32` added; `T-03` and `T-15` gain cross-references and neither residual is
reduced. **Why required:** four new named components and boundaries. **Amendment status:** **Accepted** 2026-08-14.

### 13. `KNOWN_RISKS.md` (Section 03 · Active)

**Amended:** Section 05's residual risks recorded — taint-labelling correctness, envelope width,
correlated verifier capture, provider-side correlation. **Why required:** the document exists to
record where the architecture is weakest, and Section 05 adds four places.
**Amendment status:** **Accepted** 2026-08-14.

## Tradeoffs

**Advantages:** the amendment surface is visible in one place before acceptance rather than
reconstructed after; rejection is a clean operation with a defined result; no accepted invariant is
weakened — `I-23` in particular is preserved unamended by ADR 0027's construction.

**Disadvantages:** thirteen documents is a wide surface for one section, and a wide surface is
harder to review than a narrow one. The width is a consequence of model egress having been
under-specified across many documents rather than wrongly specified in one.

## Consequences

James accepted `0024`–`0028` together on 2026-08-14, so all thirteen amendments are accepted
architecture and their in-place Proposed markings were cleared. Changing any of them now requires a
superseding ADR, not an edit.

## What Would Change This

Discovering an amendment not listed here. That is a defect in this record and is fixed by adding
the row before acceptance, not by leaving it unrecorded.
