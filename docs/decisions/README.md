# Architecture Decision Records (ADRs)

**Status:** Active — established in Section 01.
**Purpose:** Record significant architectural decisions so that future sessions — human
or AI — do not repeatedly reconsider resolved questions, and can understand *why* NOVA is
the way it is rather than only *what* it is.

---

## When to Record a Decision

Record a decision when it:

- commits NOVA to a technology, provider, or platform
- defines or changes a boundary between separated concerns
- affects the domain model, permissions, isolation, credentials, or approvals
- changes an agent's authority or context scope
- would be expensive or disruptive to reverse
- was debated, and the reasoning would otherwise be lost

Do not record routine implementation choices. An ADR is for decisions someone might
otherwise re-litigate.

---

## Required Fields

Every ADR contains:

```text
Decision
Context
Problem
Options Considered
Decision Made
Reason
Tradeoffs
Consequences
Date
Status
```

**Status** is one of: `Proposed`, `Accepted`, `Deferred`, `Superseded`, `Rejected`.

A superseded ADR is **not** deleted or edited into agreement with the new decision. It is
marked `Superseded` with a pointer to the ADR that replaced it. The history of reversals
is itself information.

---

## File Naming

```text
docs/decisions/NNNN-short-kebab-case-title.md
```

`NNNN` is a zero-padded sequential number starting at `0001`. Numbers are never reused.

---

## Authority

James approves decisions. An AI agent may draft an ADR with status `Proposed`; it may not
mark one `Accepted`.

---

## Current Records

| # | Decision | Status | Accepted |
| --- | --- | --- | --- |
| [0001](./0001-layered-architecture-with-policy-spine.md) | Layered architecture with a policy spine | **Accepted** | 2026-08-12 |
| [0002](./0002-unified-scope-tree.md) | One unified scope tree for all domains | **Accepted** *(clarified)* | 2026-08-12 |
| [0003](./0003-context-token-and-brokered-credentials.md) | Context tokens and brokered credentials | **Accepted** | 2026-08-12 |
| [0004](./0004-orchestrator-decomposition.md) | Decompose the orchestrator | **Accepted** | 2026-08-12 |
| [0005](./0005-external-coding-agent-isolation.md) | External coding agents are untrusted | **Accepted** *(clarified)* | 2026-08-12 |
| [0006](./0006-risk-classified-approvals.md) | Risk-classified actions drive approval | **Accepted** | 2026-08-12 |
| [0007](./0007-model-gateway-provider-neutrality.md) | Model gateway as the only provider-aware component | **Accepted** | 2026-08-12 |
| [0008](./0008-architectural-governance-model.md) | Five-class architectural governance model | **Accepted** | 2026-08-12 |

**All eight were accepted by James on 2026-08-12**, following review. The Section 02
architecture is therefore **Active**, not proposed.

**Two clarifications were recorded at acceptance.** Both are recorded as amendments within
their ADRs rather than as new records, because neither changed a core decision:

- **0002** — the unified scope tree remains the canonical isolation model, **and** the
  architecture must support explicitly authorized shared resources without duplicating
  client data or weakening client isolation.
- **0005** — NOVA should eventually generate precise Work Orders from high-level requests.
  The security boundary is unchanged.

### Section 03

| # | Decision | Status | Accepted |
| --- | --- | --- | --- |
| [0009](./0009-credentials-are-references.md) | Credentials are references, never data | **Accepted** *(amended)* | 2026-08-12 |
| [0010](./0010-derived-data-inheritance.md) | Derived data inherits the strictest source | **Accepted** | 2026-08-12 |
| [0011](./0011-provenance-trust-epistemic-separation.md) | Provenance, trust, and epistemic status are three axes | **Accepted** | 2026-08-12 |
| [0012](./0012-data-classification-model.md) | Six-level data classification | **Accepted** | 2026-08-12 |
| [0013](./0013-deletion-and-forgetting.md) | Deletion cascades through lineage, leaving tombstones | **Accepted** *(amended)* | 2026-08-12 |
| [0014](./0014-authorization-decision-model.md) | Ordered authorization decision, fail-closed | **Accepted** | 2026-08-12 |
| [0015](./0015-extensible-scope-kinds.md) | Scope kinds are extensible; the scope contract is not | **Accepted** *(amended)* | 2026-08-12 |

