# Vertical Slice — Implementation Findings

**Status:** findings from building the slice. **Nothing here amends the architecture.**
No invariant was created, no ADR was accepted, no document in `docs/` was changed to make
implementation easier.

Two findings. The first was resolved from the architecture's own reasoning. **The second
requires James's decision and is currently implemented under the stricter reading, marked
provisional.**

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

### Worth noting for the architecture

`I-114(a)` says "resolved before the authorization decision" without saying *how far*
before. An engineer reading only `I-114` would put resolution first and reintroduce this.
**A one-clause note in `TOOL_AND_INTEGRATION_ARCHITECTURE.md` §3 would close it** — but
that is a documentation change to an Active document and is **not** made here.

---

## Finding 2 — every plan is LOW trust, so "untrusted-derived" may gate everything

**REQUIRES JAMES'S DECISION. Implemented under the stricter reading, provisionally.**

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

### What the slice currently does

`Taint.is_untrusted_derived()` uses **`trust <= LOW`** — the stricter, fail-closed
reading. Every test above `PREPARE` therefore supplies an approval, which is why the
suite is green: **the ambiguity is masked by approval, not resolved by it.**

`slice/core/types.py` marks the method as provisional. **It is not a decision and must
not be read as one.**

### What this is not

Not an invariant defect. `I-99`, `I-40` and `MT-7` are each individually consistent. The
gap is that **no document says whether "untrusted" means a trust level or a provenance
class**, and `I-99`'s arithmetic makes the two coincide for every plan.

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
