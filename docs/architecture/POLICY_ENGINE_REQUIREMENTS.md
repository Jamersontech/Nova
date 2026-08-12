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

The PDP and the storage enforcement layer are **deliberately independent**
([`ISOLATION_ENFORCEMENT.md`](./ISOLATION_ENFORCEMENT.md) §4). The engine chosen for `D-34`
must not become the mechanism that also enforces storage-layer scope restriction — that would
collapse two independent defenses into one and re-expose the full `T-19` blast radius.

---

## 4. Deferred

`D-34` (policy language and engine) remains **deferred**. §1 is the qualification criteria; a
candidate failing `P-1`–`P-5` or `P-10` is disqualified. Engine selection sits with `D-01`
and `D-02` in Section 29, evaluated against this document.

Invariant: `I-73`.
