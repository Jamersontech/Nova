# 0052 — Authority Revocation Is an ApprovalService Act on an Item or Task

**Status:** **Accepted** — 2026-08-27
**Proposed:** 2026-08-26 — drafted by an agent on James's F-3 ruling of 2026-08-26
**Accepted:** 2026-08-27 — by James, at the ADR Decision Gate, on the corrected text below and
the two merged prerequisites it records. **Acceptance settles the ARCHITECTURE only.**
Implementing `F-3` requires a separate, explicit authorization that has not been given
**Section:** 07 — gives `S7-D5` a production surface; governed by `MEMORY_MODEL.md` §4 rule 8
**Resolves:** `F-3`, and `F-4` as a bundled consequence
**Depends on:** [ADR 0051](./0051-revoked-authority-is-labelled-not-withheld.md) (`F-13`), which had to
land first — until it did, creating a revocation made content *disappear* where rule 8 requires it
retained

> **`F-3` IMPLEMENTATION IS NOT AUTHORIZED.** The act model, selection target, `I-92` reading and
> audit path are decided and stable, and **both technical prerequisites are now SATISFIED** —
> step-up merged in `d6a0d45`, the shared establishment extraction merged in `d1f5763`.
>
> **What remains is governance, not capability.** `F-3` awaits acceptance of this ADR and a
> separate implementation authorization; neither has occurred. See
> **[Prerequisites and authorization](#prerequisites-and-authorization)**. `F-4` and `F-14` are
> bundled into `F-3` and remain unauthorized with it.

## Decision

**Revocation of an execution authority is a consequential action proposed from the row it
concerns and decided by James through the existing ApprovalService.** Ruled by James, 2026-08-26.

Seven elements, each binding:

1. **Act model — ApprovalService.** James's UI action *proposes*; the existing
   `ApprovalService` → PDP `authorize_plan` → `ToolPEP` → `CredentialBroker` → Data-Access
   Boundary → RLS `WITH CHECK` machinery *performs* it. **No second direct consequence path is
   created.**
2. **Selection target — the item or task row.** James selects the specific note or task. NOVA
   derives `creating_authority` from that row. **The opaque `trace_id` is never the primary
   human-facing identifier.**
3. **`F-9`'s authority-scope derivation remains binding**, unchanged and byte-for-byte.
4. **Reversibility — `F-3` ships with revocation ONLY.** *(Ruled 2026-08-26, superseding the
   earlier "revoke + superseding authority" ruling for this implementation.)* Supersession is
   **deferred to a separate future ADR**. Neither `schema.sql` nor `F-13`'s read path is modified
   to force reversibility into `F-3`. **The revocation this implementation creates is therefore
   PERMANENT.**
5. **`I-92` — its "revocations" means CONTROL-PLANE revocations**, not `S7-D5` client-scoped
   authority revocation. **No `W-3` partition is created.**
6. **`F-14` — re-resolve at the decision boundary, over a SHARED establishment module.**
   ApprovalService freshly determines current revoked-authority state before the consequential
   decision. Model-carried metadata is not trusted; revocation enters neither provenance nor
   trust. **The five establishment rules are not duplicated** — `_establish` is lifted into a
   shared module. That extraction was a separately authorized prerequisite, not part of this
   ADR; it has since been implemented and merged (`d1f5763`).
7. **`I-67` — step-up APPLIES.** *(Ruled 2026-08-26, reversing the earlier "no step-up" reading.)*
   Because element 4 makes this revocation permanent, the act is `IRREVERSIBLE` and `I-67`
   engages. **`I-67` is not reinterpreted or weakened to unblock `F-3`.**

   **The governing authority is `I-67` + `A-3` + [ADR 0018](./0018-authentication-model.md)
   (Accepted).** ADR 0018 decided consequence-scaled step-up on 2026-08-13; `A-3` states it;
   `I-67` mints it. **`ADR 0046`'s status was never the blocker** — it selected the *mechanism*.
   Step-up has since been built to that mechanism and merged (`d6a0d45`), and `ADR 0046` is
   Accepted with its limitation 3 updated to describe the implemented state.

**`F-4` is bundled and requires no bespoke audit write.** `F-4` and `F-14` are **downstream of
`F-3` and must not be implemented independently of it.**

---

## The question

`RevocationRegistry` has existed since `S7-D5` and has **never had a production caller**. It is
constructed at `app.py:160`, held at `seam.py:117` as `self._revocations`, and that attribute is
**never read anywhere**. `revoke()` has zero callers outside tests. So `MEMORY_MODEL.md` §4 rule 8
— *"an item created under an authority later revoked is retained and its revocation state exposed
at retrieval"* — describes a state NOVA cannot enter.

`F-13` built the reading half. This builds the writing half.

## What revocation actually is

The single fact that shapes every element below, and the one most likely to be misread:

> **The execution identity James revokes is already dead.**

`creating_authority` is `token.trace_id` (`write_path.py:468`, `:543`), and
`trace_id = uuid.uuid4().hex` (`context_service.py:122`). `AUTHENTICATION_MODEL.md` §5: *"An
execution identity is valid for one execution, in one context, until it completes or expires.
There is no refresh."* `I-107` restates it: *"execution identities are ephemeral and never
reused."*

So `I-74`'s *"in-flight executions holding a revoked token fail closed at their next enforcement
point"* is **vacuous** for a completed execution. Revoking one stops nothing, withdraws no access,
and closes no session.

**Its only effect is `S7-D5`'s retrieval label.** Revocation here is an *epistemic* act about
stored content — "stop treating what this execution wrote as unimpeached" — not an access-control
act. `I-67`, reversibility and audit placement all follow from that, and each is decided below on
that basis rather than by analogy to grant or session revocation, which are different acts under
`ADR 0021`.

## 1. Act model — ApprovalService

**Rejected: a direct James act.** It would need a new authorization path (`authorize_data_read` is
the wrong decision; `authorize_plan` presumes a plan), a new audit record, a new surface, and —
decisively — **a second route from a human click to a durable consequence**, beside the only one
that exists. `I-09` would not be engaged at all, because James acting is not James approving.

**Accepted: an ApprovalService act.** Everything the act needs already exists and applies
unchanged:

| Property | Mechanism, already present |
| --- | --- |
| Only James decides | `I-09`; `decide()`'s single-use claim on `consumed_at IS NULL` |
| The decision binds this exact action | `I-109` (nine properties + execution binding), `I-112` (plan identity re-derived from stored arguments) |
| Consequence-determining arguments are pinned | `I-100`, via `ArgumentEnvelope` built from the tool's own declaration |
| Authorization is re-run at execution | `authorize_plan`'s ten steps, `ToolPEP`, `CredentialBroker` |
| The write cannot leave its scope | Data-Access Boundary + RLS `WITH CHECK` |
| Audit | `W-2` decision record, `W-1` execution record, same transaction |
| Crash recovery | `ApprovalService.recover()`, for free |

**The act is `Risk.IRREVERSIBLE`**, which follows from element 4 making the revocation permanent
and is what element 7's `I-67` engagement rests on. It is therefore **unlike** all four existing
tools, every one of which declares `Risk.EXECUTE`. That difference is not cosmetic — it is what
the merged step-up gate keys on, and it carries an implementation requirement recorded under
[Implementation consequences](#implementation-consequences).

*(Corrected 2026-08-27. This sentence previously read "the act is `Risk.EXECUTE`" — a leftover
from the first draft, when element 7 read "no step-up". Element 7 was reversed on 2026-08-26 and
this line was not carried with it. The ruling is unchanged; only this restatement of it was
wrong.)*

One objection, answered: routing James's own authority act through a proposal he then approves
reads oddly when nothing proposed it. It resolves the way `seam.write_item` already resolves —
`propose_action` is a server call, not a model call; James's click proposes and his approval
decides. **No model is involved in a revocation at any point** (`I-101`, `I-102`).

## 2. Selection target — the item or task row

James points at *the note or task he no longer trusts*. NOVA reads `creating_authority` off that
row, through his own bound channel.

**Why not the alternatives.** The `trace_id` itself is an opaque `uuid4` that means nothing to a
person; a dedicated "authorities" list is the same UUIDs behind a new page and a new concept the
UI does not have; the activity card is workable but its `detail` text is terse. The item/task row
is the only target where **F-9's authority-scope rule is satisfied by construction** — the row's
own `scope_path` *is* the authority's scope — and the only one already rendered
(`_notes_card`, `_tasks_card`).

**The identity is pinned at PROPOSAL time, not derived at execution.** The approval's arguments
carry `execution_identity` alongside the human-meaningful `target_ref`. This is required, not
incidental: `I-109`/`I-112` bind the *arguments*, not a value derived from them later, so
deriving the authority at execution would let an intervening overwrite of the row point James's
approval at a **different authority than the one he was shown**. Pinning it makes that impossible
— and if the row is overwritten in between, `F-9`'s derivation finds no rows for the pinned
identity and **fails closed**, which is the correct outcome.

**Storing the UUID in the approval row is not exposing it.** Element 2 forbids it as the *primary
human-facing identifier*; the card names the note or task, and the UUID never reaches a rendered
surface.

Both arguments are `CONSEQUENCE`. `content_leaves` therefore returns empty — revocation persists
no prose, exactly as `complete_task` and `add_scope` persist none — so no ADR 0048 elevation is
possible and none is offered.

## 3. `F-9` remains binding

`revoke()`'s `UNION` derivation over `item` and `task`, its `len(scopes) != 1` fail-closed
denial, and its refusal to accept a caller-supplied scope are **unchanged, byte-for-byte**. At
execution it runs a second, independent derivation and must agree with the identity pinned at
proposal. Two independent derivations that must agree is stronger than either alone.

### Coverage limitation, stated rather than fixed

`F-9` derives an authority's scope from rows carrying `creating_authority`. Three classes of
authority therefore **cannot be reached from any item/task row**:

- an execution that ran only `complete_task` — it writes `done_at` alone (`write_path.py:511`)
  and stamps no authority;
- an execution that ran only `add_scope` — `scope` carries no `I-111` columns (ADR 0050);
- the **earlier** authority of an overwritten row — both upserts set
  `creating_authority = EXCLUDED.creating_authority`, so the column records the **last** writer,
  not every writer.

Each fails closed: `revoke()` finds no rows and denies. **This does not block `F-3`.** It is a
property of `F-9`'s derivation, not of this surface, and closing it means a durable execution
registry — a materially larger `C3` decision that must not ride along here. **Recorded as an
accepted limitation.**

## 4. Reversibility — `F-3` ships with revocation only

**Ruled: revocation only. Supersession is deferred to a separate future ADR.** Neither
`schema.sql` nor `F-13`'s read path is modified to force reversibility into `F-3`. **The
revocation this implementation creates is permanent.**

This reverses the direction of the packet that preceded this ADR, and it does so on evidence
rather than preference. "Revoke + superseding authority" is **not representable** under the
constraints the ruling itself sets — `authority_revocation.execution_identity` is
`text NOT NULL UNIQUE` (`schema.sql:377-383`), permitting at most one row per identity ever, and
every alternative representation requires a schema change, an `UPDATE` privilege the ruling
forbids, or reopening `F-13`'s read path. The full analysis is retained under
**[Prerequisites and authorization](#prerequisites-and-authorization)** because it governs the
deferred ADR.

Rather than bend the schema or `F-13` to fit, `F-3` takes the representable option and the cost
is **stated, not hidden**: a mistaken revocation cannot be undone by this implementation, and —
since nothing surfaces the registry to James — it is unfixable *and* invisible. That cost is what
element 7 then prices.

The architecture had **never decided reversibility**. Recorded plainly because the absence was
itself the finding: `IDENTITY_AND_AUTHORITY.md` contains no occurrence of "revocation" or
"revoke"; nothing in `docs/` mentions un-revoking, reinstating or restoring; `ADR 0021` governs
*when* revocation bites for grants, delegations, sessions, bindings and tokens, and never whether
it can be undone; and the schema has no status column. **Permanence was never inferred from the
absence of `DELETE`** — that grant posture is a durability property, and `revocation.py:29` says
so in terms. It is ruled here, for this implementation, and is open for the deferred ADR to
revisit.

## 5. `I-92` — control-plane revocations, not this one

`I-92` lists *"revocations"* among operations recorded in *"a control-plane audit partition that
is not a node in the client scope tree"*, which *"must not carry client-scope content,
identifiers, or resource references"*.

**Ruled: that means control-plane revocations** — grants, delegations, sessions, credential
bindings — **not `S7-D5` authority revocation.**

The reading is sound on three grounds. `I-92`'s own qualifier is *"operations that concern no
client scope"*, and this one concerns a client scope in every respect: `F-9` requires the record
to land at the authority's own client scope, and the effect is visible only in that scope's
retrieval. `I-92` is Section 04; `S7-D5` is Section 07 and did not exist when it was written.
And the alternative reading is self-defeating — a partition forbidden to carry client-scope
identifiers cannot record an act whose entire content *is* a client-scope identifier.

**Consequence: no `W-3` partition, no new audit table, no schema change.** The existing
`audit_record` table and the `W-1`/`W-2` writers carry it.

## 6. `F-14` — re-resolution at the decision boundary

`ADR 0051` located the consuming-authority decision *"at the authorization and approval boundary,
when a consequential action is considered."* It does not arrive there: `_scope_context` returns
`(text, taint)`, the per-row `revoked` flag never leaves the method, and `Taint` has no revocation
axis by design. So the label reaches the model — which decides nothing (`I-101`, `I-102`) — and
reaches nobody who does.

**Ruled: re-resolve, do not carry.** ApprovalService freshly computes current revoked-authority
state from the durable registry, through the approver's own bound channel, and surfaces it to
James before he decides.

Chosen over carrying the fact forward as approval metadata because re-resolution **trusts nothing
that passed through the model**, is **fresh** — an authority revoked between proposal and decision
is caught, which is precisely when James has just revoked something — and needs **no new column
and no new persistent state**.

Stated honestly: re-resolution answers *"does the scope this proposal was built from currently
contain revoked-authority content?"*, not *"did revoked content influence this specific
proposal?"*. It can over-report. **Over-reporting to the decider is the fail-safe direction, and it
never under-reports** — the alternative can under-report, which is the direction that matters.

`UNKNOWN` and `REVOKED` stay distinct, on the same reasoning `ADR 0051` gave: an unestablishable
row is reported as unknown and **never** as "not revoked".

### The rules are shared, not duplicated

**Ruled: `_establish` is lifted into a shared module that both `conversation.py` and
`approval_flow.py` import.** Re-stating the five establishment rules inside `approval_flow.py`
would create two definitions of "establishable" that can drift — the exact hazard `F-13`'s single
`_mark()` constant was created to prevent, and a drift that would silently make the decision
boundary disagree with what the model was shown.

A direct import cannot achieve this: `conversation.py` already imports `ApprovalService`, so
`approval_flow.py` importing `_establish` back is **circular**. The extraction is therefore a real
architectural change, not a refactor of convenience.

**It was a separately authorized prerequisite and was NOT performed by this ADR.** It has since
been done under its own authorization and merged (`d1f5763`), with the function moved verbatim and
`F-13`'s behaviour unchanged — see
**[Prerequisites and authorization](#prerequisites-and-authorization)**.

## 7. `I-67` — step-up applies, and was built before `F-3`

> `I-67` / `A-3`: *"`IRREVERSIBLE` actions and changes to grants, policy, classification, or
> credentials require fresh authentication, not merely a valid session."*

Revoking a completed execution identity is **not** a grant, a policy, a classification, or a
credential change — it withdraws no access from anything, because there is nothing left to
withdraw it from (see *What revocation actually is*). The second clause does not reach it.

**The `IRREVERSIBLE` clause therefore governs alone, and element 4 answers it: the revocation
`F-3` creates is permanent, so the act is `IRREVERSIBLE` and `I-67` engages.**

Element 4 and element 7 stand or fall together, and element 4 fell. The earlier reading — that
revocation is `Risk.EXECUTE` because superseding authority makes it reversible in principle —
**depended on a mechanism that cannot ship in `F-3`.** A capability that is decided but unbuilt
does not make an act reversible.

`I-67` is **not reinterpreted, narrowed, or weighed against convenience to unblock `F-3`.** The
argument that revocation "withdraws no access, so the risk is low" is real and is recorded above,
but it addresses the *second* clause, not the `IRREVERSIBLE` clause, and an irreversible act is
irreversible whatever its blast radius.

### Where the blocking authority comes from

**`I-67` + `A-3` + [ADR 0018](./0018-authentication-model.md), all accepted.** ADR 0018 was
accepted on 2026-08-13 and already decided this:

> *"strength scales with consequence: `IRREVERSIBLE` actions and changes to grants, policy, or
> credentials require **fresh** authentication, not merely a valid session"* — and its chosen
> option was *"Multi-factor baseline with consequence-scaled step-up."*

So step-up is an **accepted architectural obligation that has never been implemented**, not a new
decision. `A-3` states it; `I-67` mints it; `ADR 0046` selected the mechanism (WebAuthn).

**`ADR 0046`'s status was not, and never was, the blocker.** It supplies the *mechanism*
(WebAuthn passkeys), not the obligation. At the time this ADR was drafted its limitations table
also recorded that step-up was unbuilt — a statement about the codebase, corroborating evidence
rather than authority.

**That is no longer the state.** `F-3` would be NOVA's **first** `IRREVERSIBLE` path, so the
limitation stopped being true the moment step-up shipped. Step-up was built to `ADR 0046`'s
mechanism and merged in `d6a0d45`; `ADR 0046` is **Accepted (2026-08-26)** and its limitation 3
was rewritten at that point to describe the implemented state — that step-up exists for
`IRREVERSIBLE` decisions, that ordinary session strength remains fixed at login, and that no
freshness state is persisted.

**No authentication mechanism is designed or implemented by this ADR.** Building step-up was
`C1`/`C2` implementation of the already-accepted ADR 0018 requirement, under ADR 0046's
already-selected mechanism — see
**[Prerequisites and authorization](#prerequisites-and-authorization)**.

## `F-4` — bundled, with no bespoke audit write

`revoke()` writes no audit record today. Under this decision it does not gain one.

The existing machinery already produces every required field:

| Required | Source |
| --- | --- |
| Actor identity | `token.actor` / `decided_by` — deterministic, never caller-asserted |
| Execution identity revoked | the pinned `execution_identity` argument |
| Authority scope | `F-9`'s derived `authority_scope`, not the revoker's |
| Timestamp | `written_at DEFAULT now()` |
| Action | the tool name |
| Target | `target_ref`, in `detail` |
| Result | recorded, or the denial |
| Same transaction | **yes** — the `W-1` write shares the transaction with the registry `INSERT` |

`W-2` is the PDP's own decision record (`policy.py:254`). `W-1` is written with
`execution_event_identity(trace_id, scope_path, tool_name, ref)` in the same transaction as the
side effect (`write_path.py:552`). `I-49` is satisfied: the record lands in the authority's own
scope, which is the scope touched. `I-93`'s fail-closed rule applies unchanged.

**Adding a bespoke write inside `revoke()` would give one act two event identities** and break the
property `recover()` depends on — that evidence exists under exactly one derivable identity.
**Forbidden by this decision.**

**`F-4` is bundled into `F-3` and remains unauthorized with it.** It has no independent implementation: the
records above are produced by the ApprovalService path that `F-3` builds, so there is nothing for
`F-4` to write until that path exists. **`F-4` must not be implemented independently of `F-3`** —
doing so would mean adding the bespoke write this section forbids.

The same holds for **`F-14`**, for a different reason: it re-resolves state at the decision
boundary of a revocation approval, and until `F-3` can create a revocation there is no state to
re-resolve. **`F-14` must not be implemented independently of `F-3`** either.

## Non-goals

- **No durable execution registry.** The coverage limitation above is accepted, not fixed.
- **No human-facing revocation *review* surface** — no list of revocations, no registry browser.
  This creates one act, at one row.
- **No `W-3` control-plane audit partition.**
- **No step-up mechanism is designed or implemented here.** `I-67` applies (element 7);
  satisfying it was a separate work item — `C1`/`C2` implementation of the accepted ADR 0018
  requirement, not a new `C3` decision — and it has since been done and merged (`d6a0d45`).
- **No supersession, restore or un-revoke mechanism** — deferred to its own ADR (element 4).
- **No extraction of `_establish`** — a separately authorized prerequisite (element 6), since
  implemented and merged (`d1f5763`).
- **No revocation of grants, sessions, delegations or credential bindings.** Those are `ADR 0021`
  and remain untouched.
- **No cross-scope revocation.** An authority outside the revoker's reach is not revocable by
  them, which `revocation.py:92-95` already records as the correct answer.
- **No backfill and no retroactive reclassification.**
- **No change to what the model is shown.** `F-13`'s block is untouched.
- **Revocation still enters neither `provenance` nor `trust`** (`I-38`, `ADR 0051`).

## Affected invariants and ADRs

**Implemented, not amended:** `S7-D5`; `MEMORY_MODEL.md` §4 rule 8; `ADR 0033` §4; `ADR 0051`.

**Applied unchanged:** `I-09`, `I-49`, `I-74`, `I-93`, `I-100`, `I-101`, `I-102`, `I-107`,
`I-109`, `I-110`, `I-111`, `I-112`, `I-114`; `ADR 0036`, `ADR 0045`, `ADR 0048`.

**Interpreted, not amended:** `I-92` — see element 5. This is the one place this ADR reads an
accepted invariant narrowly, and the reading is recorded so it can be challenged.

**Engaged, and NOT reinterpreted:** `I-67` — see element 7. It was satisfied by building
step-up, never by being read down to permit `F-3`.

**The governing authority, named:** `I-67` + `A-3` + **`ADR 0018` (Accepted 2026-08-13)**.
`ADR 0046` supplies the *mechanism*, which step-up was built to.

**Untouched by this ADR:** `INVARIANTS.md`, `MEMORY_MODEL.md`, `KNOWN_RISKS.md`, `ROADMAP.md`,
`ADR 0018`, `ADR 0021`, `ADR 0046`, `ADR 0050`, `ADR 0051`. `ADR 0046` limitation 3 was revised by
the step-up work item, not by this ADR.

**Preserved byte-for-byte:** `F-9`'s guard and denial; `F-10`'s scope-pinned `UPDATE`; `F-11`'s
base taint; `F-12`'s scope predicates; `F-13`'s `_REVOKED_MARK` and `_mark()`.

## Implementation consequences

**None of this is authorized yet** — see
[Prerequisites and authorization](#prerequisites-and-authorization). Recorded so the work can be
scoped against a known shape, not so it can be built.

- `write_path.py` — one `revoke_authority_tool()` `ToolDefinition` declaring
  **`Risk.IRREVERSIBLE`**, one `transport` dispatch branch, one `REF_ARGUMENT` entry, **and the
  risk-class propagation below**.
- `approval_flow.py` — `F-14` re-resolution, exposed to the render path and re-run at decision.
- `seam.py` — a control on each note/task row, one POST route, one confirmation page; and
  `self._revocations`, currently assigned and never read, becomes read.
- `app.py` — register the tool in the `ToolRegistry`.
- `revocation.py` — called from the write path. `revoke()`'s body is expected to be **unchanged**;
  `I-74`'s in-memory `ContextService.revoke()` remains part of it.
- **`schema.sql` is not modified**, and `conversation.py` is not reopened.

### REQUIRED: `plan_for_action` must propagate the tool's declared risk class

*(Recorded 2026-08-27, found during governance review of the merged prerequisites. An
implementation requirement, not a new decision, and **not** a defect in the step-up work.)*

Element 7 requires step-up for this act. The merged gate enforces it — but the value it keys on
never leaves the tool definition:

```
seam.py:87            gate fires when  request.risk_class == "IRREVERSIBLE"
approval_flow.py:157  approval.risk_class  <-  plan.declared_risk.name
write_path.py:626     plan_for_action      ->  declared_risk=Risk.EXECUTE   <- hardcoded
```

`ToolDefinition` carries a `risk_class` field and each tool declares one, but `plan_for_action`
**never reads it.** So a `revoke_authority_tool()` declaring `Risk.IRREVERSIBLE` would produce an
`EXECUTE` plan, the approval row would record `EXECUTE`, the gate would not fire, and `I-67`
would go unsatisfied **with nothing failing** — the worst shape a security gap can take, because
every test would pass and every page would look right.

**The requirement:** `plan_for_action` must read the declared risk class from the tool's own
`ToolDefinition` and carry it into the plan, so `Risk.IRREVERSIBLE` reaches the enforcement point
that already exists.

**Existing behaviour must be preserved, and can be.** All four current tools declare
`Risk.EXECUTE`, which is exactly what `plan_for_action` hardcodes today — so reading the
declaration produces identical plans and, since `declared_risk` is part of `I-112`'s identity
hash, **identical plan identities**. Nothing about an existing approval changes. That equivalence
is a claim the implementation must prove by test rather than assert.

**This is not `MT-6`.** No existing tool's declaration changes; a new tool declares its own class,
and the plan is made to honour what the declaration already says. Nothing is reclassified.

---

## Prerequisites and authorization

> ### `F-3` IMPLEMENTATION IS NOT AUTHORIZED.
>
> **Both technical prerequisites are SATISFIED.** What remains is governance: this ADR has not
> been accepted, and no implementation authorization has been given. **`F-4` and `F-14` are
> bundled into `F-3` and remain unauthorized with it; neither may be implemented independently.**

The act model, the selection target, `F-9`'s derivation, the `I-92` reading and the `F-4` audit
path are **decided and stable**. The two things that stood between them and code have both landed.

**Four different things, deliberately kept apart** — the reason this section exists at all:

| | State |
| --- | --- |
| The architecture is **decided** | Yes — the seven elements above, ruled 2026-08-26 |
| The prerequisites are **implemented** | **Yes — both, merged and verified** |
| This ADR is **accepted** | **No** — status remains `Proposed` |
| Implementation is **authorized** | **No** — a separate act, after acceptance |

Capability existing is not permission to use it. The first two rows being satisfied does not
advance the last two, and this ADR does not advance them by saying so.

### Prerequisite 1 — fresh authentication / step-up (`I-67`) — **SATISFIED**

**Merged in `d6a0d45`** (PR #16), verified before merge.

Element 4 makes this revocation permanent; element 7 therefore engages `I-67`, and `F-3` will be
NOVA's **first** `IRREVERSIBLE` path.

**The obligation was already accepted; only the mechanism was missing.**
[ADR 0018](./0018-authentication-model.md) (Accepted 2026-08-13) decided consequence-scaled
step-up; `A-3` states it; `I-67` mints it; `ADR 0046` selected WebAuthn as the mechanism. Building
step-up was therefore **`C1`/`C2` implementation of an accepted requirement, not a new `C3`
decision** — a distinction that mattered, because it is what kept `I-67` from being weighed
against convenience.

**`I-67` was satisfied by building step-up, not by reinterpreting it.** This ADR designed no
mechanism. What shipped: `step_up_options` / `verify_step_up` on the existing WebAuthn ceremony,
single-use, purpose-bound to one approval id, expiring, user-verification required, bound to the
session's actor, minting no session and persisting no freshness state — enforced immediately
before `ApprovalService.decide()`, which is untouched. `ADR 0046` is **Accepted (2026-08-26)** and
its limitation 3 was rewritten at that point to describe the implemented state.

### Prerequisite 2 — extraction of `_establish` into a shared module — **SATISFIED**

**Merged in `d1f5763`** (PR #17), verified before merge.

Element 6 requires `F-14` to classify rows by the **same** five establishment rules `F-13` uses,
from **one** definition. `approval_flow.py` could not import `_establish` — `conversation.py`
already imports `ApprovalService`, so the dependency was circular — so the shared definition was
lifted into a module both can import.

Duplicating the rules in `approval_flow.py` was **rejected**: two definitions of "establishable"
can drift, and a drift would silently make the decision boundary disagree with what the model was
shown. What shipped: `slice/substrate/establishment.py`, a leaf importing only `core.types`, with
the function moved **verbatim** — byte-identity proven by SHA-256 — and
`ConversationService._establish` retained as a delegating alias, so both production call sites and
the test that calls it directly were untouched. `F-13`'s behaviour is unchanged.

### Deferred, not blocking — supersession

Element 4 defers "revoke + superseding authority" to a separate future ADR. The analysis is
retained here because it governs that ADR, and because it is what made the revocation permanent.

`authority_revocation.execution_identity` is `text NOT NULL UNIQUE` (`schema.sql:377-383`) —
**at most one row per identity, ever** — and `revoke()`'s `ON CONFLICT (execution_identity) DO
NOTHING` depends on that constraint. A superseding record is, by definition, a *second* durable
record for the same identity. Every way to obtain one is closed:

| Representation | Why it is closed |
| --- | --- |
| A second row in `authority_revocation` | Requires dropping `UNIQUE` — a **schema change** |
| A `superseded_at` / `superseded_by` column | A **schema change**, *and* setting it needs `UPDATE`, which element 4 forbids granting |
| A separate `authority_supersession` table | A **schema change** |
| Encoding supersession inside the `execution_identity` text | **Inventing a mechanism**, and it corrupts the column's meaning |
| Recording it in `item` or `audit_record` | `_establish` reads only `authority_revocation` |

And a constraint deeper than the schema sits behind all five:

> **Any reversibility mechanism must be visible to `_establish`, and `_establish` lives in
> `conversation.py`.** Its check is flat set membership — `revoked = {…}`, then
> `author in revoked` (`conversation.py:229-239`). Supersession means "latest record per identity
> wins", which is a different read. **So reversibility of any kind is architecturally downstream
> of `F-13`'s read path**, which this ruling forbids reopening.

No supersession or authority-replacement concept exists anywhere in NOVA to reuse: every
occurrence of "supersede" in `docs/` and `slice/` refers to superseding *ADRs*, a
governance-document concept.

**This is what made element 7 engage.** The earlier reading held that revocation is
`Risk.EXECUTE` because superseding authority makes it reversible in principle. With supersession
deferred, what ships is permanent, and that reading no longer holds — so `I-67` applies, and
prerequisite 1 existed for that reason.

### Sequence

```
step-up             ──┐   SATISFIED  d6a0d45
(C1/C2, merged)       │
                      ├──►  ADR 0052 accepted  ──►  F-3 authorized  ──►  F-3
_establish extraction ┘        (NOT YET)              (NOT YET)            │
(C1/C2, merged)                                                           │
  SATISFIED  d1f5763                          F-4 + F-14  ◄───────────────┤
                                        (bundled, never independent)      │
                                        supersession ADR  ◄───────────────┘
                                            (deferred, separate)
```

Both prerequisites were `C1`/`C2` implementation of already-decided architecture, **not** `C3`
decisions — that is why neither needed an ADR of its own.

**The next gate is acceptance of this ADR, followed by a separate implementation authorization.**
It is no longer the prerequisites, and it is not yet `F-3`.

## Date

**2026-08-26** — drafted on James's F-3 ruling of the same day, and revised the same day on his
rulings of the three questions the first draft raised: revocation-only, `I-67` applies, and a
shared establishment module.

**2026-08-27 — documentation and state correction**, after both prerequisites landed
(`d6a0d45`, `d1f5763`). **No ruling was reconsidered and no element changed.** What changed:
prerequisite status recorded as SATISFIED with merge commits; statements that `ADR 0046`
limitation 3 records step-up as unbuilt removed, along with the obsolete quotation of its former
text; the sequence diagram's stale `C3` labelling and "next gate" line corrected; one stale
restatement in §1 saying "the act is `Risk.EXECUTE`" corrected to `IRREVERSIBLE`, which is what
element 7 has said since 2026-08-26; and the `plan_for_action` risk-class propagation recorded as
an implementation requirement.

## Drafting record

Drafted `Proposed`, as `docs/decisions/README.md` requires: *"an AI agent may draft an ADR with
status `Proposed`; it may not mark one `Accepted`."* Accepted 2026-08-27 by James's explicit act
at the ADR Decision Gate — the agent recorded that act, it did not make it. Same sequence as
ADRs 0048, 0049, 0050 and 0051. The single authoritative status is the `**Status:**` line in the
header.

This ADR records a decided architecture whose prerequisites are **satisfied** and whose
implementation is **unauthorized** — the first is a property of the work, the second of the
decision, and the 2026-08-27 correction exists to stop the two being read as one.
