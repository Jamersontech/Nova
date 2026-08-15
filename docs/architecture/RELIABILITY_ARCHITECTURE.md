# Reliability Architecture

**Status:** **Active** — Section 02, approved by James 2026-08-12.
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

**A fourth outcome: unknown.** ***PROPOSED — added by Section 11, not yet accepted*** *(2026-08-15;
authority [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md),
Proposed; removed and the accepted text restored verbatim if rejected).* **The table above
classifies failures NOVA can see.** A timeout, a lost connection or a truncated response is not a
failure — it is an **absent outcome**, and the side effect may or may not have occurred.

| Signal | Classify as | Never as |
| --- | --- | --- |
| Typed provider failure | Failure | — |
| Timeout · connection loss · truncated response | **Unknown** | Failure |
| Provider success response | Success **claimed** | Success **verified** ([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §3.1) |

**Unknown is resolved by observation or it is escalated** — never by assumption in either
direction. Where the effect is independently observable, read it back; where it is not, the step
is recorded as unknown and surfaced to James under §5, because both wrong guesses are damaging: a
false "failed" invites a duplicating retry, and a false "succeeded" leaves a real change
unrecorded.

**A failure response does not mean nothing happened.** A provider may **partially execute** a
request before returning failure — some recipients sent, some records written. §3's partial
completion is written at *workflow step* granularity and does not reach inside a single request, so
a step recorded as failed can still have changed the world. Where a provider's failure semantics
are not all-or-nothing, that is a property of the **integration**, it is stated in the integration's
failure typing above, and a compensation cannot assume the step is a no-op.

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

**Resumption re-checks authorization; it does not inherit it.** ***PROPOSED — added by Section 08,
not yet accepted*** *(2026-08-14; authority
[ADR 0034](../decisions/0034-the-plan-is-a-security-object.md) and
[ADR 0035](../decisions/0035-section-08-amendments-to-accepted-architecture.md), both Proposed;
removed if either is rejected).* Point 5 above says resumption restarts from the last verified step.
**It was silent on whether the authorization still holds** — and this section's own premise is that
earlier steps did real work, which means the world the later steps were authorized against has
changed. A transfer that succeeded changes the balance the next step was authorized against.

Before the next step runs, `I-109`'s binding is **re-checked against current state**, and execution
**fails closed** if it no longer matches, requiring fresh authorization where the risk class
requires it (`I-113`). **Nothing here is re-derived by the Planner**: a plan that must change is a
new plan (`I-112`) and returns through Permission Evaluation.

---

## 4. Retry Discipline

- **Retries never carry injected credentials.** *(Added 2026-08-12, M-5.)* A queued or retried
  request is stored in **pre-injection** form; the credential is re-injected by the broker at
  send time. Retry queues, dead-letter queues, error records, logs, telemetry, and snapshots
  must not hold injected credential material
  ([`SECRETS_ARCHITECTURE.md`](./SECRETS_ARCHITECTURE.md) §4.2, `I-81`).
- Bounded attempts with exponential backoff; never unbounded.
- **Only idempotent operations retry automatically.** Idempotency is declared tool metadata
  ([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §2).
- **Idempotency is declared by NOVA and enforced by the provider, and those are not the same
  party.** ***PROPOSED — added by Section 11, not yet accepted*** *(2026-08-15; authority
  [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), Proposed;
  removed if rejected).* A tool may be correctly declared idempotent and still produce **two real
  side effects** on retry, because the deduplication the declaration assumes is performed by the
  external system. **The declaration is a claim about the tool; the guarantee belongs to the
  binding** — which is Section 10's claims-not-facts problem in a second place, and the reason this
  is stated rather than assumed. So: **automatic retry requires that the provider reached through
  this integration actually enforces the deduplication**, by a request-scoped key it honours or by
  semantics that are inherently repeatable. Where it does not, the operation is **not
  auto-retryable whatever the tool declares**, and an unknown outcome escalates instead. A
  deduplication key, where one exists, is **per logical operation** — reusing one across distinct
  operations suppresses a real second action, and re-deriving one per attempt defeats the purpose.
- Retries are recorded — a step that succeeded on attempt four is not the same as one that
  succeeded immediately, and the difference matters when diagnosing flakiness.
- Repeated failure escalates rather than retrying indefinitely.
- Circuit breaking: an integration failing consistently is marked unhealthy and dependent
  work pauses rather than hammering it.
- **Plans retry under their own rule.** *(Added 2026-08-14 — **PROPOSED**, Section 08; authority
  [ADR 0034](../decisions/0034-the-plan-is-a-security-object.md) and
  [ADR 0035](../decisions/0035-section-08-amendments-to-accepted-architecture.md), removed if either
  is rejected.)* Idempotency was declared for **tools** (metadata) and defined for **model calls**
  (`I-104`); **plan-level idempotency was undefined.** A plan is immutable once authorized
  (`I-112`), so **a plan is never "retried" in a form different from the one authorized**: either
  the same authorized plan resumes — with its binding re-checked per §3 — or a **new plan** is
  produced, which is a new authorization object, not a retry. **Re-planning loops fail closed to
  escalation** when they cannot continue safely, and are bounded by the **root execution budget**
  (`I-105`, `I-108`) rather than by a separate iteration counter: the Planner and Verifier calls
  they consume are model calls drawing on that same budget.
- **Model calls retry under their own rule.** *(Added 2026-08-14 — Section 05, **Accepted** by James 2026-08-14;
  authority [ADR 0024](../decisions/0024-model-gateway-is-an-enforcement-point.md) and
  [ADR 0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md), both
  **Accepted** 2026-08-14.)* The discipline above is written about **tools**, where idempotency is
  declared metadata. **A model call is idempotent in itself and not in its consequences.** So:
  a retried or rerouted model call **re-issues no side effect** — if its tool calls were already
  dispatched, the model call is not retried and the *step* is re-planned or escalated (§2, "model
  output wrong"). The retry boundary is the model call; the dispatch boundary is the tool
  enforcement point; they are not the same boundary. **Every attempt is separately authorized** —
  a reroute changes the destination provider, which is an input to the egress decision, so
  failover does not inherit the first call's allow — **and separately accounted**: a call that
  succeeded on attempt three cost three attempts (`I-104`,
  [`MODEL_GATEWAY_ARCHITECTURE.md`](./MODEL_GATEWAY_ARCHITECTURE.md) §6).

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
