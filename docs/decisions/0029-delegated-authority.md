# 0029 — Delegated Authority Is Verified at Issuance, Structurally Bounded, and Cannot Outlive Its Source

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 06
**Section:** 06
**Resolves:** `S6-D1`, `S6-D2`, `S6-D3`, `S6-D6`

## Decision

Four rules, joined because they are one question — *what bounds an agent's delegated authority?* —
and because each is unenforceable without the others.

**1. The Context service is the sole issuer, and issuance verifies every `I-07` input (`I-106`).**
The Agent Runtime **requests** narrowing; it never mints. Before issuing a narrowed token, Context
refuses any request exceeding the requesting execution's own integrity-verified token, the named
agent definition's Allowed Context / Allowed Tools / Permissions, James-created grants, or
applicable delegation constraints. Refusal is total, fail-closed, and recorded. **There is no
partial issuance.**

**2. Delegation is strictly narrowing and acyclic, and re-delegation is explicit (`I-107`).** Every
delegation is strictly narrower in at least one dimension — scope, rights, tools, risk ceiling —
**and** expires strictly earlier. A delegation whose delegate appears in its own ancestry is
refused. The delegation record gains `may_redelegate`, **default false**, and `ancestry`. **No
numeric depth or fan-out limit is introduced.**

**3. The cost ceiling belongs to the root execution and is shared by its entire delegation tree
(`I-108`).** A descendant cannot mint capacity, receive a fresh budget, raise the root ceiling, or
transfer capacity into an independent budget. A parent *may* carve a smaller child ceiling —
optional, and itself narrowing.

**4. A child execution never outlives the execution identity that granted it (`I-107`).** On
completion, failure, termination, revocation, or emergency stop alike, the child fails closed at
its next enforcement point. **No suspended agent state is introduced.**

## Context

`IDENTITY_AND_AUTHORITY.md` §3 claims *"no mechanism in the architecture widens authority at any
step."* Section 06 tested that claim against delegation specifically.

## Problem

**The claim held everywhere except in the derivation of delegated authority itself.**

**`I-07`'s intersection had no verifying point.** Two of its four inputs were already independently
enforced — grants by the PDP at step 5 (`I-10`), and token integrity by `I-87`/`P-12`. The other
two were not. The **agent definition** is consulted by none of `AUTHORIZATION_MODEL.md` §3's ten
steps. And `AGENT_ARCHITECTURE.md` §2 read *"the runtime cannot **issue** a token exceeding it"* —
wording that describes a minting runtime, which `I-87` forbids by requiring every consumer to
reject tokens "fabricated by anything other than the Context service". `THREAT_MODEL.md` T-24's
Agent-Runtime row answered *"an agent could receive a token it should not have"* with *"rights
remain an intersection (`I-07`)"* — **circular**, since the intersection was exactly what the
compromised component computed.

**Delegation had no bound of any kind.** A repository-wide search returns zero normative statements
bounding agent recursion, spawn count, or cycles. And `SCOPE_AND_IDENTITY_MODEL.md` §5 conditioned
re-delegation on *"where the original delegation permits it"* while listing a record with **no such
field** — a rule testing data that does not exist.

**`I-105`'s ceiling was per execution, so a delegation tree of N executions received N ceilings.**
Section 05 named "recursive delegation" as a denial-of-service vector and then bounded the ceiling
per execution, leaving a child able to manufacture capacity its parent never held. **This gap was
introduced by Section 05 and is closed here.**

**Child survival was undefined.** `V-2` covers revoked tokens; nothing covered a parent that merely
completed or failed.

## Options Considered

**For issuance verification:**
1. **PDP computes the intersection.** Turns the PDP into an identity-derivation engine, puts an
   agent-registry read on the hot path against `P-7`, and gives one component two jobs.
2. **Context verifies at issuance.** One check, at the only point where all four inputs exist
   together, by the component that already issues and is already TRUSTED.
3. **A new validating enforcement point.** A seventh PEP for one check — and the check must happen
   *before* issuance anyway, since a token is integrity-bound the moment it exists.
4. **Already covered.** False: the agent-definition input is checked by nothing.

