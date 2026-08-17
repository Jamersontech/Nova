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
identity, bound to the **access channel** at the time that channel is established, and **not
modifiable by the executing code** for the duration of that execution. *(Clarified 2026-08-12,
L-2: "channel" is deliberately abstract — a connection, a session, a signed request context, or
any equivalent. The requirement is that the binding exists and is immutable from above, not that
storage be connection-oriented.)*

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

**R-9 — Additional to authorization, never a substitute for it.** *(Added 2026-08-12, H-1.)*
The enforcement layer sits **beneath** the Data Access Policy Enforcement Point, not in place of
it. Every data access still passes the full ADR 0014 sequence at the PEP — grants, risk ceiling,
classification, conditions — and *then* meets the enforcement layer. **The enforcement layer
decides nothing about authorization; it restricts reachability.** See §3.1.

---

## 3. What "Below the Query Layer" Means

*Diagram corrected 2026-08-12 (F-1). The previous version placed the Data Access PEP above
application/agent code, which would have permitted one authorization check per **request**
rather than per **access** — contradicting accepted `SYSTEM_LAYERS.md` §5 point 5.*

```text
   Request
   ────────────────────────────────
   Authentication / identity
   ────────────────────────────────
   Application / agent execution       ← may be buggy, confused, or hostile
   ────────────────────────────────
   Query construction                  ← may omit the scope predicate
   ────────────────────────────────
   DATA ACCESS PEP  ──asks──▶ PDP     ← EVERY access · grants · risk ceiling ·
   ────────────────────────────────      classification · conditions
 ▶ STRUCTURAL STORAGE ISOLATION        ← applies scope restriction regardless
   ────────────────────────────────      decides nothing; restricts reachability
   Data store
```

**The Data Access PEP is evaluated per data access — not once per request, not once per
session, not once per execution.** Accepted `SYSTEM_LAYERS.md` §5 point 5 states the rule this
implements: *"Any layer → Knowledge & Data: read/write checked against token scope partition."*
An execution issuing ten reads is authorized ten times. A design that authorizes once and then
permits arbitrary subsequent queries beneath that check does not satisfy this document, ADR
0014, or ADR 0001.

### 3.1 Two layers, two different questions

*Added 2026-08-12 following adversarial review (H-1).*

| | Data Access PEP → PDP | Structural enforcement layer |
| --- | --- | --- |
| Question answered | *Is this action authorized?* | *Is this data reachable at all?* |
| Evaluates | Grants, risk ceiling, classification, conditions, approval | Scope binding only |
| Consults the PDP | **Yes — always** | **No, by requirement (R-7)** |
| Can permit an action | Yes | **Never** — it can only deny reachability |
| Removable | **No.** ADR 0001 / ADR 0014, unchanged | No |

**Both must pass.** A read denied by the PDP does not proceed even though it is inside the bound
scope. A read allowed by the PDP still returns nothing if it reaches outside the bound scope.

**The enforcement layer is not an authorization mechanism and must never be described,
implemented, or configured as one.** `I-77`.

The enforcement layer sits **beneath** the point where queries are composed. Everything above
it is treated as untrusted for isolation purposes — including NOVA's own code.

**Three families of mechanism satisfy this, in principle.** They are recorded as *candidates
with tradeoffs*, not as a selection:

| Family | How it satisfies R-1/R-2 | Cost |
| --- | --- | --- |
| **Per-scope physical separation** | Each isolated scope's data lives in a separate store; the connection reaches only one | Strongest isolation; heaviest operationally; cross-scope aggregation becomes N connections; provisioning per client |
| **Per-scope namespace separation** | Separate namespace per isolated scope; the channel is bound to one | Strong; moderate operational cost; migration applies per namespace |
| **Engine-enforced record restriction** | The storage engine itself applies a scope predicate drawn from channel state that the query cannot override | Lightest operationally; depends on the engine providing such a facility, and on channel state being unsettable from application code. *(A mechanism **family**, not a product — several engines offer facilities of this shape and none is selected.)* |

