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
| 05 — AI Architecture & Model Gateway | **Complete — ADRs `0024`–`0028` Accepted by James 2026-08-14** |
| 06 — Agent Architecture & Agent Governance | **Complete — ADRs `0029`–`0031` Accepted by James 2026-08-14** |
| 07 — Context & Memory Architecture | **PROPOSED, awaiting James's approval** |
| 08 — Reasoning, Planning & Orchestration | **PROPOSED, awaiting James's approval** |
| 09 — Knowledge & Research System | **PROPOSED, awaiting James's approval** |
| 10 — Tool & Capability Architecture | **PROPOSED, awaiting James's approval** |
| 11 — Integration Architecture | **PROPOSED, awaiting James's approval — `S11-D1` approved for implementation 2026-08-15, folded into ADR `0037`** |
| 12 — Automation & Workflow Engine | **PROPOSED, awaiting James's approval** |
| 13 — Communication System | **PROPOSED, awaiting James's approval** |
| 14 and beyond | Not started |

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

## Section 13 — PROPOSED, awaiting James's approval

**Communication System.** **No new invariant, no new enforcement point, no new PEP, no new security
object.** One new document, justified below.

**Delivered — all Proposed:** ADR `0039`, `COMMUNICATION_ARCHITECTURE.md`, threat `T-41`.
**`INVARIANTS.md` is untouched:** `I-01`–`I-114` are byte-identical.

