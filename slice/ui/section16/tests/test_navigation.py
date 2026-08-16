"""Section 16 structural tests -- IA, navigation model, containment.

These read source and the governing documents. The rendered behaviour is in
nav_check.mjs, which needs a browser.

NOTHING HERE IS A SECURITY TEST. The UI enforces no boundary; the PDP does.
What these assert is that the interface does not *offer* a path the policy layer
would refuse -- an interface that offers unreachable destinations teaches James
that scopes are connected when they are not. That is a UX-consistency property
with a security-shaped motivation, and calling it security testing would be the
overclaim this programme exists to avoid.

Run:  python3 -m unittest slice.ui.section16.tests.test_navigation
"""

from __future__ import annotations

import json
import pathlib
import re
import unittest

S16 = pathlib.Path(__file__).resolve().parent.parent
UI = S16.parent
DOCS = UI.parent.parent / "docs"

IA_MAP = json.loads((S16 / "ia" / "ia_map.json").read_text())
NAV_JS = (S16 / "nav" / "navigation.js").read_text()
UI_ARCH = (DOCS / "architecture" / "USER_INTERFACE_ARCHITECTURE.md").read_text()
CONTEXT_ARCH = (DOCS / "architecture" / "CONTEXT_ARCHITECTURE.md").read_text()

COMPOSITES = sorted((S16 / "composites").glob("*.js"))
SCREEN = S16 / "demo" / "index.html"
APP = S16 / "demo" / "app.js"

HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")
LENGTH = re.compile(r"(?<![\w-])\d*\.?\d+(px|rem|em|pt)\b")
VAR_USE = re.compile(r"var\((--nova-[a-z0-9-]+)\)")


def ui_arch_capability_rows():
    """Parse section 3's capability table -- the accepted source of the IA."""
    section = UI_ARCH.split("## 3. Reaching Everything Else")[1].split("## 4.")[0]
    rows = []
    for line in section.splitlines():
        m = re.match(r"\|\s*\*\*(.+?)\*\*\s*\|\s*(.+?)\s*\|$", line.strip())
        if m:
            rows.append((m.group(1), m.group(2)))
    return rows


# ---------------------------------------------------------------------------


class TestIAMatchesGoverningDocument(unittest.TestCase):
    """The IA map is a projection of Section 02, not a second source of truth."""

    def setUp(self):
        self.rows = ui_arch_capability_rows()

    def test_the_table_was_actually_parsed(self):
        self.assertGreaterEqual(len(self.rows), 10, "capability table not found or changed shape")

    def test_every_documented_capability_is_in_the_map(self):
        for name, _ in self.rows:
            with self.subTest(capability=name):
                self.assertIn(name, IA_MAP["capabilities"])

    def test_no_capability_was_invented(self):
        documented = {n for n, _ in self.rows}
        for name in IA_MAP["capabilities"]:
            with self.subTest(capability=name):
                self.assertIn(name, documented, f"{name} is not in the governing table")

    def test_the_non_navigable_row_is_marked_non_navigable(self):
        """Agents, tools, integrations, memory and workflows have no location."""
        for name, reached in self.rows:
            if "Not user-facing navigation" in reached:
                with self.subTest(capability=name):
                    self.assertFalse(IA_MAP["capabilities"][name]["navigable"])

    def test_three_areas_and_no_fourth(self):
        self.assertEqual(["life", "business", "wealth"], IA_MAP["areas"])
        self.assertRegex(re.sub(r"[\s*]+", " ", UI_ARCH), r"never adds a fourth")

    def test_scope_roots_are_exactly_the_areas(self):
        roots = {k for k in IA_MAP["scopes"] if not k.startswith("$")}
        self.assertEqual(set(IA_MAP["areas"]), roots)


