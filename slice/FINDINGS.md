# Vertical Slice — Implementation Findings

**Status:** findings from building the slice. **Nothing here amends the architecture.**
No invariant was created, no ADR was accepted, no document in `docs/` was changed to make
implementation easier.

Two lineages, in the order they were produced:

1. **Findings 1–5, from the three vertical slices.** Numbered findings about the
   architecture met in practice. Finding 1 resolved from the architecture's own reasoning;
   Finding 4 resolved by James on 2026-08-15 and applied. Their resolutions are documented
   in `docs/` as **Proposed** amendments under existing ADRs — no ADR was accepted and no
   invariant was created.
2. **The `F` series, from adversarial security audits of the substrate slice.** Its
   disposition index, its **open residuals**, the residuals since **closed**, the deliberate
   test states that must not be "fixed", and what remains unvalidated are in the final
   section of this document.

The header of this file previously said *"Two findings, both now resolved"*, which stopped
being true once the third slice and the `F` series were added. It is corrected here rather
than left standing: a document about accuracy does not get to be inaccurate about itself.

---

## Finding 1 — `I-114(a)` and `I-03` disagree about ordering, and the denial leaked scope

**RESOLVED from existing architecture. No new decision required.**

### What happened

`I-114(a)` requires the execution binding to be **resolved before the authorization
decision**. Taken literally, that puts `capability.resolve()` ahead of the PDP's
**step 3** (scope containment). Building it that way produced two defects:

**a) The denial point depended on unrelated configuration.** The same cross-client attack
died in two different places:

```
client-b has NO binding : denied at 'capability.resolve'  I-114
                          "no binding for send_message in /business/KAIRO/client-b"
client-b HAS a binding  : denied at 'step3.scope'         I-03
                          "token does not cover /business/KAIRO/client-b"
```

Whether a sibling client happened to have a binding for that tool — a routine
configuration detail with no security meaning — decided which invariant fired and how the
event was recorded. **The highest-signal alarm in the system (a cross-client attempt) was
being filed as a missing-configuration error half the time.**

**b) The error message leaked the target scope.** `I-03` is explicit: an execution cannot
read, write or enumerate another scope's resources **"by any path, including error
messages and timing."** A resolution failure naming `/business/KAIRO/client-b` does
exactly that, and distinguishes *scope exists but has no binding* from *scope does not
exist*.

### Resolution

Derived from the architecture, not invented. `AUTHORIZATION_MODEL.md` §3 already explains
why step 3 precedes step 5: *"scope containment is checked before permissions exist."*
The same reasoning extends to binding resolution — **scope containment must precede
anything that can leak.** `I-114(a)` is preserved: the binding is still resolved before
the **decision**.

Implemented in `runtime.py` as an explicit precheck, with a uniform message that names no
scope. Both defects are covered by `Test03WrongScope`.

### Now documented

`I-114(a)` says "resolved before the authorization decision" without saying *how far*
before, so an engineer reading only `I-114` would reintroduce this.
**`TOOL_AND_INTEGRATION_ARCHITECTURE.md` §3 now records the ordering** (2026-08-15,
Proposed): scope containment → binding resolution → authorization decision →
binding-envelope enforcement. **`I-114` is not weakened** and `I-03` remains the boundary
preventing cross-scope disclosure.

---

## Finding 2 — every plan is LOW trust, so "untrusted-derived" may gate everything

**RESOLVED by James 2026-08-15: it is a PROVENANCE CLASS, not a trust level.**
Implemented, documented in `PROVENANCE_AND_TRUST.md` §1.1 and
`MODEL_TRUST_AND_AUTHORITY.md` §3 under ADR 0035 (Proposed), and covered by ten tests
proving **both sides** of the distinction.

### What happened

The Planner **is a model** (`ORCHESTRATION_ARCHITECTURE.md` §1,
`MODEL_TRUST_AND_AUTHORITY.md` §1). `I-99` gives model output *"the lowest trust among"*
its inputs **plus its own `model.generated` provenance**, and
`PROVENANCE_AND_TRUST.md` §2 rates `model.generated` **Low**.

`min(anything, LOW) = LOW`. Therefore:

```
plan James stated directly, no external content anywhere   -> trust LOW
plan influenced by injected external.web content           -> trust LOW
                                          DISTINGUISHABLE BY TRUST?  No.
                                          DISTINGUISHABLE BY PROVENANCE?  Yes.
```

**Every plan NOVA will ever produce carries LOW trust.**

### Why that matters

`MT-7` row 3 and `I-100` both gate on *"derived from **untrusted content**"* and cite
`I-99` — the **trust** mechanism. `I-40` says *"**External** content may inform a plan but
never escalate one"* — a **provenance** class. These read the same until you implement
them, and then they diverge completely:

| Reading | Consequence |
| --- | --- |
| **Trust level** (`trust <= LOW`) | **Every action above `PREPARE` requires an approval naming a source — forever.** But when James stated the objective himself there *is* no external source to name. `PERMISSION_ARCHITECTURE.md` §5's standing approvals (*"deploy Client A's staging without asking"*) become unreachable, because every plan trips the source-naming requirement. |
| **Provenance class** (`external.web` / `client.supplied` / `integration.supplied` present in the union) | The system behaves as the documents evidently intend. But it means `model.generated`'s Low trust does **not** by itself make a plan "untrusted-derived", which is not stated anywhere and looks like a loophole to a reader of `I-99`. |

