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

**E-11 — Audit keys are separate from client-data keys *and* scope-partitioned.** Stated in full
at §3.2, where it belongs with the key-destruction reasoning it exists to protect (`I-83`).

**E-12 — Audit write capability is authorized by construction for an execution's own bound scope,
lasts only that execution's lifetime, and is not read capability.** No audit writer — including the
PDP (`I-85`) and the Observability responsibility — holds blanket cross-scope write capability or
broad read access. Stated in full at §3.2 (`I-88`).

**E-13 — There is no centralized audit reader.** James reads audit partitions directly, per scope;
no component holds universal cross-scope audit-read capability (`I-89`). The mechanism must be able
to serve a single audit partition without a spanning reader (`I-90`, `[PHYS]`). Stated in full at
§3.2.

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

Audit key hierarchy — entirely separate from client data keys (E-11, §3.2)
├── LIFE audit keys
├── BUSINESS audit keys
│   └── KAIRO audit keys
│       ├── Client A audit keys      ← cannot decrypt Client B's audit records
│       └── Client B audit keys
├── WEALTH audit keys
└── CONTROL-PLANE audit partition keys   ← NOT a client scope; holds no client records
                                            (E-12f, I-92; ADR 0023)
```

**The control-plane audit partition sits in the audit hierarchy, not in the client scope tree.** It
is keyed here because its records are SECURITY-CRITICAL audit, and destroying any client's keys does
not affect it. It is **not** a scope: nothing executes in it, no context resolves to it, and no token
names it.

**Why keys mirror scopes.** If one key decrypts everything, then at-rest protection has a
single failure point and offers nothing against an attacker who obtains it. Mirroring the
scope tree means at-rest compromise is bounded by the same boundary as runtime access — one
mental model, one boundary, tested once.

**The cost, stated:** more keys, more rotation surface, and cross-scope aggregation must
decrypt per scope. This is consistent with aggregation already being decomposed per scope
([`CROSS_SCOPE_DATA_RULES.md`](./CROSS_SCOPE_DATA_RULES.md) §6), so it adds no new pattern.

### 3.1 Ancestor Keys and Shared Resources

*Added 2026-08-12 following adversarial review (M-2). The naive reading of §3 creates an
architecture in which every client execution holds its ancestors' keys and can therefore decrypt
all KAIRO-level data. That reading is prohibited.*

**The situation.** A Client A execution legitimately needs a shared resource held at KAIRO
scope. If that resource is encrypted under a KAIRO-scope key, Client A's execution must be able
to decrypt it — but it must **not** thereby be able to decrypt every KAIRO-scope item.

**The rule: key access is per resource, authorized, and never ambient (`I-82`).**

> **Holding a Context Token whose scope path includes an ancestor does not confer that
> ancestor's key material.** An execution obtains the ability to decrypt a specific shared
> resource because it holds an **explicit grant over that resource** — the same grant `I-05`
> already requires. Key access follows authorization; it does not precede or replace it.

```text
Client A execution wants shared resource S at KAIRO scope
  → Data Access PEP → PDP: is there a grant for A over S?     ← no grant, no access
  → grant confirmed
  → key access for S released for this operation only
  → S decrypted
  ✗ No other KAIRO-scope item becomes decryptable