class TestNavigationModel(unittest.TestCase):
    """Pure structure over the map -- the same rules navigation.js implements."""

    def paths(self, node=None, prefix=()):
        node = IA_MAP["scopes"] if node is None else node
        for key, value in node.items():
            if key.startswith("$"):        # documentation, not a scope
                continue
            here = prefix + (key,)
            yield here
            if isinstance(value, dict) and "children" in value:
                yield from self.paths(value["children"], here)

    def offers(self, at):
        """Ancestors and direct children only -- mirrors navigationOffers()."""
        out = [at[: i + 1] for i in range(len(at) - 1)]
        node = IA_MAP["scopes"]
        for seg in at:
            node = node[seg].get("children", {}) if seg in node else {}
        out += [tuple(at) + (k,) for k in node if not k.startswith("$")]
        return [tuple(o) for o in out]

    def test_no_location_offers_a_sibling(self):
        """The central property. I-03; CONTEXT_ARCHITECTURE.md section 144."""
        for at in self.paths():
            for offer in self.offers(list(at)):
                with self.subTest(at="/".join(at), offer="/".join(offer)):
                    is_ancestor = len(offer) < len(at) and at[: len(offer)] == offer
                    is_child = len(offer) == len(at) + 1 and offer[: len(at)] == at
                    self.assertTrue(
                        is_ancestor or is_child,
                        "navigation offered something that is neither ancestor nor child",
                    )

    def test_sibling_scopes_exist_to_make_the_test_meaningful(self):
        """Guard: a tree without siblings would pass the above vacuously."""
        clients = IA_MAP["scopes"]["business"]["children"]["kairo"]["children"]
        self.assertIn("client-a", clients)
        self.assertIn("client-b", clients)

    def test_no_cross_area_path_is_constructible(self):
        for at in self.paths():
            for offer in self.offers(list(at)):
                if offer and at:
                    with self.subTest(at="/".join(at)):
                        self.assertEqual(at[0], offer[0], "navigation crossed a top-level area")

    def test_material_siblings_are_marked(self):
        """Production and staging differ materially -- CONTEXT section 101."""
        website = (IA_MAP["scopes"]["business"]["children"]["kairo"]
                   ["children"]["client-a"]["children"]["website"]["children"])
        self.assertTrue(website["production"]["material"])
        self.assertTrue(website["staging"]["material"])

    def test_switch_relation_is_the_refusal_path(self):
        self.assertIn("NEEDS_EXPLICIT_SWITCH", NAV_JS)
        self.assertIn("I-03", NAV_JS)
        self.assertRegex(NAV_JS, r"CONTEXT_ARCHITECTURE\.md section 144")

    def test_switching_grants_nothing(self):
        self.assertIn("grantsNothing", NAV_JS)
        self.assertIn("authorizes nothing", NAV_JS)

    def test_ask_never_guess_is_implemented(self):
        self.assertIn("resolveIntent", NAV_JS)
        self.assertIn("AMBIGUOUS", NAV_JS)
        self.assertIn("Ask. Never silently switch", CONTEXT_ARCH)


class TestScopeCapHolds(unittest.TestCase):
    """James's Section 16 cap: no framework, no router, no state library."""

    def test_no_application_framework_dependency(self):
        pkg = json.loads((UI / "package.json").read_text())
        self.assertEqual({}, pkg.get("dependencies", {}), "the slice must ship nothing")
        for name in pkg.get("devDependencies", {}):
            with self.subTest(dep=name):
                self.assertNotRegex(name, r"react|vue|svelte|solid|angular|preact|lit")

    def test_no_routing_or_state_library_imported(self):
        for path in COMPOSITES + [APP, S16 / "nav" / "navigation.js"]:
            for spec in re.findall(r'import\s+.*?["\'](.+?)["\']', path.read_text()):
                with self.subTest(file=path.name, imported=spec):
                    self.assertTrue(
                        spec.startswith("."),
                        f"{path.name} imports a package: {spec}",
                    )

    def test_navigation_model_stays_a_pure_module(self):
        """No history integration, no registry, no subscriptions."""
        for forbidden in ("history.pushState", "addEventListener", "window.location",
                          "createStore", "subscribe(", "registerRoute"):
            with self.subTest(construct=forbidden):
                self.assertNotIn(forbidden, NAV_JS)

    def test_app_wiring_stays_small(self):
        """A size ceiling is a blunt instrument, and that is the point."""
        lines = [l for l in APP.read_text().splitlines() if l.strip() and not l.strip().startswith("//")]
        self.assertLess(len(lines), 130, "demo wiring is growing into a framework")


