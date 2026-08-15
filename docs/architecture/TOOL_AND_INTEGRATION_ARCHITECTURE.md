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
consequence-         which arguments determine WHAT THE ACTION AFFECTS       ← Section 05
determining args     rather than how it is expressed
```

> **`consequence-determining args` — added by Section 05, ACCEPTED by James 2026-08-14.** *(2026-08-14.)*
> **As accepted 2026-08-12 the field list ended at `cost profile`.** Schema validation establishes
> that an argument is **well-formed**; it does not establish that it is **authorized**.
> `recipient: "attacker@example.com"` passes every type check `send_email` declares. Because the
> request pipeline authorizes the plan *before* Tool Selection and Execution
> ([`ORCHESTRATION_ARCHITECTURE.md`](./ORCHESTRATION_ARCHITECTURE.md) §2), argument **values** are
> fixed after the authorization that permits the action — by model output that may have read
> untrusted content.
>
> Section 05 requires each tool to declare which arguments are **consequence-determining** —
> target, scope-bearing identifier, magnitude, destination, irreversibility-bearing selector — so
> the tool enforcement point can check the actual value against the envelope the authorization
> fixed (`I-100`, [`MODEL_TRUST_AND_AUTHORITY.md`](./MODEL_TRUST_AND_AUTHORITY.md) §3).
> **A tool that does not declare them is incomplete and is not registered**, the same treatment
> [`AGENT_ARCHITECTURE.md`](./AGENT_ARCHITECTURE.md) §2 gives an incomplete agent definition.
> Changing the declaration is **C3** — it changes the safety envelope (§6).
>
> Authority: [ADR 0025](../decisions/0025-model-output-is-an-untrusted-derivation.md) and
> [ADR 0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md), both
> **Accepted** 2026-08-14.

**A tool declaring more rights than it uses is a defect**, caught in review and by
permission tests. Over-broad tools are the quiet path to over-broad agents.

**Idempotency is mandatory metadata** because the reliability layer must know whether a
retry is safe. A non-idempotent tool retried automatically is how one client receives four
SMS campaigns.

### 2.1 A declaration is a claim, not a verified fact

> ***PROPOSED — added by Section 10, not yet accepted*** *(2026-08-15; authority
> [ADR 0036](../decisions/0036-tool-declarations-are-claims-not-facts.md), Proposed; removed and the
> accepted text restored verbatim if rejected).* **Every security-relevant field above is declared
> by the tool, and every one of them is an input to authorization** — `required rights` feeds the
> PDP's grant lookup, `risk class` is the floor `I-101` raises from, `idempotency` decides whether
> the reliability layer may retry a side effect, `consequence-determining args` decides what `I-100`
> checks, `cost profile` feeds `I-105`. **The only stated verification is procedural** — the
> "defect, caught in review" line above, plus §6's C2/C3 gate. Review is James reading a
> declaration; permission tests can only exercise **declared** rights.

**Over-declaration and under-declaration are different failures.** A tool declaring *more* than it
needs is **authorized breadth**: James approved it, and `T-16` records it as unmitigable.
**Under-declaration is the opposite** — the tool does more than its declaration says, so the system
acts beyond what was authorized, and James's approval does not help because he approved a claim
about the tool rather than the tool.

**The silent case is the one this closes.** `send_email(to, subject, body, attachments)` declares
`to` and `attachments` consequence-determining and says nothing about `body`. Read as opt-in, `body`
is unchecked — so if the implementation or the provider treats content in `body` as addressing, then
`body` determines what the action affects, `I-100` faithfully checks the wrong fields, and **every
enforcement point passes.** Nobody lied; the declaration was silent, and silence read as harmless.

**Two rules, which together make `I-100` total rather than opt-in:**

```text
TOTALITY      The consequence-determining declaration must classify EVERY argument in the
              tool's input schema as consequence-determining or expressive. An argument
              the declaration does not mention makes the definition incomplete, and an
              incomplete definition is not registered (`MT-6`, unchanged).

