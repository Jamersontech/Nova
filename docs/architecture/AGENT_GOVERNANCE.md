# Agent Governance

**Status:** **Active** — Section 06, accepted by James 2026-08-14 (ADRs `0029`–`0031`).
**Covers:** how delegated authority is derived, bounded, budgeted and ended; which agent
operations are governed at which change class; and what an approval binds.
**Extends:** [`AGENT_ARCHITECTURE.md`](./AGENT_ARCHITECTURE.md) (Section 02, Active),
[`ai/AGENT_PRINCIPLES.md`](../ai/AGENT_PRINCIPLES.md) (Section 01, Active) and
[`SCOPE_AND_IDENTITY_MODEL.md`](./SCOPE_AND_IDENTITY_MODEL.md) (Section 03, Active). **None is
replaced.** Section 02 fixed what an agent *is*; this document fixes what an agent's authority
*is bounded by*.

**No runtime, platform, language, or scheduling technology is selected.** `D-25a` remains
deferred and is **not** resolved here (§9).

---

## 1. What Section 06 Closes

Sections 01–03 established that authority narrows at every step and that **"no mechanism in the
architecture widens authority"** ([`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md) §3).
That claim held for every path Section 06 examined **except** the derivation of delegated
authority itself, where four things were unstated:

1. **`I-07`'s intersection had no verifying point.** Grants are independently enforced by the PDP
   at step 5 (`I-10` — only James grants), and tokens are integrity-bound to the Context service
   (`I-87`). But the **agent definition** — one of `I-07`'s four inputs — is consulted by none of
   `AUTHORIZATION_MODEL.md` §3's ten steps, and `AGENT_ARCHITECTURE.md` §2 was worded as though
   the **runtime** issued tokens, which `I-87` forbids.
2. **Delegation had no bound.** No depth limit, no cycle rule, no fan-out limit — and
   `SCOPE_AND_IDENTITY_MODEL.md` §5 conditioned re-delegation on a permission the delegation
   record had no field for.
3. **`I-105`'s cost ceiling was per execution**, so a delegation tree of *N* executions received
   *N* ceilings. **This gap was introduced by Section 05** and is closed here.
4. **Agent creation had no change class**, and an approval bound nothing beyond "one action, one
   context, one time".

**Everything else Section 06 examined was already closed** by accepted architecture: agent
identity (`I-66`, `AUTHENTICATION_MODEL.md` §5), cross-scope isolation (`I-86`, `I-95`),
credentials (`I-22`), approval authority (`I-09`), the tool closed list
(`SECURITY_BOUNDARIES.md` §2), and the whole model path (Section 05). Section 06 reuses all of it
and adds no parallel mechanism.

---

## 2. Token Issuance Is Verified — `I-106`

**`AG-1` — The Context service is the sole issuer of Context Tokens**, including narrowed tokens
for dispatched agents. This is not new: `I-87` already requires every consumer to reject a token
"fabricated by anything other than the Context service", and
[`SYSTEM_LAYERS.md`](./SYSTEM_LAYERS.md) §5 point 1 already reads *"Context → Orchestration: token
issued, scope fixed."* A runtime-minted token would fail integrity detection at every enforcement
point, so a minting runtime was never implementable. **`AGENT_ARCHITECTURE.md` §2's wording said
otherwise and is corrected.**

**`AG-2` — The Agent Runtime requests narrowing; it never mints.** The request names the target
agent definition, the desired scope, rights, tools and risk ceiling, and carries the requesting
execution's own integrity-verified token.

**`AG-3` — Issuance verifies the request against every `I-07` input before issuing.** Context
refuses any request whose resulting token would exceed **any** of:

| Input | Authoritative source |
| --- | --- |
| The requesting execution's scope, rights and risk ceiling | Its own token, integrity-verified (`I-87`, `P-12`) |
| The named agent definition's Allowed Context, Allowed Tools and Permissions | The agent registry |
| James-created grants | The PDP (`I-10`; `AUTHORIZATION_MODEL.md` §3 step 5) |
| Applicable delegation constraints | §3 below |

