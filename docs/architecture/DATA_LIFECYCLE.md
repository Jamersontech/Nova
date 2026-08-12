# Data Lifecycle

**Status:** **Active** — Section 03, approved by James 2026-08-12 (as amended, commit 0917de5).
**Covers:** the life of an item from creation to deletion, plus temporal state, versioning,
lineage, retention, deletion, and portability.

---

## 1. The Lifecycle

```text
Create → Classify → Store → Use → Derive → Share → Archive → Expire → Delete
```

| Stage | Authorization | Provenance | Audit |
| --- | --- | --- | --- |
| **Create** | Write grant in the target scope | Source, creator, execution recorded | Created |
| **Classify** | Automatic at creation; downward reclassification is reviewed | Classification basis recorded | Assigned / reclassified |
| **Store** | Owning scope fixed; one scope only | — | — |
| **Use** | Read grant + token covers owning scope | Read recorded for CLIENT-CONFIDENTIAL and above | Accessed |
| **Derive** | Rights over **every** source | Lineage: all sources | Derived, with source list |
| **Share** | Explicit per-consumer grant — placement is not authorization | Grant recorded | Granted / revoked |
| **Archive** | Same scope, reduced access | Unchanged | Archived |
| **Expire** | Policy-driven; `james.stated` never auto-expires | Unchanged | Expired |
| **Delete** | Delete right; cascades to derived items | Tombstone retains the fact of deletion | Deleted |

---

## 2. Temporal State

NOVA must distinguish *what is true now* from *what was true then*.

```text
Item
├── valid_from / valid_until    when the item describes reality
├── recorded_at                 when NOVA learned it
├── superseded_by               the item that replaced it
└── state                       current · superseded · archived · expired · deleted
```

**Two clocks, deliberately.** *Effective time* (when a preference applies) and *record time*
(when NOVA learned it) differ, and conflating them makes "what did NOVA believe last
Tuesday?" unanswerable.

**Only `current` items drive decisions.** Superseded items are readable as history and are
never treated as present truth — the requirement that a preference changed today is not
still acted on tomorrow.

---

## 3. Versioning and Supersession

**Nothing meaningful is updated in place.** A change creates a new version and marks the old
one superseded, with a pointer forward.

```text
Preference v1 (superseded 2026-08-12) ──→ Preference v2 (current)
```

This gives three properties at once: current truth is unambiguous; history is intact; and
audit can reconstruct what was believed at any past moment.

**Historical records are never silently rewritten because current truth changed.** If James
changes a preference, the old preference remains a true record of what he wanted then.

---

## 4. Contradiction

When new information conflicts with existing:

| Situation | Resolution |
| --- | --- |
| New item from a higher-trust source | Supersede; record both |
| Equal trust, clear recency | Supersede; record both |
| Equal trust, unclear which is right | **Surface to James.** Do not pick |
| Conflicts with `james.stated` | **Never auto-supersede.** Surface it |
| External source contradicts internal | Internal stands; external recorded as a claim |

**Silent resolution is prohibited.** Quietly discarding one side is how memory poisoning
succeeds — an attacker only needs their version to win once, invisibly.

---

## 5. Lineage

Every derived item records the complete set of items it came from. Lineage makes three
otherwise-impossible operations possible:

1. **Classification inheritance** — the strictest source governs
   ([ADR 0010](../decisions/0010-derived-data-inheritance.md)).
2. **Deletion cascade** — deleting a source finds everything derived from it.
3. **Leak diagnosis** — when something appears where it should not, lineage says how it got
   there.

**An item whose lineage cannot be established is treated as derived from the strictest
classification present in its context.** Unknown lineage is never treated as clean.

---

## 6. Retention

Retention is a **scope-level policy** so that a client's data can be exported or removed as
a unit.

| Class | Default |
| --- | --- |
| Working / session memory | Expires with the execution or session |
| Operational events | Working window |
| Scope memory and knowledge | Retained until deleted; low-value items decay |
| `james.stated` items | Retained indefinitely unless deleted |
| Historical / superseded | Retained for the audit horizon |
| **Audit records** | **Retained. Never deleted** |

---

## 7. Deletion and Forgetting

*Full model: [ADR 0013](../decisions/0013-deletion-and-forgetting.md).*

"Delete it" is not one operation. NOVA must distinguish:

| Target | Behaviour |
| --- | --- |
| Source record | Deleted |
| **Derived records** | **Invalidated via lineage** — deleted or re-derived without the source |
| Embeddings / indexes | Deleted with their source; an index entry is a copy |
| Cached copies | Invalidated |
| Summaries | Invalidated — a summary may carry the deleted content |
| Future access | Revoked |
| **Audit records** | **Retained.** The record that something existed and was deleted survives |

**The architectural problem, stated precisely:** deletion is only complete when every
*derivative* is also handled, and derivatives are discoverable only if lineage was recorded
at derivation time. Lineage is therefore not an audit nicety — it is the precondition for
deletion being real.

**Tombstones.** Deleting leaves a tombstone: the item's identity, scope, classification,
deletion time, and authorization — never its content. Tombstones prevent silent
re-derivation and let audit remain complete without retaining the deleted material.

### Limits — what deletion cannot reach

*Added 2026-08-12 following adversarial review.* The cascade covers **recorded lineage within
NOVA-controlled storage**. Universal deletion is not claimed.

- **Backups** taken before deletion still contain the item. **Restoration must consult
  tombstones and re-apply deletion before restored data becomes available** (`I-55`).
- **Already-delivered exports** cannot necessarily be recalled.
- **Data transmitted to external systems** is outside NOVA's direct deletion control.
- **Model-provider retention** is outside NOVA's direct deletion control.
- **Unrecorded derivations** are undiscoverable — the reason lineage recording is mandatory
  (`I-53`).

NOVA must report what was deleted **and what lies beyond reach**, rather than reporting
deletion as complete.

**No legal claims are made here.** Whether any record must be retained for legal reasons is
Section 37's question; this defines the mechanism such a requirement would attach to.

---

## 8. Portability

**James owns his data** (Constitution §13), and must be able to leave NOVA without losing it.

- **Scope is the unit of export.** A client, a business, a life area, or everything.
- **Exports are provider-neutral** — open, self-describing formats, never a vendor dump.
- **Exports carry structure**: scope tree, classification, provenance, lineage, temporal
  state. Data without provenance loses most of its value.
- **Exports respect isolation.** A per-client export contains that client only, and no
  export mixes clients by default.
- **Credentials are never exported** — bindings may be listed; secrets are not NOVA's to
  export.
- **What requires transformation:** embeddings and indexes (derived, regenerable, tied to a
  model — exported as their sources instead), and internal identifiers (exported with a
  stable mapping).

Formats and mechanics are deferred (`D-29a`, Sections 37/44).
