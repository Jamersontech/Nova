# 0025 — Model Output Is an Untrusted Derivation, and Tool Arguments Are Authorized

**Status:** **Accepted**
**Proposed:** 2026-08-14 — Section 05
**Accepted:** 2026-08-14 by James
**Section:** 05

## Decision

Two rules, joined because the second is unenforceable without the first.

**1. Model output is a derivation of its inputs, whether or not it is stored (`I-99`).** It
carries the union of the provenance of every item in its request and the lowest trust among them,
in addition to its own `model.generated` provenance. Taint survives transience, chaining, and
summarization. Model confidence promotes nothing (`I-39`).

**2. Tool arguments are authorized, not merely validated (`I-100`).** Every
consequence-determining argument — target, scope-bearing identifier, magnitude, destination,
irreversibility-bearing selector — is checked at the tool enforcement point against the
**envelope** fixed by the authorization that permitted the action:

| Case | Outcome |
| --- | --- |
| Covered by the authorization | Proceed |
| Not covered | **Deny** — a boundary violation and a security event, not a retryable error |
| Covered but derived from untrusted content | **`PREPARE` ceiling** — no execution above `PREPARE` without approval naming the source (`I-40`, `I-58`) |

**3. Risk classification is one-way with respect to models (`I-101`).** A model may raise a risk
class. It may never lower one, and may never supply the authorizing class in the absence of one
derived from the action, resource, scope and tool.

## Context

Section 02 fixed that untrusted content may inform a plan and never escalate one (`I-40`), and
Section 03 extended it to Work Orders (`I-58`). Section 02 also fixed that a model's *ability* to
act is never authorization to act (`I-20`).

## Problem

**Three gaps of the same shape, all downstream of where the existing rules stop.**

**`I-40` is stated about plans, and arguments are fixed after the plan is authorized.** The
request pipeline ([`ORCHESTRATION_ARCHITECTURE.md`](../architecture/ORCHESTRATION_ARCHITECTURE.md)
§2) runs Permission Evaluation before Tool Selection and Execution — deliberately, so the plan is
authorized as a unit. Argument *values* are therefore determined **after** the authorization that
permits the action, by model output that may have read untrusted content. Schema validation
([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md)
§2) establishes that an argument is well-formed, which is a type check and not an authority check.
`recipient: "attacker@example.com"` is a valid string.

**`I-20` bars authorizing, not parameterizing.** Nothing said who is authorized to determine an
argument value.

**Taint had no carrier.** `PROVENANCE_AND_TRUST.md` §6.2 and `I-31` require lineage for **derived
items** — stored things. A model call's output is usually *not* stored: it is produced, used to
fill an argument or choose a step, and discarded. That transient path is precisely how injected
instruction reaches an action, and it was the one path with no labelling obligation. Without it,
"was this plan influenced by untrusted content?" — the question `I-40` and `I-58` both turn on —
has no defined answer.

**Risk class was model-derived.** Intent Classification *"sets risk class"* and the Interpreter is
model-driven. `PERMISSION_ARCHITECTURE.md` §4 forbids an agent *lowering* a class; it does not
address a class that was never set high, because the model that read the injected content
produced the classification the PDP then evaluated.

## Options Considered

1. **Do nothing; rely on `I-40` at plan granularity.** Zero cost. Leaves the entire post-
   authorization argument surface uncovered, and leaves `I-40` unevaluable because taint has no
   carrier.
2. **Require every argument value to be known and authorized at plan time.** Maximally strict.
   Destroys the authorize-the-plan-as-a-unit property, which
   `ORCHESTRATION_ARCHITECTURE.md` §2 identifies as valuable and which prevents step-by-step
   surprises mid-execution. Also impossible in practice: most argument values are results of
   earlier steps.
3. **Envelope authorization plus argument checking at the tool PEP, with taint propagation.**
   Authorization fixes bounds — which scope, which resources, which magnitude, which destinations
   — and the actual value is checked against those bounds at call time, with untrusted-derived
   values ceilinged at `PREPARE`. Preserves plan-level authorization; requires tools to declare
   which arguments are consequence-determining, and requires taint labelling to be correct.
4. **Human confirmation of every argument.** Safe and unusable. Directly produces the approval
   fatigue [`KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) records as a security failure, and
   would push James toward reflexive approval on exactly the requests that matter.

## Decision Made

Option 3, with taint propagation (rule 1) as its precondition.

## Reason

**The envelope is the only formulation that puts the check where the value exists without
destroying the property that makes plan authorization useful.** Option 2 moves the check to a
point where the value does not yet exist; option 1 leaves it at a point where nothing checks it.
Option 3 splits the decision from the check — the PDP fixes bounds once, the enforcement point
compares once — which is the same split already used successfully between the PDP and its five
enforcement points.

**Rule 1 is not optional scaffolding.** Without it, the third row of the table — the
untrusted-derived case, which is the entire prompt-injection defence — cannot be evaluated,
because nothing knows an argument came from injected content. `I-40` and `I-58` have been in force
since Sections 02 and 03 with no defined way to answer the question they ask. Rule 1 supplies it.

## Tradeoffs

**Advantages:** the post-authorization argument surface is closed; `I-40`/`I-58` become
evaluable rather than aspirational; injected content cannot redirect an authorized action to a new
target, magnitude or destination without either a denial or a visible approval naming the source;
risk classification stops depending on a model's reading of possibly-injected text; no new
approval machinery — `MT-9` reuses `HIGH-IMPACT EXECUTE`'s existing requirement to show what will
change.

**Disadvantages:** every tool must declare its consequence-determining arguments, and that
declaration is a **C3** change, so tool authoring becomes heavier; a mis-declared argument is an
authorization hole that looks like a complete tool definition; taint labelling is pervasive and
its correctness is now load-bearing — **a labelling bug is an authorization bug**; envelopes are
harder to write than allow-lists and an over-wide envelope silently reintroduces the gap; more
work lands at `PREPARE` awaiting approval, which pushes against approval fatigue in the other
direction.

**The `MT-9` case is a genuine cost.** A tool whose consequence-determining arguments cannot be
expressed as an envelope is not autonomously executable at all. Some useful automation will fall
into that category and will require approval showing actual values.

## Consequences

- [`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md)
  §2 gains a declared field; a tool without it is not registered. Authorized by
  [ADR 0028](./0028-section-05-amendments-to-accepted-architecture.md).
- The tool enforcement point does argument-envelope checking in addition to what it already does.
  It gains no decision authority — `I-77`'s rule holds: enforcement can only deny.
- **Prompt injection is not solved and is not claimed to be.** `T-03`'s residual stands: injection
  can still cause wrong in-scope work with in-envelope arguments. What is bounded is *reach*, not
  *influence*. Recorded as `T-28`.
- Attribution of "derived from untrusted content" is only as good as the labelling. Recorded in
  [`KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md).

Invariants: `I-99`–`I-101` (new). `I-20`, `I-31`, `I-39`, `I-40`, `I-58`, `I-77` untouched.

## What Would Change This

A demonstration that envelopes cannot be authored precisely enough to be meaningful — that in
practice every envelope is written wide enough to admit the attack it exists to stop. That would
argue for option 4 on a defined subset of tools rather than for abandoning argument authorization.
