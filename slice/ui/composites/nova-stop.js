// nova-stop -- the emergency stop.
//
// USER_INTERFACE_ARCHITECTURE.md section 6: "The emergency stop is always
// reachable without navigation, from every surface." So this composite takes no
// "hidden" or "collapsed" state -- there is no configuration under which it is
// not rendered. That is the point of it.
//
// PERMISSION_ARCHITECTURE.md section 5 lists emergency stop as available at any
// time. I-93 is the reason it is never withheld on a failed audit write:
// refusing to stop fails open.
//
// Presentation only. This demonstration wires the control to nothing.

import "../primitives/nova-box.js";
import "../primitives/nova-text.js";
import "../primitives/nova-button.js";
import { NovaElement, defineElement } from "../primitives/base.js";

class NovaStop extends NovaElement {
  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
      </style>
      <nova-box surface="raised" pad="snug" radius="panel" border="subtle"
                direction="column" gap="tight">
        <nova-button variant="danger" full>Emergency stop</nova-button>
        <nova-text size="caption" tone="muted">
          Halts all autonomous work immediately. Always reachable.
        </nova-text>
      </nova-box>
    `;
  }
}

defineElement("nova-stop", NovaStop);
