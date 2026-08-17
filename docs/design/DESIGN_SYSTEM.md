# NOVA Design System

**Status:** **Active** — Section 15, accepted by James 2026-08-15 ([ADR 0041](../decisions/0041-design-tokens-are-css-custom-properties.md)).
**Covers:** the design-token architecture and the layering every NOVA interface is built from.
**Extends:** [`DESIGN_PRINCIPLES.md`](./DESIGN_PRINCIPLES.md) (Section 01, Active) §6, which required
this system and deliberately did not build it.
**Does not cover:** information architecture
([`../architecture/USER_INTERFACE_ARCHITECTURE.md`](../architecture/USER_INTERFACE_ARCHITECTURE.md),
Section 02, Active), screens and UX (Section 16), responsive behaviour (Section 17), or the
application UI framework (**`D-13`, still deferred**).

---

## 1. The Layering

```text
tokens.json          the single source of truth -- the only file holding a literal value
      |  build step
tokens.css           generated -- CSS custom properties on :root
      v
Primitive components read var(--nova-*); declare no visual value
      v
Composite components built from primitives
      v
Screens              compose composites; declare no visual value of their own
```

This is `DESIGN_PRINCIPLES.md` §6's requirement, unchanged. What Section 15 added is that **it is
enforced by test rather than by convention** — a screen that declares a colour, or a component that
hard-codes a length, fails a check rather than passing review and drifting later.

**The rule that gives the layering its purpose:** a global visual change must be achievable *through
the system*, never by editing screens. That is a claim about behaviour under change, so it is
verified by changing a token and re-rendering, not by inspection.

---

## 2. Tokens Are CSS Custom Properties

**Decided in [ADR 0041](../decisions/0041-design-tokens-are-css-custom-properties.md), Accepted
2026-08-15.** Two properties make this the durable half of `D-13`:

- **Every candidate framework consumes them unchanged.** React, Vue, Svelte, Solid, Web Components
  and plain HTML all read `var(--nova-color-surface-raised)` with no adapter and no build
  integration. A token layer chosen now survives a framework chosen later.
- **Custom properties are inherited, and inheritance crosses Shadow DOM boundaries.** A change at
  `:root` reaches every component without components being rebuilt, re-registered or re-imported.

---

## 3. `tokens.json` Is the Source of Truth

**Nothing else declares a visual value.** The file has two tiers, and the separation is
load-bearing:

| Tier | Holds | Consumed by |
| --- | --- | --- |
| **Primitive** | Raw values — a hex code, a rem, a shadow | **Nothing outside the token file** |
| **Semantic** | References to primitives, by path | Components |
| **Responsive** *(Section 17)* | Per-viewport **overrides of semantic tokens that already exist** | Components, via the cascade |

**Base values and viewport-varying values are distinct.** A semantic token declares the value that
applies everywhere; a responsive band re-declares it inside a `@media` block for one viewport range.
A band may **only** override a token the semantic tier already defines — introducing one would create
a value present at a single viewport and nowhere else, which the generator refuses.

**Components remain unaware that breakpoints exist.** They read the same `var(--nova-*)` at every
width and the cascade supplies the band's value, so no component contains a media query, a breakpoint
literal or viewport logic. Layout is computed by the browser, never by JavaScript
([ADR 0043](../decisions/0043-responsive-layout-is-css-driven-from-tokens.md), **Proposed**).

A semantic token that references a missing primitive is a **build failure, never a fallback** — a
fallback is precisely how a design system loses a value: the build succeeds, one surface renders the
wrong colour, and nothing says so.

**Components consume the semantic tier only.** Reaching past it to a primitive would reattach a
component to a raw value and defeat the indirection, so it is refused by test.

Generated output is never hand-edited, and a stale generated file fails a test rather than surviving
as a quiet second source of truth.

---

## 4. Screens Own No Visual Values

A screen composes composites. It contains no colour, size, spacing, font, `<style>` block, style
attribute or class hook. Where layout is genuinely needed, it belongs to a composite that owns it —
not to the screen.

**This is the rule the whole system exists to protect**, and the one most easily lost: a single
hard-coded value on one screen looks correct until the day the token changes and that surface does
not move with the rest.

---

## 5. Accessibility Is Part of the System

**WCAG 2.2 AA is the baseline** ([ADR 0042](../decisions/0042-wcag-22-aa-is-the-accessibility-baseline.md),
**Accepted** 2026-08-15). Components use native interactive elements, expose state through ARIA rather than
through glyphs or colour, carry accessible names, and indicate focus visibly.

This is not a separate concern bolted on: `USER_INTERFACE_ARCHITECTURE.md` §5 makes the active
context a **safety** surface and §6 requires the emergency stop to be always reachable. A context
indicator that is visible but not announced, or a stop that cannot be reached by keyboard, fails
those requirements for one class of user while appearing correct.

---

## 6. What Is Built, and What It Is Not

The system is implemented in [`../../slice/ui/`](../../slice/ui/README.md) — token source,
generator, primitive and composite components, demonstration screens, and tests. It is
**slice-local**, exactly as `ROADMAP.md`'s validation-first note establishes for `slice/`, and it is
not production infrastructure.

> **The component set is not a component inventory.** Section 15 built four primitives and six
> composites because its demonstration needed them, two of which were implementation necessities
> discovered while building. Section 16 added four more for the same reason.
> **Sections 16–18 may add, replace, reorganise or discard any of them.** Only the **token layer**
> is inherited. Nothing here fixes what components NOVA has, what they are named, or how
> responsibility is divided between them.

**Web Components are demonstration technology, not NOVA's application framework.** Custom Elements
and Shadow DOM are browser standards, used because they provide a real encapsulation boundary with
zero runtime dependencies and no build step. **`D-13`'s application-framework half remains
deferred**, and Sections 16–18 are unconstrained in that choice.

---

## 7. Validation State

| Level | | |
| --- | --- | --- |
| **DOCUMENTED** | ✅ | This document, ADR 0041, ADR 0042 |
| **IMPLEMENTED** | ✅ | Token source, generator, primitives, composites, screens |
| **EXECUTED** | ✅ | Renders in a real browser; token propagation demonstrated by changing a token and re-rendering |
| **SECURITY-TESTED** | ❌ **No** | Nothing here is a security test. A colour ramp has no threat model |
| **VALIDATED AGAINST A REAL EXTERNAL SYSTEM** | ❌ **No** | No external system is involved |

**No accessibility conformance is claimed** — only the specific criteria listed in
[`../../slice/ui/section16/README.md`](../../slice/ui/section16/README.md) were tested. Conformance
requires an audit, not more assertions.
