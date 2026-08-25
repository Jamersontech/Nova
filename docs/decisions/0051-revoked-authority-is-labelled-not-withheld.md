# 0051 — A Revoked Creating Authority Is Labelled, Not Withheld

**Status:** **Accepted** — 2026-08-25
**Proposed:** 2026-08-25 — drafted by an agent on James's F-13 ruling of 2026-08-25
**Accepted:** 2026-08-25 — by James, at the ADR Decision Gate, on the decision packet and
the post-merge verification recorded below
**Section:** 07 — implements `S7-D5` at retrieval; governed by `MEMORY_MODEL.md` §4 rule 8
**Resolves:** `F-13`

## Decision

**RETAIN + LABEL.** Ruled by James, 2026-08-25.

> **When retrieval encounters an item or task whose creating authority has been revoked,
> the row is RETAINED and its revocation state is EXPLICITLY SURFACED. It is not withheld.**

Seven consequences, each binding:

1. **The row remains available to model context**, with its content unchanged.
2. **The revocation state is explicitly surfaced**, per row.
3. **Revocation is represented separately from provenance and taint** — structured
   row-level metadata beside the taint, never a provenance term.
4. **Revocation does not change trust.**
5. **Revocation does not change classification.**
6. **Revocation does not promote, downgrade, invalidate, reclassify, or otherwise alter
   the row's security state.** The row is returned exactly as established, plus one
   additional fact about it.
7. **The consuming authority decides what the revocation means** — and that decision
   happens at the existing authorization boundary, not at retrieval and not in the model.

This implements the accepted architecture as written. **No accepted document is amended.**

---

## The question

`I-111`'s read half withholds a row whose security state cannot be established, and there
are five such reasons. A sixth condition sat in the same branch: `creating_authority in
revoked`. The question was whether that belongs there.

## Problem

**It does not, and the accepted architecture says so in three places.**

`MEMORY_MODEL.md` §4 rule 8 (Active; amended and Accepted 2026-08-15 under ADR 0033):

> **A revoked creating authority is surfaced.** An item created under an authority later
> revoked is **retained** under the lifecycle rules above and its revocation state is
> **exposed at retrieval**. Nothing is automatically deleted, downgraded, invalidated,
> promoted, or reclassified — `DATA_LIFECYCLE.md` §4's rule against silent resolution
> applies: revocation happens for many reasons and only some impeach what was learned. The
> **consuming authority** decides.

ADR 0033 §4 (`S7-D5`), Accepted 2026-08-15, pre-empts the withholding reading in terms:

> **This is a retrieval-labelling rule and needs no invariant** — no new property is
> asserted, only **that an existing fact is not withheld at the point of use**.

`KNOWN_RISKS.md` (Section 07) records the accepted residual:

> `S7-D5` exposes revoked creating authority at retrieval and **deliberately does not
> re-weight**… but **it puts a judgment in front of the consumer on every affected
> retrieval**.

The implementation removed the judgment instead of presenting it, so a residual the
architecture accepted could not occur.

## REVOKED is not UNKNOWN

This is the whole of the finding, and it is a distinction of kind rather than degree.

