# 0022 — Section 04 Amendments to Accepted Architecture

**Status:** Proposed
**Proposed:** 2026-08-13 — Section 04
**Section:** 04
**Purpose:** Formally authorize the Section 04 amendments to Active/Accepted documents that ADRs
`0016`–`0021` require but do not explicitly authorize.

## Decision
Section 04 amends **nine** Active/Accepted documents. **ADRs `0016`–`0021` do not explicitly
authorize those amendments**, and both [ADR 0008](./0008-architectural-governance-model.md) and
[`INVARIANTS.md`](../architecture/INVARIANTS.md) line 10 require an ADR for a C3 change. This ADR
supplies that authority for all of them in one record, enumerated individually below.

**Every amendment listed here is Proposed. If this ADR is rejected, every one of them is removed
and the accepted text is restored verbatim.**

## Context
The Section 04 final reviews found that amendments to accepted documents had accumulated without
recorded authority. Two of them ([`MASTER_ARCHITECTURE.md`](../architecture/MASTER_ARCHITECTURE.md),
[`SYSTEM_LAYERS.md`](../architecture/SYSTEM_LAYERS.md)) were named in
[ADR 0017](./0017-isolation-independent-of-pdp.md); the rest were not named anywhere. James raised
this as `S4-P3` and directed that a single ADR close the chain.

## Problem
An amendment sitting inside an Active document is indistinguishable from accepted architecture
unless something records otherwise. Seven such amendments had no authorizing ADR, and one
(`SECURITY_BOUNDARIES.md`) was attributed to ADR 0017 without appearing in it. Accepting
`0016`–`0021` in that state would have ratified them silently — the exact failure the governance
model exists to prevent.

## Options Considered
1. **Per-document ADRs.** Seven or eight records. None can be accepted independently of the
   others, since each exists only because `0016`–`0021` exist; and `AI_TERMINOLOGY.md` spans
   several ADRs, so it has no natural home. Multiplies records and drift surface.
2. **One enumerating ADR.** This document. One decision, one place, accepted or rejected with
   `0016`–`0021`.
3. **Loosen ADR 0008 or the `INVARIANTS.md` rule** to permit section-scoped amendment without a
   per-change ADR. Rejected — it removes the friction that surfaced the problem, and is itself a
   C3 change to the governance model.

## Decision Made
Option 2.

## The amendments authorized

Each row states the document, the exact area amended, why Section 04 requires it, its relationship
to `0016`–`0021`, and its status. **All are Proposed.**

### 1. `MASTER_ARCHITECTURE.md` (Section 02 · Active) — §5, NOVA Core table

**Amended:** (a) a **Data-Access Boundary** row added; (b) the **Observability** row narrowed —
"Logs, traces, audit records" becomes collection and routing of audit events, with owning or
reading the audit corpus explicitly excluded.

**Why required:** (a) Section 04 makes the storage scope binding load-bearing (`I-61`, `I-78`,
`C-11`) and an unowned binding is one application code ends up setting. (b) James's `S4-P2`
decision (Option D) places audit reading with James directly, per scope, which the accepted row
contradicts.

**Relationship to 0016–0021:** (a) required by [ADR 0017](./0017-isolation-independent-of-pdp.md).
(b) required by [ADR 0020](./0020-keys-mirror-the-scope-tree.md) and `E-12`/`E-13`.

**Amendment status:** **Proposed.** Both marked in place with footnotes ¹ and ². **Removed, and the accepted
text restored verbatim, if this ADR is rejected.**

### 2. `SYSTEM_LAYERS.md` (Section 02 · Active) — Knowledge & Data; §5

**Amended:** a paragraph placing the Data-Access Boundary at the layer entrance; a note that
enforcement point 5 is evaluated per data access; a note that a token failing integrity detection
is not valid at any of the five points.

**Why required:** the boundary must have a layer location; F-1 established that point 5 is
per-access, not per-request; `I-87` binds all five points.

**Relationship to 0016–0021:** ADRs `0016`, `0017`, `0018`.

**Amendment status:** **Proposed**, marked in place. Removed if this ADR is rejected.

