# Deferred Decisions Register

**Status:** Active — established in Section 01.
**Purpose:** Track decisions intentionally postponed, so that a later session recognizes
them as *deliberately open* rather than *accidentally missing*.

Every entry below is **Deferred — to be resolved in a future section.** None of these is
a guess, a default, or an implied commitment. Where a future session resolves an entry,
it records an ADR (see [`README.md`](./README.md)) and removes the entry from this list.

---

## Technology and Platform

| # | Deferred decision | Target section |
| --- | --- | --- |
| D-01 | Application language, framework, and runtime | 02 / 29 |
| D-02 | Database technology and hosting | 03 |
| D-03 | Data model, schema, and storage layout | 03 |
| D-04 | Cloud provider and hosting platform | 29 |
| D-05 | Queue / job execution technology | 12 / 29 |
| D-06 | Vector database and retrieval technology | 07 / 09 |
| D-07 | Orchestration platform and execution model | 08 |
| D-08 | AI providers and specific models | 05 |
| D-09 | Authentication provider and identity model | 04 |
| D-10 | Secrets storage and credential vault technology | 04 |
| D-11 | Observability, logging, and audit stack | 27 / 28 |
| D-12 | Testing framework and AI evaluation tooling | 31 |
| D-13 | UI framework and design-token implementation | 15 / 16 |
| D-14 | Voice / speech technology | 14 |
| D-15 | Backup and disaster-recovery mechanism | 36 |

---

## Architecture and Mechanism

| # | Deferred decision | Target section |
| --- | --- | --- |
| D-20 | Model gateway design and routing policy | 05 |
| D-21 | Permission model mechanics and enforcement points | 04 |
| D-22 | Client-isolation enforcement mechanism | 04 / 22 |
| D-23 | Context Lock implementation and disambiguation behaviour | 08 / 16 |
| D-24 | Memory architecture, retention, and forgetting | 07 |
| D-25 | Agent runtime, registry, and lifecycle | 06 |
| D-26 | Approval mechanics and emergency stop for autonomous workflows | 26 |
| D-27 | Failure detection, retry, escalation, and notification | 35 / 25 |
| D-28 | Cost and resource-selection policy | 34 |
| D-29 | Data export, portability, and deletion mechanics | 37 / 44 |
| D-30 | Multi-business and multi-tenant structural approach | 20 / 22 |

---

## Open Questions Requiring James's Input

These are not technical postponements; they need information only James can supply. They
are listed so Section 02 begins by resolving them rather than assuming.

| # | Question |
| --- | --- |
| Q-01 | Which businesses besides KAIRO exist or are planned, and what are their names? |
| Q-02 | What does WEALTH cover in scope — accounts, assets, investments, budgeting, reporting? |
| Q-03 | Which devices and surfaces must NOVA run on first (desktop, mobile, web, voice)? |
| Q-04 | Is NOVA single-user only, or will other people (staff, collaborators) ever have access? |
| Q-05 | Which existing systems, tools, or data must NOVA integrate with earliest? |
| Q-06 | What are the hard constraints — budget, hosting preferences, data-residency, privacy? |
