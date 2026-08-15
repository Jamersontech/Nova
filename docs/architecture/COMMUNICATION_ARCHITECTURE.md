# Communication Architecture

**Status:** ***PROPOSED*** — Section 13, 2026-08-15. Authority
[ADR 0039](../decisions/0039-communication-is-classified-egress.md), **Proposed**. If that ADR is
rejected this document is removed; no accepted document depends on it.
**Covers:** every path by which NOVA sends something to a person outside itself — email, SMS,
messaging, and anything later added — and what comes back.

> **This document adds no new rule.** Every statement below cites an accepted rule and the
> enforcement point that applies it. It exists because the communication surface spans five
> documents and **none of them owned "communication"**, so no reader could answer *"is this message
> authorized?"* from one place — which is how a classification rule sat with no named enforcement
> point (ADR 0039).

---

## 1. What a Communication Is

A communication is **a tool action** ([`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md)),
not a special class of operation. It creates no new object and gets no separate permission model.
What makes it worth stating separately is that **it is irreversible and it leaves the trust
boundary toward a human** — `T-38` already establishes that NOVA cannot recall a submitted side
effect.

Seven things are decided about any communication, and each is decided somewhere that already
exists:

| Element | Bound by | Enforced at |
| --- | --- | --- |
| **Recipient identity** | `I-100` / `MT-5` — *Target: recipient, address* is consequence-determining | Tool call PEP, value vs envelope |
| **Recipient-list size** | `I-100` / `MT-5` — *Magnitude: recipient-list size* | Tool call PEP |
| **Attachments** | `I-100` / `MT-5` — a selector of what the action affects | Tool call PEP |
| **Content classification** | `I-27` + `I-99`, then `DATA_CLASSIFICATION.md` §2 | **PDP step 7**, at the Tool call PEP (§2) |
| **Sending account** | `I-114` — the execution binding, never an argument (§3) | Tool PEP + Credential Broker step 2a |
| **Rate / frequency** | PDP **step 8** — *time · rate · sensitivity* | PDP, per action |
| **Risk class** | `I-101` — derived, one-way with respect to models | PDP step 6 |

**Message wording is expressive and is deliberately not envelope-bound** (`MT-5`). The envelope
polices *what the action affects*, never prose. §2 is why that is safe.

---

## 2. Content Is Classified Egress

**The classification that governs a message is the classification of the content leaving — not of
the action, the tool, or the recipient record.**

[`DATA_CLASSIFICATION.md`](./DATA_CLASSIFICATION.md) §2's **"Transmitted externally"** row has said
so since Section 03:

```text
PUBLIC              ✅ freely
INTERNAL            grant
CONFIDENTIAL        grant
CLIENT-CONFIDENTIAL to that client only
SENSITIVE-PERSONAL  ❌ never
SECURITY-CRITICAL   ❌ never
```

**The composition that makes it enforceable** — four accepted rules, none new:

```text
I-99   a model-composed body is a DERIVATION of its inputs, stored or not
I-27   a derived item inherits the STRICTEST classification among its sources
       → the body carries the strictest classification of everything retrieved into it
§2     "Transmitted externally" governs what that classification may do
step 7 "Does classification permit this action here?"  → DENY if not
       asked by the PDP, at the Tool call PEP, where the send is enforced
```

**Why this needed stating.** `MT-5` classifies wording and summary text as **expressive — not
bound**, which is correct for the argument envelope and reads, to an implementer building a send
path, as *"the body needs no gate."* It does need one — a different gate, asking a different
question. *"Is this argument authorized?"* and *"may this classification leave?"* are both live, and
resolving the first does not answer the second.

**The failure this closes.** An execution in a marked LIFE area retrieves SENSITIVE-PERSONAL items;
a model composes a summary into a body; the recipient is inside the envelope; the binding is
authorized; `I-100` passes on `to`. **§2 says SENSITIVE-PERSONAL is never transmitted externally**
— and until this was composed, nothing was named that would stop the send. The same shape reaches
CLIENT-CONFIDENTIAL content sent to someone stored *in* the client's scope who is not that client,
and SECURITY-CRITICAL content — an audit excerpt, a grant listing — pasted into a status mail.

**The union is blunt on purpose.** One CLIENT-CONFIDENTIAL item retrieved into an otherwise-public
newsletter makes the whole body CLIENT-CONFIDENTIAL and the send is denied. That is the correct
failure direction. **The remedy is `I-30`'s reviewed downward reclassification, never a per-send
override** — and never an agent's decision (`I-30`, `I-110`).

---

## 3. The Sender Is the Binding, Not an Argument

*"Which account did this come from?"* is answered by the **execution binding** — tool identity and
version, integration, credential binding — resolved before the authorization decision and checked
at the Tool PEP and again at the Credential Broker (`I-114`,
[`SECRETS_ARCHITECTURE.md`](./SECRETS_ARCHITECTURE.md) §3 step 2a).

**Communication is the first major consumer of `I-114`, and it needs nothing added.** One
`send_email` tool bound in three scopes reaches three providers, three accounts, three identities
(`TOOL_AND_INTEGRATION_ARCHITECTURE.md` §1) — so *"send as Client A"* versus *"send as James"* is a
**binding** question, not an argument question, and an argument claiming a different sender is not
a route to one. **Failover never crosses to another binding** and there is **no provider
equivalence** (`I-114`(d)); every retry, resumption and failover re-resolves and re-checks.

---

## 4. Recipient Expansion — Bounded, Not Closed

`I-100` checks the recipient **identifier** against the envelope. It does not, and cannot, check
the **audience**.

A recipient identifier may denote a set: a distribution list, an alias, a shared inbox, a group, or
an address whose provider-side rules add CC, auto-forward, or expand a merge tag. **Every one of
those passes the envelope check** — the identifier is a permitted contact — while the audience is
larger, and sometimes crosses outside the scope entirely.

**This is `T-39`'s semantic-divergence residual in its sharpest concrete form**, and it is
**recorded, not closed**: `I-114` guarantees the consequence is produced by the binding James
authorized, **not that James knew everything that binding would do**. Detecting expansion requires
knowing what an external address resolves to, which is provider knowledge NOVA does not hold, and
the only component that could judge it is a model — barred by `I-101`, `I-102`, `I-110`.

**What is genuinely bounded:** the identifier must be in the envelope (`I-100`); recipient-list
*size* is consequence-determining and can carry a ceiling (`MT-5`, *Magnitude*); an envelope that
cannot be fixed is a denial rather than an autonomous send (`MT-9`); and **content classification
still gates the payload** (§2) — so an expansion that reaches outside a client cannot legitimately
carry that client's confidential material, because §2 already refused it.

---

## 5. What Comes Back Carries Nothing

**Inbound is governed entirely by ADR 0037, and communication is its first real consumer.**

| Arriving | Status | Rule |
| --- | --- | --- |
| A reply, an inbound email or SMS | Untrusted data. **No identity, no token, no grant** | `S11-D3`; `AUTHENTICATION_MODEL.md` §2 — an external system *never authenticates into NOVA* |
| A delivery receipt, bounce, read receipt | **`integration.supplied` testimony**, never `system.verified` | `S11-D2`, `I-110` |
| A provider "success" | Success **claimed**, not verified | `S11-D2` |
| Timeout, lost connection | **Unknown** — never "failed" | [`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md) §2 |

**A reply never continues an authorization.** *"Context is the Context Token: scope path + rights +
expiry — **never a conversation**"* ([`AUTHORIZATION_MODEL.md`](./AUTHORIZATION_MODEL.md) §2), and
*"a conversation does not accumulate authority; each request resolves its own context"*
([`CONTEXT_ARCHITECTURE.md`](./CONTEXT_ARCHITECTURE.md) §1). **Thread continuation therefore grants
nothing** — answering a reply is a new action, authorized on its own terms. A reply's content may
**inform** and may never **escalate** (`I-40`), carrying its taint under `I-99` and persisting under
`I-111`; a recipient, address or instruction appearing *inside* a reply is untrusted content, not a
destination NOVA may adopt.

**A bounce is not proof of non-delivery, and a receipt is not proof of delivery.** Both are claims
by the party that performed the action. Where the effect is independently observable, read it back
(`TOOL_AND_INTEGRATION_ARCHITECTURE.md` §3.1); where it is not, the outcome stays **unknown** and
escalates — **never auto-retried into a duplicate message**, which requires provider-enforced
deduplication (`RELIABILITY_ARCHITECTURE.md` §4).

---

## 6. Volume, Repetition and Timing

**Rate is already a decision input.** PDP **step 8** evaluates *time · rate · sensitivity*, and
standing approvals are bounded by *"scope, risk ceiling, expiry, and rate limit"*
([`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) §5). So repetition is governable at
the point of decision rather than needing a communication-specific counter.

**Bulk is magnitude, and magnitude is consequence-determining** (`MT-5`) — one approved message
becoming a thousand is an envelope violation at the Tool PEP, not a judgment call.

**A scheduled or recurring send is an automation, and an automation is intent, not authority**
([`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §5): every firing is authorized
freshly at fire time, nothing inherits, and revocation and stop reach it at the enforcement points
it still passes (`V-2`, `X-1`, `X-3`, `X-7`). **A campaign is not a standing permission to
message.**

**Honest limit:** individually authorized, individually reasonable messages can still aggregate
into behaviour a recipient experiences as spam. Rate limits bound frequency; they do not judge
appropriateness, and nothing here claims otherwise (`T-41`).

---

## 7. Consent and Opt-Out Are Deferred, With the Reason

*Unsubscribe*, *opt-out* and *consent* appear **nowhere in the repository**. Section 13 records the
hook and does **not** invent the policy.

**No mechanism is missing.** A suppression set narrows the recipient envelope that `MT-8` already
fixes, and is checked at the Tool PEP exactly as any other envelope membership — no new object, no
new invariant, no new enforcement point.

**What is missing is policy**, and it is not Section 13's: what constitutes consent, how it is
recorded and evidenced, how long it persists, whether it is per channel or per person, and which
jurisdictions' rules attach. Consent is also a property of **a person**, while NOVA's authorization
model is scope-shaped throughout — reconciling those is a data-governance decision.

**Owner: Section 37 (Privacy & Data Governance)**, on the same reasoning that sent Section 09's
aggregate-sensitivity finding there. **Until it exists, NOVA has no suppression check** — recorded
in [`KNOWN_RISKS.md`](./KNOWN_RISKS.md) §3.13, not mitigated.

---

## 8. What This Document Does Not Change

`I-01`–`I-114` are unmodified. No new invariant, enforcement point, PEP, security object, audit
category, authority or change class is created. The six PEPs remain six; the ten-step sequence
remains ten steps; a communication is an ordinary tool action throughout.