**This is where `I-07` becomes enforced rather than asserted.** It is the only point at which all
four inputs exist together.

**`AG-4` — Refusal is total and fail-closed.** On mismatch, on a token failing integrity, on an
unreadable or incomplete agent definition, or on any uncertainty: **no token is issued**, the
request is denied, and the refusal is recorded. **There is no partial issuance** — a token
narrowed "as far as could be verified" is a token whose bounds nobody established.

**`AG-5` — Context still decides no authorization.** *"Context answers **where** an operation
applies. Policy answers **whether** it is allowed"*
([`CONTEXT_ARCHITECTURE.md`](./CONTEXT_ARCHITECTURE.md) §1) is unchanged. `AG-3` is a **bound
check on issuance**, not an authorization decision: it can only refuse to issue, never permit
something the PDP denied. **The PDP is not turned into an agent-definition engine** and `P-11`'s
separation stands.

### What this does not do

**It does not mitigate compromise of the Context service.** A compromised Context service issues
**genuine** tokens through the legitimate path, and `AG-3` is a check that same service performs
on itself. `T-23a` is **unchanged and not improved** — stated here so `AG-1`–`AG-4` are not
mistaken for a stronger property than they are.

**It adds one trust dependency:** Context must read the agent registry. Recorded in
[`KNOWN_RISKS.md`](./KNOWN_RISKS.md).

---

## 3. Delegation Is Bounded — `I-107`

### 3.1 The delegation record

`SCOPE_AND_IDENTITY_MODEL.md` §5 lists delegator, delegate, scope, rights, expiry and purpose,
then states *"re-delegation is allowed only where the original delegation permits it"* — a rule
testing a field that does not exist. **`AG-6` adds it:**

```text
Delegation
├── delegator          the granting execution identity
├── delegate           the receiving agent
├── scope              ⊆ delegator's
├── rights             ⊆ delegator's
├── tools              ⊆ delegator's
├── risk ceiling       ≤ delegator's
├── expiry             strictly earlier than the delegator's
├── may_redelegate     explicit, DEFAULT FALSE          ← added by Section 06
├── ancestry           the chain of delegators above it  ← added by Section 06
└── purpose
```

### 3.2 The rules

**`AG-7` — Strict narrowing.** Every delegation is **strictly** narrower than its delegator in at
least one authority dimension — scope, rights, tools, or risk ceiling — **and** its expiry is
strictly earlier. A delegation identical in every dimension is refused at issuance (`AG-3`).

**This is what bounds depth, and it is why no numeric depth limit exists.** Each step descends the
authority lattice, whose height is finite, and each step shortens the lifetime. An arbitrary
"depth 3" would be a number nobody could justify; strict narrowing terminates for a stated reason.

**`AG-8` — WITHDRAWN as redundant.** *(Corrected 2026-08-15 on James's decision (C3). An
accuracy correction, not a newly discovered vulnerability. Evidence:
[`slice/FINDINGS.md`](../../slice/FINDINGS.md) Finding 4.)*

**As written it could never fire**: it compared the **delegate** — *an agent* — against
`ancestry`, *a chain of execution identities* (`AG-6`), and execution identities are ephemeral
and never reused (`AUTHENTICATION_MODEL.md` §5), so neither reading of the comparison can match.

**And it was not needed.** `AG-7` already terminates cycles: every step is strictly narrower in
at least one authority dimension and expires strictly earlier, so `A → B → A` descends a finite
lattice and ends — measured as `EXECUTE → PREPARE → ANALYZE → READ → refused`, with authority
never rising. `AG-9` stops the cycle beginning at all under the default `may_redelegate=false`;
`AG-11` fails every descendant closed when an ancestor ends; `AG-13` bounds the whole tree to one
budget. **A same-agent re-entry under strictly narrower authority is not an escalation and remains
permitted.**

**`ancestry` is retained in `AG-6`** — it records the chain for audit and is what `AG-11` walks.

