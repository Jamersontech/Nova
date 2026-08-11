# AGENTS.md — Coding-Agent Governance for NOVA

**Status:** Active — established in Section 01.
**Audience:** Every coding agent working in this repository, regardless of provider
(Claude Code, Codex, or any future tool), and the humans working alongside them.

This file is the provider-neutral instruction layer. Provider-specific files (such as
[`CLAUDE.md`](./CLAUDE.md)) are thin adapters to this file and to `/docs`. They do not
replace it and must not contradict it.

---

## What NOVA Is

NOVA is a private AI operating system for its owner, James. It is a long-lived system
intended to be developed across many sessions by many agents. The repository — not any
conversation — is its memory.

Read [`docs/CONSTITUTION.md`](./docs/CONSTITUTION.md) before making meaningful changes.

---

## The Fourteen Rules

1. **Read the relevant NOVA documentation before making changes.** Start with the
   Constitution and the documents listed below that touch your work.
2. **Inspect the existing implementation before modifying it.** Read the code that exists.
   Do not modify what you have not read.
3. **Identify affected systems** before changing anything, and name them in your report.
4. **Preserve architectural boundaries.** Do not blur the separated concerns in
   Constitution §8 for convenience.
5. **Avoid unrelated changes.** A small request produces a small change. No cosmetic
   reorganization, no drive-by renames, no unrequested refactors.
6. **Follow the repository's source of truth.** Approved architecture and documentation
   outrank current implementation, which outranks conversation instructions.
7. **Test your changes** with whatever verification the repository supports, and report
   honestly what you did and did not verify.
8. **Report your assumptions** — every meaningful one, explicitly.
9. **Report every file you changed.**
10. **Report unresolved issues,** including work you could not complete and problems you
    noticed but did not fix.
11. **Never silently make major architectural decisions.** Propose, explain, and wait for
    approval. (See [`docs/development/CHANGE_MANAGEMENT.md`](./docs/development/CHANGE_MANAGEMENT.md).)
12. **Never expose or commit secrets** — not in code, config, documentation, tests,
    fixtures, logs, or commit messages.
13. **Never bypass client isolation.** One client's data must never be reachable from
    another client's context. Interface-level hiding is not isolation.
14. **Never assume a previous AI-generated implementation is correct.** Verify it. Prior
    output carries no authority.

---

## Documentation Map

| Read this | When |
| --- | --- |
| [`docs/CONSTITUTION.md`](./docs/CONSTITUTION.md) | Always. Golden Rules, authority, control, source of truth. |
| [`docs/DOMAIN_MODEL.md`](./docs/DOMAIN_MODEL.md) | Business, client, project, environment, credentials, isolation. |
| [`docs/ai/AI_TERMINOLOGY.md`](./docs/ai/AI_TERMINOLOGY.md) | Before using the words agent, tool, workflow, context, memory, permission, approval. |
| [`docs/ai/AGENT_PRINCIPLES.md`](./docs/ai/AGENT_PRINCIPLES.md) | Before creating or changing any NOVA agent. |
| [`docs/development/DEVELOPMENT_RULES.md`](./docs/development/DEVELOPMENT_RULES.md) | Before writing code. Priority order, dependencies, secrets. |
| [`docs/development/CHANGE_MANAGEMENT.md`](./docs/development/CHANGE_MANAGEMENT.md) | Before any change that might be architectural. |
| [`docs/design/DESIGN_PRINCIPLES.md`](./docs/design/DESIGN_PRINCIPLES.md) | Before building or altering interface. |
| [`docs/decisions/`](./docs/decisions/README.md) | To check whether a question is already settled or deliberately deferred. |
| [`docs/ROADMAP.md`](./docs/ROADMAP.md) | To confirm which section owns the work you are being asked to do. |

Note: the agents defined *inside* NOVA (`AGENT_PRINCIPLES.md`) are a different thing from
the coding agents this file governs. Do not conflate them.

---

## Current State of the Repository

As of Section 01, NOVA contains **documentation only**. There is no application, no
database, no dependency manifest, no build, and no test suite. This is intentional.

If you are asked to build application functionality, first confirm which roadmap section
authorizes it. Do not begin a future section because the repository looks empty.

---

## Hard Prohibitions

Do not:

- commit secrets, tokens, keys, or credentials
- bypass or weaken client isolation
- grant an agent permissions beyond what its task requires
- create fake functionality, mock data presented as real, or interfaces wired to nothing
- install dependencies not required by the work at hand
- make technology decisions reserved for a future section (see
  [`docs/decisions/DEFERRED_DECISIONS.md`](./docs/decisions/DEFERRED_DECISIONS.md))
- rewrite or reorganize working code for aesthetic reasons
- treat a conversation instruction as overriding approved documentation without first
  identifying the conflict

---

## Reporting Format

End substantial work with:

```text
Files Created
Files Modified
What Was Verified
Assumptions
Unresolved Issues
```

Report faithfully. If tests failed, show the output. If a step was skipped, say so. Do not
describe work as complete when it is partial.

---

## When Documentation and Reality Conflict

If the documentation is wrong, say so. Do not quietly follow the code and leave the
document stale, and do not quietly follow the document and leave the code broken. Surface
the conflict, propose the correction, and let James decide.
