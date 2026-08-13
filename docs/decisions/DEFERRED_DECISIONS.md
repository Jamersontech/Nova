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

## Governance correction — M-7 resolved by James, 2026-08-12

During Section 04, `D-09`, `D-10`, `D-34` and `D-35` were reassigned away from Section 04
without approval. Reassigning section ownership is a C3 change under
[ADR 0008](./0008-architectural-governance-model.md).

**James resolved this by restoring the original ownership exactly:**

| # | Original owner | Restored to | Source of original |
| --- | --- | --- | --- |
| `D-09` | 04 | **04** | Section 01 (`0626610`) |
| `D-10` | 04 | **04** | Section 01 (`0626610`) |
| `D-34` | 04 | **04** | Section 03 (`6f90238`) |
| `D-35` | 04 / 38 | **04 / 38** | Section 03 (`6f90238`) |

The unapproved `D-09a` / `D-10a` / `D-34a` / `D-35a` identifiers and their Section 29/38
assignments are withdrawn. **No other decision ownership was changed.** `D-02` and `D-33`
retain the disposition James confirmed separately and were not touched.

---

## Decisions *created* by Section 04 — approved by James 2026-08-13

*Added 2026-08-13 (N-14). These are **new** deferred decisions minted during Section 04, not
pre-existing entries. Assigning ownership of a decision is a C3 change under
[ADR 0008](./0008-architectural-governance-model.md), so each required James's explicit
approval — which was given during the Section 04 review on **2026-08-13**.*

**These were never previously approved, and this record does not present them as though they
were.** They were created during Section 04, carried unapproved through the amendment passes, and
flagged by the final independent hostile review before being put to James.

| # | Created by | Assigned owner | Approved | Relationship to any original decision |
| --- | --- | --- | --- | --- |
| `D-33a` | Section 04 | **29** | **James, 2026-08-13** | **New.** Splits the *mechanism selection* out of `D-33`. `D-33` itself is untouched and retains the disposition James confirmed separately |
| `D-37` | Section 04 | **36** | **James, 2026-08-13** | **New.** Did not previously exist; arises from `E-10` |
| `D-38` | Section 04 | **29** | **James, 2026-08-13** | **New.** Did not previously exist; arises from `B-7` |

**Contrast with the M-7 correction above.** `D-09a`/`D-10a`/`D-34a`/`D-35a` were *reassignments
of existing Section 04 decisions* made without approval, and were **withdrawn**. The three above
are *newly created* decisions covering work Section 04 genuinely cannot do, and were
**approved**. The two cases are recorded separately and deliberately so that neither is read as
precedent for the other.

**`D-02` and `D-33` ownership is unchanged by any of this.**

---

## Resolved in Section 04

**Design decisions only. No technology was selected.** Each entry below fixes a *requirement*;
the product satisfying it remains deferred.

