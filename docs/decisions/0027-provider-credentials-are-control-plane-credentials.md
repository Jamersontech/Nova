# 0027 — Provider Credentials Are Control-Plane Credentials

**Status:** **Proposed**
**Proposed:** 2026-08-14 — Section 05
**Section:** 05

## Decision

A model-provider credential is a **control-plane credential**. It is held only by the Model
Gateway, is **never bound to a client scope**, is never brokered to an agent, tool, integration,
sandbox, or coding agent, and never appears in a prompt, log, memory, audit payload, or model
context (`I-103`).

It authorizes NOVA to talk to a provider. **It authorizes access to no client scope**, and holding
it yields nothing about any scope.

`I-23` — *"every credential binding belongs to exactly one scope; there are no global
credentials"* — is **unamended**. It governs credentials that reach an external system **on behalf
of a scope**. A provider credential does not: the scope's authorization to reach that provider is
carried by the Context Token and decided at the gateway enforcement point (`I-94`, `MG-9`), not by
the credential.

## Context

[`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md) §1
separates tool, integration, credential and account, and binds each credential to exactly one
scope node — the property that makes one `send_email` tool safe across every client.

## Problem

**A model-provider credential cannot be per-scope, and `I-23` read literally forbids it to exist.**
One provider account serves every scope permitted to use that provider. Section 02 wrote `I-23`
about integration credentials — Client A's mailbox token — and the model path was never tested
against it. Left unresolved, an implementer faces a credential the architecture says is illegal,
and the likely repairs are both bad:

- **Declare it an integration credential bound to root.** A credential bound at root is reachable
  from every scope below it, which is the "global credential" `I-23` exists to forbid, wearing a
  scope path.
- **Mint a provider account per client scope.** Satisfies the letter of `I-23` and buys nothing:
  the isolation `I-23` protects is *inside* NOVA, and it is already provided by the Context Token
  and the gateway enforcement point. Meanwhile per-client provider accounts multiply operational
  surface, rotation burden, and failure modes.

## Options Considered

1. **Root-bound integration credential.** Fits the existing model syntactically; recreates a
   global credential semantically.
2. **Per-scope provider credentials.** Satisfies `I-23` literally; large operational cost; no
   isolation gain inside NOVA; provider-side correlation persists anyway via network origin,
   billing relationship and timing.
3. **Amend `I-23` to admit exceptions.** Honest about the conflict, and it weakens an accepted
   invariant across the whole credential surface to solve one case. An invariant with an exception
   clause is an invariant an implementer can argue into.
4. **Control-plane credential class, outside the client scope tree.** `I-23` untouched, because a
   control-plane credential is not a scope-bound credential and does not claim to be. The gateway
   holds it; nothing else can; no client-scope capability is created anywhere.

## Decision Made

Option 4.

## Reason

**This is the same structural move Section 04 made for the control-plane audit partition**
([ADR 0023](./0023-audit-record-writer-authority.md)), for the same reason. Options 1 and 3 create
a capability that spans every client scope and then forbid its misuse by rule. Every defect the
Section 04 reviews found had that shape. Option 4 removes the capability instead: a credential
that is not in the client scope tree cannot reach a client scope, because there is no client scope
there to reach.

**It also keeps the invariant honest.** `I-23` continues to mean exactly what it says about the
credentials it was written for, rather than acquiring an exception that later readers must
relitigate.

## Tradeoffs

**Advantages:** `I-23` and `I-22` untouched and unweakened; one credential to rotate and revoke
per provider; no global credential exists in the client scope tree; the gateway's holding of it is
explicit and inspectable rather than an unstated assumption.

**Disadvantages:** a second credential *class* now exists, and a class distinction is a thing
future readers can misapply — a genuine risk that an implementer files an integration credential
as "control-plane" to escape per-scope binding. The class is therefore **closed**: control-plane
credentials are those reaching a service that acts for NOVA itself rather than for a scope, and
adding a member is C3.

**The residual is real and is not mitigated.** Because one credential serves many scopes, **the
provider can correlate every scope's traffic as one customer.** NOVA does not prevent this and
does not claim to. Recorded as `T-30`, extending `T-15`'s "outside NOVA's control" residual.

## Consequences

- [`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](../architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md)
  §5 is amended to name the class, authorized by
  [ADR 0028](./0028-section-05-amendments-to-accepted-architecture.md).
- Provider credentials live in the secrets store under
  [`SECRETS_ARCHITECTURE.md`](../architecture/SECRETS_ARCHITECTURE.md)'s existing requirements —
  expiring, rotatable without code change, individually revocable. No new secrets mechanism.
- Revoking a provider credential stops **all** scopes reaching that provider at once. That is the
  correct blast radius for a control-plane credential and is stated so it is not discovered during
  an incident.

Invariants: `I-103` (new). `I-21`, `I-22`, `I-23`, `I-25` untouched.

## What Would Change This

A provider offering genuinely isolated per-scope credentials at no operational cost, or a
regulatory constraint (`Q-06`) requiring per-client provider accounts — either of which makes
option 2 cheap rather than merely strict.
