# Event and Observability Architecture

**Status:** **Active** — Section 02, approved by James 2026-08-12.
**Covers:** how NOVA learns that something happened, and how it can later explain what it
did and why.

---

# Part I — Events

## 1. Event Model

```text
Event
├── type              task.completed · deployment.failed · client.replied · approval.required
├── source            which system, agent, integration, or schedule produced it
├── scope             which scope node it belongs to
├── subject           the resource it concerns
├── payload           typed data
├── occurred / received
├── trace id
└── sensitivity       affects who and what may consume it
```

**Every event belongs to exactly one scope.** An event about Client A is in Client A's
partition, and consumers see only events their token covers. Event distribution is a
common accidental leak path — a notification stream that ignores scope will happily tell
one context about another's work.

## 2. Sources and Consumers

**Sources:** NOVA itself (task completed, agent finished, approval required, workflow
paused), integrations (client replied, payment received, deployment succeeded, site down,
API failed), schedules (deadline approaching, credential expiring), and James.

**Consumers:** workflows waiting on a condition, monitoring, the notification system, and
memory. Consumers subscribe by type and scope, and receive only what their permissions
allow.

**Delivery discipline.** Events may arrive late, out of order, or more than once.
Consumers must be idempotent; a workflow resumed twice by a duplicate event must not
perform its step twice.