```

**Consequences of this rule:**

| Concern | Position |
| --- | --- |
| **Ancestor keys** | Not held ambiently by descendants. Ancestor-scope key access is released per authorized resource, per operation |
| **Descendant access** | Downward *reachability* is permitted by the scope tree; downward *decryption* still requires a grant (`I-05`, `I-82`) |
| **Shared-resource classification** | A shared resource carries a classification like any other item. CLIENT-CONFIDENTIAL cannot exist at a shared scope at all (`I-29`) |
| **Misclassification** | If a client-confidential item were wrongly placed at KAIRO scope, only descendants **granted that specific resource** could decrypt it — the blast radius is the grant list, not every client. Misclassification remains a defect; this bounds it |
| **Least privilege** | Key access is the narrowest that satisfies the operation: one resource, one operation, not a scope's whole key |
| **Key-access authorization** | Every release of ancestor-scope key access is an authorization event and is audited like any other cross-scope access (`I-49`) |
| **Failure behaviour** | If the grant cannot be confirmed, or key access cannot be established, the operation is **denied**. There is no fallback to broader key access |

**`I-71` is preserved and strengthened.** A key sufficient for Client A remains insufficient for
Client B — and additionally, Client A's *ancestor* key access is not a standing capability that
could be turned toward a sibling's data held at a shared scope.

**Not selected here:** the mechanism by which per-resource key access is released (`D-35`).
Envelope schemes, per-resource wrapping, and broker-mediated release are all candidate families;
none is chosen, and no cryptographic product is named.

---

## 3.2 Key Destruction vs Audit Retention

*Added 2026-08-12 following adversarial review (M-3). ADR 0020 listed key destruction as
supporting client offboarding; `I-47` requires audit records to be retained and append-only.
Reconciled here.*

**Determination: security audit records are NOT encrypted under client-scope keys (`I-83`).**

Audit records are classified SECURITY-CRITICAL, not CLIENT-CONFIDENTIAL. They are keyed under a
**separate audit key hierarchy**, distinct from client-data keys and from the secrets store's
keys. Destroying a client's data keys therefore does not destroy that client's audit records.

This is possible without weakening `I-48` because audit records contain **references and
identifiers, never client content**. There is nothing in an audit record that needs to be
crypto-shredded with the client's data, precisely because the content was never there.

### The audit hierarchy is separate *and* scope-partitioned

*Added 2026-08-12 following final review (F-4). "Separate from client-data keys" was stated;
"partitioned" was not. Read literally, the earlier text permitted a single global audit key —
which would mean one key giving at-rest access to every client's audit records, reintroducing
precisely the flat-key failure `E-3` exists to prevent, one layer over.*

**E-11 — The audit key hierarchy is itself scoped to the scope tree.** Audit key material is
partitioned per applicable scope, mirroring the same tree as client-data keys but as an
independent hierarchy. **There is no single global audit key**, and a key sufficient to read one
scope's audit records at rest is not sufficient for a sibling's (`I-83`, extending `I-71`'s rule
to audit).

| Property | Position |
| --- | --- |
| **Separation from client data** | Absolute. Audit keys are not derived from, wrapped by, or destroyed with client-data keys. This is what preserves the M-3 determination |
| **Partitioning** | Per applicable scope, following the scope tree. Not one key, not one key per domain |
| **Sibling reachability** | None. No client's key material — data or audit — yields a sibling's audit records at rest |
| **Ancestor access (executions)** | **None exists, and `I-82` is not what establishes that** *(corrected 2026-08-13, Decision 1)*. An execution has no ancestor-scope audit-key access of any kind: it cannot **read** any audit partition, because the only reader is James (`E-13`, `I-89`), and it cannot **write** outside its own bound scope, because audit-write capability is acquired per execution for that execution's single scope (`E-12a`, `E-12b`, `I-88`). The ancestor question `I-82` answers for **data** keys therefore does not arise for audit keys — there is no ancestor audit-key access to govern |
| **Effect of client-data key destruction** | The client's audit records remain readable, because their keys are in the other hierarchy and are not destroyed (M-3, `I-47`) |
| **Effect on `I-47`** | None. Records remain retained and append-only; partitioning changes *who can read what at rest*, never whether a record may be altered or removed |
| **Records spanning scopes** | A cross-scope access produces records in each participating scope's partition. There is no shared "cross-scope" audit partition that would become a flat corpus |
| **Sibling identifiers in those records** | The record written into one scope's partition must not disclose a sibling's identifiers or resource references. Partitioning the keys does not license writing Client B's identifiers into Client A's partition — `I-03` and `I-48` apply to audit content exactly as they apply to data, and this is where a naive implementation of the row above would break them |
| **Reading across partitions** | Follows `I-86`: audit review across scopes uses serial single-scope reads aggregated above them, not one channel joining several partitions. Multi-key does not mean multi-scope-at-once |
| **James's oversight** | Unaffected by design intent, but it is now a **multi-key** read. Reviewing audit across scopes requires access to each scope's audit key material, per scope — the same decomposition cross-scope aggregation already uses (§3 cost note) |

### The write path is partitioned too

*Added 2026-08-13 (N-4). `E-11` as first written was expressed entirely in read terms — "a key
sufficient **to read**". But `I-18` requires every authorization decision to produce an audit
record, and `I-85` records that those are emitted **by the PDP**; the Observability
responsibility likewise writes audit for the whole system. Read literally, `E-11` therefore
permitted a writer holding every scope's audit key material — the flat-key failure `E-11` exists
to prevent, moved from the storage layer to the writer. James rejected accepting that as residual
risk and directed that partitioning hold on both paths.*

> **Decided by James 2026-08-13 — `S4-P1`, Option A: audit write capability is scope-bound.**
> The pending block that stood here is removed; `E-12` and `I-88` are final in the form below.

**E-12 — Audit write capability is scope-bound, acquired rather than ambient, and is not read
capability.**

Three requirements, stated separately because each fails differently:

**E-12a — Per scope.** A writer may append audit records only to the scope partition of the
execution it is acting for. **No component holds blanket cross-scope audit-write capability** —
not the PDP, not the Observability responsibility, not any administrative path.

**E-12b — Authorized by construction, bounded to the execution's own scope and lifetime.**
*(Resolved 2026-08-13 — `S4-P6`, Option A. See "How this arrived here" below for what it replaces.)*

> **An execution that has been authorized, and whose scope binding is therefore established, may
> write audit records for that scope. That authorization *is* the capability. There is no separate
> release decision, no grant class, and no second authorization authority.**

The execution's already-established scope binding (`I-61`, `I-79`, `I-86`) **is** the authorization
boundary for its audit writes. The capability:

- covers **exactly one scope** — the execution's bound scope, never an ancestor, never a sibling,
  never the tree;
- lasts **exactly the execution's lifetime**, and ends when the execution ends;
- is **not standing, not ambient, and not transferable** — it belongs to the execution, not to the
  component running it;
- **creates no cross-scope capability** under any composition.

```text
execution is authorized, bound to exactly one scope   (I-61, I-79, I-86 — a PDP decision,
                                                       audited under I-18 like any other)
  → that authorization IS the audit-write capability for that scope
  → every emission during the execution writes to that scope only
  → execution ends → capability ends
