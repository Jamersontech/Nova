# 0043 — Responsive Layout Is CSS-Driven From Tokens

**Status:** **Proposed**
**Proposed:** 2026-08-15 — Section 17
**Section:** 17

## Decision

**Responsive layout is computed by the browser from viewport-varying design tokens. No JavaScript
participates in layout, and no application UI framework is selected.**

Four rules:

**1. A responsive tier is added to `tokens.json`.** Alongside `primitive` and `semantic`, a
`responsive` tier declares breakpoints and, per band, **overrides of semantic tokens that already
exist**. A band may not introduce a token the base tier does not declare — that would create a value
present at one viewport and nowhere else, which is how a design system grows a value nobody can
find. `build_tokens.py` emits each band as a `@media` block re-declaring those custom properties on
`:root`.

**2. Components stay unaware that breakpoints exist.** A component reads `var(--nova-layout-columns)`
at every width; the cascade supplies the band's value. **No component contains a media query, a
breakpoint literal, or any viewport logic**, and the demonstration screens are unedited between
viewports.

**3. Layout is CSS, not JavaScript.** Media queries, container queries, grid, flex, `clamp()`,
`min()` and `max()` are the permitted mechanisms. **Forbidden:** JavaScript layout engines,
breakpoint managers, `ResizeObserver`-driven responsive state, viewport state stores, device
detection, routing or state libraries, and any framework. Enforced by test, because the failure mode
is gradual — one `ResizeObserver` is reasonable in isolation, and a responsive state system is what
it becomes.

