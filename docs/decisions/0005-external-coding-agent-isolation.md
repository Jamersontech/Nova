# 0005 — External Coding Agents Are Untrusted

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 02
**Accepted:** 2026-08-12 by James
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

---

## Clarification — 2026-08-12, by James (at acceptance)

**The security boundary is unchanged.** Every rule above stands: no Context Token leaves
NOVA, sandboxes remain ephemeral and single-client, credentials remain brokered and narrow,
and output remains a proposal subject to verification, review, and approval.

This records a **capability requirement on NOVA**, not a relaxation of the boundary:

> **NOVA should eventually generate precise Work Orders for external coding agents from
> James's high-level requests.**

### Why this belongs here

This ADR accepted a real cost: because a coding agent cannot query NOVA for missing context,
an underspecified Work Order fails or produces wrong work. The obvious way to relieve that
pressure would be to widen the agent's access — **which this ADR forbids.**

The correct relief is therefore to move the specification burden *onto NOVA*. James says
"build Client A a booking page"; NOVA — not the coding agent — resolves that into a precise
task, repository, branch, constraints, and verifiable success criteria.

**This makes the boundary more durable, not less.** The better NOVA becomes at specifying
work, the weaker the argument for ever granting coding agents broader access.

### Where the specification comes from

Work Order generation is an **inside-the-boundary** activity, performed by NOVA components
that already hold the relevant context:

```text
James's high-level request
   ↓  Orchestrator — Interpreter and Planner
   ↓  Domain agents — what this kind of work requires
   ↓  Client/project scope — conventions, stack, constraints, history
   ↓  Review criteria — what "done" must mean, verifiably
   → Work Order  (still: no Context Token, no scope paths, no NOVA identity)
```

Everything informing the Work Order stays inside NOVA. What crosses the boundary is only
the finished, minimal specification — the same object with the same omissions.

### Constraints on generated Work Orders

1. **A generated Work Order carries no more than a hand-written one.** Generation must never
   become a channel for leaking scope paths, other clients' existence, or credentials
   beyond the task.
2. **Success criteria must be verifiable**, since they gate automated verification and
   review.
3. **Issuing a Work Order is subject to its risk class** ([ADR 0006](./0006-risk-classified-approvals.md)).
   Automating the *specification* does not automate the *authorization*.
4. **An underspecified generated order fails closed** — escalating to James rather than
   dispatching a vague task and hoping.
5. **Generation quality is evaluated** (Section 41). Work Order quality becomes a measurable
   property, since it directly determines coding-agent success.

### Consequence

`KNOWN_RISKS.md` recorded "Work Orders must be specified precisely" as an accepted weakness
with expected early rework. That weakness now has a defined mitigation path rather than
being a permanent cost — while the security boundary that made it necessary stays intact.

Owned by Sections 08 (planning) and 30 (coding-agent architecture). Reflected in
[`../architecture/EXECUTION_ARCHITECTURE.md`](../architecture/EXECUTION_ARCHITECTURE.md) §2.1.
