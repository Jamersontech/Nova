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

**Changing an accepted decision requires a superseding ADR**, not an edit to the original.
A superseded record keeps its text and is marked `Superseded` with a pointer forward.

Decisions that were consciously postponed are tracked separately in
[`DEFERRED_DECISIONS.md`](./DEFERRED_DECISIONS.md).
