# 0013 — Deletion Cascades Through Lineage, Leaving Tombstones

**Status:** Proposed
**Proposed:** 2026-08-12 — Section 03
**Section:** 03

## Decision
Deleting an item deletes it and **invalidates every item derived from it through recorded
lineage within NOVA-controlled storage**: derived items are deleted or re-derived without the
source; embeddings, index entries, caches, and summaries are treated as copies and removed. A
**tombstone** retains the item's identity, scope, classification, deletion time, and
authorization — never its content. **Audit records are retained.**

### Scope and limits of the cascade

*Amended 2026-08-12 following adversarial review. Universal deletion is not claimed.*

The cascade reaches **recorded lineage inside storage NOVA controls**. It does not reach:

| Beyond reach | Why |
| --- | --- |
| **Already-delivered exports** | Once an export leaves, it cannot necessarily be recalled |
| **Data transmitted to external systems** | A record pushed to a client's CRM or mailbox is outside NOVA's direct deletion control |
| **Model-provider retention** | Provider-side retention is governed by the provider, not NOVA |
| **Unrecorded derivations** | A derivative whose lineage was never recorded is not discoverable. Below CLIENT-CONFIDENTIAL, retrieval is not required to be recorded (`I-34`), so paraphrases of lower-classified items may have no lineage edge |
| Screenshots, printed material, human recollection | Outside any software boundary |

**Backups.** A backup taken before a deletion still contains the item. **Restoration must
consult tombstones and re-apply deletion before restored data becomes available** (`I-55`).
Without this rule, restore silently resurrects deleted data — the single most likely way for
deletion to fail in practice.

Where deletion cannot reach, NOVA must **say so** rather than report deletion as complete.

## Context
Constitution §13 requires that James own his data, including deletion. Section 03 must define
what deletion actually means when derived copies exist.

## Problem
"Delete it" is ambiguous. The source row is the easy part; embeddings, indexes, caches, and
summaries all contain the content in transformed form. Deleting only the source leaves the
information present and, worse, present in places nobody is looking at.

## Options Considered
1. **Delete the source only.** Trivial; the information survives in derivatives, so deletion
   is a comforting fiction.
2. **Delete source and cascade through lineage.** Genuine; requires lineage on every
   derivation and makes deletion potentially expensive.
3. **Soft-delete everything with flags.** Reversible and cheap; the data is still there, so
   it is not deletion.
4. **Delete and re-derive affected derivatives.** Most correct; most expensive.

## Decision Made
Option 2, with option 4 available where a derivative remains useful without the deleted
source.

## Reason
Deletion that leaves derivatives is not deletion. Because derivatives are discoverable only
through lineage recorded at derivation time, **lineage is the precondition for deletion being
real** — which is why ADR 0010 requires it universally rather than as an audit nicety.

## Tradeoffs
**Advantages:** deletion is genuine; tombstones prevent silent re-derivation; audit stays
complete without retaining deleted content; scope-level deletion supports client offboarding.
**Disadvantages:** cascades can be expensive and may remove derivatives that were still
useful; lineage must be complete or the cascade misses; tombstones are themselves metadata
that must be protected; retained audit records mean deletion is never *absolutely* total.

## Consequences
An item with unrecoverable lineage is treated as derived from the strictest classification
present, so it is over-restricted rather than missed. Restore paths must be tombstone-aware
(`I-55`). Deletion reports must distinguish what was deleted from what is beyond reach. The retained audit record states that
something existed and was deleted — never what it was.

**No legal claim is made.** Whether a record must be retained for legal reasons is Section
37's question; this defines the mechanism such a requirement attaches to.

Invariants `I-45`, `I-46`, `I-47`.

## What Would Change This
A regulatory requirement demanding removal of audit records themselves would conflict with
`I-47` (append-only audit) and would require a superseding ADR resolving that conflict
explicitly.
