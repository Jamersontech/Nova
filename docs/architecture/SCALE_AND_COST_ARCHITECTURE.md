# Scale and Cost Architecture

**Status:** Proposed — Section 02.
**Covers:** how NOVA grows without a rewrite, and how it stays cost-aware.
**Defers:** billing, budgets, and infrastructure sizing (`D-28`, Section 34).

---

## 1. The Growth Path

```text
James → a few businesses → many businesses → many clients
     → many projects → many agents → many workflows
```

**What must not happen:** growth requiring new services per business, schema changes per
client, or a re-architecture at any step.

**Why the scope tree handles this.** Every growth dimension is *adding nodes to a tree
under existing rules*, not adding structure. A hundredth client is the same operation as
the second: create a scope node, attach credentials, grant agents. No new code, no new
service, no migration.

| Growth | Adds | Does not add |
| --- | --- | --- |
| A business | Scope node, config, credentials | Services, schemas, deployments |
| A client | Scope node, credentials | Anything structural |
| A project | Scope node | Anything structural |
| An agent | A definition | Runtime changes |
| A tool | A definition and bindings | Per-client duplicates |
| An integration | Config and a credential, per scope | New connector code, if the provider is known |
| A surface | A client of existing services | Logic |

---

## 2. What Genuinely Scales Poorly

Honest identification of the pressure points, so they are watched rather than discovered:

| Pressure point | Symptom | Mitigation direction (deferred) |
| --- | --- | --- |
| **Cross-scope aggregation** | Queries spanning many clients grow linearly | Pre-aggregate at parent scopes; cache with provenance |
| **Memory retrieval** | Retrieval quality degrades as memory grows | Curation and decay from the start, not retrofitted |
| **Concurrent sandboxes** | Coding agents are resource-heavy | Queue and cap concurrency; cost ceilings |
| **Event volume** | Integrations produce continuous events | Filter at source; aggregate telemetry early |
| **Model cost** | Grows with agents × steps × context | §4 below |
| **Audit volume** | Append-only records only grow | Tiered retention; never delete audit, archive it |

**Memory is the one to watch earliest.** Curation and decay are far cheaper to design in
now than to retrofit onto a large corpus of undifferentiated memory.

---

## 3. Deliberate Non-Scaling

NOVA is a **private, single-user system** (`Q-04` open). It is not designed for many
concurrent human users, multi-region availability, or high-throughput public traffic.
Building for that scale would add complexity with no beneficiary — a direct violation of
Constitution §9.

What *is* required is that these could be added later without a rewrite. The identity model
already names an external-user class as unimplemented
([`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md) §2) precisely so that if
multi-user arrives, it arrives as a defined class rather than as a widening of James's
identity.

---

## 4. Cost Awareness

Cost is a first-class input to orchestration, not an after-the-fact report.

**What must be attributable:** every model call, tool call, sandbox session, and external
API call — to an execution, a workflow, and a scope. This yields cost per client, per
project, and per workflow, which for KAIRO is directly business-relevant: the cost of
serving a client is knowable.

**Cost-aware orchestration:**

- The **cheapest adequate** model, not the most capable (Constitution §15).
- Escalate deliberately — on verification failure or declared difficulty — not habitually.
- Prefer cached knowledge and memory over re-retrieval and re-reasoning.
- Cap runaway work: sandboxes, agent loops, and workflows carry cost ceilings that
  terminate and escalate rather than continue.
- Estimate before expensive work and include the estimate in approval requests.

**The tradeoff, stated plainly.** Cost-aware routing sometimes produces a worse first
answer than always using the strongest model. This is accepted for low-risk work and
**not** accepted for high-risk work, where the risk class overrides the cost preference —
a cheap wrong deployment costs more than an expensive right one.

---

## 5. Not Decided Here

Billing, budgets and alerts, infrastructure sizing, caching strategy, and concrete
performance targets. Sections 33 and 34 own them.
