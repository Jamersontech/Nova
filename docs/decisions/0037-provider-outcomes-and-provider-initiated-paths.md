# 0037 — Provider Outcomes Are Claims, and Provider-Initiated Paths Carry No Authority

**Status:** **Proposed**
**Proposed:** 2026-08-15 — Section 11
**Section:** 11
**Resolves:** `S11-D2`, `S11-D3`, and — **approved by James 2026-08-15 for implementation, ADR
still Proposed** — `S11-D1` (§ "S11-D1", below)

> *(Superseded note, retained for the record: as first written this ADR deliberately did not
> resolve `S11-D1`, which was stopped for James because it requires a new invariant and touches the
> accepted `I-109`. **James approved that decision on 2026-08-15**, and its resolution is folded in
> below rather than minted as ADR 0038 — it is the continuation of the same Section 11 decision
> family this ADR opened, and it shares this ADR's amendment surface.)* `S11-D2` and `S11-D3` are
> independent of it: neither depends on how authorization is bound to a binding.

## Decision

**Two rules, both extensions of mechanisms that already exist. Neither creates a new invariant.**

**1. A provider's statement about its own side effect is a claim, not a verified fact (`S11-D2`).**
*"The tool was authorized"* and *"the provider did exactly what NOVA authorized"* are different
propositions, and only the first is established inside NOVA. A success response, a failure
response, a timeout, a lost connection, a partial response and an asynchronous job identifier are
each **`integration.supplied` claims about the external world**, carrying that provenance and its
trust. **None of them may be recorded as `system.verified`**, because `system.verified` requires an
authoritative source checked by something other than the asserting party — which `I-110` already
requires and a provider asserting its own success is not.

**2. A provider-initiated inbound signal carries no identity and therefore no authority
(`S11-D3`).** An external system **never authenticates into NOVA**
([`AUTHENTICATION_MODEL.md`](../architecture/AUTHENTICATION_MODEL.md) §2, unchanged), so a
webhook, callback, or integration-sourced event carries **no execution identity, no Context Token,
and no grant**. It is untrusted inbound data (`SECURITY_BOUNDARIES.md` §3) which may **inform** and
may **surface**, and which **never itself authorizes an action**. The `source` field on such an
event is an **unauthenticated assertion**, not an authenticated origin.

## Context

Section 10 closed the *silent* under-declaration of a tool's own definition and handed forward one
question: *provider behaviour is not in the tool definition.* Section 11's trace of the execution
path — plan → authorized action → tool identity → binding → credential → provider → request →
side effect → response → verification → audit — found that question splits into **three**
independent families, not one. This ADR takes the two that existing invariants already answer.

## Problem

### `S11-D2` — what NOVA is entitled to conclude from a provider response

**Every downstream decision reads the recorded outcome.**
[`RELIABILITY_ARCHITECTURE.md`](../architecture/RELIABILITY_ARCHITECTURE.md) §3 requires that
*"every step records its own outcome"* and resumes *"from the last verified step"*; §4 retries only
what is declared idempotent; James is told *"exactly what completed, what did not, what is now
inconsistent"*. **All of that reads a value the provider supplied**, and nothing said what that
value is worth.

**Three concrete shapes the architecture did not separate:**

| Shape | What NOVA knew | What was actually true |
| --- | --- | --- |
| **Success claimed, effect absent** | step recorded complete | nothing happened; a compensation is planned against a change that does not exist |
| **Failure claimed, effect present** | step recorded failed | the side effect landed; retry duplicates it |
| **Ambiguous — timeout, lost connection, partial response** | no outcome at all | unknown, and **unknowable from NOVA's side** |

**The ambiguous row is the sharp one, and it is where idempotency stops being a safety property.**
§4 permits automatic retry for a tool *declared* idempotent. **Idempotency is declared by NOVA and
enforced by the provider** — they are not the same thing, and NOVA has no idempotency-key concept
at all. A tool correctly declared idempotent against a provider that does not honour a
deduplication key produces **two real side effects**, and the declaration was not wrong; it was
about the wrong party. This is Section 10's claims-not-facts problem in a second place, which is
why it is stated rather than assumed.

**A partially-executed request is not a partially-completed workflow.** §3 handles a workflow whose
fourth step failed after three succeeded — step granularity. It does not reach a **single request**
the provider partially performed before returning failure, which produces a real change under a
step recorded as failed.

### `S11-D3` — provider-initiated inbound paths

**The words "webhook" and "callback" did not appear anywhere in the repository.** The path itself,
however, is already in the accepted architecture:
[`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md)
§2 names **integrations** as event *sources* — *"client replied, payment received, deployment
succeeded, site down, API failed"* — and **workflows waiting on a condition** as *consumers*.

**So an external party can already place a signal that a workflow is waiting on**, and nothing
stated what that signal is worth. `SECURITY_BOUNDARIES.md` §2 tabulates what may cross each
boundary and describes the external-service boundary as *"scoped requests out; data in, marked
untrusted"* — written from the perspective of **NOVA asking**. A provider-initiated inbound signal
is data in that **nobody asked for**, and the table did not distinguish it. **This is the same
defect Section 05 found when model egress was missing from that table**, in the opposite direction.

**Asynchronous provider work is the same gap seen from the other end.** A submitted job can outlive
the execution that submitted it and report back later. `I-107` makes delegated authority unable to
outlive its delegator — but a provider-side job is not a delegation and `I-107` does not reach it,
so the one place where work genuinely outlives its authorizer was unstated.

## Options Considered

**For `S11-D2`:** (a) status quo — treat the response as the outcome; (b) require independent
verification of every consequential side effect by read-back; (c) **record the outcome as a claim,
separate ambiguity from failure, and make retry safety depend on the enforcing party**; (d) forbid
tools whose outcomes cannot be verified.

**For `S11-D3`:** (a) silence; (b) treat integration events as authenticated once the transport is
authenticated; (c) **state that inbound provider-initiated signals carry no identity and no
authority, and are untrusted data that may inform and surface but never authorize**.

## Decision Made

(c) in both cases.

## Reason

**(b) for `S11-D2` was rejected because it is not generally possible and would be dishonest to
claim.** Read-back verification works for some providers and some actions and not for others — a
sent message often cannot be observed at all — and a rule that cannot be enforced uniformly becomes
a rule implementers satisfy nominally. **Where read-back is available it is worth doing, and the
decision says so; where it is not, the honest outcome is a labelled unknown, not an invented
verifier.** This is the same reasoning that rejected a declaration verifier in ADR 0036, and the
reasoning `I-102` and `I-110` already encode: the only component that could bridge the gap by
judgement is a model, and a model may not establish an authorization-relevant fact.

**(d) was rejected because it would exclude most useful integrations** — mail, SMS and payment
side effects are exactly the ones hardest to observe — and Section 04 already accepted approval and
irreversibility as the controls for consequential actions.

**(b) for `S11-D3` was rejected because it confuses two different authentications.** Verifying a
webhook's transport signature establishes that **the message came from the provider**. It does not
establish that the **assertion inside it is true**, and it certainly does not create an execution
identity — `AUTHENTICATION_MODEL.md` §2 says a service *"never authenticates into NOVA"*, and that
line is correct and unchanged. Signature verification is worth having as an integrity control and
is **not** an authorization mechanism; conflating them is precisely how an inbound signal becomes a
confused deputy.

**No new invariant is required for either, and that is a finding rather than a convenience.**
`S11-D2` is `I-39`, `I-110` and `PROVENANCE_AND_TRUST.md`'s three axes applied to a class of item
nobody had labelled — a provider's assertion about its own behaviour is `integration.supplied`,
and the existing rules already forbid promoting it. `S11-D3` is `AUTHENTICATION_MODEL.md` §2 plus
`I-14`'s default deny plus `SECURITY_BOUNDARIES.md` §3, applied to a path those documents already
imply but never named. **Minting a new invariant for either would add a security invariant that
restates existing ones**, which Section 09 and Section 10 both declined to do.

## Tradeoffs

**Advantages:** every rule extends an existing mechanism; no new component, verifier, trust
dependency, authority, audit category or change class; the ambiguous-outcome case becomes
representable instead of collapsing into "failed"; the inbound path is named before it is built,
rather than after.

**Disadvantages:** **the unknown-outcome state is operationally expensive.** An ambiguous result
that cannot be resolved by read-back escalates to James, and on a flaky integration that will be
frequent — the pressure will be to treat ambiguity as failure and retry, which is exactly what
produces duplicate side effects. **Read-back verification costs a second call** on the actions
most likely to be rate-limited. **And the honest limit is that a provider which lies convincingly
is not detected**: recording the outcome as a claim bounds what NOVA concludes from it, and does
not make the claim true.

## Consequences

- Amendments to five Active documents, enumerated below; `THREAT_MODEL.md` gains `T-38`;
  `KNOWN_RISKS.md` §3.11 records the residuals. **This ADR carries its own amendment list**, the
  precedent Sections 07, 09 and 10 set.
- **`I-39`, `I-99`, `I-102`, `I-104`, `I-107`, `I-110` and `I-111` are unchanged in substance** and
  each becomes harder to defeat by having its application to this path stated.
- **`RELIABILITY_ARCHITECTURE.md` §4's retry rule is narrowed, not widened:** a declared-idempotent
  tool is auto-retryable only where the **provider** enforces the deduplication the declaration
  assumes. Where it does not, the tool is not auto-retryable, whatever it declares.
- **`S11-D1` is resolved in this ADR** (§ "S11-D1" above, added on James's 2026-08-15 approval):
  `I-114` makes the authorization aware of the binding that produces the consequence, and `I-109`
  is amended in place. `S11-D2` and `S11-D3` govern what NOVA concludes *after* a call and what an
  inbound signal is worth; `S11-D1` governs which substrate the call uses. The three stand together
  in this one ADR because they share one decision family and one amendment surface.

## S11-D1 — Authorization is bound to the execution binding (`I-114`)

*Added 2026-08-15 on James's approval. One new invariant, one amendment to an accepted invariant.*

### The decision

**A consequence-producing tool action is authorized against the binding that will produce the
consequence, not against the tool alone.** The **execution binding** — tool identity **and
version**, integration, credential binding, resolved in one scope — becomes an element of the
authorization decision ([`AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md) §2), and
`I-114` states four requirements:

