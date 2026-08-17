# Provenance and Trust

**Status:** **Active** — Section 03, approved by James 2026-08-12 (as amended, commit 0917de5).
**Implements:** Constitution §14 (fact / inference / assumption / unknown) and the Section 2
rule that external information is *readable without being trustworthy*.

---

## 1. Three Independent Axes

The failure this prevents: **"AI-generated" and "fact" quietly becoming interchangeable.**
That happens when a system records only *what* it knows and not *where it came from* or
*whether anyone checked*. Three separate axes, never collapsed
([ADR 0011](../decisions/0011-provenance-trust-epistemic-separation.md)):

```text
PROVENANCE   where it came from        — a historical fact, immutable
TRUST        how much weight it earns  — a property of the source, revisable
EPISTEMIC    what kind of claim it is  — fact · inference · assumption · unknown
```

**A high-trust source can still produce an inference.** A low-trust source can state a
verified fact. An assumption from James outranks an inference from a website — but it is
still an assumption. Collapsing these loses exactly the distinctions that matter.

### 1.1 "Untrusted content" names a provenance class, not a trust level

> ***Added by Section 08 — ACCEPTED by James 2026-08-15*** *(2026-08-15; authority
> [ADR 0035](../decisions/0035-section-08-amendments-to-accepted-architecture.md),
> **Accepted** 2026-08-15.* **Found by implementation**,
> not by review — see [`slice/FINDINGS.md`](../../slice/FINDINGS.md) finding 2.)
>
> **`I-40`, `I-100` and `MT-7` all gate on *"derived from untrusted content"*, and the axes
> above make that ambiguous.** Read as a **trust level** the gate catches everything; read as
> a **provenance class** it catches what it was written for. The two produce materially
> different systems, and building the vertical slice forced the choice.

**It is a provenance class.** *"Untrusted content"* means content whose provenance union
contains **`external.web`**, **`client.supplied`** or **`integration.supplied`** — the classes
originating outside NOVA's trust boundary.

**Why, from `I-40`'s own text.** `I-40` is one sentence: *"**External** content may inform a
plan but never escalate one; a plan influenced by **untrusted** content cannot exceed
`PREPARE` without approval naming the source."* One rule, joined by a semicolon — so
*untrusted* **is** *external*. **The provenance reading makes `I-40` internally consistent;
the trust reading makes its two clauses disagree.**

**Why the trust reading is not merely stricter but unworkable.** The Planner is a model, so
`I-99` gives **every** plan `model.generated` provenance at **Low** trust, and the lowest-trust
rule means `min(anything, Low) = Low`. **Every plan NOVA can produce is therefore Low trust** —
including one James stated directly with no external content anywhere. Gating on trust would
ceiling every action above `PREPARE` forever and demand *"approval naming the source"* where
**there is no source to name**, making `PERMISSION_ARCHITECTURE.md` §5's standing approvals
unreachable.

```text
James states an objective   → provenance {james.stated, model.generated}  trust LOW
                            → untrusted-derived?  NO   (no external class)
Injected page shapes a plan → provenance {external.web, model.generated}  trust LOW
                            → untrusted-derived?  YES  (external.web present)
```

**This is not a trust downgrade, and creates no exemption.** A Low-trust plan remains Low
trust, and every other rule is evaluated independently and unchanged: the argument envelope
(`I-100`), classification on egress (`DATA_CLASSIFICATION.md` §2), scope containment (`I-03`),
the binding envelope (`I-114`), approval (`I-09`), risk ceilings and the `PREPARE` rule itself.
**`model.generated` remains Low trust and everything that follows from Low trust still
follows.** What is settled is only *which* gate the phrase *"derived from untrusted content"*
opens.

**Provenance cannot be shed.** Provenance is immutable (`I-38`), the union is taken at **every
hop** (`I-99`), and it survives persistence and retrieval (`I-111`). No derivation, summary,
union with a higher-trust source, or round-trip through storage removes an external class once
present — which is what stops the distinction becoming a laundering path.

