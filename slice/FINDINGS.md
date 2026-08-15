# Vertical Slice — Implementation Findings

**Status:** findings from building the slice. **Nothing here amends the architecture.**
No invariant was created, no ADR was accepted, no document in `docs/` was changed to make
implementation easier.

Two findings, **both now resolved**. The first from the architecture's own reasoning; the
second by James on 2026-08-15. Both resolutions are documented in `docs/` as **Proposed**
amendments under existing ADRs — no ADR was accepted and no invariant was created.

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