1. **Resolve before deciding.** The binding is resolved *before* the authorization decision and is
   an input to it; an unresolvable binding **denies** — never a default or last-known binding.
2. **Envelope, then check.** Authorization fixes a **binding envelope**; the enforcement point
   checks the **resolved** binding against it at call time. Not covered → denied, recorded as a
   **security event**, not a retryable error. This is `I-100`'s and `I-113`'s structure reused —
   deliberately **not** a new permission model.
3. **Binding identity is consequence-bearing.** Provider, account/tenant, endpoint or declared API
   version changing produces a **different binding**, C3, invalidating authorizations that named
   the old one — exactly as a material plan change produces a new plan (`I-112`). Credential
   rotation *within* a binding is not a binding change.
4. **No substitution, no provider equivalence, no model selection.** Failover, reroute, retry and
   resumption select only within the envelope — `I-97`'s rule applied to tool bindings; an
   unavailable sole binding **fails closed**. Two integrations reaching the same provider are two
   bindings and neither stands in for the other: an equivalence rule would assert that two external
   systems behave the same, the unverifiable behavioural claim ADR 0036 declined for tools and this
   ADR declines for outcomes. The binding is **never selected by model output** (`I-98` extended).

### The `I-109` amendment

`I-109` excluded *model, provider, capability profile* from the approval binding, with the
rationale *"model/provider changes are already decided per call by `I-94`/`I-97`"*. **That
rationale is real and is preserved — but it is a fact about model calls only**, because for tool
calls there is no per-call provider decision for it to lean on. The amendment **scopes the
exclusion list** rather than deleting it: for a **model call**, model, provider and profile remain
unbound, decided per call; for a **consequence-producing tool action**, the approval **also binds
the execution binding** as a tenth property. The nine accepted properties are unchanged and
unreordered, the ephemeral-instance exclusion is unchanged, `I-93`'s deterministic identity is
still the construction, and the amendment is marked in place, reverting verbatim if this ADR is
rejected.

