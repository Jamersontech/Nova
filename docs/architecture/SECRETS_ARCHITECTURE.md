# Secrets Architecture

**Status:** Proposed — Section 04, pending James's approval.
**Covers:** requirements on secrets storage and the Credential Broker protocol.
**Implements:** [ADR 0009](../decisions/0009-credentials-are-references.md) (credentials are
references) and [ADR 0003](../decisions/0003-context-token-and-brokered-credentials.md).

**No secrets-storage technology is selected.** `D-10` remains deferred; this document defines
what a candidate must satisfy.

---

## 1. Why This Is the Highest-Value Target

ADR 0009 deliberately concentrates all secret material in one place so that no data path can
leak it. The consequence, accepted by James, is that **compromise of that store is
catastrophic** — every client's external access at once.

Concentration was still the right choice: the alternative distributes secrets across every
data path and makes leak prevention depend on all of them being correct forever. But it means
the store's requirements are the strictest in NOVA.

---

## 2. Requirements on Secrets Storage

**S-1 — Separate from the data store.** Secret material must not reside in the same store as
NOVA's data model, so that a data-layer compromise does not yield secrets, and so `I-21`
is structural rather than a discipline.

**S-2 — Broker-only access.** Exactly one component — the Credential Broker — may retrieve
secret material. No agent, orchestrator, tool, model path, migration, backup job, or
administrative console retrieves it.

**S-3 — Per-scope isolation.** A compromise of one scope's access path must not yield another
scope's secrets. Retrieval authority is per binding, not per store.

**S-4 — Retrieval is authenticated, authorized, and audited.** Every retrieval records
binding, scope, execution, and outcome — by reference, never value (`I-48`).

**S-5 — Write-mostly-once.** Secrets are written and rotated; they are not read by humans in
normal operation. A routine flow that displays a secret is a design defect.

**S-6 — Rotation without code change.** Rotating a secret must not require redeployment. A
system where rotation is expensive is a system where rotation does not happen.

**S-7 — Individual revocation.** Revoking one binding must not disturb any other scope
(`I-25`).

**S-8 — Fail closed.** If the store is unavailable, outbound calls requiring a credential are
denied, not attempted without one.

**S-9 — Expiry is visible before it bites.** Approaching expiry raises an event so a
credential does not expire silently mid-workflow
([`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md)).

**S-10 — No secret in backups of the data store.** Backups of NOVA's data model must not
contain secret material; the secrets store's own backup is separate and separately protected.

---

## 3. Broker Protocol

```text
1. Tool presents: binding id + Context Token + intended operation
2. Broker asks Policy: does this token's scope cover this binding's scope?      → deny closes
3. Broker checks: is the binding active, unexpired, unrevoked?                  → deny closes
4. Broker checks: is the operation within the binding's permitted operations?   → deny closes
5. Broker retrieves the secret and injects it into the outbound call
6. Broker discards the secret; it is not returned upward
7. Broker records the use — by reference
```

**Step 6 is the property that makes ADR 0009 real.** The secret exists in the outbound request
and nowhere else reachable by NOVA's own components.

**Step 4 exists because external systems over-grant.** A provider's API key may technically
permit far more than the task needs; the binding narrows it, and the broker enforces the
narrowing that the external system does not.

**The broker performs its own scope check (step 2) rather than trusting the caller.** This is
also the second gate that a compromised PDP must defeat
([`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md) §4) — though note the broker *asks*
the PDP here, so a compromised PDP does defeat step 2. The independent defense for secrets is
`S-3` scope isolation and the binding's own state, not the policy check.

---

## 4. Ingress Detection

`I-51` requires tool responses to declare and strip credential-shaped fields, with scanning
for undeclared material. Mechanically:

- **Declared stripping** — response schemas mark credential-bearing fields; the capability
  boundary removes them before the response reaches agent context.
- **Undeclared scanning** — responses are scanned for credential-shaped material. Known
  cases: OAuth refresh and token-issuing endpoints, key-rotation responses, and error
  payloads that echo request headers.
- **On detection** — the incident response in
  [`AUTHORIZATION_MODEL.md`](./AUTHORIZATION_MODEL.md) §5.1 applies: treat as compromised,
  revoke and rotate, purge and cascade, record without the value, escalate, fix the path.

### 4.1 Generic and unstructured responses

*Added 2026-08-12 following adversarial review (M-4). Schema-based stripping presumes a
meaningful response schema. A generic HTTP/API pass-through tool has none, so declared stripping
does nothing for exactly the tool NOVA is most likely to want.*

**Layered containment, none of which is prevention (`I-84`):**

