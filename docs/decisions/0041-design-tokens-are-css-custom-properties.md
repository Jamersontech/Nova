# 0041 — Design Tokens Are CSS Custom Properties

**Status:** **Accepted** — 2026-08-15
**Proposed:** 2026-08-15 — Section 15
**Accepted:** 2026-08-15 — by James, at the Section 15 gate, on rendered evidence from the
`slice/ui/` demonstration
**Section:** 15
**Resolves:** `D-13` **in part only** — the design-token half. The application UI framework half
remains deferred.

## Decision

**NOVA's design tokens are CSS custom properties, generated from a single JSON source of truth.
The Section 15 demonstration layer is built from native Web Components. No application UI
framework is selected.**

Concretely, four rules:

**1. `tokens.json` is the single source of truth.** Every visual value NOVA uses — colour,
typography, spacing, radius, border, elevation, motion — originates in one file. Nothing else
declares a visual value. The file is two-tiered: **primitive** tokens hold raw values, **semantic**
tokens reference primitives by path and are what components consume. A semantic token that
references a missing primitive is a build failure, not a silent fallback.

**2. Tokens are emitted as CSS custom properties.** `build_tokens.py` resolves the references and
emits `tokens.css` as `--nova-*` declarations on `:root`. The generated file is never hand-edited.
CSS custom properties are inherited, and inheritance **crosses Shadow DOM boundaries** — which is
what makes a single token change reach every component without a rebuild of the components
themselves.

**3. Components consume tokens; they never declare visual values.** A primitive component reads
`var(--nova-*)`. A composite component is built from primitives. A screen composes composites and
declares no visual value of its own. This is
[`DESIGN_PRINCIPLES.md`](../design/DESIGN_PRINCIPLES.md) §6's mandated layering, enforced by test
rather than by convention.

**4. Web Components are the Section 15 demonstration mechanism, not NOVA's UI framework.** Custom
Elements and Shadow DOM are **browser standards, not a framework**. They are used here because they
provide a real encapsulation boundary — so "a composite consumes a primitive" is a structural fact
rather than a naming convention — with zero runtime dependencies and no build step.

## Why this does not resolve the application-framework decision

**`D-13` bundles two questions that have different answers.** *"Design-token implementation"* is a
question about a value substrate; *"UI framework"* is a question about an application's component
and rendering model. Section 15 owns the first because the design system is its deliverable. The
second is decided by what Sections 16–18 need to build and by the infrastructure Sections 29–30
define, none of which exists yet.

**The token half is genuinely framework-independent, and that is why it can be settled early.**
React, Vue, Svelte, Solid, Web Components and plain HTML all consume
`var(--nova-color-surface-raised)` identically, with no translation layer, no adapter and no build
integration. A token layer chosen now survives any framework chosen later. **The reverse is not
true** — a framework chosen now would constrain every screen Section 16 has not yet designed.

**So the framework half stays open**, and `D-13` remains listed as deferred with its scope narrowed
to that half.

## Sections 16–18 are not constrained to Web Components

**This ADR binds the token layer and nothing else.** Sections 16–18 may adopt any framework, or
none. What they inherit is `tokens.json` and the generated `tokens.css` — a stylesheet, consumable
by anything that renders CSS.

The component layer built here is **demonstration, not foundation**. Its purpose is to produce
executable evidence that the layering in `DESIGN_PRINCIPLES.md` §6 actually holds, which a document
cannot do. If Section 16 adopts a framework, the primitives and composites here are **replaced, not
migrated**, and the token layer is untouched by that replacement. Nothing in this ADR asserts that
NOVA's production interface is built from Custom Elements.

## Playwright is verification tooling, not application infrastructure

**Playwright is a development and test dependency. It ships nothing.** It exists to answer a
question that cannot be answered by reading source: *does the rendered result actually change when a
token changes?* Only a browser computes the cascade, so only a browser can produce that evidence.

It uses the **pre-installed Chromium**; no browser is downloaded. It is not a build tool, not a
runtime, not a server, and it is not a step toward Sections 29–30's infrastructure. **`D-12`
(testing framework and AI evaluation tooling, owner 31) is unaffected** — Playwright is not proposed
as NOVA's testing framework, only as the instrument for this slice's render checks, exactly as the
existing slice's SQLite use is slice-local and does not resolve `D-01`/`D-02`.

## Context

[`DESIGN_PRINCIPLES.md`](../design/DESIGN_PRINCIPLES.md) §6 already binds the layering — Design
Tokens → Primitive Components → Composite Components → Screens — and states *"This is a binding
requirement on future sections. It is not implemented now."*
[`USER_INTERFACE_ARCHITECTURE.md`](../architecture/USER_INTERFACE_ARCHITECTURE.md) §8 assigns
visual design, components, layout, typography, colour and interaction patterns to Sections 15–18
and names `D-13`.

## Problem

**A design system specified only in prose cannot be checked.** A requirement that *"a global visual
change must be achievable through the design system rather than by editing dozens of unrelated
screens"* is a claim about behaviour under change. Written down, it is an intention; nothing
verifies that a screen has not quietly declared its own colour. **The failure it guards against is
invisible in review** — a hard-coded value looks correct until the day the token changes and one
surface does not move with it.

