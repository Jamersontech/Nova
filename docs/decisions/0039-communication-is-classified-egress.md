# 0039 — Communication Is Classified Egress

**Status:** **Proposed**
**Proposed:** 2026-08-15 — Section 13
**Section:** 13
**Resolves:** `S13-D1` (the only Section 13 decision)

> **Held Proposed at the 2026-08-15 ADR Decision Gate — not doubted.** ADRs `0032`–`0037`
> were accepted there on implementation evidence from the three vertical slices. This one
> was **not**, for one reason only: **it has no implementation evidence yet.** Its section
> produced documentation, and no code exercises it. **No contradiction, ambiguity or defect
> was found in it** — the review found none, and the repository agrees with it throughout.
> It stays Proposed because accepting it would rest on review alone, which is precisely what
> the vertical-slice programme exists to avoid.

## Decision

**An outbound communication is a classified egress event, and the classification that governs it is
the classification of the content leaving — not of the action, the tool, or the recipient record.**

The rule already exists: [`DATA_CLASSIFICATION.md`](../architecture/DATA_CLASSIFICATION.md) §2's
**"Transmitted externally"** row — PUBLIC freely · INTERNAL and CONFIDENTIAL by grant ·
CLIENT-CONFIDENTIAL **to that client only** · SENSITIVE-PERSONAL **never** · SECURITY-CRITICAL
**never**. **What was missing is that nobody had named where it is enforced**, and the composition
that makes it enforceable spans four accepted rules that no document had put together:

```text
I-99   a model-composed message body is a DERIVATION of its inputs,
       whether or not it is stored
I-27   a derived item inherits the STRICTEST classification among its sources
       → the body's classification is the strictest of everything retrieved into it
DATA_CLASSIFICATION §2  "Transmitted externally" then governs that classification
PDP step 7   "Does classification permit this action here?"  → DENY if not
             invoked at the Tool call PEP, which is where the send happens
```

**No new invariant, no new enforcement point, no new security object, and no new PEP.** The Tool
call PEP is one of the six that already exist; PDP step 7 is one of the ten steps that already
exist. Section 13 states the composition so an implementer cannot build a send path that checks the
recipient and never the payload.

**Four corollaries, each an application of an existing rule rather than a new one:**

1. **Recipient identity and recipient-list size are consequence-determining** and bound to the
   envelope at the Tool PEP — `MT-5` already lists *Target: recipient, address* and *Magnitude:
   recipient-list size*, and `I-100`'s worked example is literally
   `recipients ⊆ client-a's contacts, ≤ 1 message`.
2. **The sending account is bound by the execution binding**, not by an argument — `I-114`.
   Communication is the first major consumer of that invariant, and no new mechanism is added for
   it.
3. **Inbound replies, delivery receipts, bounces and read receipts carry no authority and are not
   facts** — ADR 0037 `S11-D3` (a provider-initiated signal has no identity, token or grant) and
   `S11-D2` (a provider's statement about its own side effect is `integration.supplied` testimony,
   never `system.verified`).
