# 0038 — Automations Are Intent, Not Authority

**Status:** **Proposed**
**Proposed:** 2026-08-15 — Section 12
**Section:** 12
**Resolves:** `S12-D1` (the only Section 12 decision; it is a **derivation**, not new policy)

> **Held Proposed at the 2026-08-15 ADR Decision Gate — not doubted.** ADRs `0032`–`0037`
> were accepted there on implementation evidence from the three vertical slices. This one
> was **not**, for one reason only: **it has no implementation evidence yet.** Its section
> produced documentation, and no code exercises it. **No contradiction, ambiguity or defect
> was found in it** — the review found none, and the repository agrees with it throughout.
> It stays Proposed because accepting it would rest on review alone, which is precisely what
> the vertical-slice programme exists to avoid.

## Decision

**An automation — a stored workflow definition plus the trigger or schedule that fires it — is
intent, not authority. Every firing is authorized freshly, at fire time, through the unmodified
pipeline, and nothing about the definition, the trigger, the schedule, or any previous firing
carries authorization forward.**

**No new invariant is created, and that is the finding.** Every clause above is forced by rules
that already exist; this ADR records the composition so an implementer cannot choose the industry
default instead — the stored workflow whose permissions were checked at save time, which is
precisely the loophole around Sections 01–11 that a workflow engine invites.

The derivation, clause by clause:

| Clause | Forced by |
| --- | --- |
| A definition confers no authority | `I-14` — absence of a grant is a denial, and a definition is not a grant; only James creates grants (`I-10`) |
| A trigger confers no authority | A trigger is an **event** — data ([`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §2). External signals carry no identity, token, or grant (ADR 0037 `S11-D3`); a **schedule** event is NOVA-produced and confers exactly as little — it says *when*, never *whether* |
| Each firing produces a fresh plan through Permission Evaluation | *"Permission is evaluated after planning but before any execution"* ([`ORCHESTRATION_ARCHITECTURE.md`](../architecture/ORCHESTRATION_ARCHITECTURE.md) §2) — a template that skips it violates the accepted pipeline; a plan is immutable with per-authorization identity (`I-112`) and never inherits authorization (`I-113`) |
| No firing inherits from a previous firing | `I-113` — same objective is never a reason to inherit; an approval is *"one action, in one context, at one time… never a precedent"* (`PERMISSION_ARCHITECTURE.md` §5) |
| The unattended actor is the NOVA system identity | [`IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md) §2 defines it for *"scheduled and autonomous work"*, distinct from James in the audit trail, ceiling = James's delegation minus anything requiring human approval |
| Standing autonomy exists only as James-created grants | `PERMISSION_ARCHITECTURE.md` §5 — standing approvals are *"recorded as grants"*, bounded by scope, risk ceiling, expiry, rate limit, revocable |
| Work above the autonomous ceiling pauses for approval | The workflow engine's *"Pauses — indefinite waits for approval or external events"* (`ORCHESTRATION_ARCHITECTURE.md` §4); a plan that does not exist until fire time cannot be approved before it (`I-109` binds the plan's properties) |
| Resumption, retry, and failover re-check | `I-109`/`I-113` resumption re-check (Section 08), per-attempt binding re-check (`I-114`, Section 11) |
| Persistence preserves taint, ancestry, plan identity | `I-111`, `I-112` |
| Revocation and stop reach unattended work | `V-2` next-enforcement-point fail-closed, `X-1`/`X-3`/`X-7` — enforced at enforcement points, which unattended work still passes through |

## Context

Section 12 (Automation & Workflow Engine) reconstructed the workflow machinery and found it
already dense: durable resumable workflows, step-level state, pause/resume/cancel, partial
completion, retry discipline, resumption re-checking, per-attempt binding re-checks, and stop
semantics all exist. **What no document stated is what an *automation* is** — the word "workflow"
was defined, "a routine is a recurring Workflow" appeared once
([`DOMAIN_ARCHITECTURE.md`](../architecture/DOMAIN_ARCHITECTURE.md) §2.2), schedules were named as
an event source, and nothing said what authority any of it carries across time.

## Problem

**The dangerous reading is the convenient one.** Every mainstream workflow engine stores a
definition, authorizes it at save time, and lets the scheduler run it thereafter. Under that
reading, *"James approved the automation"* becomes standing authorization: the definition is
mutated and keeps its blessing; a trigger fires and work executes under yesterday's decision; each
firing inherits from the last; and revocation of the underlying grants never re-enters the
picture because nothing re-asks. **Every one of those is a violation of an existing invariant** —
but only by composition, and no document performed the composition. An engineer implementing the
§4 workflow engine tomorrow would have to choose, and the industry default is the wrong choice.

**Three specific gaps in stating, none in substance:**

1. **The unattended actor was answered but never connected.** `IDENTITY_AND_AUTHORITY.md` §2
   defines the NOVA system identity for exactly this; no workflow text referenced it.
2. **Schedule events were named as a source and never assigned a trust status.** External signals
   got `S11-D3`; internal schedule events got nothing — leaving room to read "NOVA produced it" as
   "it carries NOVA's authority".
