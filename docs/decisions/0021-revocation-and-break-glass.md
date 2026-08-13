# 0021 — Revocation Takes Effect at the Next Decision; Break-Glass Is Bounded

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 04
**Section:** 04

## Decision
Revocation of grants, delegations, sessions, bindings, and tokens takes effect **at the next
authorization decision**; in-flight executions fail closed at their next enforcement point.
A **break-glass** path exists for availability failure only: human-only, loud, time-boxed, on
its own credential path, and **confined to the control plane**. *(Amended 2026-08-12, H-4.)*
**Break-glass must never authorize client-data access and must never bypass the normal
authorization path.** It may restore the ability to authenticate, repair policy infrastructure,
recover control-plane services, and lift an emergency stop. If policy is unavailable, break-glass
may restore NOVA's ability to *perform* authorization; it never replaces it. Protected data
remains fail-closed throughout.

## Context
Section 03 established fail-closed behaviour throughout. Fail-closed systems create a new
problem: what happens when they fail closed and James legitimately needs in.

## Problem
Two gaps. Revocation was specified as a state change without stating when it bites — and
"revoked but the running job finished anyway" is not revocation. And an undefined recovery path
guarantees that an undocumented bypass gets built under pressure, by whoever is on the worst
day of the project.

## Options Considered
**Revocation:** propagate to running executions immediately (complex, requires interrupting
work mid-flight); take effect at next decision (simple, since the PDP is consulted per decision
— a short window where an in-flight step completes); or expire naturally (unacceptable).

**Break-glass:** no path at all (purest, and produces an undocumented one the first time NOVA
is unreachable); an unrestricted admin mode (usable, and becomes the attack path that defeats
everything); or a bounded recovery-only path.

## Decision Made
Next-decision revocation, and a bounded recovery-only break-glass.

## Reason
Because the PDP is consulted per decision rather than per session, "next decision" is already
near-immediate — the elaborate propagation machinery buys very little. For break-glass, the
choice is not whether one exists but whether it is designed or improvised; an undesigned one is
built in an emergency by someone in a hurry.

## Tradeoffs
**Advantages:** revocation needs no propagation infrastructure; in-flight work fails closed
rather than completing; break-glass is loud, time-boxed, and confined to the control plane so it
cannot reach client data.
**Disadvantages:** a brief window where an already-authorized step completes after revocation;
an attacker obtaining break-glass credentials obtains **control-plane recovery access**,
including the ability to repair — and therefore potentially alter — policy infrastructure;
`B-3` loudness depends on a notification path that may itself be degraded during the incident
break-glass exists for; and rotation cannot depend on NOVA being healthy (`B-7`, `L-5`).

## Consequences
**Revocation stops future use; it does not reverse past use** — revoking a credential does not
un-send an email, and NOVA must say so rather than implying otherwise. Break-glass credentials
are stored separately and rotated after every use — by a path that **must not depend on NOVA
being healthy** (`B-7`), since they are used exactly when it is not. Invariants `I-74`–`I-76`.

## What Would Change This
A demonstrated case where next-decision revocation is too slow — long-running executions that
cross many enforcement points would need mid-execution interruption, an extension rather than a
reversal.
