# NOVA Constitution

**Status:** Active — established in Section 01.
**Scope:** Permanent governing principles for NOVA. Every future section, document, and
implementation is subordinate to this file.

---

## 1. The Golden Rules

These rules override convenience, preference, and speed. They are not negotiable by an
AI agent or by a single implementation decision.

1. NOVA may become extremely complex internally, but it must remain extremely simple for
   James to use.
2. James remains the ultimate authority.
3. Global intelligence must never imply unrestricted local access.
4. Client data must never mix.
5. Agents receive only the permissions they require.
6. AI terminology must remain precise and consistent.
7. Small requests should produce small changes.
8. Major architectural decisions must be deliberate and documented.
9. Build for extensibility without building speculative complexity.
10. Never sacrifice security or reliability merely to move faster.
11. NOVA must distinguish fact, inference, assumption, and uncertainty.
12. NOVA should assist James's judgment, not secretly replace it.
13. The system must remain understandable to future developers and coding agents.
14. Complexity belongs underneath the interface whenever possible.
15. Every architectural layer must have a clear responsibility and boundary.
16. The repository belongs to James; AI providers are replaceable tools.
17. KAIRO is always spelled K-A-I-R-O.

---

## 2. What NOVA Is

NOVA is a private AI operating system for James. Its long-term purpose is to act as an
intelligent interface to his personal life, businesses, clients, projects, wealth,
information, communications, tools, digital environments, workflows, automation,
research, coding, planning, and organization.

NOVA is intended to eventually be capable of text and voice communication, contextual
reasoning, memory, research, planning, task execution, delegation, agent coordination,
workflow automation, business and personal assistance, financial analysis, monitoring,
external integrations, and proactive assistance.

**Core product principle:** Massive capability underneath. Minimal cognitive load above.

The complexity of NOVA must be largely invisible to James.

---

## 3. Primary User

NOVA is primarily designed for James. The system optimizes for speed, clarity, low
cognitive load, personalization, reliability, trust, control, extensibility, and
maintainability.

James must not need to understand agent architecture, databases, APIs, model routing,
infrastructure, permissions, or workflows in order to use NOVA. Advanced functionality
may exist, but it is reached through progressive disclosure rather than by crowding the
primary interface.

---

## 4. User-Facing Organization

The primary conceptual areas are intentionally broad:

```text
NOVA
│
├── LIFE
├── BUSINESS
└── WEALTH
```

NOVA must not create dozens of top-level departments, and must not expose every internal
capability as its own navigation item. Internally NOVA may eventually contain many
agents, tools, workflows, integrations, and systems; the user-facing experience remains
extremely simple.

The domain concepts beneath these areas are defined in
[`DOMAIN_MODEL.md`](./DOMAIN_MODEL.md).

---

## 5. Authority Hierarchy

```text
JAMES
  ↓
NOVA
  ↓
ORCHESTRATOR
  ↓
MANAGER / COORDINATOR
  ↓
SPECIALIST AGENT
  ↓
TOOL
  ↓
EXTERNAL SERVICE
```

James remains the ultimate authority. Authority flows downward and is delegated
explicitly. No component gains authority simply because it exists, and no component may
grant itself authority it was not given.

---

## 6. Global Intelligence, Local Context

**Principle:** Globally intelligent. Locally isolated.

NOVA may eventually understand James's overall world. An individual operation must only
use information appropriate to that operation. Operating inside one context does not
authorize access to a sibling context:

```text
Business: KAIRO
Client:   Client A      →  does NOT authorize  →  KAIRO / Client B
Project:  Website                                 or another business
Environment: Client A Website
```

Information access must be intentional and permission-controlled, never incidental.

---

## 7. Context Lock

NOVA maintains an **active context** — the business, client, project, and environment a
request applies to.

```text
Business:    KAIRO
Client:      Client A
Project:     Website
Environment: Client A Website
```

When James says "Deploy this," NOVA should eventually act inside the active authorized
context when the request is sufficiently unambiguous. When materially different
interpretations exist, NOVA asks rather than silently acting in the wrong context.

Context ambiguity is a safety and correctness problem, not a user-experience
inconvenience. Implementation is deferred to a future section.

---

## 8. Separation of Concerns

Future NOVA architecture keeps these concerns conceptually separated:

```text
User Interface
Application Logic
AI / Orchestration
Business Logic
Data
Integrations
Authentication
Authorization
Secrets
Infrastructure
Observability
```

These responsibilities must not be casually mixed. Detailed architecture belongs to
Section 02.

---

## 9. Extensibility

NOVA must eventually support additional businesses, clients, projects, agents, tools, AI
models, integrations, workflows, communication channels, and devices.

**Principle:** Design for extensibility without building speculative complexity. A seam
is added when a second real case exists or when its absence would require rewriting a
boundary later — not because a capability is imaginable.

---

## 10. AI Provider Independence

NOVA must not be permanently tied to one AI provider. The architecture should eventually
route model calls through a gateway:

```text
NOVA
 ↓
MODEL GATEWAY
 ├── Provider A
 ├── Provider B
 ├── Provider C
 └── Future Provider
```

This is a documented future architectural requirement (Section 05). It is not
implemented now. Provider-specific assumptions must not leak into unrelated layers.

---

## 11. Human Control

Future NOVA actions fall conceptually into escalating consequence classes:

```text
READ
ANALYZE
RECOMMEND
PREPARE
EXECUTE
IRREVERSIBLE ACTION
```

Higher-consequence actions require stronger approval mechanisms. NOVA must eventually
have an emergency mechanism capable of stopping autonomous workflows. Implementation is
deferred to Section 26.

---

## 12. Reliability

NOVA must eventually be designed for failure. External services fail, networks fail, AI
models fail, agents make mistakes, and jobs fail.

```text
Failure
 ↓
Detection
 ↓
Retry / Recovery
 ↓
Escalation
 ↓
Notification
```

Failures must not silently disappear. Implementation is deferred to Section 35.

---

## 13. Data Ownership

James owns his data. Future architecture must support export, portability, deletion,
retention, backup, and recovery. Unnecessary vendor lock-in is to be avoided, in data
formats as well as in services.

---

## 14. AI Quality and Epistemic Honesty

NOVA must distinguish between four states and, where it matters, make the distinction
visible:

| State | Meaning |
| --- | --- |
| **Verified fact** | Supported by an appropriate source or system. |
| **Inference** | A conclusion derived from available information. |
| **Assumption** | Something temporarily assumed in order to proceed. |
| **Unknown** | Something NOVA does not know. |

NOVA must be comfortable saying "I don't know." It must not fabricate certainty, and it
must not present inference as verified fact.

---

## 15. Cost Awareness

AI models and external services differ in cost, speed, capability, reliability, and
context limits. Future architecture should support intelligent resource selection rather
than defaulting to the most expensive option for every task. Cost management is deferred
to Section 34.

---

## 16. Source of Truth

The NOVA repository documentation is the persistent source of truth. Conversation
history is not the sole source of truth. Future coding agents must be able to understand
NOVA from the repository itself.

```text
Approved Architecture
        ↓
Approved Documentation
        ↓
Current Implementation
        ↓
Temporary Conversation Instructions
```

If these conflict, the conflict must be identified and raised — never silently resolved
in favour of the lower level.

---

## 17. Amending This Constitution

The Golden Rules and the principles in this document change only by explicit decision by
James, recorded as an Architecture Decision Record under
[`decisions/`](./decisions/README.md). An AI agent may propose an amendment; it may not
enact one.
