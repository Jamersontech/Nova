# Model Trust and Authority

**Status:** **Active** — Section 05, accepted by James 2026-08-14 (ADRs `0025`, `0026`, `0028`).
**Covers:** what model output is, what it may cause, and what it may never establish — taint
propagation, tool-argument authority, risk classification, and the limits of model verification.
**Extends:** [`PROVENANCE_AND_TRUST.md`](./PROVENANCE_AND_TRUST.md) and
[`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §3 (Section 02/03, Active). Neither is
replaced.

**Companion document:** [`MODEL_GATEWAY_ARCHITECTURE.md`](./MODEL_GATEWAY_ARCHITECTURE.md) covers
what may be sent and where. This document covers what comes back.

---

## 1. The Sentence Section 05 Exists to Make True

Section 02 stated the boundary rule and it is correct:

> Untrusted content may **inform** a plan. It may never **escalate** one.
> — [`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §3, `I-40`

**`I-40` is stated about *plans*.** The request pipeline
([`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §2) authorizes the plan and
then, *after authorization*, performs Agent Selection, Tool Selection, and Execution. The plan is
authorized as a unit — deliberately, and for good reasons. But:

```text
 Planning              ← the plan exists here
 Permission Evaluation ← the plan is authorized here
 Approval
 Agent Selection
 Tool Selection        ← bounded: within each agent's closed list
 Execution             ← TOOL ARGUMENTS ARE FIXED HERE
```

**Tool argument values are determined after the authorization that permits the action.** Nothing
in Sections 01–04 says who is authorized to determine them. `I-20` says a model's *ability* to
perform an action is never authorization to perform it — it bars a model from **authorizing**. It
does not bar a model from **parameterizing** an action that is already authorized.

Schema validation ([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md)
§2, §3) checks that an argument is *well-formed*. **A well-formed argument is not an authorized
one.** `recipient: "attacker@example.com"` passes every type check `send_email` declares.

This document closes that, and three adjacent gaps of the same shape.

---

## 2. Model Output Is a Derivation

### 2.1 The taint gap

[`PROVENANCE_AND_TRUST.md`](./PROVENANCE_AND_TRUST.md) §6.2 requires that *"a summary carries the
union of its sources' provenance and the lowest trust among them."* `I-31` requires complete
lineage for **every derived item**. Both are written about **stored items**.

**A model call's output is frequently not stored.** It is produced, used within the execution to
decide the next step or fill an argument, and discarded. Along that path it is the thing that
carries injected instruction from untrusted input into NOVA's actions — and it is exactly the
path on which no lineage obligation was stated.

### 2.2 The rule

**`MT-1` — Model output is a derivation of its inputs, stored or not (`I-99`).** Every model call
output carries:

- the **union of the provenance** of every item in that call's request, including the system
  prompt, retrieved memory, tool results, and conversation history;
- the **lowest trust** among them;
- its own provenance of `model.generated`, which `PROVENANCE_AND_TRUST.md` §2 already rates
  **Low**.

**`MT-2` — Taint survives transience.** An output that is never written to storage carries the
same labels as one that is. The obligation is on the **execution**, not on the storage layer.

**`MT-3` — Taint survives summarization and iteration.** A model call whose input includes a
previous model call's output inherits that output's labels. Chaining does not launder provenance;
the union is taken at every hop, and trust only descends.

**`MT-4` — Model confidence never promotes anything.** Restating `I-39` on this path because it
is where the temptation lives: a model asserting that it has verified something, or expressing
high confidence, changes no epistemic status and no trust value.

### 2.3 What this makes possible

`I-40` and `I-58` become **mechanically evaluable** rather than aspirational. "Was this plan
influenced by untrusted content?" was previously a question with no defined answer, because the
influence travelled through an unlabelled model call. With `MT-1`–`MT-3`, the question is: *does
the labelling on the model output that produced this plan include untrusted provenance?*

**This is a requirement, not a mechanism.** How labels are represented and propagated is
implementation, and it is unverified until Section 31 like every other invariant.

---

## 3. Tool Arguments Are Authorized, Not Merely Validated

**`MT-5` — Every consequence-determining argument is bound by the authorization that permitted
the action (`I-100`).**

A **consequence-determining argument** is one that determines *what the action affects* rather
than *how it is expressed*. NOVA does not attempt an exhaustive list; the test is applied per
tool at definition time:

| Kind | Examples | Bound? |
| --- | --- | --- |
| **Target** | Recipient, address, repository, branch, environment, account, file path | **Yes** |
| **Scope-bearing identifier** | Any identifier naming a scope, client, or credential binding | **Yes** |
| **Magnitude** | Amount, quantity, count, rate, recipient-list size | **Yes** |
| **Destination** | Where output goes, where data is written, what is published | **Yes** |
| **Irreversibility-bearing** | Anything selecting a destructive or irreversible variant | **Yes** |
| **Expressive** | Wording, tone, formatting, ordering, summary text | No |

**`MT-6` — Tool definitions declare which arguments are consequence-determining.** This joins the
fields every tool already declares
([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §2). A tool that
does not declare them is incomplete and is not registered — the same treatment `AGENT_ARCHITECTURE.md`
§2 gives an incomplete agent definition. Adding or changing that declaration is a **C3** change,
because it changes the safety envelope.

**`MT-7` — Three outcomes, and only three.** At the tool PEP, for each consequence-determining
argument:

| Case | Outcome |
| --- | --- |
| The value is covered by the authorization that permitted the action | **Proceed** |
| The value is **not** covered | **Deny.** This is a boundary violation, recorded as a security event (`SECURITY_BOUNDARIES.md` §6), not a retryable error |
| The value is covered but **derived from untrusted content** | **`PREPARE` ceiling.** It may not execute above `PREPARE` without approval naming the external source (`I-40`, `I-58`) |

**The third row is the one that matters.** It is `I-40` applied at argument granularity rather
than plan granularity. A plan authorized to "email the client" cannot be turned by injected
content into an email to a different recipient, and cannot be turned into an email whose
*attachment* was chosen by the injected content, without that becoming a visible approval request
naming the source.

**`MT-8` — Authorization is over an envelope, not a literal.** `MT-5` does not require the PDP to
know every argument value at plan time — which is impossible, and would destroy the
authorize-the-plan-as-a-unit property that
[`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §2 correctly identifies as
valuable. It requires that the authorization fix an **envelope** — which scope, which resources,
which magnitude ceiling, which destinations — and that the tool PEP check the actual value
against that envelope at call time.

```text
Plan authorization  → envelope: scope /business/KAIRO/client-a, tool send_email,
                      recipients ⊆ client-a's contacts, ≤ 1 message
Tool PEP at call    → recipient = ?  ∈ envelope → proceed
                                     ∉ envelope → deny + security event
                                     ∈ envelope but untrusted-derived → PREPARE ceiling
```

**`MT-9` — An unfixable envelope is a denial.** If a tool's consequence-determining arguments
cannot be expressed as an envelope at authorization time, the action is not autonomously
executable. It requires explicit approval showing the actual values — which is precisely what
`PERMISSION_ARCHITECTURE.md` §5 already requires of `HIGH-IMPACT EXECUTE`. No new approval
machinery is introduced.

### What this does not claim

**It does not solve prompt injection.** `T-03`'s residual stands unchanged: injection can still
cause wrong *in-scope* work with *in-envelope* arguments — a badly worded email to the right
recipient, wasted effort, a wrong-but-permitted change. What `MT-5`–`MT-9` bound is **what an
injected argument can reach**, not whether injection can influence output.

---

## 4. Risk Classification Is One-Way With Respect to Models

**The gap.** The request pipeline performs Intent Classification — *"read? analyze? execute? →
sets risk class"* — as a stage of interpretation, and the Interpreter is model-driven.
[`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) §4 says risk *"may be raised by
scope … but never lowered by an agent."* **That protects against lowering a class already
assigned. It does not protect against the class never being high in the first place**, because
the model produced the classification the PDP then evaluates.

**`MT-10` — A model may raise a risk class and may never establish or lower the authorizing one
(`I-101`).**

- The class the PDP evaluates is derived from the **action, resource, scope, and tool's declared
  risk class** — properties of the world, not of the interpretation.
- Model interpretation is an **input that may raise**: if the model reads an instruction as more
  consequential than the declared class, the higher class applies (`PERMISSION_ARCHITECTURE.md`
  §4, "when a classification is uncertain, the higher class applies").
- Model interpretation **never lowers**, and never supplies the class in the absence of a derived
  one. Absence of a derivable class is not `READ`; it is a denial, on `I-52`'s pattern.

**`MT-11` — The tool's declared risk class is a floor, not a starting suggestion.** Section 02
already states that risk may be raised by context and never lowered by an agent, and that the
same tool carries different classes in different contexts. `MT-10` makes the model's role in that
raising explicit and its role in lowering impossible.

---

## 5. Model Verification Is Corroboration, Never Evidence

[`MODEL_ARCHITECTURE.md`](./MODEL_ARCHITECTURE.md) §3 says verification *"should"* not be the same
instance and *"preferably"* not the same provider, and that self-verification in the same call is
weak evidence. **That is advisory language carrying a security property**, and it sits behind no
invariant.

**`MT-12` — A model check never promotes epistemic status (`I-102`).** A result checked by a model
is `model.generated` checked by `model.generated`. Under `PROVENANCE_AND_TRUST.md` §5 that is
*inference at best, never fact*. `system.verified` requires checking against an **authoritative
source**, which a second model is not.

**`MT-13` — A model check never satisfies an approval requirement.** `I-09` — only James approves
— is unchanged and unchangeable here. A verifier reporting success does not convert a
`HIGH-IMPACT EXECUTE` into an autonomous one, and does not reduce a risk class (`MT-10`).

**`MT-14` — Independence is required, not preferred, above `PREPARE`.** Where a model check gates
an action above `PREPARE`:

- it is **not** the same call and **not** the same instance as the one that produced the result;
- it **does not** receive the producing call's untrusted inputs unlabelled — if it must see them,
  they arrive carrying `MT-1`'s labels, so the checker is checking labelled untrusted content
  rather than reading it as context;
- a **different provider** is preferred and is not required, because requiring it would make
  verification unavailable whenever only one permitted provider exists (`MG-9`) — and an
  unavailable check would be silently skipped, which is worse than a same-provider one.

**`MT-15` — The structural verifier is unchanged and is the stronger control.**
[`AGENT_ARCHITECTURE.md`](./AGENT_ARCHITECTURE.md) §1 makes review agents permanently read-only,
and [`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §2 makes Verification a
distinct stage checking declared success criteria. Those are structural. `MT-12`–`MT-14` bound
what the *model* inside that structure contributes: it can find problems, and it cannot certify
their absence.

### Stated plainly

> **NOVA's verification story above `PREPARE` rests on declared success criteria, structural
> read-only review, and James — not on a model checking a model.** Where a model check is used, it
> is a filter that catches errors, never a gate that establishes correctness.

---

## 6. What Section 05 Does Not Fix

Named so they are not mistaken for closed:

| Not fixed | Why |
| --- | --- |
| **Prompt injection influencing in-scope, in-envelope work** | `T-03`'s residual. Only reach is bounded, never influence |
| **Whether an argument is "derived from untrusted content"** | Depends on `MT-1`'s labelling being correct in implementation. A labelling bug is an authorization bug — `[PHYS]`-adjacent, unverified until Section 31 |
| **Model output quality** | Section 41 (evaluation) owns it. Nothing here makes a model correct |
| **A compromised gateway or PDP** | `T-19`, `T-29`. Every rule here is enforced by components that can be compromised |
| **Slow poisoning through accumulated low-trust memory** | `T-10`, unchanged |

Invariants: `I-99`–`I-102`.
Threats: `T-28`, `T-32`.
