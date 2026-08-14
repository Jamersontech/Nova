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
| 04 — Security, Identity & Permissions | **Complete — ADRs `0016`–`0023` Accepted by James 2026-08-13** |
| 05 — AI Architecture & Model Gateway | **PROPOSED, awaiting James's approval** |
| 06 and beyond | Not started |

**"Next" in the table above is descriptive, not a decision.** *(Flagged 2026-08-12, L-4.)* It
records the roadmap's existing numeric order and carries no C3 ordering decision. **Roadmap
ordering remains James's alone** — no agent may reorder, skip, merge, or begin a section on its
own reading of dependencies ([ADR 0008](./decisions/0008-architectural-governance-model.md)).

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

## Section 04 — **Complete: ADRs `0016`–`0023` Accepted by James 2026-08-13**

> **Status heading corrected 2026-08-14.** It read *"PROPOSED, UNDER REVIEW"*, contradicting the
> progress table at the top of this same file. **Everything below this line is the Section 04
> record as written during that section and is left unedited** — including the "Not approved"
> paragraph, which describes the state Section 04 was in when it was written, not the state today.
> No Section 04 architecture is changed by this correction.
>
> **A wider stale-marking sweep is outstanding and is deliberately not done here.** Roughly
> eighteen in-place amendment footnotes across Active documents still describe the Section 04
> amendments as *Proposed, removed if ADR 0022/0023 is rejected*. Those conditions cannot now fire
> — the ADRs are Accepted — but rewriting removal conditions inside Active documents is a larger
> action than correcting a status line, and it is James's call, not an agent's.

**Security, Identity & Permissions.** Produced isolation enforcement, authentication,
secrets, encryption, policy-engine requirements and security operations — plus ADRs
`0016`–`0023` and invariants `I-60`–`I-93`.

**Not approved.** An adversarial review returned APPROVE WITH AMENDMENTS; an amendment pass on
2026-08-12 resolved H-1 to H-4, M-1 to M-6, M-8 and M-9. **M-7 was resolved by James on
2026-08-12** by restoring the original decision ownership.

Resolved **`D-33`** as a precise requirement — enforcement below the query layer, independent
of the PDP — **without selecting a technology**, and resolved the design halves of `D-09`,
`D-10`, `D-34` and `D-35`. **`D-02` remains deferred and untouched.**

**`S4-P9` closed the entire audit-writer surface.** The `S4-P8` inventory found **58 event classes**,
only 20 with a defined writer. [ADR 0023](./decisions/0023-audit-record-writer-authority.md) defines
**three authorities and no others** — `W-1` the execution's own authorization, `W-2` the authorization
decision itself, `W-3` the control-plane operation's authorization into a **control-plane audit
partition outside the client scope tree** — plus fail-closed behaviour when a mandatory record cannot
be written (`I-91`–`I-93`). **`S4-P1` now holds by construction**: no component holds client-scope
write capability for a control-plane record, because control-plane records are not client records.
`I-49` and `E-11` were found **not** to conflict and are unamended. ADR 0023 separately authorizes the
`DATA_ARCHITECTURE.md` and `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` amendments that ADR 0022 does not
cover.

**A sixth decision settled what authorizes audit writes.** `S4-P6` (Option A): audit-write
capability is **authorized by construction** — an already-authorized execution may write audit for
its own bound scope, for its lifetime only. No separate release decision, no grant class, no second
authorization authority, no exemption from `I-18`. This **supersedes the `D` half of `S4-P5`**: with
no release decision there is no recursion to bootstrap. `M-A` was fixed in the same pass — `T-24`'s
containment claim is now explicitly dependent on `D-33` being implemented and verified.

**A fifth decision closed the audit-write bootstrap.** `S4-P5` (Options **C + D**): audit-write
capability is acquired once per execution for that execution's single scope, and the release
decision's own audit record is the first record written under the capability it grants — a bounded
base case. `I-18` is intact, no second authorization authority exists, and `I-82` is **not** the
governing mechanism. `H-1` (Option 3): step-up for cross-scope audit review only. `H-2`: no
`T-27` — `T-20a` covers the compromised audit-reading session.

**James decided four review-raised items on 2026-08-13** — `S4-P1` (audit write is scope-bound;
no blanket cross-scope audit writer), `S4-P2` (James reads audit directly per scope; no
centralized audit reader; Observability does not own or read the audit corpus), `S4-P3` (create
[ADR 0022](./decisions/0022-section-04-amendments-to-accepted-architecture.md) to authorize the
amendments to accepted documents), and `S4-P4` (the approved disqualification set stays at
`C-1`, `C-2`, `C-5`, `C-6`). **Deciding these did not approve Section 04** — see
[`decisions/DEFERRED_DECISIONS.md`](./decisions/DEFERRED_DECISIONS.md).

