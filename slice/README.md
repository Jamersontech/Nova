# NOVA Vertical Slice

**A validation artifact, not a product.** It exists to find out whether the architecture in
`docs/` can actually execute, and to surface the places where it cannot.

Run:

```
python3 -m unittest slice.tests.test_security -v
```

39 tests, no dependencies, no network.

---

## Governance

**Authorized by James on 2026-08-15 as a C3 decision.** Application infrastructure is
normally owned by **Section 29**, and `AGENTS.md` says an agent must confirm which roadmap
section authorizes application functionality before building it. **That confirmation is
this: James directed validation-first implementation ahead of Section 29.**

**Nothing about the roadmap changed.** No section was added, removed, renumbered, reordered
or marked complete. **Section 29 is not started.**

---

## What this does NOT decide

The three technology choices are **slice-local implementation choices** and select
**nothing**:

| Deferred decision | Slice uses | Still deferred? |
| --- | --- | --- |
| `D-01` application language/runtime | Python (3.11 here; 3.12 was proposed — the environment had 3.11 and the code is compatible with both), stdlib only | **Yes — owner 02/29** |
| `D-02` database technology | SQLite, one file per scope | **Yes — owner 29** |
| `D-10` secrets store technology | A separate JSON file, broker-only path | **Yes — owner 04** |
| `D-33a` isolation mechanism | Per-scope files | **Yes — not selected** |

No document in `docs/` was changed to imply otherwise. **ADRs 0032–0040 remain Proposed**
and none was accepted.

---

## The five states, and which this reaches

The distinction matters more than the test count.

| State | Reached? | Detail |
| --- | --- | --- |
| **DOCUMENTED** | ✅ | Sections 01–14 |
| **IMPLEMENTED** | ✅ | The path below exists as code with visible boundaries |
| **EXECUTED** | ✅ | It runs; the control test performs a real end-to-end action |
| **SECURITY-TESTED** | ⚠️ **Partially** | 39 adversarial tests pass. They cover the paths the slice implements — not the architecture |
| **PROVEN AGAINST A REAL EXTERNAL SYSTEM** | ❌ **No** | No network, no real provider, no real credential, no real model |

**This slice does not validate NOVA.** It validates that a narrow path through the
architecture is implementable, and it found two things wrong on the way
(`FINDINGS.md`).

### Specifically NOT proven

- **`I-03` physical isolation.** `I-03` is `[PHYS]` and requires enforcement **below the
  query layer**. Per-scope SQLite files are stronger than an application-side filter and
  are **not** the production mechanism. `D-33a` is unselected. The slice proves the
  *token and PDP* layer denies cross-scope access; it proves nothing about a compromised
  data layer.
- **`I-87` token unforgeability.** An HMAC gives **detection**, which is what CT-1 asks
  for. Unforgeability is not claimed — the architecture does not claim it either.
- **Anything involving a real model.** The Planner is a deterministic fixture *labelled*
  `model.generated`. That exercises the taint machinery correctly and proves nothing about
  a real model's behaviour.
- **Anything involving a real provider.** `T-39`'s semantic-divergence residual — a
  provider interpreting an argument differently than declared — is **untestable here by
  construction**, since the local integration does exactly what it is told.

---

## The path

```
caller identity
 -> ScopeTree            scopes, James-created grants (I-10, I-14)
 -> ContextService       SOLE issuer (I-106); HMAC integrity (I-87)
 -> AgentRegistry        13 required fields; refuses incomplete definitions
 -> Planner              model.generated, LOW trust (I-99, I-112)
 -> scope precheck       I-03 -- BEFORE resolution (see FINDINGS.md 1)
 -> CapabilityLayer      binding resolved BEFORE the decision (I-114(a))
 -> PolicyDecisionPoint  ten steps in order; envelope (I-113, I-114(b))
 -> ToolPEP              I-100 arguments, I-109 re-check, I-114(b) re-resolve
 -> CredentialBroker     steps 1-7 + 2a; per-attempt injection (I-22, I-24, I-70)
 -> LocalEcho            deterministic; success / failure / unknown / partial
 -> Outcome              taint unioned (I-99, I-27), persisted and restored (I-111)
 -> AuditWriter          W-1 / W-2; fail-closed (I-93)
```

## Deliberate absences

There is no method anywhere that:

- lets a tool authorize itself, or reach an integration except through the Tool PEP
- returns credential material upward from the broker
- lets the Agent Runtime mint a Context Token
- lets the Planner authorize its own plan
- substitutes an "equivalent" provider, or falls back to an ancestor's binding
- reads across two scopes in one query

Each absence is an architectural requirement, not an oversight.
