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
| **I-55** | Requires a backup/restore mechanism that consults tombstones | `D-15` |
| **I-60**–**I-63** | Enforcement below the query layer requires a store that can bind scope to a channel and refuse unconstrained queries. **The mechanism is specified ([ADR 0016](../decisions/0016-isolation-enforced-below-query-layer.md)); no technology is chosen** | `D-02`, `D-33a` |
| **I-66** | Non-presentability of an execution identity depends on how identities are issued and verified at runtime | `D-01`, `D-09` |
| **I-68** | Store separation and backup contents are properties of the chosen stores and backup mechanism | `D-10`, `D-02`, `D-15` |
| **I-69** | Restricting retrieval to one component requires the store to enforce caller identity | `D-10` |
| **I-71** | Per-scope key partitioning must be supported by the key-management mechanism and the store (`C-9`) | `D-35`, `D-02` |
| **I-72** | Separate keying of the secrets store is a property of the chosen stores | `D-10`, `D-35` |
| **I-80** | Provisioning validation and isolation verification can only run once an isolation mechanism exists | `D-33a`, `D-02` |
| **I-86** | Whether a channel can be constrained to exactly one scope, and whether the platform can prevent a component from holding several scope-bound channels at once, are properties of the storage and channel mechanism. Nothing in the conceptual model prevents a multi-scope connection | `D-02`, `D-33a` |
| **I-87** | Token integrity is stated as a required **property**; the mechanism that provides it — and therefore whether detection actually holds — does not yet exist | `D-09`, `D-33` |
| **I-88** | Separating write from read capability over the same audit partition, and confining a write capability to one execution's scope and lifetime, are properties of the key-management and storage mechanism, not of the conceptual model | `D-35`, `D-02` |
| **I-90** | Whether a single audit partition can be served on its own, without a component that spans partitions, is a property of the storage and audit mechanism. **`I-89` is deliberately *not* marked `[PHYS]`** — the prohibition on a universal audit reader is NOVA's own architectural choice (`S4-P2`, Option D) and holds under any mechanism; only its *feasibility* is mechanism-dependent, and that is what this row records | `D-35`, `D-02`, `D-11` |
| **I-96** ¹ | Whether an item's classification can be established at egress time, and whether redaction can be **confirmed applied** rather than merely attempted, are properties of the classification mechanism and of the gateway implementation. Nothing in the conceptual model makes redaction verifiable — which is why `I-96` **denies rather than degrades**: an unverifiable removal must not be assumed successful. **`I-94`, `I-95`, `I-97`, `I-98` and `I-99`–`I-105` are deliberately *not* `[PHYS]`** — each is a rule NOVA decides and holds to under any mechanism, and their *correct implementation* is an ordinary correctness concern, not a physical dependency | `D-08`, `D-33`, `D-02` |

> ¹ ***Added by Section 05 — ACCEPTED by James 2026-08-14*** *(2026-08-14; authority
> [ADR 0024](../decisions/0024-model-gateway-is-an-enforcement-point.md) and
> [ADR 0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md)).*

**`I-70` is deliberately *not* marked `[PHYS]`.** "The broker discards the secret and never
returns it upward" is a property of the broker's own design — a component NOVA specifies and
builds — not of any external technology. Marking it would be marking for consistency rather than
for genuine dependency, which this notation exists to avoid. Its *effectiveness* is bounded by
`I-81` (retry paths), which is **not** `[PHYS]` either, and for the same reason: holding only
pre-injection requests in retry queues, error records, logs, telemetry, snapshots, and caches is a
property of how NOVA designs that path, not of any technology it has yet to choose. *(Corrected
2026-08-12, F-5. The earlier text described `I-81` as "separately marked", which it never was.)*

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

## Added by Section 04 — Security, Identity & Permissions

> **`I-60`–`I-93` were accepted by James on 2026-08-13 with ADRs `0016`–`0023`.**
> *(Marking updated 2026-08-14. The note previously recorded them as PROPOSED pending those ADRs —
> accurate when written on 2026-08-13, and stale from the moment the ADRs were accepted later the
> same day. **Nothing about `I-60`–`I-93` is changed by this correction**; only the status line
> describing them.)* This file is Active Section 03 material and every change to it is C3.
> `I-01`–`I-59` were accepted on 2026-08-12.

*Added 2026-08-12. Same status as every invariant above: REQUIREMENT, unverified.*

### Isolation enforcement

| # | Invariant |
| --- | --- |
| **I-60** **[PHYS]** | Scope restriction is applied beneath query construction. A query lacking a scope constraint returns nothing; it never returns unrestricted data. |
| **I-61** **[PHYS]** | An execution's scope binding is established by the **Data-Access Boundary** within the TRUSTED zone, derived solely from the Context Token's scope path, and is not modifiable by application or agent code for that execution's lifetime. The token whose scope path is used must have passed the integrity check `I-87` requires; a token that fails it establishes no binding. |
| **I-62** **[PHYS]** | The storage enforcement layer does not consult the Policy Decision Point. Cross-client access therefore requires either compromise of **both** the PDP and the scope-binding path, **or** compromise of the Context service / Context Token issuance — which defeats both together, since both derive from the Context Token. **General two-of-two independence is not claimed.** |
| **I-63** **[PHYS]** | Enforcement covers enumeration, counts, and existence checks, on every access path including administrative and analytical, and denies when scope is indeterminate. |