**`AG-9` — Re-delegation is explicit.** A delegate may re-delegate only where `may_redelegate` is
true. **Default false**, so a capability an agent may *use* is not thereby one it may *pass on*.
Re-delegation narrows again under `AG-7` and may itself set `may_redelegate` only if its own
delegation permitted it.

**`AG-10` — Fan-out carries no count limit.** Parallel children are bounded by the **shared root
budget** (§4). A child-count limit would be a second arbitrary number governing the same resource
the budget already governs.

### 3.3 Delegated authority cannot outlive its source

**`AG-11` — A child execution never outlives the execution identity that granted it.** When the
granting execution identity ends — by **normal completion, failure, termination, revocation, or
emergency stop alike** — an input to the child's `I-07` intersection no longer exists, so the
child's delegated authority is no longer valid and the child **fails closed at its next
enforcement point**.

**No new mechanism is created.** `AUTHENTICATION_MODEL.md` §5 already makes an execution identity
"valid for one execution, in one context, until it completes or expires";
[`SECURITY_OPERATIONS.md`](./SECURITY_OPERATIONS.md) `V-2` already fails in-flight executions
closed at their next enforcement point. `AG-11` states that `V-2`'s trigger includes **any** end
of the granting identity, not only revocation.

**`AG-12` — There is no suspended agent state.** Section 06 deliberately does **not** introduce
one. A lifecycle state in which an agent is neither running nor ended would need its own authority
semantics, and nothing in NOVA requires it: stopping is termination, and pausing is a workflow
property ([`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §4), not an agent
property.

---

## 4. The Cost Ceiling Belongs to the Root Execution — `I-108`

**`AG-13` — One budget per delegation tree.** The model cost and token ceiling is a property of
the **root execution**, and **every descendant consumes from that same budget**. A child cannot
mint capacity, cannot receive a fresh budget, cannot raise the root ceiling, and cannot transfer
capacity into an independent budget.

**`AG-14` — A parent may carve a smaller child ceiling; it is optional and narrowing.** This is
`AG-7` applied to a consumable. It is **not required**, because requiring it would force an
allocation policy — how much a parent carves — that nothing in the architecture decides, leaving
an engineer to invent a security-relevant number.

**`AG-15` — Exhaustion behaves exactly as `I-105` already says.** Terminate and escalate; never
silent degradation; above `PREPARE` it fails closed. Retries and model fallback consume the same
budget and remain accounted per attempt (`I-104`).

**The question this answers:** *can an agent create execution capacity without consuming capacity
already granted to its parent?* **No.** Under the accepted Section 05 text it could, because
`I-105` was written per execution — this closes the gap Section 05 introduced.

**Not per agent** (instances are ephemeral, so the budget would be meaningless) and **not per
client scope** (too coarse — one runaway execution would consume a client's whole allowance).

**Under concurrency, the budget overruns boundedly and never mints.** Concurrent descendants may
each observe remaining budget and proceed, so actual consumption can exceed the ceiling by at most
the in-flight calls' worth. **This is an overrun, not capacity creation** — every one of those
calls still drew on the root budget, and the next check finds it exhausted and applies `I-105`.
Section 06 deliberately does **not** require a strictly serialized counter: the cost would be a
synchronization point on every model call, and the exposure it removes is one bounded overshoot.
**A duplicate or replayed delegation request creates no capacity either**, for the same reason —
both draw on the same budget, and each must still narrow (`AG-7`) and pass issuance (`AG-3`).

---

## 5. Agent Governance Classification

**`AG-16` — Agent operations are classified under the existing C1/C2/C3 model.** No new class is
created, and no existing class is reinterpreted. What follows makes explicit what
[`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md) §4–§5 already implies but never states
for agents, which is why an implementer could previously have read agent creation as C1.

| Operation | Class | Because |
| --- | --- | --- |
| Register or change an agent **definition** | **C2** | §4's "New components… tool definitions" — the direct analogue |
| …where it sets or changes **Permissions, Allowed Context, Allowed Tools, or risk ceiling** | **C3** | §5 already classes *agent permissions* C3; `TOOL_AND_INTEGRATION_ARCHITECTURE.md` §6 classes tool rights and risk class C3 |
| **Creating an agent** | **C3, always in practice** | Permissions, Allowed Context and Allowed Tools are **mandatory** fields (`AGENT_PRINCIPLES.md` §2), so creation always sets authority-bearing fields |
| Changing the model / capability profile | **C2** | Not an authority. Egress is decided per call by Section 05 (`I-94`, `I-97`, `I-98`) |
| **Activation** | part of the same governed act as registration | Not separately classified — see below |
| **Suspend / revoke** | **C1** | Restriction. The `I-93` principle: operations that remove access are not gated like operations that grant it |
| **Replacement** | **C3** | A replacement is a new definition with authority-bearing fields |
| **Instantiating an execution** | **not governance** | Execution, bounded by §2 |

**Registration and activation are authorization; instantiation is execution; nothing here is mere
configuration.** Registration establishes what an agent may ever hold; activation makes it
dispatchable; both are the same governed act because separating them would create a window in
which a definition is approved but its activation is not.

**`I-73` is unchanged and load-bearing:** no agent modifies policy, and none of the C2/C3
operations above may be performed by an agent — `IDENTITY_AND_AUTHORITY.md` §4 already forbids AI
implementation of C2 and above.

**Replacement does not reach in-flight executions; revocation does.** A replaced definition governs
the **next** issuance (`AG-3`); an execution already running holds a token verified against the
definition in force when it was issued, and continues under it until it completes or expires. That
is `V-1`'s existing semantics — effective at the next decision — and it is bounded, because `I-12`
makes expiry mandatory. **Replacement is therefore not a safety operation.** If a definition must
stop being used *now*, the operation is **revocation**, which is C1 precisely so it is faster to
reach than the change that caused the problem, and which fails in-flight executions closed at their
next enforcement point (`V-2`). Nothing new is decided here; this states which existing tool
answers which need, so an implementer does not reach for the slow one in an incident.

---

## 6. What an Approval Binds — `I-109`

`PERMISSION_ARCHITECTURE.md` §5 states *"an approval authorizes one action, in one context, at one
time."* It did not say what makes it the *same* action at execution time.

**`AG-17` — Nine properties are binding.** An approval remains valid only while all nine are
unchanged between approval and execution:

```text
1. action            4. effective rights   7. argument envelope (I-100)
2. resource          5. risk class         8. delegation ancestry
3. scope             6. tool set           9. cost ceiling
```

**`AG-18` — These are explicitly *not* binding:** model, provider, capability profile, the
**ephemeral agent instance identity**, wording, formatting, ordering, and other implementation
metadata. Instances are ephemeral **by design** (`AGENT_ARCHITECTURE.md` §3) — binding to one
would make every approval stale on principle. A model or provider change is separately governed
per call by Section 05 (`I-94`, `I-97`), so it needs no second gate here.

> ***AG-17/AG-18 AMENDED BY SECTION 11 — ACCEPTED by James 2026-08-15*** *(2026-08-15; authority
> [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), **Accepted**
> 2026-08-15, amendment 12; the accepted text above stands unmodified).* **`AG-18`'s
> exclusion is scoped to model calls, where its rationale lives.** *"Separately governed per call
> by `I-94`/`I-97`"* is true of a **model call** and of nothing else — a tool call has no per-call
> provider decision, so for a **consequence-producing tool action** the exclusion was unsafe: the
> approval **also binds the execution binding** — tool identity and version, integration,
> credential binding — as a **tenth** property (`I-114`, `I-109` as amended). The nine properties
> of `AG-17` are unchanged and unreordered; `AG-19`'s construction extends over the tenth
> unchanged; `AG-20` applies to a binding mismatch exactly as to the other nine. **`AG-18` must
> not be read as saying provider identity is irrelevant to tool authorization.**

**`AG-19` — The binding reuses `I-93`, and introduces no cryptography.** Section 04 already
requires a **deterministic identity derived from an operation and its trace id** for every
mandatory audit record. The approval binding is the same construction over the nine properties
above. Nothing new is invented.

**`AG-20` — A differing binding means the approval does not apply.** Execution does not proceed
under it, and fresh approval is required where the risk class requires approval at all. This is a
denial, not an error to retry.

**The property this establishes:** *an approved action cannot silently become a materially
different action because the agent executing it, its rights, its tools, its arguments, its
delegation chain, or its budget changed after approval.*

---

## 7. The Seven Prohibitions, Stated Honestly

`AGENT_PRINCIPLES.md` §4 asserts its seven prohibitions are *"enforced by design, not by
instruction alone."* Section 06 found that true of five and **false of two**. The claim is
corrected there; the enforcement is recorded here.

| # | Prohibition | Enforced by | Point |
| --- | --- | --- | --- |
| 1 | Grant itself permissions | `I-08`, `I-10` — no grant path exists | PDP step 5 |
| 2 | Silently modify another's permissions | `I-73`, C3 governance (§5) | PDP + governance |
| 3 | Silently access another client | `I-16`, `I-86`, ADR 0016 | Data-access PEP + storage |
| 4 | Escalate via a more-privileged tool **or agent** | Tool half: closed list at the tool PEP. **Agent half: `AG-3`, `AG-7`–`AG-9`** | Tool PEP · **issuance** |
| 5 | Use a credential outside its scope | `I-24`, broker step 2 | Credential Broker |
| 6 | **Present inference as verified fact** | **Nothing mechanical.** `I-39` and `PROVENANCE_AND_TRUST.md` §5 state the rule; **no enforcement point inspects output content** | **none** |
| 7 | Irreversible action without approval | `I-09`, risk class, `I-101`, **`AG-17`** | Orchestration + tool PEP |

**Prohibition 4's agent half is closed by this document.** **Prohibition 6 is not, and Section 06
does not claim to close it** — enforcing it would require a component that inspects agent output
for epistemic honesty, which NOVA does not have and which no invariant requires. It is a **review
and evaluation criterion** (Section 41), and `AGENT_PRINCIPLES.md` §4's blanket sentence is
amended to say so rather than continuing to overclaim.

---

## 8. Audit

**No new audit architecture.** Every Section 06 event resolves to one of ADR 0023's three existing
authorities.

| Event | Authority | Partition |
| --- | --- | --- |
| Agent instantiation, tools called, escalations, outcome | **`W-1`** | The execution's bound scope |
| Token issuance **refusal** (`AG-4`), denied delegation (`AG-7`–`AG-9`), budget exhaustion denial | **`W-2`** | The scope the decision concerned |
| Agent definition **registration, change, activation, suspension, revocation, replacement** | **`W-3`** | Control-plane partition |
| Delegation issued, delegation expiry, re-delegation refused | **`W-3`** | Control-plane partition |
| Failed registration / failed activation | **`W-3`** | Control-plane partition |
| Approval, and approval-binding mismatch (`AG-20`) | **`W-3`** | Control-plane partition — `S4-P9` D3 already places approvals there |

**A scopeless decision belongs to `W-3`, not `W-2`** — ADR 0023's `HIGH-1` rule, applied
unchanged. Agent-definition operations concern no client scope. **No fourth authority is created
and none is needed.**

---

## 9. What Is Deferred

| Deferred | Why | Owner |
| --- | --- | --- |
| **Agent runtime implementation** (`D-25a`) | Execution mechanics depend on the platform | 06, blocked on `D-01`, `D-04` |
| **Concrete agent definitions** | `AGENT_PRINCIPLES.md` §1 forbids creating agents to fill a taxonomy | 06 / 21, when concrete responsibilities exist |
| **Budget values** (`D-40`) | Depends on lived usage and `Q-06` | 34 |
| **Agent evaluation mechanics** | Success criteria exist; measuring them is a separate domain | 41 |

Invariants: `I-106`–`I-109`. Threats: `T-33`, `T-34`; `T-24` amended.