### 3. `SECURITY_BOUNDARIES.md` (Section 02 · Active) — §4, trust zones

**Amended:** the Context service and the Data-Access Boundary named in the TRUSTED zone.

**Why required:** Section 04 makes specific claims about both — that the Context service is a
critical trusted component of the same standing as the PDP whose compromise is unmitigated
(`T-23a`), and that the boundary must never be the agent runtime, a sandbox, or application code
(`I-61`, `I-78`). A reader must be able to locate both. **Neither is a new grant**: both were
already inside NOVA Core and therefore already trusted.

**Relationship to 0016–0021:** ADR `0017`. **This ADR supplies the authority ADR 0017 does not —
`SECURITY_BOUNDARIES.md` is absent from ADR 0017's own amendment table.**

**Amendment status:** **Proposed**, marked in place. Removed if this ADR is rejected.

### 4. `ai/AI_TERMINOLOGY.md` (Section 01 · Active) — Section 04 term block; distinctions table

**Amended:** independence language qualified to match H-2; **Data-Access Boundary** and **Context
Token Integrity** added; **Scope Binding** updated to the channel/binding model; **Break-Glass**
corrected to state the control-plane confinement and that it never authorizes client-data access;
three distinctions rows.

**Why required:** Section 01 makes this file canonical for terminology and requires new terms to
be added in the session that introduces them. The Break-Glass correction is not optional — the
prior text contradicted `I-75`, which is absolute.

**Relationship to 0016–0021:** spans `0016`, `0017`, `0018`, `0021` — which is why no single one
of them is its natural home.

**Amendment status:** **Proposed**, block marked. Removed if this ADR is rejected.

### 5. `INVARIANTS.md` (Section 03 · Active) — `I-60`–`I-90`; `[PHYS]` dependency table

**Amended:** invariants `I-60`–`I-90` added; `[PHYS]` dependency rows added; `I-61`, `I-78`, `I-83`
amended (`I-83` extended to state that audit-key access inherits nothing from data-key authorization); `I-67` extended for cross-scope audit-review step-up (`H-1` Option 3) and `I-88` finalized
for the audit-write model — execution-scoped under `S4-P5` (C+D), then authorized-by-construction
under `S4-P6` (Option A), which removed the release decision and with it the bootstrap base case; the `I-70`/`I-81` marking
rationale corrected; `I-89` split into `I-89` (architectural, **not** `[PHYS]`) and `I-90` (the mechanism dependency, `[PHYS]`) so that `[PHYS]` marks genuine physical dependency rather than architectural choice. **All are within the `I-60`–`I-90` Section 04 range — no accepted invariant
(`I-01`–`I-59`) is amended, and `I-18`, `I-47` and `I-82` are untouched.**

**Why required:** Section 04's requirements are expressed as invariants, and this file is where
invariants live. Its own line 10 states that any change is C3 and requires an ADR — **this ADR is
that ADR.**

**Relationship to 0016–0021:** all six collectively.

**Amendment status:** **Proposed**, block marked. Removed if this ADR is rejected — `I-01`–`I-59` are
unaffected in every case.

### 6. `THREAT_MODEL.md` (Section 03 · Active) — `T-19` rewrite; `T-20`–`T-26`

