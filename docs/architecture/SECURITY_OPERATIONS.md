# Security Operations

**Status:** Proposed — Section 04, pending James's approval.
**Covers:** revocation propagation, emergency stop mechanics, break-glass access, and
security incident response.

These are the operational behaviours the rest of Section 04 depends on. Without them,
revocation is a database update nobody enforces and the emergency stop is a button that asks
politely.

---

## 1. Revocation Propagation

Revocation applies to grants, delegations, sessions, credential bindings, and context tokens.
The question that matters is **when it takes effect**.

**V-1 — Effective at the next decision.** A revoked grant is denied at the next PDP
evaluation. There is no propagation delay to wait out, because the PDP is consulted per
decision rather than per session.

**V-2 — In-flight executions fail closed at their next enforcement point.** A running
execution holding a revoked token does not complete "because it already started." It reaches
its next enforcement point and is denied (`I-74`).

**V-3 — Cached read decisions are invalidated immediately.** The one cache ADR 0014 permits
is keyed to a context token; revoking that token invalidates it. No other cache may outlive a
revocation.

**V-4 — Revocation is scoped.** Revoking one binding, session, or grant does not disturb
others (`I-25`).

**V-5 — Revocation is recorded.** Who revoked what, when, and why.

**The honest limit:** revocation cannot recall what was already read, sent, or delivered.
Revoking a credential does not un-send an email. Revocation stops future use; it does not
reverse past use — and NOVA must say so rather than implying otherwise.

---

## 2. Emergency Stop

Required by Constitution §11 and specified in
[`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) §6. The mechanics:

**X-1 — Enforced at the enforcement points, not requested of components.** The stop sets a
state the enforcement points read. It does not ask the orchestrator to stop, because an
unhealthy or compromised orchestrator is exactly when it is needed (`I-19`).

**X-2 — Denies all new decisions except James's own.** Autonomous work halts; James retains
the ability to inspect and to lift the stop.

**X-3 — In-flight autonomous work halts at its next checkpoint**, leaving a known state
([`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md) §3).

**X-4 — Ends all sessions.** Resuming requires fresh authentication (`A-6`).

**X-5 — Reachable without navigation, from every surface** — including when NOVA is
unresponsive. A stop that requires a working NOVA is not an emergency stop.

**X-6 — Lifting is an explicit human act**, authenticated at full strength, and recorded.

**X-7 — Fails closed.** A component that cannot confirm the stop state refuses to proceed.

---

## 3. Break-Glass Access

Every system that fails closed needs a defined path for the case where it fails closed *and
James legitimately needs in*. Leaving this undefined guarantees an undocumented bypass gets
built under pressure.

**The normative rule, stated first and without qualification:**

> ### BREAK-GLASS MUST NEVER AUTHORIZE CLIENT-DATA ACCESS.
> ### BREAK-GLASS MUST NEVER BYPASS THE NORMAL AUTHORIZATION PATH.

*Rewritten 2026-08-12 following adversarial review (H-4). The previous `B-1` was internally
tense: it claimed both "restores access when policy is unavailable" and "never bypasses
authorization." Those cannot both be true of a single mechanism acting on data. Resolved by
confining break-glass to the control plane.*

**B-1 — Control plane only.** Break-glass acts on **platform and control-plane function**, never
on protected data. It may:

- restore the ability to authenticate,
- repair or restart policy infrastructure,
- recover control-plane services,
- lift an emergency stop.

It may **not**, under any circumstance:

- read, write, export, or otherwise access client data or any protected resource,
- stand in for the PDP, evaluate authorization, or grant access,
- act while authorization is unavailable *as though* authorization had been obtained.

**If policy is unavailable, break-glass may restore NOVA's ability to perform authorization. It
never replaces authorization.** Protected data remains fail-closed throughout (`I-17`, `I-75`).
The correct sequence is: break-glass → policy restored → normal authorization → data access.
There is no path from break-glass to data that skips the middle two steps.

