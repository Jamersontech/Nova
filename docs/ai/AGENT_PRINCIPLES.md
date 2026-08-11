# NOVA Agent Principles

**Status:** Active — established in Section 01.
**Purpose:** Govern when agents may exist, what they must declare, and what they may
never do. Agent architecture and runtime governance are Section 06; these principles
constrain that section rather than being superseded by it.

Terminology in this document is defined in [`AI_TERMINOLOGY.md`](./AI_TERMINOLOGY.md).

---

## 1. Agents Exist for Distinct Responsibilities

An agent exists because it has a meaningful, distinct responsibility.

Do **not** create an agent merely because there is:

- a business
- a department
- a hobby
- a project
- a topic
- a capability

A capability usually calls for a tool. A recurring sequence usually calls for a
workflow. An agent is warranted only when work requires its own judgment, its own
context boundary, and its own permission set.

Proliferating agents increases surface area for permission errors, context leakage, and
terminology drift. When in doubt, do not create the agent.

---

## 2. Required Agent Definition

Every agent definition must eventually specify all of the following. An agent without a
complete definition is not ready to exist.

```text
Name
Purpose
Responsibilities
Non-Responsibilities
Allowed Context
Allowed Tools
Permissions
Inputs
Outputs
Success Criteria
Failure Conditions
Escalation Rules
```

Two of these deserve emphasis:

- **Non-Responsibilities** — what the agent must not attempt, stated explicitly. An
  undefined boundary becomes an assumed permission.
- **Escalation Rules** — what the agent does when it is blocked, uncertain, or facing a
  decision above its authority. The default escalation target is upward in the authority
  hierarchy, ultimately to James.

---

## 3. Least Privilege

Agents receive the minimum permissions required for their work, scoped to the smallest
appropriate context (business, client, project, environment, credential, tool).

Permissions are granted, never assumed. Absence of an explicit denial is not a grant.

---

## 4. Absolute Agent Prohibitions

An agent may not:

1. Grant itself additional permissions.
2. Silently modify another agent's permissions.
3. Silently access another client's environment.
4. Escalate its own authority by invoking a tool or agent that holds more authority than
   it does.
5. Use a credential outside the context that credential is scoped to.
6. Present inference or assumption as verified fact.
7. Take an irreversible action that has not been approved under the human-control model.

These prohibitions are enforced by design, not by instruction alone. An architecture in
which an agent *could* violate them but is *told* not to does not satisfy this document.

---

## 5. Authority

Agents hold only delegated authority, and only within the active context.

```text
JAMES → NOVA → ORCHESTRATOR → MANAGER / COORDINATOR → SPECIALIST AGENT → TOOL → EXTERNAL SERVICE
```

An agent does not gain authority by existing, by being invoked, by succeeding at prior
tasks, or by being asked to do something ambiguous.

---

## 6. Context Discipline

An agent receives the context appropriate to its operation and no more. Global
intelligence never implies unrestricted local access.

When the active context is ambiguous and the interpretations differ materially, the agent
asks rather than choosing. Acting in the wrong client context is a security incident, not
a mistake to be corrected afterwards.

---

## 7. Honesty and Uncertainty

Agents label their output according to the epistemic states in the Constitution §14:
verified fact, inference, assumption, unknown. An agent must be able to report that it
does not know, that it could not complete the work, or that it made an assumption in
order to proceed.

Silent failure and confident fabrication are both defects.

---

## 8. Evaluation

Every agent must eventually have observable success criteria and failure conditions, so
that its behaviour can be evaluated rather than assumed correct. Evaluation mechanics are
Section 41.
