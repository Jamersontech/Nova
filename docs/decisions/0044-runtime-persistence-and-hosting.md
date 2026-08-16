# 0044 — Runtime, Persistence and Hosting

**Status:** **Proposed**
**Proposed:** 2026-08-15 — Section 29 (narrowed)
**Section:** 29 — *the runtime/persistence/hosting subset only*
**Resolves:** `D-01`, `D-02`, `D-04`, and `D-33a` **in part**

## Decision

**NOVA is a server-rendered Python application over managed PostgreSQL with Row-Level Security,
on one provider in one region.**

Four parts, decided together because each is unanswerable without the others:

**1. `D-01` — Runtime: Python, server-rendered, with light presentational islands in the browser.**
No separate single-page application. The browser receives rendered HTML and presentational
components; it holds no routing, no application state and no authorization logic.

**2. `D-02` — Persistence: managed PostgreSQL, with Row-Level Security as the storage isolation
mechanism.** The application connects as a role that is **`NOBYPASSRLS`, not a superuser, and not
the owner of the tables it reads** — because a table owner bypasses RLS silently, which would
defeat the entire mechanism while every test still passed.

**3. `D-04` — Hosting: one application host, one managed PostgreSQL instance, one region, one
provider**, plus the provider's secret mechanism. No Kubernetes, no microservices, no queue, no
vector database, no observability platform, no CDN.

**4. `D-33a` — in part: the isolation mechanism family is RLS *plus* the Data-Access Boundary.**
Neither alone is sufficient — see below. `D-33a` is recorded resolved only when the adversarial
suite passes.

## Why the runtime is server-rendered, and why that is not a style preference

[`SYSTEM_LAYERS.md`](../architecture/SYSTEM_LAYERS.md) §2 defines the Surface layer as:

> *"Devices and channels NOVA is reachable through… Owns rendering and input capture. **Owns no
> logic.** Any behaviour implemented in a surface must be reimplemented for every other surface —
> which is why none is."*

**A single-page application is a surface that owns logic.** It holds routing, view state and
often authorization-shaped decisions about what to show. That is in direct tension with accepted
Section 02 architecture, and the tension is not cosmetic: `USER_INTERFACE_ARCHITECTURE.md` §7
requires identity, context, permissions, action meaning and the emergency stop to be **identical
across every surface**. Logic in the surface is logic that must be reimplemented per surface, which
is the failure `SYSTEM_LAYERS.md` says NOVA avoids by construction.

Server rendering also keeps the **PDP and the Data-Access Boundary in the same process**, which
matters because `I-77` requires the Data Access PEP to consult the PDP on **every** data access. A
network hop between them would add latency to every read and a new failure mode to a fail-closed
path (`I-93`).

**And Python specifically**, because the trusted machinery already exists in it: PDP, Context
service, credential broker, delegation, budgets, model gateway and tool PEP — validated by an
adversarial suite. Rewriting that to satisfy a language preference would be the worst trade
available to this project.

## Why RLS alone is not enough — the `C-2` problem

Evaluated against the **four approved disqualifying criteria**
([`ISOLATION_ENFORCEMENT.md`](../architecture/ISOLATION_ENFORCEMENT.md) §5; `S4-P4`, James
2026-08-13 — `C-1`, `C-2`, `C-5`, `C-6` disqualify, the rest are informational):

| | Criterion | RLS alone | With the Data-Access Boundary |
| --- | --- | --- | --- |
| `C-1` | Query lacking a scope predicate returns another scope's data? | **No** ✅ | No |
| `C-2` | Application code can alter its own scope binding mid-execution? | **Yes — fails** ❌ | **No** ✅ |
| `C-5` | Cross-scope violation testable with hostile queries? | Yes ✅ | Yes |
| `C-6` | Enforcement independent of the PDP? | Yes ✅ | Yes |

**`C-2` is the whole design problem.** RLS reads the scope binding from a session setting, and any
code holding the connection can set it again. So RLS satisfies three of the four criteria and fails
the one that matters most for a system where application code is the thing being defended against.

**The repository already contains the answer.** `ISOLATION_ENFORCEMENT.md` §4.1 registers the
Data-Access Boundary as the only component that may open a scope-bound channel, and states that
application code may not perform *"setting, widening, re-binding or reusing a binding; re-binding
mid-execution"* (`I-78`, `I-86`). This ADR selects the technology; it does not invent the
responsibility.