**An engineer must choose, cannot avoid choosing, and the two choices produce materially
different systems.** That is the same defect shape Sections 05, 08 and 14 each found by
reading — this one was found by running.

### Resolution

**Provenance class.** `is_untrusted_derived()` is true when the provenance union contains
`external.web`, `client.supplied` or `integration.supplied`.

**The decisive evidence is `I-40`'s own text.** It is one sentence: *"**External** content
may inform a plan but never escalate one; a plan influenced by **untrusted** content cannot
exceed `PREPARE` without approval naming the source."* One rule, joined by a semicolon —
so *untrusted* **is** *external*. The provenance reading makes `I-40` internally
consistent; the trust reading makes its two clauses disagree. **No invariant changed,
because `I-40` was already correct under this reading.**

**The conflation entered through `I-100`'s parenthetical** — *"derived from untrusted
content (`I-99`)"* — which points a provenance question at the trust mechanism.

**Not a downgrade, and not a loophole.** A Low-trust plan remains Low trust. Every other
control is evaluated independently and was tested to confirm it: argument envelope
(`I-100`), classification egress (`S13-D1`), scope containment (`I-03`), binding envelope
(`I-114`), approval (`I-09`). Provenance cannot be shed — immutable (`I-38`), unioned at
every hop (`I-99`), surviving persistence (`I-111`) — and a standing approval, which names
no source, **cannot** satisfy `I-40`.

**Standing approvals are now reachable**, which they were not under the trust reading.

### What this is not

Not an invariant defect. `I-99`, `I-40` and `MT-7` are each individually consistent, and
none was amended. The gap was that **no document said whether "untrusted" means a trust
level or a provenance class**, and `I-99`'s arithmetic makes the two coincide for every
plan. That definition now exists.

---

## What did NOT go wrong

Worth recording, because these were the parts expected to be difficult:

- **`I-114`'s binding identity is clean.** Making provider, account, endpoint and
  API version part of the identity means repointing any one of them invalidates the
  authorization automatically. No extra comparison logic; the hash does it.
- **Broker step 2a is one comparison.** The Section 11 addition slotted into an existing
  protocol without disturbing steps 1–7.
- **Per-attempt re-injection made retry-after-revocation correct for free.** The broker is
  called afresh each attempt, so revocation between attempts is caught with no retry-aware
  code anywhere.
- **ADR 0036's leaf totality was easy** and caught a nested `payload.cc` that a top-level
  reading would have missed.
- **`I-93` fail-closed audit was straightforward** because the writer raises rather than
  returning a status a caller could forget to check.

## Where `I-109` was awkward — a lesser observation

`I-109` says the approval *"remains valid only while all [ten] of these are unchanged
between approval and execution."* At execution, **eight of the ten are recomputable from
current state**; two — the **argument envelope** and the **cost ceiling** — are properties
*of the authorization itself*, with no independent source to recompute them from.
Comparing them is therefore vacuous.

Not a defect: those two cannot drift, because they only exist inside the authorization
record. But the phrasing implies ten independently observable properties, and an engineer
will look for a way to recompute all ten and not find one. The slice checks the eight that
can change and treats the other two as immutable parts of the record.

---
---

# Second Vertical Slice — two agents, delegation, model gateway

**95 tests total: 49 first-slice (no regressions) + 46 second-slice.**

Two new findings. **Finding 3 was resolved from existing precedent. Finding 4 is a
contradiction between two accepted documents and requires James's decision — nothing was
invented to work around it.**

---

## Finding 3 — an empty Allowed Tools list was refused as "incomplete"

**RESOLVED from existing precedent. Contained. No decision required.**

**Enforcement point:** `AgentRegistry.register`, `AGENT_ARCHITECTURE.md` §2.

Agent B is defined with `allowed_tools = {}` — a **closed list containing nothing**, meaning
*"this agent may call no tools."* The registry refused to register it, because a
completeness check cannot distinguish **absent** from **present-and-empty**.

**Why it matters:** the refusal made **the safest possible agent unrepresentable.** An
agent that may call no tools is the maximally-restrictive configuration, and NOVA could
not express it.

**Resolved on existing precedent, not invention.** ADR 0036 already draws exactly this
distinction for tool declarations — absence is incomplete and refused; an explicit
declaration is complete however restrictive — and `I-14` already makes an empty grant set
the *denial* state rather than an error. Applied here: an **absent** Allowed Tools or
Permissions field is incomplete and refused; a **present-and-empty** one is complete and
grants nothing. Every other field still treats empty as incomplete.

**Direction of failure is safe:** an empty closed list can only deny.

---

## Finding 4 — `AG-8` cannot fire as written

**CONTRADICTION between two accepted documents. REQUIRES JAMES'S DECISION.**
**Nothing was invented. The rule is implemented exactly as written and shown not to fire.**

**Enforcement point:** `delegation.check_within_parent`, `AGENT_GOVERNANCE.md` §3.2, `I-107`.

### The contradiction

`AG-8` — *"A delegation is refused if the **delegate** already appears in its own
`ancestry`. **This blocks `A → B → A`** and every longer cycle."*

`AG-6` — the record it tests:

```text
delegator   the granting EXECUTION IDENTITY
delegate    the receiving AGENT
ancestry    the chain of DELEGATORS above it      -> execution identities
```

**`delegate` is an agent. `ancestry` is a set of execution identities. The comparison is
between two different types and can never match.**

