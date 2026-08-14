# Scope and Identity Model

**Status:** **Active** — Section 03, approved by James 2026-08-12 (as amended, commit 0917de5).
**Extends:** [`DOMAIN_ARCHITECTURE.md`](./DOMAIN_ARCHITECTURE.md) (scope tree) and
[`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md) (identity classes). Neither is
replaced. This document adds the operational detail those principles imply: scope kinds,
ownership, session and execution identity, and what each identity class may actually do.

---

## 1. Scope Kinds

A **scope** is a node in the tree — a context anchor, permission boundary, memory
partition, and credential partition ([ADR 0002](../decisions/0002-unified-scope-tree.md)).
Scopes differ in *what may attach to them*, never in *how access works*.

| Kind | Domain | May contain | May hold |
| --- | --- | --- | --- |
| `root` | — | Domains | Platform config, tool definitions, James's identity |
| `domain` | LIFE / BUSINESS / WEALTH | Domain-specific kinds | Domain policy, domain memory |
| `business` | BUSINESS | Clients, shared resources | Integrations, credentials, business memory, offerings |
| `client` | BUSINESS | Projects | Contacts, communications, documents, client memory |
| `project` | BUSINESS | Environments | Tasks, deliverables, workflows, project memory |
| `environment` | BUSINESS | — | Source, config, hosting, environment credentials |
| `area` | LIFE | Threads | Items, area memory, sensitivity marking |
| `thread` | LIFE | — | Items, thread memory |
| `holding` | WEALTH | Accounts/positions | Financial records, wealth memory |

### 1.1 Scope kinds are extensible per domain

Different domains legitimately need different internal structures — a business has clients,
a life area has threads, a wealth domain has holdings. **Do not assume every future
business will have an identical internal structure.**

A new scope kind may be introduced (a C3 change, [ADR 0015](../decisions/0015-extensible-scope-kinds.md))
provided it satisfies the **scope contract**:

1. Exactly one parent.
2. Access downward only, by explicit grant.
3. No implicit sibling path.
4. Partitions memory, knowledge, credentials, and permissions like any other scope.
5. Declares what may attach to it.

**Structure varies; authorization does not.** A domain may organize itself however it needs
as long as it obeys the same five rules — which is what lets NOVA absorb a business shaped
unlike KAIRO without a new isolation model.

---

## 2. Ownership

**Ownership is distinct from access.** The owner of a resource is the scope it belongs to —
not an identity, and not whoever created it.

```text
Resource → owned by exactly one scope
        → created by an identity (recorded as provenance, not ownership)
        → readable by identities holding a grant over that scope
```

Consequences:

- **An agent never owns anything.** It creates resources *into* a scope. Terminating the
  agent orphans nothing.
- **Ownership never transfers implicitly.** Moving a resource between scopes is an explicit,
  audited operation — and is prohibited between siblings.
- **The creator's identity is provenance** ([`PROVENANCE_AND_TRUST.md`](./PROVENANCE_AND_TRUST.md)),
  and confers no continuing rights.

This is what prevents the accumulation pattern where a long-lived agent gradually becomes
the de facto owner of everything it touched.

---

## 3. Identity Classes, Operationally

The six classes in [`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md) §2, plus two
identities that exist only at runtime.

### 3.1 Session identity

A bounded period of interaction. Carries continuity, **not authority**. A session belongs to
one human identity and may traverse many contexts. Sessions expire.

> A long session accumulates history, never permission.

### 3.2 Execution identity

One attempt to perform work. **This is the identity authorization actually evaluates.** It
is ephemeral, single-context, and single-purpose, and is derived by intersection:

```text
execution identity rights
   = agent definition rights
   ∩ granting identity's rights
   ∩ Context Token scope and rights
   ∩ risk-class ceiling
```

Intersection, never union — **the execution can never exceed any input.** This is the
structural reason no path in NOVA widens authority.

---

## 4. Capability Matrix

