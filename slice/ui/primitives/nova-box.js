// nova-box -- the surface and layout primitive.
// Owns padding, background, border, radius, elevation and stacking so that no
// composite and no screen ever declares them.

import { NovaElement, defineElement, pick } from "./base.js";

const SURFACES = ["base", "raised", "inset", "hover"];
const PADS = ["tight", "snug", "gutter", "roomy", "section"];
const RADII = ["control", "panel", "card", "pill"];
const BORDERS = ["none", "subtle", "strong", "accent"];
const ELEVATIONS = ["flat", "panel", "modal"];
const GAPS = ["tight", "snug", "gutter", "roomy", "section"];

class NovaBox extends NovaElement {
  static observedAttributes = [
    "surface", "pad", "radius", "border", "elevation", "direction", "gap", "align", "justify",
  ];

  render() {
    const surface = pick(this, "surface", SURFACES, "base");
    const pad = pick(this, "pad", PADS, "gutter");
    const radius = pick(this, "radius", RADII, "panel");
    const border = pick(this, "border", BORDERS, "none");
    const elevation = pick(this, "elevation", ELEVATIONS, "flat");
    const direction = pick(this, "direction", ["row", "column"], "column");
    const gap = pick(this, "gap", GAPS, "gutter");
    const align = pick(this, "align", ["start", "center", "stretch", "baseline"], "stretch");
    const justify = pick(this, "justify", ["start", "center", "space-between", "end"], "start");

    const borderRule =
      border === "none"
        ? "border: none;"
        : `border: var(--nova-border-width) solid var(--nova-color-border-${border});`;

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: flex;
          flex-direction: ${direction};
          gap: var(--nova-space-${gap});
          align-items: ${align};
          justify-content: ${justify};
          padding: var(--nova-space-${pad});
          background: var(--nova-color-surface-${surface});
          border-radius: var(--nova-radius-${radius});
          box-shadow: var(--nova-elevation-${elevation});
          ${borderRule}
          box-sizing: border-box;
        }
        :host([bare]) { padding: var(--nova-space-tight); background: none; }
        :host([grow]) { flex: 1; }
      </style>
      <slot></slot>
    `;
  }
}

defineElement("nova-box", NovaBox);
