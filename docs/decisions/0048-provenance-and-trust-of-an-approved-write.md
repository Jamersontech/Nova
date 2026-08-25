# 0048 — What Provenance, Trust and Classification Does an Approved Write Carry?

**Status:** **Accepted** — 2026-08-24
**Proposed:** 2026-08-24 — drafted by an agent following the post-merge hostile review of PR #6
**Accepted:** 2026-08-24 — by James, at the ADR Decision Gate, on the evidence recorded below
**Section:** 07 — extends `I-111`'s write half; governed by `I-110`
**Governance class:** **C3** — James's approval **and** an accepted ADR were required, and both
are recorded here
**Decision owner:** James. This ADR was drafted `Proposed` by an agent and moved to `Accepted`
only on James's explicit decision (`decisions/README.md`, *Authority*).
**Relates to:** `I-110` (ADR [0032](./0032-trust-promotion-authority.md)), `I-111`
(ADR [0033](./0033-section-07-amendments-to-accepted-architecture.md)), `I-40`, `I-99`, `I-20`,
`I-09`, `I-112` (ADR [0034](./0034-the-plan-is-a-security-object.md))

> **IMPLEMENTATION STATUS: NONE.** This decision is accepted; the behaviour it requires **does not
> exist yet**. The shipped write path still exhibits the F-1 behaviour documented below. Nothing
> in this ADR describes code that has been written.

---

## Decision

**Option C — content-visible approval.** Decided by James, 2026-08-24.

> **An approved write may receive elevated provenance/trust ONLY when the exact content being
> persisted was identifiable and inspectable by James before approval, the approval is bound to
> that exact content and plan identity, the resulting elevation is attributable to that approval
> evidence, and any change to the content after approval invalidates the approval.**

Approval alone does not elevate trust. Elevation requires **all five** of the following
properties; where any one is absent, the write is persisted at its **derived** taint and no
elevation occurs.

| # | Property | What it rules out |
| --- | --- | --- |
| 1 | The exact content to be persisted is **identifiable** — there is a determinate answer to "which bytes does this approval cover?" | An approval covering "a note", loosely |
| 2 | James can **inspect that content** before deciding | Endorsement of material never seen |
| 3 | The approval is **bound to that exact content**, via plan identity | Approving one thing and writing another |
| 4 | The trust elevation is **attributable to that approval evidence** — the record says *this* approval, of *this* content, is why the trust is what it is | Trust that no one can trace to a decision |
| 5 | **Changing the content after approval invalidates the approval** | Post-approval substitution, including by a concurrent or later caller |

**The default is non-elevation.** A write whose content is not content-visible under these five
properties is not refused — it is persisted honestly, carrying the taint derived from what
actually produced it. Elevation is the exception that must be earned, not the baseline that must
be argued away.

**What this decision settles, and what it leaves to implementation.** It fixes the **security
semantics** that any implementation must satisfy. It does **not** prescribe a mechanism, a
provenance label string, a UI layout, or a code change. The remaining questions in
*Explicit questions for approval* below — which label represents approved content, what trust
level it receives, what classification it receives, and what audit record `I-110` requires here —
are now bounded by Option C rather than open, but they are answered during implementation design,
subject to `I-110`'s existing requirements.

**Rejected alternatives**, with the reasoning preserved in *Options considered* below:

- **Option A** (approval confers trust) — rejected. It would make the laundering path lawful
  rather than closing it, and would record an endorsement James had no opportunity to give.
- **Option B** (approval never elevates) — rejected. It is correct-by-construction under `I-110`
  and was recognised as such, but it answers the question by declining to have trust at all,
  leaving NOVA's durable memory permanently non-authoritative.

**This decision does not change any code.** See the implementation-status notice at the head of
this ADR.

---

## Context

`I-111` requires that provenance, taint and delegation ancestry **survive persistence and are
restored at retrieval**, and states plainly that persistence *"must not discard provenance,
collapse multiple provenance sources into one, raise trust, remove taint, or replace `I-99`'s
union with the latest writer alone."*

PR #6 (merged to `main` as `e7bd2fa`) implemented that requirement's **read and persistence
half**, and implemented it correctly. This ADR concerns the **write half**, which PR #6 did not
resolve and did not claim to.

