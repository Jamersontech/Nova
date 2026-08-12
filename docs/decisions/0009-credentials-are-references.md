# 0009 — Credentials Are References, Never Data

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 03
**Accepted:** 2026-08-12 by James, as amended in commit 0917de5
**Section:** 03

## Decision
Inside NOVA a credential is a **binding** — a scoped, stateful reference — never secret
material. Secrets live only in secrets storage, reachable only by the Credential Broker, and
are injected at the outbound call boundary. Credential material is a **separate substance**,
not a data classification level: it may not be stored in, copied into, or derived into
memory, knowledge, documents, events, audit records, model prompts, logs, exports, or
backups.

### Scope of this decision — issuance, not ingress

*Amended 2026-08-12 following adversarial review.*

This decision governs how NOVA **issues** credentials. It does not, and cannot, prevent
credential material from **arriving** by other routes.

> **NOVA does not intentionally issue credential material to an agent, and no NOVA storage
> path may persist it.** Credential material may nevertheless *arrive* at an agent — through
> an integration response, an error payload, a sandbox environment variable, a subprocess or
> process listing, a generated file, a screenshot, debugging output, or text supplied by
> James. **Such arrival is an incident to detect and contain, not an event this architecture
> prevents.**

**Credential leakage is not claimed to be impossible.** What is claimed is narrower and
testable: no NOVA component *hands* a secret to an agent, and no NOVA storage path may
retain one.

**External coding agents hold real secrets by design.** Under
[ADR 0005](./0005-external-coding-agent-isolation.md) a sandboxed coding agent receives
narrow, expiring, task-scoped credentials. They are genuine secrets inside that sandbox.
The containment is their narrowness and lifetime, not their absence.

### Required ingress control

Because ingress is real, the boundary must actively defend against it:

- **Tool response schemas must declare credential-shaped fields**, and those fields must be
  **stripped at the capability boundary before the response reaches agent context** (`I-51`).
- **Responses must be scanned** for credential-shaped material even where undeclared —
  OAuth refresh, key-rotation, and error payloads that echo request headers are the known
  cases.
- **Detected ingress triggers the incident response** in
  [`../architecture/AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md) §5.1:
  treat as compromised, revoke and rotate, purge and cascade, record without the value,
  escalate to James, fix the path.

## Context
ADR 0003 established brokered credentials. Section 03 must place credentials in the data
model, which forces the question of what a credential *is* as data.

## Problem
If a credential is modelled as highly-classified data, then every data mechanism — memory,
summarization, export, backup, logging — must handle it correctly forever. One mistake at
any of those points leaks a secret.

## Options Considered
1. **Credential as maximum-classification data.** Uniform with everything else; every data
   path becomes security-critical, and correctness must hold at every one.
2. **Credential as a separate substance, referenced by binding.** Data paths have nothing to
   leak on the issuance path; requires a broker and a binding concept, and does not address
   ingress.
3. **Encrypted-at-rest inside the data model.** Feels safe; decryption must happen
   somewhere, and that somewhere becomes a leak point in agent context.

## Decision Made
Option 2.

## Reason
Option 1 makes leak prevention depend on getting every data path right forever. Option 2
makes it structural on the issuance path: a summarizer has no credential to leak because
NOVA never gives it one. The distinction is between "must not" and "was never handed one" —
it does not extend to credentials arriving by ingress.

## Tradeoffs
**Advantages:** memory, summaries, exports, logs, and backups have no legitimate path to
secret material; rotation is central; revocation is per-scope; a compromised agent has
nothing *issued to it* to steal.
**Disadvantages:** every outbound call needs a broker round trip; the broker and secrets
storage become the highest-value target; "just read the key from config" is unavailable to
implementers.

## Consequences
A credential appearing anywhere in the data model is an **incident**, not a
misclassification. Ingress must be detected at the capability boundary rather than assumed
absent. Invariants `I-21`–`I-25`, `I-51`.

## What Would Change This
Nothing foreseeable. If broker latency proves prohibitive the answer is a faster broker, not
credentials in the data model.