| # | Was | Resolved by | Still open |
| --- | --- | --- | --- |
| D-33 | Physical isolation strategy | [ADR 0016](./0016-isolation-enforced-below-query-layer.md), [ADR 0017](./0017-isolation-independent-of-pdp.md), [`ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) — **requirement fixed, mechanism family criteria defined** | The mechanism itself, with `D-02` in 29 |
| D-09 | Authentication and identity model | [ADR 0018](./0018-authentication-model.md), [`AUTHENTICATION_MODEL.md`](../architecture/AUTHENTICATION_MODEL.md) | Provider and factor technology — remains under **`D-09`**, owner 04 |
| D-10 | Secrets storage requirements | [ADR 0019](./0019-secrets-store-separation.md), [`SECRETS_ARCHITECTURE.md`](../architecture/SECRETS_ARCHITECTURE.md) | Store technology — remains under **`D-10`**, owner 04 |
| D-34 | Authorization engine requirements | [`POLICY_ENGINE_REQUIREMENTS.md`](../architecture/POLICY_ENGINE_REQUIREMENTS.md) | Language and engine — remains under **`D-34`**, owner 04 |
| D-35 | Encryption requirements and key scoping | [ADR 0020](./0020-keys-mirror-the-scope-tree.md), [`ENCRYPTION_REQUIREMENTS.md`](../architecture/ENCRYPTION_REQUIREMENTS.md) | Algorithms and key management — remains under **`D-35`**, owner 04 / 38 |

**New in Section 04:** revocation timing and break-glass ([ADR 0021](./0021-revocation-and-break-glass.md)).

**`D-02` remains deferred and untouched**, per James's instruction. ADR 0016 constrains the
eventual choice through the criteria in
[`ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) §5 — **`C-1`–`C-11`,
which is the single authoritative list** *(corrected 2026-08-13, N-5)*, of which **`C-1`, `C-2`,
`C-5`, `C-6` are the approved disqualifying criteria** (`S4-P4`) — but selects nothing.

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
| D-09 | Authentication provider and identity model *(model resolved in Section 04; provider still open)* | 04 |
| D-10 | Secrets storage and credential vault technology *(requirements resolved in Section 04)* | 04 |
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
| D-34 | Policy language and authorization engine | Requirements fixed in Section 04 ([`POLICY_ENGINE_REQUIREMENTS.md`](../architecture/POLICY_ENGINE_REQUIREMENTS.md)); a candidate failing `P-1`–`P-5`, `P-10`, or `P-11` is disqualified | `D-01`, `D-02` | 04 |
| D-35 | Encryption model — algorithms and key management | Requirements and key scoping fixed in Section 04 ([ADR 0020](./0020-keys-mirror-the-scope-tree.md)); mechanism depends on storage | `D-02` | 04 / 38 |
| D-37 | Key custody, escrow and recovery mechanics | `E-10` makes key loss equal data loss; recovery must be designed as carefully as authentication recovery | `D-02`, `D-35` | 36 |
| D-38 | Break-glass credential storage mechanism | Bounded and specified ([ADR 0021](./0021-revocation-and-break-glass.md)); the store is a technology choice | `D-10` | 29 |
| D-36 | Small-N aggregation threshold | The re-identification risk is identified; the safe threshold depends on real client counts | `Q-01`, `Q-08` | 22 / 37 |
| D-31 | Sandbox provisioning technology for coding agents | Isolation requirements defined; the technology meeting them is not chosen | Platform choice, `D-04` | 30 |
| D-32 | Notification routing and interruption policy | Depends on real usage patterns and device surfaces | `Q-03`, lived experience | 25 |
| D-33a | Isolation **mechanism selection** *(requirement resolved in 04 — [ADR 0016](./0016-isolation-enforced-below-query-layer.md))* | The requirement and the authoritative criteria [`C-1`–`C-11`](../architecture/ISOLATION_ENFORCEMENT.md) (§5) are fixed, and **the approved disqualifying set is `C-1`, `C-2`, `C-5`, `C-6`** — the remaining criteria are evaluated and recorded but do not auto-reject (`S4-P4`, James 2026-08-13); the mechanism family and product are chosen with `D-02` | `D-02`, expected client volume | **29** |

---

## Section 04 — Decisions Raised by Review and DECIDED by James, 2026-08-13

*Raised by the final pre-approval hostile reviews. Each was a decision Section 04 reached and
could not make. **All four were decided by James on 2026-08-13.** Deciding them does not approve
Section 04 — ADRs `0016`–`0022` remain **Proposed**.*

**These are `S4-P*` identifiers, deliberately not `D-*`.** They assigned no ownership to any
section, and closing them assigned none.