**The current system is not broken.** Before PR #6 the read path stamped
`Taint.of("james.stated")` on everything it retrieved, so trust was synthesized from the mere
fact that a row sat in NOVA's own database — exactly what `I-110` forbids. That synthesis is
gone. What remains unresolved is the value that is *written* in the first place.

The distinction that matters architecturally:

> `I-111`'s **retrieval and persistence enforcement is now strong**. The **write-side
> provenance/trust construction is unresolved** — it is a constant, and a decision is owed about
> what it should be.

---

## Security finding

Recorded from the post-merge hostile review of `main` @ `e7bd2fa`, reproduced end-to-end against
real PostgreSQL through the production `respond → propose → decide → execute` path.

### 1. The write plan's taint is a constant

`slice/substrate/write_path.py:413-423`, `WritePath.plan_for_action()`, line **421**:

```python
return Plan(
    steps=(PlanStep(action=tool_name, resource=scope_path, ...),),
    required_rights=frozenset({"write"}),
    declared_risk=Risk.EXECUTE,
    scope_path=scope_path,
    taint=Taint.of("james.stated"),      # <- constant, every tool, every call
    cost_estimate=1,
)
```

Every write plan therefore carries:

| Component | Value | Source |
| --- | --- | --- |
| provenance | `james.stated` | the constant |
| trust | `HIGHEST` | `PROVENANCE_DEFAULT_TRUST["james.stated"]`, `core/types.py:59` |
| classification | `INTERNAL` | `Taint.of()`'s default, `core/types.py:85` |

The value does **not** derive from the content that influenced the model. It is passed to
`transport_for()` at `write_path.py:483-484` and persisted through `I-111`'s write path at
`write_path.py:349-367`.

This is not a payload-injection defect: `I-111`'s guarantee that security metadata comes from the
plan and the token — never from the client payload — holds, and `test_17` proves it in two
independent layers. The metadata is correctly taken from the plan. The plan's value is the
question.

### 2. Reproduced laundering path

Measured, not theorised. Probe transcript, abridged:

```
0. note plan taint: provenance={'james.stated'}, trust=HIGHEST, classification=INTERNAL
1. seed a LOW-trust external.web item
   block taint with the web item present: LOW ['external.web', 'james.stated']   <- read half works
2. model emits [[PROPOSE_NOTE ref="laundered" body="<content derived from the web item>"]]
   turn: proposed
3. approval card text:
     action_text : Write item "laundered" in this scope.
     why_text    : Writing changes stored data. Reading it was autonomous; changing it is not.
     cost_text   : One row written or updated. No spend.
     if_wrong    : The item holds the wrong content until it is corrected.
     body column stored: '<the content>'      <- stored, never rendered
4. James approves. Persisted state:
     [('laundered', ['james.stated'], 3, 1, [])]        <- trust 3 = HIGHEST
5. delete the original untrusted source
   block taint now: HIGHEST ['james.stated']
   derived content still in model context: True
```

The cycle: content enters as `external.web` at LOW trust, is echoed into a proposed note, is
approved, is persisted as `james.stated`/HIGHEST, and survives the disappearance of its source —
returning to model context as high-trust content that no one stated.

**This is a provenance and trust laundering problem, not an exploit.** It requires no external
attacker, no compromise of the approval system, and no bypass of any control. Every step is the
system working exactly as written. The defect is that the label recorded at the end does not
describe the content it is attached to.

A second and more general form needs no untrusted item at all: the body inside
`[[PROPOSE_NOTE body="…"]]` is **model-generated text**, parsed from the provider's reply at
`conversation.py:87-88` and `conversation.py:320-372`. Under `I-20` and `I-99` that is
`model.generated` at LOW trust. Recording it as `james.stated` at HIGHEST asserts authorship
James never performed.

### 3. Consequence for `I-40` and the classification policy

The constant is **not only a storage-label problem**. Two authorization decisions read
`plan.taint`:

