# Known Risks and Architectural Weaknesses

**Status:** **Active** — Section 02, approved by James 2026-08-12.
**Purpose:** An honest register of where this architecture is weakest, what it deliberately
trades away, and what a future section must watch. Recorded so that later sessions inherit
the concerns rather than rediscovering them.

An architecture document that describes only strengths is not trustworthy. These are the
results of deliberately attacking the Section 02 design.

---

## 1. Fixed During Section 02

Two genuine gaps were found in self-critique and closed before Section 02 was declared
complete.

| Gap | Why it mattered | Fix |
| --- | --- | --- |
| **Cross-scope aggregation could leak on write** | Decomposition protects read access, but the aggregation point briefly holds several clients' results. Writing a summary from there would copy one client's detail into a partition another can read — isolation holding at read time and failing at write time | Aggregation rule: results are ephemeral, never written to memory, elevation is explicit and recorded, and aggregation never runs autonomously above `ANALYZE` ([`CONTEXT_ARCHITECTURE.md`](./CONTEXT_ARCHITECTURE.md) §6) |
| **Untrusted content could escalate a plan** | Marking external data "untrusted" is insufficient, because the Planner legitimately reads it. Injected instructions could shape a plan that then executes autonomously | Untrusted content may *inform* a plan but never *escalate* one; influenced plans cannot exceed `PREPARE` without approval naming the source ([`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §3) |

---

## 2. Accepted Weaknesses

Real costs knowingly accepted, with the reasoning.

### The Policy Decision Point is a central dependency
Every layer consults it. If it is unavailable, NOVA largely stops — it fails closed, which
is correct for security and costly for availability. It is also on the hot path of every
action.

**Accepted because** the alternative — distributed authorization logic — is how isolation
rots. **Requires** that the PDP stay simple, fast, and independently testable, with read
decisions cacheable within a context's lifetime. **Watch in** Sections 04 and 33.

### WEALTH's cross-domain read is a deliberate asymmetry
WEALTH may read across domains; nothing may read WEALTH. This is the only one-directional
exception in the architecture, and every exception is a place where isolation depends on
correctness rather than structure.

**Accepted because** wealth analysis genuinely needs business revenue and personal expenses,
and the reverse has no legitimate use. **Bounded by** read-only access, exclusion of
sensitive LIFE Areas, and per-access audit. **Residual risk:** a compromised WEALTH agent
sees more than any other agent. **Watch in** Sections 04 and 23.

### The Orchestrator can still grow
Domain logic and credentials are excluded, but the Planner is where heuristics naturally
accumulate — a special case here, a shortcut there.

**Mitigated by** the five-component split and the exclusions. **Not eliminated.** **Watch
in** Section 08: if the Planner starts containing business-specific branches, that is the
god-object returning by a slower route.

### Work Orders must be specified precisely
Because coding agents cannot query NOVA for missing context, an underspecified order fails
or produces wrong work.

**Accepted** as the direct cost of [ADR 0005](../decisions/0005-external-coding-agent-isolation.md).

**Mitigation path defined (2026-08-12).** At acceptance James recorded that NOVA should
eventually generate precise Work Orders from high-level requests, moving the specification
burden onto NOVA rather than relieving it by widening agent access. This converts the
weakness from a permanent cost into a capability gap owned by Sections 08 and 30.

**Residual risk:** until that capability exists, specification quality is manual and early
rework should be expected. Once it exists, **Work Order generation quality becomes a new
thing to evaluate** — a badly generated order fails as surely as a badly written one, and it
fails at machine speed. **Watch in** Sections 30 and 41.

### Memory elevation depends on judgment
Promoting a client detail into business memory is an explicit, audited operation — but the
decision to approve it is judgment, and a model-written summary can embed identifying
detail even when the elevation seems reasonable.

**Watch in** Section 07. Elevation prompts and summaries need their own evaluation.

---

## 3. Open Risks for Future Sections

| Risk | Concern | Owner |
| --- | --- | --- |
| **Physical isolation not yet chosen** | Logical isolation is fully specified; whether it is enforced by row-level rules, schema separation, or database-per-client is unresolved (`D-33`). The weakest choice would leave isolation dependent on query correctness | 03 |
| **Memory quality degrades with volume** | Retrieval quality falls as memory grows. Curation and decay are specified but unimplemented; retrofitting them onto a large corpus is far harder | 07 |
| **Risk classification may be drawn wrongly** | The seven classes are a first attempt. A boundary drawn wrongly produces either approval fatigue or unapproved consequences | 26 / 39 |
| **Approval fatigue is a security failure** | If James approves reflexively, the entire human-control model is decorative. This is a product-design problem, not a technical one | 26 |
| **Evaluation is unbuilt** | Every claim about agent behaviour is currently unverified. Until Section 41 exists, "the agent respects its boundaries" is an assumption | 41 |
| **Provider abstraction is untested** | Provider neutrality holds only if it is exercised. An abstraction never tested against a second provider is usually wrong | 05 |
| **Single-user assumptions may be embedded** | `Q-04` is unanswered. The identity model names an external-user class, but no code has been written to honour it | 04 |
| **Scope tree rigidity** | One parent per scope is deliberate. Real work that genuinely spans two clients will be awkward, and the pressure to relax this will be real — and should be resisted | 03 / 22 |

---

## 4. What Would Invalidate This Architecture

Stated plainly, so a future session can recognize it:

- **If isolation tests cannot be written** against the scope model, the model is not as
  structural as claimed.
- **If adding a business requires code changes**, the multi-business resolution failed.
- **If removing a model provider requires touching agents**, provider neutrality failed.
- **If James stops reading approval requests**, human control failed regardless of
  correctness.
- **If a new coding agent cannot understand NOVA from `docs/`**, legibility failed — which
  is the failure Section 01 exists to prevent.

Each of these is testable. None should be assumed to have been avoided.
