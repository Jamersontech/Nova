# 0045 — The Data Access PEP Decision Sequence for Reads

**Status:** **Accepted** — 2026-08-16
**Proposed:** 2026-08-15 — substrate work under ADR 0044
**Section:** 29 (narrowed)
**Resolves:** the one question blocking the application seam — *which of the ten authorization
steps apply to a data access that involves no tool?*

**Accepted 2026-08-16**, after the correction recorded below. The sequence is implemented as
`PolicyDecisionPoint.authorize_data_read` and exercised by the seam suite against real
PostgreSQL, including the fail-closed case. Accepting this is cheap to reverse: it is one method
behind one seam, and its callers do not change if the reading does.

## Decision

**A data read runs the ten-step sequence with the tool-specific steps inapplicable by their own
wording — not skipped, not faked.** Concretely:

| Step | Applies to a read? | Why |
| --- | --- | --- |
| 1 Token validity (`I-87`) | **Yes** | Unconditional |
| 2 Subject known (`I-66`) | **Yes** | Unconditional |
| 3 Scope containment (`I-03`) | **Yes** | The resource's owning scope must be covered |
| 3a Execution binding (`I-114`) | **No — by `I-114`'s own text** | `I-114` scopes itself to *"consequence-producing tool actions"*. A read produces no side effect and has no tool, no provider, no credential binding. Inventing a fake binding to satisfy the signature would misapply the invariant, not honour it |
| 4 Explicit denial (`I-15`) | **Yes** | Deny overrides any grant |
| 5 Grant (`I-14`) | **Yes** | Absence of a grant is a denial |
| 6 Risk ceiling (`I-101`) | **No — unsatisfiable for a read** | A read is class `READ`, the **lowest** class, so every valid ceiling admits it. The step is stated as inapplicable rather than performed vacuously: a comparison that cannot fail reads as a control while being none *(corrected 2026-08-16 — see below)* |
| 7 Classification egress | **No** | Nothing is transmitted outside NOVA: a read moves data from NOVA's own datastore to NOVA's own renderer. Same reason as step 8 *(corrected 2026-08-16)* |
| 8 Argument envelope (`I-100`) | **No** | There are no consequence-determining arguments; the "argument" is the scope, checked at step 3 |
| 9 Approval (`I-09`, `I-40`) | **Not for `READ`** | `PERMISSION_ARCHITECTURE.md` §5: READ–PREPARE is autonomous |
| 10 Allow + record | **Yes** | Every outcome recorded (`W-2`, `I-93`) |

### Correction, 2026-08-16

The table above originally carried **one row labelled "6–7 Risk ceiling (`I-101`)", answered
"Yes, trivially"**. That was wrong in two ways, found while auditing this ADR against the
implementation it describes:

1. **It conflated two different steps.** Step 6 is the risk ceiling; step 7 is classification
   egress. They are not one step and do not share an answer. Step 7 was never considered by the
   implementation at all — the merged row made an unimplemented step look decided.
2. **"Yes, trivially" was honest but misleading, and the code matched it literally.**
   `authorize_data_read` contained `if token.risk_ceiling < Risk.READ`, which is
   **unsatisfiable** — `READ` is the minimum of the risk enum, so the branch could never be
   taken. It read as an enforced ceiling check and was dead code.

**Both are corrected.** The rows are split, each answered on its own reasoning, and the dead
comparison is removed from `slice/core/policy.py` in favour of a stated inapplicability. No
behaviour changed: the branch never executed.

**A gap this exposes, recorded rather than fixed.** Step 7 is inapplicable *today* because no
egress path exists. When one does, the step needs a **classification to reason about**, and the
`item` table carries no classification column. That is not a contradiction of this ADR or of
ADR 0044 — it is the work step 7 will require, named here so it is not discovered late.

**One decision authority, not two.** The sequence is implemented as a method on the existing
`PolicyDecisionPoint`, not as a second engine — `I-77` says the Data Access PEP *"asks the PDP"*,
and a parallel decision engine would be the divergence risk the single-PDP architecture exists to
prevent.

**Isolation is still not authorization.** The Data-Access Boundary and RLS bound *reachability*
independently of this decision (`I-62`, `I-77`); an allow here reaches nothing outside the token's
scope, and a compromised PDP still cannot cross scopes.

## Why this is an interpretation, not new architecture

`AUTHORIZATION_MODEL.md` requires the Data Access PEP to run *"steps 1–10 in full"*, and `I-114`
scopes its own step to tool actions. Read together, "in full" means *every applicable step* — the
alternative reading would require a read to present a tool binding that `I-114` itself says only
tool actions have. This ADR records that reading so it cannot be re-litigated silently; it amends
no invariant and no accepted document.

**Reversibility:** the entire decision is one method behind one seam. If James rejects this
reading, the method changes and its callers do not.

## What Would Change This

Writes. A data **write** of consequence re-opens the argument-envelope and approval steps, and is
deliberately not decided here — the seam is read-only until then.
