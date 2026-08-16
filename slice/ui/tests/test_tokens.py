"""Section 15 design-system enforcement tests.

These make DESIGN_PRINCIPLES.md section 6's layering checkable. The rule
"screens compose components; they do not define their own visual values" is
only worth stating if something fails when it is broken -- otherwise a
hard-coded colour looks correct right up until the day the token changes and
one surface does not move with it.

These are STRUCTURAL tests over source. They are not security tests: nothing
here defends a boundary, and a colour has no threat model. The rendering
evidence lives in render_check.mjs, which needs a real browser.

Run:  python3 -m unittest slice.ui.tests.test_tokens
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

from ..tokens import build_tokens

UI = pathlib.Path(__file__).resolve().parent.parent
TOKENS_JSON = UI / "tokens" / "tokens.json"
TOKENS_CSS = UI / "tokens" / "tokens.css"
PRIMITIVES = sorted((UI / "primitives").glob("*.js"))
COMPOSITES = sorted((UI / "composites").glob("*.js"))
DEMO = UI / "demo" / "index.html"

# A six- or three-digit hex colour. The one thing a component may never contain.
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
# A raw length. 0, 100%, and grid fractions are not lengths in this sense.
LENGTH = re.compile(r"(?<![\w-])\d*\.?\d+(px|rem|em|pt)\b")
VAR_USE = re.compile(r"var\((--nova-[a-z0-9-]+)\)")
CSS_DECL = re.compile(r"^\s*(--nova-[a-z0-9-]+):", re.M)


def sources(paths):
    return [(p.name, p.read_text()) for p in paths]


class TestTokenSource(unittest.TestCase):
    """The source of truth is well-formed and complete."""

    def test_tokens_json_has_both_tiers(self):
        doc = json.loads(TOKENS_JSON.read_text())
        self.assertIn("primitive", doc)
        self.assertIn("semantic", doc)

    def test_every_semantic_reference_resolves(self):
        # resolve() raises TokenError on a dangling reference.
        primitives, semantics = build_tokens.resolve(build_tokens.load(TOKENS_JSON))
        self.assertGreater(len(primitives), 0)
        self.assertGreater(len(semantics), 0)

    def test_dangling_reference_is_a_build_failure(self):
        """The negative case. A fallback here is how a design system loses a value."""
        broken = {
            "primitive": {"color": {"red": "#ff0000"}},
            "semantic": {"color": {"danger": "{color.does.not.exist}"}},
        }
        with self.assertRaises(build_tokens.TokenError) as ctx:
            build_tokens.resolve(broken)
        self.assertIn("does.not.exist", str(ctx.exception))

    def test_non_string_token_is_rejected(self):
        broken = {"primitive": {"space": {"gutter": 16}}, "semantic": {}}
        with self.assertRaises(build_tokens.TokenError):
            build_tokens.resolve(broken)

    def test_generated_css_is_current(self):
        """tokens.css must be what tokens.json currently produces.

        Includes the Section 17 responsive bands: a stale band would mean one
        viewport rendering from a value the source no longer declares.
        """
        doc = build_tokens.load(TOKENS_JSON)
        primitives, semantics = build_tokens.resolve(doc)
        bands = build_tokens.resolve_responsive(doc, primitives, semantics)
        expected = build_tokens.render_css(primitives, semantics, bands)
        self.assertEqual(
            expected,
            TOKENS_CSS.read_text(),
            "tokens.css is stale -- run python3 -m slice.ui.tokens.build_tokens",
        )


class TestComponentsConsumeTokens(unittest.TestCase):
    """A component reads visual values. It never declares them."""

    def test_no_component_contains_a_hex_colour(self):
        for name, src in sources(PRIMITIVES + COMPOSITES):
            with self.subTest(component=name):
                self.assertEqual([], HEX.findall(src), f"{name} hard-codes a colour")

    def test_no_component_contains_a_raw_length(self):
        for name, src in sources(PRIMITIVES + COMPOSITES):
            with self.subTest(component=name):
                found = [m.group(0) for m in LENGTH.finditer(src)]
                self.assertEqual([], found, f"{name} hard-codes a length")

    def test_every_token_reference_exists(self):
        """Requirement G. A var() typo renders as nothing -- silently."""
        declared = set(CSS_DECL.findall(TOKENS_CSS.read_text()))
        self.assertGreater(len(declared), 0)
        for name, src in sources(PRIMITIVES + COMPOSITES):
            for ref in VAR_USE.findall(src):
                with self.subTest(component=name, token=ref):
                    self.assertIn(ref, declared, f"{name} references undefined {ref}")

    def test_components_reference_semantic_tokens_not_primitives(self):
        """The indirection is the point: a palette change must not touch a component."""
        for name, src in sources(PRIMITIVES + COMPOSITES):
            for ref in VAR_USE.findall(src):
                with self.subTest(component=name, token=ref):
                    self.assertFalse(
                        ref.startswith("--nova-primitive-"),
                        f"{name} reaches past the semantic tier to {ref}",
                    )

    def test_every_primitive_actually_uses_tokens(self):
        for path in PRIMITIVES:
            if path.name == "base.js":
                continue
            with self.subTest(component=path.name):
                self.assertTrue(VAR_USE.search(path.read_text()))

    def test_every_composite_imports_a_primitive(self):
        """Requirement C, structurally: composites are built from primitives."""
        for path in COMPOSITES:
            with self.subTest(component=path.name):
                self.assertRegex(
                    path.read_text(),
                    r'import\s+"\.\./primitives/',
                    f"{path.name} does not compose any primitive",
                )


class TestDemoScreenDeclaresNoVisualValues(unittest.TestCase):
    """Requirement E. The screen composes; it does not design."""

    def setUp(self):
        self.src = DEMO.read_text()
        # Comments explain the file's purpose and are not rendered output.
        self.body = re.sub(r"<!--.*?-->", "", self.src, flags=re.S)

    def test_no_style_block(self):
        self.assertNotIn("<style", self.body)

    def test_no_inline_style_attribute(self):
        self.assertNotRegex(self.body, r"\sstyle\s*=")

    def test_no_hex_colour(self):
        self.assertEqual([], HEX.findall(self.body))

    def test_no_raw_length(self):
        self.assertEqual([], [m.group(0) for m in LENGTH.finditer(self.body)])

    def test_no_class_attribute(self):
        """A class hook would be a visual system growing back on the screen."""
        self.assertNotRegex(self.body, r"\sclass\s*=")

    def test_composes_composites_only(self):
        """The screen reaches for composites, never primitives directly."""
        used = set(re.findall(r"<(nova-[a-z-]+)", self.body))
        composite_names = {"nova-" + p.stem.replace("nova-", "") for p in COMPOSITES}
        self.assertTrue(used)
        self.assertTrue(
            used <= composite_names,
            f"screen uses non-composite elements: {sorted(used - composite_names)}",
        )

    def test_links_the_generated_stylesheet(self):
        self.assertIn("tokens.css", self.body)


class TestAcceptedArchitectureIsRepresented(unittest.TestCase):
    """The demonstration must exercise the properties UI ARCH section 8 protects.

    These assert the demonstration COVERS the required surface. They are not
    claims that the architecture is enforced -- a component cannot enforce
    anything.
    """

    def setUp(self):
        self.demo = DEMO.read_text()
        self.composites = {p.name: p.read_text() for p in COMPOSITES}

    def test_three_top_level_areas_and_no_fourth(self):
        nav = self.composites["nova-area-nav.js"]
        declared = re.findall(r'"(\w+)"', re.search(r"const AREAS = \[(.*?)\]", nav).group(1))
        self.assertEqual(["life", "business", "wealth"], declared)

    def test_active_context_is_present(self):
        self.assertIn("<nova-context-bar", self.demo)

    def test_emergency_stop_is_present(self):
        self.assertIn("<nova-stop", self.demo)

    def test_progressive_disclosure_is_present_and_closed_by_default(self):
        self.assertIn("<nova-disclosure", self.demo)
        disclosure = self.composites["nova-disclosure.js"]
        self.assertIn('this.hasAttribute("open")', disclosure)

    def test_risk_classes_match_permission_architecture(self):
        card = self.composites["nova-approval-card.js"]
        for cls in ("READ", "ANALYZE", "RECOMMEND", "PREPARE",
                    "EXECUTE", "HIGH-IMPACT EXECUTE", "IRREVERSIBLE"):
            self.assertIn(cls, card, f"risk class {cls} missing")

    def test_approval_states_all_five_required_facts(self):
        card = self.composites["nova-approval-card.js"]
        for label in ("in scope", "why approval is needed",
                      "what it costs", "if this is wrong"):
            self.assertIn(label, card)
        self.assertIn("action", card)

    def test_approval_never_implies_nova_is_the_authority(self):
        """I-09 read into presentation: only James approves."""
        card = self.composites["nova-approval-card.js"]
        self.assertIn("Only James can approve", card)
        self.assertIn("it cannot approve it", card)

    def test_demo_presents_both_a_contextual_and_an_explicit_approval(self):
        self.assertIn('risk="EXECUTE"', self.demo)
        self.assertIn('risk="IRREVERSIBLE"', self.demo)

    def test_no_adr_0040_behaviour_is_implemented(self):
        """ADR 0040 is Proposed. Nothing may depend on it."""
        card = self.composites["nova-approval-card.js"]
        for proposed_only in ("step-up", "session strength", "voice", "biometric"):
            self.assertNotIn(
                proposed_only,
                card.split("// I-09")[-1],
                f"approval card implements ADR 0040 behaviour: {proposed_only}",
            )


if __name__ == "__main__":
    unittest.main()
