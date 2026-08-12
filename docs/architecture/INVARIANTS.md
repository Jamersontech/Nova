# Architectural Invariants

**Status:** **Active** — Section 03, approved by James 2026-08-12 (as amended, commit 0917de5).
**Purpose:** The complete set of properties every implementation section must satisfy.
**Each is written to be testable.** An invariant that cannot be tested is a wish.

These supersede nothing; they consolidate and extend the eight structural invariants in
[`DATA_ARCHITECTURE.md`](./DATA_ARCHITECTURE.md) §3, which remain in force as `I-S1`–`I-S8`.

**Any change to this file is a C3 architectural change** requiring an ADR.

---

## Status of Every Invariant on This Page

*Added 2026-08-12 following adversarial review.*

> **Every invariant here is an architectural REQUIREMENT.**
> **None is a VERIFIED IMPLEMENTATION PROPERTY.**

| Term | Meaning |
| --- | --- |
| **REQUIREMENT** | A property the architecture demands. Stated normatively; binding on every implementation section |
| **VERIFIED IMPLEMENTATION PROPERTY** | A property demonstrated to hold in a built system by adversarial test |

NOVA currently has **no code and no tests**. Every invariant below is therefore a
requirement, and remains unverified until the relevant implementation section builds it and
Section 31 tests it. Documents elsewhere that describe an invariant as *achieved* are
overstating it; this page is the authority on verification status.

**The requirements are not weakened by this.** They are as binding as before — what is
recorded honestly is that binding a requirement is not the same as meeting it.

### Invariants dependent on future physical implementation

Some invariants cannot be satisfied by the conceptual model alone: they are true only if the
storage and platform choices support them. These are marked **[PHYS]** below.

| # | Physical dependency | Blocked on |
| --- | --- | --- |
| **I-03** | Cross-scope unreachability must be enforced **below the query layer**. If enforcement is application-side only, `I-03` depends on query correctness rather than construction | `D-33`, `D-02` |
| **I-21** | Requires secrets storage genuinely separate from the data store | `D-10` |
| **I-33** | "Not queryable" is a storage-engine property. Retrieve-then-filter satisfies the words and defeats the intent | `D-33`, `D-02`, `D-06` |
| **I-45** | Requires a queryable lineage graph and a delete-by-lineage contract in **every** store, including indexes, caches, and backups | `D-02`, `D-06`, `D-15` |
| **I-47** | Append-only requires immutable storage or an equivalent enforced guarantee | `D-02`, `D-11` |

**Consequence for Section 04:** the isolation *requirement* can be specified without naming a
product — "enforcement must occur below the query layer such that out-of-scope partitions are
unreachable, not merely unreturned" — but `I-03` and `I-33` are not satisfied until `D-33` is
decided and implemented.

---

## Scope and Structure

| # | Invariant |
| --- | --- |
| **I-01** | Every scope except root has exactly one parent. The tree is never a graph. |
| **I-02** | Every resource is owned by exactly one scope. |
| **I-03** **[PHYS]** | An execution operating in Client A's scope cannot read, write, or enumerate Client B's resources — by any path, including error messages and timing. |
| **I-04** | No token grants rights over a sibling scope or an ancestor. |
| **I-05** | Placing a resource at a common ancestor grants no access to any descendant. Access requires an explicit grant or an explicitly defined policy naming the descendants. |
| **I-06** | A new scope kind may exist only if it satisfies the scope contract ([`SCOPE_AND_IDENTITY_MODEL.md`](./SCOPE_AND_IDENTITY_MODEL.md) §1.1). |

## Identity and Authority

| # | Invariant |
| --- | --- |
| **I-07** | An execution's rights are the *intersection* of agent definition, granting identity, token, and risk ceiling. No mechanism produces a union. |
| **I-08** | No component can widen its own authority or another's. |
| **I-09** | Only James approves. No system, agent, or automation may record an approval. |
| **I-10** | Only James grants access. |
| **I-11** | A client identity holds no permission and performs no action. |
| **I-12** | Every delegation narrows and carries an expiry. A delegation without expiry is rejected at creation. |
| **I-13** | Identity does not imply permission; context does not imply authorization; credential possession does not imply authority; approval does not imply standing permission. |

## Authorization

| # | Invariant |
| --- | --- |
| **I-14** | Default deny. Absence of a grant is a denial. |
| **I-15** | An explicit denial overrides any grant. |
| **I-16** | Scope containment is checked before permissions are evaluated. |
| **I-17** | If the PDP is unavailable, the answer is deny. There is no allow-path that bypasses it. |
| **I-18** | Every decision — allow, deny, approval-required — produces an audit record. |
| **I-19** | Emergency stop is enforced at enforcement points, not requested of the components being stopped. |
| **I-20** | A model's ability to perform an action is never authorization to perform it. |

## Credentials

| # | Invariant |
| --- | --- |
| **I-21** **[PHYS]** | No credential material is stored in memory, knowledge, documents, events, audit records, model prompts, logs, exports, or backups. |
| **I-22** | NOVA issues no credential material to an agent, orchestrator, or model; secrets are injected at the outbound boundary only. Credential material arriving by other routes — integration responses, error payloads, sandbox environments, files, screenshots, user-supplied text — is an **incident to detect and contain** (`I-51`), not an event this invariant prevents. External coding agents hold narrow, expiring secrets by design ([ADR 0005](../decisions/0005-external-coding-agent-isolation.md)). |
| **I-23** | Every credential binding belongs to exactly one scope. There are no global credentials. |
| **I-24** | A credential is usable only from a context whose scope covers its binding. |
| **I-25** | Revoking a credential affects no other scope. |