Concretely: the boundary verifies the Context Token (`I-87`), derives the binding **solely** from
that token's scope path (`I-78`), opens a transaction, sets a transaction-local binding, and returns
a handle **with no method that could re-bind it**. Application code never holds the connection.

`C-6` and `P-11` are satisfied by the same split: the PDP decides authorization in Python; RLS
enforces isolation in the engine. *"The engine must not also be the storage enforcement mechanism"*
(`P-11`) is honoured because they are different mechanisms in different processes.

## Informational criteria that are not satisfied, recorded rather than hidden

- **`C-8`** (partitioning under backup, restore, migration): a privileged dump crosses scopes. Real,
  unresolved, and inherited by `D-15`/`D-37`.
- **`C-9`** (per-scope encryption keys for client data **and** the separate audit hierarchy): one
  database with one encryption-at-rest key does not provide per-scope keys. **This is the largest
  known gap in this decision.** It does not disqualify — `C-9` was explicitly not ratified as
  disqualifying (`S4-P4`) — but if per-scope keys later become a requirement, that likely means
  multiple databases and is a materially different and more expensive architecture.
- **`C-7`** (operational cost per new scope): near zero with RLS, which is its main advantage over
  per-scope databases.

**Neither `C-8` nor `C-9` is resolved here, and `D-35`/`D-37` remain open.**

## Options Considered

1. **Per-scope databases.** Satisfies `C-1` and `C-2` by construction and would give per-scope keys
   (`C-9`). Rejected on `C-7`: operational cost per client scope, and cross-scope audit becomes N
   connections. Revisit only if `C-9` becomes a hard requirement.
2. **Per-scope SQLite files** — what the slice does today. Genuinely satisfies `C-1`, `C-5`, `C-6`,
   and it is *not* application-side filtering. Rejected for the substrate on concurrency, managed
   backup, and the absence of a real `C-2` boundary.
3. **PostgreSQL with RLS plus the Data-Access Boundary.** Chosen.
4. **A non-Python runtime with a separate API.** Rejected: would require rewriting the validated
   security machinery, and adds a surface that owns logic.

## Decision Made

Option 3, with Python server-rendering.

## Tradeoffs

**Advantages:** the security machinery is reused rather than rewritten; the browser never becomes an
authority; isolation is enforced by the storage engine independently of the PDP (`I-62`, `C-6`);
operational cost per scope is near zero; the dependency surface stays small; the design-token layer
(ADR 0041) is unaffected because it is framework-independent by construction.

**Disadvantages:** **RLS concentrates every scope's data in one database**, so a misconfigured role
is a total isolation failure rather than a partial one — the `NOBYPASSRLS` requirement is
load-bearing and must be verified, not assumed. **`C-9` is not satisfied**, as recorded above.
**Server rendering constrains interaction richness**, which is acceptable for an approval- and
review-centric surface and would not be for a highly interactive canvas. And **`D-13` is narrowed
but not resolved** — this ADR does not select a client framework, and deliberately leaves open
whether one is needed at all.

## Consequences

- A minimum schema is created — `actor`, `scope`, `grant`, `approval`, `audit_record`, `item`. **No
  domain tables**; Sections 19–28 own those.
- `actor` is an explicit reference on records rather than an assumption, so additional actors later
  need no migration. **This does not make NOVA multi-user**, and `I-09` is untouched: additional
  actors are not approvers.
- **`D-13` remains deferred.** **`D-12`, `D-14`, `D-35`, `D-37` remain deferred.** ADRs 0038–0040
  remain Proposed and nothing here depends on them.
- **No invariant is created or amended.** `I-01`–`I-114` byte-identical.
- **`I-03` remains DEMONSTRATED until the adversarial suite passes** against a real PostgreSQL
  instance. This ADR selects a mechanism; it does not confer the property.

## What Would Change This

For `D-02`: a hard requirement for per-scope encryption keys (`C-9`), which would argue for
per-scope databases despite `C-7`. For `D-01`: a surface requirement that genuinely needs rich
client-side interaction, which would argue for islands growing into a client application — a change
to make deliberately, not by accretion.
