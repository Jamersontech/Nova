# Permission Architecture

**Status:** **Active** — Section 02, approved by James 2026-08-12.
**Covers:** the permission model, action risk classification, approvals, and human control.

---

## 1. The Question the System Must Answer

> **Who** may do **what**, to **which resource**, in **which context**, using **which
> tool**, at **what risk**, and with **what approval**?

Seven dimensions. A model answering fewer produces either an unusable system or an unsafe
one.

```text
Permission = (identity | role) × right × resource type × scope × risk ceiling × conditions
```

---

## 2. One Decision Point, Many Enforcement Points

```mermaid
flowchart LR
    subgraph PEP["Policy Enforcement Points"]
        O["Orchestration"]
        A["Agent Runtime"]
        T["Tool call"]
        C["Credential Broker"]
        D["Data access"]
    end
    PDP["POLICY DECISION POINT<br/>single authority"]
    O --> PDP
    A --> PDP
    T --> PDP
    C --> PDP
    D --> PDP
    PDP --> R["allow · deny · approval required"]
    PDP --> AU["audit record"]

    style PDP fill:#7c2d12,color:#fff
```

**One place decides; five places enforce.** Scattering authorization logic across
orchestration and tool code is how isolation quietly rots — each site drifts, and no one
can answer "what is actually enforced?" A single PDP is testable in isolation
([`TESTING_ARCHITECTURE.md`](./TESTING_ARCHITECTURE.md)).

**Default deny.** Absence of a grant is a denial. Absence of an explicit *denial* is not a
grant ([`../ai/AGENT_PRINCIPLES.md`](../ai/AGENT_PRINCIPLES.md) §3).

---

## 3. Grants and Scopes

A grant names identity/role, right, resource type, scope, risk ceiling, and conditions
(time bounds, approval requirements, rate limits).

**Grants are inherited downward and never sideways or upward.** A grant over
`/business/KAIRO/client-a` covers its projects and environments. It says nothing about
Client B and nothing about KAIRO as a whole.

**Temporary permissions** carry a mandatory expiry, are recorded on issue and expiry, and
are used for exactly the pattern that otherwise causes permanent over-permissioning: "the
agent needs this once."

**Credential scopes are separate from permissions.** A permission says NOVA *may* act; a
credential is *how* it reaches outward. Holding one never implies the other.

---

## 4. Action Risk Classification

Every action carries a risk class. This is what allows James to stay in control without
approving trivia.

| Class | Meaning | Reversible | Default |
| --- | --- | --- | --- |
| **READ** | Observe existing information | n/a | Autonomous |
| **ANALYZE** | Reason over information | n/a | Autonomous |
| **RECOMMEND** | Propose a course of action | n/a | Autonomous |
| **PREPARE** | Stage a change without committing it | Yes | Autonomous |
| **EXECUTE** | Make a change of limited consequence | Usually | Contextual approval |
| **HIGH-IMPACT EXECUTE** | Change affecting clients, money, or production | Difficult | **Explicit approval** |
| **IRREVERSIBLE** | Cannot be undone | **No** | **Explicit approval, never autonomous** |

**Examples.** Reading a client's analytics is `READ`. Drafting the client email is
`PREPARE`. Sending it is `EXECUTE`. Deploying to their production site is `HIGH-IMPACT
EXECUTE`. Deleting their database, sending an SMS campaign to their customer list, or
moving money is `IRREVERSIBLE`.

**The productive consequence:** NOVA can do an enormous amount of useful work — research,
analysis, drafting, staging, planning entire client builds — with no approvals at all.
Approval is concentrated where consequences are, which is what makes it meaningful rather
than reflexive.

**Classification rules.** Risk is a property of the *action in its context*, not the tool.
The same "send email" tool is `EXECUTE` for an internal note and `IRREVERSIBLE` for a bulk
send to a client's customers. When a classification is uncertain, the higher class applies.
Risk may be raised by scope (production, client-facing, financial) but never lowered by an
agent.

---

## 5. Approval Policies

| Mode | When | Behaviour |
| --- | --- | --- |
| **Fully autonomous** | READ–PREPARE within an authorized context | Acts; records; reports |
| **Low-risk approval** | EXECUTE, routine and reversible | May batch or use standing approvals with limits |
| **High-risk approval** | HIGH-IMPACT EXECUTE | Explicit per-action approval, showing what will change |
| **Explicit human command** | IRREVERSIBLE | James must initiate, not merely consent |
| **Emergency stop** | Any time | Halts all autonomous work immediately |

**Standing approvals** ("deploy Client A's staging without asking") are permitted, bounded
by scope, risk ceiling, expiry, and rate limit — and revocable. They are recorded as grants
so that what NOVA may do autonomously is always inspectable.

**An approval authorizes one action, in one context, at one time.** It never becomes a
precedent, and it is never inferred from a previous approval.

**Approval requests must be answerable.** A request stating what will change, in which
scope, what it costs, and what happens if it is wrong is a decision James can make in
seconds. A request saying "approve this workflow?" is not.

---

## 6. Emergency Stop

Required by Constitution §11. Guarantees:

1. **Always reachable** — from any surface, at any time, without navigating.
2. **Immediate** — new work is refused and in-flight autonomous work halts at its next
   checkpoint.
3. **Fails closed** — components that cannot confirm the stop must refuse to proceed.
4. **Leaves a known state** — what stopped, what completed, what is partial.
5. **Does not require NOVA's cooperation** — a stop must not depend on the orchestrator
   being healthy. An unhealthy orchestrator is exactly when it is needed.

Point 5 is the design constraint that matters: the stop is enforced at the enforcement
points, not requested politely of the thing being stopped.

Resumption after a stop is always an explicit human act.

---

## 7. Least Privilege in Practice

- Agents receive the narrowest token that lets them finish, not their maximum allowed scope.
- Tokens expire with the work.
- Tools declare the minimum rights they need; a tool asking for more than it uses is a
  defect.
- Credentials are brokered per call, never held by agents.
- Temporary elevations expire automatically.
- No component may widen its own authority — the architecture provides no mechanism for it.
