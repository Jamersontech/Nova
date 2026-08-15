# NOVA Documentation

This documentation is the persistent source of truth for NOVA. Conversation history is
not. Every document here has a distinct purpose; nothing is duplicated between them.

---

## Read in This Order

| # | Document | Purpose |
| --- | --- | --- |
| 1 | [`CONSTITUTION.md`](./CONSTITUTION.md) | Golden Rules, what NOVA is, authority hierarchy, isolation principle, context lock, human control, source of truth. |
| 2 | [`DOMAIN_MODEL.md`](./DOMAIN_MODEL.md) | Business → Client → Project → Environment, KAIRO, client isolation, credentials. |
| 3 | [`ai/AI_TERMINOLOGY.md`](./ai/AI_TERMINOLOGY.md) | Canonical definitions of NOVA's AI vocabulary. |
| 4 | [`ai/AGENT_PRINCIPLES.md`](./ai/AGENT_PRINCIPLES.md) | When agents may exist, what they must declare, what they may never do. |
| 5 | [`development/DEVELOPMENT_RULES.md`](./development/DEVELOPMENT_RULES.md) | Priority order, scope discipline, secrets, dependencies. |
| 6 | [`development/CHANGE_MANAGEMENT.md`](./development/CHANGE_MANAGEMENT.md) | How changes are proposed, approved, made, and documented. |
| 7 | [`design/DESIGN_PRINCIPLES.md`](./design/DESIGN_PRINCIPLES.md) | Interface principles. The design system itself is Section 15. |
| 8 | [`decisions/README.md`](./decisions/README.md) | How architectural decisions are recorded. |
| 9 | [`decisions/DEFERRED_DECISIONS.md`](./decisions/DEFERRED_DECISIONS.md) | What is deliberately unresolved, and where it will be resolved. |
| 10 | [`ROADMAP.md`](./ROADMAP.md) | The 46 architectural domains and current progress. |

Then the architecture (Section 02):

| # | Document | Purpose |
| --- | --- | --- |
| 11 | [`architecture/README.md`](./architecture/README.md) | Index and reading order for the blueprint. |
| 12 | [`architecture/MASTER_ARCHITECTURE.md`](./architecture/MASTER_ARCHITECTURE.md) | **The canonical blueprint.** Start here for how NOVA works. |
| 13 | [`architecture/INVARIANTS.md`](./architecture/INVARIANTS.md) | The fifty testable properties every implementation must satisfy. |

Coding-agent governance lives at the repository root: [`../AGENTS.md`](../AGENTS.md)
(provider-neutral) and [`../CLAUDE.md`](../CLAUDE.md) (Claude Code adapter).

---

## Documentation Standards

Documentation must be precise, internally consistent, concise where possible, readable by
humans, parseable by AI coding agents, free of contradictory terminology, and free of
unnecessary duplication.

- Every document has one clear purpose. Documents are not created to increase the file
  count.
- A concept is defined in exactly one place and linked to from elsewhere.
- Terminology follows [`ai/AI_TERMINOLOGY.md`](./ai/AI_TERMINOLOGY.md) exactly.
- KAIRO is always spelled K-A-I-R-O.
- Documentation that a change makes stale is updated as part of that change.
- What is not yet decided is marked **Deferred — to be resolved in a future section**, not
  guessed.

---

## Current Status

Sections 01 (Constitution & Project Foundation), 02 (System Architecture & Master
Blueprint), 03 (Data, Scope, Identity & Memory Architecture) and 04 (Security, Identity &
Permissions) are complete. NOVA contains documentation only — no application code,
dependencies, infrastructure, or technology commitments.

The Section 02 architecture is **Active** — ADRs `0001`–`0008` were accepted by James on
2026-08-12, with clarifications recorded on 0002 (shared resources) and 0005 (NOVA-generated
Work Orders).

The Section 03 model is **Active** — ADRs `0009`–`0015` were accepted by James on 2026-08-12
as amended, with the documented residual risks explicitly accepted rather than resolved.

The Section 04 model is **Active** — ADRs `0016`–`0023` were accepted by James on 2026-08-13.
*(Status corrected 2026-08-14: this line still read "Proposed, pending James's approval of ADRs
`0016`–`0021`" — accurate before the acceptance and false after it, and it also predated ADRs
`0022`–`0023`.)*

The Section 05 model is **Active** — ADRs `0024`–`0028` were accepted by James on 2026-08-14.

The Section 06 model is **Active** — ADRs `0029`–`0031` were accepted by James on 2026-08-14.

The Section 07 model is **Proposed** — ADRs `0032`–`0033` await James's approval.

The Section 08 model is **Proposed** — ADRs `0034`–`0035` await James's approval.

The Section 09 model is **Proposed** — its single decision (`S9-D1`, source identity) is folded into ADR `0033`.

The Section 10 model is **Proposed** — ADR `0036` awaits James's approval. **No new invariant and no
new architecture document**: the decision defines what makes a tool declaration complete, inside
[`architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md`](./architecture/TOOL_AND_INTEGRATION_ARCHITECTURE.md) §2.1.

The Section 11 model is **Proposed** — ADR `0037` awaits James's approval. `S11-D1`
(binding-dependent consequence) was stopped for James and approved on 2026-08-15; its resolution is
folded into ADR `0037`, adding `I-114` and amending `I-109` in place.

Next: **Section 12 — Automation & Workflow Engine**.