### Enforcement points, named

| When | Where | Check |
| --- | --- | --- |
| Before the decision | Capability layer | Resolve the binding; unresolvable → deny (`I-114`(a)) |
| At the decision | PDP steps 5–8 | Binding is an input; the envelope is fixed ([`AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md) §3) |
| At execution | Tool enforcement point | Resolved binding ∈ envelope, or deny + security event (`I-114`(b)) |
| Before injection | **Credential Broker step 2a** | Presented `binding id` ∈ authorized envelope ([`SECRETS_ARCHITECTURE.md`](../architecture/SECRETS_ARCHITECTURE.md) §3) |
| Every retry / resume / failover | Both of the above, per attempt | Re-resolve and re-check; follows from re-injection being per attempt ([`RELIABILITY_ARCHITECTURE.md`](../architecture/RELIABILITY_ARCHITECTURE.md) §4) |
| After binding change | Approval binding | Different binding → `I-109` mismatch → approval does not apply |
| After re-planning | Plan authorization | New plan → new authorization (`I-113`, unchanged), which fixes a fresh binding envelope |
| After the fact | Audit | The binding used and the envelope checked are recorded, `W-1`, by reference ([`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](../architecture/EVENT_AND_OBSERVABILITY_ARCHITECTURE.md) §5.1) |

