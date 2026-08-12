# Deferred Decisions Register

**Status:** Active — established in Section 01.
**Purpose:** Track decisions intentionally postponed, so that a later session recognizes
them as *deliberately open* rather than *accidentally missing*.

Every entry below is **Deferred — to be resolved in a future section.** None of these is
a guess, a default, or an implied commitment. Where a future session resolves an entry,
it records an ADR (see [`README.md`](./README.md)) and removes the entry from this list.

---

## Resolved in Section 02

These moved from deferred to decided. Each is a *design* decision, not a technology
selection — the technology beneath each remains deferred below.

| # | Was | Resolved by |
| --- | --- | --- |
| D-20 | Model gateway design and routing policy | [ADR 0007](./0007-model-gateway-provider-neutrality.md), [`MODEL_ARCHITECTURE.md`](../architecture/MODEL_ARCHITECTURE.md) |
| D-21 | Permission model mechanics and enforcement points | [ADR 0003](./0003-context-token-and-brokered-credentials.md), [`PERMISSION_ARCHITECTURE.md`](../architecture/PERMISSION_ARCHITECTURE.md) |
| D-22 | Client-isolation enforcement mechanism | [ADR 0002](./0002-unified-scope-tree.md), [ADR 0003](./0003-context-token-and-brokered-credentials.md), [`SECURITY_BOUNDARIES.md`](../architecture/SECURITY_BOUNDARIES.md) |
| D-23 | Context Lock design and disambiguation behaviour | [`CONTEXT_ARCHITECTURE.md`](../architecture/CONTEXT_ARCHITECTURE.md) — *implementation still deferred to 08/16* |
| D-25 | Agent runtime model, registration, lifecycle | [`AGENT_ARCHITECTURE.md`](../architecture/AGENT_ARCHITECTURE.md) — *runtime build deferred to 06* |
| D-26 | Approval mechanics and emergency stop | [ADR 0006](./0006-risk-classified-approvals.md), [`PERMISSION_ARCHITECTURE.md`](../architecture/PERMISSION_ARCHITECTURE.md) §5–6 |
| D-27 | Failure detection, retry, escalation, notification | [`RELIABILITY_ARCHITECTURE.md`](../architecture/RELIABILITY_ARCHITECTURE.md) |
| D-30 | Multi-business structural approach | [ADR 0002](./0002-unified-scope-tree.md), [`DOMAIN_ARCHITECTURE.md`](../architecture/DOMAIN_ARCHITECTURE.md) |

**Partially resolved, still open:**

| # | Decided in Section 02 | Still unresolved | Owner |
| --- | --- | --- | --- |
| D-24 | Memory tiers, scope partitioning, hygiene rules ([`MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`](../architecture/MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md)) | Retrieval mechanics, decay algorithms, storage | 07 |
| D-28 | Cost as a first-class orchestration input | Budgets, thresholds, billing | 34 |
| D-29 | Scope as the unit of export and deletion | Export formats, deletion mechanics | 37 / 44 |

---

## Resolved in Section 03

Design decisions only. No technology was selected.

| # | Was | Resolved by |
| --- | --- | --- |
| D-03 | Data model — *conceptual* | [`DATA_ARCHITECTURE.md`](../architecture/DATA_ARCHITECTURE.md), [`INVARIANTS.md`](../architecture/INVARIANTS.md). *Physical schema still open — see D-03a* |
| D-29a | Export and deletion *design* | [ADR 0013](./0013-deletion-and-forgetting.md), [`DATA_LIFECYCLE.md`](../architecture/DATA_LIFECYCLE.md) §7–8. *Formats still open — D-29b* |

**New decisions made in Section 03:** credentials as references ([0009](./0009-credentials-are-references.md)),
derived-data inheritance ([0010](./0010-derived-data-inheritance.md)), three-axis provenance
([0011](./0011-provenance-trust-epistemic-separation.md)), classification
([0012](./0012-data-classification-model.md)), deletion ([0013](./0013-deletion-and-forgetting.md)),
authorization ordering ([0014](./0014-authorization-decision-model.md)), extensible scope kinds
([0015](./0015-extensible-scope-kinds.md)).

