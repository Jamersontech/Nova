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
| **Human (James)** | Possession + knowledge or biometric; multi-factor | Yes, bounded | §3 |
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

**A-2 — Phishing-resistant primary factor.** The primary factor must be bound to origin or
device such that replay from another origin fails. Shared secrets transmitted by the user
(passwords alone, SMS codes) do not satisfy this as a primary factor.

**A-3 — Step-up for consequence.** Authentication strength scales with what the session is
about to do. `IRREVERSIBLE` actions and changes to grants, policy, or credentials require a
**fresh** authentication — not merely a valid session.

**A-4 — Recovery is a first-class risk.** Account recovery is the most commonly attacked path
in any authentication system. Recovery must be **at least as strong as primary
authentication**, must be rate-limited, must notify, and must be audited. A recovery flow
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

---

## 5. Agent and Execution Authentication

Agent identities are **issued, not presented**: the runtime mints an execution identity for
one execution, and nothing else can produce one. An agent cannot authenticate as another
agent, as NOVA, or as James, because it holds no credential capable of the claim (`I-66`).

An execution identity is valid for **one execution, in one context, until it completes or
expires**. There is no refresh; a new execution requires a new issuance derived by the same
intersection (`I-07`).

---

## 6. What Is Deferred

| Deferred | Why |
| --- | --- |
| **Authentication provider / vendor** (`D-09`) | A technology choice. The requirements above are vendor-independent and are the criteria a provider must meet |
| **Specific factors** (passkey, hardware key, TOTP, biometric) | Product choices constrained by `A-2`; James's device and preference decide (`Q-03`) |
| **Session durations and idle timeouts** | Depend on lived usage; must be set before production |
| **Multi-user mechanics** | Blocked on `Q-04`. The external-user class exists and is unimplemented |

Invariants: `I-64`–`I-67`.