**All seven were accepted by James on 2026-08-12, as amended in commit `0917de5`** following
an adversarial review that produced nine amendments. Section 03's architecture is therefore
**Active**.

None reverses a Section 02 decision. `0009` elaborates ADR 0003, `0010` generalizes the
Section 02 aggregation finding, and `0015` extends ADR 0002 without altering the tree.

**James explicitly accepted the documented residual risks rather than treating them as
resolved** — recorded in [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md)
§3.2. Acceptance is not closure.

### Section 04 — **Accepted by James 2026-08-13**

| # | Decision | Status |
| --- | --- | --- |
| [0016](./0016-isolation-enforced-below-query-layer.md) | Isolation is enforced below the query layer | **Accepted** |
| [0017](./0017-isolation-independent-of-pdp.md) | Isolation enforcement is independent of the PDP | **Accepted** |
| [0018](./0018-authentication-model.md) | Multi-factor, phishing-resistant authentication with step-up | **Accepted** |
| [0019](./0019-secrets-store-separation.md) | Secrets storage is separate, broker-only, per-scope isolated | **Accepted** |
| [0020](./0020-keys-mirror-the-scope-tree.md) | Encryption keys mirror the scope tree | **Accepted** |
| [0021](./0021-revocation-and-break-glass.md) | Revocation at next decision; break-glass is bounded | **Accepted** |
| [0022](./0022-section-04-amendments-to-accepted-architecture.md) | Section 04 amendments to accepted architecture — authorizes the nine documented amendments | **Accepted** |
| [0023](./0023-audit-record-writer-authority.md) | Audit record writer authority; control-plane audit partition; audit-write failure behaviour. **Also authorizes the `DATA_ARCHITECTURE.md` and `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` amendments that ADR 0022 does not cover** | **Accepted** |

### Amendment-authority audit — Section 04 edits to Active/Accepted documents

*Built 2026-08-13 (R-3, R-8). The previous note was self-inconsistent — it named three documents
while saying "both edits" — and it accounted for **five** amendments. A full enumeration of the
working tree finds **thirteen** Active/Accepted documents modified by Section 04. All thirteen are
audited here. **Nothing in this table is marked approved unless that approval exists in the
repository.***

**No ADR is amended, added, or accepted by this audit. It records state; it grants nothing.**