| # | Decision | Class | James's decision, 2026-08-13 | Where implemented | Status |
| --- | --- | --- | --- | --- | --- |
| `S4-P1` | How broad may an audit writer's *write* capability be? | Security posture (C3) | **OPTION A — scope-bound.** A writer appends only within the scope it is executing in; **no blanket cross-scope audit writer exists.** *(What authorizes that capability was settled later by `S4-P6`.)* The permissive alternative — permanent, irreversible forged-audit injection across every scope — was **rejected**. Security takes priority over the `I-18`-path cost | [`../architecture/ENCRYPTION_REQUIREMENTS.md`](../architecture/ENCRYPTION_REQUIREMENTS.md) §3.2 (`E-12a`–`E-12c`); `I-88` | **DECIDED** |
| `S4-P2` | Who reads audit, and does Observability own audit records? | Architecture + C3 amendment | **OPTION D — James reads directly, per scope.** No centralized audit reader; **no new reader component**. Observability may collect and route audit events but does **not** own or read the corpus. `MASTER_ARCHITECTURE.md` §5 amended accordingly, marked **PROPOSED** | [`../architecture/ENCRYPTION_REQUIREMENTS.md`](../architecture/ENCRYPTION_REQUIREMENTS.md) §3.2; `I-89`; `MASTER_ARCHITECTURE.md` §5 footnote ² | **DECIDED** |
| `S4-P3` | By what authority does Section 04 amend accepted documents? | Governance (C3) | **CREATE ADR 0022** — a single ADR enumerating every affected Active/Accepted document individually. ADR 0008 and the `INVARIANTS.md` C3 rule are **not** loosened. `DATA_ARCHITECTURE.md` explicitly **out of scope** | [ADR 0022](./0022-section-04-amendments-to-accepted-architecture.md) | **DECIDED — ADR 0022 Proposed** |
| `S4-P4` | Which storage criteria disqualify a candidate? | Architecture (C3), shapes `D-02` | **KEEP THE ORIGINAL FOUR** — `C-1`, `C-2`, `C-5`, `C-6`. `C-3`, `C-4`, `C-8`, `C-9`, `C-10`, `C-11` are **not ratified**; their reasoning is retained marked PROPOSED. `C-9` not promoted (depends on unresolved Section 04 material); `C-11` not elevated (overlaps `C-2`) | [`../architecture/ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) §5; [ADR 0016](./0016-isolation-enforced-below-query-layer.md) | **DECIDED** |

### Raised by the fourth review and decided 2026-08-13

| # | Decision | Class | James's decision | Where implemented | Status |
| --- | --- | --- | --- | --- | --- |
| `S4-P5` | **Audit-write capability bootstrap.** `E-12b` as written was circular: emitting required a release, the release was an authorization decision, `I-18` required that decision to produce a record, and emitting that record required a release | Security posture (C3) | **OPTIONS C + D.** Capability is acquired **once per execution** for that execution's single scope (C), and the release decision's own audit record is **the first record written under the capability that release grants** (D) — a bounded base case of depth one. **`I-18` is not weakened or exempted. No second authorization authority. No blanket cross-scope capability. `I-82` is not the governing mechanism** | [`../architecture/ENCRYPTION_REQUIREMENTS.md`](../architecture/ENCRYPTION_REQUIREMENTS.md) §3.2 (`E-12a`–`E-12d`); `I-88` | **DECIDED** |
| `H-1` | Should James's audit read require step-up? | Security posture (C3) | **OPTION 3.** Step-up for **cross-scope** audit review only; single-scope audit reading proceeds at normal session strength | `I-67`; [`../architecture/AUTHENTICATION_MODEL.md`](../architecture/AUTHENTICATION_MODEL.md) `A-3a` | **DECIDED** |
| `H-2` | How to represent the compromised audit reader | Threat-model completeness | **No `T-27`.** Extend `T-20` with `T-20a`, and point `T-26` at it — Option D leaves no reader component to model separately | [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) `T-20a`, `T-26` | **DECIDED** |

### Raised by the final red-team audit and decided 2026-08-13

| # | Decision | Class | James's decision | Where implemented | Status |
| --- | --- | --- | --- | --- | --- |
| `S4-P6` | **What authorizes audit-write capability?** `S4-P5` (C+D) left the release as an authorization decision routed through the PDP, but the ADR 0014 sequence requires a grant at step 5 and `I-14` denies without one. **No such grant was ever defined**, so an implementer would have had to invent one — or emit no audit at all | Security posture (C3) | **OPTION A — authorized by construction.** An execution that has been authorized, and whose scope binding is therefore established, may write audit records for **that scope only**, for **that execution's lifetime only**. That authorization *is* the capability. **No separate release decision, no new grant class, no second authorization authority, no exemption from `I-18`, no cross-scope capability** | [`../architecture/ENCRYPTION_REQUIREMENTS.md`](../architecture/ENCRYPTION_REQUIREMENTS.md) §3.2 (`E-12a`–`E-12c`; `E-12d` superseded); `I-88` | **DECIDED** |
| `M-A` | `T-24` asserted cross-client containment against a compromised Data access PEP in the present tense, though it depends on `I-60`–`I-63` — `[PHYS]` and unbuilt | Overclaim correction | **Qualify it.** The containment holds **only once `D-33` is implemented and verified**; until then a compromised Data access PEP is a cross-client exposure | [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) `T-24` | **DECIDED** |

**`S4-P6` supersedes the `D` half of `S4-P5`.** Option D defined a depth-one bootstrap base case to
terminate the recursion. Option A removes the release decision, so **there is no recursion to
terminate**. `E-12d` is marked superseded rather than deleted, and the bootstrap-failure residual is
**retired rather than mitigated** — the window no longer exists. The `C` half (execution-scoped
rather than per-emission) stands.

**One honest consequence:** there is no longer a separate "capability released for scope X" audit
event, because no such event occurs. The scope is already named in the execution's own
authorization record, so no information is lost — but it is one fewer discrete event than the
superseded design would have produced.

### `S4-P7`–`S4-P9` — the complete audit-writer surface, decided 2026-08-13

| # | Decision | James's decision | Where implemented | Status |
| --- | --- | --- | --- | --- |
| `S4-P7`/`S4-P8` | Who writes every audit record? The inventory found **58 event classes**, only 20 defined | Enumerate first, then decide — see below | [ADR 0023](./0023-audit-record-writer-authority.md) | **CLOSED** |
| `S4-P9` D1 | Control-plane audit partition | **OUTSIDE the client scope tree.** Not a scope kind, not governed by `I-06`/ADR 0015. Holds no client records — so `S4-P1` holds **by construction** | `I-92`, `E-12f` | **DECIDED** |
| `S4-P9` D2 | Cross-scope denial recording | Actor's scope gets the denial; target's partition gets nothing naming the actor; security event to the control plane. **`I-49` needs no amendment** — `CROSS_SCOPE_DATA_RULES.md` §6 decomposition already means "per scope touched" never requires sibling identity to cross, and a denial is not an access | `I-91`, `E-12e` | **DECIDED — accepted invariant untouched** |
| `S4-P9` D3 | Approvals | **Control-plane events.** An approval precedes the execution it permits; the later execution record stays execution-scoped and the two link by reference without giving the control plane client-data access | `I-92`, EVENT_AND_OBS §5.1 | **DECIDED** |
| `S4-P9` D4 | Audit-write failure | **Fail closed for access, proceed for restriction.** Decisions deny; executions do not start; control-plane operations do not proceed; scopes do not activate. **Emergency stop proceeds** — refusing to stop fails *open*. Break-glass proceeds only with an out-of-band record (`B-7` reasoning). No recursion, no fallback writer, no "best effort" `I-18` | `I-93`, `E-14` | **DECIDED** |

**Deciding `S4-P1`–`S4-P9`, `H-1`, `H-2` and `M-A` does not approve Section 04.** ADRs `0016`–`0022`
are all still **Proposed**, and Section 04 remains **PROPOSED / UNDER REVIEW**.

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
