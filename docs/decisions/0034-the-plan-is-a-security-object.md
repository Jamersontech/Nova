# 0034 — The Plan Is a Security Object, Authorized as an Envelope and Checked Per Action

**Status:** **Accepted** — 2026-08-15
**Proposed:** 2026-08-14 — Section 08
**Accepted:** 2026-08-15 — by James, at the ADR Decision Gate, on implementation evidence from the three vertical slices
**Section:** 08
**Resolves:** `S8-D1`, `S8-D2`, `S8-D3`

## Decision

**1. A plan is a first-class security object (`I-112`).** It carries a declared schema — identity,
steps, dependencies, required rights, declared risk class, scope, provenance/taint union, cost
estimate — and a **deterministic identity** derived by `I-93`'s existing construction. **Once
authorized it is immutable**; any material change produces a **new plan** requiring new
authorization. Its taint is a **persisted security property** carried under `I-99`/`I-111`, not a
statement in prose. **A plan is never authoritative because a model produced it.**

**2. Authorization is an envelope plus a per-action check (`I-113`).** The plan is authorized as a
unit, fixing scope, risk ceiling, tool set, cost ceiling and composition. **Every individual action
is still evaluated independently** by `AUTHORIZATION_MODEL.md` §3's unmodified ten-step sequence at
its own enforcement point. **Plan authorization never replaces per-action authorization, and
per-action authorization never permits exceeding the envelope.** `PERMISSION_ARCHITECTURE.md` §5's
*"one action, in one context, at one time"* is preserved exactly: a plan approval is an **envelope**
approval, never blanket authorization for future actions.

**3. Composition is bounded by the envelope.** A plan's individually permissible actions **must not
exceed the authorized envelope when taken together**. The plan declares enough for enforcement to
detect this: permitted read + permitted write + permitted send do not silently compose into an
unauthorized higher-level operation.

**4. Re-planning creates a new plan; resumption re-checks the binding.** A re-planned plan returns
through Permission Evaluation and **cannot inherit the prior authorization because the objective is
unchanged**. Resumption after partial execution re-checks `I-109`'s binding against current state
before the next step, and **fails closed** if it no longer matches. Replanning loops fail closed to
escalation. **Bounded by the existing root-execution budget** (`I-105`, `I-108`) — no new accounting
mechanism and no arbitrary iteration limit.

## Context

`ORCHESTRATION_ARCHITECTURE.md` §2 places Permission Evaluation after Planning so that *"the full
plan is authorized as a unit"*. Section 05's `MT-8` established the envelope-then-check structure
for tool arguments. Section 06's `I-109` bound approvals to nine effective-authorization properties.

## Problem

**The plan was the unit of authorization in four accepted documents and defined by none of them.**

`ORCHESTRATION_ARCHITECTURE.md:31` enumerates it as *"A plan: steps, dependencies, required
rights"* — three words in a table cell. There is no plan record, field list, identity, version,
immutability rule, lifecycle, taint carrier, or re-authorization rule. **This is unique.** Every
other security object in NOVA is fully specified: Context Token, Delegation, Credential Binding,
Session, agent definition, tool definition, item temporal state.

**Three consequences, each independently serious.**

**Authorization granularity was contradictory.** `ORCHESTRATION_ARCHITECTURE.md:64` says the full
plan is authorized as a unit; `AUTHORIZATION_MODEL.md` §1 and §3 evaluate *"this **specific action**
against this **specific resource**"* in ten singular steps; `PERMISSION_ARCHITECTURE.md:151` says an
approval authorizes *"one action, in one context, at one time"*; `EXECUTION_ARCHITECTURE.md:180`
says *"James approves the plan"*. **An engineer building the Planner→PDP interface had to choose,
and both readings were defensible.**

**Sections 05 and 07 delivered taint to a boundary with no receiver.** `I-99` and `I-111` carry
provenance and lowest trust with great care; `I-40` requires that a plan influenced by untrusted
content not exceed `PREPARE` without approval naming the source. **`I-40` is stated on plans, and
the plan had no object to carry taint on.** The rule was correct and unenforceable.

**Nothing checked the plan.** The Verifier checks *results* against success criteria
(`ORCHESTRATION_ARCHITECTURE.md:32`). Token issuance is independently checked (`I-106`), grants are
(`I-10`), tool arguments are (`I-100`), egress is (`I-94`) — **the plan was checked by nobody**,
and `SECURITY_BOUNDARIES.md:131`'s claim that compromising the orchestrator does not bypass
enforcement is true for credentials and silent about the plan. Nothing detected mutation between
authorization and execution, and audit could not answer *"which plan was authorized?"*