And it cannot be repaired by comparing identities instead: `AUTHENTICATION_MODEL.md` §5
makes execution identities **ephemeral, "created per execution, never reused"** — so an
identity can never recur in its own ancestry either. **`AG-8` is vacuous under both
readings**, while its stated purpose — *"blocks `A → B → A`"* — plainly names **agents**.

`I-107` carries the identical wording, so the invariant inherits the defect.

### Demonstrated, not asserted

`test_AG8_as_written_cannot_fire__FINDING_4` builds `A → B → coordinator`, confirms the
agent name is absent from an ancestry of trace ids, and shows the delegation **succeeds**.

### Why this is CONTAINED rather than an escalation path

**`AG-7` still bounds the chain.** Every step must be *strictly* narrower in at least one
authority dimension and expire strictly earlier, on a finite lattice. So a cycle **cannot
regain authority** — an agent reappearing in its own chain holds strictly less than it did.
`test_AG7_still_bounds_the_chain_AG8_was_meant_to_block` proves the identical-authority
re-entry is refused by `AG-7`.

**So the security consequence is bounded**: `AG-8` does not add the protection it claims,
and `AG-7` already provides termination. What is lost is *agent-level cycle exclusion*,
which may or may not be wanted on its own merits.

### The decision James must make

**Is `AG-8` meant to exclude an agent from its own delegation chain, or is `AG-7`'s
narrowing sufficient?**

- **(a) `ancestry` carries agent identity as well as execution identity**, and `AG-8`
  compares agent to agent. Makes `AG-8` do what it says. Costs: a legitimate re-entry
  under strictly narrower authority becomes impossible.
- **(b) `AG-8` is redundant and should be withdrawn**, with `AG-7` stated as the sole
  bound. Fewer moving parts; the docs stop claiming a protection that does not exist.
- **(c) Something else.**

**This changes `I-107`, an accepted invariant, either way — so it is not the slice's call.**
No ADR was created and no invariant was touched.

---

## What the second slice actually exercised

| Area | Status | Evidence |
| --- | --- | --- |
| `I-106` sole issuance, refusal is total | **Exercised** | Runtime cannot mint; forged token fails `I-87` |
| `I-107` / `AG-7` strict narrowing | **Exercised** | Broader rights, ceiling, tools, expiry and identical-delegation all denied |
| `AG-9` re-delegation default false | **Exercised** | Denied by default; permitted when explicit; narrows again |
| `AG-8` cycles | **FINDING 4** | Cannot fire as written |
| `AG-11` child never outlives delegator | **Exercised** | Fails closed at the *next* enforcement point; prior call not undone |
| `I-94` gateway is a PEP | **Exercised** | Stop, PDP-unavailable and revocation all deny at the gateway |
| `I-95` one scope per request | **Exercised** | Two client scopes denied; PUBLIC/INTERNAL correctly *not* a second scope |
| `I-96` classification gates egress | **Exercised** | SECURITY-CRITICAL never; SENSITIVE-PERSONAL only on per-call approval; unestablishable denies |
| `I-97` constrained routing | **Exercised** | Unauthorized provider and model denied *before* egress; empty permitted set fails closed |
| `I-98` model never selects routing | **Exercised** | Model-named provider denied before any other step; provider named in response text has no effect |
| `I-99` response is a derivation | **Exercised** | Response taint computed structurally from the request |
| `I-102` / `I-110` model establishes nothing | **Exercised** | Fabricated provenance, `system_verified` and approval claims all inert |
| **Finding 2 resolution holds through a real model call** | **Exercised** | `james.stated + model.generated` is LOW trust and NOT untrusted-derived; `external.web` is |
| `I-103` provider credential | **Exercised** | Reference only, reaches the boundary, never returned or in prompts |
| `I-104` retry separately authorized | **Exercised** | Retry after UNKNOWN re-verifies and denies on revocation |
| Unknown model outcome | **Exercised** | Timeout is UNKNOWN, never failure |

## What remains untested

- **Any real provider.** The gateway is validated; **no external model API was called.**
- **`I-96` redaction.** *"Redaction cannot be confirmed applied"* has no implementation
  here; only the deny-on-unestablishable branch is exercised.
- **`I-105`/`I-108` budget across a delegation tree.** Not modelled.
- **`I-95` provider-side session sharing.** *"No conversation, cache, or provider-side
  session is shared across scopes"* is unobservable against a fixture.
- **Concurrency.** All tests are serial; `AG-10` fan-out and the budget race are untouched.

---

## Finding 4 — PHASE 1 ANALYSIS: is `AG-8` security-critical or redundant?

**CONCLUSION: `AG-8` is REDUNDANT. `AG-7`, `AG-9` and `AG-11` already provide the property
it claims, and provide it in three independent ways.**
**No security gap. A documentation correction to `I-107` is proposed and NOT applied —
`I-107` is accepted, so the wording change is James's.**

Traced through the implementation (`slice/core/delegation.py`, `context_service.delegate`),
not the prose. Every answer below was produced by running the cycle.