**The isolation frontier.** Full separation at every scope node is impractical. The
requirement is that separation exists at the **client scope** and above — the boundary
`I-03` protects. Within a client, project and environment separation may be enforced by the
same mechanism at lower granularity.

### 3.2 Cross-scope work uses serial single-scope channels

*Added 2026-08-12 following adversarial review (L-6).*

Cross-scope aggregation is decomposed into N independently authorized executions
([`CROSS_SCOPE_DATA_RULES.md`](./CROSS_SCOPE_DATA_RULES.md) §6). At this layer that has a
concrete consequence:

> **Each sub-execution uses its own single-scope channel. No channel is ever bound to more than
> one scope, and no component holds simultaneous scope-bound channels for the purpose of joining
> across them at the storage layer** (`I-86`).

A naive implementation would open one privileged channel spanning several scopes "for
efficiency." That defeats `R-2` entirely: the binding would no longer restrict anything, and
`I-03` would revert to depending on query correctness. Aggregation happens **above** the
executions, on their returned results, never inside a widened channel.

Sequencing is an implementation matter; the prohibition on multi-scope channels is not.

---

## 4. Isolation Survives a Compromised PDP — and Only That

*This is the security contribution of Section 04 to the `T-19` residual risk James accepted.*

> **On the heading.** *(Reworded 2026-08-13, R-10.)* This section was titled "Defense in Depth",
> which invites the reading H-2 withdrew — that two independently-rooted defenses must both fail.
> They must not. The property established here is narrow and one-directional: **the enforcement
> layer does not consult the PDP, so PDP compromise alone yields no cross-client data.** Both
> mechanisms still take their input from the same Context Token and are **not** independent of
> the Context service (§4.2, `T-23a`, `I-62`). Nothing in this section is a claim of general
> two-of-two independence.

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

### 4.1 Where independence actually is — and where it is not

*Rewritten 2026-08-12 following adversarial review (H-2). The previous claim that "two
independent things must fail" was asserted without identifying the trust boundary. Corrected.*

**Scope binding authority.** The **Context service** is the authoritative source of execution
scope identity. It issues the Context Token ([ADR 0003](../decisions/0003-context-token-and-brokered-credentials.md)),
and the scope path in that token is the **sole** input from which the enforcement layer's
binding is derived.

**The Data-Access Boundary is a registered NOVA Core responsibility** as of Section 04 —
[`MASTER_ARCHITECTURE.md`](./MASTER_ARCHITECTURE.md) §5 and
[`SYSTEM_LAYERS.md`](./SYSTEM_LAYERS.md) (Knowledge & Data layer), **both marked ACCEPTED in
place**; the registration is an amendment to accepted Section 02 architecture made through
[ADR 0017](../decisions/0017-isolation-independent-of-pdp.md), **Accepted by James 2026-08-13**,
so the registration is approved architecture. It is a **trusted platform boundary — not a standalone
microservice, not a new speculative subsystem, and not separately deployable**.

*One table, deliberately. (Merged 2026-08-13, N-8 — this section previously carried two
overlapping tables stating the same facts, and they had already drifted apart within a single
amendment pass.)*