DEFAULT       An argument that is present but unclassified, or whose classification cannot
              be parsed, is CONSEQUENCE-DETERMINING and is checked against the envelope
              (`I-100`). Expressive is the exception that must be declared.
```

**Totality reaches every leaf the schema exposes, not only top-level arguments.** A structured
argument — `payload: { to, subject, body }` — classified as one unit hides its parts: declaring the
object expressive would exempt `to` while satisfying a top-level reading. Either every leaf is
classified, or the object is classified **consequence-determining as a whole** and checked as a
whole. **A structured argument cannot be expressive by aggregation.**

**A schema change re-opens the question.** Tools are versioned and a schema change is already a
breaking change (§6). Under totality a newly added argument is unclassified, so the definition is
incomplete and the new version is **not registered** until it is classified — the check cannot be
skipped by growing the schema after approval.

**The same default governs the other claims.** An absent or unparseable `risk class` denies rather
than defaulting low — `I-101` already states this. An absent or unparseable `idempotency` claim
means **not idempotent**, so the reliability layer does not auto-retry. An absent `required rights`
declaration is not an empty requirement; the definition is incomplete.

**This is the repository's default-closed pattern applied to declarations.** `I-14` makes absence of
a grant a denial, `I-52` resolves unavailable classification to the strictest level, `I-79` makes a
missing scope a denial, `I-93` fails an unwritable audit closed. **Absence of information is not
permission** — and the tool declaration was the one place where absence read as *"not
consequential"*.

**No invariant is added.** `I-100` already requires the check and already refuses an undeclaring
tool; this defines what makes the declaration complete, so `I-100` and `MT-6` remain the governing
rules. Changing a classification stays **C3** (§6) — it changes the safety envelope.

**What this does not do.** It does **not** verify a declaration against the tool's actual behaviour.
That requires understanding what the tool does; the only components capable of that judgement are
models, and `I-101`, `I-102` and `I-110` all bar a model from establishing an authorization-relevant
fact. **A tool that declares `body` expressive while its implementation parses `body` for recipients
is not detected** (`T-37`). **And consequence is partly a property of the *binding*, not only the
definition** — the same `send_email` reaches different providers per scope (§1), and provider
behaviour is not in the definition. **Recorded and deliberately not resolved: that belongs to
Section 11.**

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

**Control-plane credentials.** ***Added by Section 05 — ACCEPTED by James 2026-08-14***
*(2026-08-14.)* The rules above govern credentials that reach an external system **on behalf of a
scope**. A **model-provider credential does not**: it authorizes NOVA to talk to a provider, and
authorizes access to **no client scope**. It cannot be per-scope — one provider account serves
every scope permitted to use that provider — so `I-23` read literally would forbid it to exist.

**`I-23` is unamended.** A control-plane credential is not a scope-bound credential and does not
claim to be. It is held **only** by the Model Gateway, is **never bound to a client scope**, is
**never brokered** to an agent, tool, integration, sandbox, or coding agent (`I-22` unaffected),
and lives in the secrets store under every requirement above — expiring, rotatable without code
change, individually revocable (`I-103`). The scope's authorization to reach that provider is
carried by the Context Token and decided at the gateway enforcement point (`I-94`), never by the
credential.

**The class is closed:** a control-plane credential reaches a service acting for **NOVA itself**
rather than for a scope. Adding a member is **C3**. **Two consequences, stated:** revoking one
stops *every* scope reaching that provider at once, and because one credential serves many scopes
the **provider can correlate all of them as one customer** (`T-30`) — not mitigated, not claimed
to be. Authority:
[ADR 0027](../decisions/0027-provider-credentials-are-control-plane-credentials.md) and
[ADR 0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md), both **Accepted** 2026-08-14.

---

## 6. Tool Governance

Adding a tool is a **C2 structural change** ([`IDENTITY_AND_AUTHORITY.md`](./IDENTITY_AND_AUTHORITY.md)):
it expands what NOVA can do in the world and requires James's approval. Changing a tool's
risk class or required rights is **C3 architectural** — it changes the safety envelope.

Tools are versioned; changing a schema is a breaking change for every agent using it.
