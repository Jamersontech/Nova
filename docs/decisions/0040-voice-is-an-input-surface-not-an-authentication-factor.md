# 0040 — Voice Is an Input Surface, Not an Authentication Factor

**Status:** **Proposed**
**Proposed:** 2026-08-15 — Section 14
**Section:** 14
**Resolves:** `S14-D1` (the only Section 14 decision)

> **Held Proposed at the 2026-08-15 ADR Decision Gate — not doubted.** ADRs `0032`–`0037`
> were accepted there on implementation evidence from the three vertical slices. This one
> was **not**, for one reason only: **it has no implementation evidence yet.** Its section
> produced documentation, and no code exercises it. **No contradiction, ambiguity or defect
> was found in it** — the review found none, and the repository agrees with it throughout.
> It stays Proposed because accepting it would rest on review alone, which is precisely what
> the vertical-slice programme exists to avoid.

## Decision

**Voice carries intent. It never carries authentication, and it never carries authority.**

Three statements, which together resolve a contradiction between two accepted documents:

**1. A surface varies in the authentication strength it can supply, never in what an action
means or requires.** [`USER_INTERFACE_ARCHITECTURE.md`](../architecture/USER_INTERFACE_ARCHITECTURE.md)
§7's *"a surface may vary in depth; it may never vary in authority"* is **correct and preserved** —
it governs the **action side**: what an action means, what it costs, and what it requires are
identical on every surface, and an action requiring approval on desktop cannot proceed unapproved
on voice. [`AUTHENTICATION_MODEL.md`](../architecture/AUTHENTICATION_MODEL.md) §4's voice cap is
**also correct and preserved** — it governs the **session side**: what strength *this* session
supplies. **The two were read as contradicting because nothing said they addressed different
sides.**

**2. Voice may carry an approval interaction; it may not complete one above `PREPARE`.**
`USER_INTERFACE_ARCHITECTURE.md` §6's *"approvable in one action, from any surface"* is a
**reachability** requirement — every surface must be able to present an approval request and
capture James's response, so he is never stranded. It is **not** a statement that every surface can
supply the authentication strength the risk class demands. Above `PREPARE`, the approval is
**recorded only when a session of sufficient strength exists**, which on voice means `A-3` step-up
on another surface. `I-09` is unchanged: only James approves, and a spoken *"yes"* is his
**expressed intent**, not the record of an approval.

**3. A spoken confirmation of scope is disambiguation, not authorization.**
`USER_INTERFACE_ARCHITECTURE.md` §7's *"explicit confirmation of scope for anything above
`PREPARE`"* is `CONTEXT_ARCHITECTURE.md`'s **ask-never-guess** rule applied to the least precise
surface. Resolving *which* scope is meant does not authorize anything in it; the ten-step sequence
still runs, and the strength ceiling still applies.

**Everything else about voice is already governed and gets no new mechanism** — see *Derivations*
below.

## Context

Section 14's vocabulary census found the domain almost entirely absent: `audio`, `STT`, `TTS`,
`transcript`, `transcription`, `microphone`, `speaker`, `telephony`, `phone`, `voicemail`,
`utterance`, `barge-in`, `wake word`, `voiceprint`, `biometric` and `DTMF` each returned **zero
occurrences**. `voice` returned fourteen — and **those fourteen already decide the security
question**, which is why Section 14 is far less greenfield than the vocabulary suggests.

`D-14` (voice/speech technology) remains deferred to this section and **is not resolved here**: no
technology is selected.

## Problem

**Two accepted documents give different answers about what voice can do, and an engineer building
the voice surface must choose.**

| Document | Says |
| --- | --- |
| `USER_INTERFACE_ARCHITECTURE.md` §7 · Section 02 · Active | Voice must always support *"conversation, **confirmation of high-risk actions**"*; *"voice requires explicit confirmation of scope for anything **above `PREPARE`**"* — both presupposing voice operates above `PREPARE`; and *"a surface may vary in depth; **it may never vary in authority**"* |
| `USER_INTERFACE_ARCHITECTURE.md` §6 · Section 02 · Active | Approvals are *"approvable in one action, **from any surface**"* |
| `AUTHENTICATION_MODEL.md` §4 · Section 04 · Active | *"Voice sessions **may not reach above `PREPARE`** without step-up on another surface — voice identification alone is not an authentication factor for consequential work"* |
| `THREAT_MODEL.md` `T-20` · Section 04 | *"Voice is the weakest surface and is **capped at `PREPARE`**"* |

**The sharpest form: one document says a surface may never vary in authority, and another says
voice specifically does.** Read one way, a spoken *"yes"* approves a `HIGH-IMPACT EXECUTE` because
approvals are available "from any surface". Read the other way, voice cannot participate in
approval at all — which contradicts §6 and §7's own requirements and would strand James.

