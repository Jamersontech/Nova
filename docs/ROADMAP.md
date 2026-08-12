# NOVA Master Architecture Roadmap

**Status:** Active — established in Section 01.
**Purpose:** Name the architectural domains NOVA must eventually address, and record
which have been completed.

These are **major architectural domains, not necessarily 46 separate coding sessions.**
Future sections may combine closely related domains when that produces a better
implementation. Sections are not strictly sequential; dependencies matter more than
numbering.

> **Who may exercise that latitude (added in Section 02).** Combining, resequencing, or
> redefining sections is a **C3 architectural change — James's decision alone**. The
> paragraph above describes James's latitude, not an agent's. A coding agent reads this
> roadmap to determine which section owns its work, and stops when the work belongs
> elsewhere. See [`architecture/IDENTITY_AND_AUTHORITY.md`](./architecture/IDENTITY_AND_AUTHORITY.md)
> Part II and [ADR 0008](./decisions/0008-architectural-governance-model.md).

Do not add sections merely to enlarge the roadmap. The roadmap changes only when a
genuine architectural requirement or a discovered problem justifies the change.

---

## Progress

| Section | Status |
| --- | --- |
| 01 — Constitution & Project Foundation | **Complete** |
| 02 — System Architecture & Master Blueprint | **Complete — architecture Accepted by James 2026-08-12** |
| 03 — Data, Scope, Identity & Memory Architecture | **Complete — Accepted by James 2026-08-12 (as amended)** |
| 04 — Security, Identity & Permissions | **Complete — Proposed, pending approval** |
| 05 — AI Architecture & Model Gateway | Next |
| 06 and beyond | Not started |

**No sections have been added, removed, renumbered, or redefined.** All 46 domains stand as
established in Section 01. Section 03's delivered scope was broader than its roadmap title
("Data Architecture & Information Model") — it also covered scope, identity, and memory at
James's instruction. The roadmap title is unchanged; only the record below notes the
difference.

---

## Roadmap

### Foundation
```text
01 — Constitution & Project Foundation
02 — System Architecture & Master Blueprint
03 — Data Architecture & Information Model
04 — Security, Identity & Permissions
```

### Intelligence
```text
05 — AI Architecture & Model Gateway
06 — Agent Architecture & Agent Governance
07 — Context & Memory Architecture
08 — Reasoning, Planning & Orchestration
09 — Knowledge & Research System
```

### Capability
```text
10 — Tool & Capability Architecture
11 — Integration Architecture
12 — Automation & Workflow Engine
13 — Communication System
14 — Voice & Conversational Interface
```

### Experience
```text
15 — NOVA Design System
16 — UX & Information Architecture
17 — Desktop / Mobile / Responsive Architecture
18 — Personal Command Center
```

### Domains
```text
19 — Life Architecture
20 — Business Architecture
21 — KAIRO Architecture
22 — Client & Environment Architecture
23 — Wealth Architecture
```

### Operations
```text
24 — Task & Project Management
25 — Notification & Interruption System
26 — Approval & Human-Control System
27 — Activity, Audit & Observability
28 — Monitoring & Health
```

### Engineering
```text
29 — Application Infrastructure
30 — Development Environment & Coding-Agent Architecture
31 — Testing & AI Evaluation
32 — Versioning & Change Management
33 — Performance & Scalability
34 — Cost & Resource Management
```

### Resilience
```text
35 — Reliability & Failure Recovery
36 — Backup & Disaster Recovery
37 — Privacy & Data Governance
38 — Security Hardening & Threat Modeling
```

### Safety & Quality
```text
39 — AI Safety & Action Governance
40 — AI Quality Control
41 — Agent Evaluation & Continuous Improvement
42 — NOVA Self-Improvement Architecture
```

### Maturity
```text
43 — Admin / Architect Control Center
44 — Data Portability & Vendor Independence
45 — Production Launch Architecture
46 — Long-Term Evolution Framework
```

---

## Section 01 — Completed

Established the constitution, domain model, canonical AI terminology, agent principles,
development rules, change management, design principles, decision-record practice, and
coding-agent governance. No application code, infrastructure, dependencies, or technology
commitments were created.

## Section 02 — Completed

**System Architecture & Master Blueprint.** Produced [`architecture/`](./architecture/README.md):
the scope tree, context tokens, system layers, and the agent, orchestration, execution,
data, permission, memory, tool, model, event, reliability, interface, scale, and testing
architectures — plus ADRs `0001`–`0008` recording the reasoning.

Resolved the Section 01 audit findings M-1 (LIFE), M-2 (multi-business), M-3 (identity), and
M-4 (roadmap authority). **No technology was selected** — every technology decision in
[`decisions/DEFERRED_DECISIONS.md`](./decisions/DEFERRED_DECISIONS.md) remains open by
intent.

## Section 03 — Completed

**Data, Scope, Identity & Memory Architecture.** Produced the scope and identity model,
authorization model, memory model, data classification, provenance and trust, data lifecycle,
cross-scope and cross-domain rules, fifty testable invariants, and a threat model — plus ADRs
`0009`–`0015`.

Accepted by James on 2026-08-12 following an adversarial review that produced nine
amendments — narrowed credential guarantees, the compromised-PDP risk (T-19), deletion
limits and the tombstone-restore requirement, fail-closed subsystem behaviour, aggregation
and differencing restrictions, `[PHYS]` invariant dependencies, memory quarantine and
revalidation, executable scope-kind validation, and Work Order provenance. **The documented
residual risks were explicitly accepted, not resolved.**

**Technology was deliberately not selected.** James confirmed on 2026-08-12 that **`D-02`
remains deferred** (no database or other technology to be selected; owner 29) and that
**`D-33` is a Section 04 security decision** concerning enforcement below the query layer —
see [`decisions/DEFERRED_DECISIONS.md`](./decisions/DEFERRED_DECISIONS.md).

## Section 04 — Next

**Security, Identity & Permissions.** Produced isolation enforcement, authentication,
secrets, encryption, policy-engine requirements and security operations — plus ADRs
`0016`–`0021` and invariants `I-60`–`I-76`.

Resolved **`D-33`** as a precise requirement — enforcement below the query layer, independent
of the PDP — **without selecting a technology**, and resolved the design halves of `D-09`,
`D-10`, `D-34` and `D-35`. **`D-02` remains deferred and untouched.** Every product choice was
pushed to Section 29 or 38 as `D-09a`, `D-10a`, `D-33a`, `D-34a`, `D-35a`.

Partially mitigated the `T-19` compromised-PDP risk via [ADR 0017](./decisions/0017-isolation-independent-of-pdp.md):
cross-client access now requires two independent mechanisms to fail. **Reduced in blast
radius, not resolved.**

## Section 05 — Next

**AI Architecture & Model Gateway.** Not started. `D-08` (providers and models) is its to
decide; [`architecture/MODEL_ARCHITECTURE.md`](./architecture/MODEL_ARCHITECTURE.md) fixes the
gateway design it implements.