### Authentication and sessions

| # | Invariant |
| --- | --- |
| **I-64** | Any session reaching `EXECUTE` or above satisfies multi-factor authentication with a phishing-resistant primary factor bound to origin or device. |
| **I-65** | Sessions carry absolute expiry, are per-surface, and are individually enumerable and revocable. Activity alone does not extend a session. |
| **I-66** **[PHYS]** | An execution identity is issued by the runtime for one execution and is scoped to that execution. **Required property:** an agent must not be able to present, re-present, refresh, extend, or synthesize an execution identity, and no identity class may authenticate as another. *(Amended 2026-08-12, M-8: stated as a required security property. NOVA specifies no mechanism establishing unforgeability, and none is claimed. Satisfaction depends on how identities are issued and verified at runtime — `D-01`, `D-09`.)* |
| **I-67** | `IRREVERSIBLE` actions and changes to grants, policy, classification, or credentials require fresh authentication, not merely a valid session. **Cross-scope audit review additionally requires step-up** *(added 2026-08-13, `H-1` Option 3)* — reviewing audit across more than one scope aggregates the cross-client audit corpus and is treated like any other cross-scope operation (`I-49`, `I-86`). **Single-scope audit reading by James does not require step-up.** Account recovery is at least as strong as primary authentication. |

### Secrets

| # | Invariant |
| --- | --- |
| **I-68** **[PHYS]** | Secret material resides in a store separate from NOVA's data store, and backups of the data store contain none. |
| **I-69** **[PHYS]** | Only the Credential Broker retrieves secret material. No agent, orchestrator, tool, model path, migration, backup job, or administrative console retrieves it. |
| **I-70** | The broker discards secret material after injection; it is never returned upward to the caller. |

### Encryption

| # | Invariant |
| --- | --- |
| **I-71** **[PHYS]** | Key material is partitioned to follow the scope tree. A key sufficient to read one client's data at rest is not sufficient for a sibling's. |
| **I-72** **[PHYS]** | Key material is never stored in the data model, and the secrets store is keyed separately from the data store. |

### Policy authoring

| # | Invariant |
| --- | --- |
| **I-73** | No agent modifies policy, and no policy grants an agent the ability to modify policy. Policy cannot weaken an invariant; a policy that would permit a cross-client read is invalid at authoring time. |

### Security operations

| # | Invariant |
| --- | --- |
| **I-74** | Revocation takes effect at the next authorization decision. In-flight executions holding a revoked token fail closed at their next enforcement point. |
| **I-75** | Break-glass **never authorizes client-data access and never bypasses the normal authorization path.** It is confined to the control plane — restoring authentication, repairing policy infrastructure, recovering control-plane services, lifting an emergency stop — and is human-only, time-boxed, and loudly recorded. Protected data remains fail-closed while authorization is unavailable; break-glass may restore NOVA's ability to *perform* authorization, never replace it. |
| **I-76** | Every incident is recorded and reaches James. No incident is silently resolved, and containment precedes investigation. |

## Added by the Section 04 Review Amendments

*Added 2026-08-12. Same status as every invariant above: REQUIREMENT, unverified.*

