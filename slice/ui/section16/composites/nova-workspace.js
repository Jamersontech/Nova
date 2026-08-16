// nova-workspace -- the Section 16 screen shell.
//
// Exists for the same reason nova-shell does in Section 15: so the screen file
// can hold no visual values. It adds what Section 16 needs and Section 15 did
// not have to care about -- the document landmarks WCAG 2.2 AA structure
// depends on (banner, navigation, main), a heading, and a skip control so a
// keyboard user is not walked through the whole navigation region to reach
// content.
//
// Layout and landmarks only. Every length and colour is a token.

import "../../primitives/nova-box.js";
import "../../primitives/nova-text.js";
import { NovaElement, defineElement } from "../../primitives/base.js";

class NovaWorkspace extends NovaElement {
  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host {
          display: block; min-height: 100%;
          background: var(--nova-color-surface-base);
          padding: var(--nova-space-section);
          box-sizing: border-box;
          font-family: var(--nova-type-family-ui);
        }
        .stack { display: flex; flex-direction: column; gap: var(--nova-space-roomy); }
        /* The track definition is a token, so the two-column layout collapses to
           a single column at narrower viewports without this component, the
           screen, or any JavaScript knowing a breakpoint exists (Section 17). */
        .columns { display: grid; grid-template-columns: var(--nova-layout-columns);
                   gap: var(--nova-space-roomy); align-items: start; }
        /* Long scope paths and prose must wrap rather than force the page wider
           than the viewport -- WCAG 1.4.10 forbids two-dimensional scrolling. */
        :host, .stack, .columns, .side, .main { min-width: 0; }
        .side, .main { display: flex; flex-direction: column; gap: var(--nova-space-gutter); }
        main:focus-visible, .skip:focus-visible {
          outline: var(--nova-border-emphasis) solid var(--nova-color-border-accent);
          outline-offset: var(--nova-space-tight);
        }
        h1 {
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-title);
          font-weight: var(--nova-type-weight-strong);
          line-height: var(--nova-type-leading-tight);
          color: var(--nova-color-text-primary);
          margin: 0 0 var(--nova-space-gutter) 0;
        }
        /* Present for keyboard users, out of the way until focused. Not
           display:none -- that would remove it from the tab order entirely.
           Clipped rather than displaced: pushing it off-screen leaves it
           occupying space outside the document, which can produce a stray
           scroll region. clip-path hides it in place, invents no length, and
           keeps it focusable. */
        .skip {
          position: absolute; clip-path: inset(100%);
          font-family: var(--nova-type-family-ui);
          font-size: var(--nova-type-size-body);
          color: var(--nova-color-text-primary);
          background: var(--nova-color-surface-inset);
          border: var(--nova-border-width) solid var(--nova-color-border-accent);
          border-radius: var(--nova-radius-control);
          padding: var(--nova-space-tight) var(--nova-space-snug);
          cursor: pointer;
        }
        .skip:focus { position: static; clip-path: none; }
      </style>

      <button class="skip" type="button">Skip to main content</button>

      <div class="stack">
        <header>
          <h1><slot name="title"></slot></h1>
          <slot name="context"></slot>
          <slot name="views"></slot>
        </header>

        <div class="columns">
          <div class="side">
            <slot name="side"></slot>
          </div>
          <main id="main" tabindex="-1" aria-label="Main content">
            <div class="main"><slot name="main"></slot></div>
          </main>
        </div>
      </div>
    `;

    this.shadowRoot.querySelector(".skip").addEventListener("click", () =>
      this.shadowRoot.getElementById("main").focus()
    );
  }
}

defineElement("nova-workspace", NovaWorkspace);