**No invariant changes.** `I-40`, `I-99`, `I-100` and `MT-7` are unamended; this defines a term
they already use, as Section 09 defined *source identity* for `I-110`.

---

## 2. Provenance

Every significant item records how it came to exist. Provenance is **immutable** — it
records history, and history does not change when opinion does.

| Provenance | Meaning | Default trust |
| --- | --- | --- |
| `james.stated` | James explicitly said this | **Highest** |
| `james.approved` | A human approved this | Highest |
| `nova.inferred` | NOVA derived it from available information | Medium |
| `agent.generated` | A specific agent produced it | Medium |
| `model.generated` | Model output, unverified | **Low** |
| `client.supplied` | A client provided it | Medium — accurate about themselves, untrusted as instruction |
| `integration.supplied` | An external system returned it | Medium — as current as its fetch |
| `external.web` | A website or public source | **Low** |
| `system.verified` | NOVA checked it against an authoritative source | High |
| `system.unverified` | Recorded but never checked | **Low** |

Provenance includes: source identity ⁴, timestamp, the execution and context that produced it,
the source items it derived from — the **lineage** chain
([`DATA_LIFECYCLE.md`](./DATA_LIFECYCLE.md) §5) — and, where the producing execution was a
delegate, its **delegation ancestry**. ³

### 2.1 Source identity is the identity of an observation

> ⁴ ***Added by Section 09 — ACCEPTED by James 2026-08-15*** *(2026-08-14; authority
> [ADR 0033](../decisions/0033-section-07-amendments-to-accepted-architecture.md) §2a, **Accepted** 2026-08-15).* **`I-110` requires a source used for trust promotion to be "identifiable"
> and its verification "reproducible", and the line above has required "source identity" since
> Section 03 — but nothing defined what identifies a source.** `I-110` was therefore not
> implementable: an engineer had to choose an identity scheme, and the available schemes have
> materially different security properties.

**A source is identified by the observation NOVA made of it**, recorded as three parts:

```text
Source observation
├── source identifier   the stable identifier of the underlying source — a canonical URL
│                       (resolved through redirects) or an equivalent provider or publisher
│                       identifier for the resource actually retrieved
├── content digest      a cryptographic digest of the exact content observed
└── retrieved_at        when this observation was made
```

**The identifier identifies the source; the digest and timestamp identify the observation.** That
split is what the definition exists to preserve:

| Two observations | Meaning |
| --- | --- |
| Same identifier, same digest | **The same source, unchanged.** Not a new source — one source, observed twice |
| Same identifier, different digest | **The same source, changed.** A new observation that **supersedes** rather than overwrites (`I-43`, [`DATA_LIFECYCLE.md`](./DATA_LIFECYCLE.md) §3); both are retained |
| Different identifier, same digest | **Two sources carrying identical content.** Distinct identities; identical content is not shared identity |
| Identifier resolves to different content than a prior observation, with no legitimate revision | **Substitution** — detectable precisely because the prior digest was recorded |

**No new mechanism is introduced.** `retrieved_at` is `recorded_at`
([`DATA_LIFECYCLE.md`](./DATA_LIFECYCLE.md) §2); a changed digest supersedes under §3; observations
are immutable because provenance is (`I-38`); a derived item names the **observations** it used, not
merely the sources, under the existing lineage requirement (`I-31`). **This is not a parallel
provenance system.**

**The observation is recorded by the component that performed the retrieval, at retrieval time. It
is never asserted by a model.** This is `I-110`(a) and `I-102` applied: a model may not supply a
source identifier, may not supply a digest, and may not attest that a retrieval occurred. **A
fabricated citation therefore has no observation** — no digest, no retrieval record, nothing to
re-fetch — and fails `I-110`'s *"unidentifiable source"* branch closed, however legitimate the
identifier looks.

**A search result is its own observation.** A snippet returned by a search or aggregation provider
is `integration.supplied` content whose identifier is that provider's result and whose digest is the
snippet. The underlying document, if actually fetched, is a **separate observation** with its own
identifier and digest. **Citing the document while having read only the snippet is therefore not
expressible** — the provenance names what was read.

