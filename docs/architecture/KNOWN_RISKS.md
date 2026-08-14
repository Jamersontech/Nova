# Known Risks and Architectural Weaknesses

**Status:** **Active** — Section 02, approved by James 2026-08-12. Extended in Sections 03 and 04.
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
| **Physical isolation not yet chosen** | Logical isolation is fully specified; the mechanism family — engine-enforced record restriction, per-scope namespace separation, or per-scope physical separation — is unresolved (`D-33a`). The weakest choice would leave isolation dependent on query correctness. *(Wording aligned 2026-08-13, R-9: previously "row-level rules, schema separation, or database-per-client", which used relational and product-shaped terms. The three families are named as [`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md) §3.1 states them. **No mechanism is selected.**)* | **04 / 29** |
| **Memory quality degrades with volume** | Retrieval quality falls as memory grows. Curation and decay are specified but unimplemented; retrofitting them onto a large corpus is far harder | 07 |
| **Risk classification may be drawn wrongly** | The seven classes are a first attempt. A boundary drawn wrongly produces either approval fatigue or unapproved consequences | 26 / 39 |
| **Approval fatigue is a security failure** | If James approves reflexively, the entire human-control model is decorative. This is a product-design problem, not a technical one | 26 |
| **Evaluation is unbuilt** | Every claim about agent behaviour is currently unverified. Until Section 41 exists, "the agent respects its boundaries" is an assumption | 41 |
| **Provider abstraction is untested** | Provider neutrality holds only if it is exercised. An abstraction never tested against a second provider is usually wrong | 05 |
| **Single-user assumptions may be embedded** | `Q-04` is unanswered. The identity model names an external-user class, but no code has been written to honour it | 04 |
| **Scope tree rigidity** | One parent per scope is deliberate. Real work that genuinely spans two clients will be awkward, and the pressure to relax this will be real — and should be resisted | 22 |

---

## 3.1 Risks Identified in Section 03

Full analysis in [`THREAT_MODEL.md`](./THREAT_MODEL.md). Recorded here because these are
weaknesses, not merely threats.

| Risk | Concern | Owner |
| --- | --- | --- |
| **Secrets storage is the highest-value target** | ADR 0009 concentrates all secret material in one place. That is correct — but it means compromise of that store is catastrophic, and the technology is unchosen (`D-10`) | 04 |
| **Slow memory poisoning** | Detection depends on contradiction surfacing. A consistently-wrong source that nothing contradicts is not detected | 07 / 40 |
| **Shared-resource blast radius** | A poisoned shared template reaches every consuming client at once. Inherent to sharing; argues for review on shared-resource changes | 22 |
| **Sensitivity marking is manual** | SENSITIVE-PERSONAL protection depends on James marking the Area. An unmarked health Area is only CONFIDENTIAL | 37 |
| **Small-N aggregates are not anonymous** | With few clients, an aggregate plus known values reveals the rest. Threshold undecided (`D-36`) | 22 / 37 |
| **Backups currently unmitigated** | Scope-partitioned backup is specified but the mechanism is unbuilt (`D-15`) | 36 |
| **Reviewed transformation depends on humans** | Stripping identifiers from procedural knowledge is the escape hatch in ADR 0010, and human review misses things | 22 / 31 |
| **Lineage completeness is load-bearing** | Deletion is only real if lineage was recorded at every derivation. A single missed derivation leaves an undeletable copy | 03 / 07 |
| **Fifty invariants, zero tests** | Every invariant is currently an assertion. Until Section 31, none is verified | 31 |

---

## 3.2 Residual Risks Explicitly Accepted by James — 2026-08-12

When accepting ADRs `0009`–`0015` as amended (commit `0917de5`), James **explicitly accepted
the following residual risks rather than treating them as resolved.** They are recorded here
so no future session mistakes acceptance for absence.

| Residual risk | Accepted position |
| --- | --- |
| **Credential ingress is not prevented** | NOVA does not *issue* credential material to agents, but it can arrive via integration responses, error payloads, sandbox environments, subprocess listings, files, screenshots, or user-supplied text. Detection (`I-51`) is best-effort and cannot recognise every secret format. **Leakage is not claimed impossible** |
| **External coding agents hold real secrets** | Narrow, expiring, task-scoped — but genuine. Containment is their narrowness and lifetime, not their absence (ADR 0005) |
| **A compromised PDP is a total authorization failure** | Fail-closed protects against an unavailable PDP, not a lying one. Independent verification of decisions is **not designed**. Accepted as systemic residual risk (T-19) |
| **Deletion is bounded** | The cascade reaches recorded lineage within NOVA-controlled storage only. Delivered exports, data sent to external systems, model-provider retention, and unrecorded derivations are **beyond reach** |
| **Injection persistence is contained, not removed** | Quarantine and revalidation limit influence; a patient attacker supplying plausible uncontradicted content is not detected (T-10) |
| **Aggregation disclosure is bounded by policy, not arithmetic** | Small-N aggregates leak; max/min/ranking disclose individual values. Prohibitions are rules to enforce, not mathematical impossibilities. `D-36` is unset, so client-facing cross-client aggregates are barred entirely for now |
| **`[PHYS]` invariants are unsatisfied until implementation** | *(Inventory refreshed 2026-08-13, N-13 — this row listed only the six Section 03 markings and predated Section 04's.)* The full current set is `I-03`, `I-21`, `I-33`, `I-45`, `I-47`, `I-55`, `I-60`–`I-63`, `I-66`, `I-68`, `I-69`, `I-71`, `I-72`, `I-80`, `I-86`, `I-87`, `I-88`, `I-90`, and **`I-96`** *(Section 05, Accepted 2026-08-14)* — each with a named dependency in [`INVARIANTS.md`](./INVARIANTS.md). All depend on physical choices not yet made |
| **All 93 invariants are unverified** | Every one is a REQUIREMENT, none is a VERIFIED IMPLEMENTATION PROPERTY, until Section 31. *(Count corrected 2026-08-13, N-13: the row said 59, then 88, 89, 90; the current count is 93. `I-60`–`I-93` are additionally **Proposed**, not accepted.)* |
| **Administrator error is unmitigable** | An over-broad grant or an unread approval by James is authorized breadth, not escalation |

**This acceptance does not close any of these.** Each remains open, owned by the sections
named in [`THREAT_MODEL.md`](./THREAT_MODEL.md) §4, and must be revisited there.

---

## 3.3 Risks Identified in Section 04

*Proposed — Section 04. Full analysis in [`THREAT_MODEL.md`](./THREAT_MODEL.md) `T-19`–`T-22`.*

| Risk | Concern | Owner |
| --- | --- | --- |
| **Authentication recovery is a structural weakness** | Recovery exists because James can lose his device; any usable recovery path is an alternative way in. Strength parity (`I-67`) bounds it, does not eliminate it | 04, on `D-09` |
| **Break-glass is a deliberate *availability* bypass, confined to the control plane** | *(Title corrected 2026-08-13, R-4 class sweep — "a deliberate bypass" unqualified contradicts `I-75`, which says break-glass never bypasses the authorization path and never reaches client data.)* It bypasses normal **availability** controls only. Bounded and loud, but an attacker with break-glass credentials gets control-plane recovery access — and its loudness depends on a notification path that may be degraded during the very incident it exists for | 04 / 25 |
| **Step-up does not protect an active session** | An attacker on a device James is actively using can do anything below the step-up line without challenge | 04 |
| **Secrets store availability gates all outbound work** | The broker fails closed (`S-8`), so store unavailability stops every external call. Correct for security, a real availability dependency | 04 / 35 |
| **Key custody is now load-bearing** | Per-scope keys mean key loss is data loss (`E-10`). A key-recovery path weaker than the encryption is the encryption's real strength | 36 |
| **`T-19` is reduced, not resolved** | ADR 0017 removes cross-client access from a PDP-only compromise, **once `D-33` is implemented**. Independent decision verification was considered and explicitly declined as disproportionate | 04 / 38 |
| **Isolation enforcement is specified but unbuilt** | `I-60`–`I-63` are `[PHYS]` requirements on a mechanism not yet chosen (`D-02` deferred). Until then `I-03` remains dependent on query correctness | 29 / 31 |
| **Two enforcement models to reason about** | ADR 0017's independence is a benefit that costs conceptual load: isolation cannot be adjusted through policy, only through infrastructure | 29 |

---

## 3.4 Risks Surfaced by the Section 04 Adversarial Review

*Proposed — Section 04 amendment pass, 2026-08-12. Section 04 remains under review.*

| Risk | Concern | Owner |
| --- | --- | --- |
| **Context service compromise defeats both isolation mechanisms** | ADR 0017's independence is from the **PDP**, not general. Both the PDP and the scope binding derive from the Context Token, so compromising the Context service defeats both from one point. The Context service is now a critical trusted component of the same standing as the PDP, and **nothing mitigates its compromise** (`T-23a`) | 04 / 38 |
| **PDP audit evidence is not independent** | Authorization audit records are emitted by the PDP itself, so a compromised PDP can emit false or omitted records. **No independent audit path is required or designed** (`I-85`). PDP compromise may be detectable from effects, not from the authorization trail | 27 / 38 |
| **Provisioning correctness is unverifiable today** | `I-80` requires isolation verification before client activation, but the verification cannot run until an isolation mechanism exists (`D-33a`, `D-02`) and the tests are Section 31's. Until then, a new client scope's isolation is asserted, not demonstrated | 29 / 31 |
| **Credential ingress via unstructured responses** | Generic pass-through tools have no meaningful response schema; `I-84` restricts raw pass-through and mandates scanning, but detection is heuristic and a novel format will pass. **Ingress remains possible** | 04 / 31 |
| **Break-glass reaches the control plane** | Now confined to control-plane recovery and barred from client data (`I-75`), but control-plane recovery includes repairing policy infrastructure — so break-glass credentials still confer the ability to alter the thing that authorizes. Accepted, bounded, loud | 04 |
| **Break-glass rotation cannot depend on NOVA** | `B-7` requires out-of-band rotation because break-glass is used when NOVA is degraded. The mechanism is deferred (`D-38`); until it exists, a used credential may remain valid longer than intended | 29 |
| **Token integrity is required but unbuilt, and adds a trusted component** | `I-87` requires a recipient to *detect* a modified or fabricated Context Token. It is `[PHYS]`: no mechanism is chosen (`D-09`, `D-33`), so the property does not hold today (`T-23b`). When it does exist, whatever provides it becomes a trusted component whose own compromise defeats it (`T-23c`). Trust is moved, not removed — and none of this touches compromise of the Context service itself (`T-23a`) | 04 / 31 |
| **The control-plane audit partition is a new concentration** | [ADR 0023](../decisions/0023-audit-record-writer-authority.md) routes provisioning, grants, revocations, incidents, break-glass and approvals to one partition outside the client scope tree. That is what makes `S4-P1` hold by construction — no component gains client-scope capability — but it concentrates the records establishing whether a scope was correctly isolated before activation. Compromise yields control-plane records, permanently under `I-47`, and **no client partition** (`T-27`) | 04 / 31 |
| **Full client history is now a two-partition read** | Under ADR 0023 a client's own partition holds its execution and decision records; provisioning, grant and revocation records concerning it sit in the control plane. Reviewing one client completely means both — James, per scope, with step-up where it spans scopes (`I-67`, `I-89`) | 04 |
| **Concurrent execution-scoped audit capabilities** | Under `S4-P5` (C+D) a shared service serving N executions holds N execution-scoped write capabilities, each bounded to one scope. **This is not blanket cross-scope capability** — it cannot reach a scope it is not serving — but compromise exposes the union of scopes currently served. The `I-86` prohibition on joining across simultaneously-held scope-bound channels applies equally here | 04 / 31 |
| **The audit bootstrap window — retired, not mitigated** | `S4-P6` (Option A) removed the capability-release decision, so the window `E-12d` described no longer exists: there is no release that can succeed while its record fails. Recorded because the risk was previously registered and a reader must be able to see why it is gone. **The architecture still does not establish that the audit trail is complete** — suppression by omission is unchanged (`T-26`) | 04 / 31 |
| **Cross-scope audit review depends on step-up** | `H-1` Option 3: single-scope audit reading is at normal session strength, so a compromised session exposes that scope's audit (`T-20a`). The cross-client corpus sits behind step-up — an attacker who *can* step up reaches what James reaches | 04 |
| **Audit key custody is load-bearing on both paths** | `E-11` partitions audit keys for reading and `E-12`/`I-88` require write capability to be per scope and **not** read capability, so no audit writer — the PDP included — holds a global audit key. **James declined to accept centralized audit-key custody as residual risk**; this is a requirement on a mechanism that does not exist (`I-88` is `[PHYS]`, `D-35`/`D-02`). Until it does, the separation is asserted, not demonstrated. A component that both writes and legitimately reads one scope's audit still holds both for that scope | 04 / 31 |
| **Ancestor key access is a new authorization surface** | `I-82` makes ancestor-scope key access per-resource and grant-bound rather than ambient. This is stronger, but it adds a release path that must itself be correct — a new place for a mistake | 04 / 38 |

## 3.5 Risks Identified in Section 05 — the model path

> ***Added by Section 05 — ACCEPTED by James 2026-08-14*** *(2026-08-14; authority ADRs
> [0024](../decisions/0024-model-gateway-is-an-enforcement-point.md)–[0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md),
> removed if they are rejected).*

| Risk | Detail | Owner |
| --- | --- | --- |
| **Taint labelling is now load-bearing, and a labelling bug is an authorization bug** | `I-99` propagates provenance and trust through model output so that `I-40`, `I-58` and `I-100`'s untrusted-derived case can be evaluated at all. Everything those rules protect therefore rests on labelling being **correct and pervasive** — and a missing label produces an action that looks fully authorized, with no failure to observe. This is the least visible failure mode Section 05 introduces | 05 / 31 |
| **An over-wide envelope silently restores the attack it exists to stop** | `I-100` checks a consequence-determining argument against the envelope the authorization fixed. An envelope written wide enough to be convenient admits the injected value and looks identical to a correct one at every point. Envelopes are harder to author than allow-lists, and nothing detects a bad one | 05 / 31 |
| **`I-96` is exactly as strong as the gateway enforcing it** | Redaction removes what NOVA can *identify*, and it cannot remove what NOVA has not classified. A compromised gateway reporting successful redaction is indistinguishable from a working one (`T-29`) — the same class of exposure `I-85` records for the PDP | 05 / 31 |
| **Correlated verifier failure is accepted, not solved** | `I-102` requires a different instance above `PREPARE` but only *prefers* a different provider, because requiring it would make verification unavailable wherever one permitted provider exists (`I-97`). Same provider, same injected content, both wrong is a live outcome (`T-32`) | 05 |
| **Provider-side correlation across scopes is unmitigated** | One provider credential serves many scopes (`I-103`), so the provider observes the client boundary from outside it (`T-30`). Per-scope accounts would not remove it. Whether anything closes it is `D-39` | 05 / 37 / 38 |
| **A second credential class is a thing to misapply** | `I-103` creates control-plane credentials to avoid weakening `I-23`. The obvious misuse is filing an integration credential as "control-plane" to escape per-scope binding. The class is closed and adding a member is C3 — a governance control, not a mechanical one | 05 / 22 |
| **Per-call PDP evaluation on the model path is unproven** | `I-94` puts a decision on a hot path and produces an `I-18` record per decision. `SCALE_AND_COST_ARCHITECTURE.md` §2 already names audit volume as a pressure point. If this proves unworkable the fix is a cheaper way to obtain the decision, **not** a return to unenforced egress | 05 / 33 |
| **`D-08` remains open, so the data-policy set has no members yet** | `I-97` constrains routing to a permitted provider set. No provider is selected (`Q-06`, `Q-03`), so the constraint is currently a constraint over an empty configuration. `PR-2`, `PR-3` and `PR-5` are assurances NOVA cannot verify (`D-39`) | 05 / 37 / 38 |

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