| # | Question | Answer | Enforcement point |
| --- | --- | --- | --- |
| 1 | Can `A → B → A` **increase** authority? | **No.** Holding authority *constant* is denied at step 1 | `delegation.narrowing` (`AG-7`) |
| 2 | Can it bypass the delegation **ceiling**? | **No.** Ceiling monotonically non-increasing across the whole chain | `delegation.ceiling` |
| 3 | Can it create authority **not in the parent**? | **No.** A right dropped at depth 1 cannot be regained at depth 2 | `delegation.rights` / `delegation.scope` |
| 4 | Can repeated delegation create **indefinite** authority? | **No.** Chain terminated at depth 3. **Two independent bounds**: the authority lattice is finite, and expiry strictly decreases every step | `delegation.narrowing` |
| 5 | Can the loop **bypass another control**? | **No.** Cannot widen scope, cannot regain a dropped right | `delegation.scope`, `delegation.rights` |
| 6 | Unbounded **resource** problem? | **No.** Bounded by (4), and separately by `AG-13`'s one-budget-per-delegation-tree — verified in the third slice | `AG-13` |
| 7 | Does `AG-11` change the answer after revocation? | **It strengthens it.** When the ROOT execution ends, **every** node in the cycle fails closed — including the re-entered `A'` | `context.verify` (`AG-11`) |
| 8 | Does `AG-9` change it when re-delegation is off? | **Decisively.** At the default `may_redelegate=False`, **the cycle cannot start at all** — refused at step 2 | `delegation.redelegate` (`AG-9`) |
| 9 | Do `I-106`/`I-107` guarantee termination **without** `AG-8`? | **Yes**, by two independent mechanisms — finite lattice and strictly-decreasing expiry | `AG-7` |
| 10 | Is `AG-8` security-critical? | **No. Redundant** — and, as written, incapable of firing | — |

### The measured chain

```
depth 0  A   ceiling=EXECUTE   ttl=300.000s
depth 1  B   ceiling=PREPARE   ttl=299.999s
depth 2  A'  ceiling=ANALYZE   ttl=299.998s      <- the "cycle" AG-8 names
depth 3  B'  ceiling=READ      ttl=299.996s
         terminated: delegation.narrowing (I-107)

authority never rises: True        expiry strictly decreases: True
```

**The cycle runs, and is harmless.** Each re-entry holds strictly *less* than the previous
one. `A'` is not `A` in any authority sense — it is a strictly weaker descendant that
happens to be the same agent.

### Why `AG-8` cannot fire (restated from the second slice)

`AG-6` defines `delegate` as **the receiving agent** and `ancestry` as **the chain of
delegators**, where `delegator` is **the granting execution identity**. Comparing an agent
against a set of execution identities can never match; and
`AUTHENTICATION_MODEL.md` §5 makes execution identities *"ephemeral… never reused"*, so an
identity-to-identity comparison could never fire either.

### PROPOSED CORRECTION — NOT APPLIED

**`I-107` is accepted. This is C3 and is James's decision.** The smallest correction:

**Current `I-107` text:**
> *"A delegation whose delegate already appears in its own **`ancestry`** is refused,
> blocking `A → B → A` and every longer cycle."*

**Proposed replacement:**
> *"Cycles need no separate rule: strict narrowing already terminates them. `A → B → A`
> is permitted and harmless, because each re-entry holds strictly less authority than the
> previous one and expires strictly earlier; the chain therefore descends a finite lattice
> and ends. `ancestry` is retained — it records the delegation chain for audit and is what
> `AG-11` walks to fail a descendant closed when any ancestor ends."*

**Corresponding `AGENT_GOVERNANCE.md` §3.2 change:** `AG-8` is withdrawn as a *rule* and
its content folded into `AG-7`'s rationale. **`ancestry` stays in the `AG-6` record** — the
implementation uses it for `AG-11`, so removing the field would break a working control.

**Why withdrawal rather than repair (option (a)):** making `AG-8` compare agent-to-agent
would *forbid* a legitimate pattern — the same agent legitimately re-entering a chain under
strictly narrower authority — to prevent a cycle that `AG-7` already bounds. It would add a
restriction whose only effect is to reject safe delegations.

**Classification: CONTRADICTION (documentation), resolved analytically; no security gap;
correction requires James's decision.**

---
---

# Third Vertical Slice — delegation-tree budgets

**121 tests total: 49 + 46 + 26. No regressions.**

Exercises `I-105`, `I-108`, `AG-13`, `AG-14`, `AG-15` across `A → B → C`.

**Scope of the claim:** this validates **NOVA's own authorization budget**. A provider's
account balance is an external system and is **not observable here** — the architecture
does not claim otherwise, and neither does this slice.

---

## Finding 5 — a subtree carve could be re-registered UPWARD

**RESOLVED from an existing accepted invariant. Contained. No decision required.**

**Enforcement point:** `BudgetLedger.register_child`, `I-108` / `AG-14`.

**What happened.** `AG-14` says a carve is *"optional and narrowing"* — narrowing **relative
to the parent**. My first implementation checked exactly that, and nothing else. So a child
carved at 500 could be **re-registered at 9,000**, which passed because the parent's cap was
10,000. The root ceiling was never touched, so `AG-13`'s *"cannot raise the root ceiling"*
was not violated either.

**Why it is a real gap.** Raising an existing carve from 500 to 9,000 is
*"**receiving a fresh budget**"* — which `I-108` forbids in the same sentence as raising the
root ceiling. The architecture already covers it; my implementation had simply checked one
of the two clauses.

**Resolved:** a carve, once set, may only **narrow**. Widening is refused under `I-108`.
Narrowing an existing carve remains permitted, because that is what `AG-14` is.

**No invariant was created and no wording changed** — `I-108` already said it.

---

## Slice-local limitation — SQLite thread affinity

**Not an architecture finding.** `AG-10` and `AG-13` expect concurrent descendants, and the
per-scope SQLite store was thread-affine, so the concurrency test could not run at all.
Fixed with `check_same_thread=False` and a lock. **This is a property of the fixture, not of
NOVA**; `D-02` and `D-33a` remain unselected and the architecture requires no particular
store.

