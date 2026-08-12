# 0002 — One Unified Scope Tree for All Domains

**Status:** Proposed
**Date:** 2026-08-12
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
