# 0006 — Risk-Classified Actions Drive Approval

**Status:** Proposed
**Date:** 2026-08-12
**Section:** 02

## Decision
Classify every action as READ, ANALYZE, RECOMMEND, PREPARE, EXECUTE, HIGH-IMPACT EXECUTE,
or IRREVERSIBLE. Risk class plus scope determines whether James is asked. READ through
PREPARE are autonomous within an authorized context; IRREVERSIBLE is never autonomous.

## Context
Constitution §11 requires stronger approval for higher-consequence actions, while Golden
Rule 1 requires NOVA to remain simple to use. These pull against each other.

## Problem
How does James stay in control without approving trivia — which produces reflexive
approval, the worst of both outcomes?

## Options Considered
1. **Approve everything.** Maximum control on paper. In practice James approves without
   reading, so control is illusory and the product is unusable.
2. **Approve nothing; audit after.** Excellent usability; unacceptable for irreversible
   actions on client systems and money.
3. **Risk-classified approval.** Approval concentrated where consequences are.
4. **Learned/adaptive thresholds.** Adjusts to James's habits; unpredictable, and
   unpredictability in an authorization system is a defect.

## Decision Made
Option 3, with bounded standing approvals for repetitive low-risk work.

## Reason
Approval fatigue is a security failure, not merely an annoyance. Concentrating approvals
where they matter keeps each one meaningful, and lets NOVA do large amounts of useful work
— research, drafting, staging entire client builds — with no interruption at all.

## Tradeoffs
**Advantages:** control where it counts; NOVA remains highly useful autonomously; risk
class is explicit and testable.
**Disadvantages:** classification must be right, and misclassifying downward is dangerous;
context-dependent risk (the same tool at different risk in different scopes) adds
complexity.
**Mitigation:** when uncertain, the higher class applies; risk may be raised by scope but
never lowered by an agent.

## Consequences
Every action and tool must carry a risk class. Standing approvals are bounded by scope,
ceiling, expiry, and rate — and are recorded as grants so they remain inspectable.

## What Would Change This
Evidence that a class boundary is drawn wrongly in practice — likely discovered in Sections
26 and 39, and adjustable without changing the framework.