### Governance note — D-02 and D-33 disposition, confirmed by James 2026-08-12

This register originally assigned **D-02** (database technology) and **D-33** (physical
isolation strategy) to Section 03. James's Section 03 instruction forbade selecting a
database or storage technology, so Section 03 delivered the conceptual model and left both
deferred, proposing a reassignment rather than actioning one.

**James confirmed the disposition on 2026-08-12** (a C3 decision, per
[ADR 0008](./0008-architectural-governance-model.md)):

| # | Disposition |
| --- | --- |
| **D-02** — database technology | **Remains deferred.** No database or other technology is to be selected. Owner: **29** (Application Infrastructure) |
| **D-33** — physical isolation / enforcement below the query layer | **A Section 04 security decision.** It determines whether `I-03` and `I-33` are structural or merely asserted, which makes it a security question rather than an infrastructure preference. Owner: **04**, implemented alongside `D-02` in **29** |

Section 04 may therefore specify the isolation *requirement* — enforcement must occur below
the query layer such that out-of-scope partitions are unreachable, not merely unreturned —
**without naming a product**.

---

## Resolved in Section 04

**Design decisions only. No technology was selected.** Each entry below fixes a *requirement*;
the product satisfying it remains deferred.

| # | Was | Resolved by | Still open |
| --- | --- | --- | --- |
| D-33 | Physical isolation strategy | [ADR 0016](./0016-isolation-enforced-below-query-layer.md), [ADR 0017](./0017-isolation-independent-of-pdp.md), [`ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) — **requirement fixed, mechanism family criteria defined** | The mechanism itself, with `D-02` in 29 |
| D-09 | Authentication and identity model | [ADR 0018](./0018-authentication-model.md), [`AUTHENTICATION_MODEL.md`](../architecture/AUTHENTICATION_MODEL.md) | **Provider and factor technology — `D-09a`** |
| D-10 | Secrets storage requirements | [ADR 0019](./0019-secrets-store-separation.md), [`SECRETS_ARCHITECTURE.md`](../architecture/SECRETS_ARCHITECTURE.md) | **Store technology — `D-10a`** |
| D-34 | Authorization engine requirements | [`POLICY_ENGINE_REQUIREMENTS.md`](../architecture/POLICY_ENGINE_REQUIREMENTS.md) | **Language and engine — `D-34a`** |
| D-35 | Encryption requirements and key scoping | [ADR 0020](./0020-keys-mirror-the-scope-tree.md), [`ENCRYPTION_REQUIREMENTS.md`](../architecture/ENCRYPTION_REQUIREMENTS.md) | **Algorithms and key management — `D-35a`, Section 38** |

**New in Section 04:** revocation timing and break-glass ([ADR 0021](./0021-revocation-and-break-glass.md)).

**`D-02` remains deferred and untouched**, per James's instruction. ADR 0016 constrains the
eventual choice through criteria `C-1`–`C-9` but selects nothing.

---

## Technology and Platform

| # | Deferred decision | Target section |
| --- | --- | --- |
| D-01 | Application language, framework, and runtime | 02 / 29 |
| D-02 | Database technology and hosting | **29** — *remains deferred; no technology to be selected* |
| D-03a | Physical schema and storage layout *(conceptual model done in 03)* | **29** |
| D-04 | Cloud provider and hosting platform | 29 |
| D-05 | Queue / job execution technology | 12 / 29 |
| D-06 | Vector database and retrieval technology | 07 / 09 |
| D-07 | Orchestration platform and execution model | 08 |
| D-08 | AI providers and specific models | 05 |
| D-09a | Authentication **provider and factor technology** *(model resolved in 04)* | 29 |
| D-10a | Secrets **store technology** *(requirements resolved in 04)* | 29 |
| D-11 | Observability, logging, and audit stack | 27 / 28 |
| D-12 | Testing framework and AI evaluation tooling | 31 |
| D-13 | UI framework and design-token implementation | 15 / 16 |
| D-14 | Voice / speech technology | 14 |
| D-15 | Backup and disaster-recovery mechanism | 36 |

---

## Architecture and Mechanism — Still Open

| # | Unresolved | Why it remains open | Information required | Owner |
| --- | --- | --- | --- | --- |
| D-23a | Context Lock *implementation* | Design settled; mechanics depend on the orchestration runtime | Runtime and UI surface choices | 08 / 16 |
| D-24a | Memory retrieval, decay, storage | Boundaries settled; mechanics depend on storage and retrieval technology | `D-02`, `D-06` | 07 |
| D-25a | Agent runtime implementation | Model settled; execution mechanics depend on the platform | `D-01`, `D-04` | 06 |
| D-28a | Budgets, thresholds, billing | Requires real cost data from actual usage | Observed costs once running | 34 |
| D-29b | Export formats and serialization | Design settled in Section 03; formats depend on the storage choice | `D-02` | 37 / 44 |
| D-34a | Policy **language and engine** | Requirements fixed in Section 04 ([`POLICY_ENGINE_REQUIREMENTS.md`](../architecture/POLICY_ENGINE_REQUIREMENTS.md)); a candidate failing `P-1`–`P-5` or `P-10` is disqualified | `D-01`, `D-02` | 29 |
| D-35a | Encryption **algorithms and key management** | Requirements and key scoping fixed in Section 04 ([ADR 0020](./0020-keys-mirror-the-scope-tree.md)); mechanism depends on storage | `D-02` | 38 |
| D-37 | Key custody, escrow and recovery mechanics | `E-10` makes key loss equal data loss; recovery must be designed as carefully as authentication recovery | `D-02`, `D-35a` | 36 |
| D-38 | Break-glass credential storage mechanism | Bounded and specified ([ADR 0021](./0021-revocation-and-break-glass.md)); the store is a technology choice | `D-10a` | 29 |
| D-36 | Small-N aggregation threshold | The re-identification risk is identified; the safe threshold depends on real client counts | `Q-01`, `Q-08` | 22 / 37 |
| D-31 | Sandbox provisioning technology for coding agents | Isolation requirements defined; the technology meeting them is not chosen | Platform choice, `D-04` | 30 |
| D-32 | Notification routing and interruption policy | Depends on real usage patterns and device surfaces | `Q-03`, lived experience | 25 |
| D-33a | Isolation **mechanism selection** *(requirement resolved in 04 — [ADR 0016](./0016-isolation-enforced-below-query-layer.md))* | The requirement and disqualifying criteria `C-1`–`C-9` are fixed; the mechanism family and product are chosen with `D-02` | `D-02`, expected client volume | **29** |

---

## Open Questions Requiring James's Input

These are not technical postponements; they need information only James can supply. They
are listed so Section 02 begins by resolving them rather than assuming.

| # | Question |
| --- | --- |
| Q-01 | Which businesses besides KAIRO exist or are planned, and what are their names? |
| Q-02 | What does WEALTH cover in scope — accounts, assets, investments, budgeting, reporting? |
| Q-03 | Which devices and surfaces must NOVA run on first (desktop, mobile, web, voice)? |
| Q-04 | Is NOVA single-user only, or will other people (staff, collaborators) ever have access? |
| Q-05 | Which existing systems, tools, or data must NOVA integrate with earliest? |
| Q-06 | What are the hard constraints — budget, hosting preferences, data-residency, privacy? |
| Q-07 | Which LIFE Areas actually exist, and which are sensitive? *(Added in Section 02. `DOMAIN_ARCHITECTURE.md` §2 defines the Area/Thread shape; the actual Areas are James's to name.)* |
| Q-08 | Which existing KAIRO clients and projects should NOVA know about first? *(Added in Section 02 — determines the initial scope tree.)* |

---

## Note on Section 02's Scope

Section 02 resolved **design** questions, not **technology** questions. Every entry in the
Technology and Platform table above remains open by intent — Section 02 was explicitly
forbidden from selecting technology, and none was selected. The architecture is written so
that each of those choices remains reversible when it is made.