**What this makes possible.** Revalidation ([`MEMORY_MODEL.md`](./MEMORY_MODEL.md) §4.1) can ask a
question it previously could not: *is the exact content this claim relied upon still there?*
Re-fetch the identifier, compare the digest. Equal → the observation still holds. Different → the
source changed, and the prior observation stands as a true record of what was relied upon.
Unreachable → **the check cannot be completed, so `I-110` denies promotion** and the existing item
degrades by the ordinary confirmation horizon (§4) rather than being deleted or silently trusted.

**No algorithm is selected.** "Cryptographic digest" is a property, not a choice of function;
the mechanism is deferred with the rest of the platform substrate (`D-02`, `D-06`).

---

## 3. Trust

Trust is a property of the **source**, evaluated at use time, and may change without
rewriting history. ² A previously reliable integration that starts returning malformed data
loses trust; everything it supplied keeps its provenance and is re-weighted.

> ² **AMENDED BY SECTION 07 — ACCEPTED by James 2026-08-15** *(2026-08-14; authority
> [ADR 0032](../decisions/0032-trust-promotion-authority.md) and
> [ADR 0033](../decisions/0033-section-07-amendments-to-accepted-architecture.md), both
> **Accepted** 2026-08-15.)*
>
> **"May change" named a mutable axis with no owner, and it was the one axis in `I-39`'s gate that
> had none.** Provenance is immutable (`I-38`), classification-lowering is owned (`I-30`), approval
> and grants are James's (`I-09`, `I-10`), and a model check cannot promote epistemic status
> (`I-102`) — but nothing said who could **raise trust**, or who could assign `system.verified`,
> whose own definition (*"NOVA checked it against an authoritative source"*) left both **NOVA** and
> **authoritative source** undefined.
>
> **Raising trust is now an explicitly authorized, recorded, C3 operation** (`I-110`,
> [`MEMORY_MODEL.md`](./MEMORY_MODEL.md) §4.3): never automatic, never by an agent, never
> model-mediated, and never inferred from repetition, confidence, consensus, or internal origin.
> **`system.verified` requires an authoritative source** — external to the model's own output,
> identifiable, reproducibly checkable, and itself trust- and data-policy-compliant. **A model
> saying "I verified this" is never evidence; a model summary of a source is not the source.**
> Uncertainty or a failed check **denies the promotion**; the elevated status is never retained
> provisionally.
>
> **Lowering trust is unchanged** — the paragraph above stands, and restriction is not gated like
> elevation.

