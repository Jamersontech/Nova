# NOVA Canonical AI Terminology

**Status:** Active — established in Section 01.
**Purpose:** Fix the meaning of NOVA's core AI vocabulary so that documentation, code,
and AI agents use the same words for the same things.

These terms must not be used interchangeably. When a document, identifier, or interface
label uses one of these words, it means what is written here. When new terminology is
introduced in a later section, it is added to this file in the same session it is
introduced.

---

## Core Terms

### NOVA
The overall AI operating system and intelligence interface. NOVA is the whole system, not
any single model, agent, or interface within it.

### Orchestrator
The system responsible for understanding requests, determining context, planning work,
coordinating execution, delegating tasks, and assembling results. There is one
orchestration role in the authority hierarchy; it is not a synonym for "agent."

### Agent
A specialized AI worker with defined responsibilities, tools, context, permissions,
inputs, outputs, and success criteria. An agent is a governed unit of work, not merely a
prompt or a model call.

### Manager / Coordinator
A system or agent responsible for coordinating other agents or work. A coordinator sits
between the orchestrator and specialist agents; it delegates and assembles, and it holds
no authority beyond what it was delegated.

### Tool
A callable capability that allows an agent or system to perform a specific operation. A
tool performs an operation; it does not decide whether the operation should happen.

### Workflow
A defined sequence of tasks, tools, decisions, and/or approvals.

### Task
A unit of work that can be assigned, executed, monitored, and completed.

### Context
Information relevant to the current operation. Context is scoped and permission-
controlled; being able to retrieve information does not make it in-context.

### Memory
Information intentionally retained for future use. Memory is deliberate retention;
transient context is not memory.

### Integration
A connection between NOVA and an external system.

### Credential
A secret, token, authorization grant, or mechanism that permits access to an external
system. A credential is an independent security object, distinct from the integration
that uses it and from the environment it is scoped to.

### Environment
An isolated technical context associated with a project. (See
[`../DOMAIN_MODEL.md`](../DOMAIN_MODEL.md) §7.)

### Permission
A rule defining what an identity, agent, tool, or system may access or execute.

### Approval
Explicit authorization required before an action is executed. Approval is granted by a
human for a specific action; a permission is a standing rule. They are not
interchangeable: a permitted action may still require approval.

---

## Terms Added in Section 02

Defined in full in [`../architecture/`](../architecture/README.md); registered here because
this file is the canonical vocabulary.

### Identity
A durable claim to be a specific actor. NOVA distinguishes six classes: human, system,
agent, coding-agent, service, and client. → [`../architecture/IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md)

### Authentication
Proving an identity is genuine. Distinct from **authorization**, which decides whether that
identity may act.

### Authorization
Deciding whether an identity may perform an action. Distinct from **authentication**.

### Role
A named bundle of permissions attachable to an identity. An identity is *who*; a role is
*what kind of actor*. One identity may hold several roles.

### Scope
A node in NOVA's scope tree — simultaneously a context anchor, permission boundary, memory
partition, and credential partition. Business, Client, Project, Environment, Life Area, and
Life Thread are all *kinds of scope*. → [`../architecture/DOMAIN_ARCHITECTURE.md`](../architecture/DOMAIN_ARCHITECTURE.md)

### Context Token
The scoped, expiring object carried by every operation, naming the scope path and rights it
is authorized for. The mechanism by which context becomes enforceable rather than advisory.

### Work Order
What an **external coding agent** receives instead of a Context Token: a task, one
repository, one branch, one sandbox, brokered credentials, and success criteria. It confers
no authority inside NOVA. → [`../architecture/EXECUTION_ARCHITECTURE.md`](../architecture/EXECUTION_ARCHITECTURE.md)

### Risk Class
The consequence classification of an action — READ, ANALYZE, RECOMMEND, PREPARE, EXECUTE,
HIGH-IMPACT EXECUTE, IRREVERSIBLE — which determines what approval is required.

### Execution
One attempt to perform work, authorized by exactly one context and performed by one agent.
The unit that audit, cost, and observability attach to.

### Coding Agent
An **external** system that writes or runs code on NOVA's behalf (Claude Code, Codex).
Outside NOVA's trust boundary. **Not** a NOVA agent, despite the shared word — see the
table below.

---

## Terms Added in Section 03

Defined in full in [`../architecture/`](../architecture/README.md).

### Scope Kind
What a scope *is* — `business`, `client`, `project`, `environment`, `area`, `thread`,
`holding`. Kinds differ in what may attach to them, never in how access works. New kinds must
satisfy the scope contract. → [ADR 0015](../decisions/0015-extensible-scope-kinds.md)

### Ownership
The scope a resource belongs to. **Not** an identity, and not its creator — the creator is
provenance. An agent never owns anything.

### Execution Identity
The ephemeral, single-context identity that authorization actually evaluates. Derived by
*intersection* of agent definition, granting identity, token, and risk ceiling — never union.

### Credential Binding
A scoped, stateful **reference** to an external secret. What NOVA stores. The secret itself is
never in the data model. → [ADR 0009](../decisions/0009-credentials-are-references.md)

### Classification
The handling level of an item — PUBLIC, INTERNAL, CONFIDENTIAL, CLIENT-CONFIDENTIAL,
SENSITIVE-PERSONAL, SECURITY-CRITICAL — controlling storage, access, memory, logging, model
exposure, transmission, retention, deletion, and export.

### Provenance
Immutable record of where information came from. Distinct from **trust** (revisable weight of
the source) and from **epistemic status** (fact / inference / assumption / unknown).

### Trust
The weight a source earns, evaluated at use time and revisable without rewriting history.

### Lineage
The complete set of items an item was derived from. The precondition for classification
inheritance, deletion cascade, and leak diagnosis.

### Derived Item
Anything produced from other items — summary, aggregate, embedding, index entry, report.
Inherits the strictest classification and narrowest scope among its sources.
→ [ADR 0010](../decisions/0010-derived-data-inheritance.md)

### Supersession
Replacing an item with a new version while retaining the old as history. NOVA does not update
meaningful information in place.

### Tombstone
The record left by deletion: identity, scope, classification, time, authorization — **never
content**.

### Grant / Denial
A **grant** is an explicit right for a subject over a scope. A **denial** is an explicit
refusal that overrides any grant. The *absence* of a grant is not a denial — it is default
deny.

### Invariant
A property every implementation must satisfy, written to be testable.
→ [`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md)

