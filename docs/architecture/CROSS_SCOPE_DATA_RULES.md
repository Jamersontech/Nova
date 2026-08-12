# Cross-Scope and Cross-Domain Data Rules

**Status:** Proposed — Section 03, pending James's approval.
**Purpose:** The highest-risk area in the model. Every mechanism here is examined with one
question: **could this become a side channel from one scope into another?**

---

## 1. The Governing Rule

> **Derived information obeys the same or stricter isolation rules as its source material.**
> A summary can leak as effectively as raw data ([ADR 0010](../decisions/0010-derived-data-inheritance.md)).

Reading is the obvious channel and is well defended. **Writing is where isolation actually
fails** — through summaries, aggregates, indexes, caches, and logs that carry content
outward while appearing to be new objects.

---

## 2. Mechanism-by-Mechanism Analysis

| Mechanism | Side channel? | Boundary |
| --- | --- | --- |
| **Aggregation** | **Yes** | Decompose per scope; aggregate above; result is ephemeral and never written to memory ([`CONTEXT_ARCHITECTURE.md`](./CONTEXT_ARCHITECTURE.md) §6) |
| **Analytics / reporting** | **Yes** | Same as aggregation. Reports are derived items inheriting the strictest source classification |
| **Dashboards** | **Yes** | Render per-scope data per scope; cross-scope views are aggregates and follow the aggregation rule |
| **Summaries** | **Yes — highest risk** | Inherit strictest source scope; a client summary cannot be written above the client scope |
| **Benchmarking** | **Yes** | Comparing clients is cross-scope aggregation: ephemeral, approval-gated above `ANALYZE`, never persisted with identifying detail |
| **Model training / fine-tuning** | **Yes — prohibited** | **Client data is never used to train or fine-tune any model.** Not opt-in, not anonymized — prohibited |
| **Embeddings** | **Yes** | An embedding is a derived copy. It inherits scope and classification; indexes are partitioned by scope |
| **Search indexes** | **Yes** | Queries are scope-filtered *before* execution, never after. A cross-scope index is prohibited |
| **Logs** | **Yes** | References and identifiers only for CLIENT-CONFIDENTIAL and above; never content |
| **Caches** | **Yes** | Keyed by scope **and** token; never shared across scopes; invalidated on revocation and deletion |
| **Backups** | **Yes** | Preserve scope partitioning; restoring one scope must not restore another's data |
| **Derived data generally** | **Yes** | Strictest-source inheritance, lineage recorded, deletion cascades |

**Model training is the one flat prohibition.** Everything else has a governed path.

---

## 3. The KAIRO Aggregate Case

```text
Client A  +  Client B  →  KAIRO aggregate
```

**Permitted:**

- Counts, totals, and distributions where no client is identifiable *and* the aggregate
  cannot be reversed to identify one.
- Ephemeral answers to James's questions ("what did hosting cost across clients?"), returned
  and discarded.
- Procedural knowledge stripped of identifying content, via reviewed transformation.

**Prohibited:**

- Writing any client-identifying content to the KAIRO scope.
- Persisting an aggregate that permits re-identification.
- Any agent holding a token spanning both clients.
- Aggregates over small populations where the aggregate *is* the client's data.

**The small-N problem, stated honestly.** With three clients, "average client revenue" plus
two known values reveals the third. Aggregation over a small set is not anonymous. NOVA must
therefore treat small-N aggregates as CLIENT-CONFIDENTIAL rather than as safe derived data —
and **anonymization is never assumed to make something safe**. Removing names does not
remove identifiability.

---

## 4. Cross-Domain Rules

| Direction | Default | Permitted with | Never |
| --- | --- | --- | --- |
| **LIFE → BUSINESS** | Prohibited | Explicit per-item grant, audited | Sensitive-personal content, in any form |
| **BUSINESS → LIFE** | Prohibited | Explicit per-item grant | Client-confidential content |
| **LIFE → WEALTH** | Prohibited | Read grant for financial analysis | Sensitive-personal content |
| **WEALTH → LIFE** | Prohibited | Explicit grant | — |
| **BUSINESS → WEALTH** | Prohibited | Read grant for financial analysis (revenue, costs) | Client-identifying detail |
| **WEALTH → BUSINESS** | **Prohibited** | — | **Wealth data never enters business or client work** |

**WEALTH's asymmetry, bounded.** WEALTH may read financial facts from LIFE and BUSINESS
because wealth analysis genuinely needs them. Nothing reads WEALTH. Three constraints keep
this from becoming a general-purpose hole:

1. **Read-only**, never write.
2. **Financial facts only** — amounts, dates, categories. Not client identities, not
   communications, not sensitive-personal content.
3. **Per-access audited**, and the grant is revocable.

A compromised WEALTH agent still sees more than any other agent. That residual risk is
recorded in [`KNOWN_RISKS.md`](./KNOWN_RISKS.md) and [`THREAT_MODEL.md`](./THREAT_MODEL.md).

---

## 5. Shared Resources

Per [ADR 0002](../decisions/0002-unified-scope-tree.md), as clarified:

- Placement at an ancestor is a **modelling rule, not an access grant**.
- Each consuming descendant is authorized explicitly, or by an explicitly defined policy.
- **Reference, never copy.**
- A shared resource contains **no client-identifying data** — enforced by classification:
  CLIENT-CONFIDENTIAL cannot be promoted upward.
- Shared resources are versioned, owned by their scope, classified, and carry provenance.
- Grants are per-descendant, auditable, and individually revocable.

**Never solve sharing by copying client-specific information into a shared location.** If
two clients need the same thing, the shared object is the *generic* thing, and each client's
specifics stay in their own scope.

### 5.1 Sharing across businesses

*Added during Section 03 self-critique: the rule above addressed sharing between clients of
one business, but not between businesses.*

The same mechanism extends upward without a new rule. The nearest common ancestor of two
businesses is the **BUSINESS domain scope**; of a business and a life area, the **root**.

```text
BUSINESS  (domain scope)         ← a resource both businesses use lives here
├── KAIRO      → granted explicitly    ✅
└── Business B → granted explicitly    ✅
```

The same four constraints apply, and one is sharper at this height:

- Placement at BUSINESS grants **nothing** to KAIRO or Business B — each is granted
  individually (`I-05`).
- **Nothing CLIENT-CONFIDENTIAL can reach a domain scope** (`I-29`), so cross-business
  sharing is structurally limited to generic material: procedures, preferences, templates.
- Root-level sharing is rarer still and should be reserved for genuinely global items —
  James's standing preferences, tool definitions.

**The higher the placement, the wider the blast radius** (T-11). A poisoned resource at
BUSINESS reaches every business. Placement should be at the *lowest* common ancestor that
satisfies the need, never the most convenient one.

---

## 6. When Cross-Scope Is Requested

```text
Request spanning N scopes
  → N sub-contexts, one per scope, independently authorized
  → N isolated executions, no token spans siblings
  → aggregation above the executions
  → result ephemeral; persisting requires explicit elevation
  → cross-scope access recorded per scope touched
```

If any sub-request is denied, **the aggregate is incomplete and says so** — it never
silently returns partial results as though complete.