**An integration-sourced event's `source` is an unauthenticated assertion.** ***PROPOSED — added by
Section 11, not yet accepted*** *(2026-08-15; authority
[ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), Proposed; removed
and the accepted text restored verbatim if rejected).* The source list above includes
**integrations**, and the consumer list includes **workflows waiting on a condition** — so an
external party can place a signal NOVA is waiting on. **An external system never authenticates into
NOVA** ([`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §2, unchanged), so such an event
carries no execution identity, no Context Token and no grant, and by `I-14` authorizes nothing. It
may satisfy a wait condition; it may never widen what the waiting work may do, because resumption
re-checks authorization rather than inheriting it
([`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md) §3). **Scope is unchanged and still
binding** — §1's rule that every event belongs to exactly one scope applies to integration events
exactly as to internal ones, so an inbound signal cannot introduce a cross-scope path. Full model:
[`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §4.1; residual
`T-38`.

## 3. Retention

Events are retained by class: operational events for a working window, security and audit
events long-term, high-volume telemetry aggregated after a short window. Retention is a
scope-level policy so that a client's data can be exported or removed as a unit
(Constitution §13).

---

# Part II — Observability

## 4. The Questions That Must Be Answerable

NOVA must be able to answer, after the fact:

| Question | Answered by |
| --- | --- |
| What happened? | Event and audit records |
| Why did it happen? | Trace: request → intent → plan → dispatch |
| Which agent did it? | Execution record with agent identity |
| Which tool did it use? | Tool call record |
| Which credentials were involved? | Credential *reference* — never the secret |
| Which model was used? | Model call record |
| What failed? | Error record with typed failure |
| **What did NOVA believe at the time?** | Retrieval record: what was in context, its kind, source, age |
| What was approved, by whom, when? | Approval record |
| What did it cost? | Cost record per execution |

**The belief question is the hard one, and the most valuable.** When NOVA does something
wrong, the cause is usually not a bug in execution but bad or stale input. Recording what
was retrieved, what kind it was, and how old it was — per
[`MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`](./MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md) §7 — is
what turns "NOVA did something strange" into a diagnosable event.

## 5. Three Record Types

| Type | Purpose | Mutable | Retention |
| --- | --- | --- | --- |
| **Logs** | Operational detail for debugging | No | Short |
| **Traces** | Causal chain across components, joined by trace id | No | Medium |
| **Audit records** | Who did what, under what authorization | **Append-only, never deleted** | Long |

**Audit records are immutable, including to James.** A record James can quietly change
cannot serve as evidence of what NOVA did. Corrections are appended, never overwritten —
the same principle as superseded ADRs.

**One trace id spans everything** from James's words to the outbound API call, so a single
question — "what happened when I asked to deploy?" — yields one coherent chain.

## 5.1 What Must Be Auditable

*Added in Section 03.* The minimum set. Each produces an append-only record carrying
references and identifiers — never content, never secrets.

| Category | Recorded |
| --- | --- |
| **Access** | Reads of CLIENT-CONFIDENTIAL and above; every cross-scope and cross-domain access, per scope touched |
| **Denial** | Every denied decision, with the failing step |
| **Grants** | Creation, modification, expiry, revocation |
| **Approvals** | What was approved, by whom, when, for which single action |
| **Memory** | Creation, correction, supersession, deletion, **elevation** to a parent scope, and **trust promotion — granted and refused alike** ³ |
| **Derivation** | Every derived item with its complete source lineage |
| **Deletion** | The tombstone: identity, scope, classification, time, authorization |
| **Credentials** | Requests, issuance, use, rotation, revocation — by **reference only** |
| **Agent execution** | Instantiation, tokens held, tools called, escalations, outcome |
| **Work Orders** | Issuance, limits, termination, results, approval |
| **External transmission** | What left NOVA, to which service, under which scope |
| **Model interactions** | Profile, provider, scope, cost, outcome — not prompt content by default |
| **Administrative changes** | Policy, classification changes, scope creation, reclassification |
| **Agent definition lifecycle** ² | Registration, change, activation, suspension, revocation, replacement — and every failure of these |
| **Delegation** ² | Delegation issued, refused, expired; re-delegation refused; token-issuance refusal (`I-106`); budget-exhaustion denial |

> ² ***Added by Section 06 — ACCEPTED by James 2026-08-14*** *(2026-08-14; authority
> [ADR 0029](../decisions/0029-delegated-authority.md),
> [ADR 0030](../decisions/0030-agent-governance-and-approval-binding.md) and
> [ADR 0031](../decisions/0031-section-06-amendments-to-accepted-architecture.md), all **Accepted** 2026-08-14).* **No new audit authority is created** — ADR 0023's
> three cover every event here. Delegation appeared in `I-92`'s control-plane list but not in this
> canonical category list, and agent-definition lifecycle appeared in neither.
>
> ³ ***PROPOSED — added by Section 07, not yet accepted*** *(2026-08-14; authority
> [ADR 0032](../decisions/0032-trust-promotion-authority.md) and
> [ADR 0033](../decisions/0033-section-07-amendments-to-accepted-architecture.md), both Proposed;
> removed if either is rejected).* **No new audit authority is created** — a trust promotion
> concerns a client scope, so the decision is **`W-2`** and the resulting write **`W-1`**, in that
> scope's partition, exactly as ADR 0023 already provides. **Refusals are recorded too**: a denied
> promotion is the more interesting signal, and `I-110` fails closed, so refusal is the expected
> outcome of an unsupported request rather than an error.

> **Authority:** agent-definition lifecycle and delegation issuance/expiry are **`W-3`**
> (control-plane — they concern no client scope, ADR 0023's `HIGH-1` rule applied unchanged);
> issuance refusals, delegation refusals and budget denials are **`W-2`** (the decision is the
> authority for the record of itself); agent **execution** remains **`W-1`** as above. Approval and
> approval-binding mismatch (`I-109`) are `W-3`, where `S4-P9` D3 already places approvals.

**Writer authority for each category.** ***PROPOSED — added by Section 04, not yet accepted***
*(2026-08-13, `S4-P9`; authorized by
[ADR 0023](../decisions/0023-audit-record-writer-authority.md), which is Proposed. Removed if that
ADR is rejected.)* Every category above resolves to exactly one of three authorities:

| Category | Authority | Partition |
| --- | --- | --- |
| Access · Memory · Derivation · Deletion · Agent execution · Work Orders · External transmission · Model interactions | **`W-1`** — the execution's own authorization (`I-88`) | The execution's bound scope |
| **Denial** | **`W-2`** — the decision itself (`I-91`) | The scope the decision concerned; a cross-scope denial records in the **actor's** scope, never naming the actor in the target's |
| **Grants · Approvals · Administrative changes** · the lifecycle half of **Credentials** (rotation, revocation) | **`W-3`** — the control-plane operation's own authorization (`I-92`) | **Control-plane audit partition** — outside the client scope tree |
| The in-execution half of **Credentials** (request, issuance, use) | **`W-1`** | The execution's bound scope |

**Approvals are control-plane events**, not execution events: an approval is an authorization act
performed *before* the execution it permits. The later execution record remains execution-scoped in
the client partition, and the two are linkable by reference **without granting the control plane any
access to client data** (`I-48`).

**Reclassification downward is audited with particular care** — it is the most dangerous
routine operation in the model ([`DATA_CLASSIFICATION.md`](./DATA_CLASSIFICATION.md) §3).

### The audit trail must not become a leak channel

An audit system that records *what* was accessed rather than *that* it was accessed becomes
a cross-client corpus with weaker access controls than the data it describes — a boundary
violation wearing a different name.

Therefore: audit records are classified SECURITY-CRITICAL, are **scope-partitioned like any
other data**, contain references rather than content, and are readable only by James.
Aggregating audit across scopes is itself a cross-scope operation subject to
[`CROSS_SCOPE_DATA_RULES.md`](./CROSS_SCOPE_DATA_RULES.md).

---

## 6. What Is Never Recorded

Credentials, secrets, and tokens (references only); sensitive LIFE content outside its
Area; and full external payloads by default. Observability must not become the place where
isolation is lost — a log aggregator holding every client's data alongside every other's
is a boundary violation wearing a different name.

## 7. Reaching James

Observability serves two audiences. Engineers need traces and logs. **James needs a plain
account of what NOVA did, what it is waiting on, and what needs him** — surfaced through
Activity and Approvals ([`USER_INTERFACE_ARCHITECTURE.md`](./USER_INTERFACE_ARCHITECTURE.md)),
not through dashboards of system internals. Complexity belongs underneath
(Constitution Golden Rule 14).
