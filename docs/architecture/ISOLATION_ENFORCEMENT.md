# Isolation Enforcement

**Status:** Proposed — Section 04, pending James's approval.
**Owns:** `D-33` — physical isolation and enforcement below the query layer.
**Purpose:** State precisely what "enforcement below the query layer" requires, so that
`I-03` and `I-33` become structural rather than asserted — **without selecting a technology.**

`D-02` remains deferred. This document defines the requirement a future storage choice must
satisfy and the criteria by which candidates are judged. It names no product.

---

## 1. The Problem This Solves

`I-03` requires that an execution in Client A's scope cannot read, write, or enumerate Client
B's resources by any path. Section 03 marked it **[PHYS]** because the conceptual model alone
cannot deliver it: if isolation is enforced only by application code adding a scope filter to
each query, then `I-03` holds exactly as long as every query is written correctly, forever.

That is not a structural property. It is a coding convention with a security label.

> **The requirement: a query that omits, mistakes, or maliciously removes its scope
> constraint must return nothing rather than another scope's data.**

---

## 2. The Enforcement Requirement

**R-1 — Enforcement below the query layer.** Scope restriction must be applied by a layer the
application cannot bypass by constructing a different query. A query with no scope predicate
must yield an empty result or an error — never unrestricted data.

**R-2 — Binding to execution scope.** The restriction must derive from the execution's scope
identity, established at connection or session establishment and **not modifiable by the
executing code** for the duration of that execution.

**R-3 — Enumeration is access.** Listing identifiers, counting rows, or observing existence in
another scope is a violation. Restriction applies to metadata and existence, not only content.

**R-4 — Uniform across access paths.** Reads, writes, deletes, searches, index lookups,
aggregate queries, and administrative paths are all subject to it. A single unrestricted path
defeats the property.

**R-5 — Deny on ambiguity.** If the enforcing layer cannot determine the execution's scope,
it denies. There is no unrestricted default.

**R-6 — Independently testable.** It must be possible to attempt a cross-scope read *with
deliberately malformed application code* and observe refusal at the enforcement layer.

**R-7 — Independent of the PDP.** The enforcing layer must not consult the Policy Decision
Point to decide scope restriction. See §4 — this is what makes the property survive a
compromised PDP.

**R-8 — Failure is denial.** If the enforcing layer is unavailable or errors, access is
denied, consistent with `I-17`.

---

## 3. What "Below the Query Layer" Means

```text
   Application / agent code            ← may be buggy, confused, or hostile
   ────────────────────────────────
   Query construction                  ← may omit the scope predicate
   ────────────────────────────────
 ▶ ENFORCEMENT LAYER                   ← applies scope restriction regardless
   ────────────────────────────────
   Storage
```

The enforcement layer sits **beneath** the point where queries are composed. Everything above
it is treated as untrusted for isolation purposes — including NOVA's own code.

**Three families of mechanism satisfy this, in principle.** They are recorded as *candidates
with tradeoffs*, not as a selection:

| Family | How it satisfies R-1/R-2 | Cost |
| --- | --- | --- |
| **Per-scope physical separation** | Each isolated scope's data lives in a separate store; the connection reaches only one | Strongest isolation; heaviest operationally; cross-scope aggregation becomes N connections; provisioning per client |
| **Per-scope namespace separation** | Separate schema/namespace per isolated scope; the session is bound to one | Strong; moderate operational cost; migration applies per namespace |
| **Engine-enforced row restriction** | The engine applies a scope predicate from session state that the query cannot override | Lightest operationally; depends on the engine enforcing it, and on session state being unforgeable from application code |

**The isolation frontier.** Full separation at every scope node is impractical. The
requirement is that separation exists at the **client scope** and above — the boundary
`I-03` protects. Within a client, project and environment separation may be enforced by the
same mechanism at lower granularity.

---

## 4. Defense in Depth: Isolation Survives a Compromised PDP

*This is the security contribution of Section 04 to the `T-19` residual risk James accepted.*

Section 03 recorded that a compromised PDP is a total authorization failure: it returns
`ALLOW`, and every enforcement point obeys. That remains true **for authorization**.

**It need not be true for client isolation.** If the enforcement layer derives scope
restriction from the execution's bound scope identity (**R-2**) and never consults the PDP
(**R-7**), then a compromised PDP granting `ALLOW` for a Client B resource still produces
**no data**, because the storage connection is bound to Client A and cannot reach Client B's
partition.

```text
Compromised PDP  →  says ALLOW for Client B's resource
Execution         →  bound to Client A at connection establishment
Enforcement layer →  applies Client A restriction — does not ask the PDP
Result            →  empty / denied
```

**Two independent things must fail** for cross-client access: the PDP *and* the enforcement
layer's scope binding. That is a meaningful reduction in `T-19`, and it is the reason **R-7**
is a requirement rather than an implementation detail.

**Stated precisely, and no further.** This does **not** make a compromised PDP survivable in
general — such a PDP can still authorize destructive, irreversible, and unapproved actions
*within* the compromised execution's own scope, approve nothing legitimately, and lie in
every other respect. It also assumes the attacker cannot forge the scope binding itself; an
attacker with control of connection establishment defeats it. `T-19` is **reduced in blast
radius, not resolved.**

---

## 5. Evaluation Criteria for the Future Mechanism

When `D-02` is decided (Section 29), the storage choice must be evaluated against these, and
**a candidate that cannot satisfy R-1, R-2, R-6, and R-7 is disqualified regardless of other
merits**:

| # | Criterion |
| --- | --- |
| C-1 | Can a query lacking a scope predicate return another scope's data? Must be **no** |
| C-2 | Can application code alter its own scope binding mid-execution? Must be **no** |
| C-3 | Does enforcement cover enumeration, counts, and existence checks? Must be **yes** |
| C-4 | Does it apply to every access path including administrative and analytical? Must be **yes** |
| C-5 | Can cross-scope violation be tested with deliberately hostile queries? Must be **yes** |
| C-6 | Is enforcement independent of the PDP? Must be **yes** |
| C-7 | What is the operational cost per new client scope? Informational |
| C-8 | How does it behave under restore, migration, and backup? Must preserve partitioning (`I-55`) |
| C-9 | Does it support per-scope encryption keys? (See [`ENCRYPTION_REQUIREMENTS.md`](./ENCRYPTION_REQUIREMENTS.md)) |

---

## 6. What Section 04 Does *Not* Decide

**No technology is selected.** `D-02` remains deferred to Section 29. `D-33` is resolved as a
**requirement**, not a product: the mechanism family, vendor, and configuration are chosen
when `D-02` is decided, and must be evaluated against §5.

**`I-03` and `I-33` remain `[PHYS]` and remain unverified.** This document specifies what
would satisfy them; nothing yet does.

Invariants: `I-60`–`I-63`.
