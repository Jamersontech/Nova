# 0045 — The Data Access PEP Decision Sequence for Reads

**Status:** **Proposed**
**Proposed:** 2026-08-15 — substrate work under ADR 0044
**Section:** 29 (narrowed)
**Resolves:** the one question blocking the application seam — *which of the ten authorization
steps apply to a data access that involves no tool?*

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
| 6–7 Risk ceiling (`I-101`) | **Yes, trivially** | A read is class `READ`; the token's ceiling must admit it |
| 8 Argument envelope (`I-100`) | **No** | There are no consequence-determining arguments; the "argument" is the scope, checked at step 3 |
| 9 Approval (`I-09`, `I-40`) | **Not for `READ`** | `PERMISSION_ARCHITECTURE.md` §5: READ–PREPARE is autonomous |
| 10 Allow + record | **Yes** | Every outcome recorded (`W-2`, `I-93`) |

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
