# 0017 — Isolation Enforcement Is Independent of the Policy Decision Point

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 04
**Section:** 04
**Partially mitigates:** `T-19` (compromised PDP)

## Decision
The layer enforcing storage scope isolation must **not** consult the Policy Decision Point.
Scope restriction derives from the execution's bound scope identity, established **by the
Data-Access Boundary inside the TRUSTED zone**, from the Context Token's scope path and
nothing else. Application and agent code cannot set, widen, re-bind, or bypass it. If scope is
missing, ambiguous, invalid, inconsistent, or cannot be established, the channel is not opened
and access is denied.

### This is ADDITIONAL to the Data Access PEP — never a replacement

*Amended 2026-08-12 following adversarial review (H-1).*

> **Structural storage isolation does not replace, weaken, bypass, or reimplement the Data
> Access Policy Enforcement Point. Both exist. Both run. Neither substitutes for the other.**

The Data Access PEP defined under [ADR 0001](./0001-layered-architecture-with-policy-spine.md)
and [ADR 0014](./0014-authorization-decision-model.md) remains in force **unchanged**. Every
data access still asks the PDP, and still passes the full ordered sequence — context validity,
subject, containment, explicit denial, **grants**, **risk ceiling**, **classification**,
**conditions**, and approval.

The required conceptual path *(diagram corrected 2026-08-13, N-2. The previous version omitted
application/agent execution and query construction, placing the PEP immediately below
authentication — which reads as one check per **request**. That is the defect F-1 corrected in
[`ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) §3, and this diagram now
matches it.)*:

```text
Request
  → authentication / identity
  → application / agent execution   ← may be buggy, confused, or hostile
  → query construction              ← may omit the scope predicate
  → DATA ACCESS PEP  ──asks──▶ PDP  ← EVERY access · grants · risk ceiling ·
                                       classification · conditions
  → structural scope isolation      ← applies the scope restriction regardless;
                                       decides nothing, restricts reachability
  → data store
```

**The Data Access PEP is evaluated per data access — not once per request, not once per session,
not once per execution.** This is accepted `SYSTEM_LAYERS.md` §5 point 5 (*"Any layer → Knowledge
& Data: read/write checked against token scope partition"*), and `R-9` and `I-77` restate it. An
execution issuing ten reads is authorized ten times. A design that authorizes once at request
entry and then permits arbitrary subsequent queries beneath that check does **not** satisfy this
ADR.

**The storage isolation layer does not decide whether an action is authorized.** It decides
nothing. It restricts *reachability*. An action the PDP denies must not proceed even though the
storage layer would have permitted it within scope; an action the PDP allows must still fail if
it reaches outside the bound scope.

Reading this ADR as permitting connection-scope binding to serve as the authorization check for
data reads would delete grants, risk ceilings, classification and conditions from the read path
— a security regression wearing the appearance of a security improvement. That reading is
**prohibited**. `I-77`.

### This ADR amends accepted Section 02 architecture

*Added 2026-08-13 (N-3), approved by James as a C3 amendment during the Section 04 review.*

This ADR registers the **Data-Access Boundary** as a named responsibility. Doing so required
editing two documents James already accepted on 2026-08-12:

| Accepted document | What Section 04 adds | Status |
| --- | --- | --- |
| [`MASTER_ARCHITECTURE.md`](../architecture/MASTER_ARCHITECTURE.md) §5 | A row in the NOVA Core responsibility table, with a footnote marking it Proposed | **Proposed**, not accepted |
| [`SYSTEM_LAYERS.md`](../architecture/SYSTEM_LAYERS.md) (Knowledge & Data; §5) | A paragraph placing the boundary at the layer entrance, and a per-data-access note on point 5 | **Proposed**, not accepted |

**Both edits are marked in place as Proposed** so that no reader mistakes them for architecture
accepted on 2026-08-12. They take effect only when James accepts this ADR. If this ADR is
rejected, both edits are removed rather than retained.

**What is being added is a responsibility, not a subsystem.** The Data-Access Boundary is a
trusted platform boundary — not a standalone microservice, not a new speculative subsystem, and
not separately deployable. Section 04 needs the storage scope binding to have a *named owner*
inside the TRUSTED zone (`I-61`, `I-78`, `C-11`); an unowned binding is one application code
ends up setting.

**No new authorization authority is created.** The boundary decides nothing. It never consults
the PDP (`R-7`, `I-62`), never replaces the Data Access PEP (`I-77`), and cannot permit an
access — only fail to open a channel.

## Context
Section 03's adversarial review found `T-19`: a compromised PDP returns `ALLOW` and every
enforcement point obeys. James accepted this as unmitigated residual risk. Section 04 owns the
enforcement mechanism (`D-33`) and can address part of it.

## Problem
The architecture concentrates authorization in one trusted component. Concentration is correct
— scattered authorization is how isolation rots (ADR 0001) — but it creates a single component
whose compromise defeats everything, including client isolation.

## Options Considered
1. **Accept `T-19` as-is.** No new complexity; the most important invariant in NOVA depends on
   one component's integrity.
2. **Independent enforcement layer.** Client isolation survives PDP compromise; requires the
   enforcement layer never to consult policy, which forbids expressing isolation as policy
   rules.
3. **Independent verification of PDP decisions** — quorum, second opinion, attestation.
   Addresses `T-19` more completely; substantial complexity and latency on every decision, and
   the verifier becomes a second trusted component.
4. **Both 2 and 3.** Strongest; option 3's cost is not justified at NOVA's scale today.

## Decision Made
Option 2. Option 3 is explicitly **not** adopted and remains available if `T-19` proves more
serious in practice.

## Reason
The two defenses fail for different reasons: the PDP by defeating one component's logic, the
enforcement layer by subverting the scope-bound channel. Making them independent of each other
means **PDP compromise alone** is not sufficient, and the cost is a constraint on how isolation
is expressed rather than new machinery.

**This is not general independence.** Both derive from the Context Token, so compromise of the
Context service defeats both — see Consequences. The claim is deliberately narrow.

## Tradeoffs
**Advantages:** cross-client isolation survives **PDP** compromise; no added latency; a hostile
query still returns nothing.
**Disadvantages:** isolation cannot be expressed as policy rules, so it cannot be adjusted
without changing infrastructure — a cost that is also a benefit; two enforcement models to
reason about; `D-34` engine selection must not also become the storage enforcement mechanism.

## Consequences
**`T-19` is reduced in blast radius, not resolved.** A compromised PDP can still authorize
destructive, irreversible, and unapproved actions within an execution's own scope, and can
deny legitimate work.

**The independence is bounded, and the boundary is now named.** *(Amended 2026-08-12, H-2.)*
Both the PDP and the scope binding derive from the **Context Token**. They are independent of
*each other* — the enforcement layer never asks the PDP — but they share that upstream root.
**Compromise of the Context service, or of Context Token issuance, defeats both together from a
single point.** The Context service therefore becomes a critical trusted component of the same
standing as the PDP, and **nothing in Section 04 mitigates its compromise** (`T-23a`).

The accurate claim is: cross-client access requires either compromise of both the PDP and the
binding path, **or** compromise of the Context service — not general two-of-two independence.
**No cryptographic unforgeability is claimed**; NOVA has no accepted mechanism for such a claim.
What *is* required, as of the final review (F-3), is that a recipient be able to **detect** a
modified or fabricated Context Token and refuse it (`I-87`,
[`AUTHENTICATION_MODEL.md`](../architecture/AUTHENTICATION_MODEL.md) §6). That is a detection
property on a mechanism that does not yet exist; it narrows who can produce an accepted token and
**changes nothing about the boundary above** — both mechanisms still derive from the same token,
and `T-23a` is unreduced. Independent decision verification remains undesigned. Invariants `I-61`,
`I-62`, `I-78`, `I-79`, `I-87`.

## What Would Change This
Evidence of PDP compromise being more likely or more damaging than assessed, which would make
option 3's cost worth paying — recorded then as a superseding ADR, not an amendment here.