---

## What the third slice exercised

| Rule | Status | Evidence |
| --- | --- | --- |
| `I-105` every execution carries a ceiling | **Exercised** | An unbudgeted execution **denies** rather than running unlimited; ceiling 0 is valid and denies everything |
| `I-105` / `AG-15` exhaustion terminates and escalates | **Exercised** | Denial names *"terminate and escalate"*; **no code path degrades, truncates or downgrades** |
| `I-108` / `AG-13` one budget per tree | **Exercised** | Root, child and grandchild spend all hit the same root; no API opens a second root |
| `I-108` no minting / fresh budget | **Exercised** | Repeated delegation manufactures nothing (5 re-delegations share one 500); carve cannot be widened (Finding 5) |
| `I-108` no independent pool | **Exercised** | When the **root** is exhausted a child's carve is worthless |
| `AG-14` carve is narrowing and optional | **Exercised** | Carve > parent denied; `None` is valid and inherits the root ceiling |
| `AG-14` siblings bounded collectively | **Exercised** | Two children carved 400 each under a 500 parent: the second is denied |
| `AG-15` / `I-104` per-attempt accounting | **Exercised** | Retries charged individually; **an UNKNOWN outcome is charged, not free** |
| Cost integrity | **Exercised** | Cost is **computed from the actual request**; `declared_cost` is accepted and ignored; a cheap declaration with an expensive request still denies |
| Uncomputable cost | **Exercised** | Fails closed under `I-105`, never becomes free |
| Revocation | **Exercised** | Prevents subsequent spend; mid-chain revocation enforced at the **next** enforcement point; completed spend is **not refunded** |
| Concurrency | **Exercised, as specified** | Bounded overrun then hard stop — `AG-13` explicitly permits this and does **not** require a serialized counter |
| Finding 2 resolution | **Still holds** | Across a three-level tree: `james.stated` LOW but not untrusted-derived; `external.web` is |

## What remains unvalidated after three slices

- **No real model provider has been called.** The gateway is IMPLEMENTED and
  SECURITY-TESTED; **no provider is VALIDATED**.
- **Provider billing.** Deliberately out of scope — an external system, not observable.
- **`I-96` redaction confirmation.** Only the deny-on-unestablishable branch exists.
- **Token-based cost.** Cost here is a length proxy; real token accounting is a provider
  property.
- **`I-03` `[PHYS]`.** Unchanged from slice 1 — per-scope files are not the production
  mechanism.
- **Long-running concurrency.** One four-thread test; no sustained load, no scheduler.

---

## Finding 4 — RESOLVED AND APPLIED, 2026-08-15

**James approved withdrawing `AG-8` as redundant (C3). Documentation-only correction; no
invariant created, no ADR created, no security behaviour changed.**

This is an **accuracy correction, not a newly discovered vulnerability.** The property
`AG-8` claimed was already provided — four independent ways, each measured:

| Mechanism | What it provides |
| --- | --- |
| `AG-7` | Strict narrowing terminates the cycle: `EXECUTE → PREPARE → ANALYZE → READ → refused` |
| `AG-9` | At the default `may_redelegate=false`, the cycle **cannot begin** |
| `AG-11` | When any ancestor ends, every descendant fails closed |
| `AG-13` | The whole tree draws on one budget |

**A same-agent re-entry under strictly narrower authority is not an escalation and remains
permitted.**

### Applied

| Document | Change |
| --- | --- |
| `INVARIANTS.md` `I-107` | *"acyclic"* removed from the summary (cycles are now permitted); the cycle clause replaced with the withdrawal and its reasoning |
| `AGENT_GOVERNANCE.md` §3.2 | `AG-8` withdrawn with rationale; heading *"The four rules"* → *"The rules"* |
| `SCOPE_AND_IDENTITY_MODEL.md` §5 | Numbered rule 2 replaced with the withdrawal |
| `ORCHESTRATION_ARCHITECTURE.md` §5 | *"acyclic"* removed — current normative text |
| `ROADMAP.md` Section 06 | **Annotated, not rewritten** — it is the record of what Section 06 delivered, and repo precedent (Section 04) is to annotate a superseded record rather than edit it |

**`ancestry` is retained everywhere.** `AG-11` walks it, and `I-111` persists it.

**`ADR 0029` is deliberately untouched.** It is **Accepted** and is the historical record of
the decision as made on 2026-08-14. Rewriting an accepted ADR would falsify that record; the
correction is carried by the documents the ADR governs.

**Unchanged:** `AG-7`, `AG-9`, `AG-10`, `AG-11`, `AG-13`, `AG-14`, `AG-15`, and every
invariant other than `I-107`'s cycle clause. `I-01`–`I-114` remain contiguous and unique.

**Classification: CONTRADICTION (documentation) — RESOLVED.**

---

# Substrate security findings — the `F` series

**Status:** the working record of the adversarial security audits run against the substrate
slice. **Nothing here amends the architecture.** No invariant was created and no ADR was
accepted to make any of these fixes possible; where a fix needed a decision, James made it
and the decision is recorded in `docs/decisions/`.

**Why this section exists.** The `F`-series findings were carried in pull-request bodies and
commit messages, which is durable but scattered — a reader has to know which PR to open, and
an agent starting fresh sees none of it. The **open residuals** below were in no file at all.
Anything recorded here was verified against the code at the time of writing; nothing was
reconstructed from memory.

## Disposition