**For delegation bounds:** numeric depth limits; a delegation-count budget; prohibiting
re-delegation entirely; structural rules.

**For cost:** per execution (the broken status quo); per root execution with a shared budget; per
agent; per client scope; mandatory parent allocation.

**For child lifetime:** immediate invalidation; continue to own expiry; independent
re-authorization; survive-but-cannot-spawn.

## Decision Made

Issuance: **option 2**. Delegation: **structural rules**. Cost: **per root execution, shared**,
with optional carving. Child lifetime: **immediate invalidation**.

## Reason

**Verification belongs where all the inputs are, and that place already exists.** Option 2 adds no
component, no second policy engine, and no enforcement point. It makes `I-07` enforced rather than
asserted at the one moment the agent definition, the parent token, the grants and the delegation
constraints are all in hand. After issuance is too late — the token is integrity-bound and every
downstream point is obliged to honour it.

**Structural bounds beat numeric ones because they can be justified.** Strict narrowing descends a
finite authority lattice and shortens lifetime at every step, so depth terminates *for a stated
reason*. "Depth 3" is a number nobody could defend and every implementer would tune. The same logic
governs fan-out: it is bounded by the budget, which already governs the resource fan-out consumes,
rather than by a second arbitrary number.

**One budget per tree is the only option that answers the question directly.** *Can an agent create
capacity without consuming its parent's?* Under a shared root budget the answer is no, by
construction. **Mandatory parent allocation was rejected specifically because it fails the
implementability test** — "how much does a parent carve?" is a security-relevant number the
architecture does not decide, so requiring it would hand that decision to an engineer.

**The child-lifetime rule is a statement, not an invention.** `I-07` makes child rights ⊆ the
granting identity's rights; `AUTHENTICATION_MODEL.md` §5 ends that identity at completion or
expiry; `V-2` already fails in-flight executions closed at their next enforcement point. All this
decision does is say that `V-2`'s trigger includes **any** end of the granting identity, not only
revocation. Letting a child continue would permit authority to outlive its source — the exact
laundering the narrowing rules exist to prevent.

## Tradeoffs

**Advantages:** `I-07` becomes enforced rather than asserted; no new component, PEP, policy engine,
token issuer, or governance class; delegation is non-amplifying, non-cyclic, bounded, expiring and
non-transferable-by-default; recursive capacity minting is closed; `I-87` and `I-66` preserved
unchanged.

**Disadvantages:** **the Context service must now read the agent registry — a new trust
dependency**, and a component that was purely a scope resolver acquires a bound-checking duty. Every
delegation must differ from its parent in some dimension, which forbids the "pass my authority
through unchanged" pattern an implementer might find convenient. A shared root budget means one
runaway child can starve its siblings — accepted, because the alternative is a child that cannot be
starved because it mints its own. The `ancestry` field grows with depth.

**One honest consequence:** a legitimate long delegation chain will hit the lattice floor and stop.
That is the intended behaviour and it will occasionally be inconvenient.

## Consequences

- `AGENT_ARCHITECTURE.md` §2's issuance wording is corrected; `SCOPE_AND_IDENTITY_MODEL.md` §5
  gains the two missing record fields; `CONTEXT_ARCHITECTURE.md` gains the issuance check —
  authorized by [ADR 0031](./0031-section-06-amendments-to-accepted-architecture.md).
- `THREAT_MODEL.md` T-24's Agent-Runtime row is corrected: its previous answer was circular.
- **A compromised Context service still issues genuine tokens naming anything.** `T-23a` is
  **unchanged and not improved**; `AG-3` is a check that same service performs on itself. Stated so
  this decision is not mistaken for a trusted-root mitigation.
- `I-105` is amended in scope, not in behaviour: exhaustion still terminates and escalates.

Invariants: `I-106`–`I-108` (new), `I-107` covering child lifetime. `I-07`, `I-08`, `I-12`, `I-66`,
`I-87`, `I-104`, `V-2` untouched.

## What Would Change This

A demonstration that strict narrowing terminates legitimate delegation chains too early in
practice. That would argue for a richer authority lattice — more dimensions to narrow along — not
for permitting a delegation that narrows nothing.
