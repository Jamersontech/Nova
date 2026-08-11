# NOVA Development Rules

**Status:** Active — established in Section 01.
**Audience:** Humans and AI coding agents working in this repository.

---

## 1. Priority Order

When two goals conflict, the higher one wins:

```text
1. Security
2. Reliability
3. Maintainability
4. Extensibility
5. User simplicity
6. Performance
7. Cost efficiency
8. Development speed
```

Development speed is last. It must never override a higher priority. "It was faster" is
not a justification for weakening security, hiding a failure, or degrading clarity.

Note that user simplicity ranks above performance and cost: a system that is fast and
cheap but confusing to James has failed at its purpose.

---

## 2. No Unnecessary Refactoring

A small request should normally produce a small change.

Do **not**:

- rewrite unrelated code
- redesign unrelated systems
- rename unrelated components
- reorganize the repository for cosmetic reasons
- install unnecessary dependencies
- replace working architecture without justification
- make broad changes because they "seem cleaner"

If a request genuinely requires a larger architectural change, stop and explain why
before making it. Scaling a change up is James's decision, not the agent's.

---

## 3. Inspect Before Modifying

Read the existing implementation before changing it. Do not assume a previous
AI-generated implementation is correct, and do not assume it is wrong. Verify.

Identify which systems a change affects before making it, and say so in the report.

---

## 4. Preserve Architectural Boundaries

The separated concerns in the Constitution §8 — UI, application logic, AI/orchestration,
business logic, data, integrations, authentication, authorization, secrets,
infrastructure, observability — are not mixed for convenience. A change that would blur a
boundary is an architectural change and follows the change-management process for one.

---

## 5. Secrets

- Never hard-code secrets.
- Never commit secrets to Git.
- Never place secrets in documentation, examples, tests, fixtures, or commit messages.
- Never paste secrets into agent context that does not require them.
- If a secret is exposed, treat it as compromised and report it immediately.

---

## 6. Client Isolation

No change may weaken client isolation. Interface-level hiding is not isolation. Any code
path that could return one client's data inside another client's context is a defect
regardless of whether it is currently reachable.

---

## 7. Dependencies

Dependencies are a long-term liability, not a free convenience.

- Add a dependency only when it is genuinely required by the work at hand.
- Prefer no dependency over a trivial one.
- Do not add speculative dependencies for future sections.
- Record significant dependency choices as decisions (see
  [`../decisions/README.md`](../decisions/README.md)).

---

## 8. Technology Decisions

Do not make detailed technology decisions that belong to a future section — databases,
cloud providers, AI/model providers, queues, vector databases, orchestration platforms,
hosting platforms, infrastructure platforms — unless the existing repository requires an
immediate decision.

When a decision is intentionally postponed, record it in
[`../decisions/DEFERRED_DECISIONS.md`](../decisions/DEFERRED_DECISIONS.md) as
**Deferred — to be resolved in a future section.** Do not guess.

---

## 9. Testing and Verification

Changes are tested with whatever verification the repository supports at the time. When
no test infrastructure exists yet, say plainly what was and was not verified rather than
implying verification that did not happen.

Report failures with their actual output. A failing test is information, not something to
route around.

---

## 10. Reporting

At the end of a unit of work, report:

- files changed
- assumptions made
- what was verified and how
- unresolved issues and known gaps

Do not report work as complete when part of it was skipped or blocked. State what was
left out and why.

---

## 11. No Fake Functionality

Do not create placeholder systems that pretend to work, mock data presented as real,
or interfaces wired to nothing while appearing functional. An unbuilt system is
documented as unbuilt.