Each finding's full record — reasoning, verification, mutation results — is in its pull
request and merge commit. That is the authority; this table is the index.

| Finding | Subject | PR | Branch |
| --- | --- | --- | --- |
| `F-7` | qualified migration guard | #15 | `fix/f7-qualified-migration-guard` |
| `F-8` | elevation audit scope | #9 | `fix/f8-elevation-audit-scope` |
| `F-9`, `F-10` | authority scope and completion scope | #11 | `fix/f9-f10-authority-and-completion-scope` |
| `F-11` | scope names are control state | #13 | `fix/f11-scope-names-control-state` |
| `F-12` | sibling scope isolation | #12 | `fix/f12-sibling-scope-isolation` |
| `F-13` | revoked authority is labelled, not withheld | #14 | `fix/f13-revoked-authority-labelling` |
| `I-106` | grant-side risk-ceiling enforcement | #18 | (with `F-3`) |
| `F-3` | revoke an execution authority through the approval path | #18 | `feature/f3-revocation` |
| `F-4` | passkey bootstrap enrolment race | #21 | `fix/f4-passkey-enrolment-race` |

`F-2` predates this record; its disposition is in its own pull request and is not restated
here, because restating it accurately would require reading that PR rather than recalling it.

---

## OPEN RESIDUALS

**This is the part of this document with a claim on somebody's attention.** Every item below
is present in `main` as merged. None is a regression; each was found, judged, and left
deliberately. Each was re-verified against the code when this section was written.

