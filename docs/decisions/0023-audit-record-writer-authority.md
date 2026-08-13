# 0023 — Audit Record Writer Authority and the Control-Plane Audit Partition

**Status:** Proposed
**Proposed:** 2026-08-13 — Section 04
**Section:** 04
**Resolves:** `S4-P7` / `S4-P8` — who is authorized to write every audit record NOVA requires
**Also authorizes:** the Section 04 amendments to `DATA_ARCHITECTURE.md` and
`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`, which [ADR 0022](./0022-section-04-amendments-to-accepted-architecture.md) does not cover

## Decision

**One principle governs every audit record:**

> **An audit record is written under the authority of the operation it records, into the partition
> of the scope that operation concerned. Operations concerning no client scope are recorded in the
> **control-plane audit partition**, which is not a node in the client scope tree.**

Three writer authorities follow, and there are no others:

| Authority | Applies to | Target partition |
| --- | --- | --- |
| **W-1 — Execution authorization** | Successful execution-scoped events | The execution's single bound scope |
| **W-2 — The authorization decision itself** | Attempted, denied and pre-binding events | The scope the decision concerned |
| **W-3 — The control-plane operation's own authorization** | Events concerning no client scope | The control-plane audit partition |

**No new authorization authority is created.** `W-1` is the existing `E-12b` rule. `W-2` observes
that `I-18` already makes a decision produce a record, and states that the decision is the authority
for the record *of that decision* — allow and deny alike. `W-3` is the control-plane operation's own
authorization, which for every event in its class is James's (`I-09`, `I-10`) or a human act
(`B-2`, `X-6`).

**No new trusted component is created.** The control-plane audit partition is a **partition**, not a
service. Nothing gains a capability it did not have; what changes is where records go.

## Context

`S4-P8` enumerated the complete audit surface: **58 event classes**. Only 20 — the successful
execution-scoped family — had a defined writer. 36 had none, and 2 were undetermined. Four earlier
attempts (`C-1`, `S4-P5`, `H-A`/`S4-P6`, and the `S4-P6` red-team) each closed the gap in front of
them and left an adjacent one open, because none enumerated the surface first.

## Problem

`E-12b` grants audit-write capability to *"an execution that has been authorized, and whose scope
binding is therefore established."* Denials, pre-binding refusals and control-plane operations have
neither. The obvious repair — give some component the ability to write any client partition —
recreates the blanket cross-client writer `S4-P1` exists to forbid, and does so on the records most
relevant to detecting an attack.

## Options Considered

1. **Attempt-scoped authority alone.** Covers 34/58. Leaves every control-plane event undefined.
2. **A control-plane writer with client-scope reach.** Covers 42/58, and hands one component
   capability over every client partition — `S4-P1` violated by construction.
3. **Hybrid of 1 and 2.** Covers 58/58 and inherits option 2's blanket writer.
4. **Attempt-scoped authority plus a control-plane audit partition outside the client scope tree.**
   Covers 58/58. No component ever holds client-scope capability for a control-plane record,
   because control-plane records are not client-scope records.

## Decision Made

Option 4.

## Reason

**`S4-P1` holds by construction rather than by prohibition.** Options 2 and 3 create a capability
spanning client scopes and then forbid its misuse by rule. Every defect these reviews have found has
had that shape: a capability that exists, bounded by an instruction not to use it. Option 4 removes
the capability instead. A writer confined to the control-plane partition cannot reach a client
partition because there is no client partition there to reach.

## The control-plane audit partition

**It is outside the client scope tree.** It is **not** a new scope kind and is **not** governed by
[ADR 0015](./0015-extensible-scope-kinds.md) or the `I-06` scope contract, because it is not a scope:
nothing executes *in* it, no context resolves to it, no token names it, and it holds no client data.