---

## Terms Added in Section 04

> **PROPOSED — not yet accepted.** *(Marked 2026-08-13, N-9.)* This file is **Active Section 01**
> material, so every change to it is a C3 amendment. **James approved making this amendment
> through Section 04 on 2026-08-13**; he has **not** accepted ADRs `0016`–`0021`. Every term in
> this section stands or falls with them, and is removed rather than retained if they are
> rejected. Terms in the Core, Section 02, and Section 03 blocks above are accepted and unchanged.

Defined in full in [`../architecture/`](../architecture/README.md).

### Enforcement Layer
The layer beneath query construction that applies scope restriction, deriving it from an
execution's bound scope identity and **not** from the Policy Decision Point. Distinct from the
PDP: the PDP decides *whether*, the enforcement layer makes out-of-scope data *unreachable*.
It is **additional to** the Data Access PEP, never a replacement — every data access still
asks the PDP (`I-77`).

**On "independent":** the enforcement layer is independent **of the PDP**, and that is the whole
of the claim. Both it and the PDP take their input from the same Context Token, so they are
**not** independent of the Context service; compromising it defeats both together (`T-23a`).
**General two-of-two independence is not claimed** (`I-62`). *(Qualified 2026-08-13, N-9 — the
earlier entry read "Deliberately independent" without this bound, which is the claim H-2
withdrew.)*
→ [ADR 0016](../decisions/0016-isolation-enforced-below-query-layer.md),
[ADR 0017](../decisions/0017-isolation-independent-of-pdp.md)