**And a design token is not a requirement, it is a value.** Section 04 could specify secrets
requirements without a store and Section 05 could specify provider criteria without a provider,
because both describe behaviour. A hex code, a spacing scale and a type ramp describe nothing —
their correctness is only observable when rendered.

## Options Considered

1. **Document-only Section 15.** Specify the taxonomy in prose, resolve nothing. Zero risk, zero
   evidence; leaves the §6 requirement unverifiable and repeats the pattern the vertical-slice
   programme exists to correct.
2. **Select a full application framework now** (React + Vite, or equivalent). Strongest ecosystem
   for Sections 16–18 and compile-time enforcement of token usage. Rejected: it commits NOVA's
   component model before Section 16 has designed a screen and before Sections 29–30 define
   infrastructure, and a framework is not required to prove token propagation —
   [`AGENTS.md`](../../AGENTS.md) forbids dependencies not required by the work at hand.
3. **Split `D-13`: tokens as CSS custom properties now, framework deferred**, with Web Components
   as a zero-dependency demonstration layer.
4. **Plain CSS classes and static HTML.** Minimal, but no encapsulation boundary, so
   "composites consume primitives" degrades to a naming convention and the evidence is weak.

## Decision Made

Option 3.

## Reason

**It is the smallest change that produces the evidence.** Requirements A–G of the Section 15 gate —
tokens resolve, primitives render from tokens, composites from primitives, a screen from composites,
and a token change propagating without editing the screen — are all satisfied by the platform's own
inheritance semantics. No framework contributes anything to proving them.

**It separates a durable decision from a premature one.** The token substrate outlives any
framework; the framework choice does not outlive Section 16's requirements, which do not exist yet.
Deciding the half that is stable and deferring the half that is not is the same posture Section 04
took with `D-09`/`D-10` (requirements resolved, store deferred) and Section 05 with `D-08`
(criteria `PR-1`–`PR-9` fixed, provider deferred).

**Shadow DOM makes the demonstration honest rather than decorative.** Custom properties piercing
the shadow boundary is the exact mechanism the propagation requirement depends on. A demonstration
built without an encapsulation boundary would prove a weaker claim while appearing to prove this
one.

## Tradeoffs

**Advantages:** zero runtime dependencies; no build step; no bundler; the token layer survives any
future framework; Sections 16–18 keep their choice; the §6 layering becomes test-enforced rather
than aspirational; one dev-only dependency, using a browser already present.

**Disadvantages:** **Web Components are less familiar than React**, and a future maintainer may read
the demonstration layer as a commitment it explicitly is not — which is why this ADR states it three
times and why the components are named as demonstration in their own README. **No compile-time
typing of token references**, so requirement G is enforced by test rather than by compiler; a test
can be deleted where a type error cannot. And **the component layer is throwaway by design** — if
Section 16 adopts a framework, that work is discarded, which is a real cost accepted deliberately in
exchange for evidence now.

## What the implementation added beyond the approved gate

**Recorded rather than absorbed.** The gate proposed four primitives and four composites. The
implementation has four primitives and **six** composites. The two extra were **implementation
necessities discovered while building, not a decision to expand into Section 16**:

- **`nova-shell`** — without a composite owning layout, `demo/index.html` would have had to declare
  its own grid, spacing and background, which is precisely the rule the demonstration exists to
  prove. The screen can only hold *zero* visual values if something else holds them.
- **`nova-disclosure`** — required to demonstrate progressive disclosure, which
  [`DESIGN_PRINCIPLES.md`](../design/DESIGN_PRINCIPLES.md) §4 and
  [`USER_INTERFACE_ARCHITECTURE.md`](../architecture/USER_INTERFACE_ARCHITECTURE.md) §4 both
  require and which the gate listed among the properties to exercise.

**The six composites are not a component inventory.** Nothing here fixes what components NOVA has.
**Section 16 may add, replace, reorganise or discard every one of them** — they are demonstration
scaffolding, and only the token layer is inherited. A future reader finding six composites should
not treat that number, those names, or that division of responsibility as settled architecture.

## Consequences

- `slice/ui/` is created, holding the token source, generator, primitives, composites, a
  demonstration screen and tests. **It is slice-local**, exactly as
  [`ROADMAP.md`](../ROADMAP.md)'s validation-first note establishes for `slice/`, and is not
  application infrastructure.
- **`D-13` stays deferred with narrowed scope** — the framework half only.
  [`DEFERRED_DECISIONS.md`](./DEFERRED_DECISIONS.md) records the narrowing.
- **No invariant is created or amended.** `I-01`–`I-114` are byte-identical. The design system is a
  presentation layer over decisions already made; it creates no rule, no enforcement point and no
  authority.
- **`I-09` constrains the approval component**: an approval presentation may never imply that a
  model, an agent or an automation is the approving authority. This is `I-09` applied to
  presentation, not a new requirement.
- **No accepted ADR is amended.** ADRs 0038–0040 remain **Proposed** and are not relied on: the
  demonstration is built against the **accepted** text of
  `USER_INTERFACE_ARCHITECTURE.md` §6–§7 only, and does not encode ADR 0040's
  reachability-versus-authentication-strength distinction.

## What Would Change This

For the token mechanism: a rendering target that does not support CSS custom properties — which
would mean NOVA's interface is not web-delivered, a far larger decision than this one. For the
demonstration layer: Section 16 selecting a framework, at which point the primitives and composites
are replaced and this ADR's token half stands unchanged.
