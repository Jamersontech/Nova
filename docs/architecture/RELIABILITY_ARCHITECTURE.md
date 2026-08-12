# Reliability Architecture

**Status:** Proposed — Section 02.
**Implements:** Constitution §12. External services fail, networks fail, models fail,
agents make mistakes, jobs fail — and **failures must not silently disappear.**

---

## 1. The Failure Pipeline

```text
Failure → Detection → Classification → Response → Escalation → Notification → Record
```

**Classification is the stage that determines everything after it.** A rate limit, an
expired credential, a changed API contract, and a wrong result are four different problems;
retrying is correct for one, harmful for another, and useless for the rest.

---

## 2. Failure Types and Responses

| Failure | Detection | Response |
| --- | --- | --- |
| **Model unavailable / rate limited** | Gateway error | Backoff, reroute to equivalent profile |
| **Model output malformed** | Schema validation | Re-request with tighter constraints, then escalate |
| **Model output wrong** | Verification against success criteria | Do not present as success. Re-plan or escalate |
| **Agent fails** | Failure condition met | Terminate instance; report; do not silently re-dispatch indefinitely |
| **Agent stuck** | No progress within limits | Terminate; preserve partial work; escalate |
| **Tool fails** | Typed tool error | Retry **only if idempotent**; otherwise escalate |
| **API fails** | Integration error | Classify: transient → retry; auth → credential flow; contract change → **escalate, never adapt silently** |
| **Credential expired** | Auth failure, or proactive expiry event | Pause dependent work; notify; resume after renewal |
| **External service changed** | Contract mismatch | Fail closed. **Never guess the new shape** |
| **Deployment fails** | Verification | Roll back if the environment supports it; otherwise halt and report exact state |
| **Workflow partially completes** | Step-level state | See §3 |
| **Coding agent stuck** | Time/cost/iteration ceiling | Terminate; preserve branch; escalate |

**The two rows that most need discipline:** a contract change must never be silently
accommodated — an integration that "adapts" to unexpected data is corrupting data
inward. And a non-idempotent tool must never be auto-retried.

---

## 3. Partial Completion

> *"What happens if half of a workflow succeeds?"*

This is the normal case, not an edge case. A workflow that creates a client, provisions
three environments, and fails on the fourth has done real work that must not be lost or
silently duplicated.

**The model:**

1. **Every step records its own outcome** — not just the workflow's. State is durable and
   inspectable at all times.
2. **Steps declare a compensation** where one exists: how to undo the step. Steps without a
   compensation are marked irreversible and require approval before running.
3. **On failure, the workflow pauses** in a known state — never rolls back automatically
   past an irreversible step, and never continues past a failed prerequisite.
4. **James is told exactly** what completed, what did not, what is now inconsistent, and
   what the options are: resume, compensate, or abandon.
5. **Resumption restarts from the last verified step**, not the beginning.

**Automatic rollback is deliberately not the default.** Undoing half a real-world workflow
can cause more damage than the failure — deleting a provisioned environment a client is
already using, for instance. NOVA pauses and asks unless a compensation is declared safe.

---

## 4. Retry Discipline

- Bounded attempts with exponential backoff; never unbounded.
- **Only idempotent operations retry automatically.** Idempotency is declared tool metadata
  ([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §2).
- Retries are recorded — a step that succeeded on attempt four is not the same as one that
  succeeded immediately, and the difference matters when diagnosing flakiness.
- Repeated failure escalates rather than retrying indefinitely.
- Circuit breaking: an integration failing consistently is marked unhealthy and dependent
  work pauses rather than hammering it.

---

## 5. Escalation and Notification

```text
Automatic recovery
   → failed → agent-level escalation
   → failed → orchestrator-level escalation
   → failed → James
```

Escalation is upward only — never sideways to another agent that might approve what the
first could not.

**Failures reach James when** they block work he asked for, affect a client, involve money
or irreversibility, indicate a security concern, or recur. Routine transient failures that
recovered are recorded but not surfaced — otherwise notification fatigue makes the
important ones invisible.

---

## 6. Degraded Operation

NOVA should degrade rather than stop entirely. If model routing is impaired, interactive
work continues while background work pauses. If one integration is down, only work
depending on it pauses. **Degradation is always visible** — NOVA states that it is
operating in a reduced mode rather than quietly producing lower-quality results.

---

## 7. Health

The system continuously answers: are core services responsive, are integrations healthy,
are credentials near expiry, are workflows stuck, are agents completing, are error rates
normal, is cost within expectation. Health is a first-class signal because most of the
failures above are visible before they cause damage — an expiring credential is a
notification today or a broken deployment next week.
