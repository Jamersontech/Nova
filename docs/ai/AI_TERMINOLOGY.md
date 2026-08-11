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

---

## Naming Rule

Terms defined here are used verbatim in documentation, code identifiers, and interface
copy. Synonyms invented for variety ("bot", "worker", "assistant", "helper", "skill",
"module") are not canonical NOVA terms and must not be introduced as substitutes without
being defined here first.
