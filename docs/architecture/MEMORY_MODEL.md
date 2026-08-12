# Memory Model

**Status:** Proposed — Section 03, pending James's approval.
**Extends:** [`MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`](./MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md),
which established the six kinds of information, the tiers, and scope partitioning. This
document defines each memory type operationally. **No storage or retrieval technology is
selected** (`D-02`, `D-06`, `D-24a`).

---

## 1. The Governing Constraint

> **Memory must never become a hidden channel around authorization.**

Everything below follows from it. Memory is read through the same enforcement point as any
other resource: a query carries a Context Token, and partitions outside it are **not
queryable** — not filtered afterwards, which would mean the data was retrieved and then
hidden.

---

## 2. Memory Types

| Type | Contains | Owner (scope) | Created by | Crosses scope? | Summarizable? | May drive decisions? |
| --- | --- | --- | --- | --- | --- | --- |
| **Working** | State within one execution | none — execution-local | Execution | ❌ | ❌ | Within the execution |
| **Session** | Continuity across one session | Session, not a scope | Interaction layer | ❌ | ❌ | Yes, non-authoritative |
| **Episodic** | What happened, and when | Scope of the event | Execution records | ❌ | Within scope | Yes |
| **Semantic** | Durable facts about the world | Owning scope | Curation from verified sources | Grant only | Within scope | Yes, if fact-status holds |
| **Procedural** | How to do something | Scope where it applies | James, or reviewed derivation | ✅ if non-identifying | ✅ | Yes |
| **Preferences** | James's standing choices | Root or domain | `james.stated` only | ✅ within LIFE/BUSINESS split | ✅ | Yes |
| **Business knowledge** | Offerings, process, brand | Business | James, curation | ❌ upward | ✅ | Yes |
| **Client knowledge** | Client stack, contacts, history | Client | Work in that client | **❌ never upward** | Within client only | Yes |
| **Project knowledge** | Decisions, conventions, state | Project | Project work | ❌ upward past client | Within client | Yes |
| **Historical records** | Superseded state, corrections | Original scope | Supersession | ❌ | ❌ | **No** — reference only |
| **Derived knowledge** | Summaries, aggregates, conclusions | Strictest source scope | Derivation | **Per [ADR 0010](../decisions/0010-derived-data-inheritance.md)** | Constrained | Yes, labelled as inference |
| **External knowledge** | Fetched from outside | Scope that fetched it | Integration/research | ❌ | With provenance | **Only up to `PREPARE`** |
| **Execution state** | Transient workflow state | Workflow's scope | Workflow engine | ❌ | ❌ | Within workflow |

### The three that carry the most risk

**Derived knowledge** is the leak vector. A summary is a copy: it inherits the strictest
scope and classification of its sources, and cannot be written anywhere its sources could
not be written.

**Procedural memory** is the one type that legitimately generalizes across clients — "how we
deploy a static site" is genuinely reusable. It may cross scope **only when stripped of
identifying content**, and that stripping is a reviewed transformation, never an automatic
one.

**External knowledge** is readable but low-trust. It may inform planning and may never
escalate it.

---

## 3. Lifecycle Per Type

| Operation | Rule |
| --- | --- |
| **Create** | Written into the scope of the creating context, classified at creation, provenance recorded |
| **Update** | Never in place for anything historical — supersession, not overwrite (§4 of [`DATA_LIFECYCLE.md`](./DATA_LIFECYCLE.md)) |
| **Correct** | Correction supersedes; the prior version is retained as historical record |
| **Delete** | Real deletion of the item plus invalidation of derived items ([ADR 0013](../decisions/0013-deletion-and-forgetting.md)) |
| **Expire** | Working and session memory expire automatically; scope memory decays by policy, never silently for `james.stated` items |
| **Elevate** | Moving memory to a parent scope is an explicit, permissioned, audited operation — never a side effect of summarization |

**`james.stated` memory never decays automatically.** Ageing out something James explicitly
said would make NOVA quietly forget instructions it was given.

---

## 4. Retrieval

Every retrieval:

1. carries a Context Token; partitions outside it are not queryable,
2. labels each item with type, provenance, trust, epistemic status, and age,
3. prefers live data over memory for anything volatile,
4. never merges kinds into undifferentiated "context",
5. records what was retrieved, so audit can reconstruct what NOVA believed.

**Retrieval is an authorization event, not a lookup.** Treating it otherwise is precisely
how memory becomes the hidden channel this model exists to prevent.

---

## 5. Memory Is Not Context, Not Authorization

| | Is | Is not |
| --- | --- | --- |
| **Memory** | What NOVA retained | Permission to use it |
| **Context** | Where an operation applies | Authority to act there |
| **Authorization** | Whether an action is allowed | Derived from either of the above |

Remembering a client's API endpoint does not authorize calling it. Remembering that James
approved something last week does not approve it now.