| # | Document | Section / status | What Section 04 changes | Authorizing ADR | Does that ADR explicitly authorize it? | James approval | Amendment status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | [`../architecture/MASTER_ARCHITECTURE.md`](../architecture/MASTER_ARCHITECTURE.md) §5 | 02 · Active | Data-Access Boundary row added; Observability row narrowed (`S4-P2`) | `0017` + **`0022`** §1 | **Yes** | **Given 2026-08-13** (to make the amendment; the ADR itself is not accepted) | **Proposed**, marked in place |
| 2 | [`../architecture/SYSTEM_LAYERS.md`](../architecture/SYSTEM_LAYERS.md) | 02 · Active | Boundary paragraph at the Knowledge & Data entrance; per-data-access note on point 5 | `0017` + **`0022`** §2 | **Yes** | **Given 2026-08-13** | **Proposed**, marked in place |
| 3 | [`../architecture/SECURITY_BOUNDARIES.md`](../architecture/SECURITY_BOUNDARIES.md) §4 | 02 · Active | Adds Context service + Data-Access Boundary to the TRUSTED zone | **`0022`** §3 | **Yes** | Authorized via ADR 0022 *(Proposed)* | **Proposed** |
| 4 | [`../ai/AI_TERMINOLOGY.md`](../ai/AI_TERMINOLOGY.md) | 01 · Active | Section 04 term block; independence qualification; Data-Access Boundary; Context Token Integrity; Scope Binding; Break-Glass correction | **`0022`** §4 | **Yes** | Authorized via ADR 0022 *(Proposed)* | **Proposed** |
| 5 | [`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md) | 03 · Active | Adds `I-60`–`I-88`; `[PHYS]` dependency rows; `I-61`/`I-78`/`I-83` amendments | **`0022`** §5 | **Yes** | Authorized via ADR 0022 *(Proposed)* | **Proposed** |
| 6 | [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) | 03 · Active | `T-19` rewrite; `T-23a/b/c`; `T-20`–`T-22`; `T-24`, `T-25` | **`0022`** §6 | **Yes** | Authorized via ADR 0022 *(Proposed)* | **Proposed** |
| 7 | [`../architecture/AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md) §7 | 03 · Active | Independence qualification; Data Access PEP preservation | **`0022`** §7 | **Yes** | Authorized via ADR 0022 *(Proposed)* | **Proposed** |
| 8 | [`../architecture/PERMISSION_ARCHITECTURE.md`](../architecture/PERMISSION_ARCHITECTURE.md) §2 | 02 · Active | Five-PEPs-remain note; token-integrity requirement at each point | **`0022`** §8 | **Yes** | Authorized via ADR 0022 *(Proposed)* | **Proposed** |
| 9 | [`../architecture/RELIABILITY_ARCHITECTURE.md`](../architecture/RELIABILITY_ARCHITECTURE.md) | 02 · Active | Retries carry no injected credentials (`I-81`) | **`0022`** §9 | **Yes** | Authorized via ADR 0022 *(Proposed)* | **Proposed** |
| 9a | [`../architecture/DATA_ARCHITECTURE.md`](../architecture/DATA_ARCHITECTURE.md) §4 | 02 · Active | Audit Record row — three writer authorities replace "Written by executions" | **`0023`** | **Yes** | Authorized via ADR 0023 *(Proposed)* | **Proposed** |
| 9b | [`../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §5.1 | 03 · Active | Writer-authority mapping for the thirteen audit categories | **`0023`** | **Yes** | Authorized via ADR 0023 *(Proposed)* | **Proposed** |
| 10 | [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) | 02 · Active | Section 04 risk rows; `[PHYS]` inventory; invariant count | — | **Not required** — the document's own header says "Extended in Sections 03 and 04"; extension is its stated purpose | n/a | Extension, not amendment |
| 11 | [`../ROADMAP.md`](../ROADMAP.md) | 01 · Active | Section 04 status; invariant range; governance notes | — | **Not required** — recording section status is this document's purpose | n/a | Status record |
| 12 | [`./DEFERRED_DECISIONS.md`](./DEFERRED_DECISIONS.md) | 01 · Active | M-7 correction; `D-33a`/`D-37`/`D-38`; criteria references | — | **Not required** — maintaining the register is its purpose | `D-33a`/`D-37`/`D-38` ownership **approved 2026-08-13** | Register update |
| 13 | `README.md` *(this file)* | 01 · Active | Section 04 ADR index; this audit | — | **Not required** — indexing ADRs is its purpose | n/a | Index update |

#### The authority gaps — closed by ADR 0022

*Updated 2026-08-13. James decided `S4-P3`: **create a single ADR enumerating every affected
document.*** [ADR 0022](./0022-section-04-amendments-to-accepted-architecture.md) now supplies the
authority for rows 1–9 above, enumerating each individually with its reason, its relationship to
`0016`–`0021`, and its removal condition.

Two rules were deliberately **not** loosened in doing so:

> [`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md), line 10 — *"Any change to
> this file is a C3 architectural change **requiring an ADR**."*
> [ADR 0008](./0008-architectural-governance-model.md) — C3 changes are James's alone.

**ADR 0022 satisfies both rather than amending either.** *(Status corrected 2026-08-14: this
paragraph described ADR 0022 as Proposed, which was accurate when written on 2026-08-13 and stale
from the moment James accepted `0016`–`0023` later that day.)* **ADR 0022 is Accepted**, so rows
1–9 are accepted architecture and the removal condition below did not fire. The condition is
retained as the record of what would have happened: had ADR 0022 been rejected, every amendment
would have been removed and the accepted text restored verbatim. `0016`–`0021` could not have
been accepted without also deciding `0022`, and were not.

**`DATA_ARCHITECTURE.md` is now amended — under ADR 0023, not ADR 0022.** *(2026-08-13, `S4-P9`.)*
Its Audit Record row was the accepted statement that audit records are "Written by executions", which
the `S4-P8` inventory showed leaves 36 mandatory event classes unwritable.
[ADR 0023](./0023-audit-record-writer-authority.md) supplies that authority **separately and
visibly** rather than silently broadening ADR 0022's scope, which James had explicitly bounded.
`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` §5.1 is authorized the same way.

**Its relational partitioning wording remains out of scope and unedited** — that is a separate matter
from the writer question and no ADR authorizes it.