**The Credential Broker check closes the gap its own protocol exposed:** step 1 already receives a
`binding id`, and every existing step asked whether that binding was *acceptable* — never whether
it was *the one authorized*. Step 2a is one comparison, not a second permission model.

### Rejected alternatives

**Binding at plan time to a literal single binding id** — rejected: `MT-8` established that
authorization is over an envelope, not a literal, and an envelope may legitimately name more than
one binding. **Provider equivalence classes** — rejected as above; fail closed instead.
**Verifying provider semantics against the declaration** — rejected on ADR 0036's ground: the only
component that could judge is a model, barred by `I-101`/`I-102`/`I-110`. **A separate binding
authorization service** — rejected: the PDP, broker and tool PEP already sit on the path; adding a
fourth party adds surface, not assurance.

### Honest limits

`I-114` controls **NOVA's own choice of execution substrate**. It does not control the external
system: a provider changing behaviour behind a stable identity is undetected (`T-39` residual), a
submitted side effect is not recalled (`T-38`), and an integration whose consequence-bearing fields
are recorded inaccurately passes the check on wrong information — the claims-not-facts limit, in a
third place.

## The amendments

**All are Proposed and marked in place. If this ADR is rejected, each is removed and the accepted
text restored verbatim.**

| # | Document | Section / status | Change |
| --- | --- | --- | --- |
| 1 | `TOOL_AND_INTEGRATION_ARCHITECTURE.md` §3, §3.1, §4.1, §4.2 | 02 · Active | Outcome claims; resolve-then-decide invocation ordering; integration identity and no-substitution; provider-initiated inbound paths |
| 2 | `RELIABILITY_ARCHITECTURE.md` §2, §3, §4 | 02 · Active | Ambiguous outcome as a distinct state; partial request execution; provider-enforced idempotency; per-attempt binding re-check and envelope-bounded failover |
| 3 | `PROVENANCE_AND_TRUST.md` §5 | 03 · Active | A side-effect claim is not the *"fact about the external system"* a fetch is |
| 4 | `EVENT_AND_OBSERVABILITY_ARCHITECTURE.md` §2, §5.1 | 03 · Active | An integration-sourced event's `source` is an unauthenticated assertion; External transmission records the execution binding |
| 5 | `SECURITY_BOUNDARIES.md` §2 | 02 · Active | The external-service row covers provider-**initiated** inbound; the Tool row gains the binding-envelope check |
| 6 | `AUTHORIZATION_MODEL.md` §2, §3 | 03 · Active | **Execution binding** as an element; resolved before the decision, an input to steps 5–8; ten steps unchanged |
| 7 | `SECRETS_ARCHITECTURE.md` §3 | 03 · Active | Broker **step 2a**: the presented binding must fall within the authorized envelope |
| 8 | `INVARIANTS.md` | 03 · Active | **`I-114`** (new); **`I-109` amended in place** — exclusion list scoped between model calls and tool actions. `I-01`–`I-108`, `I-110`–`I-113` unmodified |
| 9 | `THREAT_MODEL.md` | 03 · Active | `T-38`, `T-39`. `T-03`'s and `T-16`'s residuals **not reduced** |
| 10 | `KNOWN_RISKS.md` §3.11 | 03 · Active | Section 11 residuals |

## What Would Change This

For `S11-D2`, a provider class offering a **cryptographically attestable receipt** of a side
effect — a signed statement of what was done, verifiable by NOVA without trusting the asserting
channel. That would argue for verified outcomes **in addition to** claims, never for treating an
ordinary success response as one. For `S11-D3`, nothing: an external system authenticating into
NOVA is a C4 change to the identity model, not an integration feature.
