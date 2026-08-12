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
| **Memory** | Creation, correction, supersession, deletion, and **elevation** to a parent scope |
| **Derivation** | Every derived item with its complete source lineage |
| **Deletion** | The tombstone: identity, scope, classification, time, authorization |
| **Credentials** | Requests, issuance, use, rotation, revocation — by **reference only** |
| **Agent execution** | Instantiation, tokens held, tools called, escalations, outcome |
| **Work Orders** | Issuance, limits, termination, results, approval |
| **External transmission** | What left NOVA, to which service, under which scope |
| **Model interactions** | Profile, provider, scope, cost, outcome — not prompt content by default |
| **Administrative changes** | Policy, classification changes, scope creation, reclassification |

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
