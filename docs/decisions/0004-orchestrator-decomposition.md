# 0004 — Decompose the Orchestrator; Exclude Domain Logic and Credentials

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 02
**Accepted:** 2026-08-12 by James
**Section:** 02

## Decision
Split the Orchestrator into Interpreter, Planner, Dispatcher, Verifier, and Assembler.
Prohibit it from holding domain knowledge or credentials, and from making authorization
decisions — it asks the Policy service.

## Context
The Section 2 brief explicitly asks whether the orchestrator could become an
unmaintainable god-object. It is the component every feature naturally lands in.

## Problem
How is the coordinating component prevented from accumulating all system knowledge?

## Options Considered
1. **Single orchestrator component.** Simplest to build; becomes the god-object, untestable
   in parts, unreplaceable.
2. **Five-component pipeline with exclusions.** Each piece has one job and is separately
   testable; more interfaces to define.
3. **Fully distributed choreography, no orchestrator.** No central component at all;
   authority becomes untraceable, which is unacceptable given the authority hierarchy.

## Decision Made
Option 2.

## Reason
The exclusions matter more than the split. Domain logic in the orchestrator makes it grow
without bound; credentials in the orchestrator make it the highest-value target in the
system. Removing both keeps it a coordinator.

## Tradeoffs
**Advantages:** each stage independently testable and replaceable; verification is a
distinct stage rather than an afterthought; a compromised orchestrator yields no secrets.
**Disadvantages:** more inter-component contracts; simple requests traverse five stages;
"where does this logic go?" needs judgment.

## Consequences
Domain knowledge must live in domain agents even when embedding it in the orchestrator
would be faster. Verification cannot be skipped for expedience.

## What Would Change This
Evidence that the five-stage pipeline adds latency that materially harms interactive use,
in which case stages could merge — but the two exclusions must survive any such merge.