## Options Considered

**For what a plan is:**
1. **Leave it an intermediate model output**, relying on per-action checks alone. Cheapest. Leaves
   composition and plan-mutation permanently unaddressable, and leaves `I-40` unenforceable.
2. **A security object with schema, identity and immutability.** Costs a schema and an identity
   construction; gives every existing mechanism something to attach to.

**For granularity:**
1. **Per plan only.** Matches "authorized as a unit"; would require the PDP to become a
   plan-composition engine, contradicting `AUTHORIZATION_MODEL.md` §3 and `P-7`.
2. **Per action only.** Matches the PDP as built; abandons "authorized as a unit", destroys the
   no-surprises property `ORCHESTRATION_ARCHITECTURE.md` §2 identifies as valuable, and leaves
   composition ungoverned.
3. **Envelope plus per-action check.** Reconciles all four documents without amending the PDP.

**For re-planning:** inherit the prior authorization if the objective is unchanged; re-authorize
always; re-authorize only on material change.

## Decision Made

Security object · envelope plus per-action check · re-planning always produces a new plan.

## Reason

**The envelope-then-check structure is not new here — it is the third application of a pattern the
architecture already relies on.** `MT-8` authorizes a tool-argument envelope and checks the value at
the tool PEP. `I-106` verifies an issuance envelope and lets the PDP still decide each access.
Section 08 applies the same shape one level up. That is why the PDP needs no modification: **it
keeps evaluating exactly what it evaluates today**, and the envelope constrains what may be
submitted to it.

**Giving the plan an object is what makes the existing mechanisms operate rather than adding new
ones.** `I-40` gains a taint carrier. `I-109` gains something to bind to. `I-93`'s deterministic
identity gains a second reuse. `I-105`/`I-108` already bound the cost. **No competing mechanism is
created, and no new trust dependency is introduced.**

**"Re-authorize only on material change" was rejected** because "material" would be judged by the
Planner — a model — which is precisely `I-101`'s prohibited shape. Every re-plan producing a new
plan is more expensive and has no judgment call in it.

**No numeric replan limit** is introduced. `I-105`'s root budget already bounds the loop, and an
arbitrary iteration cap would be a second number governing a resource the budget already governs —
the reasoning `AG-10` used to reject a fan-out limit.

## Tradeoffs

**Advantages:** `I-40` becomes enforceable for the first time; plan mutation, composition and
stale-approval attacks become detectable; audit can name the authorized plan; the four documents
stop contradicting each other; the PDP is untouched; no new mechanism, component, or trust
dependency.

**Disadvantages:** **every re-plan costs a full authorization cycle**, and verifier-driven
re-planning is a normal occurrence rather than an exception — this is real latency and real PDP
load on a common path. **The plan schema is a new mandatory declaration surface**, and an
under-declared plan is an envelope too wide to catch the composition it was meant to catch — the
same failure mode ADR 0025 records for tool argument declarations. **Composition detection is only
as good as what the plan declares**, and the architecture cannot enumerate every dangerous
composition in advance.

**Stated honestly:** this makes composition *governable*, not *solved*. A plan whose declared
envelope is wide enough to contain an exfiltration sequence is authorized correctly and is still an
exfiltration sequence.

## Consequences

- `ORCHESTRATION_ARCHITECTURE.md` gains the plan object and composition rules;
  `PERMISSION_ARCHITECTURE.md` §5, `AUTHORIZATION_MODEL.md` §3 and
  `RELIABILITY_ARCHITECTURE.md` §3–§4 are amended — authorized by
  [ADR 0035](./0035-section-08-amendments-to-accepted-architecture.md).
- **`I-40` is not weakened.** It is given the carrier it always required.
- **The PDP is not modified** and does not become a composition engine. `P-7` and `P-11` stand.
- A compromised orchestrator can still construct any plan it likes — but the plan is now compared
  against its authorization at each enforcement point, and `T-36` records what remains.
- Audit gains plan identity under the existing model: a plan authorization is a decision (`W-2`) in
  the scope it concerned; execution records remain `W-1`. **No new audit authority.**

Invariants: `I-112`–`I-113` (new). `I-40`, `I-93`, `I-99`–`I-102`, `I-104`–`I-111` untouched.

## What Would Change This

Evidence that per-action authorization inside an authorized envelope is redundant in practice —
which would argue for narrowing what the envelope must re-check, **not** for letting plan approval
stand in for action authorization.
