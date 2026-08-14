# 0031 — Section 06 Amendments to Accepted Architecture

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 06
**Section:** 06
**Purpose:** Formally authorize every Section 06 amendment to an Active/Accepted document, in one
record, enumerated individually.

## Decision

Section 06 amends **thirteen** Active/Accepted documents. ADRs `0029`–`0030` require those
amendments but do not individually authorize them, and both
[ADR 0008](./0008-architectural-governance-model.md) and
[`INVARIANTS.md`](../architecture/INVARIANTS.md) require an ADR for a C3 change.

**Every amendment listed here is Proposed and is marked in place. If this ADR is rejected, every
one of them is removed and the accepted text is restored verbatim.**

**Three are corrections of statements that are wrong as accepted**, not additions — items 1, 3 and
10. They are called out because a correction to accepted text deserves more scrutiny than an
addition to it.

## Context

Sections 04 and 05 each closed this gap with a single enumerating ADR ([0022](./0022-section-04-amendments-to-accepted-architecture.md),
[0028](./0028-section-05-amendments-to-accepted-architecture.md)). Section 06 follows the same
convention, recorded up front.

## Problem

An amendment sitting inside an Active document is indistinguishable from accepted architecture
unless something records otherwise.

## The amendments

### 1. `AGENT_ARCHITECTURE.md` (Section 02 · Active) — §2, §3 — **CORRECTION**

**As accepted 2026-08-12, §2 read:** *"the runtime cannot **issue** a token exceeding it,
regardless of what the orchestrator requests."* **This is wrong as accepted.** `I-87` requires
every consumer to reject a token "fabricated by anything other than the Context service", so a
runtime that issues tokens produces tokens every enforcement point must refuse. **Amended to:** the
runtime **requests** issuance; Context issues and verifies (`I-106`). §3 gains child lifetime
(`AG-11`) and the explicit absence of a suspended state (`AG-12`). **Amendment status:**
**Proposed**, marked in place.

### 2. `ai/AGENT_PRINCIPLES.md` (Section 01 · Active) — §4

**Amended:** the blanket *"enforced by design, not by instruction alone"* is qualified per
prohibition. **Why required:** Section 06 found the claim true of five prohibitions, newly true of
prohibition 4's agent half, and **false of prohibition 6** — no enforcement point inspects agent
output for epistemic honesty. **This is Section 01 material and therefore C4-adjacent**; it is
recorded as a correction of an overclaim, not a weakening of a principle — the prohibition stands,
only the enforcement claim is corrected. **Amendment status:** **Proposed**, marked in place.

### 3. `SCOPE_AND_IDENTITY_MODEL.md` (Section 03 · Active) — §5 — **CORRECTION**

**As accepted, §5 lists a delegation carrying** delegator, delegate, scope, rights, expiry, purpose
**and then states** *"re-delegation is allowed only where the original delegation permits it."*
**The rule tests a field the record does not have.** **Amended:** the record gains
`may_redelegate` (default false) and `ancestry`, and the four bounding rules are stated (`I-107`).
**Amendment status:** **Proposed**, marked in place.

### 4. `IDENTITY_AND_AUTHORITY.md` (Section 02 · Active) — §5

**Amended:** the Specific Authorities table gains agent creation, registration, activation,
suspension, revocation and replacement rows. **Why required:** ADR 0030. §5 classes *agent
permissions* C3 but names no agent lifecycle operation, so agent creation had no class.
**No new change class is created.** **Amendment status:** **Proposed**, marked in place.

### 5. `CONTEXT_ARCHITECTURE.md` (Section 02 · Active) — §2, §5

**Amended:** issuance verification (`AG-1`–`AG-5`) and a conflict row for a request exceeding the
agent definition. **Why required:** ADR 0029 makes Context the verifying point. §1's *"Context
answers where; Policy answers whether"* is **preserved** — the check can only refuse to issue.
**Amendment status:** **Proposed**, marked in place.

