"""Section 17 structural tests -- responsive tokens and the CSS/JS boundary.

These read source. The rendered behaviour is in viewport_check.mjs, which needs
a real browser at real viewport sizes.

NOTHING HERE IS A SECURITY TEST. Layout enforces nothing. The reachability
checks assert that a narrow viewport does not hide the emergency stop or the
approvals route -- a regression that would breach
USER_INTERFACE_ARCHITECTURE.md sections 6-7 through layout alone. That is a
presentation property, not a control.

Run:  python3 -m unittest slice.ui.section17.tests.test_responsive
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

S17 = pathlib.Path(__file__).resolve().parent.parent
UI = S17.parent
S16 = UI / "section16"

TOKENS_JSON = json.loads((UI / "tokens" / "tokens.json").read_text())
TOKENS_CSS = (UI / "tokens" / "tokens.css").read_text()

# Every component and screen the slice renders, across all three sections.
COMPONENTS = sorted(
    list((UI / "primitives").glob("*.js"))
    + list((UI / "composites").glob("*.js"))
    + list((S16 / "composites").glob("*.js"))
)
SCREENS = [UI / "demo" / "index.html", S16 / "demo" / "index.html"]
APP_JS = [S16 / "demo" / "app.js"]
NAV_JS = S16 / "nav" / "navigation.js"

MEDIA_BLOCK = re.compile(r"@media \(max-width: (\d+)px\) \{\s*:root \{(.*?)\}\s*\}", re.S)
DECL = re.compile(r"(--nova-[a-z0-9-]+):")


class TestResponsiveTokenTier(unittest.TestCase):
    """The responsive tier is part of the token system, not a parallel one."""

    def setUp(self):
        self.responsive = TOKENS_JSON["responsive"]
        self.semantic_paths = set(self._flatten(TOKENS_JSON["semantic"]))

    def _flatten(self, node, prefix=()):
        for key, value in node.items():
            if key.startswith("$"):
                continue
            here = prefix + (key,)
            if isinstance(value, dict):
                yield from self._flatten(value, here)
            else:
                yield ".".join(here)

    def test_tokens_json_remains_the_source_of_truth(self):
        self.assertIn("primitive", TOKENS_JSON)
        self.assertIn("semantic", TOKENS_JSON)
        self.assertIn("responsive", TOKENS_JSON)

    def test_breakpoints_are_declared_in_one_place(self):
        bps = self.responsive["breakpoints"]
        self.assertTrue(bps)
        for band, width in bps.items():
            with self.subTest(band=band):
                self.assertRegex(width, r"^\d+px$")

    def test_the_scale_is_minimal(self):
        """Two breakpoints -> three bands. More would be unrequired architecture."""
        bps = {k: v for k, v in self.responsive["breakpoints"].items() if not k.startswith("$")}
        self.assertEqual(2, len(bps), f"breakpoint scale grew: {sorted(bps)}")

    def test_every_band_has_an_override_block(self):
        for band in self.responsive["breakpoints"]:
            with self.subTest(band=band):
                self.assertIn(band, self.responsive)

    def test_bands_only_override_declared_semantic_tokens(self):
        """A band cannot invent a token that exists at one viewport and nowhere else."""
        for band in self.responsive["breakpoints"]:
            for dotted in self.responsive[band]:
                if dotted.startswith("$"):
                    continue
                with self.subTest(band=band, token=dotted):
                    self.assertIn(dotted, self.semantic_paths)

    def test_bands_never_override_primitives(self):
        for band in self.responsive["breakpoints"]:
            for dotted in self.responsive[band]:
                with self.subTest(band=band, token=dotted):
                    self.assertFalse(dotted.startswith("primitive."))

    def test_narrow_band_is_below_the_wcag_test_width(self):
        """320 CSS px is WCAG 1.4.10's test condition, so a band must cover it."""
        widths = [int(w.rstrip("px")) for w in self.responsive["breakpoints"].values()]
        self.assertTrue(any(w >= 320 for w in widths),
                        "no band applies at the 320px reflow test width")


class TestGeneratedCSS(unittest.TestCase):

    def test_media_blocks_were_emitted(self):
        self.assertEqual(2, len(MEDIA_BLOCK.findall(TOKENS_CSS)))

    def test_bands_are_emitted_widest_first(self):
        widths = [int(w) for w, _ in MEDIA_BLOCK.findall(TOKENS_CSS)]
        self.assertEqual(sorted(widths, reverse=True), widths,
                         "a wider band emitted after a narrower one would override it")

    def test_every_responsive_declaration_exists_in_the_base(self):
        """An override must refine a base value, never introduce one."""
        base = set(DECL.findall(TOKENS_CSS.split("@media")[0]))
        for _, body in MEDIA_BLOCK.findall(TOKENS_CSS):
            for name in DECL.findall(body):
                with self.subTest(token=name):
                    self.assertIn(name, base)

    def test_layout_columns_is_tokenised(self):
        self.assertIn("--nova-layout-columns:", TOKENS_CSS)

    def test_control_target_is_tokenised(self):
        self.assertIn("--nova-control-target:", TOKENS_CSS)


