# Authentication Model

**Status:** Proposed — Section 04, pending James's approval.
**Covers:** how each identity class proves it is what it claims, and how sessions are
established, bounded, and ended.
**Extends:** [`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md) (identity classes) and
[`SCOPE_AND_IDENTITY_MODEL.md`](./SCOPE_AND_IDENTITY_MODEL.md) (session and execution
identity). Neither is replaced.

**No authentication vendor, protocol, or factor technology is selected.** `D-09` is resolved
only as far as the *model*; the provider remains deferred.

---

## 1. Authentication Is Not Authorization

Restating the distinction because this is the document where it is most easily lost:

> **Authentication** establishes *who is acting*. **Authorization** decides *whether they
> may*. Passing the first grants nothing (`I-13`).

A fully authenticated James still faces default deny, containment-first evaluation, risk
classes, and approval requirements. Authentication opens the door to the building, not to
any room in it.

---

## 2. Per-Class Requirements

| Identity class | Authenticates by | Session? | Requirement |
| --- | --- | --- | --- |
| **Human (James)** | Multiple independent factors, primary factor replay-resistant per `A-2` | Yes, bounded | §3 |
| **System (NOVA)** | Platform-internal identity, non-exportable | No — acts per execution | Cannot be assumed by any other component |
| **Agent** | Issued per execution by the runtime; never long-lived | No — execution-scoped | Cannot be presented by anything but the runtime |
| **Coding agent** | Sandbox-bound identity, valid for one Work Order | No | Confers nothing inside NOVA |
| **Service** | The external system's own mechanism, via a credential binding | n/a | Never authenticates *into* NOVA |
| **Client** | **Does not authenticate.** A subject, never an actor (`I-11`) | No | No credential is ever issued to a client |

**The row that matters most is the last.** Clients hold no login, no token, and no portal
identity. Any future client-facing surface is a *deliverable produced by NOVA*, not a client
session — otherwise the entire isolation model acquires an actor it was not designed for.

---

## 3. Human Authentication

**Requirements, not products:**

**A-1 — Multi-factor by default.** At least two independent factors for any session that can
reach `EXECUTE` or above. A single factor may open a `READ`-only session.

**A-2 — Phishing-resistant primary factor.** The primary factor must resist replay by an
attacker who has induced James to authenticate against a system they control. *(Clarified
2026-08-12, L-1: this states the required **property**, not a technology. Binding to origin or
device is one well-known way to achieve it and is not mandated. Any mechanism demonstrably
providing equivalent replay resistance satisfies `A-2`.)* Shared secrets transmitted by the user
— passwords alone, codes read aloud or retyped — do not provide this property and do not satisfy
`A-2` as a primary factor. **No factor technology, protocol, or vendor is selected** (`D-09`).

**A-3 — Step-up for consequence.** Authentication strength scales with what the session is
about to do. `IRREVERSIBLE` actions and changes to grants, policy, or credentials require a
**fresh** authentication — not merely a valid session.

**A-3a — Step-up for cross-scope audit review.** *(Added 2026-08-13, `H-1` Option 3.)* Reviewing
audit records across **more than one scope** requires step-up (`I-67`). **Single-scope audit
reading does not** — routine oversight of one scope proceeds at normal session strength.

**Why the line is drawn there.** `S4-P2` (Option D) removed every component-held audit-read
capability and placed the corpus behind James's direct per-scope access. That is a real gain — no
component becomes a cross-client audit corpus — but it means the **cross-client corpus is now
reachable from one authenticated session**. Cross-scope audit review is treated exactly as NOVA
already treats every other cross-scope operation: elevated, decomposed per scope, and recorded per
scope touched (`I-49`, `I-86`, [`CROSS_SCOPE_DATA_RULES.md`](./CROSS_SCOPE_DATA_RULES.md)).

**The cost, stated:** step-up lands during incident review, which is when James is most likely to
need breadth quickly and when the notification path may itself be degraded (`B-3`). Single-scope
reading stays unimpeded so that routine oversight does not train reflexive approval
([`KNOWN_RISKS.md`](./KNOWN_RISKS.md) records approval fatigue as a security failure). **Audit
records remain readable only by James** and remain append-only and undeletable, including by him
(`I-47`).

**A-4 — Recovery is a first-class risk.** Account recovery is the most commonly attacked path
in any authentication system. Recovery must be **at least as strong as primary
authentication**, must be rate-limited, must notify, and must be audited. **Failed authentication and
failed recovery are recorded in the control-plane audit partition** (`I-92`, `E-12f`) — they occur
before any scope exists (§1), so they are never written into a client partition
*(clarified 2026-08-13, `HIGH-1`)*. A recovery flow
weaker than the primary factor makes the primary factor decorative.

**A-5 — No shared identity.** One human identity is James's. If `Q-04` is later answered
"multi-user", additional humans receive their own identities under the external-user class —
never a shared credential and never an expansion of James's identity.

**A-6 — Compromise assumption.** The model assumes James's device may be lost or compromised.
Sessions must be individually enumerable and revocable, and revocation must take effect at
the next decision (`I-65`).

---

## 4. Sessions

```text
Session
├── identity          exactly one human identity
├── established_at    when authentication succeeded
├── factors           which factors were satisfied
├── strength          determines the ceiling of what it can reach
├── expires_at        absolute; not extended by activity alone
├── revoked           independently revocable
└── surface           which device/channel it belongs to
```

**A session carries continuity, not authority** — restating
[`SCOPE_AND_IDENTITY_MODEL.md`](./SCOPE_AND_IDENTITY_MODEL.md) §3.1. Rules:

- **Absolute expiry.** Sessions end at a fixed horizon regardless of activity. Idle timeout
  is additional, not a substitute.
- **Strength ceiling.** A session established with weak factors cannot reach high-risk
  actions; it must step up (`A-3`).
- **Per-surface.** Sessions are not shared between devices. Compromise of one surface does not
  hand over the others.
- **Enumerable and revocable.** James can see and end every active session.
- **Emergency stop ends all sessions** and requires fresh authentication to resume
  ([`SECURITY_OPERATIONS.md`](./SECURITY_OPERATIONS.md) §4).

**Voice is the weakest surface** ([`USER_INTERFACE_ARCHITECTURE.md`](./USER_INTERFACE_ARCHITECTURE.md) §7).
Voice sessions may not reach above `PREPARE` without step-up on another surface — voice
identification alone is not an authentication factor for consequential work.

> **This cap governs the session side, and voice biometrics are not adopted.** ***PROPOSED — added
> by Section 14, not yet accepted*** *(2026-08-15; authority
> [ADR 0040](../decisions/0040-voice-is-an-input-surface-not-an-authentication-factor.md),
> Proposed; removed and the accepted text restored verbatim if rejected).* The rule above and
> `USER_INTERFACE_ARCHITECTURE.md` §7's *"a surface may never vary in authority"* read as
> contradicting. **Both are correct**: §7 governs the **action side** — what an action means and
> requires is identical everywhere — and this rule governs the **session side**, what strength this
> session supplies. Voice therefore **carries** an approval interaction and **cannot complete one**
> above `PREPARE`; a spoken *"yes"* is expressed intent, and the approval is recorded only when a
> sufficient-strength session exists (`A-3`). `I-09` and `I-109` are unchanged.
>
> **A voiceprint is not a factor, and that is a decision rather than an omission.** It would
> establish an authorization-relevant fact — *"this speaker is James"* — by statistical inference
> from a signal an adversary can **synthesise or replay**, against the identity that originates all
> authority. `A-2` already excludes *"codes read aloud"* as a primary factor for exactly this
> family of weakness, and a voiceprint is weaker still. **Four claims stay separate**, and voice
> establishes only the third — as `integration.supplied` testimony from a speech provider, never as
> fact (`I-39`, `I-110`):
>
> ```text
> audio came from a device   → a claim about a channel, not about a person
> this speaker is James      → NOT ESTABLISHABLE by voice; identity comes from A-1/A-2
> James said these words     → provider testimony, untrusted
> James authorized this      → I-09 + sufficient session strength + I-109's binding
> ```

---

## 5. Agent and Execution Authentication

Agent identities are **issued, not presented**: the runtime mints an execution identity for one
execution. **Required property:** nothing other than the runtime may produce, re-present, refresh,
or synthesize one, and no identity class may authenticate as another (`I-66`).

*(Clarified 2026-08-12, M-8.)* This is stated as a **requirement on the runtime**, not as a proven
property. NOVA specifies no mechanism establishing unforgeability and claims none; whether the
requirement holds depends on how identities are issued and verified at runtime (`D-01`, `D-09`),
and it is unverified until Section 31.

An execution identity is valid for **one execution, in one context, until it completes or
expires**. There is no refresh; a new execution requires a new issuance derived by the same
intersection (`I-07`).

---

## 6. Context Token Integrity

*Added 2026-08-12 following final review (F-3). The Context Token is the sole input from which
both the PDP's evaluation and the storage scope binding derive
([`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md) §4.1–4.2). Until now, nothing in the
architecture required a recipient to be able to tell a genuine token from a modified or
invented one.*