```

**Why there is no recursion.** Nothing in this path is a second authorization decision, so `I-18`
is never triggered a second time and there is nothing to bootstrap. **`I-18` is untouched and not
exempted**: the execution's own authorization is a decision and does produce a record; audit
emission is a *consequence* of that decision, not a new request for authorization.

**What is no longer recorded, stated plainly.** There is no separate "capability released for scope
X" audit event, because no such event occurs. The scope is already named in the execution's own
authorization record, so no information is lost — but this is one fewer discrete event than the
superseded design would have produced, and that is a real difference rather than a presentational
one.

**E-12d — Superseded, retained for the record.** *(Superseded 2026-08-13 by `S4-P6`, Option A.)*
`E-12d` defined a bootstrap base case: the audit record of a capability release was to be the first
record written under the capability that release granted, terminating the recursion at depth one.
That was the `D` half of `S4-P5`.

**It is no longer required, because the recursion it terminated no longer occurs.** Option A
removes the release decision entirely, so there is no first-record problem and nothing to
bootstrap. `E-12d` is recorded here as superseded rather than deleted, so the reasoning chain
stays legible: `S4-P5` solved the circularity by terminating it; `S4-P6` dissolved it.

**E-12c — Write is not read.** Holding write capability for a partition confers **no** ability to
read it, any other partition, or the hierarchy as a whole (`I-88`).

**E-12e — Attempted and denied events: the decision is the authority (`W-2`, `I-91`).** *(Added
2026-08-13, `S4-P9`, [ADR 0023](../decisions/0023-audit-record-writer-authority.md).)* The record of
an authorization decision — **allow, deny, or approval-required alike** — is written under the
authority of **that decision**, into the partition of the scope the decision concerned. This covers
denials, pre-binding refusals (`I-78`, `I-79`), token rejections (`I-87`), broker denials, and every
attempt that never became an authorized execution.

**`W-2` applies only where the decision concerned a client scope.** Authentication and recovery
precede context resolution — [`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §1: *"Authentication
establishes who is acting. Authorization decides whether they may."* At a failed authentication or a
failed recovery (`A-4`) **no client scope exists**, so those records are **control-plane events under
`E-12f`/`I-92`** — they are never forced into a client partition to satisfy a placement rule.
*(Closed 2026-08-13, `HIGH-1`.)* **No
execution, binding, grant class or second authority is required**: `I-18` already makes the decision
produce a record, and `E-12e` states that the decision is the authority for the record of itself. The
authority covers **one record of one decision** — not standing, not transferable, and unable to reach
a scope the decision did not concern.

