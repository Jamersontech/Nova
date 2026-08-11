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

No ADRs have been recorded yet. Section 01 established governing principles rather than
architectural choices; the first ADRs are expected in Section 02.

Decisions that were consciously postponed are tracked separately in
[`DEFERRED_DECISIONS.md`](./DEFERRED_DECISIONS.md).
