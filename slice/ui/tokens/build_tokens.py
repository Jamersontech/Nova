"""Generate tokens.css from tokens.json.

ADR 0041: tokens.json is the single source of truth and CSS custom properties
are the emission format. This generator is deliberately small -- it resolves
references, refuses to guess, and writes a file nobody hand-edits.

The only interesting behaviour is reference resolution. A semantic token holds
"{color.slate.900}", which must name a real primitive. A dangling reference is
a build failure rather than a fallback, because a fallback is exactly how a
design system quietly loses a value: the build succeeds, one surface renders
the wrong colour, and nothing says so.

Run:  python3 -m slice.ui.tokens.build_tokens
"""

from __future__ import annotations

import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).parent
SOURCE = HERE / "tokens.json"
OUTPUT = HERE / "tokens.css"

REF = re.compile(r"^\{([a-z0-9_.-]+)\}$", re.I)
PREFIX = "--nova"


class TokenError(Exception):
    """A token source that cannot be resolved. Never recovered from."""


def _flatten(node, path=()):
    """Depth-first walk yielding (dotted-path, value) for every leaf string."""
    for key, value in node.items():
        if key.startswith("$"):          # $comment and friends are not tokens
            continue
        here = path + (key,)
        if isinstance(value, dict):
            yield from _flatten(value, here)
        elif isinstance(value, str):
            yield ".".join(here), value
        else:
            raise TokenError(
                f"{'.'.join(here)}: token values must be strings, got {type(value).__name__}"
            )


def _css_name(dotted: str) -> str:
    return f"{PREFIX}-" + dotted.replace(".", "-")


def load(source: pathlib.Path = SOURCE) -> dict:
    try:
        return json.loads(source.read_text())
    except json.JSONDecodeError as exc:
        raise TokenError(f"{source.name} is not valid JSON: {exc}") from exc


def resolve(doc: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Return (primitives, semantics) as dotted-path -> literal value.

    Semantics are resolved against primitives. A semantic may also hold a
    literal, but every {reference} must name a primitive that exists.
    """
    if "primitive" not in doc or "semantic" not in doc:
        raise TokenError("tokens.json must define both 'primitive' and 'semantic'")

    primitives = dict(_flatten(doc["primitive"]))
    semantics: dict[str, str] = {}

    for dotted, raw in _flatten(doc["semantic"]):
        match = REF.match(raw.strip())
        if match is None:
            # A literal in the semantic tier is allowed but is a smell: it means
            # a value exists that the primitive tier does not know about.
            semantics[dotted] = raw
            continue
        target = match.group(1)
        if target not in primitives:
            raise TokenError(
                f"semantic token '{dotted}' references '{target}', "
                f"which is not a primitive token"
            )
        semantics[dotted] = primitives[target]

    return primitives, semantics


def render_css(primitives: dict[str, str], semantics: dict[str, str]) -> str:
    lines = [
        "/* GENERATED FILE -- do not edit.",
        " * Source: slice/ui/tokens/tokens.json",
        " * Regenerate: python3 -m slice.ui.tokens.build_tokens",
        " *",
        " * Custom properties are inherited, and inheritance crosses Shadow DOM",
        " * boundaries. That is why a change here reaches every component without",
        " * the components being rebuilt or re-registered (ADR 0041).",
        " */",
        ":root {",
        "  /* ---- primitive tier: raw values ---- */",
    ]
    for dotted in sorted(primitives):
        lines.append(f"  {_css_name('primitive.' + dotted)}: {primitives[dotted]};")

    lines.append("")
    lines.append("  /* ---- semantic tier: what components consume ---- */")
    for dotted in sorted(semantics):
        lines.append(f"  {_css_name(dotted)}: {semantics[dotted]};")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def build(source: pathlib.Path = SOURCE, output: pathlib.Path = OUTPUT) -> str:
    primitives, semantics = resolve(load(source))
    css = render_css(primitives, semantics)
    output.write_text(css)
    return css


def main() -> int:
    try:
        css = build()
    except TokenError as exc:
        print(f"token build FAILED: {exc}", file=sys.stderr)
        return 1
    count = css.count(f"  {PREFIX}-")
    print(f"wrote {OUTPUT.relative_to(pathlib.Path.cwd())} -- {count} custom properties")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