Otherwise none reverses an accepted decision. `0016` resolves `D-33` as a **requirement without
selecting a technology**; `0017` partially mitigates the `T-19` residual risk James accepted;
`0018`–`0021` resolve the design halves of `D-09`, `D-10`, `D-34` and `D-35`, leaving every
product choice deferred. **`D-02` was not touched.**

**Changing an accepted decision requires a superseding ADR**, not an edit to the original.
A superseded record keeps its text and is marked `Superseded` with a pointer forward.

### Section 05 — **Accepted by James 2026-08-14**

| # | Decision | Status |
| --- | --- | --- |
| [0024](./0024-model-gateway-is-an-enforcement-point.md) | Model egress is the **sixth** Policy Enforcement Point; one scope per request; data policy constrains the candidate provider set, including on fallback | **Accepted** |
| [0025](./0025-model-output-is-an-untrusted-derivation.md) | Model output is a derivation carrying its inputs' provenance whether or not it is stored; **tool arguments are authorized, not merely validated**; risk classification is one-way with respect to models | **Accepted** |
| [0026](./0026-model-verification-is-corroboration.md) | A model check never promotes epistemic status, satisfies an approval, or lowers a risk class; independence required above `PREPARE` | **Accepted** |
| [0027](./0027-provider-credentials-are-control-plane-credentials.md) | Provider credentials sit outside the client scope tree, leaving `I-23` **unamended** rather than adding an exception to it | **Accepted** |
| [0028](./0028-section-05-amendments-to-accepted-architecture.md) | Section 05 amendments to accepted architecture — authorizes all thirteen | **Accepted** |

### Amendment-authority audit — Section 05 edits to Active/Accepted documents

**No ADR is amended, added, or accepted by this audit. It records state; it grants nothing.**
Every row is authorized by [ADR 0028](./0028-section-05-amendments-to-accepted-architecture.md),
which enumerates each individually with its reason. **All thirteen were accepted with ADRs
`0024`–`0028` on 2026-08-14, and their in-place Proposed markings were cleared at acceptance** —
the step Section 04's acceptance omitted, which is why eighteen stale markings still sit in
Section 04 material (recorded as outstanding in [`../ROADMAP.md`](../ROADMAP.md)).

| # | Document | Section / status | What Section 05 changes |
| --- | --- | --- | --- |
| 1 | [`../architecture/PERMISSION_ARCHITECTURE.md`](../architecture/PERMISSION_ARCHITECTURE.md) §2 | 02 · Active | Sixth enforcement point added to the diagram and text |
| 2 | [`../architecture/MASTER_ARCHITECTURE.md`](../architecture/MASTER_ARCHITECTURE.md) §4, §5 | 02 · Active | Policy arrow from the Model Gateway; gateway row gains egress enforcement and provider-credential custody (footnote ³) |
| 3 | [`../architecture/MODEL_ARCHITECTURE.md`](../architecture/MODEL_ARCHITECTURE.md) §2–§4, §6 | 02 · Active | Where the permission decision is enforced; data policy as a constraint; verification limits; fallback bounded by the permitted set |
| 4 | [`../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md) §2, §5 | 02 · Active | `consequence-determining args` tool field; control-plane credential class |
| 5 | [`../architecture/SECURITY_BOUNDARIES.md`](../architecture/SECURITY_BOUNDARIES.md) §2, §5 | 02 · Active | Model-provider boundary row; Model Gateway assumed-compromise row |
| 6 | [`../architecture/PROVENANCE_AND_TRUST.md`](../architecture/PROVENANCE_AND_TRUST.md) §6 | 03 · Active | Requirement 2 extended to model output whether or not it is stored |
| 7 | [`../architecture/CROSS_SCOPE_DATA_RULES.md`](../architecture/CROSS_SCOPE_DATA_RULES.md) §2 | 03 · Active | The model request named as a cross-scope join point |
| 8 | [`../architecture/RELIABILITY_ARCHITECTURE.md`](../architecture/RELIABILITY_ARCHITECTURE.md) §4 | 02 · Active | Model-call retry semantics |
| 9 | [`../architecture/SCALE_AND_COST_ARCHITECTURE.md`](../architecture/SCALE_AND_COST_ARCHITECTURE.md) §4 | 02 · Active | Cost ceilings terminate rather than degrade; fail closed above `PREPARE` |
| 10 | [`../architecture/SYSTEM_LAYERS.md`](../architecture/SYSTEM_LAYERS.md) §5 | 02 · Active | Sixth boundary enforcement point |
| 11 | [`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md) | 03 · Active | `I-94`–`I-105` added; `I-96` `[PHYS]` dependency row. **`I-01`–`I-93` unmodified** |
| 12 | [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) | 03 · Active | `T-28`–`T-32`; three rows added to §3. **No row added to §2** |
| 13 | [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) §3.5 | 03 · Active | Eight Section 05 residual risks; `[PHYS]` inventory updated |