**Amended:** `T-19` rewritten (audit-independence claim withdrawn, M-6); `T-20`–`T-22` added,
with `T-20a` (compromise of James's audit-reading session) added under `T-20` per `H-2`; `T-23`
split into `T-23a`/`T-23b`/`T-23c`; `T-24` (compromised PEP), `T-25` (compromised Data-Access
Boundary) and `T-26` (compromised Observability) added; `T-24`'s containment claim qualified as
dependent on `D-33` being implemented and verified (`M-A`), and `T-26`'s bootstrap residual retired
under `S4-P6`. **No `T-27` was created** — `H-2` resolves into `T-20` because Option D leaves no
reader component to threat-model separately.

**Why required:** Section 04 introduces trusted components and withdraws a previously recorded
mitigation. Registering a trusted component without a threat entry, or leaving a withdrawn claim
standing, are both defects the reviews found.

**Relationship to 0016–0021:** `0017` (T-19, T-23, T-25), `0018` (T-20, T-21), `0020` (T-26),
`0021` (T-22).

**Amendment status:** **Proposed.** Removed if this ADR is rejected — `T-01`–`T-18` are unaffected.

### 7. `AUTHORIZATION_MODEL.md` (Section 03 · Active) — §7

**Amended:** independence qualified to "independent of this PDP, not of the Context service"; an
explicit statement that structural isolation does not remove or replace the Data Access PEP.

**Why required:** without it, an accepted document carries the H-2 claim that was withdrawn, and
nothing in the accepted set forbids substituting connection-scope binding for the PEP.

**Relationship to 0016–0021:** ADRs `0016`, `0017`.

**Amendment status:** **Proposed.** Removed if this ADR is rejected.

### 8. `PERMISSION_ARCHITECTURE.md` (Section 02 · Active) — §2

**Amended:** a note that all five enforcement points remain in force after Section 04; the
token-integrity requirement (`I-87`) applied at each point.

**Why required:** ADR 0017 adds a layer beneath the Data access PEP, and the accepted document
must state that the PEP survives. `CT-2` levies integrity detection on all five points.

**Relationship to 0016–0021:** ADRs `0016`, `0017`, `0018`.

**Amendment status:** **Proposed.** Removed if this ADR is rejected.

### 9. `RELIABILITY_ARCHITECTURE.md` (Section 02 · Active)

**Amended:** retries and queued requests carry no injected credential material; re-injection at
send time (`I-81`).

**Why required:** `I-81` constrains reliability infrastructure, which this document owns. Stating
it only in `SECRETS_ARCHITECTURE.md` would leave the owning document silent.

**Relationship to 0016–0021:** ADR `0019`.

**Amendment status:** **Proposed.** Removed if this ADR is rejected.

## Documents deliberately NOT authorized here

**`DATA_ARCHITECTURE.md` (Section 02 · Active) is out of scope.** It describes partitioning as
"row-level vs schema vs database separation" — relational and product-shaped phrasing corrected
elsewhere in Section 04. **James excluded it from this pass.** It is named here so the
inconsistency is recorded as deliberate rather than missed. Amending it requires adding it to this
ADR explicitly.

**Documents needing no authority:** [`KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) (its header
states it is extended in Sections 03 and 04), [`../ROADMAP.md`](../ROADMAP.md) (recording section
status is its purpose), [`DEFERRED_DECISIONS.md`](./DEFERRED_DECISIONS.md) and
[`README.md`](./README.md) (maintaining the register and index is their purpose). These are
updates within each document's stated function, not amendments to architectural content.

## Reason
One record that can be read in full, accepted or rejected as a unit, and that names every affected
document. The alternative — inferring authority from ADRs that do not mention the change — is what
produced the gap.

## Tradeoffs
**Advantages:** the chain closes in one place; every amendment is individually enumerated with its
reason and its removal condition; no accepted document carries an unattributed change; ADR 0008 and
the `INVARIANTS.md` rule are honoured rather than weakened.

**Disadvantages:** this ADR must be kept in step with `0016`–`0021` — if one of them is rejected
individually, the corresponding rows here need revisiting. It is also a governance record rather
than an architectural decision, which is an unusual shape for an ADR; the alternative was worse.

## Consequences
**ADRs `0016`–`0021` cannot be accepted without also deciding this one**, since accepting them
while these amendments lack authority is precisely the silent ratification `S4-P3` identified.

**Rejection is clean.** Every amendment is marked in place and removable, restoring the accepted
text verbatim. No accepted architecture depends on any of them.

**ADR 0008 is not loosened, and `INVARIANTS.md`'s C3 rule is not loosened.** This ADR satisfies
those rules rather than amending them.

Invariants: `I-60`–`I-90` (authorization to record them in
[`INVARIANTS.md`](../architecture/INVARIANTS.md); the invariants themselves are proposed by
`0016`–`0021`).

## What Would Change This
A decision that section-scoped amendments should not require per-change authority — which would be
an amendment to [ADR 0008](./0008-architectural-governance-model.md), recorded as a superseding
ADR, not an edit here.