**This is the same defect shape Sections 05 and 08 found**: accepted documents describing one
mechanism at incompatible granularities, with no statement of how they relate. It matters more here
because **voice is the one surface where input, identity, authority and approval are all carried by
the same undifferentiated signal** — a sound. Every boundary the architecture draws between them is
invisible in the medium itself.

## Options Considered

1. **Voice can approve, because §6 says any surface.** Rejected: it makes `AUTHENTICATION_MODEL.md`
   §4 and `T-20`'s residual dead text, and makes the weakest-authenticated surface the one that authorizes the
   most consequential actions.
2. **Voice cannot participate in approval at all.** Rejected: contradicts §6 and §7 as accepted,
   and strands James — the surface most likely to be in use hands-free would be the one unable even
   to *show* an approval request.
3. **Adopt voice biometrics (voiceprint) as an authentication factor**, making voice
   self-sufficient. Rejected — see *Reason*.
4. **Separate the action side from the session side**: a surface never varies what an action
   requires, and always varies what strength it supplies. Voice carries the interaction; strength
   comes from `A-3` step-up.

## Decision Made

Option 4.

## Reason

**Option 4 is the only reading under which both accepted documents remain true**, and it requires
no new mechanism: `A-3` step-up, the session strength ceiling, `I-09`, and `I-109`'s binding all
already exist and already do the work.

**Option 3 was rejected on the architecture's own established grounds, and the rejection is worth
recording.** A voiceprint would be a **new trust dependency** doing exactly the work the
architecture refuses elsewhere: it would establish an authorization-relevant fact — *"this speaker
is James"* — by statistical inference from a signal an adversary can synthesise. Voice cloning from
seconds of sample audio is a present capability, not a speculative one; replay is trivial; and a
false accept is a **silent, complete impersonation of the only identity that originates authority**
(`IDENTITY_AND_AUTHORITY.md` §2). `A-2` already requires factors resistant to replay and relay, and
*"codes read aloud"* are already excluded as primary factors — a voiceprint is weaker than what is
already excluded. **NOVA does not adopt voice biometrics as an authentication factor, and this ADR
records that as a decision rather than an omission.** Whether a voiceprint may serve as a
*non-authoritative* convenience signal — routing, personalisation — is not decided here and would
be Section 37's if it ever arises, because it is biometric data.

**The four claims voice blurs, kept apart** — this is the discipline the decision exists to
preserve:

```text
"This audio came from James's device."   ← a claim about a channel. Establishes nothing about a person
"This speaker is James."                 ← NOT ESTABLISHABLE by voice. Identity comes from A-1/A-2
"James said these words."                ← integration.supplied testimony from an STT provider
"James authorized this action."          ← requires I-09, sufficient session strength, and I-109's binding
```

**Each arrow is a boundary the medium hides**, and none of them is crossed by the model
interpreting the audio (`I-20`: ability is never authorization; `I-102`: a model never establishes
an authorization-relevant fact).

## Derivations — what Section 14 did *not* need to decide

Each of these is a genuine voice concern that an existing rule already answers, with its
enforcement point named. **None required new machinery.**

