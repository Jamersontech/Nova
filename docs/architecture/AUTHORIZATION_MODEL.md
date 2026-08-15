# Authorization Model

**Status:** **Active** — Section 03, approved by James 2026-08-12 (as amended, commit 0917de5).
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
| **Execution binding** ² | The concrete substrate a tool action will use: tool identity **and version**, integration, credential binding, resolved in one scope | The tool definition, which is scope-independent |
| **Execution context** | The runtime envelope: identity, token, limits, trace | Ambient state |

> ² ***PROPOSED — added by Section 11, not yet accepted*** *(2026-08-15; authority
> [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), Proposed;
> removed and the accepted table restored verbatim if rejected).* **`Action` above is *"the
> operation, carrying a risk class"* and explicitly *"never a tool name"* — but the operation's
> actual consequence is produced by the integration and credential bound in the current scope**
> ([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §1), which no
> element named. The same tool, the same schema-valid and envelope-covered arguments, reaches a
> different external system with different semantics depending on where it is bound. `I-114` makes
> that substrate an element the decision sees; **no new permission model is introduced** — it is an
> input to the sequence below, not a parallel one.

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

**The execution binding is resolved before step 1, not after step 10.** ***PROPOSED — added by
Section 11, not yet accepted*** *(2026-08-15; same authority as ² above).* **The ten steps are
unchanged, unreordered, and none is added** — what changes is that for a consequence-producing tool
action the **execution binding is resolved first and is an input** to steps 5 through 8, so the
question at step 5 is *"a grant for this subject, action, resource type and scope — reached through
this integration and credential binding"* rather than a binding-agnostic one.

**The ordering matters and was wrong in the invocation sequence.**
[`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §3 asks Policy
*"may this token call this tool at this risk?"* and **then** resolves the credential — so the
decision was made before the substrate producing the consequence existed. **Resolve, then decide**
(`I-114`(a)). An unresolvable binding is a **denial**, never a default or a last-known binding.

**The PDP is not made a routing engine.** It does not choose the binding — it receives the resolved
one and decides. Selection remains where it already lives: the integration is bound at a scope node
(§1 of that document), and the enforcement point checks what was selected against what was
authorized (`I-114`(b)). This preserves `P-7` and `P-11` exactly as `I-113` does for composition.

**Where `I-07`'s intersection is enforced.** ***Added by Section 06 — ACCEPTED by James 2026-08-14***
*(2026-08-14; authority [ADR 0029](../decisions/0029-delegated-authority.md) and
[ADR 0031](../decisions/0031-section-06-amendments-to-accepted-architecture.md), both **Accepted** 2026-08-14).* **The ten steps above are unchanged.** This note exists because a
reader checking where `I-07` is enforced finds nothing here and would reasonably conclude nothing
enforces it.

Two of `I-07`'s four inputs are enforced by this sequence: **grants** at step 5 — and only James
creates grants (`I-10`) — and the **token's** scope and risk ceiling at steps 3 and 6, integrity-
bound to the Context service (`I-87`, `P-12`). The **agent definition** is not an input to this
sequence and never becomes one. It is verified **at token issuance** by the Context service, which
refuses to issue beyond it (`I-106`,
[`AGENT_GOVERNANCE.md`](./AGENT_GOVERNANCE.md) §2). **The PDP is deliberately not made an
agent-definition intersection engine:** that would put a registry read on the hot path against
`P-7` and give one component two jobs. Issuance is also the only point where all four inputs exist
together — after issuance the token is already integrity-bound and every enforcement point is
obliged to honour it.

**What this sequence evaluates, and what it does not.** ***PROPOSED — added by Section 08, not yet
accepted*** *(2026-08-14; authority
[ADR 0034](../decisions/0034-the-plan-is-a-security-object.md) and
[ADR 0035](../decisions/0035-section-08-amendments-to-accepted-architecture.md), both Proposed;
removed if either is rejected).* **The ten steps above are unchanged.** They evaluate **one action
against one resource**, exactly as §1 and §2 state.

[`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §2 also says *"the full plan is
authorized as a unit"*. **Both are true, and they are different decisions.** Plan authorization is a
separate **envelope** decision fixing scope, risk ceiling, tool set, cost ceiling and composition
(§2.2 there, `I-113`); the sequence above then runs **per action** inside that envelope. **Neither
substitutes for the other:** an envelope never authorizes an action, and an action's allow never
permits exceeding the envelope.

**The PDP is not made a plan-composition engine.** Composition is checked against the declared
envelope at the enforcement points, not by adding steps here — `P-7` and `P-11` stand.

---

## 4. Fail-Closed

If the PDP is unavailable, unreachable, or returns an error, the answer is **deny**. There
is no degraded mode, no cached-allow fallback, no "assume the last answer."

This is an availability cost accepted knowingly ([`KNOWN_RISKS.md`](./KNOWN_RISKS.md) §2):
NOVA stopping is recoverable; NOVA acting unauthorized may not be.

**Read decisions may be cached within a single context's lifetime**, keyed to that token,
and invalidated by revocation or emergency stop. Nothing else is cached.

### 4.1 Failure behaviour of the other security-critical subsystems

*Added 2026-08-12 following adversarial review, which found three subsystems with no defined
failure behaviour.*

Fail-closed applies to more than the PDP. Each rule below is stated so it is unambiguous
under failure, timeout, malformed response, or unavailability.

| Subsystem | On failure / timeout / malformed / unavailable |
| --- | --- |
| **Policy (PDP)** | **Deny.** No degraded mode, no cached-allow fallback (`I-17`) |
| **Credential Broker** | **Deny.** No outbound call proceeds without a brokered injection |
| **Context service** | **Deny.** An operation with no valid Context Token cannot proceed |
| **Classification** | **Apply the strictest applicable classification** for the creating scope, and deny any action the strictest level forbids. Never default to permissive, never store unclassified (`I-52`) |
| **Lineage recording** | **The derivation fails.** An item that cannot record its lineage is not created (`I-53`) |
| **Audit** | **Deny any action classified above `PREPARE`.** `READ`–`PREPARE` may proceed and are queued for record (`I-54`) |

**Why lineage failure blocks derivation.** A derived item created without lineage is
permanently undeletable through the cascade and permanently unclassifiable by inheritance
([ADR 0013](../decisions/0013-deletion-and-forgetting.md)). Allowing the derivation to
succeed trades a transient failure for a permanent defect.

**Why audit failure blocks only above `PREPARE`.** An action that cannot be recorded should
not occur — but applying that to reads would make NOVA unusable whenever the audit sink
hiccups, and reads at `READ`–`PREPARE` are reversible and low-consequence. The line is drawn
at the same place the approval model draws it
([`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) §4), so there is one boundary
to reason about, not two. Queued records must be durable, and a queue that cannot accept a
record is itself an audit failure.

**These are not independent of the approval model.** An action requiring approval already
requires a recorded approval; if audit is unavailable, that record cannot be written, so the
approval cannot be granted. The rules compose rather than conflict.

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
were deferred by Section 03. **Section 04 fixed the requirements** —
[`POLICY_ENGINE_REQUIREMENTS.md`](./POLICY_ENGINE_REQUIREMENTS.md) for the engine,
[`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) for identity, and
[`SECRETS_ARCHITECTURE.md`](./SECRETS_ARCHITECTURE.md) for the broker — while leaving every
product choice deferred (`D-09`, `D-10`, `D-34`).

**Scope containment (step 3) is *additionally* enforced beneath the query layer**, independently
of this PDP ([ADR 0016](../decisions/0016-isolation-enforced-below-query-layer.md),
[ADR 0017](../decisions/0017-isolation-independent-of-pdp.md)). A compromised PDP that returns
`ALLOW` for another client's resource still yields no data.

**Independent of the PDP — not independent of the Context service.** *(Qualified 2026-08-13,
N-10.)* Both this PDP and the storage scope binding take their input from the same Context Token,
so compromise of the Context service or of token issuance defeats both together (`T-23a`,
`I-62`). No general two-of-two independence is claimed.

**This does not remove or replace the Data Access enforcement point.** The Data Access PEP in
[`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) §2 remains one of the five PEPs and
still asks the PDP for every data access, still running steps 1–10 above in full. Structural
isolation is a **second restriction on reachability, independent of this PDP** — it decides
nothing about authorization and can only deny. Implementing connection-scope binding *instead of* the Data
Access PEP would silently remove grants, risk ceilings, classification and conditions from the
read path, and is prohibited (`I-77`).
