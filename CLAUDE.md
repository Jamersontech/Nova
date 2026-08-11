# CLAUDE.md — Claude Code Adapter

This file is the Claude Code-specific adapter for NOVA. It is deliberately short.

**The canonical rules live in [`AGENTS.md`](./AGENTS.md) and [`/docs`](./docs/README.md).**
This file does not restate them, and it does not override them.

---

## Before You Work

1. **Read [`AGENTS.md`](./AGENTS.md).** It is the provider-neutral governance layer and
   applies to you in full.
2. **Read the relevant documents in [`/docs`](./docs/README.md)** — the documentation map
   in `AGENTS.md` tells you which ones apply to your task.
3. **Confirm which roadmap section owns the work** you have been asked to do
   ([`docs/ROADMAP.md`](./docs/ROADMAP.md)). Do not begin a future section.

---

## While You Work

4. **Follow the approved NOVA architecture.** Where architecture is not yet defined, it is
   deferred, not open — check
   [`docs/decisions/DEFERRED_DECISIONS.md`](./docs/decisions/DEFERRED_DECISIONS.md) before
   deciding anything.
5. **Inspect before modifying.** Read the existing implementation; do not change code you
   have not read.
6. **Keep changes scoped** to what was asked. A small request produces a small change.
7. **Run the appropriate tests** and other verification the repository supports.

---

## When You Report

8. **Explain important assumptions** explicitly, along with files changed, what was
   verified, and what remains unresolved.
9. **Never treat conversation history as the only source of truth.** The repository is the
   persistent record; a conversation is temporary context.
10. **Never override documented architecture without explicitly identifying the
    conflict.** Name the conflict, propose a resolution, and let James decide.

---

## Notes Specific to This Environment

- NOVA currently contains documentation only — no application, dependencies, build, or
  test suite. There is nothing to run yet, and no test command to invoke.
- Do not add tooling, configuration, or dependencies to make the repository "feel" like a
  project. Section 02 defines the architecture; Section 29 and Section 30 define the
  infrastructure and development environment.
- Do not create provider-specific instruction files beyond adapters like this one. The
  repository stays provider-neutral.