## Data, Derivation, and Classification

| # | Invariant |
| --- | --- |
| **I-26** | Every stored item carries a classification. Unclassified is not a state. |
| **I-27** | A derived item inherits the strictest classification and narrowest scope among its sources. |
| **I-28** | Derived data cannot have weaker scope restrictions than its sources unless an explicit, reviewed transformation permits it. |
| **I-29** | CLIENT-CONFIDENTIAL and SENSITIVE-PERSONAL items are never promoted to a parent scope. |
| **I-30** | Downward reclassification is never automatic and never performed by an agent. |
| **I-31** | Every derived item records complete lineage. Unknown lineage is treated as the strictest classification present. |
| **I-32** | Client data is never used to train or fine-tune any model. |

## Memory

| # | Invariant |
| --- | --- |
| **I-33** **[PHYS]** | Memory outside a token's partitions is not queryable — not retrieved-then-filtered. |
| **I-34** | Memory retrieval is an authorization event and is recorded for CLIENT-CONFIDENTIAL and above. |
| **I-35** | Elevating memory to a parent scope is explicit, permissioned, and audited — never a side effect of summarization. |
| **I-36** | `james.stated` memory never expires automatically and is never auto-superseded. Aged items are re-confirmed rather than expired — see `I-59`. |

## Provenance and Truth

| # | Invariant |
| --- | --- |
| **I-37** | Provenance, trust, and epistemic status are recorded separately and never collapsed. |
| **I-38** | Provenance is immutable. |
| **I-39** | An item may be treated as fact only if its provenance and trust support it. Model confidence never promotes epistemic status. |
| **I-40** | External content may inform a plan but never escalate one; a plan influenced by untrusted content cannot exceed `PREPARE` without approval naming the source. |
| **I-41** | Contradictions are surfaced, never silently resolved. |

## Temporal and Lifecycle

| # | Invariant |
| --- | --- |
| **I-42** | Only `current` items drive decisions. Superseded items are history. |
| **I-43** | Meaningful changes supersede rather than overwrite; historical records are not rewritten because current truth changed. |
| **I-44** | Effective time and record time are stored separately. |
| **I-45** **[PHYS]** | Deleting an item invalidates every item derived from it, discoverable via lineage. |
| **I-46** | Deletion leaves a tombstone recording that deletion occurred, never the deleted content. |

## Audit

| # | Invariant |
| --- | --- |
| **I-47** **[PHYS]** | Audit records are append-only and are never deleted or edited, including by James. |
| **I-48** | Audit records contain references and identifiers, never client content or secrets. |
| **I-49** | Every cross-scope and cross-domain access is recorded per scope touched. |
| **I-50** | The audit trail can reconstruct what NOVA believed at the time of any decision. |

## Added by the Section 03 Review Amendments

*Added 2026-08-12. Same status as every invariant above: REQUIREMENT, unverified.*

| # | Invariant |
| --- | --- |
| **I-51** | Tool response schemas declare credential-shaped fields, and those fields are stripped at the capability boundary before a response reaches agent context. Responses are additionally scanned for undeclared credential-shaped material. |
| **I-52** | If classification is unavailable, the strictest applicable classification for the creating scope applies, and any action that level forbids is denied. Unclassified is never stored. |
| **I-53** | If lineage cannot be recorded, the derivation fails. No derived item is created without lineage. |
| **I-54** | If audit is unavailable, actions classified above `PREPARE` are denied. `READ`–`PREPARE` may proceed with records durably queued; a queue that cannot accept a record is itself an audit failure. |
| **I-55** **[PHYS]** | Restoration from backup consults tombstones and re-applies deletion before restored data becomes available. |
| **I-56** | A new scope kind is validated executably against the scope contract at registration and rejected on failure. Human C3 review is additional, never the sole enforcement. |
| **I-57** | Maximum, minimum, and ranking derived from other clients never appear in client-visible output where they can reveal an individual client's information. Any cross-client aggregate in client-facing output requires explicit review that accounts for cumulative disclosure across prior releases. |
| **I-58** | A Work Order materially influenced by untrusted external content preserves that provenance, carries the approval requirement the influenced plan would have carried, and surfaces the influence in the approval request. |
| **I-59** | `james.stated` items are never deleted or auto-superseded. Past a confidence horizon their epistemic status degrades to assumption and they require re-confirmation before driving an action above `PREPARE`. Confirmation creates a new version; the original is retained. |

---

## Testing These

[`TESTING_ARCHITECTURE.md`](./TESTING_ARCHITECTURE.md) §3 requires isolation, permission,
credential, context, boundary, escalation, sandbox, and injection tests. **This file is the
specification those tests implement.** Each invariant should map to at least one adversarial
test written from the position of "how would I violate this?" — not "does the happy path
work?"

`I-03` deserves particular attention: it includes error messages and timing, because a
denial that reveals *whether a resource exists* is itself a cross-client disclosure.
