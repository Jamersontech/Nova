# 0050 — Scope Names Are Control State, Not Content

**Status:** **Accepted** — 2026-08-25
**Proposed:** 2026-08-25 — drafted by an agent on James's F-11 ruling of 2026-08-25
**Accepted:** 2026-08-25 — by James, at the ADR Decision Gate, on the governance packet
and the review recorded below
**Section:** 07 — classifies a scope-bearing identifier against `I-111` and `I-100`;
governed by `MT-5`/`MT-6`
**Resolves:** `F-11`

## Decision

**A scope name is CONTROL / ADDRESSING state, not CONTENT.** Ruled by James, 2026-08-25.

> **`scope.scope_path` is a scope-bearing identifier. It is governed by `I-100`'s
> consequence-determining argument envelope and by ADR 0036's classification rules. It
> does **not** fall under `I-111`'s persistence-and-retrieval provenance requirement.**

Seven consequences, each binding:

1. **`scope_name` remains CONSEQUENCE-determining.** It is not reclassified EXPRESSIVE.
2. **`I-100`'s envelope continues to bind the exact scope-bearing identifier.** The name
   that is created is byte-for-byte the name the approval fixed.
3. **No `I-111` provenance columns are added to `scope`.** The table keeps
   `(id, scope_path, kind, parent_path, created_at)`.
4. **`add_scope` does not become content-capable.** `content_leaves(add_scope)` stays
   empty, so it remains structurally incapable of an ADR 0048 trust elevation.
5. **No backfill, and none is required** — there is no provenance concept being
   introduced for scopes, so there is nothing to backfill.
6. **This does not make arbitrary model-authored strings control state.** The ruling is
   grounded specifically in the structural and security role of a scope-bearing
   identifier, not in the fact that a model chose the characters.
7. **`conversation.py`'s base attribution is corrected as part of this decision** — see
   *The line-325 correction* below. It is not a separate change and does not land
   independently of this record.

---

## Context

`F-11` was raised by a hostile audit of `main` at `31a2216` and re-verified at `60827ec`
and `a7bd97d`. Its measured facts are not in dispute:

| Fact | Where |
| --- | --- |
| A model authors the name | `conversation.py`, the `PROPOSE_SCOPE` marker grammar |
| It becomes durable, and scopes are never deleted | `write_path.py`, `INSERT INTO scope`; no `DELETE FROM scope` exists |
| It re-enters model context on every later turn | `conversation.py`, `f"Scope: {scope_path}"` |
| No provenance is recorded for it | `schema.sql`, the `scope` table has none of the five `I-111` columns |
| The block carrying it was attributed `james.stated`/`HIGHEST` | `conversation.py`, the base taint |

ADR 0048 established what an approved write carries; ADR 0049 applied `I-111` to a second
persisted entity, a task title. `F-11` asked whether a third — a scope name — follows.

## Problem

**`I-111` names no table and contains no exemption**, so its text does not by itself
exclude a scope name. ADR 0049 declined to read the same silence in `MEMORY_MODEL.md` as
an exemption for tasks. If that reasoning transfers, a model-authored scope name is
durable content whose provenance is discarded at persistence — the exact defect shape
`F-2` closed.

**But two of the three facts that decided `F-2` are absent here, and the third points the
other way.** For a task title: the tool declared it EXPRESSIVE, the approval card rendered
it as a content leaf, and no accepted document classified it. For a scope name: the tool
declares it CONSEQUENCE, the card renders no content leaf for it, and **an accepted
document classifies the category directly.**

## Options Considered

1. **A — CONTENT.** Five `I-111` columns on `scope`; `scope_name` becomes EXPRESSIVE;
   `add_scope` persists and restores a taint and becomes elevation-capable.
2. **B — CONTROL / ADDRESSING.** `scope_name` stays CONSEQUENCE; `I-100`'s envelope
   remains the governing control; no schema change.
3. **Do nothing.** Leave both the classification and the attribution as they are.

## Decision Made

**Option B**, with the line-325 attribution corrected inside this decision.

Option 3 was rejected: it would leave the implementation asserting `james.stated` over
bytes NOVA did not author as James-stated content, which `I-110` disfavours regardless of
how the classification question is answered.

## Reason

**1. `MT-5` classifies the category directly, and it is the primary evidence.**
`MODEL_TRUST_AND_AUTHORITY.md`'s consequence-determining table contains the row:

