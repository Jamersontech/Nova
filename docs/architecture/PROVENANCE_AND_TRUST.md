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

Provenance includes: source identity, timestamp, the execution and context that produced it,
and the source items it derived from — the **lineage** chain
([`DATA_LIFECYCLE.md`](./DATA_LIFECYCLE.md) §5).

---

## 3. Trust

Trust is a property of the **source**, evaluated at use time, and may change without
rewriting history. A previously reliable integration that starts returning malformed data
loses trust; everything it supplied keeps its provenance and is re-weighted.

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
integration.supplied + fresh          → fact about the external system at that moment
integration.supplied + stale          → assumption
```

**Confidence is not provenance and not trust.** A model's certainty about its own output
carries no evidential weight and may never promote an item's epistemic status.

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
