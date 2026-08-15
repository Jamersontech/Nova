# 0035 — Section 08 Amendments to Accepted Architecture

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 08
**Section:** 08
**Purpose:** Authorize every Section 08 amendment to an Active/Accepted document, in one record,
enumerated individually.

## Decision

Section 08 amends **seven** Active/Accepted documents. [ADR 0034](./0034-the-plan-is-a-security-object.md)
requires them but does not individually authorize them, and both
[ADR 0008](./0008-architectural-governance-model.md) and
[`INVARIANTS.md`](../architecture/INVARIANTS.md) require an ADR for a C3 change.

**Every amendment listed here is Proposed and is marked in place. If this ADR is rejected, every
one of them is removed and the accepted text is restored verbatim.**

## No new architecture document

**`PLANNING_ARCHITECTURE.md` was considered and deliberately not created.**
`ORCHESTRATION_ARCHITECTURE.md` is 129 lines across four sections and already owns the Planner, the
pipeline, the orchestrator contract and the workflow engine. The plan object, its lifecycle and the
composition rule belong to exactly those four sections and are placed in them. Splitting them out
would separate *the plan* from *the pipeline that produces and consumes it* — two documents that
would then have to be read together to answer any question about either, which is the failure the
repository's document boundaries exist to avoid.

**The test applied:** a new document is warranted when the existing one becomes structurally
overloaded. `ORCHESTRATION_ARCHITECTURE.md` gains one subsection and three amendments and remains
coherently about one subject. Section 05 created two documents because model egress and model output
are genuinely different subjects from `MODEL_ARCHITECTURE.md`'s provider-neutrality; Section 06
created one because agent governance is a different subject from agent runtime shape. **Section 08's
subject is the pipeline that already lives here.**

## The amendments

### 1. `ORCHESTRATION_ARCHITECTURE.md` (Section 02 · Active) — §1, §2, §4

**Amended:** §1's Planner row gains the plan object; a new **§2.1** defines the plan schema,
identity, immutability and lifecycle; a new **§2.2** defines envelope authorization, per-action
checking and composition; §2's pipeline gains the re-authorization loop; §4's workflow rules gain
resumption re-checking. **Why required:** ADR 0034's entire decision. `:31`'s *"A plan: steps,
dependencies, required rights"* was the only enumeration in the repository.
**Amendment status:** **Proposed**, marked in place.

### 2. `PERMISSION_ARCHITECTURE.md` (Section 02 · Active) — §5

**Amended:** the approval section distinguishes an **envelope approval** from an action approval.
**Why required:** `:151`'s *"one action, in one context, at one time"* and
`EXECUTION_ARCHITECTURE.md:180`'s *"James approves the plan"* described different objects with no
statement of how they relate. **The one-action rule is preserved unchanged**; what is added is that a
plan approval is an envelope and never becomes blanket authorization.
**Amendment status:** **Proposed**, marked in place.

### 3. `AUTHORIZATION_MODEL.md` (Section 03 · Active) — §3

**Amended:** a note that the ten-step sequence evaluates **actions**, that plan authorization is a
separate envelope decision, and that neither substitutes for the other. **Why required:** a reader
reconciling *"the full plan is authorized as a unit"* with ten singular steps finds nothing here.
**The ten steps are unchanged and the PDP is not made a composition engine.**
**Amendment status:** **Proposed**, marked in place.

### 4. `RELIABILITY_ARCHITECTURE.md` (Section 02 · Active) — §3, §4

**Amended:** §3's resumption rule gains binding re-checking; §4 gains plan-level retry semantics.
**Why required:** §3's *"Resumption restarts from the last verified step"* was silent on whether the
approval still held after earlier steps changed the world, and plan-level idempotency was undefined
while `I-104` defined it for model calls and tool metadata defined it for tools.
**Amendment status:** **Proposed**, marked in place.

### 5. `INVARIANTS.md` (Section 03 · Active)

