// nova-button -- the action primitive.
//
// A button here is presentation only. It carries no authority: pressing one in
// this demonstration records nothing and approves nothing. I-09 places approval
// authority with James alone, and nothing in a component may imply otherwise.

import { NovaElement, defineElement, pick } from "./base.js";

const VARIANTS = ["primary", "quiet", "danger"];

// Per variant: background, text colour, border colour.
const SURFACE = {
  primary: ["var(--nova-color-accent-base)", "var(--nova-color-text-oncolor)", "var(--nova-color-accent-base)"],
  quiet: ["var(--nova-color-surface-inset)", "var(--nova-color-text-secondary)", "var(--nova-color-border-strong)"],
  danger: ["var(--nova-color-stop-soft)", "var(--nova-color-stop-base)", "var(--nova-color-stop-base)"],
};

class NovaButton extends NovaElement {
  static observedAttributes = ["variant", "full"];

  render() {
    const variant = pick(this, "variant", VARIANTS, "quiet");
    const [background, color, borderColor] = SURFACE[variant];

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: inline-flex; }
        :host([full]) { display: flex; }
        button {
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-body);
          font-weight: var(--nova-type-weight-medium);
          line-height: var(--nova-type-leading-tight);
          color: ${color};
          background: ${background};
          border: var(--nova-border-width) solid ${borderColor};
          border-radius: var(--nova-radius-control);
          padding: var(--nova-space-tight) var(--nova-space-gutter);
          cursor: pointer;
          width: 100%;
          transition: background var(--nova-motion-duration) var(--nova-motion-ease),
                      border-color var(--nova-motion-duration) var(--nova-motion-ease);
        }
        button:hover { background: var(--nova-color-surface-hover); }
        button:focus-visible {
          outline: var(--nova-border-emphasis) solid var(--nova-color-border-accent);
          outline-offset: var(--nova-space-tight);
        }
      </style>
      <button part="button" type="button"><slot></slot></button>
    `;
  }
}

defineElement("nova-button", NovaButton);