> | **Scope-bearing identifier** | *Any identifier naming a scope, client, or credential binding* | **Bound: Yes** |

A scope name is literally an identifier naming a scope. The same table's **Expressive**
row reads *"Wording, tone, formatting, ordering, summary text"* — none of which describes
a single lowercase path segment. `MT-5`'s own test is *"determines **what the action
affects** rather than **how it is expressed**"*, and a scope name determines what every
future action in that subtree affects.

**2. `I-100` enumerates it.** *"Every consequence-determining argument — target,
**scope-bearing identifier**, magnitude, destination, irreversibility-bearing selector — is
checked at the tool enforcement point against the envelope."* The envelope pins the exact
name, so the created scope is the approved scope and no substitution is possible between
approval and execution.

**3. ADR 0036 puts the burden on EXPRESSIVE.** CONSEQUENCE is the default and *"expressive
arguments must be argued for rather than assumed."* No argument for EXPRESSIVE survives
`MT-5`'s scope-bearing-identifier row.

**4. Option A would have traded away an existing control.** An EXPRESSIVE argument is
explicitly not policed by the envelope. Reclassifying would remove `I-100`'s exact-value
pinning of the scope name in order to buy a provenance record — and no analysis showed
that trade to be net-positive. `MT-6` also makes the reclassification itself a **C3**
change, so Option A contained a second governance act inside it.

**5. The security machinery is expressed in the identifier.** `nova.in_scope()`,
`ContextToken.covers()`, every RLS policy, grant lookup, channel binding and credential
binding id are all functions of the path. Labelling the coordinate system with content
provenance would taint the addressing rather than the data.

**6. ADR 0049's decisive leg does not transfer.** Its rejection of control-state
classification rested partly on the fact that treating titles as control state *"would put
storage in contradiction with ADR 0036's EXPRESSIVE ruling and with the approval card that
already shows James the title as content."* Neither condition holds for a scope name: the
declaration says CONSEQUENCE and the card offers no content leaf. Its other leg — a claim
carried in imperative grammar, with the attacker choosing the grammar — is acknowledged
and is why the attribution correction below is part of this decision rather than deferred.

## The line-325 correction

*(the base attribution in `ConversationService._scope_context`)*

**The problem, stated exactly.** The model-context block was attributed
`Taint.of("james.stated", CONFIDENTIAL)` — `HIGHEST` trust — and the comment justified it
as covering *"the scope path and the pending count — both NOVA's own facts."* After
`add_scope`, a scope path can contain a segment a model chose, so the premise is false.
The failure mode is not elevation of content: `Taint.union` takes the **lowest** trust, so
any contributing item or task already dominates. It is the **empty scope** — which is the
normal state of a freshly created one — where `contributed` is empty and the block's taint
**is** the base, asserting `james.stated`/`HIGHEST` over a model-authored path.

**The correction.** The base becomes the `I-99` union of `james.stated` and the existing
`UNKNOWN_ORIGIN` term already defined in `write_path.py` for exactly this purpose —
*"what a write plan carries when nobody said where its content came from… DELIBERATELY NOT
`james.stated`: an absent taint is unknown, and unknown must never read as 'James said
it'."* The union yields provenance `{james.stated, model.generated}` at `LOW` trust,
classification unchanged at `CONFIDENTIAL`.

**Why coarse, and deliberately so.** Under this ruling there is no stored provenance from
which to reconstruct per-segment authorship, and **inventing one would be the very thing
`I-110` forbids.** So the correction says only what is actually known: some of this block
is NOVA's and James's own framing, and some of it may not be. It does not claim the
model-authored segment is `james.stated`, and it does not manufacture a precise origin.

**It is a restriction, not a promotion.** `I-110`'s closing sentence — *"Lowering trust is
not governed by this invariant — restriction is not gated like elevation"* — means this
direction is not gated by the promotion rule. It is nevertheless recorded here, and lands
with this ADR rather than ahead of it, because it is part of the same C3 question.

**What it does not change.** `is_untrusted_derived()` is unaffected: neither
`james.stated` nor `model.generated` is in `EXTERNAL_PROVENANCE`, so `I-40`'s
source-naming gate still fires on external content and only on external content. The
classification stays `CONFIDENTIAL`, so the gateway's `I-95` still sees the block as scoped
material rather than ambient `INTERNAL` text. Item and task taints continue to contribute
exactly as before. The pending count is untouched.

