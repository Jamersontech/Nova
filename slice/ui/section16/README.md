# Section 16 — Navigation and Context Lock (slice)

**A demonstration of behaviour, not an application.** Section 16 owns UX and the concrete
navigation model. The *information architecture itself* was decided in Section 02 and is
Active — [`USER_INTERFACE_ARCHITECTURE.md`](../../../docs/architecture/USER_INTERFACE_ARCHITECTURE.md)
§3 — so this slice **implements** that decision and does not re-make it.

Authority: [ADR 0042](../../../docs/decisions/0042-wcag-22-aa-is-the-accessibility-baseline.md)
(**Accepted** 2026-08-15) for the accessibility baseline. Tokens come from Section 15
([ADR 0041](../../../docs/decisions/0041-design-tokens-are-css-custom-properties.md), Accepted).

---

## What this is not

- **Not Section 17.** No responsive or device architecture. No breakpoints.
- **Not Section 18.** No Personal Command Center. The four views show the minimum that proves they
  are reachable, not designed screens.
- **Not Section 43.** No admin or architect surface. Level 5 is not navigable here.
- **Not a router, state library, or application framework.** See the cap below.
- **Not wired to anything.** No control performs an action. Approving approves nothing (`I-09`).

## The cap, and why it is written down

James capped Section 16 explicitly: it may implement scope-path ↔ location mapping, explicit
switching, navigation guards, and switch confirmation — and **may not** implement a routing
framework, a general routing abstraction, a state-management layer, or an application UI framework.
`D-13`'s framework half stays deferred.

The risk is accretion rather than a single decision: a router plus a state layer built by hand *is*
an application framework, arrived at without anyone choosing one. So the cap is enforced by test —
`nav/navigation.js` may not reference history, listeners, stores or subscriptions, and the
demonstration wiring has a line ceiling. A blunt instrument, deliberately.

---

## The model

`nav/navigation.js` is pure functions over `ia/ia_map.json`. The IA map is a **machine-readable
projection** of Section 02 §3, and `test_navigation.py` parses that document and fails if the two
disagree — so the map cannot quietly become a second source of truth.

**The one property worth stating plainly:** navigation offers a location's ancestors and its direct
children, and never a sibling. A move to a sibling is refused as implicit navigation and returned as
requiring an explicit switch (`I-03`;
[`CONTEXT_ARCHITECTURE.md`](../../../docs/architecture/CONTEXT_ARCHITECTURE.md) §144). Switching
changes what is displayed and **grants nothing** — resolving *which* scope is meant is
disambiguation, never authorization.

Where an instruction matches more than one scope and the alternatives differ materially — production
versus staging — NOVA **asks**. It does not ask when alternatives are equivalent in effect
(`CONTEXT_ARCHITECTURE.md` §101).

---

## Running it

```bash
python3 -m unittest slice.ui.section16.tests.test_navigation   # 29 structural tests
node slice/ui/section16/tests/nav_check.mjs                    # 43 render/behaviour checks
```

> The browser path is **pinned to this environment** for the same reason as Section 15's check:
> the installed Playwright pins a newer Chromium build than the image ships. The evidence is real;
> the command is environment-specific.

---

## Validation state

| Level | | |
| --- | --- | --- |
| **DOCUMENTED** | ✅ | The navigation model, the Context Lock UI half (`D-23a`), the design-system dependency, ADR 0042 |
| **IMPLEMENTED** | ✅ | IA map, navigation model, 5 composites, demonstration screen |
| **EXECUTED** | ✅ | 43 checks in a real browser: refused sibling moves, confirmed switches, surfaced ambiguity, persistence across 9 states |
| **SECURITY-TESTED** | ❌ **No** | **The UI enforces nothing.** The PDP enforces scope boundaries |
| **VALIDATED AGAINST A REAL EXTERNAL SYSTEM** | ❌ **No** | A local server and a local browser are not an external system |

**Why the sibling test is not a security test.** It asserts that the interface does not *offer* a
path the policy layer would refuse. That matters — an interface offering unreachable destinations
teaches James that scopes are connected when they are not — but it is a UX-consistency property with
a security-shaped motivation. A navigation model cannot deny anything; `I-03` is enforced below the
query layer.

---

## Accessibility: exactly what was tested

[ADR 0042](../../../docs/decisions/0042-wcag-22-aa-is-the-accessibility-baseline.md) adopts WCAG 2.2
AA as the baseline. **This slice does not claim conformance.** Conformance cannot be established by
automated checks — most criteria need human judgement, and an audit is a different exercise from a
test suite.

**Tested here, by hand, against named criteria:**

| Criterion | What is checked |
| --- | --- |
| 1.3.1 Info and Relationships | `header`/`main` landmarks; every navigation region has an accessible name |
| 2.1.1 Keyboard | All 14 interactive controls are native buttons; a view change works from the keyboard |
| 2.4.1 Bypass Blocks | A skip control exists and is in the tab order |
| 2.4.6 Headings and Labels | The page has a heading |
| 2.4.7 Focus Visible | Focus lands on the control |
| 2.4.11 Focus Not Obscured | A visible outline is computed, not suppressed |
| 4.1.2 Name, Role, Value | Every control has an accessible name; disclosure exposes `aria-expanded`; the context indicator has a role and name |

**Not tested, and therefore not claimed:** colour contrast ratios (1.4.3, 1.4.11), target size
(2.5.8), reflow (1.4.10 — Section 17), consistent help (3.2.6), redundant entry (3.3.7), motion
preferences, screen-reader announcement quality, and focus *order* as opposed to focus visibility.

**Three Section 15 components were corrected** to meet the baseline. `nova-area-nav` and
`nova-disclosure` had click handlers on non-interactive elements, which is not keyboard operable;
both are now native buttons with state exposed through ARIA. `nova-context-bar` had no accessible
name, which matters because
[`USER_INTERFACE_ARCHITECTURE.md`](../../../docs/architecture/USER_INTERFACE_ARCHITECTURE.md) §5
makes the context indicator a **safety** surface — visible but unannounced is invisible to a
screen-reader user. ADR 0041 records that Section 16 may change Section 15's demonstration
components freely; the token architecture is untouched.