| Layer | Requirement |
| --- | --- |
| **Tool-specific rules** | A tool whose responses are known to carry credential material (token issuance, key rotation, OAuth refresh) declares them and strips them, regardless of general schema |
| **Raw-response restriction** | A generic pass-through tool must **not** return raw unstructured responses into agent context by default. Responses are parsed, filtered, or summarized at the capability boundary, and raw bodies are available only where a specific declared need exists |
| **Unknown/unstructured handling** | Where a response cannot be structurally understood, it is treated as **potentially credential-bearing**: scanned, and preferentially not placed in durable memory or model context |
| **Heuristic detection** | Applied to all responses, declared or not. **Explicitly best-effort** |
| **Error handling** | Error payloads are scanned with the same rules as success payloads — they are the most common echo path for request headers |
| **Retry handling** | See §4.2 and `I-81` |
| **Logs and telemetry** | Response bodies for CLIENT-CONFIDENTIAL and above are referenced, not copied (`I-48`) |
| **Generated artefacts** | Files written by a sandboxed coding agent are scanned before being treated as reviewable output |

**Stated honestly, and not improved by these layers:** detection is **heuristic and will miss
novel formats**. Restricting raw pass-through reduces exposure; it does not eliminate it, and a
sufficiently unusual credential format in an unstructured body will pass. **Credential ingress
remains possible.** These are containment and minimization requirements, not prevention, and
nothing here should be read as claiming credentials cannot leak.

### 4.2 Retry and reliability paths

*Added 2026-08-12 following adversarial review (M-5).*

The broker discarding the secret (§3 step 6) proves only that the secret is not returned
**upward**. It says nothing about whether the secret persists **sideways**, in the reliability
infrastructure that holds the outbound request.

**Requirement: reliability mechanisms must not become credential persistence mechanisms
(`I-81`).**

| Path | Requirement |
| --- | --- |
| **Retry queues** | A queued retry stores the request **without** injected credential material. Re-injection happens at send time, through the broker, exactly as for the first attempt |
| **Request objects** | The injected form of a request is not retained after the attempt completes |
| **Logs** | Outbound requests are logged by reference; headers and bodies carrying credentials are never logged |
| **Error records** | An error capturing a failed request captures it in pre-injection form |
| **Telemetry** | Records metadata — endpoint, latency, outcome — never the request as sent |
| **Dead-letter queues** | Hold pre-injection requests only. A DLQ is durable and long-lived, so a credential there is a credential at rest in the wrong store |
| **Snapshots / caches** | Never hold injected requests |
| **Credential material arriving in a *response*** | **Not covered by `I-81`.** `I-81` governs credentials NOVA *injects* on the way out. A credential echoed back by an external system — in a success body, an error payload, or a redirect — is **ingress**, governed by `I-84` and §4.1, where detection is **explicitly best-effort**. A DLQ or error record capturing such a response can therefore hold credential material that `I-81` does not reach *(cross-referenced 2026-08-13, N-12)* |

> **`I-81` does not solve ingress, and must not be read as doing so.** It closes the *egress*
> persistence path — injected secrets never reaching queues, DLQs, logs, telemetry, snapshots, or
> error records. The ingress path stays open by `I-84`'s own admission: **credential ingress
> remains possible**, and a novel format in an unstructured body will pass detection.

**Re-injection on retry is deliberate**, and it means each retry is a fresh broker call subject
to the full check sequence — so a credential revoked between attempts is not reusable by a
queued retry.

**Bounded retries are preserved** ([`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md)
§4); only the storage of injected material is prohibited.

**The limit:** this constrains NOVA's own reliability infrastructure. It cannot constrain an
external system that logs the credential it received, or a platform component not built to this
requirement. Verification is deferred to Section 31.

---

## 5. Rotation

| Trigger | Behaviour |
| --- | --- |
| Scheduled | Rotate on a per-binding schedule; no downtime |
| Expiry approaching | Event raised; rotation before expiry (`S-9`) |
| Suspected exposure | **Immediate** rotation, treated as compromise |
| Ingress detected | Immediate rotation (§4) |
| Staff/device change | Rotation of anything that device could reach |

Rotation is per binding. A rotation that requires rotating unrelated scopes' credentials
indicates shared credential material, which violates `I-23`.

---

## 6. Deferred

`D-10` (secrets storage technology) remains **deferred**. §2 is the evaluation criteria for
whichever store is later chosen; a candidate failing `S-1`, `S-2`, `S-3`, or `S-7` is
disqualified.

Invariants: `I-68`–`I-70`.
