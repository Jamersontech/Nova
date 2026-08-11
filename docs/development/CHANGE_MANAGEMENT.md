# NOVA Change Management

**Status:** Active — established in Section 01.
**Purpose:** Define how changes to NOVA are made, so that changes remain deliberate,
traceable, and reversible in intent.

---

## 1. Standard Change Process

Most changes follow this sequence:

```text
REQUEST
 ↓
UNDERSTAND
 ↓
INSPECT
 ↓
PLAN
 ↓
IDENTIFY AFFECTED SYSTEMS
 ↓
IMPLEMENT
 ↓
TEST
 ↓
VERIFY
 ↓
DOCUMENT
```

| Stage | What it means |
| --- | --- |
| Request | The stated ask, in James's words. |
| Understand | Resolve what is actually being asked; ask if materially ambiguous. |
| Inspect | Read the existing implementation and relevant documentation. |
| Plan | Decide the smallest change that satisfies the request. |
| Identify affected systems | Name what else the change touches before touching it. |
| Implement | Make the scoped change. |
| Test | Run the verification the repository supports. |
| Verify | Confirm the original request is satisfied, not merely that code runs. |
| Document | Update documentation the change makes stale. |

Documentation is part of the change, not a follow-up task. A change that makes a document
wrong is not finished until the document is correct.

---

## 2. Architectural Change Process

Large architectural changes additionally require approval before implementation:

```text
PROPOSE
 ↓
REVIEW
 ↓
APPROVE
 ↓
IMPLEMENT
 ↓
TEST
 ↓
DOCUMENT
```

Approval comes from James. An AI agent may propose and may recommend; it may not approve
its own architectural change.

A change is architectural if it:

- alters a boundary between separated concerns (Constitution §8)
- changes the domain model or its hierarchy
- affects permissions, isolation, credentials, or approval behaviour
- commits NOVA to a provider, platform, or storage technology
- changes an agent's authority, permissions, or context scope
- contradicts approved documentation
- would be difficult to reverse

Approved architectural changes are recorded as decisions (see
[`../decisions/README.md`](../decisions/README.md)).

---

## 3. Handling Conflicts

When a request conflicts with approved architecture or documentation, identify the
conflict and raise it. Do not silently choose a side. The precedence order is in the
Constitution §16:

```text
Approved Architecture → Approved Documentation → Current Implementation → Temporary Conversation Instructions
```

An instruction given in conversation does not override approved documentation. It may
become an approved change — through the process above.

---

## 4. Scope Control

The delivered change matches the requested scope: not quietly narrowed, not widened, not
transformed. If the work reveals that a larger change is needed, say so and let James
decide.

---

## 5. Git Practice

- Commit messages describe what changed and why, in plain language.
- Related changes are committed together; unrelated changes are not.
- Secrets never enter a commit, a branch, or a commit message.
- Work is pushed to the branch that was designated for it, never to another branch
  without explicit permission.