| | UNKNOWN / unestablishable | REVOKED |
| --- | --- | --- |
| Authority | not known (NULL), or not checkable (broad ancestry) | **known** |
| Revocation status | **not determinable** — *"could not check" ≠ "not revoked"* | **determined** |
| Security state | **not established** | **established**, and restorable |
| Governing rule | fail closed (`I-110`, `I-52`'s pattern) | **retain + label** (`S7-D5`) |
| Who decides | nobody can — there is nothing to decide on | **the consuming authority** |

The five unknown branches rest on an argument that does not transfer: a delegate's
ancestors may have executed in scopes the bound channel cannot read, so absence of a
revocation record is not evidence of absence. For a revoked author there is no gap — **the
record was found.** Withholding on that basis applies a rule for unknown state to known
state.

## Revocation is not provenance

**Provenance is an ORIGIN.** Revocation is a later fact *about* an authority, learned after
the row was written. Recording it as a provenance term would make a set `I-38` calls
immutable change after the fact, and would read as though the content came from somewhere
it did not. `Taint` has no revocation axis and does not gain one.

**And it must not re-weight.** Rule 8 forbids downgrading and reclassifying, and
`KNOWN_RISKS` records that `S7-D5` *"deliberately does not re-weight"* as correct rather
than as a limitation. So trust and classification are untouched, and the row's taint joins
the `I-99` union exactly as it always did.

The representation is therefore **a structured per-row flag carried beside the taint** —
deterministic, unambiguous, impossible to confuse with provenance, and clearly distinct
from a withheld row, which does not appear at all.

## The model is not the consuming authority

Rule 8 says *"the consuming authority decides"*, and `I-101` and `I-102` establish that a
model is never an authority: it never supplies an authorization-relevant fact and never
satisfies an approval requirement.

So the model **receives the content and the label as information available for reasoning,
and decides nothing by holding them.** The consuming-authority decision occurs where it
already occurs — at the authorization and approval boundary, when a consequential action
is considered. **No new approval mechanism is created and the approval flow is not
redesigned.**

The block therefore states the fact and explicitly declines to draw a conclusion from it.

## The withheld message was false

The message read:

> *"…their provenance, trust or creating authority **cannot be established**, so they are
> not shown to the model."*

For a revoked row every clause of that was untrue: provenance, trust and classification
were all restored, and the creating authority was established — **as revoked**. Because
one counter served both cases, a scope holding one unestablishable row and one revoked row
emitted a single sentence asserting the false reason for both.

Correcting it is part of this decision. The two states are now counted separately, reported
separately, and can never be collapsed. The withheld sentence now covers only rows that are
genuinely unestablishable, and is accurate for all of them.

## Human-facing surface

**None is required by this ADR.** Rule 8 requires exposure *"at the point of use"* and
names no surface; `authority_revocation` reaches no render path today, and adding one would
raise governance questions — who may revoke, what identity James acts on, where it is
surfaced — that belong to `F-3`. **This decision is confined to retrieval and model
context.** A human-facing revocation surface may be addressed during `F-3` governance.

## `F-3` remains separately governed

`F-13` had to be settled first: `F-3` creates revocations, and until now doing so would
have made content *disappear* from model context where rule 8 requires it retained. That
is now fixed, so `F-3` can be built to the correct behaviour rather than against it.

**Nothing about `F-3` or `F-4` is decided here.** Who may revoke, whether `I-67` requires
step-up, what execution identity James acts on and where it is surfaced, whether revocation
is a direct or approval-flow act, whether it is intentionally irreversible, and what audit
record `F-4` requires — all remain open, at a separate future gate.

## Tradeoffs

**Advantages.** The accepted architecture is implemented as written, with no document
amended. A false statement is removed. `S7-D5`'s labelling becomes real, and the
`KNOWN_RISKS` residual becomes reachable and honest. `F-3` can now be built correctly.

**Disadvantages, stated honestly.** Content created under a revoked authority now **reaches
the model where it previously did not** — a real widening of what the model sees, and the
one respect in which this decision is less restrictive than the code it replaces. The
architecture accepts that deliberately: revocation happens for many reasons and only some
impeach what was learned, and the alternative is NOVA silently making an epistemic judgement
reserved for the consuming authority. Every other control is untouched, and a labelled row
carries exactly the trust it always carried — which for a low-trust origin is still low.

## Consequences

- **`INVARIANTS.md` is not amended.** `S7-D5` deliberately mints no invariant.
- **`MEMORY_MODEL.md`, ADR 0033 and `KNOWN_RISKS.md` are not amended** — they are
  implemented.
- **No schema change, no provenance columns, and no backfill.** Revocation state is derived
  at read time from the existing `authority_revocation` registry, exactly as before.
- **`F-9`, `F-10`, `F-11` and `F-12` are unchanged.** `revocation.py` and `write_path.py`
  are untouched; `F-12`'s scope predicates and `F-11`'s base taint are untouched. ADR 0050
  is untouched.
- **Six existing assertions change**, because this ruling reverses the behaviour they
  encoded. Each asserted *"the revoked row is absent"* and now asserts *"the revoked row is
  present and labelled"*. **The underlying security coverage is converted, not deleted** —
  every one still proves that revocation reaches the reader.
- **`I-40`, `I-100`, `I-110` and `I-111` are unaffected in substance.** A retained row's
  taint contributes to the `I-99` union as it always did, so `I-40` fires on external
  content exactly as before — in fact slightly more often, since such a row is no longer
  dropped before the union. Nothing is promoted, so `I-110` is not engaged.

## Implementation scope

`slice/substrate/conversation.py` only:

- `_establish` no longer withholds on `author in revoked`; it returns the flag beside the
  restored taint.
- The block labels each affected row and adds one statement of what the label means and
  what it does not authorize.
- The withheld sentence covers only unestablishable rows.
- The read audit record counts `revoked_authority` separately from `withheld`.

Plus `slice/substrate/tests/test_revoked_authority_labelling.py` and the six converted
assertions.

## Date

2026-08-25 — drafted on James's F-13 ruling of the same day, after a governance packet that
argued both branches and did not decide between them.

## Status

**Accepted** — 2026-08-25, by James, at the ADR Decision Gate.

Drafted `Proposed` and accepted by James's explicit act, as `docs/decisions/README.md`
requires: *"an AI agent may draft an ADR with status `Proposed`; it may not mark one
`Accepted`."* Same sequence as ADRs 0048, 0049 and 0050.

---

# IMPLEMENTATION RECORD — added after the decision

*This section decides nothing.*

**Representation:** a boolean flag per established row, returned by `_establish` beside the
taint, rendered as the single constant `_REVOKED_MARK` (`[creating authority revoked]`) via
one `_mark()` helper — so the marker the block renders and the marker anything asserts about
it cannot drift.

**Not changed:** `schema.sql`, `slice/core/`, `slice/tools/`, `write_path.py`,
`revocation.py`, `approval_flow.py`, `boundary.py`, `auth.py`, `attention.py`, `seam.py`,
ADR 0050, `INVARIANTS.md`, `MEMORY_MODEL.md`, `KNOWN_RISKS.md`, `ROADMAP.md`.

**IMPLEMENTATION STATUS: IMPLEMENTED AND VERIFIED, PENDING MERGE.**