**It holds only records of operations that concern no client scope** — scope creation, provisioning,
validation, verification, activation, rollback, grants and delegations, revocations, emergency stop,
break-glass, incidents, policy changes, classification changes, credential lifecycle, session
lifecycle, restore/migration verification, approvals, and audit-write failures.

**It must not become a disguised universal client-audit corpus.** A control-plane record names the
operation and the scope it concerned; it does **not** carry the client-scope content, identifiers or
resource references that would make it a substitute for reading a client's own partition (`I-48`,
`E-11`). Reading it is subject to `I-89` exactly as any partition is: **James only**.

**Its keys are in the audit hierarchy, separate from client-data keys** (`I-83`), and destroying any
client's keys does not affect it.

## Cross-scope denial recording

`S4-P8` reported an apparent conflict between `I-49` ("every cross-scope and cross-domain access is
recorded per scope touched") and `E-11`'s prohibition on writing a sibling's identifiers into another
client's partition.

**On analysis there is no conflict, and `I-49` requires no amendment.**
[`CROSS_SCOPE_DATA_RULES.md`](../architecture/CROSS_SCOPE_DATA_RULES.md) §6 — accepted — already
decomposes cross-scope work into *N sub-executions, one per scope, independently authorized, no token
spanning siblings*. "Per scope touched" is therefore satisfied by **each sub-execution recording in
its own partition about its own scope's access**. No sibling identity ever needs to cross a
partition boundary.

**And a denial is not an access.** `I-49` governs accesses that occurred. A denied attempt is
Family B, governed by `W-2`, and §6 already states that a denied sub-request makes the aggregate
incomplete — handled above the executions, not inside a sibling's partition.

**Therefore:** the actor's scope receives the denial record (`W-2`); the target's partition receives
nothing naming the actor; a security-event record goes to the control-plane partition
(`SECURITY_BOUNDARIES.md` §6 already classifies a denied cross-boundary attempt as a security event).
`I-49` and `E-11` are both preserved **unamended**.

## Audit-write failure

**`I-18` is mandatory and is not weakened.** If a required audit record cannot be durably written,
the recording obligation is not satisfied, and the architecture must say what happens rather than
leaving an implementer to choose.

**The governing distinction:** operations that **grant or exercise** access fail **closed** — they do
not proceed. Operations that **restrict or remove** access proceed, because refusing to stop is
failing *open*.

| Operation | On audit-write failure |
| --- | --- |
| **Authorization decision** | Resolves to **DENY** (`I-14`, `I-17` — deny is already the failure answer) |
| **Execution start** | Execution does **not** start |
| **Control-plane operation** | Does **not** proceed |
| **Provisioning** | Scope does **not** activate — `I-80` already requires the record before activation |
| **Emergency stop** | **Proceeds.** Stopping is a restriction; failing it closed would leave access running. The audit failure is recorded when the path recovers |
| **Break-glass** | **Proceeds only with an out-of-band record**, on the same reasoning as `B-7`'s out-of-band rotation: break-glass is used precisely when NOVA is degraded. The interval between use and durable recording is recorded as exposure |

### Scopeless decisions belong to `W-3`, not `W-2`

*Added 2026-08-13, closing `HIGH-1`.* `W-2` places a record *"into the partition of the scope the
decision concerned."* **Authentication and recovery precede context resolution** — accepted
`AUTHENTICATION_MODEL.md` §1 separates *who is acting* from *whether they may*, and a session exists
before any scope does. At a **failed authentication** or **failed recovery** (`A-4`) there is no
client scope, so `W-2`'s placement rule has nothing to resolve.

**Both are control-plane events under `W-3`.** `I-92` already listed *session lifecycle*; it now names
them explicitly. **No event is forced into a client partition merely to satisfy a placement rule**,
and no new authority was created — this is `W-3` applied to events that always belonged to it.

### Uncertain persistence is resolved by identity

*Added 2026-08-13, closing `HIGH-2`.* NOVA's accepted event model already assumes at-least-once
delivery with idempotent consumers, and every action already emits a record **linked by trace id**
(`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` §§1–2, `MASTER_ARCHITECTURE.md` §6). Audit records inherit
that model rather than a new one: a **deterministic event identity** derived from the operation and
its trace id; physical writes sharing an identity are **one logical record**; an uncertain write is
retried and collapsed on read.

**`I-47` is unaffected** — nothing is removed, duplicates collapse logically. **No false history is
created**: a decision record records that the decision was taken; whether the operation proceeded is a
separate record, so a persisted record alongside a fail-closed outcome is accurate. **Exactly-once is
neither required nor claimed.**

**No recursion.** The audit-failure record is itself a control-plane event under `W-3`. If it cannot
be written either, **no further record is attempted** — the operation has already failed closed, and
the condition surfaces as an incident (`I-76`). There is no third attempt and no fallback writer.

**No fallback universal writer is introduced**, and no "best effort" reading of `I-18` is permitted.

## Amendments this ADR authorizes

[ADR 0022](./0022-section-04-amendments-to-accepted-architecture.md) does **not** cover these two
documents — `DATA_ARCHITECTURE.md` was explicitly excluded by James. This ADR supplies the authority,
separately and visibly, rather than silently broadening ADR 0022.

### 1. `DATA_ARCHITECTURE.md` (Section 02 · Active) — §4 entity table

**As accepted 2026-08-12 the row read:** `| Audit Record | An immutable record of an action and its
authorization | **Written by executions** |`

**Amended to** reflect the three writer authorities. **Why required:** the accepted row is
*incomplete rather than wrong* — it was written in Section 02, before control-plane operations were
specified in Section 04. Read literally it makes 36 mandatory event classes unwritable and renders
`I-18`, `I-80`, `V-5`, `B-3`, `X-6` and `I-76` unimplementable.

**Amendment status:** **Proposed**, marked in place. Removed and the accepted text restored verbatim
if this ADR is rejected.

### 2. `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` (Section 03 · Active) — §5.1

**Amended:** a writer-authority note added to the thirteen audit categories, mapping each to `W-1`,
`W-2` or `W-3`. **Why required:** §5.1 is the canonical audit-category list and mandates categories —
Grants, Administrative changes, Credentials, Approvals — that have no execution, contradicting
`DATA_ARCHITECTURE.md` as accepted. **Amendment status:** **Proposed**, marked in place.

## Tradeoffs

**Advantages:** all 58 event classes have exactly one authority and one partition; `S4-P1` holds
structurally; no new component, authority or grant class; `I-49` and `E-11` preserved unamended; the
`I-80` provisioning impossibility is resolved; audit-write failure is specified rather than left to
an implementer.

**Disadvantages:** reviewing one client's complete history is now a **two-partition read** — that
client's partition plus the control-plane records concerning it. Under `S4-P2` Option D that is James,
per scope, and where it spans scopes it requires step-up (`I-67`). The control-plane partition also
becomes a concentration of security-relevant records and a target in its own right (`T-27`).

## Consequences

**A compromised PDP can still fabricate a decision about any scope**, and under `W-2` that decision is
its own write authority. This is **not new exposure**: `I-85` already records that PDP-emitted audit
is not evidence of PDP integrity. It is restated here so `W-2` is not mistaken for a stronger
property than it is.

**The control-plane partition is a new concentration.** Compromise of a control-plane writer yields
control-plane records — provisioning, grants, revocations, incidents — but **no client partition**.
Recorded as `T-27`.

Invariants: `I-88` (amended), `I-91`–`I-93` (new). `I-01`–`I-59` unmodified; `I-14`, `I-17`, `I-18`,
`I-47`, `I-49`, `I-82`, `I-85` untouched.

## What Would Change This

A demonstration that the control-plane partition cannot be kept free of client-scope content — which
would collapse it into a client-audit corpus and require reopening the option set, recorded as a
superseding ADR rather than an edit here.