**Three new decisions were created and approved.** *(Recorded 2026-08-13, N-14.)* `D-33a` (→ 29),
`D-37` (→ 36) and `D-38` (→ 29) were **created during Section 04** and their ownership was
**explicitly approved by James on 2026-08-13**. They are new decisions, not reassignments of
existing ones, and are recorded separately from the M-7 correction so the two are not confused —
see [`decisions/DEFERRED_DECISIONS.md`](./decisions/DEFERRED_DECISIONS.md).

**Section 04 amends nine accepted documents, all marked Proposed in place and all authorized
through [ADR 0022](./decisions/0022-section-04-amendments-to-accepted-architecture.md)** —
`MASTER_ARCHITECTURE.md`, `SYSTEM_LAYERS.md`, `SECURITY_BOUNDARIES.md`,
`PERMISSION_ARCHITECTURE.md`, `RELIABILITY_ARCHITECTURE.md` (Section 02), `INVARIANTS.md`,
`THREAT_MODEL.md`, `AUTHORIZATION_MODEL.md` (Section 03), and `ai/AI_TERMINOLOGY.md` (Section 01).
`DATA_ARCHITECTURE.md` is explicitly **out of scope**. **ADR 0022 is Proposed and no ADR is
accepted**; if it is rejected, every amendment is removed and the accepted text restored verbatim.

**Prior ownership unchanged.** `D-09`, `D-10`, `D-34` and `D-35` remain owned by **Section 04**
(`D-35`: 04 / 38), as originally established. Four unapproved reassignments made during Section
04 were withdrawn by James on 2026-08-12 — see
[`decisions/DEFERRED_DECISIONS.md`](./decisions/DEFERRED_DECISIONS.md). `D-33` follows the
disposition James confirmed separately.

Partially mitigated the `T-19` compromised-PDP risk via [ADR 0017](./decisions/0017-isolation-independent-of-pdp.md):
a compromised PDP alone no longer yields cross-client data. **The independence is from the PDP
only — both mechanisms derive from the Context Token, so compromising the Context service
defeats both (`T-23a`). Reduced in blast radius, not resolved.**

## Section 05 — PROPOSED, awaiting James's approval

**AI Architecture & Model Gateway.** Section 04 was accepted on 2026-08-13, and Section 05 was
begun on 2026-08-14 at James's instruction.
[`architecture/MODEL_ARCHITECTURE.md`](./architecture/MODEL_ARCHITECTURE.md) (Section 02, Active)
fixes the gateway design Section 05 implements and is **extended, not replaced**.

**Delivered — all Proposed:**
[`architecture/MODEL_GATEWAY_ARCHITECTURE.md`](./architecture/MODEL_GATEWAY_ARCHITECTURE.md) (what
may be sent, where, under whose authority) and
[`architecture/MODEL_TRUST_AND_AUTHORITY.md`](./architecture/MODEL_TRUST_AND_AUTHORITY.md) (what
model output may cause), with ADRs `0024`–`0028` and invariants `I-94`–`I-105`.

**The four decisions:** model egress is the **sixth Policy Enforcement Point**
([ADR 0024](./decisions/0024-model-gateway-is-an-enforcement-point.md)) — it was the only path on
which NOVA's data leaves its trust boundary with no enforcement point named, so emergency stop and
revocation did not reach it and failover had no data-policy constraint; **model output is an
untrusted derivation and tool arguments are authorized, not merely validated**
([ADR 0025](./decisions/0025-model-output-is-an-untrusted-derivation.md)) — argument *values* are
fixed after the authorization that permits the action, and schema validity is a type check;
**model verification is corroboration, never evidence**
([ADR 0026](./decisions/0026-model-verification-is-corroboration.md)); and **provider credentials
are control-plane credentials** ([ADR 0027](./decisions/0027-provider-credentials-are-control-plane-credentials.md)),
which leaves `I-23` unamended rather than adding an exception to it.

**Section 05 amends thirteen accepted documents**, all marked Proposed in place and all authorized
through [ADR 0028](./decisions/0028-section-05-amendments-to-accepted-architecture.md). **No ADR is
accepted**; if one is rejected, the amendments it required are removed and the accepted text
restored verbatim. `I-01`–`I-93` are **unmodified**.

**`D-08` is not resolved.** Section 05 fixed the criteria a provider must satisfy (`PR-1`–`PR-9`)
and selected none — the constraints that decide it are `Q-06` and `Q-03`, James's to answer. This
is the posture Section 04 took with `D-09` and `D-10`. `D-20` is partially resolved: routing
**constraints** fixed, thresholds deferred. `D-39` and `D-40` are new.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.
