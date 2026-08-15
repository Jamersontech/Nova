// Shared plumbing for NOVA primitives (ADR 0041).
//
// Every component here follows one rule: it reads visual values from
// `var(--nova-*)` and declares none of its own. That rule is what makes
// DESIGN_PRINCIPLES.md section 6's layering checkable rather than aspirational,
// and slice/ui/tests/test_tokens.py enforces it by scanning these files.
//
// Custom properties are inherited and cross the shadow boundary, so a component
// picks up a token change with no re-registration and no rebuild.

export function defineElement(name, ElementClass) {
  if (!customElements.get(name)) {
    customElements.define(name, ElementClass);
  }
}

// Reads an attribute, falling back to a default, and constrains it to a known
// set. An unknown value falls back rather than emitting an undefined custom
// property -- a var() typo renders as "nothing", which is the silent failure
// this design system exists to prevent.
export function pick(el, attr, allowed, fallback) {
  const value = el.getAttribute(attr);
  return allowed.includes(value) ? value : fallback;
}

export class NovaElement extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  connectedCallback() {
    this.render();
  }

  attributeChangedCallback() {
    if (this.shadowRoot) this.render();
  }

  // Subclasses implement render(). Kept explicit rather than templated so the
  // token references stay greppable by the enforcement test.
  render() {}
}