| # | Invariant |
| --- | --- |
| **I-77** | Structural storage isolation is **additional to** the Data Access PEP, never a replacement. Every data access still passes the full ADR 0014 sequence — grants, risk ceiling, classification, conditions. The isolation layer decides nothing about authorization and can only deny reachability. |
| **I-78** | A scope binding is established only by the **Data-Access Boundary** within the TRUSTED zone, derived solely from the Context Token's scope path, and is verified against the presented token at establishment — including the token's integrity property (`I-87`). A mismatch, or a token whose integrity cannot be established, is refused and recorded. |
| **I-79** | If execution scope is missing, ambiguous, invalid, inconsistent with the token, or cannot be established, no scope-bound channel is opened and access is denied. There is no unbound channel and no default scope. |
| **I-80** **[PHYS]** | A client scope becomes operationally active only after provisioning, configuration validation, isolation verification, and the required isolation tests have all passed and been recorded. Existence of a scope record is not activation; any failure or incomplete stage leaves the scope inactive for protected operations. |
| **I-81** | Reliability infrastructure never persists injected credential material. Retry queues, dead-letter queues, request objects, error records, logs, telemetry, snapshots, and caches hold pre-injection requests only; credentials are re-injected by the broker at send time. |
| **I-82** | Holding a Context Token whose scope path includes an ancestor confers no ancestor key material. Decryption of an ancestor-scope shared resource requires an explicit grant over that resource; key access is released per resource, per operation, and is audited. |
| **I-83** | Security audit records are keyed under a hierarchy separate from client-data keys, and that hierarchy is **itself partitioned across the scope tree** — there is no single global audit key, and no audit-key capability spans sibling scopes in either direction, for reading or writing. **Audit-key access inherits nothing from data-key authorization**: being authorized for a scope's data keys confers no audit-key access to that scope or any other, and the ancestor data-key rule (`I-82`) does not govern the audit hierarchy. Destroying a client's data keys does not destroy that client's audit records or tombstones, and `I-47` is unaffected. |
| **I-84** | Generic and unstructured tool responses are not returned raw into agent context by default; they are parsed, filtered, or summarized at the capability boundary, and unstructured responses are treated as potentially credential-bearing. **This is containment, not prevention — credential ingress remains possible.** |
| **I-85** | Audit records of authorization decisions are emitted by the PDP and are therefore **not independent evidence of PDP integrity**. NOVA requires no independent audit path for authorization decisions and designs none; a compromised PDP may emit false or omitted records. |
| **I-86** **[PHYS]** | No access channel is bound to more than one scope, and no component holds simultaneous scope-bound channels in order to join across them at the storage layer. Cross-scope work uses serial single-scope channels, aggregated above the executions. |
| **I-87** **[PHYS]** | A Context Token carries an integrity property that allows a receiving component to **detect** modification after issuance or fabrication by anything other than the Context service. Every component consuming a token performs that check; a token that fails it, or whose integrity cannot be established, is rejected, no binding is established, the access is denied, and the rejection is recorded. **This is a detection property, not a claim of unforgeability, and it does not mitigate compromise of the Context service itself** (`T-23a`). No mechanism is specified ([`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §6). |
| **I-88** **[PHYS]** | Audit write capability is **authorized by construction, scope-bound, and is not read capability.** An execution that has been authorized — and whose scope binding is therefore established (`I-61`, `I-79`, `I-86`) — may write audit records for **that scope only**, for **that execution's lifetime only**. That authorization *is* the capability: there is no separate release decision, no grant class, and no second authorization authority. **No component — including the PDP (`I-85`) and the Observability responsibility — holds blanket cross-scope audit-write capability**, and none may write for a scope it is not executing in. `I-18` is unaffected and not exempted: the execution's own authorization is a decision and produces a record; audit emission is a consequence of it, not a new authorization request. Write confers no read over that partition or any other, and append-only (`I-47`) is unaffected. A component running several concurrent executions holds one execution-bound capability per execution and **must never use them to write across scopes**. This is writer authority **`W-1`** and governs successful execution-scoped events only; attempted/denied events are `I-91` and control-plane events are `I-92` ([ADR 0023](../decisions/0023-audit-record-writer-authority.md)). |
| **I-89** | There is **no centralized audit reader and no component holding universal or cross-scope audit-read capability** — not the Observability responsibility, not a reader service, not an administrative path. James reads audit partitions directly and per scope; cross-scope review is N per-scope reads aggregated above them (`I-86`), recorded per scope touched (`I-49`), and requires step-up (`I-67`). His access is not grant-mediated: `I-09` and `I-10` are unchanged, and `I-82` — a data-key rule — does not apply. **Not `[PHYS]`:** this is an architectural property NOVA decides and holds to (`S4-P2`, Option D), true of any mechanism. Whether the mechanism can *support* it is `I-90`. |
| **I-90** **[PHYS]** | Audit partitions must be **individually readable per scope without an aggregating component** — a scope's audit records can be retrieved on their own, and reconstructing a cross-scope view requires N separate per-scope reads rather than a component that spans partitions. `I-89` is the architectural prohibition; this is the mechanism property that prohibition depends on. If the chosen storage and audit mechanism cannot serve a single partition without a spanning reader, `I-89` cannot be satisfied. |
| **I-91** | **Writer authority `W-2`.** The record of an authorization decision — **allow, deny, or approval-required alike** — is written under the authority of **that decision**, into the partition of the scope the decision concerned. This covers denials, pre-binding refusals (`I-78`, `I-79`), token rejections (`I-87`), and every attempted access that did not become an authorized execution. **`W-2` applies only where the decision concerned a client scope.** A decision taken before any scope exists — authentication and recovery, which precede context resolution ([`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §1) — is a control-plane event under `I-92`, **never forced into a client partition**. **No execution, scope binding, grant class or second authority is required or created**; `I-18` already makes the decision produce a record, and this states that the decision is the authority for the record of itself. A denied cross-scope attempt is recorded in the **actor's** scope; the target's partition receives nothing naming the actor (`E-11`), and the security event is recorded in the control-plane partition (`I-92`). **This authority confers nothing beyond the single record of the single decision** — it is not standing, not transferable, and cannot reach a scope the decision did not concern. |
| **I-92** | **Writer authority `W-3`, and the control-plane audit partition.** Operations that concern no client scope — scope creation, provisioning, validation, verification, activation, rollback, grants, delegations, revocations, emergency stop, break-glass, incidents, policy changes, classification changes, credential lifecycle, session lifecycle **including failed authentication and failed recovery (`A-4`)**, restore/migration verification, approvals, and audit-write failures — are recorded in a **control-plane audit partition that is not a node in the client scope tree**. It is **not a scope kind** and is not governed by the `I-06` scope contract: nothing executes in it, no context resolves to it, no token names it, and it holds no client data. It **must not carry client-scope content, identifiers, or resource references** (`I-48`, `E-11`) and must never become a substitute for reading a client's own partition. Reading it is `I-89`: **James only**. **No component acquires client-scope write capability by writing here**, which is what makes `S4-P1` hold by construction. |
| **I-93** | **Audit-write failure is fail-closed for access, fail-open for restriction.** If a record `I-18` requires cannot be durably written: an authorization decision resolves to **deny**; an execution does **not** start; a control-plane operation does **not** proceed; a scope does **not** activate (`I-80`). **Operations that restrict or remove access proceed** — emergency stop is not withheld because its record failed, since refusing to stop fails *open*; break-glass proceeds only with an out-of-band record, on `B-7`'s reasoning, with the interval to durable recording recorded as exposure. The failure record is itself a control-plane event (`I-92`); **if it too cannot be written, no further attempt is made** — the operation has already failed closed and the condition surfaces as an incident (`I-76`). **No fallback writer, no universal client-scope capability, and no "best effort" reading of `I-18` is permitted.** **Persistence is resolved by identity, not by acknowledgement:** every mandatory audit record carries a **deterministic event identity** derived from the operation it records and its trace id; **physical writes sharing an identity are one logical record**, so an uncertain write is retried and de-duplicated by identity rather than producing a second event. `I-47` is unaffected — nothing is removed; duplicates collapse logically on read. **A decision record records that the decision was taken; whether the operation proceeded is a separate record**, so a record persisted while the caller failed closed is accurate rather than false. If a deterministic identity cannot be established, the write is treated as failed and the rule above applies. |

## Added by Section 05 — AI Architecture & Model Gateway

> **`I-94`–`I-105` were accepted by James on 2026-08-14 with ADRs `0024`–`0028`.** *(Added and
> accepted 2026-08-14.)* This file is Active Section 03 material and every change to it is C3.
> `I-01`–`I-93` are **unmodified** by Section 05.

*Same status as every invariant above: REQUIREMENT, unverified.*

### Model egress

| # | Invariant |
| --- | --- |
| **I-94** | **Model egress is a Policy Enforcement Point.** Every model call is an authorization decision evaluated by the PDP **per call**, against the Context Token, the classification of every item in the request, and the **destination provider**. There is no path to a provider without a decision, and PDP unavailability is deny (`I-17`). Emergency stop (`I-19`) and revocation (`I-74`) take effect here as at every enforcement point; a gateway that cannot confirm a stop refuses to call. The gateway **decides nothing** — like every enforcement point it can only deny (`I-77`). |
| **I-95** | **No model request carries content from more than one scope** — meaning content not covered by the execution's single bound scope, the same test `I-86` applies to channels. PUBLIC and INTERNAL material is not a second scope; an ancestor-scope shared resource requires the per-resource grant `I-82` already demands and is then covered. **Sibling content in one request is forbidden**, and no token or grant produces it. Model context is scope-bound and is **discarded at scope change**; no conversation, cache, or provider-side session is shared across scopes. Cross-scope work reaching a model is N single-scope calls aggregated above them — the rule [`CROSS_SCOPE_DATA_RULES.md`](./CROSS_SCOPE_DATA_RULES.md) §3 and §6 already apply to storage and output, applied to the model request. **A model call concerning no client scope is decided the same way and its record is a control-plane event under `W-3` (`I-92`)**, never placed in a client partition. |
| **I-96** **[PHYS]** | **Content whose classification forbids model exposure never reaches a provider.** SECURITY-CRITICAL and credential material never cross under any grant, approval, or profile; SENSITIVE-PERSONAL crosses only on explicit per-call approval; CLIENT-CONFIDENTIAL crosses only in a scoped call (`I-95`, `I-97`). **If the classification of any item cannot be established, or redaction cannot be confirmed applied, the request is denied** (`I-52`'s pattern). Redaction removes what NOVA can identify: this is containment, not prevention, and it does nothing after egress (`T-15`). |
| **I-97** | **Provider selection is authorization-constrained, not weighted.** A request is routed only to a provider permitted for the scope and for every classification present; the remaining routing factors optimise **within** that set. **Fallback, failover, reroute and retry select only within the permitted set**; if it is empty the call fails closed and says so. Degradation never widens the permitted set. |
| **I-98** | **Capability profile, provider, and model are never selected by model output at call time.** They are declared by the agent definition or fixed in the authorized plan, and no model output requests, names, changes, or causes a reroute away from that. **The plan is itself model-produced, and this is narrower than "no model touches routing":** a profile in an authorized plan has passed the PDP at Permission Evaluation, and a plan influenced by untrusted content is already ceilinged at `PREPARE` (`I-40`, `I-58`, detectable via `I-99`). What is forbidden is a change **after** the authorization that fixed it — the same authorize-the-envelope-then-check-the-value structure as `I-100`. |

### Model output and authority

| # | Invariant |
| --- | --- |
| **I-99** | **Model output is a derivation of its inputs, whether or not it is stored.** It carries the union of the provenance of every item in its request — system prompt, retrieved memory, tool results, conversation history — and the **lowest trust** among them, in addition to its own `model.generated` provenance. Taint survives **transience** (an output never written to storage carries the same labels as one that is), **chaining** (a call reading a previous call's output inherits its labels; the union is taken at every hop), and **summarization**. Model confidence promotes nothing (`I-39`). This is `PROVENANCE_AND_TRUST.md` §6.2 and `I-31` applied where the derivation actually happens, and it is what makes `I-40` and `I-58` evaluable. |
| **I-100** | **Tool arguments are authorized, not merely validated.** Schema validity is a type check, not an authority check. Every **consequence-determining** argument — target, scope-bearing identifier, magnitude, destination, irreversibility-bearing selector — is checked at the tool enforcement point against the **envelope** fixed by the authorization that permitted the action. A value **covered** by it proceeds; a value **not covered** is denied and recorded as a security event, not a retryable error (`SECURITY_BOUNDARIES.md` §6); a covered value **derived from untrusted content** (`I-99`) cannot execute above `PREPARE` without approval naming the source (`I-40`, `I-58`). Tools declare which arguments are consequence-determining, and one that does not is not registered. An action whose consequence-determining arguments cannot be expressed as an envelope is not autonomously executable. |
| **I-101** | **Risk classification is one-way with respect to models.** The class the PDP evaluates derives from the action, resource, scope, and the tool's declared risk class. A model may **raise** it; a model **never lowers** it and **never supplies it** in the absence of a derived one — absence is a denial, not `READ` (`I-52`'s pattern). `PERMISSION_ARCHITECTURE.md` §4 forbids an agent lowering a class; this closes the case where the class was never set high, because a model that read injected content produced the classification. |
| **I-102** | **Model verification is corroboration, never evidence.** A result checked by a model never gains epistemic status (`I-39` — `model.generated` checked by `model.generated` is inference at best; `system.verified` requires an authoritative source), **never satisfies an approval requirement** (`I-09` unchanged), and **never lowers a risk class** (`I-101`). Where a model check gates an action above `PREPARE` it is not the same call and not the same instance that produced the result, and it does not receive the producing call's untrusted inputs unlabelled. A **different provider is preferred and not required** — requiring it would make verification unavailable wherever one permitted provider exists (`I-97`), and a silently skipped check is worse than a same-provider one. |

### Provider credentials, retries, and cost

| # | Invariant |
| --- | --- |
| **I-103** | **Provider credentials are control-plane credentials.** Held only by the Model Gateway, **never bound to a client scope**, never brokered to an agent, tool, integration, sandbox, or coding agent (`I-22` unaffected), never present in a prompt, log, memory, audit payload, or model context (`I-21`). A provider credential authorizes NOVA to talk to a provider and authorizes access to **no client scope**; the scope's authorization to reach that provider is carried by the Context Token and decided at `I-94`, never by the credential. **`I-23` is unamended** — a control-plane credential is not a scope-bound credential and does not claim to be. The class is closed: its members reach services acting for NOVA itself rather than for a scope, and adding one is C3. **Residual, not mitigated:** one credential serving many scopes lets the provider correlate them as one customer (`T-30`). |
| **I-104** | **A retried or rerouted model call re-issues no side effect, and every attempt is separately authorized and accounted.** If a model call's tool calls were already dispatched, the model call is not retried — the step is re-planned or escalated. The retry boundary is the model call; the dispatch boundary is the tool enforcement point; they are not the same boundary. A reroute changes the destination provider, which is an input to `I-94`, so failover inherits no prior allow. Cost accounting records **attempts**, not outcomes. |
| **I-105** | **Every execution carries a model cost and token ceiling, and reaching it terminates and escalates.** It never silently degrades to a cheaper model, a shorter context, or a truncated result. **Above `PREPARE` it fails closed**: a high-risk action does not complete on a degraded basis to stay within budget. Ceilings are attributable per execution, workflow and scope, so abnormal consumption is a signal rather than only an invoice. Unbounded model consumption is a denial of service reachable by injected content without crossing an authorization boundary; ceiling **values** are deferred (`D-40`). |

## Added by Section 06 — Agent Architecture & Agent Governance

> **`I-106`–`I-109` were accepted by James on 2026-08-14 with ADRs `0029`–`0031`.** *(Added and
> accepted 2026-08-14.)* This file is Active Section 03 material and every change to it is C3.
> `I-01`–`I-105` are **unmodified** by Section 06.
>
> **`I-109` carries a Proposed Section 11 amendment** *(2026-08-15)* scoping its exclusion list
> between model calls and tool actions — marked in place in the row itself, authorized by
> [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), and reverted to
> the accepted wording verbatim if that ADR is rejected. **`I-106`–`I-108` are unmodified.**

*Same status as every invariant above: REQUIREMENT, unverified.*

| # | Invariant |
| --- | --- |
| **I-106** | **The Context service is the sole issuer of Context Tokens, and issuance is verified.** The Agent Runtime **requests** narrowing; it never mints — a runtime-minted token fails `I-87`'s integrity detection at every enforcement point. Before issuing, Context refuses any request whose resulting token would exceed **any** of: the requesting execution's own integrity-verified token; the named **agent definition's** Allowed Context, Allowed Tools and Permissions; James-created grants (`I-10`); or the delegation constraints of `I-107`. **This is where `I-07`'s intersection is enforced rather than asserted** — the only point at which all four inputs exist together; the PDP's ten-step sequence never consults the agent definition and is not made to (`P-7`, `P-11`). **Refusal is total and fail-closed**: on mismatch, on failed token integrity, on an unreadable or incomplete agent definition, or on any uncertainty, **no token is issued**, the access is denied, and the refusal is recorded. **There is no partial issuance.** Context still decides no authorization — it can only refuse to issue, never permit what the PDP denied. **This does not mitigate compromise of the Context service** (`T-23a`), which would be performing this check on itself. |
| **I-107** | **Delegation is strictly narrowing, explicitly re-delegable, and cannot outlive its delegator.** Every delegation is **strictly** narrower than its delegator in at least one of scope, rights, tools, or risk ceiling, **and** expires strictly earlier — **which is what bounds delegation depth**, on a finite authority lattice, and is why no numeric depth limit exists. ***AG-8 WITHDRAWN AS REDUNDANT — corrected 2026-08-15 on James's decision (C3); accuracy correction, not a newly discovered vulnerability. Evidence: `slice/FINDINGS.md` Finding 4.*** **Cycles need no separate rule, because strict narrowing already terminates them.** `A → B → A` is permitted and harmless: each re-entry holds **strictly less** authority than the previous one and expires strictly earlier, so the chain descends a finite lattice and ends — measured as `EXECUTE → PREPARE → ANALYZE → READ → refused`. The withdrawn rule could never fire in any case: it compared the **delegate** (an *agent*) against **`ancestry`** (a chain of *execution identities*), and execution identities are ephemeral and never reused (`AUTHENTICATION_MODEL.md` §5). **The `ancestry` field is retained** — it records the chain for audit and is what fails a descendant closed when any ancestor ends. `AG-7`, `AG-9`, `AG-11` and `AG-13` are unchanged and each independently bounds the cycle. Re-delegation requires **`may_redelegate`**, which is explicit and **defaults to false**: a capability an agent may *use* is not thereby one it may *pass on*. **Fan-out carries no count limit** — parallel children are bounded by `I-108`, which governs the resource fan-out consumes. **A child execution never outlives the execution identity that granted it**: on normal completion, failure, termination, revocation, or emergency stop alike, the child's delegated authority is invalid and it fails closed at its next enforcement point (`V-2`, extended from revocation to any end of the granting identity). **No suspended agent state exists.** All of this is checked at issuance (`I-106`). |
| **I-108** | **The model cost and token ceiling belongs to the root execution and is shared by its entire delegation tree.** A descendant **cannot mint capacity, receive a fresh budget, raise the root ceiling, or transfer capacity into an independent budget.** A parent **may** carve a smaller child ceiling — optional and itself narrowing; it is **not** mandatory, because requiring it would force an allocation policy the architecture does not decide and hand a security-relevant number to an implementer. Retries and model fallback consume the same budget and remain accounted per attempt (`I-104`). Exhaustion behaves exactly as `I-105` states: terminate and escalate, never silent degradation, fail closed above `PREPARE`. **The ceiling is not per agent** (instances are ephemeral) **and not per client scope** (one runaway execution would consume a client's whole allowance). **Accepted cost:** one runaway child can starve its siblings. **Under concurrency the budget overruns boundedly and never mints** — concurrent descendants may each observe remaining budget, so consumption can exceed the ceiling by at most the in-flight calls' worth; every such call still drew on the root budget, and the next check applies `I-105`. A strictly serialized counter is deliberately not required. A duplicate or replayed delegation creates no capacity, for the same reason. |
| **I-109** | **An approval binds the effective authorization, not the implementation.** It remains valid only while all nine of these are unchanged between approval and execution: **action, resource, scope, effective rights, risk class, tool set, argument envelope (`I-100`), delegation ancestry, cost ceiling.** It does **not** bind the **ephemeral agent instance identity**, wording, formatting, ordering, or other implementation metadata — instances are ephemeral by design, so binding to one would make every approval stale on principle. ***AMENDED BY SECTION 11 — ACCEPTED by James 2026-08-15*** *(2026-08-15; authority [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), **Accepted** 2026-08-15).* **The remaining exclusions are now scoped, because one list served two different things.** For a **model call**, the approval does **not** bind model, provider or capability profile — unchanged, and for the reason originally given: those are decided **per call** by `I-94` and `I-97`, which constrain routing to the permitted set, so the decision is made afresh rather than inherited. **For a consequence-producing tool action there is no such per-call decision, and the exclusion was unsafe:** the approval **also binds the execution binding** — tool version, integration, credential binding (`I-114`) — as a **tenth** bound property. **`I-109` must not be read as saying provider identity is irrelevant to tool authorization.** The nine properties above are unchanged and unreordered. The binding reuses `I-93`'s **deterministic identity** construction; **no cryptography is introduced.** If the binding differs at execution, **the approval does not apply**, execution does not proceed under it, and fresh approval is required where the risk class requires approval. `I-09` is unchanged: only James approves. |

## Added by Section 07 — Context & Memory Architecture

> **`I-110`–`I-111` are PROPOSED, not accepted.** *(Added 2026-08-14.)* This file is Active
> Section 03 material and every change to it is C3. **Everything from `I-110` down is proposed
> through Section 07 and stands or falls with ADRs `0032`–`0033`, which are Proposed.** If those
> ADRs are rejected, these invariants are removed rather than retained. `I-01`–`I-109` are
> **unmodified** by Section 07.

*Same status as every invariant above: REQUIREMENT, unverified.*

| # | Invariant |
| --- | --- |
| **I-110** | **Raising an item's trust is an explicitly authorized operation.** It is **never automatic, never performed by an agent, and never model-mediated**, and is never inferred from repetition, model confidence, consensus across model calls, internal origin, or the fact that NOVA produced it. It is a **C3** change, governed exactly as `I-30` governs downward reclassification. **Every promotion records seven things or does not happen:** the item, its immutable provenance, the evidence relied on, the authoritative source, the resulting trust level, the responsible authority, and the trace identity. **`system.verified` may be assigned only after checking against an authoritative source**, which must be (a) **external to the model's own output**, (b) **identifiable**, (c) **reproducibly and auditably checkable**, and (d) **itself compliant with the applicable trust and data-policy requirements**. **A model asserting that it verified something is never evidence of verification** (`I-102`), and **a model-generated summary of an authoritative source is not the authoritative source** (`I-99`). **Enforcement is at the memory write / revalidation path, before the elevated item becomes eligible for downstream use.** On uncertainty, missing evidence, an unidentifiable source, or a failed check, **the promotion is denied and the item keeps its existing trust** — never retained provisionally, never applied pending review. `I-38` is untouched: provenance is immutable, and a promotion adds a verification record rather than rewriting origin. **Lowering trust is not governed by this invariant** — restriction is not gated like elevation. |
| **I-111** | **Provenance, taint and delegation ancestry survive persistence and are restored at retrieval.** Persistence **must not** discard provenance, collapse multiple provenance sources into one, raise trust, remove taint, or replace `I-99`'s union with the latest writer alone. Retrieval **must restore** everything `I-99`, `I-100`, `I-101`, `I-27`, `I-29` and the quarantine and promotion rules are evaluated against — the **union** of contributing provenance, the **lowest** trust among them, and, where the producing execution was a delegate, its **delegation ancestry** (`I-107`). **Survival is not authority:** memory written by a delegated child is scope-owned and correctly outlives the child, and a broader ancestor retrieving it **must not treat it as more authoritative than the authority and trust state under which it was created** (`I-27`). Delegate memory is **not invalid**, and no separate authority hierarchy for memory is created. **This is a security property, not an implementation detail:** `I-100`'s untrusted-derived argument ceiling is evaluated against this labelling, so a write that collapses it or a retrieval that drops it defeats `I-100` silently while satisfying every other retrieval rule. |

## Added by Section 08 — Reasoning, Planning & Orchestration

> **`I-112`–`I-113` are PROPOSED, not accepted.** *(Added 2026-08-14.)* This file is Active
> Section 03 material and every change to it is C3. **Everything from `I-112` down is proposed
> through Section 08 and stands or falls with ADRs `0034`–`0035`, which are Proposed.** If those
> ADRs are rejected, these invariants are removed rather than retained. `I-01`–`I-111` are
> **unmodified** by Section 08.

*Same status as every invariant above: REQUIREMENT, unverified.*

| # | Invariant |
| --- | --- |
| **I-112** | **A plan is a security object with a declared schema, a deterministic identity, and immutability after authorization.** It carries: identity · steps · dependencies · required rights · declared risk class · scope · **provenance/taint union** · cost estimate ([`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §2.1). **Identity is derived by the construction `I-93` already establishes** and `I-109` already reuses; no new identity mechanism exists. **Once authorized the plan is immutable:** any material change — a step, resource, right, risk class, scope, tool, or cost — **produces a new plan with a new identity requiring new authorization**, and a reused identity after mutation is not the plan that was authorized. **The plan's taint is a persisted security property, not prose**: it carries the union of its inputs' provenance and the lowest trust among them under `I-99`, persisted and restored under `I-111`, and **not** as a parallel provenance system. This is what makes `I-40` enforceable — a plan influenced by untrusted or quarantined content carries that fact to the authorization boundary and cannot exceed `PREPARE` without approval naming the source. **`I-40` is unweakened.** **A plan is never authoritative because a model produced it** (`I-20`): the Planner is a model, its output is `model.generated` at low trust, and a plan becomes authoritative only on authorization. |
| **I-113** | **Plan authorization is an envelope; every action inside it is still authorized independently.** The plan-level decision fixes **scope, risk ceiling, tool set, cost ceiling and composition**; each action is then evaluated by [`AUTHORIZATION_MODEL.md`](./AUTHORIZATION_MODEL.md) §3's **unmodified** ten-step sequence at its own enforcement point. **Neither substitutes for the other:** an envelope never authorizes an action, and an action's allow never permits exceeding the envelope. **The PDP is not a composition engine** (`P-7`, `P-11`). **Composition is bounded:** a plan's individually permissible actions **must not exceed the envelope when taken together**, and the plan declares enough for enforcement to evaluate the collection rather than only its members — permitted read + permitted write + permitted send do not silently compose into an unauthorized operation. **Re-planning creates a new plan** (`I-112`) which **returns through Permission Evaluation and never inherits the prior authorization because the objective is unchanged.** **Resumption after partial execution re-checks `I-109`'s binding against current state before the next step and fails closed if it no longer matches**, requiring fresh authorization where the risk class requires it. **Re-planning loops fail closed to escalation** and are bounded by the **root execution budget** (`I-105`, `I-108`) — the Planner and Verifier calls they consume draw on it — rather than by a separate iteration counter. `PERMISSION_ARCHITECTURE.md` §5's *"one action, in one context, at one time"* is preserved unchanged: **a plan approval is an envelope approval and never becomes blanket authorization.** |

## Added by Section 11 — Integration Architecture

> **`I-114` is PROPOSED, not accepted, and `I-109` is amended in place — also Proposed.**
> *(Added 2026-08-15.)* This file is Active Section 03 material and every change to it is C3.
> **`I-114` and the `I-109` amendment stand or fall together with
> [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), which is
> Proposed.** If it is rejected, `I-114` is removed rather than retained and **`I-109`'s accepted
> wording is restored verbatim**. `I-01`–`I-108` and `I-110`–`I-113` are **unmodified** by
> Section 11.

*Same status as every invariant above: REQUIREMENT, unverified.*

| # | Invariant |
| --- | --- |
| **I-114** | **A consequence-producing tool action is authorized against the binding that will produce the consequence, not against the tool alone.** A tool is defined once at root; the **integration** and **credential binding** that carry it are per scope ([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §1), so the same tool with the same schema-valid, envelope-covered arguments (`I-100`) reaches a different external system with different semantics depending on where it is bound. **The authorization must therefore see what the execution will actually use.** Four requirements. **(a) Resolve before deciding.** The **execution binding** — tool identity **and version**, integration, credential binding, and the scope it is resolved in — is resolved **before** the authorization decision, and is an input to it. An action whose binding cannot be resolved is **denied**, never executed against a default or a last-known binding (`I-14`'s pattern). **(b) The authorization fixes a binding envelope; the enforcement point checks the actual binding against it.** This is `I-100`'s and `I-113`'s structure reused, not a second permission model: plan or action authorization fixes **which bindings are permitted**, and the tool enforcement point checks the **resolved** binding at call time. A binding **covered** by the envelope proceeds; a binding **not covered** is **denied and recorded as a security event, not a retryable error** (`SECURITY_BOUNDARIES.md` §6), exactly as `I-100` treats an uncovered argument. **(c) Binding identity is consequence-bearing.** An integration's identity changes when what it reaches or how it interprets a request changes — provider, account or tenant, endpoint, or declared API version. **A configuration change that alters the consequence produces a different binding, not the same binding reconfigured**, or this invariant is vacuous. Changing it is **C3** (`TOOL_AND_INTEGRATION_ARCHITECTURE.md` §6), on the same ground that changing a tool's risk class or required rights is. **(d) There is no binding substitution and no provider equivalence.** Failover, reroute, retry and resumption select **only within the authorized envelope** — the rule `I-97` already applies to model providers, applied to tool bindings. Two integrations reaching the same provider are **two bindings**; NOVA defines no mechanism by which one may stand in for another, and an unavailable binding **fails closed** rather than substituting. **The binding is never selected by model output** (`I-98` extended from provider/profile/model to the execution binding): it is resolved from the scope and the authorized envelope, and no model output requests, names, changes, or causes a reroute away from it. **What this does not do:** it controls **NOVA's own choice of execution substrate**, not the external system's behaviour. A provider that changes what it does behind a stable identity is not detected here (`T-39`), and a side effect already submitted is not recalled (`T-38`, ADR 0037 §`S11-D3`). |

---

## Testing These

[`TESTING_ARCHITECTURE.md`](./TESTING_ARCHITECTURE.md) §3 requires isolation, permission,
credential, context, boundary, escalation, sandbox, and injection tests. **This file is the
specification those tests implement.** Each invariant should map to at least one adversarial
test written from the position of "how would I violate this?" — not "does the happy path
work?"

`I-03` deserves particular attention: it includes error messages and timing, because a
denial that reveals *whether a resource exists* is itself a cross-client disclosure.
