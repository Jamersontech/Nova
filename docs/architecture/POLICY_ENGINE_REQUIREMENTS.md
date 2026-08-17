# Policy Engine Requirements

**Status:** Proposed — Section 04, pending James's approval.
**Owns:** the Section 04 half of `D-34`. **No policy language or engine is selected.**
**Implements:** [ADR 0014](../decisions/0014-authorization-decision-model.md) — the ordered,
fail-closed decision sequence.

---

## 1. What the Engine Must Do

The decision sequence is fixed by ADR 0014 and is not open to reinterpretation by an engine's
evaluation model:

```text
1 context valid → 2 subject known → 3 scope containment → 4 explicit denial
→ 5 grant present → 6 risk ceiling → 7 classification → 8 conditions
→ 9 approval required? → 10 allow
```

**P-1 — Order is preserved.** Containment (step 3) is evaluated before grants (step 5). An
engine whose evaluation model cannot guarantee ordering — or which resolves conflicts by
priority scores or last-match-wins — does not satisfy ADR 0014.

**P-2 — Deny overrides.** An explicit denial beats any grant, without exception and without a
priority mechanism that could invert it (`I-15`).

**P-3 — Default deny.** Absence of a grant is denial. The engine must have no permissive
default and no implicit allow (`I-14`).

**P-4 — Total.** Every decision returns exactly one of `allow`, `deny`, `approval-required`.
No "unknown", no "not applicable", no empty result treated as allow.

**P-5 — Deterministic.** The same inputs produce the same decision. No probabilistic
evaluation, no learned thresholds, no time-varying behaviour other than declared conditions.

**P-6 — Explainable.** Every decision reports which step decided it. A denial that cannot say
why is unusable operationally and untestable.

**P-7 — Fast enough for every call.** The PDP is on the hot path of every action. Slow
authorization produces pressure to cache or bypass it, and bypass is how isolation rots.

**P-8 — Testable in isolation.** Decisions must be exercisable without running the rest of
NOVA, so the invariants in [`INVARIANTS.md`](./INVARIANTS.md) can be tested directly.

**P-9 — Policy is versioned and audited.** Policy changes are C3 changes
([ADR 0008](../decisions/0008-architectural-governance-model.md)), recorded, and attributable.

**P-10 — No model in the decision path.** Authorization is never decided by an AI model.
Model output may *request* an action; it never *authorizes* one (`I-20`).

**P-11 — The engine must not also be the storage enforcement mechanism.** The engine chosen for
`D-34` must not become the layer that enforces storage-layer scope restriction. The storage
enforcement layer must not consult the PDP (`R-7`, `I-62`), and an engine that *is* the
enforcement layer cannot satisfy that requirement. §3 states what this does and does not buy.
*(Moved here 2026-08-13, R-7 — `P-11` was defined in §3 while `P-1`–`P-10` sat here and §4 listed
it as disqualifying, so an implementer reading the requirement set would miss it.)*

**P-12 — Token integrity is part of step 1.** *(Moved here 2026-08-13, R-7, with `P-11`.)* Step 1
of the ADR 0014 sequence — *context valid* — includes detecting a Context Token modified after
issuance or fabricated by a non-issuer, and refusing it (`I-87`, `CT-1`–`CT-3`,
[`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §6). An engine that cannot be given a
token-validity input, or that treats an unverifiable token as evaluable, does not satisfy `P-4`
or step 1. **This is a detection requirement on a mechanism that does not yet exist** (`I-87` is
`[PHYS]`); no unforgeability is claimed.

`P-10` deserves emphasis: an LLM asked "should this be allowed?" is non-deterministic,
unexplainable, and manipulable by injected content — it violates `P-4`, `P-5`, `P-6`, and
`I-20` simultaneously.

---

## 2. Policy Authoring

**Who may write policy.** Policy changes are C3 — James approves; an agent may draft.
No agent modifies policy, and no policy grants an agent the ability to modify policy
(`I-73`).

**Policy is data, not code.** Expressed declaratively so it can be reviewed, diffed, tested,
and audited. Policy expressed as general-purpose code becomes unreviewable and can smuggle
side effects into the decision path.

**Policy must not be able to weaken an invariant.** The invariants are architecture; policy
operates *within* them. A policy that would permit a cross-client read is invalid and must be
rejected at authoring time, not merely produce a denial at runtime.

---

## 3. Relationship to Isolation Enforcement

*Corrected 2026-08-13 (N-1). The earlier text called the two "deliberately independent" and
described collapsing them as losing "two independent defenses". That is the general-independence
claim withdrawn under H-2, and it is not what the architecture establishes.*

**The independence this preserves is narrow, and stating it precisely matters:**

| Claim | Status |
| --- | --- |
| The enforcement layer is independent **of the PDP** | **Established.** It never consults the PDP (`R-7`, `I-62`), so a compromised PDP alone yields no cross-client data |
| The two are independent **of each other** | **Established**, in that direction only |
| The two are independent **of the Context service** | **NOT established, and not claimed.** Both derive their input from the Context Token. Compromise of the Context service, or of token issuance, defeats both together from a single point (`T-23a`) |
| General two-of-two independence | **Not claimed** (`I-62`) |

Collapsing the engine into the enforcement layer therefore removes the **PDP-compromise**
mitigation specifically ([ADR 0017](../decisions/0017-isolation-independent-of-pdp.md)) and
returns `T-19` to its full blast radius. It does not remove a general two-of-two property,
because there is none to remove.

**Token integrity is `P-12`**, stated with the rest of the requirement set in §1.

---

## 4. Deferred

`D-34` (policy language and engine) remains **deferred**. §1 is the qualification criteria; a
candidate failing `P-1`–`P-5`, `P-10`, `P-11`, or `P-12` is disqualified. Engine selection sits with `D-01`
and `D-02` in Section 29, evaluated against this document.

Invariants: `I-73`, `I-87`.
