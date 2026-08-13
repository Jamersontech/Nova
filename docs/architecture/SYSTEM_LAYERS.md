# System Layers

**Status:** **Active** — Section 02, approved by James 2026-08-12.
**Purpose:** Define what each layer owns, what it must never own, and which layers it may
call. This is the document that keeps responsibilities from bleeding into each other.

---

## 1. The Layer Model

```text
SURFACE            → INTERACTION → CONTEXT → ORCHESTRATION → AGENT RUNTIME
                   → CAPABILITY → INTEGRATION → KNOWLEDGE & DATA → PLATFORM
```

**Calling rule:** a layer may call the layer directly beneath it, and may consult any
cross-cutting spine. It may not reach two layers down, and it may never call upward.
Upward communication happens by returning results or emitting events.

This rule is what prevents, for example, the Interaction layer from calling a tool
directly — which would bypass context resolution and policy entirely.

---

## 2. Layer Responsibilities

### Surface
Devices and channels NOVA is reachable through: desktop, web, mobile, voice, future
surfaces. Owns rendering and input capture. **Owns no logic.** Any behaviour implemented
in a surface must be reimplemented for every other surface — which is why none is.

### Interaction
Turns human expression into structured intent, and structured results back into human
language. Owns conversation state and presentation of what NOVA is doing.
**Does not own:** deciding what to do, or whether it is permitted.

### Context
Resolves which scope a request applies to, holds the Context Lock, and refuses to guess
when interpretations differ materially. **Does not own:** whether access to that scope is
allowed — that is Policy. Context answers *where*, Policy answers *whether*.

### Orchestration
Interprets intent, plans work, dispatches it, verifies results, assembles the answer.
**Does not own:** domain knowledge, credentials, or tool implementations. The orchestrator
coordinates; it does not know how KAIRO invoices work.

### Agent Runtime
Instantiates agents, enforces their declared limits, isolates them from each other,
terminates them. **Does not own:** deciding what work exists, or granting permissions.

### Capability
Tool definitions, input/output schemas, risk classes, and invocation. Every tool call is
checked against the caller's Context Token here. **Does not own:** credentials — it asks
the Credential Broker at call time.

### Integration
Connectors to external systems, plus the Credential Broker. The only layer that holds
outbound secrets, and it holds them for the duration of a call rather than handing them
upward. **Does not own:** business meaning of the data it moves.

### Knowledge & Data
Memory, knowledge, documents, records, and events — scope-partitioned. **Does not own:**
interpretation. Storage does not decide what is true.

**The Data-Access Boundary sits at the entrance to this layer.** ***PROPOSED — added by Section
04, not yet accepted*** *(2026-08-13, N-3). This paragraph is an amendment to accepted Section 02
architecture proposed through [ADR 0017](../decisions/0017-isolation-independent-of-pdp.md),
which remains **Proposed**. It is not approved architecture until James accepts that ADR.*

It is a **trusted platform responsibility and boundary — not a standalone microservice, not a new
speculative subsystem, and not separately deployable.** It establishes an execution's storage
scope binding and opens the scope-bound channel. It owns **the binding**; it does not own **the
decision** — enforcement point 5 below still consults the PDP for every access. Application and
agent code may not open a channel, set a binding, widen one, or re-bind mid-execution
(`I-78`, `I-86`). Full registration:
[`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md) §4.1.

### Platform
Compute, storage, queues, sandboxes, networking, secret storage primitives.
**Does not own:** anything NOVA-specific. This layer is the most replaceable by design.

---

## 3. Why This Differs From the Brief's Layer List

Three deliberate changes, each with a reason:

**"User Experience" → "Surface."** User experience is a property of the entire system, not
a tier within it. Naming a layer "UX" invites the mistake of treating simplicity as
something one layer provides, when in fact an over-complex orchestrator produces a
confusing product no interface can rescue. What genuinely belongs at the top is the set of
*surfaces* NOVA is reachable through.

**Security is not a layer.** The brief lists security concerns among the layers. A layer
implies a single point of transit. Authorization must be enforced at every boundary —
orchestration, agent, tool, credential, and data — so it is modelled as a spine consulted
by all layers rather than a stage passed through once. This is the difference between a
system that checks permission and a system that has permissions.

**"Data / Knowledge" is one layer with several distinct concepts.** Memory, knowledge,
documents, and records live at the same architectural depth but must never be treated as
the same kind of information. They are kept in one layer with strict internal distinctions
rather than split into layers, which would wrongly imply an ordering between them.

The brief's decomposition was close to correct; these are refinements, not a replacement.
If James prefers the original naming, the substance survives a rename — see
[`../decisions/0001-layered-architecture-with-policy-spine.md`](../decisions/0001-layered-architecture-with-policy-spine.md).

---

## 4. Cross-Cutting Spines

Spines are not layers. Any layer may consult any spine; no spine may be bypassed.

| Spine | Consulted for | Enforced at |
| --- | --- | --- |
| Identity & Policy | "Is this identity allowed to do this, here, at this risk?" | Every layer |
| Approval & Control | "Does a human need to say yes first?" | Orchestration, Capability |
| Observability & Audit | "Record what happened and what was believed" | Every layer |
| Cost | "What will this cost, and is there a cheaper adequate option?" | Orchestration, Model Gateway |

---

## 5. Boundary Enforcement Points

Each of these is a place where a Context Token is checked. They are listed here so that a
future implementer knows exactly where enforcement is mandatory:

1. Context → Orchestration: token issued, scope fixed.
2. Orchestration → Agent Runtime: agent receives a *narrowed* token, never a widened one.
3. Agent Runtime → Capability: tool call checked against token scope and risk class.
4. Capability → Integration: credential request checked against token scope.
5. Any layer → Knowledge & Data: read/write checked against token scope partition.

A call that arrives at any of these five without a valid token is denied and recorded.
There is no "internal" call path that skips them.

**Point 5 is evaluated per data access, not per request or session** *(clarified in Section 04,
F-1)*. An execution issuing ten reads is authorized ten times; there is no once-per-request or
once-per-session variant of point 5. Beneath it, the **Data-Access Boundary** holds the scope
binding against which the structural scope restriction of
[ADR 0016](../decisions/0016-isolation-enforced-below-query-layer.md) is applied — **additional
to** point 5, never a replacement for it (`I-77`).

**A token failing integrity detection is not a valid token** at any of the five points above
(`I-87`, `CT-2`). *(Added 2026-08-13, N-6 — proposed through Section 04, pending acceptance of
[ADR 0018](../decisions/0018-authentication-model.md).)*
