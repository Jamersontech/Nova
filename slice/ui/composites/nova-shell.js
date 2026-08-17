// nova-shell -- the layout owner.
//
// This composite exists so the demonstration screen can declare NO visual
// values at all. Without it, index.html would need its own grid, spacing and
// background rules, and DESIGN_PRINCIPLES.md section 6's "screens compose
// components; they do not define their own visual values" would be violated by
// the one file meant to prove it.
//
// Layout structure only -- every length and colour comes from a token.

import "../primitives/nova-box.js";
import { NovaElement, defineElement } from "../primitives/base.js";

class NovaShell extends NovaElement {
  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block;
          min-height: 100%;
          background: var(--nova-color-surface-base);
          padding: var(--nova-space-section);
          box-sizing: border-box;
          font-family: var(--nova-type-family-ui);
        }
        .stack { display: flex; flex-direction: column; gap: var(--nova-space-roomy); }
        .columns {
          display: grid;
          grid-template-columns: 1fr 3fr;
          gap: var(--nova-space-roomy);
          align-items: start;
        }
        .side { display: flex; flex-direction: column; gap: var(--nova-space-gutter); }
        .main { display: flex; flex-direction: column; gap: var(--nova-space-gutter); }
      </style>
      <div class="stack">
        <slot name="context"></slot>
        <div class="columns">
          <div class="side"><slot name="side"></slot></div>
          <div class="main"><slot name="main"></slot></div>
        </div>
      </div>
    `;
  }
}

defineElement("nova-shell", NovaShell);