3. **Nothing said an automation definition is not a security object** — while agent definitions,
   tool definitions, plans, and bindings all are. The asymmetry is correct and needed stating:
   those objects **fix authority**; a definition fixes only what will be *asked*.

## Options Considered

1. **Definition-as-authorization** (save-time approval, runs inherit). Violates `I-14`, `I-113`,
   `PERMISSION_ARCHITECTURE.md` §5, and the pipeline ordering — architecturally excluded, not
   merely dispreferred.
2. **Definition as pre-authorized plan template.** A template with standing identity that skips
   Permission Evaluation violates `I-112` (plan identity is per authorization) and `I-113`.
   Excluded.
3. **Definition as intent; per-firing authorization at fire time.** The only reading consistent
   with the accepted architecture.
4. **Make the definition a governed security object with its own change class** (the Section 06
   agent-definition treatment). Rejected as unnecessary: an agent definition **fixes authority**
   (Permissions, Allowed Context, Allowed Tools), which is why its creation is C3. An automation
   definition fixes none — the authority an automation exercises lives entirely in James's grants,
   standing approvals, agent definitions and tool declarations, each already governed. Governing
   the definition would create a second, redundant control surface and imply the definition
   *carries* something worth governing.

## Decision Made

Option 3, with option 4's concern handled where the authority actually lives.

## Reason

**The security objects are already the right ones.** A firing can do nothing its grants,
delegations, tool declarations and bindings do not permit *at that moment* — which means
revocation, expiry, agent/tool/binding changes, and risk-class changes all take effect on the next
firing (and mid-run at the next enforcement point, `V-2`) with **no automation-specific
revocation machinery needed**. Conversely, making the definition a governed object would not add
one enforcement point, because the definition is never consulted by the PDP, the broker, or any
PEP.

**Creating or changing an automation is configuration, and what bounds it is the closed capability
surface, not a new class.** An agent can create an automation only if automation-creation is a
tool on its closed list — granting which is C3 (`IDENTITY_AND_AUTHORITY.md` §5, agent permissions)
— and a model cannot request it into existence (`I-98`-family: model output selects nothing).
NOVA core creates one on James's instruction as C1 configuration. In every case the *authority the
automation will exercise* was granted by James through the existing governed channels, or the
firings simply deny (`I-14`).

## Tradeoffs

**Advantages:** no new invariant, object, component, authority, or change class; revocation and
stop work on unattended work through the machinery that already exists; the definition can be
freely edited without an approval ceremony because editing it changes only what will be asked.

**Disadvantages:** **per-firing authorization is a real cost** — every firing runs Interpretation
through Permission Evaluation, and a high-frequency schedule multiplies PDP load (the pressure
will be to cache allows across firings, which is exactly re-introducing save-time authorization;
`I-17`'s bound — read-decision caching within one context lifetime, invalidated by revocation —
is the only caching permitted). **Approval-gated automations wake James** — a recurring workflow
above the standing-approval ceiling pauses at Approval every firing, by design; the mitigation is
a properly bounded standing approval, never a wider default. **And a standing approval is
authorized breadth**: a mutated definition whose new behaviour still fits an existing standing
approval's scope/risk/rate bounds executes under it — James approved those bounds, `T-16`'s
family, recorded as residual (`T-40`).

## Consequences

- [`ORCHESTRATION_ARCHITECTURE.md`](../architecture/ORCHESTRATION_ARCHITECTURE.md) gains §5
  stating the automation model; [`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md)
  §5.1 gains the automation-lifecycle audit row; `THREAT_MODEL.md` gains `T-40`;
  `KNOWN_RISKS.md` gains §3.12. **This ADR carries its own amendment list** — the Sections 07–11
  precedent.
- **`INVARIANTS.md` is deliberately not amended.** `I-01`–`I-114` are byte-identical to their
  current text. Every rule this ADR states is an application of `I-10`, `I-14`, `I-17`, `I-20`,
  `I-40`, `I-98`–`I-114`, `V-2`, and `X-1`–`X-7`.
- **No new architecture document.** The workflow engine lives in `ORCHESTRATION_ARCHITECTURE.md`
  §4 and the automation model belongs beside it.

## The amendments

**All are Proposed and marked in place. If this ADR is rejected, each is removed and the accepted
text restored verbatim.**

| # | Document | Section / status | Change |
| --- | --- | --- | --- |
| 1 | `ORCHESTRATION_ARCHITECTURE.md` §5 (new) | 02 · Active | The automation model: intent-not-authority, per-firing authorization, actor identity, trigger status, failure states |
| 2 | `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` §5.1 | 03 · Active | Automation-lifecycle audit row |
| 3 | `THREAT_MODEL.md` | 03 · Active | `T-40`. `T-16`'s and `T-36`'s residuals **not reduced** |
| 4 | `KNOWN_RISKS.md` §3.12 | 03 · Active | Section 12 residuals |

## What Would Change This

A demonstrated need for **pre-authorized offline execution** — firings that must proceed while the
PDP is unreachable — which per-firing authorization cannot serve. That would be a C4-scale change
to the fail-closed model (`I-17`), not an automation feature, and would need James's explicit
decision at that level.
