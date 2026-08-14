# 0019 — Secrets Storage Is Separate, Broker-Only, and Per-Scope Isolated

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 04
**Accepted:** 2026-08-13 by James
**Section:** 04
**Partially resolves:** `D-10` — requirements, not the product

## Decision
Secret material resides in a store **separate from NOVA's data store**, reachable only by the
Credential Broker, isolated per scope, with authenticated and audited retrieval, rotation
without code change, individual revocation, and fail-closed behaviour. Backups of the data
store contain no secret material. **No secrets-storage technology is selected.**

## Context
ADR 0009 made credentials references rather than data. Section 04 must state what the store
holding the actual secrets has to satisfy.

## Problem
ADR 0009 concentrates every secret in one place. That is correct — the alternative spreads
secrets across every data path — but it makes that store the highest-value target in NOVA, and
"we'll protect it well" is not a requirement.

## Options Considered
1. **Secrets in the primary data store, encrypted.** Simplest operationally; a data-layer
   compromise yields secrets, and `I-21` becomes a discipline rather than a structural fact.
2. **Separate store, broker-only, per-scope isolated.** Data-layer compromise yields no
   secrets; adds a second store to operate, secure, back up, and keep available.
3. **Per-scope separate stores.** Strongest blast-radius containment; operationally
   disproportionate at NOVA's scale, and multiplies the availability surface.

## Decision Made
Option 2, with per-scope *isolation of retrieval authority* inside the store — capturing most
of option 3's containment without its operational cost.

## Reason
`I-21` states no credential material lives in memory, documents, exports, or backups. If
secrets share the data store, that invariant depends on every data path being correct forever
— the same failure mode ADR 0016 rejects for isolation. Separation makes it structural.

## Tradeoffs
**Advantages:** data-layer compromise yields no secrets; rotation and revocation are per
binding; the broker is a single auditable choke point; `S-1` makes `I-21` structural.
**Disadvantages:** a second store to secure, operate, and keep available; the broker is on
every outbound path, so its availability gates all external work; store compromise is still
catastrophic — reduced in likelihood, not consequence.

## Consequences
The broker fails closed (`S-8`), so secrets-store unavailability stops all outbound work.
Ingress detection is operationalized but remains heuristic and does not close the ingress path
James accepted. Invariants `I-68`–`I-70`.

## What Would Change This
Operational experience showing two stores is unsustainable — in which case the answer is a
managed separate store, not merging secrets into the data model.
