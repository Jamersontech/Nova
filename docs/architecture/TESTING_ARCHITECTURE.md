# Testing Architecture

**Status:** Proposed — Section 02.
**Defers:** frameworks and tooling (`D-12`, Section 31).

---

## 1. The Governing Statement

> **An AI system cannot be considered reliable merely because the code runs.**

Conventional testing proves that components behave as written. It cannot prove that an
agent respects a boundary it was merely instructed to respect, that a model produces
adequate output, or that isolation holds under an input nobody anticipated. NOVA therefore
needs two distinct kinds of verification: **deterministic** tests of the system, and
**evaluative** tests of its judgment.

---

## 2. Deterministic Testing

| Kind | Verifies |
| --- | --- |
| **Unit** | Individual components in isolation |
| **Integration** | Components together; connectors against contracts |
| **End-to-end** | Complete flows from request to result |
| **Contract** | External integrations still match their expected shape |
| **Regression** | Previously fixed defects stay fixed |
| **Failure injection** | Behaviour when things break — the paths least exercised in practice |

**Failure injection is not optional.** Every response in
[`RELIABILITY_ARCHITECTURE.md`](./RELIABILITY_ARCHITECTURE.md) is a claim about behaviour
under conditions that rarely occur naturally. Untested recovery paths are, in practice,
broken recovery paths.

---

## 3. Security Testing — The Non-Negotiable Layer

These tests verify the properties the entire architecture rests on. **They must fail loudly
and block everything.**

| Test | Asserts |
| --- | --- |
| **Isolation** | A token for Client A cannot reach Client B's data, memory, credentials, or events — by any path |
| **Permission** | Every enforcement point denies what the PDP denies; no path bypasses a PEP |
| **Credential** | No credential appears in prompts, logs, memory, results, or audit payloads |
| **Context** | No operation touches a resource outside its token's scope |
| **Boundary** | Every crossing in [`SECURITY_BOUNDARIES.md`](./SECURITY_BOUNDARIES.md) §2 behaves as documented |
| **Escalation** | No component can widen its own authority |
| **Sandbox** | A coding agent cannot reach NOVA internals, other clients, or other sandboxes |
| **Injection** | External content treated as instructions does not alter permissions, context, or plans |

**Isolation tests are written adversarially**, from the position of "how would I get from
Client A to Client B?" — not "does the happy path work?" The invariants in
[`DATA_ARCHITECTURE.md`](./DATA_ARCHITECTURE.md) §3 are the specification these tests
enforce.

---

## 4. Agent and AI Evaluation

Different in kind: these measure quality and judgment, and results are distributions rather
than pass/fail.

| Evaluation | Measures |
| --- | --- |
| **Agent** | Does it meet its declared success criteria across representative cases |
| **Boundary adherence** | Does it stay within its Non-Responsibilities when tempted |
| **Escalation** | Does it escalate when it should, rather than proceeding uncertainly |
| **Honesty** | Does it label fact, inference, assumption, unknown correctly (Constitution §14) |
| **Tool use** | Does it choose correct tools with correct arguments |
| **Orchestration** | Do plans achieve intent; is verification catching bad results |
| **Model routing** | Is the cheapest adequate model actually adequate |
| **Regression** | Has behaviour degraded after a change to prompts, models, or definitions |

**Success criteria and failure conditions are mandatory agent fields**
([`../ai/AGENT_PRINCIPLES.md`](../ai/AGENT_PRINCIPLES.md) §2) precisely so this is possible.
An agent whose success cannot be measured cannot be evaluated, and must not be trusted with
greater authority.

**Model and prompt changes require re-evaluation.** A provider's silent model update can
change behaviour with no code change — which is why evaluation must be repeatable and
scheduled, not run once at build time.

---

## 5. What "Verified" Means

Adopted from [`../development/DEVELOPMENT_RULES.md`](../development/DEVELOPMENT_RULES.md) §9
and sharpened for AI work:

- "The code runs" is not verification.
- "The tool returned success" is not verification.
- "The model produced output" is certainly not verification.
- **Verification is: the declared success criteria were met, and the security properties
  still hold.**

Where no test infrastructure exists yet, state plainly what was and was not verified rather
than implying verification that did not happen.

---

## 6. Testing in an Empty Repository

NOVA has no code yet. This document is a **requirement on Sections 03 onward**: as each
system is built, its tests are built with it — particularly the security tests in §3, which
must exist from the first line of code that touches a scope. Retrofitting isolation tests
onto an existing system means discovering the leaks in production.
