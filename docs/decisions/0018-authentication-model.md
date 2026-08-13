# 0018 — Multi-Factor, Phishing-Resistant Authentication with Step-Up

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 04
**Section:** 04
**Partially resolves:** `D-09` — the model, not the provider

## Decision
Human authentication requires multi-factor by default for any session reaching `EXECUTE` or
above, with a phishing-resistant primary factor bound to origin or device. Authentication
strength scales with consequence: `IRREVERSIBLE` actions and changes to grants, policy, or
credentials require **fresh** authentication, not merely a valid session. Recovery must be at
least as strong as primary authentication. Sessions carry absolute expiry, are per-surface,
and are individually enumerable and revocable. Clients never authenticate.
**No provider, protocol, or factor technology is selected.**

## Context
`D-09` is assigned to Section 04. Section 03 established identity classes and that a session
carries continuity, not authority.

## Problem
NOVA can reach money, client production systems, and irreversible actions. A compromised
session is a compromised business. But authentication friction on every interaction destroys
the product principle of minimal cognitive load.

## Options Considered
1. **Single strong authentication, long sessions.** Lowest friction; a stolen session reaches
   everything, and the highest-consequence actions are protected no better than the lowest.
2. **Re-authenticate for everything.** Maximum protection; James authenticates dozens of times
   daily, so in practice he weakens factors to cope — a net loss.
3. **Multi-factor baseline with consequence-scaled step-up.** Friction concentrated where
   consequence is; requires a risk classification, which already exists (ADR 0006).
4. **Risk-adaptive/behavioural authentication.** Adjusts to context; non-deterministic and
   manipulable, and unpredictability in an authorization-adjacent control is a defect.

## Decision Made
Option 3, reusing the ADR 0006 risk classes so authentication strength and approval
requirements share one boundary rather than two.

## Reason
The same reasoning as ADR 0006: concentrating protection where consequence lives keeps each
challenge meaningful. Reusing the existing risk classes means one mental model, and no new
place for the two to disagree.

## Tradeoffs
**Advantages:** routine work is low-friction; irreversible actions and security-configuration
changes always require a fresh, strong proof; per-surface sessions contain device compromise;
recovery is treated as the attack path it is.
**Disadvantages:** step-up interrupts at the worst moment — during consequential work; a
phishing-resistant primary factor implies a device dependency and a real lockout risk, making
`A-4` recovery load-bearing; per-surface sessions mean authenticating on each device.

## Consequences
Voice cannot exceed `PREPARE` without step-up elsewhere. Recovery design becomes a Section 04
deliverable of equal weight to primary authentication. Multi-user mechanics remain blocked on
`Q-04`.

**Context Tokens must carry a detectable integrity property.** *(Added 2026-08-12, F-3.)* A
component receiving a Context Token must be able to detect modification after issuance or
fabrication by a non-issuer, and must refuse the token if it cannot (`CT-1`–`CT-3`, `I-87`). **No
mechanism is selected, and unforgeability is not claimed**; the requirement does not mitigate
compromise of the Context service (`T-23a`) and introduces a new trusted component of its own
(`T-23c`).

Invariants `I-64`–`I-67`, `I-87`.

## What Would Change This
`Q-04` answered **"multi-user"**. *(Corrected 2026-08-12, M-9. The earlier characterisation as
"an extension, not a reversal" understated the disruption and is withdrawn.)*

Multi-user is **not** something that can be layered onto the current model:

- **`I-09` currently means only James approves.** A second approver requires a **superseding
  ADR** for that authority invariant.
- **`I-10` currently means only James grants access.** A second granter requires a **superseding
  ADR** for that authority invariant.
- Delegation *between humans* does not exist in the current model at all
  ([`SCOPE_AND_IDENTITY_MODEL.md`](../architecture/SCOPE_AND_IDENTITY_MODEL.md) §5 narrows only
  downward from James).

Authentication itself would extend cleanly — the external-user identity class already exists and
is deliberately unimplemented. **The authority model would not.** Changing who may approve, grant,
or delegate is a **C3 change requiring explicit superseding governance**, not an addition.

**`I-09` and `I-10` are not modified now**, and no multi-user design is introduced. This records
only what the change would cost when `Q-04` is answered.
