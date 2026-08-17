# User Interface Architecture

**Status:** **Active** — Section 02, approved by James 2026-08-12.
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

> ***PROPOSED — added by Section 14, not yet accepted*** *(2026-08-15; same authority as §7).*
> ***"From any surface" is a reachability requirement, not an authentication claim.*** Every
> surface must be able to **present** an approval request and **capture** the response, so James is
> never stranded. It does not assert that every surface supplies the authentication strength the
> risk class demands: a session's strength ceiling still applies (`A-3`,
> [`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §4), and above `PREPARE` on voice that
> means step-up on another surface. **`I-09` is unchanged** — only James approves — and `I-109`
> still binds the approval to its ten properties, so an approval captured on one surface applies
> only to the action it was given for.

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

> **Two sides, and this table governs only one.** ***PROPOSED — added by Section 14, not yet
> accepted*** *(2026-08-15; authority
> [ADR 0040](../decisions/0040-voice-is-an-input-surface-not-an-authentication-factor.md),
> Proposed; removed and the accepted text restored verbatim if rejected).* **As accepted, this
> section and [`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §4 read as contradicting.**
> *"A surface may vary in depth; it may never vary in authority"* — above — sits against §4's
> *"voice sessions may not reach above `PREPARE` without step-up on another surface"*, and §6's
> *"approvable… from any surface"* against the same. An engineer building the voice surface had to
> choose, and the readings produce materially different systems.
>
> **Both statements are correct, and they govern different sides.** This document governs the
> **action side**: what an action *means*, what it costs, and what it *requires* are identical on
> every surface — that is what *"never vary in authority"* asserts, and it stands unchanged.
> `AUTHENTICATION_MODEL.md` §4 governs the **session side**: what authentication strength *this
> session* can supply. A surface never changes what an action demands; it always determines what
> can be offered toward it.
>
> **So "confirmation of high-risk actions" in the table above is reachability, not completion.**
> Voice must be able to *present* the request and *capture* James's response. Above `PREPARE` the
> approval is **recorded only when a session of sufficient strength exists** (`A-3` step-up), and
> a spoken *"yes"* is his **expressed intent, not the record of an approval** (`I-09` unchanged).
> **And "explicit confirmation of scope" is disambiguation, not authorization** —
> [`CONTEXT_ARCHITECTURE.md`](./CONTEXT_ARCHITECTURE.md)'s ask-never-guess rule applied to the
> least precise surface. Resolving *which* scope is meant authorizes nothing in it.

---

## 8. What Section 2 Does Not Decide

Visual design, components, layout, typography, colour, interaction patterns, and the design
system itself — Sections 15–18 (`D-13`). This document constrains those sections: whatever
they produce must preserve three top-level areas, progressive disclosure, always-visible
context, and unmissable approvals.
