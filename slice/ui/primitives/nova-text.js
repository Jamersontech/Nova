// nova-text -- the typography primitive.
// Every piece of text in the demonstration goes through this element, so the
// type ramp has exactly one definition.

import { NovaElement, defineElement, pick } from "./base.js";

const SIZES = ["caption", "body", "lead", "title", "display"];
const WEIGHTS = ["normal", "medium", "strong"];
const TONES = ["primary", "secondary", "muted", "oncolor"];

class NovaText extends NovaElement {
  static observedAttributes = ["size", "weight", "tone", "tracking"];

  render() {
    const size = pick(this, "size", SIZES, "body");
    const weight = pick(this, "weight", WEIGHTS, "normal");
    const tone = pick(this, "tone", TONES, "primary");
    const tracking = pick(this, "tracking", ["normal", "label"], "normal");
    const uppercase = tracking === "label";

    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-${size});
          font-weight: var(--nova-type-weight-${weight});
          line-height: var(--nova-type-leading-normal);
          letter-spacing: var(--nova-type-tracking-${tracking});
          color: var(--nova-color-text-${tone});
          text-transform: ${uppercase ? "uppercase" : "none"};
          margin: 0;
        }
        :host([inline]) { display: inline; }
      </style>
      <slot></slot>
    `;
  }
}

defineElement("nova-text", NovaText);
