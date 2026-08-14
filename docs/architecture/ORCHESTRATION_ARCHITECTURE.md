# Orchestration Architecture

**Status:** **Active** — Section 02, approved by James 2026-08-12.
**Covers:** the Orchestrator and the workflow engine.

---

## 1. The God-Object Problem

An orchestrator that interprets, plans, holds domain knowledge, decides permissions, calls
tools, manages credentials, and formats replies becomes the single unmaintainable centre
of the system. Every future feature lands in it; nothing can be tested in isolation; no
part can be replaced.

**The Orchestrator is therefore split into five components with narrow contracts**, and is
stripped of two responsibilities it must never hold.

```mermaid
flowchart LR
    IN["Intent<br/>+ Context Token"] --> I["INTERPRETER"] --> P["PLANNER"] --> D["DISPATCHER"] --> V["VERIFIER"] --> A["ASSEMBLER"] --> OUT["Response"]
    P -.consults.-> POL["Policy"]
    D -.consults.-> POL
    D --> RT["Agent Runtime"]
    V -.may re-plan.-> P
```

| Component | Owns | Never owns |
| --- | --- | --- |
| **Interpreter** | Structured intent from expression | Deciding what to do about it |
| **Planner** | A plan — a **security object** with declared schema and identity (§2.1) | Executing anything; **authorizing the plan it produced** |
| **Dispatcher** | Delegating steps to agents with narrowed tokens | Doing work itself |
| **Verifier** | Checking results against success criteria | Producing results |
| **Assembler** | The answer James sees, with what was done | Deciding what happened |

**The two responsibilities the Orchestrator must never hold:**

1. **Domain knowledge.** It does not know how KAIRO invoices work or what a good website
   is. That belongs to domain agents. An orchestrator that accumulates domain logic becomes
   the god-object by a slower route.
2. **Credentials.** It never holds a secret. Credentials resolve at the tool boundary.

---

## 2. Request Pipeline

```text
User Request
 ↓  Interpretation      what is being asked
 ↓  Context Resolution  where it applies      → ask if materially ambiguous
 ↓  Intent Classification  read? analyze? execute?  → sets risk class
 ↓  Planning            steps, dependencies, rights required
 ↓  Permission Evaluation  Policy: allow / deny / approval required
 ↓  Approval            James, if the risk class requires it
 ↓  Agent Selection     match responsibility, scope, rights
 ↓  Tool Selection      within each agent's closed list
 ↓  Execution           narrowed tokens, isolated instances
 ↓  Verification        against declared success criteria
 ↓  Result Assembly     result + what was done + what is uncertain
 ↓  User Response
```

Two properties of this order matter:

- **Permission is evaluated after planning but before any execution**, so the full plan is
  authorized as a unit rather than step-by-step surprises mid-execution.
- **Verification is a distinct stage.** "The tool returned 200" is not verification.
  Verification checks the declared success criteria — and may send the plan back.

**A returned plan re-enters the pipeline at Planning, not at Execution.** ***PROPOSED — added by
Section 08, not yet accepted*** *(2026-08-14; authority
[ADR 0034](../decisions/0034-the-plan-is-a-security-object.md) and
[ADR 0035](../decisions/0035-section-08-amendments-to-accepted-architecture.md), both Proposed;
removed if either is rejected).* Re-planning produces a **new plan** with a new identity, which
passes through Permission Evaluation and Approval again (§2.1, §2.2, `I-113`). **A re-planned plan
never inherits the prior plan's authorization because the objective is unchanged.**

---

## 2.1 The Plan Is a Security Object

***PROPOSED — added by Section 08, not yet accepted*** *(2026-08-14; same authority as above).*