| # | Residual | Where | Severity | Why it was left |
| --- | --- | --- | --- | --- |
| R-1 | An additional-device enrolment ceremony stays redeemable for its full `CEREMONY_LIFETIME` (5 minutes) even if the session that authorized it is revoked | `auth.py` `verify_enrolment` — it receives no session to re-check | Significant | Same bug class as `F-4`, materially weaker: it still required a strong session belonging to that actor. Fixing it means passing the session in and widening the seam route |
| R-2 | **No credential-management or revocation surface exists.** Nothing lists enrolled passkeys and nothing deletes one | `A-6` enumerates `auth_session` only; `schema.sql` grants `nova_auth` `SELECT, INSERT, UPDATE` on `auth_credential` — **no `DELETE`** | Significant | Removing a credential needs a `DELETE` grant, which is a schema change touching accepted privilege separation. That is governance review, not a fix to slip into a bug PR |
| R-3 | The `F-4` bootstrap advisory lock waits without bound (`lock_timeout = 0`) | `auth.py` `verify_enrolment`, bootstrap branch | Residual | James's ruling, PR #21: the critical section is one `INSERT` and a commit, and it fails closed. A timeout introduces a new failure mode needing explicit error-translation and API-semantics decisions |
| R-4 | The `F-4` concurrency test's **detection** power is statistical (~1 in 10^5 escape for an unlocked build); the fixed invariant itself is deterministic | `test_auth.py` `test_18d`, recorded in its own docstring | Residual | Workers cannot be made to reach the write in lockstep from outside the API |
| R-5 | `binding_for` hardcodes `account="nova_substrate", endpoint="local:5433"`, so repointing `NOVA_PGDATABASE` yields the **same** execution-binding identity — `I-114(c)` says those fields are in the identity *"precisely so that repointing any of them produces a DIFFERENT binding"* | `write_path.py:817` | Residual | No functional or security effect today: `account` is never compared to the live connection, the constant is symmetric at propose and execute, and `approval.binding_identity` is written but never selected back (`_COLUMNS` omits it). A future one-line fix is safe |
| R-6 | Expired ceremonies are never swept — `_Ceremonies._open` shrinks only via `take` | `auth.py` | Informational | `login_options` is therefore an unauthenticated unbounded allocator. Localhost-only, memory-only, no authorization consequence |
| R-7 | The trust-on-first-use bootstrap window is closed by an **operational** control — not exposing the port until enrolment is done — and the perimeter is localhost, so a local process is inside it | `auth.py` module docstring, limitation 1; ADR 0046 | Stated limitation | Recorded in the ADR as a limitation rather than hidden. `F-4` narrowed it; it did not remove it |
| R-8 | **Test-completeness only. `task` and `authority_revocation` DO have RLS today — this is not a current isolation gap.** The structural RLS assertion checks a hardcoded five-table list (`item`, `scope`, `grant`, `approval`, `audit_record`), while `schema.sql` applies `ENABLE`/`FORCE ROW LEVEL SECURITY` and the `scope_isolation` policy to seven. So `task` and `authority_revocation` are enforced by the schema but not *structurally asserted* by the test | `tests/test_isolation.py:317-334` (`test_8b`), against the RLS loop in `schema.sql` | Test-completeness | Verified on a fresh database: both omitted tables come up `relrowsecurity` and `relforcerowsecurity` true. Both are also covered BEHAVIOURALLY elsewhere — building a fresh database from a schema with `task`'s RLS removed fails `test_tasks`, and removing `authority_revocation`'s fails `test_f3_revocation` `test_18` and `test_provenance_persistence` `test_19` and `test_22`. Notably the full isolation suite passed in the `task` case, and `test_8b` passed in both, because it only checks its five named tables. The defect is therefore PROSPECTIVE: a future scoped table could be added to `schema.sql` and omitted from `test_8b`, which would then assert nothing about it, and whether anything caught it would depend on someone also writing behavioural tests. This is the silent-omission class ADR 0052 element 8a closed for tool declarations. The eventual fix is declarative — derive the scoped-table set from schema metadata (every table carrying a `scope_path` column) rather than maintaining a second human-edited list — and is **DEFERRED**; it is deliberately not implemented here. Context, not a separate residual: `schema.sql` is additive rather than declarative for RLS, so re-applying a schema that omits `ENABLE`/`FORCE` does not disable it on an existing database. That direction is fail-safe, and it is why a first mutation attempt was discarded as invalid and the experiment repeated against a genuinely fresh database |
| ~~R-9~~ | **Test-completeness only, and prospective. NOT a current vulnerability — all five current mappings were independently verified and agree.** `recover()` decides an interrupted execution by whether the `I-93` write-identity row exists, but the writer and the reader derive that identity's reference argument INDEPENDENTLY: the writer hardcodes it per branch (`payload["item_ref"]`, `payload["task_ref"]`, `payload["scope_name"]`, `payload["execution_identity"]`) while the reader looks it up as `REF_ARGUMENT.get(request.tool_name, "")` — a map with an **empty-string default**, so an unmapped tool degrades silently instead of failing closed | `approval_flow.py:348-353` (`recover()`) against `write_path.py:239-245` (`REF_ARGUMENT`) and the per-branch `ref` assignments at `write_path.py:519, 543, 560, 609, 622` | **CLOSED — PR pending** | The two derivations are coupled only by someone remembering. If the writer gains a tool and `REF_ARGUMENT` does not, the reader falls back to `""`, the recomputed identity no longer matches the recorded one, and `recover()` settles a SUCCESSFUL execution as `FAILED` — which by its own contract requires a fresh human decision, so a later approval could permit a SECOND execution. `revoke_authority` is idempotent (`ON CONFLICT DO NOTHING`); `add_scope` and `add_task` are not. THE SUITE DOES NOT CATCH THIS CLASS: removing `COMPLETE_TASK` from `REF_ARGUMENT` left the full 656-test run reporting only the two known date-dependent `test_attention` baseline failures (`test_04`, `test_18`), and the mutation was restored byte-identically under SHA-256 verification. That is evidence about TEST COVERAGE, not evidence that production is broken. The gap is coverage: `recover()` is exercised only through `write_item` — `test_approval_recovery.py` uses `it-1`/`hello` throughout, and `test_f3_revocation.py` only mentions `recover()` in a docstring rather than exercising it for the other tools. The mismatch is concrete: for `complete_task` the writer records `72ff79ffee3fdc34cca31028933d7bdc` (`ref="tk-1"`) while a reader falling back to `""` recomputes `e3c99528c90c9399985da12d9ef77d64`. The eventual fix is to derive the reference ONCE from the tool declaration so writer and reader consume the same source, and to remove the `""` default so an unmapped tool fails closed — the same shape as ADR 0052 element 8a and as R-8's declarative remedy. It is **DEFERRED** and is deliberately not implemented here; no source, test or schema file is touched by this record. **SUPERSEDED 2026-09-10 — implemented and closed; the sentences above describe the code as it stood when the residual was recorded, not as it stands now. See *Residuals closed* below.** |
| R-10 | *(Round 8 audit candidate `G-1`.)* **Alpha exposure. NOT a gateway defect — the Model Gateway enforces `I-96` correctly and fails closed when a restrictive classification is actually supplied. The gap is UPSTREAM, in labelling.** Production assigns exactly two classifications — `INTERNAL` to the instructions and `CONFIDENTIAL` to James's content — so SENSITIVE-PERSONAL and SECURITY-CRITICAL cannot be assigned by any live path. The documented protection *"content whose classification forbids model exposure never reaches a provider; SENSITIVE-PERSONAL crosses only on explicit per-call approval"* is therefore not fully realizable on the current Alpha path | `conversation.py:378-379` (the only assignment) against `core/gateway.py:148-163` (`I-96`) and `DATA_CLASSIFICATION.md:42` (the *Transmitted externally* row) | Significant | CURRENT EXPOSURE, unlike `R-8` and `R-9`. The scenario is ordinary use, not an attack: James stores sensitive-personal information in a scope; it is loaded into the scope context of a later conversation there; production labels it `CONFIDENTIAL`; the gateway sees `CONFIDENTIAL` and permits transmission; no per-call SENSITIVE-PERSONAL approval was ever possible because nothing assigned that classification. Evidence: no production route, form or handler accepts a classification; `SENSITIVE_PERSONAL` and `SECURITY_CRITICAL` appear in no production code outside the enum and the two checks that consume it; `sensitive_personal_approval` is passed by no production caller, only by `slice/tests/test_slice2.py` — which is why the gateway would fail closed if the label ever appeared. WHAT IS WORKING, and must not be misread from this entry: `core/gateway.py` is the sole production model-egress choke point (the only network egress in the repository is the provider transport's `urlopen`, reachable only through `gateway.call`); `I-94`, `I-95`, `I-96`, `I-97` and `I-98` are enforced there; an unestablishable classification denies; the destination is a module constant rather than caller- or model-selected; and provider credentials stay inside the transport boundary. Recommendation: provide a production-authoritative classification assignment path for stored and user-supplied content, then verify end to end that SENSITIVE-PERSONAL and SECURITY-CRITICAL material cannot reach model providers without the intended explicit approval/control. The implementation architecture is a separate decision and is NOT settled here; nothing is implemented by this record. An Alpha-use caveat is carried in `substrate/README.md` §3 |

---

## RESIDUALS CLOSED