| Voice concern | Governed by | Enforced at |
| --- | --- | --- |
| A transcript is not what was said | An STT provider is an **integration**; its output is `integration.supplied` (`S11-D2`'s shape), untrusted (`SECURITY_BOUNDARIES.md` §3) | Ingested as untrusted data |
| Transcript / audio can't become fact | `I-39`, `I-110` — trust promotion is never automatic, never model-mediated, never inferred from repetition | Trust-promotion authority (C3) |
| Spoken injection | Untrusted content may inform, never escalate (`I-40`); taint carried `I-99`, persisted `I-111` | Plan authorization; `MT-7` third row |
| Spoken command → tool | Argument envelope (`I-100`, `MT-5`); leaf totality (ADR 0036) | Tool call PEP |
| *"Yes"* then the model changes recipient/amount/tool | **`I-109`** — approval binds ten properties; any change and the approval does not apply | Pre-execution binding check |
| Conversation accumulating authority | *"Context… **never a conversation**"* (`AUTHORIZATION_MODEL.md` §2); *"a conversation does not accumulate authority"* (`CONTEXT_ARCHITECTURE.md` §1) | Context resolution per request |
| STT / TTS / telephony provider | **`I-114`** — each is a distinct execution binding; no substitution, no provider equivalence | Tool PEP + Broker step 2a, per attempt |
| Spoken output to a person | Section 13 `S13-D1` — classified egress: `I-99` → `I-27` → `DATA_CLASSIFICATION.md` §2 | **PDP step 7**, Tool call PEP |
| Outbound call recipient | `MT-5` *Target*; recipient-list size is *Magnitude* | Tool call PEP |
| Inbound call / callback / DTMF | ADR 0037 `S11-D3` — no identity, no token, no grant | `I-14` default deny |
| Call "connected" / "failed" claims | `S11-D2` — provider testimony, never `system.verified`; timeout is **unknown**, never failure | `RELIABILITY_ARCHITECTURE.md` §2 |
| Scheduled or recurring calls | Section 12 — an automation is **intent, not authority**; every firing freshly authorized | Per-firing pipeline |
| Audio / transcript classification | `I-27` strictest-source; audio of a marked LIFE area is SENSITIVE-PERSONAL | Classification at creation; step 7 on egress |
| Spoken *"stop"* | `X-5` — stop is reachable from every surface **without navigation**; `X-1` enforced at enforcement points | Enforcement points read stop state |

**Two asymmetries worth stating because they are easy to get backwards.** A spoken stop **may**
take effect from an unauthenticated speaker — stop is **restriction**, and the architecture
deliberately does not gate restriction like it gates grant (`X-5`; the same reasoning that makes
agent suspension C1). **Lifting** a stop is the opposite: `X-6` requires an explicit human act
authenticated at **full strength**, which voice cannot supply. And a **TTS provider change alters
what an external person hears, while an STT provider change alters what NOVA believes** — the first
is egress, the second is input; both are `I-114` bindings, and neither substitutes within the
other's envelope.

## Tradeoffs

**Advantages:** no new invariant, document, object, factor, authority or change class; two accepted
documents stop contradicting each other without either being overruled; the voiceprint question is
answered deliberately rather than left for an implementer.

**Disadvantages:** **hands-free is materially limited, permanently.** Anything above `PREPARE`
needs another surface, which is exactly when hands-free is most wanted — driving, cooking, walking
— and the pressure to relax this will be constant and reasonable-sounding. **Step-up interrupts the
one interaction whose value is not being interrupted**, which will push usage toward batching
approvals, and batching is what `KNOWN_RISKS.md` already records as producing reflexive approval.
**And the residual risk is unmitigated rather than reduced**: a cloned voice that sounds exactly
like James can still drive every `READ`–`PREPARE` operation, read aloud whatever those surface, and
consume budget — bounded by the ceiling, not by detection.

## Consequences

- `USER_INTERFACE_ARCHITECTURE.md` §6 and §7, and `AUTHENTICATION_MODEL.md` §4, gain marked notes
  reconciling the two sides. **Neither document's accepted text is overruled**; both are narrowed to
  the side they actually govern.
- `COMMUNICATION_ARCHITECTURE.md` gains §8 stating the voice pipeline's trust chain. **Coupling
  stated:** that document is Proposed under ADR 0039, so if 0039 is rejected §9 goes with it — the
  reconciliation in the two Active documents does **not** depend on it and stands alone.
- `THREAT_MODEL.md` gains `T-42`; `KNOWN_RISKS.md` gains §3.14.
- **`INVARIANTS.md` is deliberately not amended.** `I-01`–`I-114` byte-identical.
- **No new architecture document.** Voice-as-surface is `USER_INTERFACE_ARCHITECTURE.md`'s;
  voice-as-session is `AUTHENTICATION_MODEL.md`'s; voice-as-communication is
  `COMMUNICATION_ARCHITECTURE.md`'s. All three exist and each cleanly owns its part.
- **`D-14` remains deferred.** No speech, telephony, or audio technology is selected.

## The amendments

**All are Proposed and marked in place. If this ADR is rejected, each is removed and the accepted
text restored verbatim.**

| # | Document | Section / status | Change |
| --- | --- | --- | --- |
| 1 | `USER_INTERFACE_ARCHITECTURE.md` §6, §7 | 02 · Active | Approval reachability vs. authentication strength; confirmation-of-scope is disambiguation |
| 2 | `AUTHENTICATION_MODEL.md` §4 | 04 · Active | The voice cap governs the session side; voice biometrics explicitly not adopted |
| 3 | `COMMUNICATION_ARCHITECTURE.md` §8 | 13 · **Proposed** | The voice pipeline trust chain (couples to ADR 0039) |
| 4 | `THREAT_MODEL.md` | 03 · Active | `T-42`. `T-03`'s, `T-20`'s and `T-39`'s residuals **not reduced** |
| 5 | `KNOWN_RISKS.md` §3.14 | 03 · Active | Section 14 residuals |

## What Would Change This

An authentication factor that works over an audio channel and is genuinely resistant to replay,
relay and synthesis — which a voiceprint is not. That would raise the voice ceiling by satisfying
`A-2`, **not** by weakening `A-3` or by treating speaker recognition as identity.
