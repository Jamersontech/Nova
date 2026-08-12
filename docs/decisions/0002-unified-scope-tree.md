# 0002 — One Unified Scope Tree for All Domains

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 02
**Accepted:** 2026-08-12 by James
**Section:** 02
**Resolves:** M-1, M-2

## Decision
Model LIFE, BUSINESS, and WEALTH as subtrees of a single scope tree. A **scope** is
simultaneously a context anchor, permission boundary, memory partition, and credential
partition. Access flows downward only, by explicit grant; siblings have no path between
them.

## Context
Section 1 defined Business → Client → Project → Environment but left LIFE and WEALTH
undefined (M-1), and did not specify how multiple businesses share infrastructure (M-2).

## Problem
Do LIFE and WEALTH get their own hierarchies, and does each business get its own
infrastructure?

## Options Considered
1. **Separate hierarchies per domain.** Each domain modelled naturally. Triples the
   permission, memory, and isolation logic; three places for isolation bugs to hide.
2. **One scope tree, uniform rules.** One rule set. Requires LIFE to fit a shape derived
   from business work.
3. **Flat entities with tags.** Flexible; isolation becomes a query concern, which is how
   client data leaks.

## Decision Made
Option 2. LIFE uses Area → Thread; BUSINESS uses Business → Client → Project → Environment;
WEALTH uses Account Group. All are *kinds of scope* under identical access rules. One
shared platform; per-business data and configuration only.

## Reason
Isolation is the highest-priority property. One rule applied uniformly is far more
defensible than three rule sets, and is testable as a single invariant.

## Tradeoffs
**Advantages:** one isolation model to implement, test, and audit; adding a business or
client is configuration; LIFE inherits all platform capability for free.
**Disadvantages:** LIFE's Area/Thread shape is somewhat imposed; the tree forbids a scope
having two parents, so genuinely shared work must be modelled as two scopes.

## Consequences
Every entity belongs to exactly one scope. "One project serving two clients" is not
expressible — deliberately. Multi-parent scopes would be a C3 change requiring a new ADR.

## What Would Change This
A real workload that genuinely cannot be modelled as a tree, where forcing it causes more
harm than the isolation guarantee prevents.

---

## Clarification — 2026-08-12, by James (at acceptance)

**The core decision is unchanged.** The unified scope tree remains the canonical isolation
model, and every rule above stands. This clarifies a requirement the original text left
implicit.

> **The architecture must support explicitly authorized shared resources, without
> duplicating client data and without weakening client isolation.**

### How sharing works within the tree

A shared resource is **placed at the nearest common ancestor scope and referenced
downward** — never linked laterally between siblings.

```text
KAIRO                          ← shared resource lives here
├── shared: site template, component library, SOP, brand asset
├── Client A  → references it downward   ✅
└── Client B  → references it downward   ✅
                Client A ⇄ Client B      ❌ still no path
```

This uses the existing downward-access rule rather than adding an exception to it. No new
crossing is created, and the "siblings have no path" guarantee is untouched.

### The three rules that keep this safe

1. **Reference, never copy.** Children reference a shared resource; they do not receive a
   duplicate. This satisfies "without duplicating client data" and means one update
   propagates rather than drifting into divergent per-client copies.
2. **A shared resource may contain no client-identifying data.** Placement at a shared
   scope is a promotion, and promotion of client material is the memory-elevation operation
   — explicit, permissioned, and audited
   ([`../architecture/MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`](../architecture/MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md) §3).
   A template is shareable; a template containing Client A's copy is not.
3. **Sharing is explicit authorization, never ambient.** A resource is shared because it
   was deliberately placed at a shared scope, not because two clients happen to need
   something similar. Reads of shared resources are attributable to the child scope that
   made them.

### What remains prohibited

- A resource owned by one client being read from another client's context.
- A scope having two parents.
- A "shared" resource that is in practice one client's material relabelled.
- Sharing a **credential** across clients. Credentials remain scoped to exactly one node
  ([ADR 0003](./0003-context-token-and-brokered-credentials.md)); shared *capability* never
  means shared *access*.

### Consequence

The tool-binding model already demonstrates the pattern: one `send_email` tool defined at
root, bound per scope to per-client credentials
([`../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md) §1).
This clarification generalizes that pattern from tools to any resource — templates,
component libraries, playbooks, brand assets, standard operating procedures.

Reflected in [`../architecture/DOMAIN_ARCHITECTURE.md`](../architecture/DOMAIN_ARCHITECTURE.md) §3.5.