Closing a residual does not delete it. The row above keeps its original wording — struck
through, with its disposition changed — because the record of what was wrong is the part
worth keeping, and rewriting it after the fact would make this document a description of
the current code rather than a history of it. Numbers are never reused.

### `R-9` — the writer and the reader derived the execution reference separately

**What was actually wrong.** `recover()` decides an interrupted execution by whether an
`audit_record` row exists under a rebuilt execution identity, and that identity contains a
REFERENCE naming the record the tool wrote. Two independent derivations produced it: the
writer hardcoded the argument name in each of its five branches, while the reader looked it
up in `REF_ARGUMENT` **with an empty-string default**. The comment above that table already
claimed the two "cannot drift". Nothing enforced the claim.

**What was fixed.**

1. `write_path.reference_for(tool_name, arguments)` is now the single derivation, called by
   both the writer (`PostgresItemIntegration.transport_for`, once, before branch dispatch)
   and the reader (`ApprovalService.recover`). Two derivations became one.
2. The empty-string default is gone. An unmapped tool raises `Denied(..., "I-93")` rather
   than addressing nothing, and so does an argument that is absent or empty — an empty
   reference is not an address, and accepting one recreates the defect a layer down.
3. `recover()` settles such a row `unresolved`, not `failed` — the state it already had for
   "we do not know", reached by the same route as a tampered plan. This is the security
   half: `failed` means "did not happen, decide again", so declaring a SUCCESSFUL execution
   failed is what could have permitted a second one.
4. `_verify_reference_totality()` runs at **import**. A tool in `ALL_TOOLS` with no entry,
   or an entry naming an argument its own `input_schema` does not expose, refuses to load.
   The omission is now impossible rather than merely unlikely — MT-6's shape, and ADR 0036
   rule 1's.

**What was declined, and why it is named rather than silently skipped.** The residual said
the reference should be derived "from the tool declaration". Doing that literally means a
fifteenth field on `ToolDefinition`, whose field list ADR 0036 governs — a governance
change, not a bug fix, and not one to slip into a remediation. The explicit table plus an
import-time totality check delivers both stated properties (one source; fails closed) inside
the module that owns the writer and the reader. **If James wants the field on the
declaration instead, that is an ADR 0036 amendment and this fix does not pre-empt it.**

**Verification.** Real PostgreSQL throughout; nothing mocked.

- Regression **656 → 666 tests**, with only the two known date-dependent `test_attention`
  failures and the one deliberate timing skip. No other test changed behaviour.
- Ten new tests: `test_approval_recovery.py` `test_20`, `test_20a`, `test_21`, `test_22`,
  `test_23`, `test_24`, `test_25`; `test_tasks.py` `test_19`, `test_20`, `test_21`. The
  last three close the coverage gap the residual named — recovery had been exercised only
  through `write_item`, so no test ever rebuilt an identity for a tool whose reference is
  not `item_ref`.
- **Six mutations, six detected, no survivors**, every source restored byte-identically
  under SHA-256: the reader's empty default restored (M1); `reference_for` returning `""`
  for an unmapped tool (M2); the import-time check deleted (M3); the entire PRE-FIX
  arrangement reinstated — per-branch writer derivation plus table-reading reader (M4);
  the totality check no longer verifying the argument is declared (M5); an absent or empty
  argument accepted (M6).
- Two of these mutations survived a first round and are recorded because they were real
  gaps, not noise. A per-branch hardcode placed BESIDE the shared derivation survived —
  correctly, since the shared call runs first, which is why M4 was rewritten to remove the
  shared derivation rather than shadow it. And the absent-argument guard survived until
  `test_20a` existed.
- **The exact mutation this residual recorded as invisible** — deleting `COMPLETE_TASK`
  from `REF_ARGUMENT`, which previously left all 656 tests green — now stops **23 test
  modules from importing at all**, because the substrate refuses to load with an incomplete
  reference table.

---

## Deliberate test states — DO NOT "FIX" THESE

A future reader will see a red suite and want to make it green. Two of these three are
**expected**, and turning them green would destroy information.

| State | Where | Why it stays |
| --- | --- | --- |
| `test_attention.test_04` FAILS | `tests/test_attention.py` | Date-dependent. Established baseline; not a regression |
| `test_attention.test_18` FAILS | `tests/test_attention.py` | Date-dependent. Established baseline; not a regression |
| One SKIP | `tests/test_isolation.py:405` | *"timing indistinguishability not tested"* — deliberate, and a skip that became a pass would be a false claim |

**The expected result of the full suite is `FAILED (failures=2, skipped=1)`.** A run reporting
`OK` has not run against PostgreSQL: the suites **skip rather than pass** without their
subject, and `db.available()` must be checked before any result is interpreted. A skipped
security suite is not a pass.

---

## What remains unvalidated

**The real model path has never run.** `conversation → real Anthropic call → proposal →
approval → persisted note → restart → `F-3` revocation` is the one Alpha path with no
execution behind it. Everything downstream of the model call is proven; the call itself is
not.

It is blocked only on `ANTHROPIC_API_KEY` reaching the process environment. The procedure
already exists and is capped — `slice/tests/real_preflight.py` (zero network calls) then
`slice/tests/real_run.py` (5 attempts, 2 successes, `max_tokens=16`). Egress was verified
independently: an uncredentialed request to `api.anthropic.com` returns a genuine
`HTTP 401 … x-api-key header is required`, so the host is reachable and the endpoint is
correct.

**Do not fabricate this call, and do not substitute a mock and report it as validation.**