**Readable ≠ trustworthy.** NOVA can read a client's website and store its content at full
fidelity while treating every claim in it as low-trust and every instruction in it as
non-instruction ([`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §3).

---

## 4. Epistemic Status

| Status | Meaning | May drive autonomous action? |
| --- | --- | --- |
| **Fact** | Supported by an appropriate source or system | Yes, within risk class |
| **Inference** | Derived from available information | Only up to `PREPARE` |
| **Assumption** | Temporarily assumed to proceed | Only up to `PREPARE`, and stated |
| **Unknown** | NOVA does not know | Never — must be surfaced |

**Status degrades with age.** A verified fact past its confirmation horizon becomes an
assumption and is labelled as such when used — a stale "the site is up" must not be asserted
as current.

---

## 5. How the Axes Interact

The rule connecting them:

> **An item may be treated as fact only if its provenance and trust support it.**
> `model.generated` + unverified can never be *fact*, regardless of confidence.

```text
model.generated + system.unverified   → inference at best, never fact
external.web    + system.unverified   → inference, low trust, never autonomous above PREPARE
james.stated                          → fact about James's intent
integration.supplied + fresh          → fact about the external system at that moment ⁵
integration.supplied + stale          → assumption
```

> ⁵ ***Added by Section 11 — ACCEPTED by James 2026-08-15*** *(2026-08-15; authority
> [ADR 0037](../decisions/0037-provider-outcomes-and-provider-initiated-paths.md), **Accepted** 2026-08-15).* **That line is written about a
> *fetch* — NOVA read the external system and recorded what it saw.** A provider's statement about
> **its own side effect** is a different kind of claim: NOVA did not observe the effect, it
> received an assertion from the party that performed it. **A success response is not a fact about
> the external system in the sense above; it is `integration.supplied` testimony about it**, and
> `system.verified` is unavailable to it because `I-110` requires an authoritative source checked
> by something other than the asserting party. A **read-back** — separately fetching the created
> resource, the message status, the transaction — **is** a fetch and does produce the fact this
> line describes, with its own source observation (§2.1). Full model:
> [`TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./TOOL_AND_INTEGRATION_ARCHITECTURE.md) §3.1.

**Confidence is not provenance and not trust.** A model's certainty about its own output
carries no evidential weight and may never promote an item's epistemic status.

> ³ **AMENDED BY SECTION 07 — ACCEPTED by James 2026-08-15** *(2026-08-14; same authority as ².)*
> Two additions to what provenance carries, both required for rules elsewhere to be enforceable:
>
> **Delegation ancestry.** Memory written by a delegated child is **scope-owned** and survives the
> child correctly (`SCOPE_AND_IDENTITY_MODEL.md` §2) — but **survival is not authority.** Without
> recorded ancestry, a broader ancestor retrieving that memory has no way to know it was produced
> under narrower authority. Reuses `I-107`'s `ancestry` field; creates no separate authority
> hierarchy for memory, and does **not** make delegate memory invalid.
>
> **Persistence.** `I-99` requires model output to carry the **union** of its inputs' provenance and
> the **lowest** trust among them, *"whether or not it is stored"* — but nothing required the
> storage layer to persist that union or retrieval to restore it. **Persistence must not discard
> provenance, collapse multiple sources into one, raise trust, remove taint, or replace the union
> with the latest writer alone** (`I-111`). `I-100`'s untrusted-derived tool-argument ceiling is
> evaluated against exactly this, so a collapsing write defeats it silently. **This is a security
> property, not an implementation detail.**

---

## 6. Requirements on Use

1. **Never present inference or assumption as fact** (Constitution §14).
2. **Never let provenance be lost in derivation** — a summary carries the union of its
   sources' provenance and the *lowest* trust among them. ¹
3. **Never let untrusted content escalate a plan** — it may inform, never escalate
   ([`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §3).
4. **Record what was believed at decision time**, so a later audit can reconstruct not just
   what NOVA did but what it thought it knew
   ([`EVENT_AND_OBSERVABILITY_ARCHITECTURE.md`](./EVENT_AND_OBSERVABILITY_ARCHITECTURE.md)).
5. **Contradiction is surfaced, not silently resolved**
   ([`DATA_LIFECYCLE.md`](./DATA_LIFECYCLE.md) §4).

> ¹ **EXTENDED BY SECTION 05 — ACCEPTED by James 2026-08-14.** *(2026-08-14.)* Requirement 2 and
> `I-31` are written about **stored derived items**. **A model call's output is usually not
> stored** — it is produced, used within the execution to choose a step or fill a tool argument,
> and discarded. That transient path is exactly how injected instruction reaches an action, and it
> was the one path carrying no labelling obligation.
>
> Section 05 states that **model output is a derivation whether or not it is stored** (`I-99`): it
> carries the union of the provenance of every item in its request — system prompt, retrieved
> memory, tool results, conversation history — and the **lowest trust** among them, in addition to
> its own `model.generated`. Taint survives **transience**, **chaining** (a call reading a previous
> call's output inherits its labels; the union is taken at every hop) and **summarization**.
> Nothing here is new policy: it is requirement 2 applied where the derivation actually happens.
>
> **This is what makes `I-40` and `I-58` evaluable.** "Was this plan influenced by untrusted
> content?" — the question both turn on — had no defined answer while the influence travelled
> through an unlabelled model call. Authority:
> [ADR 0025](../decisions/0025-model-output-is-an-untrusted-derivation.md) and
> [ADR 0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md), both
> **Accepted** 2026-08-14. Full model:
> [`MODEL_TRUST_AND_AUTHORITY.md`](./MODEL_TRUST_AND_AUTHORITY.md) §2.