**B-2 — Human-only.** No agent, workflow, or automation may invoke it.

**B-3 — Loud by construction.** Invocation raises a high-priority notification, is prominently
recorded, and is visible in Activity. Silent break-glass is indistinguishable from compromise.

**B-4 — Time-boxed.** Break-glass access expires quickly and automatically; it is not a mode
NOVA can be left in.

**B-5 — Scoped to recovery, consistent with B-1.** Its permitted actions are exactly the
control-plane recoveries listed in `B-1`. `B-5` adds no capability beyond `B-1`; the two state
the same boundary from different directions, deliberately, so neither can be read as the
loophole in the other.

**B-6 — Its own credential path.** Break-glass credentials are stored and protected separately
and are never reachable by NOVA's own components.

**B-7 — Rotation must not assume a healthy platform.** *(Added 2026-08-12, L-5.)* Break-glass
credentials are used precisely when NOVA is degraded or offline, so **rotation cannot depend on
NOVA being able to rotate them.** The architecture requires that rotation be possible
out-of-band, independently of NOVA's availability, and that a credential used during an outage
be treated as spent and rotated at the earliest opportunity — with the interval between use and
rotation recorded as exposure. The mechanism is deferred (`D-38`); the requirement that it not
depend on NOVA's own health is not.

**The residual risk, stated:** break-glass is a path around normal *availability* controls. It
is bounded to the control plane by `B-1` and `B-5`, time-boxed by `B-4`, and made loud by `B-3`
— but an attacker obtaining break-glass credentials obtains **control-plane recovery access**,
which includes the ability to repair (and therefore potentially to alter) policy infrastructure.
That is a genuine and accepted weakness. It is *not* direct access to client data, and the
architecture must not be implemented in a way that makes it so.

---

## 4. Security Incident Response

An incident is any confirmed or suspected violation of an invariant. Section 03 defined the
credential-exposure response ([`AUTHORIZATION_MODEL.md`](./AUTHORIZATION_MODEL.md) §5.1);
this generalizes it.

```text
Detect → Contain → Assess → Eradicate → Recover → Record → Improve
```

| Incident | Immediate containment |
| --- | --- |
| **Credential ingress or exposure** | Treat as compromised; revoke and rotate; purge and cascade; escalate |
| **Cross-scope access attempt** | Terminate the execution; the agent's boundary attempt is a failure condition, not a retryable error |
| **Confirmed cross-scope disclosure** | Emergency stop on the affected scopes; assess blast radius via lineage; notify James immediately |
| **Suspected PDP compromise** | Emergency stop. Authorization cannot be trusted; isolation may still hold if enforcement is independent ([`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md) §4) |
| **Secrets store compromise** | Rotate **everything**; assume all bindings exposed; notify affected external systems |
| **Sandbox escape** | Destroy the sandbox; revoke its brokered credentials; quarantine its output; do not merge |
| **Poisoned memory or knowledge** | Quarantine the source, re-evaluate derived items via lineage, lower source trust |

**Two rules across all of them:**

1. **Containment precedes investigation.** Stop the bleeding, then diagnose.
2. **Incidents are never silently resolved.** Every incident reaches James, and the record is
   append-only (`I-47`).

**Lineage is the assessment tool.** "What else is affected?" is answerable only because every
derivation records its sources ([ADR 0010](../decisions/0010-derived-data-inheritance.md)) —
which is why `I-53` fails a derivation that cannot record lineage.

---

## 5. Deferred

| Deferred | Owner |
| --- | --- |
| Detection tooling and alerting technology | 28 |
| Break-glass credential storage mechanism | 04 → 29, with `D-10` |
| Notification routing for security events | 25 (`D-32`) |
| Backup and restore mechanics, including `I-55` enforcement | 36 (`D-15`) |

Invariants: `I-74`–`I-76`.
