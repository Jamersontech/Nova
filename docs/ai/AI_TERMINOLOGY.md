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

---

## Naming Rule

Terms defined here are used verbatim in documentation, code identifiers, and interface
copy. Synonyms invented for variety ("bot", "worker", "assistant", "helper", "skill",
"module") are not canonical NOVA terms and must not be introduced as substitutes without
being defined here first.