### 6. `AUTHORIZATION_MODEL.md` (Section 03 · Active) — §3

**Amended:** a note that the agent-definition input to `I-07` is verified at **issuance**, not by
the ten-step sequence. **Why required:** a reader checking where `I-07` is enforced finds nothing in
§3 and would reasonably conclude nothing enforces it. **The ten steps are unchanged.**
**Amendment status:** **Proposed**, marked in place.

### 7. `PERMISSION_ARCHITECTURE.md` (Section 02 · Active) — §5

**Amended:** the approval binding set (`I-109`). **Why required:** ADR 0030. *"One action, in one
context, at one time"* fixes how many times an approval may be used, not what it is an approval
**of**. **Amendment status:** **Proposed**, marked in place.

### 8. `SCALE_AND_COST_ARCHITECTURE.md` (Section 02 · Active) — §4

**Amended:** the ceiling belongs to the root execution and is shared by its delegation tree.
**Why required:** ADR 0029 rule 3. §4 as amended by Section 05 caps "sandboxes, agent loops, and
workflows"; a delegation tree is none of those unless it happens to be a workflow.
**Amendment status:** **Proposed**, marked in place.

### 9. `MODEL_GATEWAY_ARCHITECTURE.md` (Section 05 · Active) — §7

**Amended:** `MG-18`'s per-execution ceiling is scoped to the root execution. **Why required:**
`I-105` as accepted is per execution, so a delegation tree received one ceiling per execution — the
capacity-minting gap **Section 05 introduced**. This amends Section 05 material accepted one day
earlier, which is why it is enumerated rather than folded into an edit. **Amendment status:**
**Proposed**, marked in place.

### 10. `THREAT_MODEL.md` (Section 03 · Active) — **CORRECTION** + additions

**Corrected:** `T-24`'s Agent-Runtime row answered *"an agent could receive a token it should not
have"* with *"rights remain an intersection (`I-07`)"* — **circular**, since the intersection was
what the compromised component computed. **Added:** `T-33` (delegation-tree abuse), `T-34`
(approval substitution). `T-23a`'s residual is **not reduced**. **Amendment status:** **Proposed**,
marked in place.

### 11. `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` (Section 03 · Active) — §5.1

**Amended:** agent-definition lifecycle and delegation added to the auditable categories with their
`W-1`/`W-2`/`W-3` authority. **Why required:** §5.1 is the canonical category list; delegation
appeared in `I-92` but not here, and agent-definition lifecycle in neither. **No new audit
authority is created** — ADR 0023's three cover every event. **Amendment status:** **Proposed**,
marked in place.

### 12. `INVARIANTS.md` (Section 03 · Active)

**Amended:** `I-106`–`I-109` added under a Section 06 heading. **`I-01`–`I-105` are unmodified.**
**Amendment status:** **Proposed**, marked in place.

### 13. `KNOWN_RISKS.md` (Section 03 · Active)

**Amended:** Section 06's residual risks recorded — the Context service's new registry dependency,
sibling starvation under a shared budget, the binding-boundary judgment, and prohibition 6.
**Amendment status:** **Proposed**, marked in place.

## Tradeoffs

**Advantages:** the amendment surface is visible before acceptance; rejection is a clean operation;
three corrections of wrong accepted text are called out rather than buried among additions; no
accepted invariant is weakened.

**Disadvantages:** thirteen documents again, including one Section 01 document (`AGENT_PRINCIPLES.md`)
and one Section 05 document accepted the previous day. Amending recently accepted material is
a signal worth noticing: `MODEL_GATEWAY_ARCHITECTURE.md` §7 is amended because Section 05 shipped a
gap, not because Section 06 changed its mind.

## Consequences

Accepting `0029`–`0030` accepts these thirteen amendments. Rejecting either removes the amendments
that ADR required; the rows above name which.

## What Would Change This

Discovering an amendment not listed here — fixed by adding the row before acceptance, not by
leaving it unrecorded.
