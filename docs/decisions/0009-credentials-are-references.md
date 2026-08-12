# 0009 — Credentials Are References, Never Data

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 03
**Section:** 03

## Decision
Inside NOVA a credential is a **binding** — a scoped, stateful reference — never secret
material. Secrets live only in secrets storage, reachable only by the Credential Broker, and
are injected at the outbound call boundary. Credential material is a **separate substance**,
not a data classification level: it may not be stored in, copied into, or derived into
memory, knowledge, documents, events, audit records, model prompts, logs, exports, or
backups.

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
2. **Credential as a separate substance, referenced by binding.** Data paths cannot leak
   what they cannot hold; requires a broker and a binding concept.
3. **Encrypted-at-rest inside the data model.** Feels safe; decryption must happen
   somewhere, and that somewhere becomes a leak point in agent context.

## Decision Made
Option 2.

## Reason
Option 1 makes leak prevention depend on getting every data path right forever. Option 2
makes it structural: a summarizer cannot leak a credential because it never has one. The
distinction is between "must not" and "cannot."

## Tradeoffs
**Advantages:** memory, summaries, exports, logs, and backups cannot leak secrets; rotation
is central; revocation is per-scope; a compromised agent has nothing to steal.
**Disadvantages:** every outbound call needs a broker round trip; the broker and secrets
storage become the highest-value target; "just read the key from config" is unavailable to
implementers.

## Consequences
A credential appearing anywhere in the data model is an **incident**, not a
misclassification. Invariants `I-21`–`I-25`.

## What Would Change This
Nothing foreseeable. If broker latency proves prohibitive the answer is a faster broker, not
credentials in the data model.
