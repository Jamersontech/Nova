# Authorization Model

**Status:** Proposed — Section 03, pending James's approval.
**Extends:** [`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md), which established
the single Policy Decision Point, risk classes, and approval modes. This document defines
the elements the PDP evaluates and how a decision is reached. **No authorization engine is
implemented here.**

---

## 1. The Question

> **Can this specific actor perform this specific action against this specific resource, in
> this specific context, right now?**

Every word is load-bearing. Dropping *"right now"* produces permissions that outlive their
purpose; dropping *"in this context"* produces the confused deputy.

---

## 2. Elements

| Element | Is | Never is |
| --- | --- | --- |
| **Subject** | The execution identity requesting the action | The human who started the session |
| **Resource** | The specific thing acted upon, owned by exactly one scope | A resource *type* |
| **Action** | The operation, carrying a risk class | A tool name |
| **Scope** | The resource's owning node | The subject's "location" |
| **Context** | The Context Token: scope path + rights + expiry | A conversation |
| **Policy** | A rule producing allow/deny/approval-required | A preference |
| **Grant** | An explicit right for a subject over a scope | Inferred from anything |
| **Denial** | An explicit refusal | The absence of a grant (that is *default deny*) |
| **Approval** | A human authorization for one action, once | A standing state |
| **Credential binding** | A resolvable reference to an external secret | The secret |
| **Execution context** | The runtime envelope: identity, token, limits, trace | Ambient state |

**Grant vs denial matters:** an explicit denial **overrides any grant** and cannot be
outvoted by a broader permission. Default deny handles absence; explicit denial handles
prohibition.

---

## 3. Decision Sequence

Evaluated in order. **Any step may deny; no step may widen.**

```text
1. Is the context valid?          expired · revoked · malformed        → DENY
2. Is the subject known?          unrecognized execution identity      → DENY
3. Does the token cover the resource's owning scope?                   → DENY if not
4. Is there an explicit denial?                                        → DENY
5. Is there a grant for (subject, action, resource type, scope)?       → DENY if none
6. Is the action's risk class within the token's ceiling?              → DENY if not
7. Does classification permit this action here?                        → DENY if not
8. Are conditions satisfied?      time · rate · sensitivity            → DENY if not
9. Does the risk class require approval?                → APPROVAL REQUIRED
10. Otherwise                                                          → ALLOW
```

Step 3 before step 5 is deliberate: **scope containment is checked before permissions
exist.** A grant cannot rescue a resource outside the token's scope, which is what makes
"Client A's token can never reach Client B" true regardless of how permissions are
configured.

**Every outcome is recorded** — allow, deny, and approval-required alike. Denials are the
more interesting signal.

---

## 4. Fail-Closed

If the PDP is unavailable, unreachable, or returns an error, the answer is **deny**. There
is no degraded mode, no cached-allow fallback, no "assume the last answer."

This is an availability cost accepted knowingly ([`KNOWN_RISKS.md`](./KNOWN_RISKS.md) §2):
NOVA stopping is recoverable; NOVA acting unauthorized may not be.

**Read decisions may be cached within a single context's lifetime**, keyed to that token,
and invalidated by revocation or emergency stop. Nothing else is cached.

---

## 5. Credentials Are References

*Full reasoning: [ADR 0009](../decisions/0009-credentials-are-references.md).*

Inside NOVA a credential is a **binding**, never a secret:

```text
Credential Binding
├── id                  stable reference
├── scope               exactly one node — the only scope that may use it
├── external system     what it authenticates to
├── permitted operations  narrower than the secret may technically allow
├── state               active · expiring · expired · revoked
└── (no secret material — ever)
```

The secret itself lives only in secrets storage, reachable only by the Credential Broker,
and is injected at the outbound call boundary.

**The rule that makes this enforceable:** credential material is not a data classification —
it is a **separate substance** that may not be stored in, copied into, or derived into
memory, knowledge, documents, events, audit records, model prompts, or logs. A credential
appearing in any of these is an incident, not a misclassification.

**Possession is not authority.** Holding a binding grants nothing; the broker re-checks
scope and policy at every use.

### 5.1 If credential material appears where it should not

*Added during Section 03 self-critique: the model stated this must never happen but defined
no response when it does.*

A credential appearing in memory, a log, a prompt, an export, a document, or an audit payload
is an **incident** (`I-21`). Prohibition is not a response, so the response is defined:

1. **Treat the credential as compromised.** Not "possibly exposed" — compromised. It may have
   reached a model provider, a log aggregator, or a backup already.
2. **Revoke and rotate it.** Revocation affects only its scope (`I-25`).
3. **Purge the containing item**, and cascade through lineage to every derived copy
   ([ADR 0013](../decisions/0013-deletion-and-forgetting.md)) — a summary of a log containing
   a secret contains the secret.
4. **Record the incident** — where it appeared, which binding, when, and what was purged.
   Never the value.
5. **Escalate to James immediately.** This is not a self-healing condition.
6. **Fix the path.** A credential reaching ordinary storage means some code path handled
   secret material, which contradicts the broker model. The leak is a symptom; the path is
   the defect.

**Purging alone is insufficient.** A secret that reached storage must be assumed to have
reached everything downstream of that storage, which is why rotation is step 2 and not a
last resort.

---

## 6. Temporary and Emergency

**Temporary grants** require an expiry — one with no expiry is rejected at creation.
Expiry is enforced by the PDP, not by cleanup jobs, so a missed cleanup cannot silently
extend access.

**Revocation** takes effect at the next decision. In-flight executions holding a revoked
token fail closed at their next enforcement point.

**Emergency stop** invalidates all contexts, denies all new decisions except James's own,
and halts autonomous work. It is enforced at the enforcement points rather than requested
of the components being stopped — an unhealthy orchestrator is exactly when it is needed.

---

## 7. What Section 3 Does Not Decide

The engine, policy language, storage, evaluation performance, and caching implementation
are deferred (`D-09`, `D-10`, `D-34`). Section 3 fixes *what must be evaluated and in what
order*; Section 04 builds it.
