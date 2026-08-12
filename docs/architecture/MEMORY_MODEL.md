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

## 4.1 Low-Trust Memory: Quarantine and Revalidation

*Added 2026-08-12 following adversarial review, which found that injected content is
*contained* by the `PREPARE` ceiling but never *removed* — it persists and keeps influencing
every future retrieval.*

**Quarantine.** Memory formed from `external.web`, `client.supplied`, or
`integration.supplied` provenance at low trust is held in a quarantined state:

- retrievable and clearly labelled, never silently merged into general context,
- unable to raise a plan above `PREPARE` without approval naming the source (`I-40`),
- excluded from derivation into higher-trust items until revalidated,
- excluded from procedural generalization across scopes.

**Revalidation.** Quarantined memory is re-evaluated when its source is re-fetched, when its
trust changes, or on an age horizon. Revalidation either promotes it (a verified source now
supports it), leaves it quarantined, or marks it disputed. **Revalidation never deletes it** —
provenance is immutable (`I-38`), and a false claim that was believed is itself a fact worth
retaining.

**Contradiction.** When quarantined memory conflicts with higher-trust memory, the higher
trust stands and the conflict is recorded; it is never silently discarded
([`DATA_LIFECYCLE.md`](./DATA_LIFECYCLE.md) §4). Repeated contradiction from one source is a
signal to lower that source's trust.

**Residual risk, stated plainly:** quarantine contains injection persistence; it does not end
it. A patient attacker supplying consistently plausible content that nothing contradicts is
not detected by this mechanism (`T-10`).

---

## 4.2 Stale Instructions — Resolving the `I-36` Tension

*Added 2026-08-12 following adversarial review.*

`I-36` states that `james.stated` memory never expires automatically and is never
auto-superseded. That is correct and must not change — **NOVA must not quietly forget what
James told it.** But taken alone it produces the opposite hazard: an instruction given a year
ago remains `current` and authoritative forever, and NOVA may act on it as though it were
said today.

**Both properties are required.** The resolution is neither expiry nor deletion:

| Mechanism | Behaviour |
| --- | --- |
| **Never delete** | `james.stated` items are retained indefinitely. History is not erased because it aged (`I-36`, `I-38`) |
| **Never auto-supersede** | No agent, model, or policy may override what James said |
| **Confidence horizon** | Each `james.stated` item carries an age beyond which it is no longer treated as *currently confirmed* |
| **Revalidation, not expiry** | Past its horizon, the item remains `current` and readable, but its **epistemic status degrades from fact to assumption** ([`PROVENANCE_AND_TRUST.md`](./PROVENANCE_AND_TRUST.md) §4) |
| **Re-confirmation** | Before an aged instruction drives an action above `PREPARE`, NOVA asks James to confirm it still holds — surfacing when it was said |
| **Confirmation supersedes** | A confirmation creates a new version with a fresh horizon; the original remains as history (`I-43`) |

**The distinction that matters:** the instruction is not forgotten, not weakened, and not
deleted — it is **re-confirmed before it is acted on**. Historical truth is preserved;
stale authority is not assumed. `I-59`.

Horizons are per-item-class and are not set here; the mechanism is fixed, the durations are
Section 07's.

---

## 5. Memory Is Not Context, Not Authorization

| | Is | Is not |
| --- | --- | --- |
| **Memory** | What NOVA retained | Permission to use it |
| **Context** | Where an operation applies | Authority to act there |
| **Authorization** | Whether an action is allowed | Derived from either of the above |

Remembering a client's API endpoint does not authorize calling it. Remembering that James
approved something last week does not approve it now.
