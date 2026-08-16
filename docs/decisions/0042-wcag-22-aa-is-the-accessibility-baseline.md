# 0042 — WCAG 2.2 AA Is NOVA's Accessibility Baseline

**Status:** **Accepted** — 2026-08-15
**Proposed:** 2026-08-15 — Section 16
**Accepted:** 2026-08-15 — by James, at the Section 16 gate, on the executed evidence from the
`slice/ui/section16/` demonstration
**Section:** 16

## Decision

**Every NOVA interface surface meets WCAG 2.2 Level AA. An interface that does not is a defect,
not a preference.**

The baseline binds **Sections 17, 18 and 43** as well as Section 16 — a responsive layout, the
Personal Command Center and the Admin/Architect view are surfaces, and a baseline that applied only
to the first surface built would not be a baseline.

## Context

**The repository had nothing to say about accessibility.** Before Section 16, the words
*accessibility*, *keyboard*, *WCAG*, *screen reader*, *focus* and *ARIA* appeared in none of the 96
documents. `USER_INTERFACE_ARCHITECTURE.md` decides what is reachable and how;
`DESIGN_PRINCIPLES.md` decides character. Neither says whether a person who cannot use a mouse, or
cannot see the screen, can operate NOVA.

## Problem

**Silence here is not neutrality — it is a decision that gets made by default, late, and badly.**
Accessibility is cheap while an interface is being designed and expensive once screens exist,
because it is a property of structure: landmarks, element semantics, focus order, accessible names.
Retrofitting means rewriting the structure.

**And NOVA's interface carries safety obligations that are specifically accessibility-shaped.**
`USER_INTERFACE_ARCHITECTURE.md` §5 makes the active context *"the one piece of internal machinery
that must be exposed"*, because Constitution §7 makes context ambiguity a **safety** problem. §6
requires the emergency stop to be *"always reachable"*. **A context indicator that is visible but
not announced is invisible to a screen-reader user, and a stop that cannot be reached by keyboard is
not always reachable.** Those are not comfort features; they are the safety properties the interface
exists to deliver, and an inaccessible implementation silently fails them for one class of user
while appearing correct.

## Options Considered

1. **Say nothing; treat accessibility as an implementation detail.** Zero cost now. Leaves the
   safety obligations above dependent on whoever writes each screen, and guarantees a retrofit.
2. **WCAG 2.2 Level A.** A real floor, but A permits things AA forbids that matter directly here —
   notably contrast minimums and visible focus, both of which the context indicator and the stop
   depend on.
3. **WCAG 2.2 Level AA.** The standard regulatory and industry baseline. Covers contrast, focus
   visibility and appearance, target size, consistent help, and redundant entry.
4. **WCAG 2.2 Level AAA.** Rejected: AAA is not achievable for all content even in principle, and
   the W3C itself does not recommend it as a general policy. Adopting it would produce a standard
   NOVA fails by definition, which is worse than a standard it meets.

## Decision Made

Option 3 — WCAG 2.2 Level AA.

## Reason

**It is the level at which the criteria NOVA's own architecture already depends on become
mandatory.** 2.4.7 Focus Visible, 2.4.11 Focus Not Obscured, 1.4.3 Contrast and 1.4.11 Non-text
Contrast are all AA, and each maps onto something `USER_INTERFACE_ARCHITECTURE.md` §5 or §6 already
requires for reasons that have nothing to do with disability. **Adopting AA is therefore closer to
naming an existing requirement than to adding one.**

**Version 2.2 rather than 2.1** because it is current, and its additions — target size, consistent
help, focus appearance — are exactly the ones an approval-heavy interface needs: an approval control
that is hard to hit is a safety problem for everyone.

## Tradeoffs

**Advantages:** the safety obligations in §5 and §6 hold for every user rather than most; structure
is decided while it is cheap; a mechanical test surface exists, so the claim is checkable rather
than aspirational; Sections 17, 18 and 43 inherit a decided baseline instead of re-deciding it.

**Disadvantages:** **every future surface carries an obligation that can fail review**, and some
patterns become unavailable — colour-only status, div-as-button, decorative motion without a reduced
-motion path. **AA is not a guarantee of usability** for assistive-technology users; it is a floor,
and a conformant interface can still be unpleasant to operate. And **conformance cannot be fully
established by automated testing** — the honest limit, recorded below.

## Consequences

- Section 16's components use native interactive elements, landmark structure, accessible names,
  visible focus indicators, and state exposed through ARIA rather than through glyphs or colour.
- **Two Section 15 demonstration components were corrected** rather than left as-is: `nova-area-nav`
  and `nova-disclosure` used click handlers on non-interactive elements, which is not keyboard
  operable. ADR 0041 records that Section 16 may change those components freely, so this is the
  boundary working as intended rather than a Section 15 amendment.
- **No invariant is created.** `I-01`–`I-114` are byte-identical. This is a quality standard for
  surfaces, not a rule the PDP evaluates.
- **`D-12` is unaffected.** No accessibility audit tooling is selected; the Section 16 checks are
  hand-written against named criteria. Choosing an audit library is testing tooling, owner 31.

**The honest limit, stated rather than engineered around.** *"Meets WCAG 2.2 AA"* is a claim no test
suite can fully establish. Automated checks reach a minority of the criteria; the rest — meaningful
sequence, sensible focus order, whether an accessible name actually describes the control — require
human judgement. **Section 16 therefore claims only the specific criteria it tested, listed in
[`slice/ui/section16/README.md`](../../slice/ui/section16/README.md), and does not claim
conformance.** A future section that wants a conformance claim needs an audit, not more assertions.

## What Would Change This

A newer WCAG version reaching Recommendation, which would argue for moving the baseline forward
rather than abandoning it. Nothing argues for lowering it: the safety obligations that motivate AA
do not weaken.
