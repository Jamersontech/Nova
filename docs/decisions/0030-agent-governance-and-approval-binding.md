# 0030 — Agent Governance Classification and What an Approval Binds

**Status:** **Accepted**
**Proposed:** 2026-08-14 — Section 06
**Accepted:** 2026-08-14 by James
**Section:** 06
**Resolves:** `S6-D4`, `S6-D5`

## Decision

**1. Agent operations are classified under the existing C1/C2/C3 model. No new class is created
and no existing class is reinterpreted.**

| Operation | Class |
| --- | --- |
| Register or change an agent **definition** | **C2** |
| …setting or changing Permissions, Allowed Context, Allowed Tools, or risk ceiling | **C3** |
| **Creating an agent** | **C3 in every real case** — those fields are mandatory |
| Changing the model / capability profile | **C2** |
| Activation | part of the same governed act as registration |
| Suspend / revoke | **C1** — restriction |
| Replacement | **C3** |
| Instantiating an execution | **not governance** — execution, bounded by ADR 0029 |

**Registration and activation are authorization. Instantiation is execution. Neither is
configuration.**

**2. An approval binds nine properties of the effective authorization (`I-109`):** action,
resource, scope, effective rights, risk class, tool set, argument envelope (`I-100`), delegation
ancestry, cost ceiling.

**It does not bind** model, provider, capability profile, the **ephemeral agent instance
identity**, wording, formatting, ordering, or other implementation metadata.

If the binding differs at execution, the approval does not apply, execution does not proceed under
it, and fresh approval is required where the risk class requires approval. The binding reuses
`I-93`'s deterministic-identity construction. **No cryptography is invented.**

## Context

`IDENTITY_AND_AUTHORITY.md` §4 classes "New components… tool definitions" as C2 and "agent
authority" as C3; §5 classes *agent permissions* C3. `TOOL_AND_INTEGRATION_ARCHITECTURE.md` §6
classes adding a tool C2 and changing its risk class or rights C3. `PERMISSION_ARCHITECTURE.md` §5
states an approval authorizes *"one action, in one context, at one time."*

## Problem

**Agents were named nowhere in the governance table.** C2 names *tool* definitions explicitly and
§5 classes *agent permissions* as C3 — but **creating an agent**, which is the operation that fixes
its Permissions, Allowed Context and Allowed Tools in the first place, appears in no row. An
implementer could defensibly read agent creation as C1 configuration and stand up a privileged
agent without James. That is the shortest available path from model output to privileged execution.

**And nothing said what makes an approved action the *same* action at execution time.** "One
action, one context, one time" fixes *how many* times an approval may be used, not *what it is an
approval of*. Between approval and execution the agent definition, its tool set, its effective
rights, its delegation chain or its budget could change, and the approval would still appear to
apply. Section 05's `MT-8` envelope bound tool *arguments*; nothing bound the *agent*.

## Options Considered

**For governance:** a new C4 agent class; a new agent-specific governance framework; classifying
agent operations under existing C1/C2/C3; leaving it implicit.

**For approval binding:** bind nothing beyond the action (status quo); bind the agent instance;
bind everything including metadata; bind the effective authorization only.

## Decision Made

Existing C1/C2/C3, made explicit. Effective-authorization binding.

## Reason

**The existing table already decides this; it just never said so about agents.** A new class would
create a second governance vocabulary for one subject, and every future reader would have to learn
why agents are special when they are not — an agent definition is a component that carries
authority, which is precisely what C2 and C3 already distinguish between. Making the implication
explicit removes the ambiguity without adding a concept.

**Suspension and revocation are C1 for the same reason `I-93` lets restriction proceed when its
record fails:** operations that *remove* access are not gated like operations that *grant* it.
Gating an emergency suspension behind C3 approval would make the safety operation slower than the
dangerous one.

**Approvals must bind authority, not implementation.** Binding the agent *instance* was rejected
outright: instances are ephemeral **by design** (`AGENT_ARCHITECTURE.md` §3), so that binding would
make every approval stale on principle and train exactly the reflexive re-approval
[`KNOWN_RISKS.md`](../architecture/KNOWN_RISKS.md) records as a security failure. Binding
*everything* fails the same way. Binding *nothing* leaves the substitution attack open.

**Model and provider are excluded deliberately**, not by oversight: Section 05 decides egress per
call at the gateway enforcement point (`I-94`, `I-97`), so a provider change is already separately
authorized. A second gate here would be duplicate machinery for a case already covered.

## Tradeoffs

**Advantages:** no new governance class, framework, or vocabulary; the shortest injection path to a
privileged agent is closed at the governance layer rather than by a runtime check; approvals stop
being silently transferable to a materially different action; no cryptography added — `I-93`'s
construction is reused.

**Disadvantages:** **agent creation is now effectively always C3**, so every new agent needs James,
and the friction is real — `AGENT_PRINCIPLES.md` §1's "when in doubt, do not create the agent"
becomes operationally enforced, which is the intent but will feel slow. The nine-property binding
means some benign changes invalidate an approval and require re-approval, pushing against approval
fatigue in the opposite direction from `AG-18`'s exclusions. And the boundary between "changes
effective rights" and "implementation metadata" is a judgment an implementer must make correctly on
each tool and agent field.

## Consequences

- `IDENTITY_AND_AUTHORITY.md` §5 gains agent rows; `PERMISSION_ARCHITECTURE.md` §5 gains the
  binding — authorized by [ADR 0031](./0031-section-06-amendments-to-accepted-architecture.md).
- `I-73` is unchanged and load-bearing: no agent performs any C2 or C3 operation above, because
  `IDENTITY_AND_AUTHORITY.md` §4 already forbids AI implementation of C2 and above.
- **Approval-binding mismatch is a control-plane audit event under `W-3`** — ADR 0023's `S4-P9` D3
  already places approvals there. No new audit authority.
- **Prohibition 6 of `AGENT_PRINCIPLES.md` §4 — "present inference as verified fact" — remains
  unenforced by any mechanism**, and §4's blanket "enforced by design" claim is corrected rather
  than defended. Enforcing it would require a component inspecting agent output for epistemic
  honesty, which NOVA does not have. It is a review and evaluation criterion (Section 41).

Invariants: `I-109` (new). `I-09`, `I-10`, `I-73`, `I-93`, `I-100`, `I-101` untouched.

## What Would Change This

Evidence that C3-on-every-agent-creation is so slow it drives agents to be created as
over-broad general-purpose definitions to avoid repeat approval — which would argue for a narrow
C2 sub-case with a fixed authority envelope, recorded as a superseding ADR.