class TestScreenDeclaresNoVisualValues(unittest.TestCase):
    """Section 15's rule, applied to Section 16's screen."""

    def setUp(self):
        self.body = re.sub(r"<!--.*?-->", "", SCREEN.read_text(), flags=re.S)

    def test_no_style_block_or_attribute(self):
        self.assertNotIn("<style", self.body)
        self.assertNotRegex(self.body, r"\sstyle\s*=")

    def test_no_hex_or_length(self):
        self.assertEqual([], HEX.findall(self.body))
        self.assertEqual([], [m.group(0) for m in LENGTH.finditer(self.body)])

    def test_no_class_hook(self):
        self.assertNotRegex(self.body, r"\sclass\s*=")

    def test_composes_composites_only(self):
        used = set(re.findall(r"<(nova-[a-z-]+)", self.body))
        available = {p.stem for p in COMPOSITES} | {p.stem for p in (UI / "composites").glob("*.js")}
        self.assertTrue(used)
        self.assertTrue(used <= available, f"non-composite elements: {sorted(used - available)}")

    def test_uses_the_generated_stylesheet(self):
        self.assertIn("tokens.css", self.body)


class TestComponentsConsumeTokens(unittest.TestCase):

    def test_no_hard_coded_visual_values(self):
        for path in COMPOSITES:
            with self.subTest(component=path.name):
                src = path.read_text()
                self.assertEqual([], HEX.findall(src), f"{path.name} hard-codes a colour")
                self.assertEqual([], [m.group(0) for m in LENGTH.finditer(src)],
                                 f"{path.name} hard-codes a length")

    def test_every_token_reference_exists(self):
        declared = set(re.findall(r"^\s*(--nova-[a-z0-9-]+):",
                                  (UI / "tokens" / "tokens.css").read_text(), re.M))
        for path in COMPOSITES:
            for ref in VAR_USE.findall(path.read_text()):
                with self.subTest(component=path.name, token=ref):
                    self.assertIn(ref, declared)

    def test_no_component_reaches_past_the_semantic_tier(self):
        for path in COMPOSITES:
            for ref in VAR_USE.findall(path.read_text()):
                with self.subTest(component=path.name, token=ref):
                    self.assertFalse(ref.startswith("--nova-primitive-"))


class TestContainmentOfProposedArchitecture(unittest.TestCase):
    """ADR 0040 is Proposed. Nothing in Section 16 may depend on it."""

    def all_source(self):
        return "\n".join(
            p.read_text() for p in
            COMPOSITES + [APP, SCREEN, S16 / "nav" / "navigation.js"]
        )

    def test_no_adr_0040_only_semantics(self):
        for proposed_only in ("step-up", "step up", "session strength", "session-strength",
                              "voiceprint", "biometric"):
            with self.subTest(term=proposed_only):
                self.assertNotIn(proposed_only, self.all_source().lower())

    def test_no_voice_automation_or_communication_implementation(self):
        src = self.all_source().lower()
        for term in ("speechrecognition", "webkitspeech", "automation.run",
                     "sendmail", "smtp", "twilio"):
            with self.subTest(term=term):
                self.assertNotIn(term, src)

    def test_no_authentication_or_authorization_logic(self):
        src = self.all_source().lower()
        for term in ("authenticate", "authorize(", "grantpermission", "issuetoken"):
            with self.subTest(term=term):
                self.assertNotIn(term, src)

    def test_approval_authority_is_not_implied_by_section_16(self):
        """I-09. Section 16 reuses Section 15's card and adds no approval path."""
        card = (UI / "composites" / "nova-approval-card.js").read_text()
        self.assertIn("Only James can approve", card)
        self.assertNotIn("approve(", self.all_source())


if __name__ == "__main__":
    unittest.main()