**Registers and status records, not amendments:** `ROADMAP.md` (Section 05 status),
`DEFERRED_DECISIONS.md` (`D-08`, `D-20`, `D-39`, `D-40`), `architecture/README.md` and this file
(indexes). Maintaining these is their purpose.

**Two stale status markings were corrected, not rewritten** *(2026-08-14)*: `INVARIANTS.md`
described `I-60`–`I-93` as PROPOSED pending ADRs `0016`–`0023`, and this file described ADR 0022
as Proposed. Both were accurate on 2026-08-13 and stale once James accepted those ADRs later that
day. **No Section 04 architecture was changed** — only the sentences describing its status.

---

### Section 06 — **Accepted by James 2026-08-14**

| # | Decision | Status |
| --- | --- | --- |
| [0029](./0029-delegated-authority.md) | Delegated authority is verified at issuance by the sole issuer, structurally bounded (strict narrowing, no ancestry cycles, explicit re-delegation), budgeted per delegation tree, and cannot outlive its granting execution identity | **Accepted** |
| [0030](./0030-agent-governance-and-approval-binding.md) | Agent lifecycle operations classified under the **existing** C1/C2/C3 model; an approval binds nine effective-authorization properties | **Accepted** |
| [0031](./0031-section-06-amendments-to-accepted-architecture.md) | Section 06 amendments to accepted architecture — authorizes all thirteen | **Accepted** |

### Amendment-authority audit — Section 06 edits to Active/Accepted documents

**No ADR is amended, added, or accepted by this audit. It records state; it grants nothing.**
All thirteen are authorized by
[ADR 0031](./0031-section-06-amendments-to-accepted-architecture.md) and were **accepted with ADRs
`0029`–`0031` on 2026-08-14; their in-place Proposed markings were cleared at acceptance** — the
step Section 04's acceptance omitted, which is why eighteen stale markings still sit in Section 04
material (recorded as outstanding in [`../ROADMAP.md`](../ROADMAP.md)). **Three are corrections of accepted text that is wrong**, not additions — rows 1,
3 and 10 — and are flagged as such because a correction deserves more scrutiny than an addition.

| # | Document | Section / status | What Section 06 changes |
| --- | --- | --- | --- |
| 1 | [`../architecture/AGENT_ARCHITECTURE.md`](../architecture/AGENT_ARCHITECTURE.md) §2, §3 | 02 · Active | **CORRECTION** — "the runtime cannot *issue* a token" is impossible under `I-87`; the runtime requests, Context issues. Child lifetime; no suspended state |
| 2 | [`../ai/AGENT_PRINCIPLES.md`](../ai/AGENT_PRINCIPLES.md) §4 | 01 · Active | The "enforced by design" claim qualified per prohibition; prohibition 6 recorded as unenforced |
| 3 | [`../architecture/SCOPE_AND_IDENTITY_MODEL.md`](../architecture/SCOPE_AND_IDENTITY_MODEL.md) §5 | 03 · Active | **CORRECTION** — `may_redelegate` and `ancestry` added; §5's re-delegation rule tested a field the record lacked. Four bounding rules |
| 4 | [`../architecture/IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md) §5 | 02 · Active | Agent lifecycle governance rows. **No new change class** |
| 5 | [`../architecture/CONTEXT_ARCHITECTURE.md`](../architecture/CONTEXT_ARCHITECTURE.md) §2, §5 | 02 · Active | Issuance verification; conflict row |
| 6 | [`../architecture/AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md) §3 | 03 · Active | Note on where `I-07` is enforced. **The ten steps are unchanged** |
| 7 | [`../architecture/PERMISSION_ARCHITECTURE.md`](../architecture/PERMISSION_ARCHITECTURE.md) §5 | 02 · Active | The nine-property approval binding |
| 8 | [`../architecture/SCALE_AND_COST_ARCHITECTURE.md`](../architecture/SCALE_AND_COST_ARCHITECTURE.md) §4 | 02 · Active | Ceiling belongs to the root execution |
| 9 | [`../architecture/MODEL_GATEWAY_ARCHITECTURE.md`](../architecture/MODEL_GATEWAY_ARCHITECTURE.md) §7 | **05 · Active** | `MG-18a` — same. Amends Section 05 material accepted the same day, because Section 05 shipped the gap |
| 10 | [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) | 03 · Active | **CORRECTION** — `T-24`'s Agent-Runtime row was circular. `T-33`, `T-34` added |
| 11 | [`../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §5.1 | 03 · Active | Agent-definition lifecycle and delegation categories. **No new audit authority** |
| 12 | [`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md) | 03 · Active | `I-106`–`I-109`. **`I-01`–`I-105` unmodified** |
| 13 | [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) §3.6 | 03 · Active | Six Section 06 residual risks |

