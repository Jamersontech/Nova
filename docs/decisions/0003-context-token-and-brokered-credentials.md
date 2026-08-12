# 0003 — Context Tokens and Brokered Credentials

**Status:** Proposed
**Date:** 2026-08-12
**Section:** 02

## Decision
Every operation carries a **Context Token** naming the scope path, rights, and expiry.
Enforcement points verify it at the point of access. Agents **never** hold credentials; a
**Credential Broker** injects secrets at the outbound integration boundary.

## Context
Constitution Golden Rule 4 requires that client data never mix, and Section 1 requires
isolation enforced by data, authorization, credential, environment, and permission
boundaries rather than interface hiding.

## Problem
How is isolation enforced against an agent that is confused, misled by injected content, or
compromised — rather than merely instructed to behave?

## Options Considered
1. **Instruction-based.** Agents told which client they serve. Zero cost; fails the moment
   an agent misbehaves, and cannot be tested.
2. **Filter at query time.** Enforcement in data access. Better; leaves credentials in agent
   memory and each query site can drift.
3. **Context tokens plus brokered credentials.** Isolation and secrets both enforced
   structurally. More machinery.

## Decision Made
Option 3.

## Reason
The property required is that a compromised agent has *nothing to leak*. Under option 3, an
agent holds no secret and its token is refused outside its scope, so both leakage paths are
closed by construction rather than by conduct.

## Tradeoffs
**Advantages:** compromised agents, prompt injection, and confused-deputy attacks are all
contained; every access is auditable; testable as an invariant.
**Disadvantages:** more moving parts; every tool call incurs a policy and broker round trip;
credential rotation must be handled centrally.

## Consequences
No component may bypass the broker. Any future "just give the agent the API key for
performance" proposal is a C3 change and should be refused.

## What Would Change This
Broker latency proving unworkable for a class of operations — in which case the answer is a
faster broker, not agent-held secrets.
