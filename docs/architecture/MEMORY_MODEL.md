# Memory Model

**Status:** **Active** — Section 03, approved by James 2026-08-12 (as amended, commit 0917de5).
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

**Three further requirements on every retrieval.** ***PROPOSED — added by Section 07, not yet
accepted*** *(2026-08-14; authority
[ADR 0033](../decisions/0033-section-07-amendments-to-accepted-architecture.md), Proposed; removed
if rejected).*

6. **The union provenance and lowest trust are restored, not just a single provenance value**
   (`I-111`). Rule 2 above labels items with *"provenance, trust, epistemic status, and age"* —
   singular fields. `I-99` requires the **union** of every contributing source and the **lowest**
   trust among them, and `I-100`'s untrusted-derived tool-argument ceiling is evaluated against it.
   A retrieval that returns a collapsed provenance satisfies rule 2 and defeats `I-100`.
7. **Delegation ancestry is restored with the item** (`I-111`). Memory written by a delegated child
   is **scope-owned and survives the child correctly** — but **survival is not authority.** A
   broader ancestor retrieving it must not treat it as more authoritative than the authority and
   trust state under which it was created (`I-107` ancestry, `I-27` strictest-source). The memory is
   **not invalid**, and no separate authority hierarchy for memory is created.
8. **A revoked creating authority is surfaced.** An item created under an authority later revoked is
   **retained** under the lifecycle rules above and its revocation state is **exposed at
   retrieval**. Nothing is automatically deleted, downgraded, invalidated, promoted, or
   reclassified — `DATA_LIFECYCLE.md` §4's rule against silent resolution applies: revocation
   happens for many reasons and only some impeach what was learned. The **consuming authority**
   decides, and where fresh authorization is required the existing rules control.

---

## 4.1 Low-Trust Memory: Quarantine and Revalidation

*Added 2026-08-12 following adversarial review, which found that injected content is
*contained* by the `PREPARE` ceiling but never *removed* — it persists and keeps influencing
every future retrieval.*

**Quarantine.** Memory formed from `external.web`, `client.supplied`, `integration.supplied`, or
**`model.generated`** ¹ provenance at low trust is held in a quarantined state:

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

> ¹ ***PROPOSED — added by Section 07, not yet accepted*** *(2026-08-14; authority
> [ADR 0033](../decisions/0033-section-07-amendments-to-accepted-architecture.md), Proposed;
> removed if rejected).* **`model.generated` was absent from this set.** `I-99` covered it
> partially — model output inherits its inputs' provenance, so output derived from web or client
> content was already quarantined — but output derived from **purely internal** inputs was Low-trust
> and **unquarantined**: silently mergeable into general context and eligible for derivation into
> higher-trust items, both of which quarantine exists to prevent. **Trust alone does not do
> quarantine's work.**
>
> **Model-generated memory is not safe because its inputs were internal, because it carries no
> external provenance, because a trusted model produced it, or because it was generated inside
> NOVA.** No new quarantine concept is created; the existing rules apply unchanged.
>
> **This makes §2's Semantic-memory rule enforceable rather than aspirational.** §2 already says
> semantic memory is *"created by curation from verified sources"*; with this, model output cannot
> become durable higher-trust knowledge except through §4.3's promotion. **The operational cost is
> real and is accepted:** durable knowledge now arrives predominantly through curation, and the
> convenient path — an agent's good summary quietly becoming knowledge — is closed.

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

## 4.3 Trust Promotion

***PROPOSED — added by Section 07, not yet accepted*** *(2026-08-14; authority
[ADR 0032](../decisions/0032-trust-promotion-authority.md) and
[ADR 0033](../decisions/0033-section-07-amendments-to-accepted-architecture.md), both Proposed;
removed if either is rejected).*

§4.1 says revalidation *"either **promotes** it… leaves it quarantined, or marks it disputed."*
**Promotion had no owner.** `I-39` gates fact status on *provenance **and** trust*; provenance is
immutable (`I-38`), classification-lowering is owned (`I-30`), approval and grants are James's
(`I-09`, `I-10`), and a model check cannot promote epistemic status (`I-102`) — **trust was the one
axis in that gate with no authority attached.** An unowned promotion converts contained untrusted
content into apparent fact without violating any invariant.

**`I-110` closes it.** Raising trust is an **explicitly authorized operation** — never automatic,
never performed by an agent, never model-mediated, and never inferred from repetition, model
confidence, consensus, internal origin, or the fact that NOVA produced it. It is a **C3** change,
governed exactly as `I-30` governs downward reclassification.

**Every promotion records seven things, or it does not happen:** the item · its immutable
provenance · the evidence relied on · the authoritative source · the resulting trust · the
responsible authority · the trace identity.

**`system.verified` requires an authoritative source, and the term is defined** — external to the
model's own output, identifiable, verification reproducible and auditable, and itself satisfying the
applicable trust and data-policy requirements. **A model saying "I verified this" is never evidence
of verification, and a model-generated summary of an authoritative source is not the authoritative
source.**

**Enforcement:** the memory write / revalidation path, **before** the item becomes eligible for
downstream use. **On uncertainty, missing evidence, an unidentifiable source, or a failed check the
promotion is denied** and the item keeps its existing trust — never retained provisionally, never
pending review.

**Provenance is untouched** (`I-38`): a promotion adds a verification record and a new trust value;
it never rewrites where an item came from. **Lowering trust is deliberately not governed here** —
restriction is not gated like elevation, the same asymmetry `I-93` and ADR 0030 apply.

---

## 5. Memory Is Not Context, Not Authorization

| | Is | Is not |
| --- | --- | --- |
| **Memory** | What NOVA retained | Permission to use it |
| **Context** | Where an operation applies | Authority to act there |
| **Authorization** | Whether an action is allowed | Derived from either of the above |

Remembering a client's API endpoint does not authorize calling it. Remembering that James
approved something last week does not approve it now.
