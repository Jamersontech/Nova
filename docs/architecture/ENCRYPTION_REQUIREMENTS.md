# Encryption Requirements

**Status:** Proposed — Section 04, pending James's approval.
**Covers:** what must be encrypted, where, and how keys relate to the scope tree.
**Owns:** the Section 04 half of `D-35`; hardening and threat-specific measures are Section 38.

**No algorithm, library, key-management product, or provider is selected.** Requirements only.

---

## 1. What Encryption Does and Does Not Buy

Encryption protects data **at rest against storage-layer compromise** and **in transit against
network observation**. It does **not** provide isolation between scopes at runtime — a
compromised execution with a valid scope binding reads plaintext through the normal path.

> **Encryption is not a substitute for [`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md).**
> Isolation prevents reaching another scope's data; encryption limits what a stolen disk,
> backup, or snapshot yields.

Stating this because "it's encrypted" is the most common substitute for an isolation argument.

---

## 2. Requirements

**E-1 — Encrypted in transit, everywhere.** Every hop — surface to NOVA, between services, to
external systems, to model providers, to storage — is encrypted in transit. There is no
"internal network is trusted" exemption.

**E-2 — Encrypted at rest, everywhere data lives.** Primary storage, indexes, caches that
persist, backups, exports at rest, and the secrets store.

**E-3 — Keys scoped to the scope tree.** Key material is partitioned so that a key sufficient
to read Client A's data at rest is **not** sufficient for Client B's. Encryption keys follow
the same "no sibling path" rule as everything else (`I-71`).

**E-4 — Secrets store keyed separately.** The secrets store's keys are distinct from the data
store's, so one compromise does not yield the other (`S-1`).

**E-5 — Rotation without re-architecture.** Key rotation must be possible without data
migration that requires downtime or code change.

**E-6 — Keys are never in the data model.** Key material obeys the same rule as credential
material (`I-21`): it is a separate substance, not classified data.

**E-7 — Backups carry their partitioning.** An encrypted backup must preserve scope key
separation, so restoring one scope cannot decrypt another (`I-55`, `C-8`).

**E-8 — Exports are separately protected.** An export leaving NOVA is protected independently
of NOVA's keys — otherwise portability (Constitution §13) either fails or leaks.

**E-9 — Field-level encryption where classification demands it.** SENSITIVE-PERSONAL and
SECURITY-CRITICAL items may require protection beyond volume-level encryption so that
database-level access does not yield plaintext. Which items, and at what cost, is a Section 38
decision.

**E-10 — Loss of keys is loss of data.** Key custody and recovery must be designed with the
same seriousness as authentication recovery (`A-4`). A key-recovery path weaker than the
encryption is the real strength of the encryption.

---

## 3. Key Scoping

```text
Root key material
├── LIFE domain keys
│   └── per-Area keys (sensitive Areas separately)
├── BUSINESS domain keys
│   ├── KAIRO business keys
│   │   ├── Client A keys        ← cannot decrypt Client B
│   │   └── Client B keys
└── WEALTH domain keys

Secrets store keys — entirely separate hierarchy (E-4)
```

**Why keys mirror scopes.** If one key decrypts everything, then at-rest protection has a
single failure point and offers nothing against an attacker who obtains it. Mirroring the
scope tree means at-rest compromise is bounded by the same boundary as runtime access — one
mental model, one boundary, tested once.

**The cost, stated:** more keys, more rotation surface, and cross-scope aggregation must
decrypt per scope. This is consistent with aggregation already being decomposed per scope
([`CROSS_SCOPE_DATA_RULES.md`](./CROSS_SCOPE_DATA_RULES.md) §6), so it adds no new pattern.

---

## 4. Deferred

| Deferred | Owner |
| --- | --- |
| Algorithms, libraries, key-management technology | 38 *(technology — not selected here)* |
| Field-level encryption scope and cost (`E-9`) | 38 |
| Key custody, escrow, and recovery mechanics (`E-10`) | 04 → 36 |
| Whether the storage choice can support per-scope keys (`C-9`) | 29, when `D-02` is decided |

`D-35` is **partially resolved**: requirements are fixed here; mechanism remains deferred.

Invariants: `I-71`–`I-72`.
