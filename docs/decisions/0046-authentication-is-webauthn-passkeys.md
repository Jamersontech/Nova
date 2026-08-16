# 0046 — Authentication Is WebAuthn Passkeys with Opaque Server-Side Sessions

**Status:** **Proposed**
**Proposed:** 2026-08-16 — substrate work under ADR 0044
**Section:** 04 — `D-09` has always been owned by Section 04
**Resolves:** `D-09` — the **provider and factor technology** half. The *model* half was resolved
by [ADR 0018](./0018-authentication-model.md) and is not reopened.

## Decision

**NOVA authenticates James with a WebAuthn passkey and issues an opaque, server-side,
individually revocable session. No password exists anywhere in the system.**

Four parts:

**1. The protocol is WebAuthn.** The primary factor is a passkey. Verification is performed
server-side by the `py_webauthn` library; **no cryptography or protocol logic is written in this
repository**.

**2. Session strength is read out of the verified signature.** The authenticator reports user
verification in the `UV` flag of `authenticatorData`, which is inside the signed payload. A session
established with `UV` set is `multi_factor` and may reach `EXECUTE`; without it the session is
`single_factor` and may only read.

**3. The browser holds one opaque value.** A 256-bit session reference, `HttpOnly`,
`SameSite=Strict`, `Secure` over https. The database stores **only its SHA-256** — the column is a
verifier, not a credential. No Context Token, no scope, no rights, and no authorization state ever
reaches the browser.

**4. Authentication is confined by database privilege.** It runs *before* any Context Token exists,
so it cannot go through the Data-Access Boundary. A third role, `nova_auth`, holds privileges on
`auth_credential` and `auth_session` and **nothing else**; `nova_app` is revoked from both.

## Why WebAuthn, and why that is not a vendor preference

`A-2` requires a primary factor that **resists replay by an attacker who has induced James to
authenticate against a system they control**. That is a property, not a product, and the model
deliberately mandates no technology.

WebAuthn provides the property **by construction rather than by policy**: the authenticator signs
over the hash of the relying-party ID together with the browser's own origin, so an assertion
produced at an attacker's origin does not verify at NOVA's. Nothing is typed, so nothing typed can
be captured. The suite proves this rather than asserting it — an assertion generated against
`https://evil.example` is refused, and so are a wrong relying party, a replayed challenge, a
tampered signature and a regressed signature counter.

`A-1` requires two independent factors for any session reaching `EXECUTE`. A passkey with user
verification supplies possession of the authenticator plus a factor checked on the device. **The
client cannot assert its own strength**, because the flag is inside the signature the server
verified — which is the only reason the `EXECUTE` gate is worth anything.

**No provider was selected because none was needed.** The alternative shape — a hosted identity
provider behind the session seam — would add an external dependency, a new trusted component, and
an account NOVA does not otherwise require, in exchange for a property the browser platform already
provides directly. `A-5` (one human identity is James's) removes the usual reason to buy identity
infrastructure: there are no users to administer, invite, or federate.

## Authentication terminates at one fact

```text
browser → WebAuthn ceremony → opaque session → AUTHENTICATED SERVER IDENTITY
                                                          │
                                    everything below is unchanged
                                                          ▼
        Context service (sole issuer, I-106) → PDP → Data-Access Boundary → RLS
```

`I-13` restated: **passing authentication grants nothing.** The session carries no rights, no
scope, no grants and no ceiling. Those are derived per request by the Context service and decided
by the PDP, exactly as before this ADR. The authorization system was **not redesigned around
authentication**, and no invariant changed.

## What is deliberately not built

No user administration, organisations, invitations, SSO, OAuth layer, account dashboard, or
multi-tenant identity architecture. `A-5` and `Q-04` (*"do not build a multi-user product now"*)
make all of it premature.

## Limitations, recorded rather than hidden

| | Limitation | Why it is acceptable **today** |
| --- | --- | --- |
| **1** | **Bootstrap is trust-on-first-use.** The first passkey enrols with no session, because otherwise none could ever exist. Whoever reaches the enrolment route first on a system with no credential becomes James | Every *subsequent* passkey requires an authenticated multi-factor session belonging to the same actor (proven by test). In deployment the window closes by not exposing the route after enrolment — an **operational** control, and not claimed to be more |
| **2** | **No attestation is verified.** NOVA does not establish *which* authenticator model holds the key | `A-2` is about replay resistance and does not require attestation. Device allow-listing is a Section 31 concern |
| **3** | **No step-up re-authentication (`A-3`).** Session strength is fixed at login | No `IRREVERSIBLE` path exists yet to require it. Stated, not claimed |
| **4** | **No recovery flow (`A-4`).** Losing every passkey means losing access | That is the safe direction to fail. Recovery is the most attacked path in any authentication system and is not built speculatively — `A-4` requires it to be *at least as strong as* the primary factor, which is real work |
| **5** | **No idle timeout.** Expiry is absolute (12 hours) | `A-4`'s session rules call absolute expiry the requirement and idle timeout *"additional, not a substitute"* |

**`CT-1` is untouched.** Context Token integrity remains as it was; this ADR concerns the human
factor and the session, not the token, and claims no progress on `T-23a`/`T-23c`.

## Reversibility

**High for the session half, moderate for the protocol half.** Sessions are two additive tables and
one service class behind the seam's `resolve()` call; replacing them touches nothing below. The
protocol choice is harder to reverse only in that enrolled passkeys would need re-enrolment — but
no data migration is involved, because a credential is a public key and a session is disposable.

**No invariant was added, amended or weakened by this decision.**