**CT-1 — Context Tokens must carry an integrity property (`I-87`) `[PHYS]`.** A component that
receives a Context Token must be able to **detect** that the token was modified after issuance,
or fabricated by something that is not the Context service. A token that fails this detection is
rejected, and the rejection is recorded. There is no path that accepts a token whose integrity
cannot be established.

**CT-2 — Detection is required at every point that consumes a token.** That includes the PDP,
each of the five enforcement points, and the Data-Access Boundary at binding establishment
(`I-78`). A component that consumes a token without checking is a defect, not a permitted
optimisation.

**CT-3 — Failure is closed.** Missing, unverifiable, or failed-integrity tokens are treated
exactly as a missing scope under `I-79`: no channel is opened, the access is denied, and the
event is recorded.

### What CT-1 does not say

**No mechanism is specified, and none is implied.** No signature scheme, message authentication
code, algorithm, protocol, key hierarchy, token format, or vendor is selected here. CT-1 states a
**property a future mechanism must provide**; the mechanism itself is deferred with the rest of
the platform substrate (`D-09`, `D-33`).

**"Unforgeable" is not claimed.** CT-1 says a recipient must be able to *detect* unauthorized
modification or fabrication. It does not assert that forgery is impossible, and no such assertion
is made anywhere in Section 04.

