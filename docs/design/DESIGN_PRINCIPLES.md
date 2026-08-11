# NOVA Design Principles

**Status:** Active — established in Section 01.
**Scope:** Principles only. The concrete design system — tokens, components, typography,
colour, spacing — belongs to Section 15. No interface is built in Section 01.

---

## 1. Core Principle

**Sophisticated system. Simple interface.**

NOVA's internal complexity is not evidence that its interface should be complex. The
interface must not grow a control, panel, or navigation item merely because a subsystem
exists behind it.

---

## 2. Intended Character

NOVA should eventually feel:

- premium
- high-tech
- modern
- intelligent
- calm
- fast
- intentional
- polished
- visually coherent

"Calm" and "fast" are the two that constrain the others. A screen that impresses on first
sight but slows daily use has failed.

---

## 3. What to Avoid

Avoid unnecessary cards, navigation items, sidebars, animations, glowing effects,
gradients, visual noise, and decorative complexity.

Each of these is permitted only where it does specific work — communicating state,
establishing hierarchy, or confirming an action. Decoration without a job is removed.

---

## 4. Progressive Disclosure

Advanced capability is reached, not displayed. The primary surface shows what James needs
now; depth is available on request. James must never be required to understand agents,
permissions, model routing, or infrastructure to use NOVA.

---

## 5. Simplicity Under Growth

The user-facing structure stays broad and shallow:

```text
NOVA
│
├── LIFE
├── BUSINESS
└── WEALTH
```

Adding businesses, clients, projects, agents, tools, or integrations must not add
top-level surface area. Growth happens inside these areas, not beside them.

---

## 6. Design System Requirement

Future UI development uses a centralized design system:

```text
Design Tokens
      ↓
Primitive Components
      ↓
Composite Components
      ↓
Screens
```

A global visual change must be achievable through the design system rather than by
editing dozens of unrelated screens. Screens compose components; they do not define their
own visual values.

This is a binding requirement on future sections. It is **not** implemented now.

---

## 7. Clarity About State

The interface must make it clear what context is active, what NOVA is doing, what it has
done, and what requires James's approval. Ambiguity about active context is a safety
problem (Constitution §7), and the interface is where that ambiguity most often appears.
