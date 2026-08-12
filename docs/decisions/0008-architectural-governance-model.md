# 0008 — Five-Class Architectural Governance Model

**Status:** Proposed
**Date:** 2026-08-12
**Section:** 02
**Resolves:** M-4

## Decision
Classify every change as C0 (editorial), C1 (implementation), C2 (structural), C3
(architectural), or C4 (constitutional). AI agents may implement C0 and C1; C2 and above
require James's approval; C3 and C4 additionally require an ADR. **Roadmap ordering is C3 —
James only.**

## Context
The Section 1 audit found (M-4) that nothing stated who may reorder sections, change
principles, or alter agent permissions. `ROADMAP.md` says sections are not strictly
sequential, while `AGENTS.md` says not to begin a future section — with no stated arbiter.

## Problem
Without explicit authority, an agent can rationalize almost any change as within scope, and
architecture erodes one reasonable-seeming decision at a time.

## Options Considered
1. **Everything requires approval.** Maximum safety; James becomes a bottleneck for typos.
2. **Agent judgment on significance.** Fast; the judgment is exactly what cannot be trusted,
   since a motivated agent will classify downward.
3. **Explicit change classes with escalation.** Clear boundaries; requires classifying each
   change.

## Decision Made
Option 3, with the rule that ambiguous classification escalates to the higher class.

## Reason
The failure being prevented is gradual architectural drift, which happens through changes
each individually defensible. Explicit classes make "is this mine to decide?" answerable
before the change rather than after.

## Tradeoffs
**Advantages:** unambiguous authority; C0/C1 keeps routine work fast; the escalation rule
biases errors toward safety; roadmap authority is settled.
**Disadvantages:** classification is a judgment call at the margins; C2+ latency depends on
James's availability; a cautious agent may over-escalate.

## Consequences
Agents must classify before acting. `ROADMAP.md`'s "not strictly sequential" describes
James's latitude, not an agent's — clarified in that document.

## What Would Change This
Practice showing a class boundary is drawn wrongly — most likely C2, which may prove either
too broad or too narrow once real implementation begins in Section 03.