**Amended:** `I-112`–`I-113` added under a Section 08 heading. **`I-01`–`I-111` unmodified.**
**Amendment status:** **Proposed**, marked in place.

### 6. `THREAT_MODEL.md` (Section 03 · Active)

**Amended:** `T-36` (plan-boundary abuse) added. `T-03`'s and `T-19`'s residuals are **not
reduced**. **Amendment status:** **Proposed**, marked in place.

### 7. `KNOWN_RISKS.md` (Section 03 · Active) — §3.8

**Amended:** Section 08's residual risks recorded. **Amendment status:** **Proposed**, marked in
place.

## Tradeoffs

**Advantages:** seven documents rather than thirteen, because Section 08 gives an existing set of
mechanisms a carrier rather than adding mechanisms; no new document, no new invariant family, no
new audit authority, no PDP change.

**Disadvantages:** `ORCHESTRATION_ARCHITECTURE.md` roughly doubles in length and becomes the longest
Section 02 document. If Section 12 (Automation & Workflow Engine) later needs comparable depth on
workflows, the split deferred here will have to be revisited — recorded so that decision is made
deliberately rather than discovered.

### 8. `PROVENANCE_AND_TRUST.md` §1.1 and `MODEL_TRUST_AND_AUTHORITY.md` §3 — **"untrusted content" is a provenance class** *(added 2026-08-15)*

***Folded into this ADR rather than minting a new one.*** This is the plan-taint family: `I-112`
makes the plan carry `I-99`'s union, and this settles what the union is *read for*. Splitting one
taint decision across two ADRs would make the family harder to follow.

**Found by implementation, not review.** Building the vertical slice showed that the Planner is a
model, so `I-99` gives **every plan** `model.generated` provenance at Low trust and
`min(anything, Low) = Low`. **A plan James stated directly is indistinguishable *by trust* from
one shaped by injected content**, so reading `I-40`/`I-100`/`MT-7`'s *"derived from untrusted
content"* as a trust level would ceiling every action above `PREPARE` permanently and demand an
approval *naming a source* that does not exist — making `PERMISSION_ARCHITECTURE.md` §5's standing
approvals unreachable.

**Amended:** *"untrusted content"* is defined as a **provenance class** — `external.web`,
`client.supplied`, `integration.supplied` — not a trust level. **Why required:** `I-40` is one
sentence joining *"**External** content may inform a plan"* to *"a plan influenced by
**untrusted** content"*; the provenance reading makes it internally consistent and the trust
reading makes its two clauses disagree. **`I-40`, `I-99`, `I-100` and `MT-7` are unamended** —
this defines a term they already use, exactly as Section 09 defined *source identity* for `I-110`.

**Not a trust downgrade and not an exemption.** A Low-trust plan remains Low trust; the argument
envelope, classification egress, scope containment, binding envelope, approval and risk ceilings
are each evaluated independently and unchanged. Provenance cannot be shed — immutable (`I-38`),
unioned at every hop (`I-99`), surviving persistence (`I-111`) — so this is not a laundering path.
**Amendment status:** **Proposed**, marked in place. Evidence:
[`slice/FINDINGS.md`](../../slice/FINDINGS.md) finding 2, with ten tests proving both sides.

**Recorded, not acted on:** `I-109` says its bound properties are checked *"against current
state"*, but at execution **eight of the ten are independently recomputable and two — the argument
envelope and the cost ceiling — are authorization-issued values with no independent source**.
Harmless (they cannot drift) but the phrasing implies otherwise. **No invariant or decision is
created for this**; it is noted for a future revision of `I-109`.

## Consequences

Accepting `0034`–`0035` accepts these seven amendments. **`EXECUTION_ARCHITECTURE.md` is
deliberately not amended** — its *"James approves the plan"* becomes correct rather than ambiguous
once §5 defines an envelope approval, so no text there needs to change.

## What Would Change This

Discovering an amendment not listed here — fixed by adding the row before acceptance, not by leaving
it unrecorded.
