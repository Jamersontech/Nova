# 0005 — External Coding Agents Are Untrusted

**Status:** Proposed
**Date:** 2026-08-12
**Section:** 02

## Decision
Treat external coding agents (Claude Code, Codex, future systems) as **untrusted
contractors**. They receive a **Work Order** — never a Context Token — run in ephemeral
single-client sandboxes, hold only brokered narrow expiring credentials, and produce
**proposals** that are verified, reviewed, and approved before landing.

## Context
NOVA must eventually orchestrate coding agents to build client work
([`../architecture/EXECUTION_ARCHITECTURE.md`](../architecture/EXECUTION_ARCHITECTURE.md)).
These agents are autonomous, capable, and outside NOVA's control.

## Problem
How much NOVA access should a coding agent receive?

## Options Considered
1. **Full NOVA context.** The agent could resolve ambiguity itself and would need less
   briefing. A single prompt injection, confused agent, or upstream compromise would reach
   every client NOVA serves.
2. **Scoped NOVA access.** Read access to its client's context only. Smaller blast radius,
   but still a path from an untrusted process into NOVA's internals, and the scoping logic
   becomes security-critical.
3. **No NOVA access — Work Order and sealed sandbox.** Blast radius limited to one branch
   in one repository. Requires precise task specification up front.

## Decision Made
Option 3.

## Reason
Coding agents execute arbitrary generated code against real client infrastructure, and
their input includes repository contents that may be adversarial. The blast radius of
options 1 and 2 is every client; of option 3, one branch.

## Tradeoffs
**Advantages:** prompt injection in a client repository cannot reach NOVA or other clients;
credentials are narrow and expiring; all output is reviewed; every action is attributable.
**Disadvantages:** work orders must be specified precisely, since the agent cannot ask NOVA
for missing context; more provisioning machinery; occasional rework when a work order was
underspecified.

## Consequences
Poor task specification surfaces as failed work orders rather than as agents improvising.
Any future proposal to widen coding-agent access is C3 and should be refused absent a
compelling, bounded reason.

## What Would Change This
A mechanism providing scoped, read-only, audited context to a sandbox with a demonstrably
contained blast radius — a genuine improvement worth revisiting, not a convenience.