class TestCSSJavaScriptBoundary(unittest.TestCase):
    """James's Section 17 cap: CSS computes layout, JavaScript does not.

    Mechanically detectable, because the failure mode is gradual. A single
    ResizeObserver is reasonable in isolation; a responsive state system is what
    it becomes, and by then Web Components have quietly acquired a layout engine.
    """

    FORBIDDEN = [
        "ResizeObserver",
        "matchMedia",
        "window.innerWidth",
        "window.innerHeight",
        "clientWidth",
        "offsetWidth",
        "getBoundingClientRect",
        "screen.width",
        "orientationchange",
        "visualViewport",
        "navigator.userAgent",
        "navigator.maxTouchPoints",
    ]

    def sources(self):
        return [(p.name, p.read_text()) for p in COMPONENTS + APP_JS + [NAV_JS]]

    def test_no_javascript_reads_viewport_geometry(self):
        for name, src in self.sources():
            for construct in self.FORBIDDEN:
                with self.subTest(file=name, construct=construct):
                    self.assertNotIn(construct, src,
                                     f"{name} computes layout in JavaScript via {construct}")

    def test_no_breakpoint_values_appear_outside_the_token_source(self):
        """A breakpoint literal in a component is a second source of truth."""
        widths = [w.rstrip("px") for w in TOKENS_JSON["responsive"]["breakpoints"].values()]
        for name, src in self.sources():
            for width in widths:
                with self.subTest(file=name, width=width):
                    self.assertNotIn(width, src)

    def test_no_device_detection(self):
        for name, src in self.sources():
            with self.subTest(file=name):
                self.assertNotRegex(src.lower(), r"\bis(mobile|tablet|desktop|touch)\b")

    def test_media_queries_live_only_in_the_generated_stylesheet(self):
        """Components adapt by reading tokens, not by declaring breakpoints."""
        for name, src in self.sources():
            with self.subTest(file=name):
                self.assertNotIn("@media", src)

    def test_no_framework_or_layout_dependency(self):
        pkg = json.loads((UI / "package.json").read_text())
        self.assertEqual({}, pkg.get("dependencies", {}))
        self.assertEqual(["playwright"], list(pkg.get("devDependencies", {})))


class TestScreensStillOwnNoVisualValues(unittest.TestCase):
    """Section 17 must not have pushed responsive values back onto the screens."""

    HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
    LENGTH = re.compile(r"(?<![\w-])\d*\.?\d+(px|rem|em|pt)\b")

    def test_no_screen_declares_a_visual_value(self):
        for screen in SCREENS:
            body = re.sub(r"<!--.*?-->", "", screen.read_text(), flags=re.S)
            with self.subTest(screen=screen.name):
                self.assertNotIn("<style", body)
                self.assertEqual([], self.HEX.findall(body))
                self.assertEqual([], [m.group(0) for m in self.LENGTH.finditer(body)])

    def test_no_component_hard_codes_a_length(self):
        for name, src in [(p.name, p.read_text()) for p in COMPONENTS]:
            with self.subTest(component=name):
                self.assertEqual([], [m.group(0) for m in self.LENGTH.finditer(src)],
                                 f"{name} hard-codes a length")


class TestVisualSurfacesOnly(unittest.TestCase):
    """Section 17 covers desktop, web and mobile. Voice is out of scope."""

    def all_source(self):
        """Executable code only.

        Comments are excluded deliberately: the components *name* the ADR 0040
        semantics they refuse to implement, and that containment note must not
        be what trips the containment test.
        """
        out = []
        for path in COMPONENTS + APP_JS + SCREENS:
            for line in path.read_text().splitlines():
                stripped = line.strip()
                if stripped.startswith(("//", "*", "/*", "<!--")):
                    continue
                out.append(line)
        return "\n".join(out).lower()

    def test_no_voice_implementation(self):
        for term in ("speechrecognition", "webkitspeech", "speechsynthesis", "voiceprint"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.all_source())

    def test_no_adr_0040_session_strength_semantics(self):
        for term in ("step-up", "step up", "session strength", "session-strength"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.all_source())


if __name__ == "__main__":
    unittest.main()