- `slice/core/policy.py:149` — `if plan.taint.is_untrusted_derived() and plan.declared_risk >
  Risk.PREPARE:` — the enforcement point for `I-40` (*"a plan influenced by untrusted content
  cannot exceed PREPARE without approval naming the source"*). With `plan.taint` fixed at
  `james.stated`, `is_untrusted_derived()` can never return true through this write path, so the
  branch is structurally unreachable.
- `slice/core/policy.py:121-127` — the external-transmission rule reads
  `plan.taint.classification`, which is always `INTERNAL`.

Both taint-sensitive policy decisions therefore operate on synthetic state. Whatever this ADR
decides governs authorization behaviour, not merely a stored column.

**Stated precisely, so it is not over-read:** `I-40` is **not** globally broken, and its
enforcement code at `policy.py:149` is correct. The claim is narrower and entirely about inputs —
**this shipped write path supplies synthetic trusted taint to the policy decision**, so the
untrusted-derived branch cannot activate through it. The same check is live wherever a plan
carries a derived taint; `planner.py:36` constructs exactly such a taint, and `runtime.py`
exercises the branch. The defect is the value handed to the check by `WritePath`, not the check.

### 4. An existing construction, offered as evidence — not as the answer

`slice/agent/planner.py:33-36` already implements a taint propagation model:

```python
base = input_taint or Taint.of("james.stated", classification)
# I-99: the Planner's output is a derivation of its inputs PLUS its own
# model.generated provenance, at the lowest trust among them.
plan_taint = base.derive("model.generated")
```

`Taint.derive()` (`core/types.py:106-113`) unions the input provenance with `model.generated` and
takes the **lower** of the two trust levels.

The shipped substrate does not use this path. `Planner` is wired only into `slice/runtime.py:55`;
`slice/substrate/app.py` imports neither `runtime` nor `Planner`, and the conversation and
approval flow reach the datastore exclusively through `WritePath.plan_for_action()`.

**This is evidence of an existing architectural direction. It is not an accepted decision for
approved writes, and this ADR does not treat it as one.** An approved write is a different event
from a planner's proposal: `I-09`'s human decision sits between them, and whether that decision
changes the answer is precisely the question here.

### 5. What the approval card actually shows

`slice/substrate/seam.py:758-790`, `_approval_card()`, renders exactly: risk class,
`action_text`, scope, `why_text`, `cost_text`, `if_wrong_text`, and `requested_by`. The proposal
body is stored in the `approval.body` column but is **not rendered**.

For a note, `action_text` is set at `approval_flow.py:110` to:

```text
Write item "{item_ref}" in this scope.
```

— an identifier, not the content. So for the note path the flow is: model-generated body →
stored on the approval row → approval card identifies the write without exposing the body → James
approves → persisted as `james.stated`/HIGHEST.

The ADR must therefore hold apart two things the current implementation conflates:

| | |
| --- | --- |
| **James approving an action** | a decision that a state transition may occur (`I-09`) |
| **James vouching for content** | a claim about the truth and origin of the exact bytes persisted |

**These are not equivalent, and this ADR must not assume they are.** An approval mechanism can
authorize an action without authenticating the factual provenance of what that action writes.

### The principle this decision turns on

> **Authorization to persist content and evidence about that content's provenance are two
> separate security properties.**
>
> An approval can establish that James authorized a state transition **without** establishing
> that James authored, verified, or endorsed the factual claims inside the payload. One is a
> decision about permission; the other is a claim about origin. A system may choose to let the
> first imply the second — but only deliberately, on stated evidence, and never by omission.

This separation is the substance of `I-110`. An invariant that forbids inferring trust from
"repetition, model confidence, consensus across model calls, internal origin, or the fact that
NOVA produced it" is an invariant about **what counts as evidence of trustworthiness**. "An
approval row exists" is a fact about permission. Whether it is also evidence about content is the
question this ADR exists to put to James, and the current implementation answers it *yes* without
ever having asked.

*(For completeness and not as part of this decision: the task path shows the title in
`action_text`, so it does not share the invisibility problem — but it persists no security state
at all. That is finding F-2, downstream of this ADR; see* **Scope boundaries** *.)*

---

## Current behaviour

| Stage | Where | Behaviour today |
| --- | --- | --- |
| Proposal | `conversation.py:87-90`, `:320-375` | Body/title extracted from model text |
| Plan construction | `write_path.py:413-423` | `taint = Taint.of("james.stated")` — constant |
| Approval record | `approval_flow.py:113-137` | Body stored; `action_text` names the write |
| Approval surface | `seam.py:758-790` | Body **not** rendered for a note |
| Authorization | `policy.py:121-127`, `:149` | Reads the constant taint |
| Persistence | `write_path.py:349-367` | Writes the constant into the five `I-111` columns |
| Retrieval | `conversation.py:158-200`, `:212-224` | Restores faithfully; withholds fail-closed |
| Block taint | `conversation.py:266-267` | `I-99` union of restored item taints over a `james.stated` base |

The retrieval and persistence machinery is correct. It is faithfully preserving a value that was
never derived.

---

## Why this is a C3 decision

`I-110` (`INVARIANTS.md`, added by Section 07, Accepted 2026-08-15) states:

> **Raising an item's trust is an explicitly authorized operation.** It is **never automatic,
> never performed by an agent, and never model-mediated**, and is never inferred from repetition,
> model confidence, consensus across model calls, internal origin, or the fact that NOVA produced
> it. **It is a `C3` change**, governed exactly as `I-30` governs downward reclassification.
> **Every promotion records seven things or does not happen** […]

Deciding that an approved write carries HIGHEST trust *is* a trust-elevation rule. Deciding that
it does not is a rule about the same subject. Either answer sets policy on the matter `I-110`
reserves as C3, and `IDENTITY_AND_AUTHORITY.md` Part II requires James's approval **and** an ADR
for a C3 change.

Three further reasons this cannot be an implementation detail:

1. It changes **authorization** behaviour, not only stored data (`I-40`, above).
2. Option C would impose a **UI obligation** on the approval surface — itself governed material.
3. It determines whether NOVA's own durable memory is treated as authoritative, which shapes
   every future capability that reads it.

---

## Decision question

> **When James approves a plan that writes an item, what provenance, trust and classification
> does the persisted item carry — and on what evidence?**

Stated more sharply: **is approval by itself sufficient evidence to elevate the trust of persisted
content, and if so, under what conditions?**

---

## Options considered

Presented as they were put to James, unedited after the decision. **Option C was chosen**; A and B
are retained in full, because the reasoning that rejected them is the reasoning that explains C.

### Option A — Approval confers trust

An approved write is recorded as `james.approved` (or an equivalent state) at high trust.
Approval becomes a trust-elevation event.

**Consequences**

- Approval acquires a **new security meaning**: it stops being only "may this happen?" and
  becomes "this content is trustworthy". That change cannot be made silently.
- The approval card must arguably expose enough of the content for the elevation to mean
  anything; otherwise the system records an endorsement James had no opportunity to give.
- `james.approved` must be **defined**: today it exists in `PROVENANCE_DEFAULT_TRUST`
  (`core/types.py:60`) at `Trust.HIGHEST` with no rule saying when it may be assigned.
- `I-110`'s **seven-item evidence record** would apply, since this is a promotion.
- Model-derived content **regains high trust** by passing through an approval — which is the
  laundering path made lawful rather than closed. That may be an acceptable, deliberate answer;
  it must not be an accidental one.
- `I-40` would continue never to fire on the write path.

### Option B — Approval authorizes the action but does not elevate content trust

The persisted item keeps its derived taint — for example the existing direction
`input_taint → derive("model.generated")` — preserving provenance and the lower trust.

**Consequences**

- Approval answers *"may this write happen?"* and nothing more. `I-09` is unweakened; `I-110` is
  untouched because no promotion occurs.
- Model-generated content stays **distinguishable after persistence**, which is what `I-111` says
  persistence is for.
- `I-40` becomes live on the write path: a plan derived from `external.web` would need an
  approval naming the source before exceeding `PREPARE`. This is a **behaviour change** — writes
  that succeed today may begin to require more.
- The most conservative reading of provenance, and the cheapest to implement.
- **Product consequence that must be faced honestly:** NOVA accumulates approved memories that
  are never treated as authoritative facts. Downstream capabilities gated on trust would find
  their own database mostly low-trust, and `I-100`'s untrusted-derived ceiling would apply
  broadly. Whether that is correct rigour or an unusable product is a judgement for James.

### Option C — Hybrid: trust elevation only where the content was shown and approved — **CHOSEN**

Elevation is permitted **only** when the exact content persisted was displayed on the approval
surface and explicitly approved, with the approval evidence bound to that content.

**This option is not "show the body on the approval card."** Display is one of five properties,
and on its own it proves nothing — a card that shows one body while the write path persists
another would be worse than showing nothing, because it would manufacture evidence. The security
semantics of content-visible approval are:

| # | Property | What it rules out |
| --- | --- | --- |
| 1 | The exact content to be persisted is **identifiable** — there is a determinate answer to "which bytes does this approval cover?" | An approval covering "a note", loosely |
| 2 | James can **inspect that content** before deciding | Endorsement of material never seen |
| 3 | The approval is **bound to that exact content**, via plan identity | Approving one thing and writing another |
| 4 | The trust elevation is **attributable to that approval evidence** — the record says *this* approval, of *this* content, is why the trust is what it is | Trust that no one can trace to a decision |
| 5 | **Changing the content after approval invalidates the approval** | Post-approval substitution, including by a concurrent or later caller |

These are stated as **security semantics, not as an implementation prescription**. How they are
satisfied is an implementation question that follows acceptance. It is worth noting that NOVA
already possesses most of the machinery: `I-112`'s deterministic plan identity covers the tool
*and* its arguments, and `approval_flow.py:193-197` reconstructs the plan at decision time and
refuses if the identity differs — which is properties 3 and 5 already working for arguments.
Property 4 is the genuinely new obligation, and it is where `I-110`'s seven-item record would
attach.

**Consequences**

- The strongest claim that a high-trust label reflects genuine human endorsement.
- Requires **UI change**: `_approval_card()` (`seam.py:758-790`) must render the full body, with
  the display questions that follow (length limits, escaping, truncation — and a truncated body
  is not an approved body).
- Requires defining **precisely what content the approval covers**, and binding it to plan
  identity so that the approved bytes and the written bytes are provably the same. `I-112`'s
  reconstruct-and-compare already binds arguments to the plan identity, so the mechanism exists
  and would need extending rather than inventing.
- Creates **two classes of write** — content-visible (may elevate) and content-opaque (may not) —
  which must be defined so the boundary is not decided case by case by whoever adds the next
  tool.
- More work than A or B, but it is the only option that does not require either treating unseen
  model output as James-authored or accepting a permanently low-trust memory.

### Other variants (noted, not developed)

- **A deferred or two-stage promotion**: persist at derived trust, with a separate explicit
  promotion operation satisfying `I-110`'s seven-item record. Keeps write and promotion distinct
  at the cost of a second surface.
- **Provenance union without elevation**: record both `james.approved` *and* the derived
  provenance, letting `I-99`'s lowest-trust rule decide. Honest about what happened; may make
  `james.approved` a label with no effect.

These are recorded so they are not lost. Developing them is out of scope unless James asks.

---

## Comparison / tradeoffs

Recorded as it was put to James. Column C is the accepted option; the other two columns are kept
so the tradeoff that was accepted remains legible.

| # | Criterion | A — approval confers trust | B — no elevation | C — hybrid, content-visible |
| --- | --- | --- | --- | --- |
| 1 | **Provenance honesty** | Weak — records endorsement possibly never given | Strong — records what actually produced the bytes | Strong, *if* display is genuinely complete |
| 2 | **Trust semantics** | Approval = trust; simple, and a large claim | Approval ≠ trust; conservative | Trust follows evidence of human review |
| 3 | **Classification** | Must be decided explicitly; today it is `INTERNAL` by an argument default (`types.py:85`) while the retrieval block is `CONFIDENTIAL` (`conversation.py:266`) | Inherited from the input taint, so it follows `I-27`'s strictest-wins rule without a new choice | Inherited as in B; a visible approval is evidence about trust, not about sensitivity — so classification should probably not follow the same rule as trust |
| 4 | **`I-110` compliance** | Requires the seven-item record; is a promotion rule | Compliant by construction — no promotion occurs | Compliant if evidence is recorded per `I-110` |
| 5 | **`I-40` / taint-policy effectiveness** | Stays inert on the write path | Becomes live; may restrict writes that pass today | Live for opaque writes; suppressed where James saw the content |
| 6 | **What James is actually approving** | Ambiguous — the action, read as the content | The action, unambiguously | The action *and* the content, explicitly |
| 7 | **Auditability** | Needs `I-110`'s seven items | Little new evidence needed | Must bind approved bytes to plan identity — most evidence, most defensible |
| 8 | **UX implications** | None immediately — which is part of the objection | None | Approval surface must change; longer, denser cards |
| 9 | **Implementation complexity** | Low | Low–moderate (plumb context taint into the plan) | Highest (UI + binding + two write classes) |
| 10 | **Future delegation implications** | A delegate's write could reach HIGHEST via one approval | Delegate writes stay derived; consistent with `I-107` ancestry handling | Delegates likely fall in the opaque class — conservative by default |
| 11 | **Effect on durable memory** | Memory becomes broadly authoritative — and broadly launderable | Memory is honest but rarely authoritative | Memory is authoritative exactly where a human looked |

---

## Required decision criteria

The ten criteria above are the axes on which this decision should be judged. They are listed as
criteria, not as a scoring system: **no weighting is proposed**, because choosing the weights is
itself part of the decision James is being asked to make.

---

## Explicit questions for approval

These were the questions put to James. **Questions 1–4 are answered by the accepted decision:**
approval authorizes the state transition and constitutes evidence about content *only* under the
five properties (Q1); James is not recorded as the provenance source for content he did not author
unless that content was content-visible and bound (Q2); the five properties *are* the evidence
that makes elevation valid (Q3); and yes, the exact content must be inspectable before approval
(Q4).

**Questions 5–10 remain open and belong to implementation design**, now bounded by Option C rather
than unbounded. They are retained verbatim so the implementation task inherits them.

1. Does approval authorize **only the state transition**, or does it also constitute **evidence
   about the truth and provenance** of the content?
2. Can James legitimately be recorded as the **provenance source** for content he did not
   personally author?
3. If approval can elevate trust, **what exact evidence** makes that elevation valid?
4. Must the **exact content be shown** on the approval surface for an elevation to be valid?
5. What **provenance label** represents approved model-generated content — `james.approved`,
   `model.generated`, a union of both, or something new?
6. What **trust level** should that content receive?
7. What **classification** should it receive, and derived from what? (Today it is `INTERNAL` by
   an argument default, while the retrieval block is `CONFIDENTIAL` — `conversation.py:266`.)
8. Should an approved write remain **distinguishable** from a direct James-authored statement?
9. Should downstream policies such as `I-40` treat approved model-derived content as **trusted or
   derived**?
10. What **audit evidence** is required for a trust elevation — is `I-110`'s seven-item record the
    standard here, or does an approval-based elevation need its own?

---

## Scope boundaries

This ADR decides **one thing**: the provenance, trust and classification of an item written
through an approved plan.

It explicitly does **not** decide:

- **task provenance or task schema changes** (finding F-2) — see *Dependencies* below;
- **the production revocation surface** or its API;
- **`I-74` in-flight execution kill**, or its separation from durable `S7-D5` revocation;
- **delegation semantics**, including whether delegate-written items should remain withheld;
- **migration guard hardening** (the unqualified `table_name` predicate in `schema.sql:295-297`);
- **one-authority/one-scope database constraints** — the post-merge review recommended *against*
  a schema constraint, and nothing here revisits that;
- **test coverage cleanup**;
- **planner/runtime wiring** — `planner.py` is cited as evidence of direction only. Whether the
  substrate should route through `Planner` is an implementation question that follows this
  decision and does not precede it.

### This decision applies PROSPECTIVELY only

**Ruled by James, 2026-08-24, when the implementation design surfaced the question.**

Items persisted **before** the ADR 0048 implementation lands are **left exactly as stored**. They
are not retroactively reclassified, downgraded, rewritten, backfilled, marked, or migrated, and no
agent reinterprets the historical approvals behind them. They are legacy state and they stay as
they are.

The reason is jurisdictional, not cosmetic: changing the trust of already-stored data is
**downward reclassification, which `I-30` governs and which `I-110` says is C3** — *"never
automatic and never performed by an agent"*. That is a separate decision from this one, and it has
not been made. Folding it into this implementation would turn an accepted write-path decision into
an unauthorized retroactive data-reclassification project.

Existing `approval` rows carry no proposed taint. They remain executable and **can never elevate**:
absent evidence is unknown, and unknown is not a licence. No backfill, and no destructive
migration.

---

## Dependencies / downstream work

**Blocked by this ADR** (do not start until it is accepted):

- **F-2, task provenance.** Tasks persist no security state (`schema.sql:225-235`,
  `write_path.py:305-311`) and reach model context under the `james.stated` base
  (`conversation.py:243-246`, `:266-267`). **The approved-write decision is a prerequisite for
  deciding how persisted task titles should be classified, because tasks combine mutable control
  state with model-authored textual content.** A `due_on` date is NOVA's own control fact; a
  title is the model's prose; they live in one row, and the row changes after creation
  (`COMPLETE_TASK`, `ON CONFLICT DO UPDATE`). Withholding a task additionally hides it from the
  model while `AttentionService` still surfaces it — an incoherence items do not have. **This ADR
  does not decide any of that, and proposes no task columns and no change to task behaviour.**
  It belongs in a separate ADR, downstream of this one.
- Any change to `WritePath.plan_for_action()`, `_approval_card()`, or the `I-40` evaluation path.

**Independent of this ADR** (C1, may proceed separately if James wishes):

- A regression test for the `len(scopes) > 1` fail-closed branch in `revocation.py:91-95`.
- Schema qualification of the migration guard.
- Retitling or rewriting `test_02` and `test_04`, which claim to cover union provenance but only
  assert a database round-trip — and would pass unchanged under the constant described here.

---

## Status and next step

**Status: `Accepted` — 2026-08-24, by James, at the ADR Decision Gate.** The decision is made.
**No code has been changed, and none should be until implementation is separately planned.**

**Current state of the system.** `main` @ `e7bd2fa` stands as-is and still exhibits the **F-1
behaviour documented above**: `WritePath.plan_for_action()` carries a constant
`Taint.of("james.stated")`, every approved item persists as `james.stated`/`HIGHEST`/`INTERNAL`,
and the note approval card does not expose the body. **Accepting this ADR did not close that
gap** — it decided what closing it must look like. F-1 remains open until implementation lands.

There is no emergency. Every write remains behind `I-09`'s approval gate, no production
integration currently writes untrusted content, and the merged `I-111` read half continues to
withhold anything unestablishable.

**Next step:** implementation design against the five properties, in a separate task. It must
determine — within Option C, and subject to `I-110`'s existing requirements — which provenance
label represents approved content, what trust level and classification it carries, what makes an
approval content-visible for each tool, and what audit evidence records the elevation. Nothing in
this ADR authorizes a specific mechanism.

---

## Date

**2026-08-24** — proposed and accepted. Option C chosen by James.

---

## References

**Invariants:** `I-09`, `I-20`, `I-40`, `I-99`, `I-100`, `I-107`, `I-110`, `I-111`, `I-112` —
[`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md)

**ADRs:** [0032](./0032-trust-promotion-authority.md) (trust promotion authority),
[0033](./0033-section-07-amendments-to-accepted-architecture.md) (`I-110`/`I-111`),
[0034](./0034-the-plan-is-a-security-object.md) (the plan as a security object),
[0006](./0006-risk-classified-approvals.md) (risk-classified approvals),
[0008](./0008-architectural-governance-model.md) (the five governance classes)

**Architecture:** [`../architecture/IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md)
Part II (governance classes), [`../architecture/AUTHORIZATION_MODEL.md`](../architecture/AUTHORIZATION_MODEL.md)

**Code, at `main` @ `e7bd2fa`:**

```text
slice/substrate/write_path.py:413-423   plan_for_action -- the constant taint (line 421)
slice/substrate/write_path.py:483-484   the taint passed to the transport
slice/substrate/write_path.py:349-367   the I-111 item write
slice/core/policy.py:121-127            external-transmission rule, reads plan classification
slice/core/policy.py:149                I-40 enforcement, reads plan.taint
slice/agent/planner.py:33-36            the derive() construction (evidence, not decision)
slice/substrate/seam.py:758-790         _approval_card -- what James sees
slice/substrate/approval_flow.py:110    action_text for a note write
slice/substrate/conversation.py:87-90   the proposal markers parsed from model text
slice/substrate/conversation.py:158-200 _establish -- I-111's read half
slice/substrate/conversation.py:266-267 the block taint union
slice/core/types.py:58-69               PROVENANCE_DEFAULT_TRUST
slice/core/types.py:106-113             Taint.derive
```
