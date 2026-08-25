# 0049 — Task Titles Are Content, Not Control State

**Status:** **Accepted** — 2026-08-25
**Proposed:** 2026-08-25 — drafted by an agent on James's F-2 decision of 2026-08-25
**Accepted:** 2026-08-25 — by James, at the ADR Decision Gate, on the review recorded below
**Section:** 07 — applies `I-111` to a second persisted entity; governed by `I-110`
**Governance class:** **C3** — a domain-model classification
([`IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md) §4), so James's
approval **and** an ADR were required, and both are recorded here
**Decision owner:** James. Drafted `Proposed` by an agent and moved to `Accepted` only on
James's explicit decision (`decisions/README.md`, *Authority*).
**Resolves:** **F-2** — the task-content provenance gap left open by
[ADR 0048](./0048-provenance-and-trust-of-an-approved-write.md)
**Relates to:** `I-111`, `I-110`, `I-112`, `I-40`, `I-99`, `I-27`, `I-09`; ADRs
[0036](./0036-tool-declarations-are-claims-not-facts.md),
[0048](./0048-provenance-and-trust-of-an-approved-write.md)

> **IMPLEMENTATION STATUS: IMPLEMENTED, PENDING MERGE.** This ADR was drafted `Proposed`
> before implementation, accepted on 2026-08-25, and the implementation is on
> `feature/adr-0049-task-content-provenance` (PR #10), **not yet merged to `main`**.
>
> An implementation record is appended below the decision and is clearly separated from it;
> **nothing above that separator describes code**, and the record decides nothing.

---

## Decision

**A task title is CONTENT, not control state.** Decided by James, 2026-08-25.

> **`task.title` is expressive content and carries the same provenance, trust and
> classification guarantee as `write_item` content. It falls under `I-111`'s persistence and
> retrieval requirement, and reaches model context only when that state can be established.**

Five consequences, each binding:

1. **Row-level provenance (mutable-task Model 1).** The five `I-111` columns —
   `provenance`, `trust`, `classification`, `delegation_ancestry`, `creating_authority` —
   go on `task` itself. **No task-history or version system is introduced.**
2. **Title and security state change together, atomically.** The existing upsert already
   destroys the previous title; the same statement must destroy its taint. An old title's
   provenance must never survive a replacement title.
3. **A changed title is a new plan.** `I-112`'s identity already hashes every argument
   including `title`, so a title mutation is a different plan requiring a fresh approval.
   Nothing about `I-112` changes.
4. **Legacy tasks are not backfilled and fail closed for model context.** Rows written before
   this decision carry NULL security state; NULL is unknown, and unknown is withheld from the
   model. They are not reclassified, downgraded, marked, or migrated — the same prospective-only
   ruling ADR 0048 records for items.
5. **Withholding is a model-context property only.** Human surfaces are unchanged, and
   authorization is untouched (see *Three separate properties* below).

**The default remains non-elevation.** A task title becomes `HIGHEST` only under the
content-visible approval rules ADR 0048 already established for expressive content — never
because an approval row exists, and never by a rule written specially for tasks.

---

## Context

`I-111` requires that provenance, taint and delegation ancestry **survive persistence and are
restored at retrieval**. ADR 0048 decided what an approved write carries and implemented it for
`item`, and named the task gap **F-2** as downstream, saying explicitly that it *"belongs in a
separate ADR, downstream of this one."* This is that ADR.

The question was genuinely open, and this ADR should not pretend otherwise. `I-111`'s normative
clauses govern *"persistence"* and *"retrieval"* without naming a table — but
[`MEMORY_MODEL.md`](../architecture/MEMORY_MODEL.md) §2's taxonomy of thirteen memory types
**contains no row for a task**, and its nearest neighbour, *Execution state*, is defined as
**transient** workflow state, which a durable task is not. The architecture had classified
neither way. That silence is what made this C3.

---

## The security argument that decides it

**A task title can contain factual claims inside imperative language.**

> *"Call the supplier — their bank details changed to X"*

That is grammatically an instruction and semantically a claim about the world. Treating every
task title as inherently safe control state would mean an attacker-controlled fact can be
laundered through a task: written as a title, persisted with no record of where it came from,
and later returned to model context as `james.stated`/HIGHEST **after its original source has
disappeared**.

Measured on `main` @ `ce9d229`, through the production path:

```
block taint with a LOW external.web item in scope:  LOW ['external.web', 'james.stated']
model proposes a task titled with that content; James approves
the source item is deleted
  -> title still in model context:  True
  -> block taint:                   HIGHEST ['james.stated']      <- origin gone
```

This is the same cycle ADR 0048 closed for items, still open for tasks. The asymmetry is what
makes it untenable: **identical text is labelled honestly if written as a note and laundered if
written as a task**, and which one it becomes is a choice available to whatever produced it.

---

## Architecture evidence already on record

None of this is new architecture. Every layer above storage already treats a task title as
content; only persistence disagrees.

| Evidence | Where |
| --- | --- |
| `add_task_tool()` declares `title` **EXPRESSIVE**, commented *"prose — MT-5, same ruling as write_item"* | `write_path.py`, tool declaration |
| ADR 0036 makes EXPRESSIVE the exception a tool must argue for; CONSEQUENCE is the default | [ADR 0036](./0036-tool-declarations-are-claims-not-facts.md) |
| `content_leaves()` returns `{"title"}` for `add_task` | `write_path.py` |
| ADR 0048's approval card renders the title as content to be inspected | `seam.py`, `_approval_card` |
| The approval row already stores the honest `proposed_taint` for a task proposal | `approval_flow.py` |
| Open tasks already reach model context, tested deliberately | `test_tasks.test_12` |
| The taint is computed, carried the whole way, and **discarded at the INSERT** | `write_path.py`, `ADD_TASK` branch |
| Attention is a human surface that never touches the gateway (`I-95`) | `attention.py` module docstring |
| Fail-closed withholding already applies to model context while the human UI still displays the record | ADR 0048 / `I-111`, `test_20` |

The gap is one statement wide: `INSERT INTO task (task_ref, scope_path, actor_ref, title, due_on)`
names no security column.

---

## Options considered

### Option A — task titles are content — **CHOSEN**

**Argument.** The architecture already decided this once, in ADR 0036, and ADR 0048 built its
entire content-visibility mechanism on that classification. Under A, F-2 is not a new rule but
the removal of an inconsistency between the storage layer and every layer above it.

**Consequences.** A schema change to accepted architecture. Task titles become subject to
withholding, so the model can be blind to a task James can see. Legacy tasks are withheld from
the model, which is an observable behaviour change for existing rows — and per ADR 0048's
prospective-only ruling they are **not** backfilled.

### Option B — task titles are control state — **REJECTED**

**Its strongest argument, recorded because it is real.** A task is an instruction, not a claim.
Its function is to make something happen; *"Book the dentist"* asserts nothing that could be
true or false, so trust-labelling it is arguably a category error. James approved the task's
existence, the due date is a commitment he made, and NOVA legitimately owns its own worklist.
On this reading, `MEMORY_MODEL`'s silence is evidence the architecture never meant tasks to be
memory, and applying memory provenance to an operational queue imports machinery that does not
fit. It is also free: no schema change, no migration, no withholding semantics for a mutable
row.

**Why it was rejected.** The category argument does not survive contact with a title that
carries a factual claim in imperative grammar, and an attacker picks the grammar. B would
create a documented **exemption** from an invariant whose normative text contains no exemption,
leaving a live channel by which untrusted content reaches model context as trusted — the exact
shape ADR 0048 rejected for items. It would also put storage in contradiction with ADR 0036's
EXPRESSIVE ruling and with the approval card that already shows James the title as content.

**Rejected variants.** *Version-level provenance*, *immutable content + mutable control fields*
and *a separate content object referenced by the task* were each considered and set aside. The
decisive fact is that the existing upsert keeps exactly one row per `(scope_path, task_ref)`
and destroys the previous title outright: **there is no historical version that could become
detached from its provenance**, so the lineage those models buy is lineage NOVA does not keep
for tasks, and each would raise a fresh question against [ADR 0013](./0013-deletion-and-forgetting.md)'s
cascade.

---

## Three separate properties

This decision keeps them distinct, and no clause below may be read as collapsing them.

| Property | Meaning | Effect of this decision |
| --- | --- | --- |
| **Human visibility** | James can see the task | **Unchanged.** Attention and the scope page show the complete task, title included, whether or not the model may consume it. Nothing is hidden, redacted, replaced, or altered on a human surface. |
| **Model visibility** | The model may consume the title as trusted context | **Constrained.** Established state, or withheld. |
| **Authorization** | James may act on the task | **Unchanged.** `COMPLETE_TASK` remains independently actionable; a withheld title does not block completion, and never becomes a covert authorization change. |

`MEMORY_MODEL.md` §5 already draws this distinction — *"Memory is what NOVA retained, not
permission to use it"* — and this ADR relies on it rather than restating it as something new.

---

## Does `I-111` need to change?

**No, and it should not be broadened.**

`I-111`'s normative clauses already read *"Provenance, taint and delegation ancestry survive
**persistence** and are restored at **retrieval**"*, *"**Persistence** must not discard
provenance…"*, and *"**Retrieval** must restore…"* — none of them names a table or a data type.
The word *memory* appears only in the explanatory *Survival is not authority* clause, which is
about a delegate's authority, not about scoping the invariant. Applying `I-111` to `task` is
therefore an **application of the accepted text, not an amendment to it**, and no edit to
`INVARIANTS.md` is proposed.

The ambiguity was never in `I-111`. It was in `MEMORY_MODEL.md` §2, whose taxonomy has no row
for a task, so a reader could not tell whether a task was within the system `I-111` governs.
**That silence is what this ADR closes** — by classifying tasks explicitly, using the existing
vocabulary and inventing no new trust concept.

Recording this in the invariant instead would broaden it: `I-111` would acquire a list of
entities it covers, which is a maintenance burden and an invitation to read the list as
exhaustive. The classification belongs where classifications live.

---

## What this decision does not weaken

| | |
| --- | --- |
| **ADR 0048** | Untouched. Elevation still requires all five content-visible properties, and this ADR adds no path to `HIGHEST` that ADR 0048 did not already define. Task titles earn trust under the *same* rules, not looser ones. |
| **`I-110`** | Untouched. No new promotion mechanism; a task elevation is the existing one, and where a real elevation is persisted it is recorded as `I-110` requires. |
| **`I-112`** | Untouched. Plan identity already covers `title`; a changed title is already a new plan needing fresh approval. No identity semantics change. |
| **`I-40`** | Untouched. The honest derived taint still reaches the PDP before any elevation, and an externally-derived task plan still needs an approval naming the source. |
| **`I-99`/`I-27`** | Applied, not changed — union provenance, lowest trust, strictest classification. |
| **F-8** | Its guarantee is preserved exactly: *an elevation audit exists if and only if a row carries the elevated taint.* Because tasks will now carry it, the set of rows satisfying that condition grows; the condition itself does not move. |
| **RLS / isolation** | Untouched. `task` is already in the ownership and policy loops. |

---

## Consequences

**Accepted.** Legacy tasks become invisible to the model until rewritten — deliberately, and
without backfill. The model may be unable to reason about a task James can plainly see, which
is the same asymmetry items already have. A task title that draws on an external source will
require an approval naming that source before it can be written at all (`I-40`), which is a
behaviour change for a case that does not arise today but will.

**Rejected as costs not worth paying.** Any form of task history; any second trust model; any
special-case rule that lets a task reach `HIGHEST` more easily than an item.

---

## Date

**2026-08-25** — proposed and accepted. Option A chosen by James, with row-level provenance
as the mutable-task model, and the three properties recorded above kept distinct: a withheld
task stays visible to James unchanged, its title is withheld from model context, and neither
affects his authorization to act on it.

---

## References

**Invariants:** `I-09`, `I-27`, `I-40`, `I-99`, `I-110`, `I-111`, `I-112` —
[`../architecture/INVARIANTS.md`](../architecture/INVARIANTS.md)

**ADRs:** [0036](./0036-tool-declarations-are-claims-not-facts.md) (EXPRESSIVE/CONSEQUENCE),
[0048](./0048-provenance-and-trust-of-an-approved-write.md) (content-visible approval),
[0033](./0033-section-07-amendments-to-accepted-architecture.md) (`I-110`/`I-111`),
[0013](./0013-deletion-and-forgetting.md) (deletion cascade)

**Architecture:** [`../architecture/MEMORY_MODEL.md`](../architecture/MEMORY_MODEL.md) §2 and §5,
[`../architecture/IDENTITY_AND_AUTHORITY.md`](../architecture/IDENTITY_AND_AUTHORITY.md) §4

**Code, at `main` @ `ce9d229`:**

```text
slice/substrate/schema.sql              the task table -- no security columns
slice/substrate/write_path.py           add_task_tool: title EXPRESSIVE; ADD_TASK discards taint
slice/substrate/write_path.py           content_leaves() -> {"title"} for add_task
slice/substrate/conversation.py         _establish (I-111 read half); _scope_context reads tasks
slice/substrate/attention.py            human surface; never touches the gateway
slice/substrate/seam.py                 the scope page; _approval_card renders the title
```

---
---

# IMPLEMENTATION RECORD — added after the decision

*Everything above this separator is the decision. This section records what was built against
it and decides nothing. It is written after implementation and describes code.*

**Schema.** Five nullable columns added to `task` — `provenance text[]`, `trust smallint`,
`classification smallint`, `delegation_ancestry text[]`, `creating_authority text` — matching
`item` exactly, via the repository's existing `ADD COLUMN IF NOT EXISTS` pattern. No guard is
needed: unlike `item.provenance`, no conflicting column existed. No backfill, no migration of
historical rows.

**Write path.** The `ADD_TASK` branch persists the five values in the **same statement** as the
title, and its `ON CONFLICT … DO UPDATE` updates all five alongside `title` and `due_on`, so a
replacement title cannot inherit its predecessor's provenance. The values come from the plan's
taint and the token — never from the payload — exactly as `write_item` takes them.
`COMPLETE_TASK` writes no content and is unchanged.

**Read path.** `_scope_context` selects the five columns with each open task and passes the rows
through the **existing** `_establish`, unchanged: it never inspects the content field, so a task's
`(title, due_on)` travels where an item's `body` does. No second establishment mechanism and no
second taint representation exists. Withheld tasks are counted and reported to the model in the
same sentence style as withheld notes, and both contribute to the block's `I-99` union.

**Human surfaces.** `attention.py` and the scope page in `seam.py` are untouched and still select
`task_ref, title, due_on`. A withheld task appears there in full.

**Elevation audit.** F-8 placed the `trust.elevation` record inside the branch that stores the
taint, so that an audit exists exactly where an elevation is real. Tasks now store a taint, so
the record is emitted from the `ADD_TASK` branch too — through **one** helper called only by
branches that persist a taint, so there is still a single definition of "an elevation happened"
and `complete_task`/`add_scope` still cannot emit one. F-8's condition is unchanged; the set of
rows meeting it grew, which is what this decision means.
