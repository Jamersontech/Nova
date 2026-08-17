# Section 17 — Responsive Reflow (slice)

**No new screen.** Section 17 drives the **existing, unedited Section 16 screen** at four viewport
sizes. That choice is the evidence: if the same file works at 1440px and at 320px, the responsive
behaviour lives in tokens and CSS, which is exactly the claim.

Authority: [ADR 0043](../../../docs/decisions/0043-responsive-layout-is-css-driven-from-tokens.md)
(**Proposed**). Tokens from Section 15 ([ADR 0041](../../../docs/decisions/0041-design-tokens-are-css-custom-properties.md),
Accepted); accessibility baseline from [ADR 0042](../../../docs/decisions/0042-wcag-22-aa-is-the-accessibility-baseline.md)
(Accepted).

---

## What this is not

- **Not a device architecture.** No viewport classes, no capability model, no device detection.
- **Not touch, density, or safe areas.** No accepted requirement governs them, so they are absent
  rather than invented.
- **Not voice.** Visual surfaces only — `D-14` and ADR 0040 are untouched.
- **Not a framework.** `D-13` stays deferred. No dependency was added.
- **Not Section 18.** No Command Center, no new screens.

## The mechanism

```text
tokens.json           responsive tier: breakpoints + per-band semantic overrides
      |  build_tokens.py
tokens.css            @media blocks re-declaring --nova-* on :root, widest band first
      v
components            read var(--nova-*) at every width; contain no media query,
                      no breakpoint literal, no viewport logic
      v
screen                unedited between viewports
```

**A band may only override a semantic token that already exists.** Introducing one would create a
value present at a single viewport and nowhere else — the generator refuses it.

## Breakpoints

| Band | Applies | |
| --- | --- | --- |
| `mid` | ≤ 1023px | two-column split collapses |
| `narrow` | ≤ 599px | tighter spacing, smaller display type |
| *(base)* | ≥ 1024px | the desktop layout |

**These values are a Section 17 decision, not an inherited requirement.** No accepted document names
a breakpoint. WCAG 1.4.10 fixes a 320px test *condition* — a width to pass at — and mandates no
scale. Two breakpoints are the minimum for the three bands the slice must show, and a test asserts
the scale stays at two.

## Running it

```bash
python3 -m unittest slice.ui.section17.tests.test_responsive   # 21 structural tests
node slice/ui/section17/tests/viewport_check.mjs               # 39 browser checks
```

The viewport check mutates one responsive token, rebuilds, re-renders, asserts the layout moved and
the screen file did not, then restores. It leaves the tree as it found it.

> The browser path is **pinned to this environment**, as in Sections 15–16: the installed Playwright
> pins a newer Chromium build than the image ships. The evidence is real; the command is
> environment-specific.

---

## Validation state

| Level | | |
| --- | --- | --- |
| **DOCUMENTED** | ✅ | Responsive model, breakpoint rationale, CSS/JS containment, ADR 0043 |
| **IMPLEMENTED** | ✅ | Responsive token tier, generator bands, CSS layout rules, target sizing |
| **EXECUTED** | ✅ | 39 browser checks at 1440 / 900 / 390 / 320px: reflow, orientation, 200% text, target size, stop and approval reachability, context visibility, token-driven layout change |
| **SECURITY-TESTED** | ❌ **No** | Layout enforces nothing. Even the stop-reachability check is a presentation property; the stop's authority lives in the PDP and `SECURITY_OPERATIONS.md` |
| **VALIDATED AGAINST A REAL EXTERNAL SYSTEM** | ❌ **No** | A resized local browser is not an external system |

## Accessibility: exactly what was added

**No conformance claim.** Section 17 adds four criteria to the tested list; everything Section 16
left untested that is not below remains untested.

| Criterion | What is checked |
| --- | --- |
| **1.4.10 Reflow** | No horizontal scrolling at 1440, 900, 390 and **320** CSS px |
| **1.3.4 Orientation** | Portrait and landscape both render with no content lost and no horizontal scrolling |
| **1.4.4 Resize Text** | Root font size doubled — no horizontal scrolling, content still present |
| **2.5.8 Target Size** | All 14 interactive controls ≥ 24×24 CSS px at every viewport |

**Still not tested, and therefore still not claimed:** colour contrast ratios (1.4.3, 1.4.11),
consistent help (3.2.6), redundant entry (3.3.7), motion preferences, screen-reader announcement
quality, and focus *order*.

---

## A defect this slice uncovered

`nova-scope-switch` set `hidden`, but its shadow root declared `:host { display: block }` — an
**author** style, which outranks the user agent's `[hidden] { display: none }`. The dialog therefore
rendered at full height on every page load. Section 16's check read the `hidden` *attribute* and
reported it closed, so the test passed while the screen was wrong.

Both are fixed: the component opts back in with `:host([hidden]) { display: none }`, and Section 16's
check now measures **computed display** rather than the attribute. The visual check caught what the
behavioural check could not — worth remembering when deciding whether a rendering test is worth its
cost.
