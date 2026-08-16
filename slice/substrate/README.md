# Substrate — Data-Access Boundary and physical scope isolation

**The first work in this repository that tests a security control rather than a presentation
property.** It makes `I-03` enforceable by the storage engine instead of by application care.

Authority: [ADR 0044](../../docs/decisions/0044-runtime-persistence-and-hosting.md) (**Proposed**)
for the runtime/persistence/hosting decision; [ADR 0017](../../docs/decisions/0017-isolation-independent-of-pdp.md)
(**Accepted**) for the Data-Access Boundary responsibility, which this module implements rather
than invents.

---

## The problem this solves

The previous store exposed:

```python
StoreRegistry.for_scope("business/kairo/client-b")     # any code, any scope
```

`runtime.py` passed `token.scope_path` and was correct **by convention**. But `I-78` requires the
binding to be established *"only by the Data-Access Boundary… derived solely from the Context
Token's scope path, and verified against the presented token at establishment."* A method taking a
caller-supplied string is not that, and renaming it would not have made it that.

Here the scope is **never a parameter**. It is read from a verified token, and the returned handle
has no method that could change it.

## What enforces what — the split matters

| Criterion | Required | Enforced by |
| --- | --- | --- |
| **C-1** query without a scope predicate reaches another scope | No | **PostgreSQL RLS**, in the engine |
| **C-2** application code alters its own binding mid-execution | No | **The boundary's interface.** RLS cannot do this — the binding is a session setting and any code holding the connection can set it again |
| **C-5** violation testable with hostile queries | Yes | Raw `nova_app` connections in the suite |
| **C-6** enforcement independent of the PDP | Yes | This module never calls the PDP (`I-62`) |

**RLS alone satisfies three of four.** `C-2` is why the boundary exists.

## Roles

```
nova_owner   owns the tables. Migrations only. Never used by request handling.
nova_app     NOBYPASSRLS, NOSUPERUSER, not a table owner. Subject to RLS.
```

A table owner bypasses RLS unless `FORCE ROW LEVEL SECURITY` is set, and a superuser bypasses it
unconditionally. **Both are silent** — every application test would still pass while isolation was
absent. Both are asserted by test, not assumed.

## Running it

```bash
# a real PostgreSQL instance must be reachable (see db.py for connection settings)
python3 -m unittest slice.substrate.tests.test_isolation
```

The suite **skips** when PostgreSQL is unavailable. It never passes without its subject: a green
security suite that never ran is worse than a red one.

## The negative control

`test_0` disables RLS mid-run, asserts the leak **appears**, re-enables it, and asserts the leak
closes.

This exists because the first version of this suite **passed with RLS disabled** — the fixture
re-applied the schema in `setUpClass` and silently re-enabled it. Every other check asserts that
scope B is unreachable; none of them can tell whether that is because RLS enforces it or because
the data simply is not there. Without `test_0`, a misconfigured database produces a fully green
security suite, which is how isolation failures survive review.

---

## `I-03` status — stated precisely

| Layer | Status |
| --- | --- |
| **The substrate** (`slice/substrate/`) | **ENFORCED** — below the query layer, evidenced against real PostgreSQL 16.13 |
| **The application path** (`seam.py` → PEP → boundary → RLS) | **ENFORCED** — the seam drives the same property over real HTTP: no application-side predicate exists (verified by source inspection), an application-level negative control shows RLS is what holds it, and sequential requests on a shared pool carry nothing across scopes |
| **The pre-substrate slice** (`slice/core` `StoreRegistry`, `runtime.py`) | **DEMONSTRATED** — the earlier SQLite mechanism remains as slice fixtures; it is not the application path |

The Data Access PEP exists: `PolicyDecisionPoint.authorize_data_read`
([ADR 0045](../../docs/decisions/0045-data-access-pep-decision-sequence.md), **Proposed**) — the
ten-step sequence with the tool-specific steps inapplicable by `I-114`'s own wording. One decision
authority, not two.

**Still not claimed:** timing (`I-03 [PHYS]` names it; untested, stated), `C-8` backup
partitioning, `C-9` per-scope keys, and authentication — `SessionStore` is an explicit stand-in
confined to one class until `D-09` is resolved.

### What the nine adversarial checks established

1. Isolation holds with **no application-side filter** — `SELECT` with no predicate
2. A **direct hostile query** for the sibling scope returns zero rows
3. **No predicate** returns only the bound scope and its descendants; enumeration and counts too
4. The channel **exposes no way to rebind**; a rebind behind its back **fails closed** (`I-78`)
5. A binding **does not survive** into the next transaction on a pooled connection
6. **No token → no channel** (`I-79`); an unbound connection reads nothing — no default scope
7. A **forged token** (`I-87`), an **expired** token, and an **empty scope** all open no channel
8. The application role **cannot bypass RLS**, does not own the tables, cannot disable RLS
9. Cross-scope **write is refused**, `UPDATE`/`DELETE` reach nothing, and an out-of-scope row is
   **indistinguishable from a non-existent one**

### What was NOT established, and is therefore not claimed

- **Timing.** `I-03 [PHYS]` names timing explicitly. This suite does **not** test it, and
  `test_9d` skips with that stated. A meaningful timing result needs many samples, a quiet
  machine and a statistical claim; asserting it from a handful of calls in a shared container
  would be theatre. **The timing clause of `I-03` remains unestablished.**
- **`C-8`** — partitioning under backup, restore and migration. A privileged dump crosses scopes.
- **`C-9`** — per-scope encryption keys. One database, one key. `D-35`/`D-37` remain open.
- **Python cannot make the connection truly unreachable.** `ScopedChannel` gives application code
  no API to reach it, but introspection could still find a name-mangled attribute. The
  architecture places this module in the TRUSTED zone, where the threat is mistake rather than a
  hostile in-process adversary. **A structural guarantee against error, not a sandbox.**

---

## The seam

```
HTTP GET /scope/<path>/items
  → opaque session cookie → server-side actor identity   (D-09 stand-in)
  → Context service issues the Context Token             (I-106)
  → PolicyDecisionPoint.authorize_data_read              (I-77; ADR 0045)
  → Data-Access Boundary opens the scope-bound channel   (I-78, I-79, I-87)
  → SELECT with no scope predicate — RLS bounds it
  → audit row, deterministic identity, same transaction  (I-93, W-1)
  → server-rendered HTML
```

The browser holds one opaque session id and nothing else — no token, no decision, no credential.
An ungranted scope and a nonexistent scope return byte-identical pages, so a requester without
access does not learn which it was.

```bash
python3 -m unittest slice.substrate.tests.test_seam        # 14 application-path checks
```

## Validation state

| Level | | |
| --- | --- | --- |
| **DOCUMENTED** | ✅ | ADR 0044; the role split; the C-1/C-2 division |
| **IMPLEMENTED** | ✅ | Schema, RLS policies, Data-Access Boundary, scoped channel |
| **EXECUTED** | ✅ | 20 checks against a live PostgreSQL 16.13 cluster |
| **SECURITY-TESTED** | ✅ **Yes — for `I-03` in the substrate** | Adversarial, bypassing the application read path, with a load-bearing negative control. **First legitimate use of this label in the repository.** Scoped to the checks listed above; timing excluded |
| **VALIDATED AGAINST A REAL EXTERNAL SYSTEM** | ⚠️ **Partially** | A real PostgreSQL server was used — a genuine external process, not a mock. It was **local**, not a managed cloud instance, so the hosting half of ADR 0044 is unvalidated |