**A denied cross-scope attempt** is recorded in the **actor's** scope. The target's partition
receives nothing naming the actor (`E-11`), and the security event goes to the control-plane
partition ([`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §6 already classifies it as one).
**`I-49` needs no amendment**: `CROSS_SCOPE_DATA_RULES.md` §6 already decomposes cross-scope work into
per-scope sub-executions, so "per scope touched" never requires sibling identity to cross a
partition — and a denial is not an access.

**E-12f — Control-plane events: the control-plane audit partition (`W-3`, `I-92`).** Operations that
concern no client scope are recorded in a **control-plane audit partition that is not a node in the
client scope tree**. It is **not a scope kind** and is not governed by the `I-06` contract. **No
component acquires client-scope write capability by writing here** — which is precisely what makes
`S4-P1` hold by construction rather than by prohibition. It must carry no client-scope content,
identifiers or resource references (`I-48`, `E-11`), and reading it is `I-89`: James only.

**E-14a — Event identity resolves uncertain persistence (`I-93`).** *(Added 2026-08-13, `HIGH-2`.)*
NOVA's accepted event model already states that events *"may arrive late, out of order, or more than
once"* and that consumers must be idempotent
([`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](./EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §2), and that
every action emits a record **linked by trace id**. Audit records inherit that model rather than a new
one:

| Question | Rule |
| --- | --- |
| **Event identity** | Every mandatory audit record carries a **deterministic identity** derived from the operation it records and its trace id. The same operation always yields the same identity |
| **Retry after an uncertain write** | **Retry.** Delivery is at-least-once, as the accepted event model already assumes |
| **Duplicate physical writes** | **One logical record.** Writes sharing an identity are the same event; duplicates collapse on read. `I-47` is unaffected — nothing is removed |
| **Acknowledgement lost after persistence** | The record exists and is correct. The caller still fails closed if it cannot confirm — and that is not a contradiction, because a **decision record records that the decision was taken**, while whether the operation proceeded is a **separate record**. No false history is created |
| **Partial persistence** | A record without a resolvable identity is not a record. Treated as failed; `E-14` applies |
| **Identity cannot be established** | Treated as a failed write; `E-14` applies |
| **Exactly-once** | **Not required and not claimed.** Deterministic identity plus at-least-once plus read-side collapse is sufficient, and matches the accepted model |

**E-14 — Audit-write failure (`I-93`).** If a record `I-18` requires cannot be durably written, the
operation **fails closed** — decisions resolve to deny, executions do not start, control-plane
operations do not proceed, scopes do not activate. **Operations that restrict or remove access
proceed instead**: refusing to stop is failing *open*. Emergency stop is never withheld for a failed
record; break-glass proceeds only with an out-of-band record on `B-7`'s reasoning. The failure record
is a control-plane event; **if it too fails, no further attempt is made** — one attempt, then stop —
and the condition surfaces as an incident (`I-76`). **This is what bounds the recursion:** the failure
record is not itself retried under `E-14a`, so no failure loop can form. **No fallback writer and no
"best effort" reading of `I-18`.**

### Why `I-82` does not govern this

*Stated explicitly because `E-12b` previously cited it and the citation was unsupported.*

`I-82` governs **decryption of an ancestor-scope shared resource**, and requires an **explicit
grant over that resource**. An audit write is **none of those things**: it is not decryption, it
is not ancestor-scoped, and there is no "grant over an audit partition" anywhere in the model.
`I-82` also requires its own release to be audited, so invoking it added a second recursion rather
than resolving the first.

**`I-82` is not the authority for audit-write capability and is not cited as one.** It remains
what it was — the ancestor-key rule — and is unchanged. `E-12a`–`E-12c` and `I-88` are
self-standing: under `S4-P6` (Option A) the execution's own already-granted authorization is the
capability, so there is no release to authorize, no grant class to define, and **no second
authorization authority**.

### How this arrived here

*Three passes, recorded so the reasoning is auditable.*

| Stage | Rule | Why it changed |
| --- | --- | --- |
| Original | Capability released **per emission**, citing `I-82` | Circular: emitting required a release, the release was an authorization decision, `I-18` required a record, emitting that record required a release. Also mis-cited `I-82` |
| `S4-P5` (C + D) | Released **per execution**, with the release record as a depth-one base case | Terminated the recursion, but left the release as an authorization decision whose step-5 grant was never defined — an implementer would have had to invent one |
| **`S4-P6` (Option A)** | **Authorized by construction from the execution's own authorization** | Removes the release decision, so there is no recursion and no undefined grant. `I-18` untouched, `I-14` untouched, ADR 0014's sequence unchanged |

| Question | Position |
| --- | --- |
| **Write ≠ read** | Holding write capability for a scope's audit partition confers **no** read capability over it. The two are distinct capabilities over distinct key material, not two uses of one key |
| **Scope of a writer's capability** | **One scope, authorized by construction from the execution's own authorization, lifetime = the execution's lifetime (`E-12a`, `E-12b`).** An execution is bound to exactly one scope (`I-61`, `I-79`, `I-86`), so the capability is inherently scope-bound and cannot span siblings. **This is not standing capability and not cross-scope capability** — it ends when the execution ends |
| **The PDP as writer (`I-85`)** | The PDP emits a decision record **under the capability of the execution it is deciding for**, in that execution's single scope. It holds **no** global audit key, acquires no read access by emitting, and has no capability of its own that spans scopes. A shared service serving several concurrent executions holds one execution-scoped capability per execution — see the concurrency residual below |
| **The Observability responsibility** | Same rule, and no exemption for being the pipeline. It may collect and route audit events, and may append only within the scope of the execution it is acting for. **It does not own or read the audit corpus** (`S4-P2`, Option D) |
| **Append-only interaction (`I-47`)** | Unaffected and reinforced: write capability permits **append only** — never amendment, never deletion, never read-modify-write |
| **Sibling reachability on the write path** | None. A writer's capability for Client A's partition yields nothing for Client B's, in either direction |
| **Reading remains James's** | Read access is governed by `E-11` and §"James's audit access" below. **No writer is a reader**, and no component holds universal cross-scope audit-read capability (`S4-P2`, Option D) |
| **Consistency with `E-3`** | Same principle, one layer over: capability follows the scope tree, and no single credential spans siblings |

**No mechanism is selected.** Whether write-without-read is achieved by separate key material per
direction, by an append-only interface that holds the key beneath it, or by any other family, is
deferred with `D-35` and `D-02`. **No algorithm, protocol, or product is named here**, and this
states a requirement the future mechanism must meet — not a property NOVA has (`I-88` is
`[PHYS]`).

**The bound on a compromised writer, stated exactly.** A compromised writer can forge audit
records **only in the scopes of the executions whose capability it currently holds**, and only by
appending. It cannot reach a scope it is not serving, cannot read what it writes into, cannot amend
or delete anything (`I-47`), and holds nothing that survives those executions. This is a bound, not
an elimination: records forged within a held scope are still permanent under `I-47`, and `I-85`
still means the trail cannot prove its own integrity.

### Three residual risks, stated rather than resolved

**1. The concurrency residual — the honest cost of Option C.** A shared service that serves many
executions at once (the PDP is the obvious case) holds **one execution-scoped capability per
in-flight execution**. Each is bounded to its own single scope, and none can reach a scope that
service is not currently serving — so **this is not blanket cross-scope capability**, and no
component can acquire capability for a scope it is not legitimately serving. But it is broader than
one scope at one instant: **compromise exposes the union of the scopes currently being served.**
The analogous data-plane rule (`I-86`) forbids joining across simultaneously-held scope-bound
channels; the same prohibition applies here — holding several execution-scoped capabilities must
never be used to write across scopes.

**2. The bootstrap failure case — resolved by `S4-P6`, not carried forward.** Under the superseded
`S4-P5` design a capability release could succeed while its bootstrap emission failed, leaving a
usable capability with no decision record. **That window no longer exists**, because there is no
release event to succeed or fail: capability follows the execution's own authorization. This
residual is retired rather than mitigated.

**It changes nothing about completeness.** **The architecture still does not establish that the
audit trail is complete**, and this document does not claim it is — see residual 3.

**3. Suppression by omission is unchanged.** Nothing here verifies that a produced record actually
arrives (`T-26`). `I-18` requires a record to be *produced*; completeness of the trail is not
established by `I-18`, by `E-12`, or by anything else in Section 04.

**`I-47` and `I-85` are preserved exactly as written.** Append-only is unaffected — the bootstrap
record is an append like any other. `I-85` still holds: audit records of authorization decisions
are emitted by the PDP and are **not** independent evidence of its integrity, and the bootstrap
record is no exception.

**The accepted cost.** One capability acquisition per execution rather than per emission. **James
decided the security requirement takes priority** (`S4-P1`); Option C reduces the frequency without
weakening the scope bound, and the remaining performance consequence belongs to `D-35`, `D-02` and
`D-11`, not to a weakening of `E-12`.

> ### DECIDED — `S4-P1` (Option A) and `S4-P2` (Option D), James, 2026-08-13
>
> **`S4-P1` — audit write is scope-bound**, and **`S4-P6` (Option A)** settles what authorizes it:
> the execution's own already-granted authorization, by construction, for its single bound scope
> and its lifetime only. **No blanket cross-scope audit writer exists**, no separate release
> decision occurs, and no grant class is introduced (`E-12a`–`E-12c`, `I-88`). The permissive
> alternative — accepting permanent, irreversible
> forged-audit injection across every scope — was **rejected**.
>
> **`S4-P2` — James reads directly, per scope.** **No centralized audit reader is introduced and
> no new reader component is created.** Observability may collect and route audit events; it does
> **not** own or read the audit corpus. See §"James's audit access" below.
>
> **Consequence for accepted architecture:** [`MASTER_ARCHITECTURE.md`](./MASTER_ARCHITECTURE.md)
> §5, **as accepted on 2026-08-12**, stated that the Observability service **owns** "Logs, traces,
> audit records". That is inconsistent with `S4-P2`, so the row **has been amended** — narrowed to
> collection and routing of audit events, with owning or reading the corpus excluded. The
> amendment is marked
> **PROPOSED** in place and is authorized through
> [ADR 0022](../decisions/0022-section-04-amendments-to-accepted-architecture.md) — it is **not**
> accepted architecture, and is removed if ADR 0022 is rejected.

### James's audit access

*Added 2026-08-13 (N-11); corrected 2026-08-13 (Decision 1). `E-11` previously said ancestor audit
key access "follows `I-82`", importing a data-key rule into the audit hierarchy. That invocation is
removed: **`I-82` governs ancestor-scope data-key/decryption access only** and has no bearing on
audit keys. The authority model is unchanged.*

[`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](./EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §5 states
audit records are **readable only by James**. That is unchanged. What partitioning changes is the
*mechanics* of his read, not his authority:

- **James's authority is not granted to him and is not grant-mediated.** `I-09` and `I-10` stand
  exactly as written: James is the sole approval and grant authority. He does not hold a grant over
  an audit partition, because he is the party who would issue it. `I-82` is not involved either
  way — it governs data keys, not audit keys.
- **His read is per scope, not global.** Reviewing audit across scopes is N per-scope reads
  aggregated above them, exactly as `I-86` requires of any cross-scope work. There is no
  master read that spans partitions.
- **What actually bounds audit-key access, stated directly.** Audit keys are scope-bound and
  partitioned across the scope tree (`E-11`, `I-83`); **no audit-key capability spans sibling
  scopes**, in either direction, for reading or writing; write capability is execution-scoped
  (`E-12`, `I-88`); read capability is held by no component at all (`E-13`, `I-89`). **Audit-key
  access inherits nothing from the data-key rules** — being authorized for a scope's data keys
  confers no audit-key access to that scope or any other. `I-82` is a data-key rule and is neither
  cited nor relied upon here.
- **Cross-scope audit review is itself a cross-scope operation**, recorded per scope touched
  (`I-49`), as `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` §5 already requires.

**No new authority model is introduced, and none of `I-09`, `I-10`, `I-11` is altered.**

### The audit reader — decided `S4-P2`, Option D

*James decided 2026-08-13. **No centralized audit reader exists, and none is created.***

**James reads audit partitions directly, per scope, through the architecture already defined.**
There is no audit-reader service, no aggregation component, and no component holding universal
cross-scope audit-read capability (`I-89` — an architectural property, deliberately **not**
`[PHYS]`). The mechanism must be able to serve one audit partition without a component that spans
partitions; that feasibility is `I-90`, which **is** `[PHYS]` *(split 2026-08-13, Decision 2)*.

| Question | Position |
| --- | --- |
| **Who reads the audit corpus** | **James, directly and per scope.** No component reads it on his behalf |
| **Does Observability read it** | **No.** It may collect and route audit events; it does not own or read the corpus. This requires amending `MASTER_ARCHITECTURE.md` §5 — proposed, see [ADR 0022](../decisions/0022-section-04-amendments-to-accepted-architecture.md) |
| **Is a new component introduced** | **No.** Option D was chosen partly because it introduces none |
| **Cross-scope review** | N per-scope reads, aggregated above them (`I-86`), recorded per scope touched (`I-49`) |
| **Mediating authority** | None. James's access is not grant-mediated; `I-09`/`I-10` are unchanged. `I-82` is a **data-key** rule and does not apply to audit keys in either direction |
| **What no component may hold** | Universal or cross-scope audit-read capability, whether as a reader, a pipeline, or an administrative path (`I-89`) |

**The accepted cost, stated:** an incident review spanning clients is N per-scope reads with no
aggregating component to make it convenient. `SECURITY_OPERATIONS.md` §4 assumes blast-radius
assessment via lineage; that assessment now runs per scope. **This is the chosen trade** — no
component becomes a cross-client audit corpus, which is precisely the failure
[`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](./EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §5 warns
about.

**No technology, tooling, or mechanism is selected** for how James performs a per-scope read.

**The cost, stated:** an incident review that spans clients now requires per-scope audit key
access rather than one read, and key custody (`E-10`) becomes load-bearing for the *audit trail*
as well as for data. Loss of a scope's audit key material is loss of that scope's at-rest audit
evidence — which is why `E-10` applies to this hierarchy in full.

**No cryptographic algorithm, key-management technology, or vendor is selected here** — the same
restraint as the rest of this document (`D-35`, Section 38).

### Three distinct operations, kept apart

| Operation | What it destroys | What survives |
| --- | --- | --- |
| **Deletion of client data** | The items, and derived items via recorded lineage ([ADR 0013](../decisions/0013-deletion-and-forgetting.md)) | Tombstones; audit records |
| **Destruction of client-data encryption keys** | The ability to decrypt that scope's data at rest, including in backups | Audit records (separate key hierarchy); tombstones |
| **Retention of security audit evidence** | Nothing — audit is retained and append-only (`I-47`) | The record that data existed, was accessed, and was deleted |

**Key destruction is a supplement to deletion, not a substitute for it.** It renders at-rest
copies — including backups taken before deletion — undecryptable, which is a genuine
strengthening of `I-55`. It does not remove the obligation to run the lineage cascade, and it
does not reach anything outside NOVA-controlled storage.

**`I-47` is not weakened.** Audit records remain retained, append-only, and readable after a
client's data keys are destroyed. If a future requirement demanded destruction of audit records
themselves, that would conflict with `I-47` and requires a superseding ADR — the same position
ADR 0013 already records.

**Tombstones follow audit, not client data.** A tombstone must remain readable after key
destruction, or deletion becomes unverifiable and re-derivation cannot be prevented.

---

## 4. Deferred

| Deferred | Owner |
| --- | --- |
| Algorithms, libraries, key-management technology | 38 *(technology — not selected here)* |
| Field-level encryption scope and cost (`E-9`) | 38 |
| Key custody, escrow, and recovery mechanics (`E-10`) | 04 → 36 |
| Whether the storage choice can support per-scope keys (`C-9`) | 29, when `D-02` is decided |

`D-35` is **partially resolved**: requirements are fixed here; mechanism remains deferred.

Invariants: `I-71`–`I-72`, `I-82`, `I-83`, `I-88`–`I-93`.
