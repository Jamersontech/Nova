# Section 15 — NOVA Design System (slice)

**This is a demonstration layer, not NOVA's interface.** It exists to produce executable
evidence for one claim that a document cannot support on its own:

> *"A global visual change must be achievable through the design system rather than by editing
> dozens of unrelated screens."* — [`DESIGN_PRINCIPLES.md`](../../docs/design/DESIGN_PRINCIPLES.md) §6

That is a claim about behaviour under change. Written down it is an intention; here it is
checked by changing a token and re-rendering in a real browser.

Authority: [ADR 0041](../../docs/decisions/0041-design-tokens-are-css-custom-properties.md)
(**Proposed**). Like the rest of [`slice/`](../README.md), the technology here is **slice-local**.

---

## What this is not

- **Not Section 16.** No UX or information architecture, no screen designs.
- **Not Section 17.** No responsive or device architecture. There are no breakpoints.
- **Not Section 18.** No Personal Command Center.
- **Not NOVA's UI framework.** `D-13`'s framework half remains **deferred**. Custom Elements are
  a browser standard used for the demonstration; Sections 16–18 may adopt any framework, or none,
  and inherit only the tokens.
- **Not wired to anything.** No control performs an action. Pressing *Approve* approves nothing —
  `I-09` places that authority with James alone.

---

## The layering

```text
tokens.json          single source of truth -- the only file holding a literal value
   |  build_tokens.py
tokens.css           GENERATED -- :root { --nova-* }
   v
primitives/          nova-text, nova-box, nova-button, nova-badge
   v                 read var(--nova-*); declare no visual value
composites/          nova-context-bar, nova-area-nav, nova-approval-card,
   v                 nova-stop, nova-disclosure, nova-shell
demo/index.html      composes composites; contains no colour, size, spacing,
                     font, <style> block, style attribute or class hook
```

Tokens are two-tiered. **Primitive** tokens hold raw values; **semantic** tokens reference them by
path and are what components consume. Components are barred by test from reaching past the semantic
tier — that indirection is what lets the palette change without a component being touched.

---

## Running it

```bash
python3 -m slice.ui.tokens.build_tokens      # regenerate tokens.css
python3 -m unittest slice.ui.tests.test_tokens   # 27 structural tests
node slice/ui/tests/render_check.mjs         # 26 render checks, real browser
```

The render check starts a local static server, drives Chromium, mutates one token, rebuilds,
re-renders, asserts the computed styles moved and `demo/index.html` did not, then restores the
token. It leaves the tree as it found it.

> **The browser path is pinned to this environment.** `render_check.mjs` launches Chromium via an
> explicit `executablePath` — `/opt/pw-browsers/chromium-1194/chrome-linux/chrome` — because the
> installed Playwright pins a newer build number than this image ships, and downloading a second
> browser was not warranted for a slice. **So the render result is not reproducible as-is on an
> arbitrary machine:** on a different environment the path must be changed, or the pinned browser
> installed. The *evidence* is real; the *command* is environment-specific. A future section that
> wants portable render verification is choosing testing tooling, which is `D-12`, owner 31.

## The component inventory is not settled

Four primitives and six composites exist because the demonstration needed them — `nova-shell` so
the screen could hold no visual values at all, `nova-disclosure` to exercise progressive
disclosure. **Both were discovered while building, not planned at the gate**, and neither is a
claim about what components NOVA has. **Section 16 may add, replace, reorganise or discard any of
them.** Only the token layer is inherited.

---

## Validation state

Using the repository's five levels, honestly:

| Level | | |
| --- | --- | --- |
| **DOCUMENTED** | ✅ | The taxonomy and layering, ADR 0041 |
| **IMPLEMENTED** | ✅ | Tokens, generator, 4 primitives, 6 composites, demonstration screen |
| **EXECUTED** | ✅ | Renders in Chromium; 26 render checks pass against computed styles |
| **SECURITY-TESTED** | ❌ **No** | **Nothing here is a security test.** A colour ramp has no threat model. The tests are structural and visual |
| **VALIDATED AGAINST A REAL EXTERNAL SYSTEM** | ❌ **No** | No external system is involved. A local static server and a local browser are not one |

**The accepted-architecture checks are coverage, not enforcement.** Tests assert that the
demonstration *presents* three areas, an always-visible context, unmissable approvals, an
always-reachable stop and risk classification. A component cannot enforce any of that — enforcement
lives in the PDP and the enforcement points, none of which this touches.

---

## What is deliberately absent, and why

**ADR 0040 is Proposed**, so nothing here depends on it. The approval card presents a request and
says nothing about which surface may *complete* one: no session-strength ceiling, no step-up, no
voice. If that distinction turns out to be needed for the demonstration to be coherent, it is a
conflict to report, not to implement. `test_tokens.py` asserts the absence so it cannot creep in.