### Data-Access Boundary
The **trusted platform responsibility**, at the entrance to the Knowledge & Data layer, that
establishes an execution's storage scope binding and opens the scope-bound channel. It derives
the binding solely from the Context Token's scope path, inside the TRUSTED zone. **Not a
standalone microservice, not a new subsystem, and not separately deployable.** It owns *the
binding*, never *the decision*: it never consults the PDP, creates no authorization authority,
and cannot permit an access — it can only refuse to open a channel. Application and agent code
cannot open, set, widen, re-bind, or reuse a binding (`I-61`, `I-78`, `I-86`).
→ [`../architecture/ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) §4.1,
[ADR 0017](../decisions/0017-isolation-independent-of-pdp.md)

### Context Token Integrity
The property that lets a component **receiving** a Context Token detect that it was modified
after issuance or fabricated by something other than the Context service, and refuse it if that
cannot be established. Required at every consuming point — the PDP, all five enforcement points,
and the Data-Access Boundary. **It is a detection property, not unforgeability**: NOVA selects no
mechanism, claims no impossibility of forgery, and gains nothing from it against a compromised
Context service, which issues genuine tokens (`T-23a`). `I-87` is `[PHYS]` — a requirement on a
mechanism that does not yet exist.
→ [`../architecture/AUTHENTICATION_MODEL.md`](../architecture/AUTHENTICATION_MODEL.md) §6

### Scope Binding
The association between an execution and the scope its storage access is restricted to,
established by the **Data-Access Boundary** when the access **channel** is established, derived
solely from the Context Token's scope path, and immutable for that execution's lifetime. No
channel is bound to more than one scope (`I-86`). *(Updated 2026-08-13, N-9: "channel" is
deliberately abstract per `R-2`/L-2 — a connection, a session, a signed request context, or any
equivalent. The earlier wording said "connection or session establishment", which implied a
connection-oriented store.)*

### Step-Up
Requiring **fresh** authentication — not merely a valid session — before an action of higher
consequence. Distinct from re-authentication after expiry: step-up is triggered by what is
about to happen, not by elapsed time.

### Credential Broker Protocol
The seven-step sequence by which a tool obtains use of a credential without ever receiving it:
present binding and token, policy check, binding-state check, operation check, inject, discard,
record. → [`../architecture/SECRETS_ARCHITECTURE.md`](../architecture/SECRETS_ARCHITECTURE.md) §3

### Break-Glass
A bounded, human-only, time-boxed, loudly recorded path **confined to restoring NOVA's
control-plane service** when authentication or policy is **unavailable**. It may restore the
ability to authenticate, repair or restart policy infrastructure, recover control-plane services,
and lift an emergency stop.

**It NEVER authorizes client-data access, provides any path to client data, or bypasses the
normal authorization path** — not for data James could authorize, and not for data he could not.
If policy is unavailable, break-glass may restore NOVA's ability to *perform* authorization; it
never replaces it. Protected data remains fail-closed throughout (`I-75`, `B-1`, `B-5`).
*(Corrected 2026-08-13, R-4. The earlier entry said "restore service" without the control-plane
bound, and said break-glass "never grants access James could not otherwise authorize" — which
implied it could grant access he could. Both contradicted `I-75`, which is absolute.)*
→ [ADR 0021](../decisions/0021-revocation-and-break-glass.md)

### Incident
A confirmed or suspected violation of an invariant. Incidents are contained before they are
investigated, always reach James, and are never silently resolved.

---

## Distinctions That Are Frequently Confused

| Do not conflate | With | Because |
| --- | --- | --- |
| Agent | Tool | An agent decides and delegates; a tool executes one operation. |
| Agent | Model | A model is a replaceable provider capability; an agent is a governed role. |
| Permission | Approval | A permission is standing; an approval is per-action and human-granted. |
| Context | Memory | Context is what is relevant now; memory is what is deliberately retained. |
| Environment | Credential | An environment is a technical context; a credential is a secret scoped to one. |
| Workflow | Task | A workflow sequences tasks; a task is a single unit of work. |
| Business | Client | See [`../DOMAIN_MODEL.md`](../DOMAIN_MODEL.md) §1. |
| **Agent** | **Coding agent** | A NOVA agent is inside the trust boundary; a coding agent is an untrusted external system. |
| **Identity** | **Role** | An identity is who; a role is a bundle of permissions it may hold. |
| **Authentication** | **Authorization** | Proving who you are, versus deciding what you may do. |
| **Context** | **Context Token** | Context is the concept; the token is the enforceable object carrying it. |
| **Context Token** | **Work Order** | A token confers authority inside NOVA; a work order confers none. |
| **Scope** | **Context** | A scope is a fixed node in the tree; a context is one operation's position in it. |
| **Ownership** | **Access** | A resource is owned by a scope; access requires a grant over that scope. |
| **Credential** | **Credential binding** | The secret versus the reference NOVA stores. NOVA holds only the binding. |
| **Provenance** | **Trust** | Where it came from versus how much weight the source earns. |
| **Trust** | **Epistemic status** | A property of the source versus a property of the claim. |
| **Classification** | **Scope** | *What may be done* with an item versus *where* it lives. Both are required. |
| **Grant absent** | **Explicit denial** | Absence is default deny; an explicit denial additionally overrides any grant. |
| **Session identity** | **Execution identity** | Continuity versus the identity authorization evaluates. |
| **PDP** | **Enforcement layer** | The PDP decides *whether*; the enforcement layer makes out-of-scope data *unreachable*. Independent **of the PDP** — not of the Context service, on which both depend (`T-23a`). |
| **Data-Access Boundary** | **Data Access PEP** | The boundary holds the scope *binding*; the PEP asks the PDP for the *decision*, on every access. Neither replaces the other (`I-77`). |
| **Token integrity** | **Unforgeability** | Detecting a modified or fabricated token versus preventing one. NOVA requires the first and claims nothing about the second. |
| **Authentication** | **Step-up** | Proving identity versus proving it *again, freshly*, because of what is about to happen. |
| **Break-glass** | **Authorization bypass** | Break-glass restores **control-plane service**; it never authorizes client-data access at all, and never bypasses the authorization path (`I-75`). |
| **Revocation** | **Reversal** | Revocation stops future use; it does not undo past use. |

---

## Naming Rule

Terms defined here are used verbatim in documentation, code identifiers, and interface
copy. Synonyms invented for variety ("bot", "worker", "assistant", "helper", "skill",
"module") are not canonical NOVA terms and must not be introduced as substitutes without
being defined here first.