**The gap this closes.** §1 previously enumerated a plan as *"steps, dependencies, required
rights"* — three words in a table cell, and the only description of it in the repository. Every
other security object in NOVA has a declared schema: the Context Token
([`MASTER_ARCHITECTURE.md`](./MASTER_ARCHITECTURE.md) §2.2), a Delegation
([`SCOPE_AND_IDENTITY_MODEL.md`](./SCOPE_AND_IDENTITY_MODEL.md) §5), a Credential Binding
([`AUTHORIZATION_MODEL.md`](./AUTHORIZATION_MODEL.md) §5), a Session
([`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §4), an agent definition, a tool definition.
**The plan was the one object the authorization model treats as its unit while having no structure**
— so `I-40`'s rule that untrusted content may not escalate a plan had nothing to attach to, `I-109`
had nothing to bind to, and nothing could detect a plan changing between authorization and
execution.

```text
Plan
├── identity            deterministic, derived as I-93 derives event identity
├── steps               ordered, each naming its action, resource and required rights
├── dependencies        which steps require which predecessors verified
├── required rights     the union the plan needs — never wider than the requester holds
├── declared risk class the highest class any step carries
├── scope               the single bound scope this plan operates in (I-95, I-86)
├── provenance/taint    the union of contributing provenance and the lowest trust among
│                       them, carried under I-99 and persisted under I-111
└── cost estimate       drawn against the root execution budget (I-105, I-108)
```

**`I-112` fixes four properties:**

**Identity is deterministic**, derived by the construction `I-93` already established for audit
records and `I-109` already reuses for approval binding. **No new identity mechanism is invented.**

**The plan is immutable once authorized.** Any material change — a step, a resource, a right, the
risk class, the scope, the tool set, the cost — **produces a new plan with a new identity requiring
new authorization.** A plan whose identity is reused after mutation is not the plan that was
authorized.

**Taint is a persisted security property, not prose.** The plan carries the union of its inputs'
provenance and the lowest trust among them, under `I-99` and `I-111` — **not a parallel provenance
system.** This is what makes `I-40` enforceable: a plan influenced by untrusted or quarantined
content carries that fact to the authorization boundary, and cannot exceed `PREPARE` without
approval naming the source. **`I-40` is not weakened; it is given the carrier it always required.**

**A plan is never authoritative because a model produced it.** The Planner is a model
([`MODEL_TRUST_AND_AUTHORITY.md`](./MODEL_TRUST_AND_AUTHORITY.md) §1), its output is
`model.generated` at low trust (`I-99`), and producing a plan confers nothing (`I-20`). The plan
becomes authoritative only when authorized — never before, and never by assertion.

---

## 2.2 Envelope Authorization and Per-Action Checking

***PROPOSED — added by Section 08, not yet accepted*** *(2026-08-14; same authority as above).*

**Four accepted documents described plan authorization at three different granularities:** §2 above
(*"the full plan is authorized as a unit"*), `AUTHORIZATION_MODEL.md` §1 and §3 (*"this **specific
action** against this **specific resource**"*, ten singular steps),
`PERMISSION_ARCHITECTURE.md` §5 (*"one action, in one context, at one time"*), and
`EXECUTION_ARCHITECTURE.md` §2.1 (*"James approves the plan"*). An engineer building the
Planner→PDP interface had to choose between defensible readings that produce materially different
systems. **`I-113` reconciles them without amending the PDP.**

```text
Plan authorization  → ENVELOPE: scope, risk ceiling, tool set, cost ceiling, composition
Each action         → the unmodified ten-step sequence, at its own enforcement point
                      ∈ envelope → proceed
                      ∉ envelope → deny, even if the action alone would be permitted
```

**Neither substitutes for the other.** Plan authorization **never** replaces per-action
authorization, and per-action authorization **never** permits exceeding the envelope. This is the
same structure `MT-8` uses for tool arguments and `I-106` uses for token issuance — a third
application of a pattern the architecture already relies on, not a new one.

**Composition is bounded by the envelope.** A plan's individually permissible actions **must not
exceed the authorized envelope when taken together.** Permitted read + permitted write + permitted
send do not silently compose into an unauthorized higher-level operation. The plan declares enough
(§2.1) for enforcement to evaluate the collection rather than only its members.

**The PDP is not modified and does not become a composition engine.** It keeps evaluating exactly
what it evaluates today; the envelope constrains what may be submitted to it. `P-7` and `P-11`
stand.

**Stated honestly:** this makes composition **governable, not solved.** A plan whose declared
envelope is wide enough to contain a dangerous sequence is authorized correctly and is still
dangerous — the same limit ADR 0025 records for over-wide argument envelopes.

---

## 3. Orchestrator Contract

**Inputs:** structured intent, Context Token, identity, conversation continuity,
constraints (cost/time/risk).

**Outputs:** the result, an account of what was done, unresolved items, epistemic labels
(Constitution §14), and a trace id.

**Non-responsibilities:** domain logic, credentials, tool implementation, authorization
decisions (it *asks* Policy), UI decisions, memory curation.

**Failure modes and responses:**

| Failure | Response |
| --- | --- |
| Intent unclear | Ask. Do not guess above `PREPARE` |
| Context ambiguous | Ask. Never pick the likelier scope |
| Permission denied | Report plainly, with what would be needed |
| No capable agent | Report the gap. Do not improvise with a wrong-fit agent |
| Step fails | Reliability policy: retry, compensate, or escalate |
| Partial completion | Report exactly what completed and what did not |
| Verification fails | Do not present as success. Re-plan or escalate |
| Approval denied | Stop. Leave no partial state |

**Escalation always goes upward** — to James, never sideways to another agent for a second
opinion that manufactures consent.

---

## 4. Workflow Engine

Workflows are durable, multi-step, resumable units of work. Anything spanning approvals,
external systems, or long durations is a workflow, not a request.

```text
Plan → Execute → Verify → Approve → Deploy → Monitor
```

**Required capabilities:**

| Capability | Requirement |
| --- | --- |
| Sequential | Ordered steps with explicit dependencies |
| Parallel | Independent steps concurrently, each in its own context |
| Dependencies | A step runs only when its prerequisites verified |
| Retries | Bounded, with backoff, only for idempotent steps |
| Pauses | Indefinite waits for approval or external events |
| Failures | Explicit handling; never silent |
| Resumption | Resume from last verified step, not from the beginning |
| Cancellation | Stoppable at any point, leaving a known state |

**State is durable and inspectable.** A workflow that cannot say which step it is on, what
it has done, and what it is waiting for cannot be recovered or trusted.

**Each step carries its own narrowed token.** A workflow spanning two clients holds no
token spanning both — it holds two, used separately.

**Partial completion is a first-class outcome**, not an error state to be hidden. Handling
is defined in [`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md).

**Resumption re-checks the authorization binding.** ***PROPOSED — added by Section 08, not yet
accepted*** *(2026-08-14; same authority as §2.1).* A workflow that resumes from its last verified
step re-checks `I-109`'s binding against **current** state before the next step, and **fails closed**
if it no longer matches (`I-113`). This is the case §3 of
[`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md) describes as normal: a plan's first
action changes the world, and the authorization for its second action was evaluated against the
world before that change. **Resumption is not a continuation of the old authorization; it is a fresh
check of whether the old authorization still holds.**