**Most of the surface was already governed, and the vocabulary census proved it** rather than
assuming it. Recipient identity and recipient-list size are already consequence-determining
(`MT-5`'s *Target* and *Magnitude* rows), and `I-100`'s worked example is literally
`recipients ⊆ client-a's contacts, ≤ 1 message`. The sending account is the **execution binding**
(`I-114`) — communication is that invariant's first major consumer and needs nothing added.
Inbound replies and delivery receipts are ADR 0037's `S11-D3` and `S11-D2`. Rate is **PDP step 8**.
Bulk is magnitude. A scheduled campaign is an automation — intent, not authority (Section 12).
**A conversation is explicitly not a context**, so thread continuation grants nothing.

**Four terms returned zero occurrences repository-wide:** *sender*, *reply*, *bounce / read
receipt*, and *unsubscribe / opt-out*. Three were governed under other names. The fourth is real.

**The finding — `S13-D1`.** **Communication is the second egress path out of the trust boundary,
and only the first was given an enforcement story.** `DATA_CLASSIFICATION.md` §2's *"Transmitted
externally"* row has been normative since Section 03 — CLIENT-CONFIDENTIAL *to that client only*,
SENSITIVE-PERSONAL and SECURITY-CRITICAL **never** — and **no document named where it is
enforced**. Section 05 gave the model path `I-94`/`I-96` at a new Model Gateway PEP. The
communication path needed **no new machinery** and had simply never been composed: `I-99` makes a
model-composed body a derivation whether or not it is stored, `I-27` gives it the **strictest
classification among its sources**, §2 governs that classification, and **PDP step 7** asks exactly
that question at the **Tool call PEP** — one of the six that already exist.

**Why it was easy to miss.** `MT-5` classes wording and summary text as **expressive — not bound**,
which is *correct* for the argument envelope. An implementer reading `I-100` sees the recipient
checked and the body unchecked and concludes the body needs no gate. It needs a different gate,
answering a different question: *"is this argument authorized?"* and *"may this classification
leave?"* are both live, and the first does not answer the second.

**Deliberately deferred with the reason stated:** consent and opt-out. The **mechanism** is not
missing — a suppression set narrows the recipient envelope `MT-8` already fixes. The **policy** is,
and consent is a property of *a person* while the authorization model is scope-shaped throughout.
**Section 37 (Privacy & Data Governance)**, on the same reasoning that sent Section 09's
aggregate-sensitivity finding there. Until it exists NOVA has no suppression check — recorded, not
mitigated.

**A new document was created, against the default.** The surface spans five accepted documents —
classification, tool/binding, reliability, provenance, events — and **none of them owned
"communication."** A reader asking *"is this message authorized?"* had nowhere single to look,
which is precisely how a classification rule sat unenforced. `COMMUNICATION_ARCHITECTURE.md`
**adds no rule of its own**; every statement cites the accepted rule and its enforcement point.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 12 — PROPOSED, awaiting James's approval

**Automation & Workflow Engine.** **No new architecture document and no new invariant.** The
workflow engine already lives in `ORCHESTRATION_ARCHITECTURE.md` §4, and the automation model
belongs beside it as §5.

**Delivered — all Proposed:** ADR `0038`, threat `T-40`. **`INVARIANTS.md` is untouched:**
`I-01`–`I-114` are byte-identical to their current text.

**The baseline was denser than the section title suggests.** Durable resumable workflows,
step-level state, pause/resume/cancel, partial completion as a first-class outcome, retry
discipline, per-step narrowed tokens, resumption re-checking `I-109` against current state,
per-attempt binding re-checks (`I-114`), `V-2` revocation and `X-1`/`X-3`/`X-7` stop semantics all
already existed. **Section 12 found no missing mechanism.**

**What was missing was a definition.** The word *"workflow"* was defined and *"a routine is a
recurring Workflow"* appeared once — but **nothing said what a stored definition plus a trigger
carries across time.** The industry default answer is that the definition is authorized when
saved and the scheduler runs it thereafter, and that reading is **the single largest available
loophole around Sections 01–11**: it turns every control into a one-time check.

**The decision — `S12-D1`, and it is a derivation rather than new policy.** An automation is
**intent, not authority**. Every firing is authorized freshly at fire time through the unmodified
§2 pipeline; nothing carries authorization forward — not the definition, not the trigger, not the
schedule, not a previous firing, not a previous approval. Every clause is forced by an existing
rule: `I-14` (a definition is not a grant), `I-113` (same objective never inherits), `I-112`
(fresh plan identity), `PERMISSION_ARCHITECTURE.md` §5 (an approval is never a precedent), `I-17`
(no caching beyond one context lifetime), `S11-D3` (a signal carries no identity), `V-2`/`X-1`.

**Three questions the brief raised that the repository had already answered.** *Who acts when
James is absent?* — the **NOVA system identity**, defined in `IDENTITY_AND_AUTHORITY.md` §2 for
*"scheduled and autonomous work"*, ceiling = James's delegation minus anything needing human
approval. *How does unattended work exceed the autonomous ceiling?* — a **standing approval**,
already *"recorded as grants"*, bounded by scope, risk ceiling, expiry and rate limit, revocable;
`IRREVERSIBLE` never. *What is re-checked on resume?* — `I-109` against current state, fail closed.
**None of these needed inventing; they needed connecting.**

**The definition is deliberately not made a security object.** Agent and tool definitions, plans
and bindings are, because each **fixes authority**. An automation definition fixes none — the
authority a firing exercises lives in James's grants, standing approvals, agent definitions, tool
declarations and bindings, each already governed. Governing the definition would add a second,
redundant control surface and imply it carries something worth governing. What bounds automation
creation is the **closed capability surface**: an agent can create one only if that capability is
on its tool list, granted C3.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 11 — PROPOSED, awaiting James's approval

**Integration Architecture.** **The roadmap title is unchanged.** The brief framed this work as
*"Binding-Dependent Tool Consequences / Tool Execution & Integration Behavior"*, which describes
the work done inside the section; renaming a section is C3 and was not done.

**No new architecture document; one new invariant (`I-114`), created on James's explicit
approval.** `TOOL_AND_INTEGRATION_ARCHITECTURE.md` already owns integrations and providers, and
`RELIABILITY_ARCHITECTURE.md` already owns outcomes and retries.

**Delivered — all Proposed:** ADR `0037` (carrying `S11-D1`–`S11-D3`), invariant `I-114`, the
in-place `I-109` amendment, threats `T-38`–`T-39`. `I-01`–`I-108` and `I-110`–`I-113` are
byte-identical to their accepted text.

**Section 10 handed forward one hypothesis, and it survived attack — but it split into three.**
Tracing plan → action → tool → binding → credential → provider → request → side effect →
response → verification → audit produced three independent families, not one:

**`S11-D2` — a provider's outcome is a claim, not a verified fact.** *"The tool was authorized"*
and *"the provider did exactly what NOVA authorized"* are different propositions, and every
downstream decision — resumption from *"the last verified step"*, compensation, what James is told
completed — read a value the provider supplied, with nothing saying what it was worth. **Unknown is
now a distinct outcome from failure**, because collapsing them is what produces duplicate side
effects; and **idempotency is declared by NOVA but enforced by the provider**, so automatic retry
requires the provider actually to deduplicate, not merely a tool that declares it does. Also
recorded: a failure response does not mean nothing happened — a request may be **partially
executed**.

**`S11-D3` — provider-initiated inbound signals carry no authority.** *"Webhook"* and *"callback"*
appeared **nowhere in the repository**, yet the path was already in the accepted architecture:
`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` §2 names integrations as event **sources** and workflows
waiting on a condition as **consumers**. So an external party could already place a signal NOVA
waits on. The answer comes entirely from existing rules — an external system *"never authenticates
into NOVA"*, so no identity, no token, no grant, and `I-14` denies by default. **This was the same
completeness defect Section 05 found when model egress was missing from the boundary table, in the
opposite direction.**

**`S11-D1` — stopped for James, approved 2026-08-15, then implemented.** The authorization
envelope was expressed in **tool** terms while the consequence is produced by the **binding**: a
tool is defined once at root, and integrations, credentials and providers are per scope. `I-109`
excluded provider on a rationale — *"already decided per call by `I-94`/`I-97`"* — true for model
calls, with no analogue for tools. On James's approval, **`I-114`** binds a consequence-producing
tool action to its **execution binding** (tool identity and version · integration · credential
binding): resolved **before** the decision and an input to it, checked as an **envelope** at the
tool PEP and at the Credential Broker's new **step 2a**, re-resolved and re-checked on **every**
retry, resumption and failover, with **no substitution and no provider equivalence** — an
unavailable sole binding fails closed. Integration identity is **consequence-bearing**: repointing
provider, account/tenant, endpoint or declared API version is a **different binding**, C3,
invalidating authorizations that named the old one. **`I-109` is amended in place**, scoping its
exclusion list: model calls keep the per-call exclusion; tool actions bind the execution binding as
a **tenth** property. Threat `T-39` records what remains: `I-114` controls **NOVA's choice of
substrate**, not provider behaviour behind a stable identity.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 10 — PROPOSED, awaiting James's approval

**Tool & Capability Architecture.** **No new architecture document and no new invariant.**
`TOOL_AND_INTEGRATION_ARCHITECTURE.md` already owns tools, integrations, credentials and tool
governance, and the finding is a definition of a field that document already requires — the same
shape as Section 09's, and the reason it lands in §2.1 rather than in a new file.

**Delivered — all Proposed:** ADR `0036`, threat `T-37`. **`INVARIANTS.md` is untouched:**
`I-01`–`I-113` are byte-identical to their accepted text.

**The core finding.** **Every security-relevant property of a tool is declared by the tool, and
every one of them is an input to authorization** — `required rights` feeds the PDP's grant lookup,
`risk class` is the floor `I-101` raises from, `idempotency` decides whether the reliability layer
may retry a side effect, `consequence-determining args` decides what `I-100` checks, `cost profile`
feeds `I-105`. The only stated verification was procedural: *"a defect, caught in review and by
permission tests"* — but permission tests can only exercise **declared** rights, and review is James
reading a declaration rather than observing behaviour.

**Over-declaration was already handled; under-declaration was not.** A tool declaring more than it
needs is authorized breadth — James approved it, and `T-16` records it as unmitigable. A tool
declaring *less* than it does makes the system act beyond what was authorized, and approval does not
help because James approved a claim about the tool rather than the tool. **The silent case is the
sharp one:** an argument the declaration simply does not mention was read as harmless, so `I-100`
faithfully checked the wrong fields and every enforcement point passed.

**The decision.** The declaration is **total** — every schema argument must be classified, and
`MT-6` already refuses an incomplete definition — and the **default inverts** from expressive to
consequence-determining. That is `I-14`/`I-52`/`I-79`/`I-93`'s default-closed pattern applied to
declarations: **absence of information is not permission.**

**The honest limit.** This closes the *silent* under-declaration and not the *wrong* one. Validating
a declaration against behaviour requires semantic understanding of the tool; the only available
source is a model, and `I-101`, `I-102` and `I-110` bar exactly that — building a verifier would
introduce the trust dependency the architecture is organised to avoid. Recorded as `T-37`.

**One earlier defect corrected.** `TOOL_AND_INTEGRATION_ARCHITECTURE.md` §2's Section 05 amendment
note was headed *"ACCEPTED"* while still closing *"both Proposed… restored if they are rejected"* — a
stale marking left by the Section 05 acceptance pass, corrected here because Section 10 amends that
exact block. **No text changed meaning; only the status label.**

**Deferred to Section 11.** Consequence is partly a property of the **binding**, not the definition:
one `send_email` reaches a different provider per scope, and provider behaviour is not in the tool
definition. Recorded, deliberately not decided.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 09 — PROPOSED, awaiting James's approval

**Knowledge & Research System.** **The least greenfield section so far, and deliberately the
smallest.** Discovery found the research *domain* barely named — `citation` appeared once,
`synthesis` and `freshness` not at all — while the research *security machinery* was almost entirely
built by Sections 03, 05, 07 and 08. Repetition-as-corroboration, model-asserted verification,
model summaries posing as sources, claim-specific source authority, stale-but-authoritative
sources, injection expanding a research plan, and cross-scope research were **each already blocked
by an existing invariant**, most of them named explicitly in `I-110`.

**One genuine decision: `S9-D1` — source identity.** `PROVENANCE_AND_TRUST.md` §2 has required
*"source identity"* since Section 03, and `I-110` requires a source to be **identifiable** and
**reproducibly checkable** — but nothing defined what identifies a source, so `I-110` was not
implementable. A source is now identified by the **observation** NOVA made of it: **source
identifier · content digest · `retrieved_at`** (§2.1).

**No new invariant and no new ADR.** `I-110` remains the governing security invariant and becomes
implementable; the definition is folded into
[ADR 0033](./decisions/0033-section-07-amendments-to-accepted-architecture.md) §2a, which already
amends the exact section and owns the same decision family. **No new architecture document.**

**Two findings recorded rather than resolved:** an aggregate of individually PUBLIC sources can be
sensitive while `I-27` keeps it PUBLIC — **Section 37's**, not Section 09's; and promoting a
synthesis promotes every claim inside it, which is a residual rather than an open decision.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 08 — PROPOSED, awaiting James's approval

**Reasoning, Planning & Orchestration.** **No new architecture document was created.**
`ORCHESTRATION_ARCHITECTURE.md` already owns the Planner, the pipeline, the orchestrator contract
and the workflow engine, and the plan belongs to exactly those sections — splitting it out would
separate the plan from the pipeline that produces and consumes it. Rationale recorded in
[ADR 0035](./decisions/0035-section-08-amendments-to-accepted-architecture.md).

**Delivered — all Proposed:** ADRs `0034`–`0035`, invariants `I-112`–`I-113`, threat `T-36`.

**The core finding.** The plan was treated as the unit of authorization by four accepted documents
and **defined by none of them** — the only enumeration was `ORCHESTRATION_ARCHITECTURE.md:31`'s
*"A plan: steps, dependencies, required rights"*. No record, identity, version, immutability rule,
lifecycle, taint carrier, or re-authorization rule. **Every other security object in NOVA has a
schema**; the plan did not. So `I-40`'s rule that untrusted content may not escalate a plan had
nothing to attach to, `I-109` had nothing to bind to, and nothing detected a plan changing between
authorization and execution. **Sections 05 and 07 built taint carefully and delivered it to a
boundary with no receiver.**

**Authorization granularity was also contradictory** across `ORCHESTRATION_ARCHITECTURE.md` §2
(*"the full plan is authorized as a unit"*), `AUTHORIZATION_MODEL.md` §1/§3 (ten singular steps),
`PERMISSION_ARCHITECTURE.md` §5 (*"one action, in one context, at one time"*) and
`EXECUTION_ARCHITECTURE.md` §2.1 (*"James approves the plan"*).

**Three decisions.** The plan is a **security object** with deterministic identity reusing `I-93`'s
construction, immutable after authorization (`I-112`). Authorization is an **envelope plus a
per-action check** — the third application of the `MT-8`/`I-106` pattern — which reconciles all four
documents **without modifying the PDP** (`I-113`). **Re-planning creates a new plan** and never
inherits authorization; **resumption re-checks the binding** and fails closed.

**Section 08 amends seven accepted documents**, all marked Proposed in place and authorized through
[ADR 0035](./decisions/0035-section-08-amendments-to-accepted-architecture.md). **No ADR is
accepted.** `I-01`–`I-111` are **unmodified**.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 07 — PROPOSED, awaiting James's approval

**Context & Memory Architecture.** Discovery found context and memory **already densely specified**
across five Active documents — `CONTEXT_ARCHITECTURE.md`, `MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`,
`MEMORY_MODEL.md`, `DATA_LIFECYCLE.md`, `PROVENANCE_AND_TRUST.md`. **Section 07 is not a greenfield
section, and no new architecture document was created.** `CONTEXT_ARCHITECTURE.md` needed **no
amendment at all**: it already answers every context question Section 07 raised.

**Delivered — all Proposed:** ADRs `0032`–`0033`, invariants `I-110`–`I-111`, threat `T-35`.

**The critical finding.** `I-39` gates fact status on *provenance **and** trust*. Provenance is
immutable (`I-38`), classification-lowering is owned (`I-30`), approval and grants are James's
(`I-09`, `I-10`), and a model check cannot promote epistemic status (`I-102`) — **but trust was the
one axis in that gate with no authority attached.** `PROVENANCE_AND_TRUST.md` said trust *"may
change"*; `MEMORY_MODEL.md` said revalidation *"promotes it"*; `system.verified` was defined as
*"NOVA checked it against an authoritative source"* with **neither term defined anywhere in the
repository**. An unowned promotion converted contained untrusted content into apparent fact
**without violating any invariant**. `I-110` closes it, and defines *authoritative source*.

**Four supporting decisions:** `model.generated` joins the existing quarantine set; delegate memory
carries its delegation ancestry and **survival is not authority**; `I-99`'s union provenance and
lowest trust **survive persistence and are restored at retrieval** (`I-111`) — which is what
`I-100`'s tool-argument ceiling actually depends on; and retrieval **surfaces** a revoked creating
authority without automatically re-weighting it.

**Section 07 amends eight accepted documents**, all marked Proposed in place and authorized through
[ADR 0033](./decisions/0033-section-07-amendments-to-accepted-architecture.md). **No ADR is
accepted.** `I-01`–`I-109` are **unmodified**. `D-24`/`D-24a` remain deferred — retrieval mechanics,
decay algorithms and storage depend on `D-02`/`D-06`, and confidence-horizon **durations** are
values, not security decisions.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 06 — **Complete: ADRs `0029`–`0031` Accepted by James 2026-08-14**

**Agent Architecture & Agent Governance.** Section 05 was accepted on 2026-08-14 and Section 06
begun the same day at James's instruction. `AGENT_ARCHITECTURE.md` (Section 02) and
`ai/AGENT_PRINCIPLES.md` (Section 01) fix what an agent *is* and are **extended, not replaced**.

**Delivered — all Proposed:** [`architecture/AGENT_GOVERNANCE.md`](./architecture/AGENT_GOVERNANCE.md),
ADRs `0029`–`0031`, invariants `I-106`–`I-109`, threats `T-33`–`T-34`.

**Six decisions, approved and accepted by James on 2026-08-14.** Token
issuance is verified by the Context service, the sole issuer — **the runtime requests narrowing and
never mints** (`I-106`), which is where `I-07`'s intersection stops being asserted. Delegation is
**strictly narrowing, acyclic, and explicitly re-delegable** with `may_redelegate` defaulting to
false (`I-107`) — no numeric depth or fan-out limits, because strict narrowing bounds depth
structurally. The **cost ceiling belongs to the root execution and is shared by the whole
delegation tree** (`I-108`), closing a capacity-minting gap **Section 05 introduced**. Agent
lifecycle operations are classified under the **existing** C1/C2/C3 model — no new class. An
approval binds **nine effective-authorization properties** (`I-109`). A child never outlives its
granting execution identity.

**Three corrections of accepted text**, called out in
[ADR 0031](./decisions/0031-section-06-amendments-to-accepted-architecture.md): `AGENT_ARCHITECTURE.md`
said the *runtime* issues tokens (impossible under `I-87`); `SCOPE_AND_IDENTITY_MODEL.md` §5
conditioned re-delegation on a field the record lacked; `THREAT_MODEL.md` T-24 answered the
runtime-compromise row circularly.

**One honest correction to Section 01 material:** `AGENT_PRINCIPLES.md` §4's *"enforced by design"*
claim covers five of seven prohibitions, six as of Section 06 — **prohibition 6 is not mechanically
enforced and NOVA has no component that could enforce it.** The overclaim is corrected, not
defended.

**Section 06 amends thirteen accepted documents**, all authorized through
[ADR 0031](./decisions/0031-section-06-amendments-to-accepted-architecture.md) and all **accepted
with it on 2026-08-14**; their in-place Proposed markings were cleared at acceptance, so no stale
removal condition is left behind. `I-01`–`I-105` are **unmodified**. `D-25a` remains deferred,
blocked on `D-01`/`D-04`; `D-25` was not reopened. Changing any Section 06 decision now requires a
superseding ADR, not an edit.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.

## Section 05 — **Complete: ADRs `0024`–`0028` Accepted by James 2026-08-14**

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

**Section 05 amends thirteen accepted documents**, all authorized through
[ADR 0028](./decisions/0028-section-05-amendments-to-accepted-architecture.md) and all **accepted
with it on 2026-08-14**; their in-place Proposed markings were cleared at acceptance, so no stale
removal condition is left behind. `I-01`–`I-93` are **unmodified**. Changing any Section 05
decision now requires a superseding ADR, not an edit.

**`D-08` is not resolved.** Section 05 fixed the criteria a provider must satisfy (`PR-1`–`PR-9`)
and selected none — the constraints that decide it are `Q-06` and `Q-03`, James's to answer. This
is the posture Section 04 took with `D-09` and `D-10`. `D-20` is partially resolved: routing
**constraints** fixed, thresholds deferred. `D-39` and `D-40` are new.

**Roadmap ordering is unchanged.** No section was added, removed, renumbered, redefined, or
reordered.