**4. Section 17 covers visual surfaces only** — desktop, web, mobile. **Voice is out of scope**
(`D-14`, and ADR 0040's unresolved session-strength semantics, which remain Proposed).

## The breakpoint scale — a Section 17 implementation decision

**Two breakpoints, yielding three bands:**

| Band | Applies | Rationale |
| --- | --- | --- |
| `mid` | ≤ 1023px | Below a typical landscape tablet, where a two-column split stops paying for itself |
| `narrow` | ≤ 599px | Phone widths, where the split must be gone entirely |
| *(base)* | ≥ 1024px | Desktop: the two-column layout the Section 16 screen was designed at |

**These values are chosen by Section 17. They are not dictated by the architecture, and this ADR does
not pretend otherwise.** No accepted document names a breakpoint, a viewport class or a device
category — `viewport`, `breakpoint`, `orientation`, `density` and `safe area` appear nowhere in the
repository.

**WCAG 1.4.10 fixes a test *condition*, not a scale.** It requires content to reflow at 320 CSS px
without two-dimensional scrolling. That is a width the slice must *pass at*, and it is why a band
must apply below it — but it mandates no particular breakpoint. Conflating the two would be
presenting an implementation choice as an inherited requirement.

**Two is the minimum that demonstrates the requirement**, which asks for desktop, tablet and mobile —
three bands, therefore two boundaries. A third breakpoint would be unrequired architecture, so a test
asserts the scale stays at two.

## Context

Section 15 established the token layer ([ADR 0041](./0041-design-tokens-are-css-custom-properties.md),
Accepted) and Section 16 the navigation model and Context Lock UI. `DESIGN_PRINCIPLES.md` §6 requires
a global visual change to be achievable *through the system*.
[`USER_INTERFACE_ARCHITECTURE.md`](../architecture/USER_INTERFACE_ARCHITECTURE.md) §7 requires mobile
to retain conversation, notifications, **approvals** and the **emergency stop**, and fixes that a
surface *"may vary in depth; it may never vary in authority"*.
[ADR 0042](./0042-wcag-22-aa-is-the-accessibility-baseline.md) (Accepted) adopts WCAG 2.2 AA, which
contributes the only mechanically testable responsive requirements the repository has: **1.4.10
Reflow**, **1.3.4 Orientation**, **1.4.4 Resize Text** and **2.5.8 Target Size**.

## Problem

**Responsive behaviour is where a component library usually acquires a framework.** The conventional
route is a JavaScript layout layer — observe the viewport, publish a breakpoint, let components
subscribe. Each step is defensible; the result is an application framework nobody chose, which is
exactly what `D-13` reserves for James.

**And "responsive architecture" normally means far more than this repository governs.** Breakpoint
systems, viewport classes, device capability models, touch behaviour, density and safe areas have no
governing requirement here. Building them would be authoring architecture while appearing to
implement it.

## Options Considered

1. **JavaScript-driven responsive state** — a breakpoint manager components subscribe to. Familiar,
   flexible, and the accretion path to a framework. Rejected.
2. **Per-component media queries** — each component declares its own breakpoints. No JavaScript, but
   the breakpoint values scatter across the codebase and become a second source of truth that drifts.
   Rejected.
3. **Viewport-varying tokens with CSS doing the work** — breakpoints in one generated place,
   components unaware.
4. **Full device architecture** — viewport classes, capability detection, touch model. Rejected:
   mostly ungoverned, and several C3 decisions Section 17 was not asked to make.

## Decision Made

Option 3.

## Reason

**It is Section 15's mechanism applied one dimension further.** A token already changes appearance
everywhere without a component being touched; a responsive token changes it *per viewport* on the
same terms. Nothing new is invented, and the propagation property is preserved and re-tested.

**It keeps the breakpoint values in exactly one place** — the token source — so there is no second
source of truth to drift.

**It keeps `D-13` genuinely open.** Media queries, grid and container queries are browser features.
A framework chosen later consumes the same generated stylesheet unchanged, and the responsive layer
survives the choice exactly as the base token layer does.

## Tradeoffs

**Advantages:** no dependency, no build step beyond the existing generator; breakpoints in one place;
components need no responsive awareness; the CSS/JavaScript boundary is mechanically detectable; the
existing demonstration screens are reused unedited, which is stronger evidence than a purpose-built
responsive screen would be.

**Disadvantages:** **CSS-only responsiveness cannot express everything.** Layout that depends on
content measurement — a genuine masonry, or text that must fit a computed box — has no expression
here, and a future section meeting that need will have to revisit this boundary rather than quietly
cross it. **Token-driven layout is less locally legible** than a media query beside the rule it
affects: a reader of `nova-workspace` sees `var(--nova-layout-columns)` and must consult the token
source to learn it changes. And **the breakpoint values are a judgement**, defensible but not
derived, which is why they are recorded here as a decision rather than presented as a finding.

## Consequences

- `tokens.json` gains a `responsive` tier; `build_tokens.py` emits `@media` bands widest-first so a
  narrower band wins by source order. `DESIGN_SYSTEM.md` §3 is amended to distinguish base tokens
  from viewport-varying values.
- `nova-workspace`'s grid track becomes a token; interactive controls gain a token-driven minimum
  target size (2.5.8). **The Section 16 screen and its navigation model are unchanged.**
- **No invariant is created or amended.** `I-01`–`I-114` byte-identical. Layout creates no rule, no
  enforcement point and no authority.
- **`D-13` remains deferred** — no framework is selected. **`D-12` remains deferred** — no new testing
  tooling; the existing Playwright dev dependency drives viewport sizes. **`D-14` remains deferred.**
- **Sections 18, 29, 30 and 43 are unconstrained.** They inherit a token layer and may replace every
  component. The breakpoint scale is a Section 17 choice they may revisit.
- **ADRs 0038–0040 remain Proposed** and nothing here depends on them.

**The honest limit.** This establishes responsive *reflow*, not a device architecture. Touch and
pointer behaviour beyond target size, density, safe areas and orientation-specific layout are **not
addressed and not claimed**, because no accepted requirement governs them. A future section needing
them is making new architecture, and should say so.

## What Would Change This

A layout requirement that CSS cannot express, which would argue for revisiting the JavaScript
boundary deliberately rather than eroding it. Or Section 18 or a later section establishing a real
device-capability requirement, which would argue for a device model this ADR deliberately does not
create.