**Registers and status records, not amendments:** `ROADMAP.md`, `docs/README.md`,
`DEFERRED_DECISIONS.md` (`D-25a`), `architecture/README.md` and this file.

---

### Section 07 — Proposed, awaiting James

| # | Decision | Status |
| --- | --- | --- |
| [0032](./0032-trust-promotion-authority.md) | **Trust promotion authority** — raising trust is an explicitly authorized, recorded, C3 operation; never automatic, never by an agent, never model-mediated. `system.verified` requires an authoritative source, and the term is defined | Proposed |
| [0033](./0033-section-07-amendments-to-accepted-architecture.md) | `model.generated` quarantined; delegate memory carries ancestry and survival is not authority; union provenance survives persistence; revoked creating authority surfaced at retrieval. Authorizes all eight amendments | Proposed |

### Amendment-authority audit — Section 07 edits to Active/Accepted documents

**No ADR is amended, added, or accepted by this audit. It records state; it grants nothing.**
All eight are authorized by
[ADR 0033](./0033-section-07-amendments-to-accepted-architecture.md), are **Proposed**, and are
marked in place.

| # | Document | Section / status | What Section 07 changes |
| --- | --- | --- | --- |
| 1 | [`../architecture/MEMORY_MODEL.md`](../architecture/MEMORY_MODEL.md) §4, §4.1, §4.3 | 03 · Active | `model.generated` quarantined; new §4.3 trust promotion; three retrieval requirements |
| 2 | [`../architecture/PROVENANCE_AND_TRUST.md`](../architecture/PROVENANCE_AND_TRUST.md) §2, §3 | 03 · Active | Trust-change authority; delegation ancestry and persistence in provenance |
| 3 | [`../architecture/MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`](../architecture/MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md) §5, §7 | 02 · Active | Promotion in hygiene; taint restoration in retrieval discipline |
| 4 | [`../architecture/IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md) §5 | 02 · Active | Trust-promotion row. **No new change class** |
| 5 | [`../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §5.1 | 03 · Active | Promotion granted and refused in the Memory category. **No new audit authority** |
| 6 | [`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md) | 03 · Active | `I-110`–`I-111`. **`I-01`–`I-109` unmodified** |
| 7 | [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) | 03 · Active | `T-35`. `T-10`'s residual **not reduced** |
| 8 | [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) §3.7 | 03 · Active | Six Section 07 residual risks |

**Deliberately not amended:** `CONTEXT_ARCHITECTURE.md` — Section 07 found **no context decision to
make**; it already answers every context question raised. `DATA_LIFECYCLE.md` — a trust operation
changes no lifecycle stage.

**Registers and status records, not amendments:** `ROADMAP.md`, `docs/README.md`,
`DEFERRED_DECISIONS.md` (`D-24a`) and this file.

---

### Section 08 — Proposed, awaiting James

| # | Decision | Status |
| --- | --- | --- |
| [0034](./0034-the-plan-is-a-security-object.md) | **The plan is a security object** with declared schema, deterministic identity and immutability after authorization; authorization is an **envelope plus a per-action check**; re-planning creates a new plan | Proposed |
| [0035](./0035-section-08-amendments-to-accepted-architecture.md) | Section 08 amendments — authorizes all seven, and records why `PLANNING_ARCHITECTURE.md` was **not** created | Proposed |
| [0036](./0036-tool-declarations-are-claims-not-facts.md) | **Tool declarations are claims, not facts** — the classification must be **total** over the input schema, and an absent or unparseable claim is read as **consequence-determining**. No new invariant | Proposed |
| [0037](./0037-provider-outcomes-and-provider-initiated-paths.md) | **Provider outcomes are claims; provider-initiated paths carry no authority; and authorization binds the execution binding (`I-114`)** — unknown is distinct from failure, retry needs **provider-enforced** deduplication, an inbound webhook/callback/event has no identity, and a tool action is authorized against the integration/credential binding that produces the consequence, with `I-109` amended in place | Proposed |

### Amendment-authority audit — Section 08 edits to Active/Accepted documents

**No ADR is amended, added, or accepted by this audit. It records state; it grants nothing.**
All seven are authorized by [ADR 0035](./0035-section-08-amendments-to-accepted-architecture.md),
are **Proposed**, and are marked in place.

| # | Document | Section / status | What Section 08 changes |
| --- | --- | --- | --- |
| 1 | [`../architecture/ORCHESTRATION_ARCHITECTURE.md`](../architecture/ORCHESTRATION_ARCHITECTURE.md) §1, §2, §2.1, §2.2, §4 | 02 · Active | Plan object schema, identity, immutability; envelope authorization and composition; re-plan loop; resumption re-check |
| 2 | [`../architecture/PERMISSION_ARCHITECTURE.md`](../architecture/PERMISSION_ARCHITECTURE.md) §5 | 02 · Active | Envelope approval distinguished from action approval. **One-action rule unchanged** |
| 3 | [`../architecture/AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md) §3 | 03 · Active | What the ten steps evaluate and what they do not. **Steps unchanged; PDP not a composition engine** |
| 4 | [`../architecture/RELIABILITY_ARCHITECTURE.md`](../architecture/RELIABILITY_ARCHITECTURE.md) §3, §4 | 02 · Active | Resumption re-checks authorization; plan-level retry semantics |
| 5 | [`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md) | 03 · Active | `I-112`–`I-113`. **`I-01`–`I-111` unmodified** |
| 6 | [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) | 03 · Active | `T-36`. `T-03`, `T-19`, `T-24` residuals **not reduced** |
| 7 | [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) §3.8 | 03 · Active | Six Section 08 residual risks |

**Deliberately not amended:** `EXECUTION_ARCHITECTURE.md` — its *"James approves the plan"* becomes
correct rather than ambiguous once `PERMISSION_ARCHITECTURE.md` §5 defines an envelope approval.

**No new document.** `PLANNING_ARCHITECTURE.md` was considered and rejected — see ADR 0035.

**Registers and status records, not amendments:** `ROADMAP.md`, `docs/README.md` and this file.

---

### Section 09 — Proposed, awaiting James

**No new ADR and no new invariant.** Section 09's single decision — `S9-D1`, **source identity** —
is folded into [ADR 0033](./0033-section-07-amendments-to-accepted-architecture.md) **§2a**, which
already amends `PROVENANCE_AND_TRUST.md` §2 and owns the same decision family. It completes
[ADR 0032](./0032-trust-promotion-authority.md)'s definition of an authoritative source: `I-110`
required a source to be *identifiable* and *reproducibly checkable*, and nothing defined what
identifies one. **`I-110` remains the governing security invariant** and is now implementable.

| Document | Section / status | What Section 09 changes |
| --- | --- | --- |
| [`../architecture/PROVENANCE_AND_TRUST.md`](../architecture/PROVENANCE_AND_TRUST.md) §2.1 | 03 · Active | Defines a **source observation**: identifier · content digest · `retrieved_at` |
| [`../architecture/MEMORY_MODEL.md`](../architecture/MEMORY_MODEL.md) §4.1 | 03 · Active | Revalidation becomes a digest comparison; unreachable source denies promotion |
| [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) §3.9 | 03 · Active | Three Section 09 residuals, two of them recorded rather than resolved |

Both amendments are **Proposed** under ADR 0033 and marked in place.

---

### Section 10 — Proposed, awaiting James

**One ADR, no new invariant, no new document.**
[ADR 0036](./0036-tool-declarations-are-claims-not-facts.md) establishes that a tool definition's
security-relevant fields are **claims made by the tool, not verified facts about it**, and that an
absent, incomplete or unparseable claim is read at its most consequential. `I-100` already requires
consequence-determining arguments to be checked and already refuses to register a tool that does not
declare them; `MT-6` already refuses an incomplete definition. **What was undefined is what makes a
declaration complete**, so the material is a definition and belongs in the document that specifies
the field — the same reasoning that put Section 09's source identity in `PROVENANCE_AND_TRUST.md`.
**`I-100` and `MT-6` remain the governing rules.**

| Document | Section / status | What Section 10 changes |
| --- | --- | --- |
| [`../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md) §2.1 | 02 · Active | Declaration **totality** over the input schema; default inverted to **consequence-determining**; claims-not-facts rule. Also corrects a stale Section 05 status label in §2 |
| [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) | 03 · Active | `T-37` under-declared tool. **`T-16`'s residual is not reduced** |
| [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) §3.10 | 03 · Active | Four Section 10 residuals, one of them deferred to Section 11 |

All are **Proposed** under ADR 0036 and marked in place. **`INVARIANTS.md` is deliberately not
amended** — `I-01`–`I-113` are byte-identical to their accepted text.

---

### Section 11 — Proposed, awaiting James

**One ADR, one new invariant (created on James's explicit 2026-08-15 approval), no new document.**
[ADR 0037](./0037-provider-outcomes-and-provider-initiated-paths.md) resolves `S11-D1`–`S11-D3`.
`S11-D2` and `S11-D3` are answered by invariants that already exist — `I-39`, `I-102` and `I-110`
for what a provider's outcome claim is worth; `AUTHENTICATION_MODEL.md` §2 and `I-14` for what an
inbound provider-initiated signal is worth — applied to paths those documents implied but never
named. `S11-D1` required **`I-114`** and an in-place amendment to `I-109`.

| Document | Section / status | What Section 11 changes |
| --- | --- | --- |
| [`../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md) §3, §3.1, §4.1, §4.2 | 02 · Active | Resolve-then-decide invocation ordering; outcome claims and the three outcomes; integration identity and no-substitution; provider-initiated inbound paths |
| [`../architecture/RELIABILITY_ARCHITECTURE.md`](../architecture/RELIABILITY_ARCHITECTURE.md) §2, §4 | 02 · Active | **Unknown** as a distinct outcome; partial request execution; provider-enforced idempotency; per-attempt binding re-check, envelope-bounded failover |
| [`../architecture/PROVENANCE_AND_TRUST.md`](../architecture/PROVENANCE_AND_TRUST.md) §5 | 03 · Active | A side-effect claim is not the *"fact about the external system"* a fetch is |
| [`../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §2, §5.1 | 03 · Active | An integration-sourced event's `source` is an unauthenticated assertion; External transmission records the execution binding |
| [`../architecture/SECURITY_BOUNDARIES.md`](../architecture/SECURITY_BOUNDARIES.md) §2 | 02 · Active | The external-service row covers provider-**initiated** inbound; the Tool row gains the binding-envelope check |
| [`../architecture/THREAT_MODEL.md`](../architecture/THREAT_MODEL.md) | 03 · Active | `T-38`, `T-39`. **`T-03`'s and `T-16`'s residuals not reduced** |
| [`../architecture/KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) §3.11 | 03 · Active | Section 11 residuals — `S11-D1`'s substitution half closed, its semantic half bounded |

All are **Proposed** under ADR 0037 and marked in place, along with the `S11-D1` additions:
`AUTHORIZATION_MODEL.md` §2–3 (execution binding as an element, resolved before the decision),
`SECRETS_ARCHITECTURE.md` §3 (broker step 2a), `INVARIANTS.md` (**`I-114`** new; **`I-109`**
amended in place), and `THREAT_MODEL.md` `T-39`.

**`S11-D1` was stopped for James and approved on 2026-08-15.** Its resolution is folded into
ADR 0037 (its own § "S11-D1") rather than minted as ADR 0038 — same decision family, same
amendment surface. It adds **`I-114`** (authorization binds the execution binding: resolve before
deciding · envelope-then-check at the tool PEP and broker step 2a · consequence-bearing binding
identity, C3 · no substitution, no provider equivalence, no model selection) and **amends `I-109`
in place**, scoping its exclusion list: model calls keep the per-call `I-94`/`I-97` exclusion; a
consequence-producing tool action binds the execution binding as a tenth property. Both are
Proposed and revert verbatim if ADR 0037 is rejected.

---

Decisions that were consciously postponed are tracked separately in
[`DEFERRED_DECISIONS.md`](./DEFERRED_DECISIONS.md).