## Tradeoffs

**Advantages.** No schema change, no migration, no backfill, no new provenance concept.
`I-100`'s exact-value binding of the scope name is preserved rather than traded away. The
addressing layer stays free of content semantics. The one measured defect — a false
attribution — is fixed at its actual location.

**Disadvantages, stated honestly.** The scope name remains a **narrow channel by which
model-chosen characters become durable and permanently model-visible with no recorded
origin**, and this ADR does not close it — it rules that `I-111` is not the instrument for
closing it. The channel is bounded by the marker grammar to one lowercase segment of at
most 64 characters from `[a-z0-9_.-]`, and by `I-100`'s envelope to the exact value James
approved and read in the approval card's action text; it is not zero. The base-taint
correction is **coarse**: every scope block now reads `LOW`, including for scopes James
created himself, because nothing distinguishes them. That is the honest cost of declining
to invent provenance.

## Consequences

- **`INVARIANTS.md` is not amended.** No invariant is created, changed or exempted.
  `I-111` is untouched — this ADR determines that a scope-bearing identifier is not among
  the objects it governs, which its text already leaves to classification.
- **`MEMORY_MODEL.md` is not amended.** Its taxonomy is of memory; the scope tree is the
  permission model's coordinate system, and its absence there is consistent with this
  ruling rather than a gap in it.
- **`MT-5` and `MT-6` are unchanged and are the governing statements.**
- **ADR 0036 is unchanged**; this is an application of its default, not an exception to it.
- **ADRs 0048 and 0049 are unchanged.** Nothing here alters what an approved write carries
  or the classification of a task title.
- **`task_ref` and `item_ref` are closed by the same reasoning.** Both are scope-relative
  identifiers addressing a record, not expressive content, and both are already declared
  CONSEQUENCE. Absent materially different architecture, the question does not need to be
  reopened for them. **This is the reasoning's reach and its limit:** it extends to
  identifiers that address, and to nothing else. A model-authored string that names no
  record and addresses nothing is not made control state by this ADR.
- **`add_scope` remains structurally incapable of elevation.** `content_leaves` stays
  empty, which is a property of the tool rather than a check that could be forgotten, so
  `F-8`'s guarantee is unaffected.

## What Would Change This

Evidence that a scope name is read as anything other than an address — a path segment
parsed for meaning by a downstream consumer, or an interface that renders it as prose to
the model outside the `Scope:` line. That would make it a target-bearing string that also
carries content, and would reopen the classification on new facts rather than on this
record.

## Date

2026-08-25 — drafted on James's F-11 ruling of the same day, after a governance packet
that argued both readings from the accepted architecture and did not decide between them.

## Status

**Accepted** — 2026-08-25, by James, at the ADR Decision Gate.

Drafted `Proposed` and accepted by James's explicit act, as `docs/decisions/README.md`
requires: *"an AI agent may draft an ADR with status `Proposed`; it may not mark one
`Accepted`."* Same sequence as ADRs 0048 and 0049.

---

# IMPLEMENTATION RECORD — added after the decision

*This section decides nothing. It records what was built, so a later reader can tell the
ruling apart from its implementation.*

**Production change — one statement in `slice/substrate/conversation.py`:**

```python
base = Taint.union(
    Taint.of("james.stated", Classification.CONFIDENTIAL),
    Taint.of(UNKNOWN_ORIGIN, Classification.CONFIDENTIAL),
)
```

`UNKNOWN_ORIGIN` is imported from `write_path.py` rather than restated, so the
"we do not know where this came from" term has one definition. The surrounding comment,
which asserted the scope path was one of *"NOVA's own facts"*, is corrected.

**Not changed:** the `scope` table, `add_scope`, the tool registry, `content_leaves`,
`I-100`'s envelope construction, the pending count, the withheld messaging, `_establish`,
item and task taint contribution, `F-9`'s revocation derivation, `F-10`'s completion
predicate, `F-12`'s sibling-scope predicates, RLS, grants, roles, `ContextToken.covers()`,
`nova.in_scope()`, and all of `slice/core/` and `slice/tools/`.

**Tests:** `slice/substrate/tests/test_scope_name_attribution.py`.

**IMPLEMENTATION STATUS: IMPLEMENTED, PENDING MERGE.**