4. **A conversation is not a context.** [`AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md)
   §2 says Context *"is the Context Token: scope path + rights + expiry"* and **"never a
   conversation"**; [`CONTEXT_ARCHITECTURE.md`](../architecture/CONTEXT_ARCHITECTURE.md) says a
   *"conversation does not accumulate authority; each request resolves its own context."* Thread
   continuation therefore grants nothing.

## Context

Section 13 reconstructed the communication surface and found **most of it already governed** —
recipients, recipient cardinality, attachments-as-arguments, the sending binding, inbound signals,
delivery claims, retries, duplicate sends, rate, threads, and stop/revocation each trace to an
existing rule with a named enforcement point. The vocabulary census found the domain well
represented: *recipient* appears in `MT-5`'s consequence-determining table and `I-100`'s worked
example; *channel*, *thread*, *inbound*, *forward*, *broadcast* and *template* all appear.

**Four terms returned zero occurrences repository-wide:** *sender*, *reply*, *unsubscribe /
opt-out*, and *bounce / read receipt*. Three of the four turned out to be governed under other
names — the sender by the execution binding (`I-114`), replies and receipts by ADR 0037. **The
fourth, consent state, is genuinely absent and is deferred (below).**

## Problem

**Communication is the second egress path out of NOVA's trust boundary, and only the first one was
given an enforcement story.** Section 05 found model egress absent from four
enforcement-enumerating documents and closed it with `I-94`/`I-96` at a new Model Gateway PEP.
Communication egress differs in two ways that make it *more* consequential and made the gap easier
to miss:

- **It is irreversible in a way model egress is not.** A message delivered to a person cannot be
  recalled — `T-38` already establishes that NOVA cannot recall a submitted side effect. A model
  provider request is at least bounded by contract; a human recipient is not.
- **The dangerous object is the payload, and the payload is the one argument nothing checks.**
  `MT-5` classifies *"wording, tone, formatting, ordering, summary text"* as **expressive — not
  bound**, and that classification is **correct**: the envelope should not police prose. But an
  email body is not only prose; it is a **carrier of retrieved items**. An implementer reading
  `I-100` sees recipients checked and body unchecked, and concludes the body needs no gate.

**The concrete failure the composition closes:** a `PREPARE`-ceiling-clear execution in a LIFE area
retrieves SENSITIVE-PERSONAL items, a model composes a summary of them into a message body, the
recipient is inside the envelope, the binding is authorized, `I-100` passes on `to`, and the message
sends. **`DATA_CLASSIFICATION.md` §2 says SENSITIVE-PERSONAL is never transmitted externally, and
nothing had been named that would stop it.** The same shape reaches CLIENT-CONFIDENTIAL content
sent to a recipient who is stored in the client's scope but is not that client (a vendor contact on
a client project), and SECURITY-CRITICAL content — an audit excerpt, a grant listing — pasted into
a status mail.

## Options Considered

1. **Status quo.** The rule exists in the classification table; assume implementers apply it.
   Rejected: `MT-5` actively points the other way for the body argument, so the likely reading is
   the wrong one.
2. **Make message content consequence-determining.** Would put prose inside the argument envelope,
   destroying the expressive/consequential distinction `MT-5` exists to draw and making every
   envelope unfixable (`MT-9` → everything requires explicit approval).
3. **A new communication-egress invariant and PEP**, mirroring `I-94`/`I-96`. Rejected: the Model
   Gateway needed a **new** PEP because model egress had none. **Communication already flows
   through the Tool call PEP**, one of the six, and PDP step 7 already asks the classification
   question. A new invariant would restate `I-27` + `I-99` + step 7 for one action family.
4. **State the composition** and name where it is enforced.

## Decision Made

Option 4.

## Reason

**Every link already exists and is accepted.** `I-99` establishes that model output is a derivation
*whether or not it is stored* — which is what makes a transient, never-persisted email body a
derived item at all. `I-27` gives a derived item the strictest classification among its sources.
`DATA_CLASSIFICATION.md` §2 governs what that classification may do on transmission. PDP step 7
asks exactly that question, at the Tool call PEP, which is where a send is enforced. **Minting an
invariant here would add a testable statement that restates four accepted ones**, which Sections
09, 10 and 12 each declined to do in the same situation.

**Option 3 would also mislead.** A separate communication-egress PEP would imply communication
escapes the tool path — it does not, and `I-114` depends on it not doing so.

**The one thing genuinely worth stating beyond the composition is the direction of the default.**
`MT-5` says content is expressive; §2 of the classification table says content classification gates
transmission. Both are true of different questions — *"is this argument authorized?"* versus *"may
this classification leave?"* — and the composition is what keeps an implementer from resolving the
apparent tension by dropping the second.

## Tradeoffs

**Advantages:** no new invariant, PEP, object, authority or change class; the enforcement point is
one an implementer already builds; the classification union is computed by machinery (`I-27`,
`I-99`, `I-111`) that already exists for other reasons.

**Disadvantages:** **classification-union accuracy is now load-bearing on the send path.** If a
retrieval does not carry its classification into the composed body, the gate passes on wrong
information — the claims-not-facts limit again, in a fourth place. **Step 7 becomes a
higher-traffic check**, and the pressure will be to compute the union loosely or cache it.
**And the strictest-source rule is blunt**: one CLIENT-CONFIDENTIAL item retrieved into an
otherwise-public newsletter makes the whole body CLIENT-CONFIDENTIAL and blocks the send. That is
the correct failure direction and it will feel wrong often enough to invite a "just this once"
override, which would be downward reclassification — already `I-30`-governed and never automatic.

## Consequences

- A new document, [`COMMUNICATION_ARCHITECTURE.md`](../architecture/COMMUNICATION_ARCHITECTURE.md),
  states the communication security surface in one place. **Justification for a new document, since
  the default is not to create one:** the surface spans five accepted documents — content
  classification (`DATA_CLASSIFICATION.md`), recipient and binding
  (`TOOL_AND_INTEGRATION_ARCHITECTURE.md`, `MODEL_TRUST_AND_AUTHORITY.md`), delivery and retry
  (`RELIABILITY_ARCHITECTURE.md`), receipts and provenance (`PROVENANCE_AND_TRUST.md`), inbound
  (`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`) — and **none of them owns "communication."** A reader
  asking *"is this message authorized?"* had no single place to look, which is precisely how a
  classification rule sat unenforced. The document **adds no rule of its own**; every statement in
  it cites the accepted rule and the enforcement point it comes from.
- `DATA_CLASSIFICATION.md` §2 gains a marked note naming the enforcement point for its own
  "Transmitted externally" row.
- `THREAT_MODEL.md` gains `T-41`; `KNOWN_RISKS.md` gains §3.13.
- **`INVARIANTS.md` is deliberately not amended.** `I-01`–`I-114` are byte-identical.

**Deferred, deliberately and with the reason stated: consent and opt-out state.** *Unsubscribe*,
*opt-out* and *consent* return **zero occurrences** repository-wide. Whether a person has withdrawn
consent to be contacted is a property of **the person**, not of a scope — and NOVA's authorization
model is scope-shaped throughout. A suppression set is **expressible without new machinery** (it
narrows the recipient envelope `MT-8` already fixes, checked at the Tool PEP exactly as any other
envelope membership), so **no mechanism is missing**. What is missing is the *policy*: what
constitutes consent, how it is recorded, how long it persists, and which jurisdictions' rules
attach. **That is Section 37's (Privacy & Data Governance)**, on the same reasoning that sent
Section 09's aggregate-sensitivity finding there. Section 13 records the hook and does not invent
the policy.

## The amendments

**All are Proposed and marked in place. If this ADR is rejected, each is removed and the accepted
text restored verbatim.**

| # | Document | Section / status | Change |
| --- | --- | --- | --- |
| 1 | `COMMUNICATION_ARCHITECTURE.md` | **new** · Section 13 | The communication security surface, stated from accepted rules with their enforcement points |
| 2 | `DATA_CLASSIFICATION.md` §2 | 03 · Active | Names the enforcement point for the "Transmitted externally" row |
| 3 | `THREAT_MODEL.md` | 03 · Active | `T-41`. `T-03`'s, `T-16`'s, `T-38`'s and `T-39`'s residuals **not reduced** |
| 4 | `KNOWN_RISKS.md` §3.13 | 03 · Active | Section 13 residuals, including the Section 37 deferral |

## What Would Change This

A demonstrated need to transmit content whose classification forbids it — for example a client
genuinely entitled to material currently classed above what §2 permits outward. That is a
**classification** question answered by `I-30`'s reviewed downward reclassification, not a
communication feature, and never a per-send override.