What each identity class may do. `—` means never, by architecture rather than by policy.

| Capability | Human (James) | System (NOVA) | Agent | Coding agent | Service | Client |
| --- | --- | --- | --- | --- | --- | --- |
| **Own** resources | via scopes | — | — | — | — | — |
| **Read** | any scope | granted scopes | token scope only | work-order workspace only | — | — |
| **Write** | any scope | granted scopes | token scope only | workspace only | — | — |
| **Execute** | ✅ | granted, risk-limited | token + closed tool list | sandbox only | — | — |
| **Approve** | ✅ **only** | — | — | — | — | — |
| **Delegate** | ✅ | narrowing only | narrowing only | — | — | — |
| **Grant access** | ✅ | — | — | — | — | — |
| **Revoke access** | ✅ | on expiry/emergency only | — | — | — | — |
| **Create credentials** | ✅ | — | — | — | — | — |
| **Request credential use** | ✅ | ✅ | ✅ via broker | ✅ via brokered handle | — | — |
| **Hold a credential** | ✅ | — | **—** | **—** | ✅ (is one) | — |

Four rows carry the weight:

- **Only James approves.** No system, agent, or automation may approve — otherwise
  human-in-the-loop is decorative.
- **Only James grants access.** Nothing in NOVA can widen its own or another's authority.
- **No agent ever holds a credential.** Agents *request use*; the broker injects at the
  boundary ([ADR 0009](../decisions/0009-credentials-are-references.md)).
- **Clients hold nothing.** A client identity is a subject data is *about*, never an actor.

**Service identity is the one exception worth stating carefully:** a service identity
effectively *is* a credential — it is the external-side account. It exists at the boundary
and never inside NOVA's agent layer.

---

## 5. Delegation

Delegation always narrows and is always recorded:

```text
James → NOVA → coordinator → specialist → tool → external service
```

A delegation carries: delegator, delegate, scope (⊆ delegator's), rights (⊆ delegator's),
expiry, purpose, **`may_redelegate`** and **`ancestry`**. ¹ **A delegation with no expiry is not
permitted** — unbounded delegation is how temporary access becomes permanent.

Re-delegation is allowed only where the original delegation permits it, and narrows again.

> ¹ **AMENDED BY SECTION 06 — ACCEPTED by James 2026-08-14.** *(2026-08-14; authority
> [ADR 0029](../decisions/0029-delegated-authority.md) and
> [ADR 0031](../decisions/0031-section-06-amendments-to-accepted-architecture.md), both **Accepted** 2026-08-14.)*
>
> **The two new fields fix a rule that tested data the record did not carry.** As accepted, the
> paragraph above conditions re-delegation on *"where the original delegation permits it"* while
> the field list contained **no such field** — an implementer had nothing to check.
> **`may_redelegate` is explicit and defaults to false**, so a capability an agent may *use* is not
> thereby one it may *pass on*. **`ancestry`** records the chain of delegators, which is what makes
> cycle refusal possible.
>
> **Four bounding rules** ([`AGENT_GOVERNANCE.md`](./AGENT_GOVERNANCE.md) §3, `I-107`), all checked
> at issuance (`I-106`):
>
> 1. **Strict narrowing.** Strictly narrower in at least one of scope, rights, tools, or risk
>    ceiling, **and** strictly earlier expiry. **This is what bounds depth** — each step descends a
>    finite authority lattice — which is why no numeric depth limit exists.
> 2. **No ancestry cycles.** Refused if the delegate already appears in its own `ancestry`.
> 3. **Explicit re-delegation**, per the field above.
> 4. **No fan-out count limit.** Parallel children are bounded by the shared root-execution budget
>    (`I-108`), which already governs the resource fan-out consumes.
>
> **A delegation cannot outlive its delegator's execution identity** — completion, failure,
> termination, revocation and emergency stop alike; the delegate fails closed at its next
> enforcement point (`V-2`, `AG-11`).
