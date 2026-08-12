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

**Stated honestly:** scanning is **heuristic and will miss novel formats**. It reduces
ingress; it does not close it. This is the residual risk James accepted, and it is not
improved by Section 04 — only made operational.

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
