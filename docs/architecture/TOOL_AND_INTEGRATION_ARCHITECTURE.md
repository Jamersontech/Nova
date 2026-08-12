# Tool and Integration Architecture

**Status:** **Active** — Section 02, approved by James 2026-08-12.
**Covers:** tools, integrations, credentials, and the accounts they reach — and why these
four must never be treated as the same thing.

---

## 1. Four Concepts, Kept Apart

| Concept | Is | Owned at | Example |
| --- | --- | --- | --- |
| **Tool** | A callable capability with a schema | Defined once at root | `send_email` |
| **Integration** | A configured connection to an external system | A scope node | KAIRO's mail provider connection |
| **Credential** | The secret authorizing that connection | Exactly one scope node | Client A's mailbox token |
| **Account** | The external-side entity | Outside NOVA | The actual mailbox at the provider |

**The relationship that makes tools safely reusable:**

```text
send_email  (one tool definition, defined once)
   ├── bound in /business/KAIRO/client-a → Client A's integration → Client A's credential
   ├── bound in /business/KAIRO/client-b → Client B's integration → Client B's credential
   └── bound in /life/admin              → James's personal mail  → personal credential
```

One tool, many bindings. The tool is shared; the integration, credential, and data never
are. This is what allows every business and client to use the same capabilities without
any possibility of mixing them — and why "we need a separate email tool per client" is
never the answer.

---

## 2. Tool Definition

Every tool declares:

```text
name                 canonical, stable
purpose              one sentence
input schema         typed, validated before invocation
output schema        typed, validated after
required rights      minimum permissions — no more
auth requirements    which integration kind, if any
risk class           default class; may be raised by context, never lowered
context requirements which scope kinds it may be bound in
error behaviour      failure modes and what each means
audit behaviour      what is recorded (never secrets or payload contents by default)
idempotency          whether a retry is safe
cost profile         expected cost, if material
```

**A tool declaring more rights than it uses is a defect**, caught in review and by
permission tests. Over-broad tools are the quiet path to over-broad agents.

**Idempotency is mandatory metadata** because the reliability layer must know whether a
retry is safe. A non-idempotent tool retried automatically is how one client receives four
SMS campaigns.

---

## 3. Invocation

```mermaid
sequenceDiagram
    participant A as Agent
    participant C as Capability Layer
    participant P as Policy
    participant B as Credential Broker
    participant I as Integration
    participant X as External Service

    A->>C: call(tool, args, Context Token)
    C->>C: validate args against schema
    C->>P: may this token call this tool at this risk?
    P-->>C: allow
    C->>B: credential for this tool in this scope
    B->>P: does token cover this credential's scope?
    P-->>B: allow
    B->>I: inject secret at the boundary
    I->>X: request
    X-->>I: response
    I-->>C: result (secret never returned)
    C->>C: validate result against schema
    C-->>A: result
    C->>C: emit audit record
```

**The secret never travels back up.** It is injected at the integration boundary and
discarded. The agent's context, the model's prompt, and the returned result never contain
it.

**Both directions are schema-validated.** Unvalidated tool output is a common injection
path into subsequent model calls.

---

## 4. Integrations

An integration is a configured connection bound to exactly one scope node. NOVA will
eventually integrate email, calendars, SMS, Google services, CRMs, payments, hosting,
domains, analytics, automation platforms, GitHub, coding agents, and other APIs.

**Rules:**

- An integration belongs to one scope. There are no global integrations.
- Two clients using the same provider have two integrations and two credentials.
- Integration failures are typed — auth, rate limit, unavailable, changed contract, invalid
  request — because recovery differs per type ([`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md)).
- **All data returned is untrusted** ([`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §3).
- Contract changes are expected. An integration that silently changes shape must surface as
  a failure, not as corrupted data flowing inward.

---

## 5. Credentials

Established in Section 1 ([`../DOMAIN_MODEL.md`](../DOMAIN_MODEL.md) §8); the mechanism:

- **Scoped to one node.** Never global, never shared across clients.
- **Brokered, never held.** No agent, orchestrator, or model ever receives one.
- **Least authority.** The narrowest external permission that works.
- **Expiring and rotatable.** Rotation must not require code changes.
- **Never in prompts, logs, memory, documents, audit payloads, or repositories.**
- **Revocable individually**, without disturbing other scopes.
- **Expiry is an event**, surfaced before it breaks something.

**Brokered handles for external agents.** A sandboxed coding agent receives a short-lived
handle to a narrow capability — never the client's primary secret. When the work order
ends, the handle is revoked whether or not the agent finished.

---

## 6. Tool Governance

Adding a tool is a **C2 structural change** ([`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md)):
it expands what NOVA can do in the world and requires James's approval. Changing a tool's
risk class or required rights is **C3 architectural** — it changes the safety envelope.

Tools are versioned; changing a schema is a breaking change for every agent using it.
