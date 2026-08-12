# NOVA Architecture

**Status:** Proposed — Section 02, pending James's approval.

This directory is NOVA's architectural blueprint: what every major system is, how they
interact, where the boundaries are, and how information and authority flow.

**Start with [`MASTER_ARCHITECTURE.md`](./MASTER_ARCHITECTURE.md).** It is the canonical
document; everything else elaborates one part of it.

---

## Reading Order

**To understand the shape of NOVA** (start here, in order):

| # | Document | Answers |
| --- | --- | --- |
| 1 | [`MASTER_ARCHITECTURE.md`](./MASTER_ARCHITECTURE.md) | The whole system in one document |
| 2 | [`SYSTEM_LAYERS.md`](./SYSTEM_LAYERS.md) | What each layer owns and may call |
| 3 | [`DOMAIN_ARCHITECTURE.md`](./DOMAIN_ARCHITECTURE.md) | LIFE, BUSINESS, WEALTH; the scope tree |
| 4 | [`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md) | Who acts, and who decides what changes |

**To work on a specific system:**

| Document | Answers |
| --- | --- |
| [`CONTEXT_ARCHITECTURE.md`](./CONTEXT_ARCHITECTURE.md) | How NOVA knows *where* it is working |
| [`MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`](./MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md) | Memory, knowledge, documents, live data |
| [`AGENT_ARCHITECTURE.md`](./AGENT_ARCHITECTURE.md) | Internal agents; vs. external coding agents |
| [`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) | The orchestrator; workflows |
| [`EXECUTION_ARCHITECTURE.md`](./EXECUTION_ARCHITECTURE.md) | Coding agents; the KAIRO client model |
| [`DATA_ARCHITECTURE.md`](./DATA_ARCHITECTURE.md) | Entities, relationships, invariants |
| [`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) | Tools, integrations, credentials |
| [`MODEL_ARCHITECTURE.md`](./MODEL_ARCHITECTURE.md) | Provider-neutral model access |
| [`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](./EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) | Events, traces, audit |
| [`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md) | Failure, retry, partial completion |
| [`USER_INTERFACE_ARCHITECTURE.md`](./USER_INTERFACE_ARCHITECTURE.md) | Information architecture; devices |
| [`SCALE_AND_COST_ARCHITECTURE.md`](./SCALE_AND_COST_ARCHITECTURE.md) | Growth and cost awareness |
| [`TESTING_ARCHITECTURE.md`](./TESTING_ARCHITECTURE.md) | How any of this is verified |

**Security-critical, read before touching anything that crosses a boundary:**

| Document | Answers |
| --- | --- |
| [`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) | Every boundary and what may cross it |
| [`KNOWN_RISKS.md`](./KNOWN_RISKS.md) | Where this architecture is weakest, and what to watch |
| [`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) | Permissions, risk classes, approvals |

---

## The Two Ideas That Explain Most of It

**The scope tree.** Everything NOVA knows and does hangs off one tree of scopes. A scope is
at once a context anchor, a permission boundary, a memory partition, and a credential
partition. Access flows downward only, by explicit grant. Siblings — Client A and Client B,
LIFE and BUSINESS — have no path between them.

**The context token.** Every operation carries a scoped, expiring token naming what it may
touch. Tools, memory, credentials, and integrations refuse anything the token does not
cover. Isolation is enforced where access happens, not where intent is formed.

Understand those two and the rest follows.

---

## Why Decisions Were Made

Reasoning, alternatives, and tradeoffs live in [`../decisions/`](../decisions/README.md) as
ADRs `0001`–`0008`. Read those before proposing a change to anything they cover — they exist
so settled questions are not silently re-litigated.

---

## Status and Authority

Section 1 established that James approves architectural decisions and an AI agent may only
propose them. These documents are therefore **Proposed**. The ADRs carry status `Proposed`;
once James accepts them, this directory becomes Active.

Nothing here selects a database, cloud, framework, language, or model provider. Section 2
defines *what must exist and how the parts relate*. Sections 03 onward choose *what to build
it with* — see [`../decisions/DEFERRED_DECISIONS.md`](../decisions/DEFERRED_DECISIONS.md).
