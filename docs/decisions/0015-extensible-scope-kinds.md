# 0015 — Scope Kinds Are Extensible; the Scope Contract Is Not

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 03
**Section:** 03

## Decision
Domains may define their own scope kinds — `business`/`client`/`project`/`environment` for
BUSINESS, `area`/`thread` for LIFE, `holding` for WEALTH, and others later. Any new kind must
satisfy the **scope contract**: exactly one parent; downward-only access by explicit grant;
no implicit sibling path; partitions memory, knowledge, credentials, and permissions;
declares what may attach to it. **Structure varies; authorization does not.** Adding a kind
is a C3 change.

### Enforcement — mechanical, not review alone

*Amended 2026-08-12 following adversarial review.*

The contract must be **validated executably at kind registration**. A kind that fails any of
the five rules is **rejected by the registry**, not merely questioned in review.

| Rule | Mechanically checkable as |
| --- | --- |
| Exactly one parent | The kind's declaration permits exactly one parent kind; the registry rejects multi-parent declarations |
| Downward-only access by explicit grant | The kind declares no access semantics of its own; authorization is evaluated solely by the PDP against scope paths |
| No implicit sibling path | No declaration may create a reference or grant between siblings |
| Partitions memory, knowledge, credentials, permissions | The kind declares partition participation for all four; absence is rejection |
| Declares what may attach | An explicit attachment list is present and well-formed |

**Human C3 review remains required** — mechanical validation cannot judge whether a kind is
*sensible*, only whether it is *conformant*. Both gates apply, and either can reject.

**Why review alone is insufficient:** a kind could declare conformance and not implement it,
and nothing would catch the difference. Enforcement that depends solely on a human reading a
declaration is a documentation practice, not a control. `I-56`.

## Context
ADR 0002 unified all domains into one scope tree. Section 03's brief requires that different
domains support domain-specific structures, and that NOVA not assume every future business
has KAIRO's internal shape.

## Problem
If the tree permits only one fixed hierarchy, a business shaped unlike KAIRO — an agency with
retainers rather than projects, a product business with no clients at all — cannot be
modelled without distorting it or forking the isolation model.

## Options Considered
1. **One fixed hierarchy for all domains.** Simplest and most uniform; forces every future
   business into KAIRO's shape, and distortion is where isolation bugs breed.
2. **Extensible kinds bound by a contract.** Structural flexibility with uniform
   authorization; requires the contract to be enforced when kinds are added.
3. **Fully generic nodes with no kinds.** Maximum flexibility; nothing constrains what may
   attach where, so validation becomes ad hoc.

## Decision Made
Option 2.

## Reason
The isolation guarantee comes from the contract — one parent, downward-only, no sibling path
— not from the *names* of the levels. Fixing names buys uniformity NOVA does not need while
costing adaptability it will.

## Tradeoffs
**Advantages:** new businesses and domains model naturally; LIFE and WEALTH already differ
without special-casing; the isolation model is written once; each kind's attachment rules are
declared and testable.
**Disadvantages:** more kinds to reason about; a badly designed kind could complicate the
tree; a future kind may tempt someone to violate the contract "just for this case."

## Consequences
The contract, not the kind list, is load-bearing. A proposed kind that cannot satisfy all
five rules must be rejected — that rejection is the point, not an obstacle. Rejection is
performed by the registry, not left to review. Invariants `I-01`, `I-06`, `I-56`.

## What Would Change This
A domain whose real structure cannot satisfy the contract. That would be evidence against
ADR 0002's tree itself and would require a superseding ADR at that level, not an exception
here.