| Aspect | Registration |
| --- | --- |
| **Architectural location** | NOVA Core, at the entrance to the Knowledge & Data layer |
| **Responsibility** | Establish an execution's storage scope binding; open and hold the scope-bound channel |
| **Trust boundary** | **TRUSTED** zone ([`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §4) — never the agent runtime, never a sandbox, never application or agent code |
| **Authoritative source of scope identity** | The **Context service** — not the boundary. The boundary derives; it does not decide |
| **Derived from** | The Context Token's scope path, **and nothing else** |
| **Relationship to the Data Access PEP** | **Distinct, and it is not a substitute.** The PEP asks the PDP on **every** data access; the boundary holds the binding. Neither substitutes for the other (`I-77`) |
| **Relationship to the PDP** | **None by requirement.** It never consults the PDP (`R-7`, `I-62`) |
| **Relationship to storage isolation** | It is what makes `R-1`/`R-2` real — the binding it holds is what the enforcement layer restricts against |
| **Verified how** | At establishment the boundary (a) checks the presented Context Token's **integrity** and refuses a token that fails or cannot be verified (`I-87`, `CT-1`–`CT-3`), and (b) checks the binding against that token's scope path. Either failure refuses the channel and is recorded (`I-78`, `I-79`) |
| **What application/agent code may NOT control** | Opening a channel; setting, widening, re-binding or reusing a binding; re-binding mid-execution; opening an unbound or multi-scope channel (`I-78`, `I-86`) |
| **Authorization authority** | **None. It creates no new authorization authority.** It cannot permit an access — its only failure mode is refusing to open a channel |

**No technology is implied.** The boundary is a responsibility, not a product; how the channel
is opened depends on `D-02`/`D-33` and is not decided here.

**Failure behaviour — fail closed in every case (`I-79`).** If scope is **missing**,
**ambiguous**, **invalid**, **inconsistent with the token**, or **cannot be established**, the
channel is not opened and the access is denied. There is no unbound channel and no default
scope.

### 4.2 The honest independence boundary

**Independence holds against PDP compromise. It does not hold against Context service
compromise.**

```text
Compromised PDP           → says ALLOW for Client B
Binding (from Context)    → still Client A
Enforcement layer         → refuses — never asked the PDP
Result                    → no data.        ✅ independence holds

Compromised Context svc   → issues a token naming Client B
PDP                       → correctly authorizes what the token says
Binding                   → Client B, because that is what the token said
Enforcement layer         → permits Client B
Result                    → cross-client access.  ❌ BOTH mechanisms fail together
```

**Both mechanisms derive from the same upstream root: the Context Token.** They are independent
of *each other* — the enforcement layer never asks the PDP — but they share an upstream
dependency. Compromise of the Context service, or of anything that can forge a Context Token,
defeats both at once from a single point.

**Therefore the accurate claim is narrow:**

> Cross-client access requires either **(a)** compromise of both the PDP and the scope-binding
> path, or **(b)** compromise of the Context service or Context Token issuance, which defeats
> both together.

This is a real reduction in `T-19` specifically — PDP compromise alone no longer yields
cross-client data — and it is **not** general two-of-two independence. The Context service
becomes a critical trusted component of the same standing as the PDP, and **nothing in Section
04 mitigates its compromise.** Recorded as `T-23a`.

**No cryptographic unforgeability is claimed** for tokens or bindings. NOVA has no accepted
architectural basis or implementation mechanism for such a claim, and asserting one would be
exactly the overclaim this review exists to prevent.

**What *is* required is detection, not impossibility (`I-87`, added F-3).** A component receiving a
Context Token must be able to detect that it was modified after issuance or fabricated by
something other than the Context service, and must refuse it if that cannot be established
([`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §6). This narrows the set of parties who
can produce an *accepted* token. It changes nothing above: both mechanisms still derive from the
same token, the Context service remains the shared upstream root, and a compromised Context
service issues genuine tokens that pass every integrity check there is. `I-87` does not restore
the withdrawn independence claim and does not reduce `T-23a`.

**Stated precisely, and no further.** This does **not** make a compromised PDP survivable in
general — such a PDP can still authorize destructive, irreversible, and unapproved actions
*within* the compromised execution's own scope, deny legitimate work, and lie in every other
respect. And per §4.1–4.2, the independence is bounded: compromise of the **Context service**
defeats both mechanisms together. `T-19` is **reduced in blast radius, not resolved.**

---

## 4.3 Provisioning a New Client Scope

*Added 2026-08-12 following adversarial review (H-3). Isolation is **established** at
provisioning; if provisioning is wrong, `I-60`–`I-63` fail silently and permanently for that
client while every query looks normal.*

> **Provisioning correctness is itself a security property, not an operational chore.**

### The required lifecycle

```text
Create scope record
  → provision isolation          (partition / namespace / binding, per the chosen mechanism)
  → validate configuration       (does the provisioned artefact match the intended scope?)
  → verify isolation             (does the enforcement layer actually restrict this scope?)
  → run required isolation tests (adversarial, from outside and from within)
  → ACTIVATE                     (only now may protected operations run)
```

**A client scope must not become operationally active merely because its record exists**
(`I-80`). Existence of metadata is not evidence of isolation.

### Required at each stage

| Stage | Requirement |
| --- | --- |
| **Provision** | Create the isolation artefact the chosen mechanism requires. Failure aborts; no partial state is left active |
| **Validate configuration** | The artefact exists, names the intended scope, and carries no inherited or default-wide access |
| **Verify isolation** | Confirm the enforcement layer applies restriction for this scope — observed, not assumed |
| **Isolation tests** | At minimum: (1) an unconstrained query from this scope returns nothing outside it; (2) a query from an existing sibling cannot reach the new scope; (3) a query from the new scope cannot reach that sibling; (4) enumeration and existence checks are restricted (`R-3`); (5) scope-indeterminate access is denied (`R-5`) |
| **Activate** | Permitted **only** when every preceding stage has passed and been recorded |

### Failure behaviour

- **Any stage failing or incomplete leaves the client inactive.** Protected operations are
  refused; the scope may exist as a record but is unusable (`I-80`).
- **Fail closed.** An indeterminate verification result is a failure, not a pass.
- **Rollback / cleanup.** Failed provisioning removes or quarantines partial artefacts so a
  half-provisioned scope cannot later be activated by a retry that skips verification.
- **Recorded.** Provisioning, validation, verification, test outcomes and activation are all
  audited (`I-18`, `I-49`).
- **Re-verification on change.** Migration, restore, or a change to the isolation mechanism
  re-runs verification before the scope returns to active use.

### What this does *not* establish

**Documenting this procedure does not make `I-60`–`I-63` verified.** The lifecycle is a
`[PHYS]`-dependent **requirement**: it cannot be executed until an isolation mechanism exists
(`D-33a`, `D-02`), and the tests it mandates are the Section 31 adversarial isolation tests,
which do not yet exist. `I-80` is marked `[PHYS]` accordingly.

---

## 5. Evaluation Criteria for the Future Mechanism

> **This table is the single authoritative list of storage/isolation evaluation criteria.**
> *(Consolidated 2026-08-13, N-5.)* No other document may state a different range or a different
> disqualification set; where one previously did — ADR 0016's `C-1`–`C-9`, and the register's
> `C-1`–`C-9` — those were stale and are corrected to point here. `C-10` and `C-11` were added by
> the H-3 and F-2 amendments and had not been propagated.

When `D-02` is decided (Section 29), the storage choice is evaluated against all eleven.

> **Decided by James 2026-08-13 — `S4-P4`: the approved disqualification set remains
> `C-1`, `C-2`, `C-5`, `C-6`**, exactly as [ADR 0016](../decisions/0016-isolation-enforced-below-query-layer.md)
> records. **`C-3`, `C-4`, `C-8`, `C-9`, `C-10` and `C-11` are NOT ratified as disqualifying.**
> Their reasoning is retained below marked **PROPOSED**, and a candidate failing one of them is
> **not** thereby rejected. Only the four approved criteria disqualify.

| # | Criterion | Required answer | Weight |
| --- | --- | --- | --- |
| C-1 | Can a query lacking a scope predicate return another scope's data? | **No** | **DISQUALIFYING — approved** (`R-1`, ADR 0016) |
| C-2 | Can application code alter its own scope binding mid-execution? | **No** | **DISQUALIFYING — approved** (`R-2`, ADR 0016) |
| C-3 | Does enforcement cover enumeration, counts, and existence checks? | **Yes** | *Proposed as disqualifying (`R-3`) — **not ratified*** |
| C-4 | Does it apply to every access path including administrative and analytical? | **Yes** | *Proposed as disqualifying (`R-4`) — **not ratified*** |
| C-5 | Can cross-scope violation be tested with deliberately hostile queries? | **Yes** | **DISQUALIFYING — approved** (`R-6`, ADR 0016) |
| C-6 | Is enforcement independent of the PDP? | **Yes** | **DISQUALIFYING — approved** (`R-7`, ADR 0016) |
| C-7 | What is the operational cost per new client scope? | — | Informational |
| C-8 | Does it preserve partitioning under restore, migration, and backup? | **Yes** | *Proposed as disqualifying (`I-55`) — **not ratified*** |
| C-9 | Does it support per-scope encryption keys, for client data **and** for the separate audit key hierarchy? | **Yes** | *Proposed as disqualifying (`I-71`, `I-83`, `E-3`, `E-11`) — **not ratified**; see the note below* |
| C-10 | Can provisioning of a new scope be validated and isolation-verified before activation (§4.3)? | **Yes** | *Proposed as disqualifying (`I-80`) — **not ratified*** |
| C-11 | Can a scope-bound channel be opened only by the **Data-Access Boundary**, never by application code (§4.1)? | **Yes** | *Proposed as disqualifying (`I-78`) — **not ratified**; substantially overlaps `C-2`, which is approved* |

### The proposed additions, retained as proposals — `S4-P4`

*James decided 2026-08-13: **the approved set stays at four.** The reasoning below is kept because
it will be needed when the additions are put formally, and is marked PROPOSED so it cannot be read
as a requirement.*

| | Approved | Proposed in addition |
| --- | --- | --- |
| **Disqualifying** | `C-1`, `C-2`, `C-5`, `C-6` — four, per [ADR 0016](../decisions/0016-isolation-enforced-below-query-layer.md) | `C-3`, `C-4`, `C-8`, `C-9`, `C-10`, `C-11` — **not ratified** |
| **Informational** | `C-7`, and every unratified criterion above for rejection purposes | — |

**The argument for the additions, unratified:** `C-3` and `C-4` restate `R-3`/`R-4`; `C-8`
restates `I-55`; `C-10` restates `I-80`; `C-11` restates `I-78`. Each already carried "Must be
yes" in its criterion text, so the argument is that they were always intended as disqualifying and
merely sat outside the stated list. **That argument was not accepted as sufficient**, and they
remain proposals.

**`C-9` is the weakest case, and James named it specifically.** Unlike the others it carried no
"Must" at all, so promoting it is a genuine change rather than a restatement. It also **grew**
during the consolidation: it now covers the audit key hierarchy, which exists only because of
`E-11` — itself Section 04 material entangled with the `S4-P1`/`S4-P2` decisions. Disqualifying a
storage candidate on the basis of a requirement not yet accepted is the wrong order. It is also the
single largest narrowing of the `D-02` field, since it would require per-scope key support for
**two** independent hierarchies.

**`C-11` is not elevated separately** because it substantially overlaps `C-2`, which is approved:
if application code cannot alter its binding (`C-2`), it largely cannot open its own channel.

**What this means for `D-02`:** a candidate is rejected on `C-1`, `C-2`, `C-5` or `C-6` alone. The
other criteria are evaluated and recorded, and a candidate failing one is a **flagged concern for
James**, not an automatic rejection.

---

## 6. What Section 04 Does *Not* Decide

**No technology is selected.** `D-02` remains deferred to Section 29. `D-33` is resolved as a
**requirement**, not a product: the mechanism family, vendor, and configuration are chosen
when `D-02` is decided, and must be evaluated against §5.

**`I-03` and `I-33` remain `[PHYS]` and remain unverified.** This document specifies what
would satisfy them; nothing yet does.

Invariants: `I-60`–`I-63`, `I-77`–`I-80`, `I-86`, `I-87`. *(Corrected 2026-08-13, N-13 — the
earlier trailer listed only `I-60`–`I-63` and predated the amendment passes that gave this
document the provisioning, binding-authority, serial-channel and token-integrity requirements.)*
