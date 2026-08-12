# User Interface Architecture

**Status:** Proposed — Section 02.
**Scope:** Information architecture only. **No visual design, no components, no screens** —
those are Sections 15–18. This document decides *what is reachable and how*, not what it
looks like.

---

## 1. The Constraint

NOVA's internals are large: a scope tree, an orchestrator, agents, tools, integrations,
memory, workflows, events, approvals. **None of that structure may surface as navigation.**

> Sophisticated system. Simple interface.
> ([`../design/DESIGN_PRINCIPLES.md`](../design/DESIGN_PRINCIPLES.md))

The failure mode to avoid is the one every internal platform falls into: each subsystem
earns a menu item, and the product becomes an admin console for its own architecture.

---

## 2. Primary Structure

```text
NOVA
├── LIFE
├── BUSINESS
└── WEALTH
```

Three areas. Adding businesses, clients, projects, agents, tools, or integrations **never
adds a fourth**. Growth happens inside, never beside.

**Conversation is not a section — it is the interface.** NOVA is primarily talked to. The
three areas are where James goes when he wants to *look* at something rather than ask.

---

## 3. Reaching Everything Else

Every capability the brief lists is reachable without a top-level home:

| Capability | Reached by |
| --- | --- |
| **Conversation** | The primary surface. Always present |
| **Tasks** | Inside their scope; aggregated in a cross-scope "what needs doing" view |
| **Projects** | Inside a client, inside a business |
| **Businesses** | Inside BUSINESS |
| **Clients** | Inside their business |
| **Wealth** | Inside WEALTH |
| **Notifications** | A persistent, low-weight indicator — not a section |
| **Approvals** | Surfaced where the work is, and in one pending-approvals view. **Never buried** |
| **Activity** | A single chronological account of what NOVA did; filterable by scope |
| **Settings** | Reached deliberately, not displayed |
| **Agents, tools, integrations, memory, workflows** | **Not user-facing navigation.** Visible through Activity, or in the Admin/Architect view (Section 43) |

**Three views cut across the tree** because they answer questions James actually asks:
*what needs my decision* (approvals), *what did NOVA do* (activity), *what needs doing*
(tasks). Everything else is reached by drilling into a scope.

---

## 4. Progressive Disclosure

```text
Level 1   Ask NOVA. Get an answer.
Level 2   See the three areas and current state.
Level 3   Drill into a business, client, project, or life area.
Level 4   Inspect what NOVA did — activity, traces, decisions.
Level 5   Administer — agents, tools, permissions, memory. (Section 43)
```

Most days end at Level 1 or 2. Levels 4 and 5 exist so NOVA is inspectable and controllable,
not because they are part of daily use. **Depth is available, never imposed.**

---

## 5. Context Must Always Be Visible

The one piece of internal machinery that **must** be exposed: the active context.

```text
KAIRO · Client A · Website · Production
```

Constitution §7 makes context ambiguity a safety problem, and the interface is where that
ambiguity is most cheaply prevented. James must always be able to see which scope NOVA is
operating in, and switching must be explicit and obvious. This is the single exception to
"complexity belongs underneath" — because an invisible context is a hazard, not a
simplification.

---

## 6. Approvals

Approval requests must state, in plain language: what will happen, in which scope, why it
needs approval, what it costs, and what happens if it is wrong. Approvable in one action,
from any surface, and never so frequent that approving becomes reflexive
([`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) §5).

**The emergency stop is always reachable** without navigation, from every surface.

---

## 7. Multi-Device

| Surface | Suited to | Must always support |
| --- | --- | --- |
| **Desktop / web** | Depth: review, planning, inspection | Everything |
| **Mobile** | Awareness and decisions on the move | Conversation, notifications, **approvals**, emergency stop |
| **Voice** | Hands-free capture and quick queries | Conversation, confirmation of high-risk actions |
| **Future** | — | At minimum: conversation, approvals, stop |

**Consistent across every surface:** identity, active context, permissions, the meaning of
an action, what requires approval, and the emergency stop. A surface may vary in *depth*;
it may never vary in *authority*. An action requiring approval on desktop cannot proceed
unapproved on mobile.

**Voice carries a specific hazard:** it is the least precise about context. Voice therefore
requires explicit confirmation of scope for anything above `PREPARE`, and states the
context it is acting in aloud.

---

## 8. What Section 2 Does Not Decide

Visual design, components, layout, typography, colour, interaction patterns, and the design
system itself — Sections 15–18 (`D-13`). This document constrains those sections: whatever
they produce must preserve three top-level areas, progressive disclosure, always-visible
context, and unmissable approvals.
