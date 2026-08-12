# 0007 — Model Gateway as the Only Provider-Aware Component

**Status:** Proposed
**Date:** 2026-08-12
**Section:** 02

## Decision
All model access passes through a Model Gateway. Agents request **capability profiles**,
never model ids. The gateway is the only component aware of providers, and performs
redaction and data-policy enforcement before egress.

## Context
Constitution §10 requires provider independence; §16 states AI providers are replaceable
tools.

## Problem
Provider independence is easy to declare and easy to lose — a model id in agent code, a
provider-specific prompt format, or a dependence on one vendor's tool-calling semantics
each quietly create lock-in.

## Options Considered
1. **Direct provider SDK calls.** Simplest; every call site becomes a lock-in point.
2. **Thin abstraction over one provider.** Looks portable; the abstraction inevitably
   mirrors that provider's semantics, so it is lock-in with extra steps.
3. **Gateway with capability profiles.** Genuine substitutability; requires designing
   profiles that do not encode any provider's model.

## Decision Made
Option 3, with routing on task, quality, latency, cost, context, tool capability,
reliability, and data policy.

## Reason
The requirement is that removing a provider entirely leaves NOVA working. That is only true
if nothing above the gateway names one.

## Tradeoffs
**Advantages:** providers replaceable by configuration; cost-aware routing possible;
redaction has a single chokepoint; per-provider quality becomes measurable.
**Disadvantages:** capability profiles are hard to design well and may not expose a
provider's best features; an extra hop; routing itself becomes a system to maintain.

## Consequences
Provider-specific features are used only when expressible as a profile. "Just call the API
directly here" is a C3 change.

## What Would Change This
A capability so valuable and so provider-specific that abstracting it costs more than the
lock-in — which should be recorded as an explicit, bounded exception, not a quiet one.