**CT-1 does not mitigate compromise of the Context service.** A compromised Context service issues
tokens through the legitimate issuance path — they are genuine tokens naming the wrong scope, and
integrity detection has nothing to detect. `T-23a` is unchanged by this requirement.

**CT-1 does not restore the withdrawn independence claim.** The PDP and the scope binding still
derive from the same Context Token, and are still not independent of the Context service
([`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md) §4.2). CT-1 narrows *who can produce a
token that is accepted*; it does not add a second independent root of trust.

**CT-1 is itself a new dependency.** Whatever eventually provides token integrity becomes a
trusted component whose own compromise defeats the property — recorded as a distinct threat in
[`THREAT_MODEL.md`](./THREAT_MODEL.md) `T-23c`.

---

## 7. What Is Deferred

| Deferred | Why |
| --- | --- |
| **Authentication provider / vendor** (`D-09`) | A technology choice. The requirements above are vendor-independent and are the criteria a provider must meet |
| **The mechanism providing Context Token integrity** (`CT-1`) | A technology choice, deferred with the platform substrate (`D-09`, `D-33`). The property is fixed here; nothing about how it is achieved is |
| **Specific factor mechanisms** | Product and protocol choices constrained by the `A-2` property; James's devices and preference decide (`Q-03`) |
| **Session durations and idle timeouts** | Depend on lived usage; must be set before production |
| **Multi-user mechanics** | Blocked on `Q-04`. The external-user class exists and is unimplemented |

Invariants: `I-64`–`I-67`, `I-87`, `I-89`–`I-90`.
