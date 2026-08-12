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

## Technology and Platform

| # | Deferred decision | Target section |
| --- | --- | --- |
| D-01 | Application language, framework, and runtime | 02 / 29 |
| D-02 | Database technology and hosting | 03 |
| D-03 | Data model, schema, and storage layout | 03 |
| D-04 | Cloud provider and hosting platform | 29 |
| D-05 | Queue / job execution technology | 12 / 29 |
| D-06 | Vector database and retrieval technology | 07 / 09 |
| D-07 | Orchestration platform and execution model | 08 |
| D-08 | AI providers and specific models | 05 |
| D-09 | Authentication provider and identity model | 04 |
| D-10 | Secrets storage and credential vault technology | 04 |
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
| D-29a | Export formats and deletion mechanics | Requires the data model | `D-03` | 37 / 44 |
| D-31 | Sandbox provisioning technology for coding agents | Isolation requirements defined; the technology meeting them is not chosen | Platform choice, `D-04` | 30 |
| D-32 | Notification routing and interruption policy | Depends on real usage patterns and device surfaces | `Q-03`, lived experience | 25 |
| D-33 | Physical isolation strategy — row-level vs schema vs database per client | Logical isolation is specified; the physical enforcement mechanism is a Section 03 choice with cost and complexity tradeoffs | `D-02`, expected client volume | 03 |

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
