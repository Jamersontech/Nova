# 0001 — Layered Architecture with a Policy Spine

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 02
**Accepted:** 2026-08-12 by James
**Section:** 02

## Decision
Adopt a nine-layer architecture (Surface, Interaction, Context, Orchestration, Agent
Runtime, Capability, Integration, Knowledge & Data, Platform) with four cross-cutting
spines (Identity & Policy, Approval & Control, Observability & Audit, Cost). Layers may
call only the layer beneath them and may consult any spine.

## Context
Section 2 proposed a nine-layer stack including "User Experience" as the top layer and
security among the layers. NOVA must remain legible to future coding agents while enforcing
authorization everywhere.

## Problem
Where do security, observability, and approvals live? Treating them as layers implies a
single point of transit; every layer in fact needs them.

## Options Considered
1. **Layers only, security as a layer.** Simple to draw. Implies one checkpoint; leads to
   inconsistent enforcement elsewhere.
2. **Layers plus cross-cutting spines.** More concepts, but matches how enforcement must
   actually work.
3. **Services with no layering.** Maximum flexibility; no structural constraint on what may
   call what, which is how boundaries erode.

## Decision Made
Option 2, with "User Experience" renamed to "Surface" (UX is a system-wide quality, not a
tier) and memory/knowledge/records kept as distinct concepts within one layer.

## Reason
Authorization must be enforced at five distinct points. A spine makes that explicit; a
layer would suggest checking once is sufficient.

## Tradeoffs
**Advantages:** enforcement is structural; layers stay testable; the call rule prevents
shortcut paths.
**Disadvantages:** two concepts (layers and spines) instead of one; the call rule can feel
bureaucratic for simple operations.

## Consequences
Every enforcement point must be implemented; a call skipping a layer is a defect, not an
optimization. Renaming layers later is cheap; removing the spines would not be.

## What Would Change This
Evidence that the layer discipline blocks legitimate work, or a decomposition achieving the
same enforcement with fewer concepts.
