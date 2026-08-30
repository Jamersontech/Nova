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
nova_auth    authentication only. Privileges on auth_credential and
             auth_session and NOTHING else.
```

**Why a third role.** Authentication runs *before* a Context Token exists, so it cannot go through
the Data-Access Boundary — there is no scope to bind to yet. Rather than let it hold a connection
that could reach scoped data, it gets an identity that cannot: `nova_auth` is refused on `item`,
`approval`, `audit_record`, `scope` and `grant`, and `nova_app` is revoked from both auth tables.
Both directions are asserted by test. `I-78` is untouched — no scope-bound channel is opened here.

A table owner bypasses RLS unless `FORCE ROW LEVEL SECURITY` is set, and a superuser bypasses it
unconditionally. **Both are silent** — every application test would still pass while isolation was
absent. Both are asserted by test, not assumed.

## First run (local Alpha)

**One user, one trusted machine, localhost only.** NOVA binds `127.0.0.1` and nothing else, and
that bind is a security control, not a default — see *Why localhost is the perimeter* below.

Every command here was run against a clean PostgreSQL 16.13 cluster before being written down.

### 1. PostgreSQL

**PostgreSQL 16.** `schema.sql` creates the four roles (`nova_owner`, `nova_app`, `nova_auth`,
`nova_control`) itself, so there is no role setup to do. There is no password: the DSNs in
`db.py` carry none, so the cluster must accept local connections (`trust` or `peer` in
`pg_hba.conf`). On a single-user machine that is the same trust boundary as your OS account.

If you do not already have a cluster, create one. NOVA's defaults expect **port 5433** and a
socket in **`/tmp`** — unusual on purpose, so it never collides with a system PostgreSQL:

```bash
initdb -D ~/.nova/pg
pg_ctl -D ~/.nova/pg -o '-p 5433 -k /tmp' -l ~/.nova/pg/pg.log start
```

If your `initdb`/`pg_ctl` are not on `PATH`, they live under the packaged bin directory —
on Debian/Ubuntu, `/usr/lib/postgresql/16/bin/`.

### 2. The database — **not `nova_substrate`**

**NOVA does not create it.** This is the one step nothing in the code does for you:

```bash
createdb -h /tmp -p 5433 nova_alpha
export NOVA_PGDATABASE=nova_alpha        # keep this exported for every command below
```

> **The Alpha database must never be `nova_substrate`.** That is the database the test suite
> uses, and `db.reset_data()` **TRUNCATEs** it — `item`, `task`, `approval`, `scope`, `grant`,
> `auth_credential` and the rest — at the start of nearly every database-backed test. Measured on
> a real installation: running the suite took it from 3 scopes, 9 grants and James's one passkey
> to 0, 0, and two leftover test credentials. The passkey was gone, so he could not sign in; two
> credentials existed, so trust-on-first-use was closed and he could not register a new one
> either. The installation was unrecoverable, silently.
>
> `NOVA_PGDATABASE` is the whole fix. Nothing else needs to change, and the test suite keeps its
> own default.

The schema, the roles, the RLS policies, the three areas and James's grants are all applied
automatically on first start.

### 3. The conversation credential

```bash
export ANTHROPIC_API_KEY=...        # resolved only inside the provider transport, at send time
```

**Without it NOVA starts and refuses to converse, and refusing to converse means nothing can be
recorded** — the only path that creates a note, a task or a scope is a proposal the model emits,
which you then approve. NOVA says so at startup, and says so again on the conversation page if
you try anyway.

### 4. Start it

```bash
export NOVA_PGDATABASE=nova_alpha        # if this shell has not already
python3 -m slice.substrate.app
```

```
NOVA listening on http://localhost:8080  (sign in at http://localhost:8080/auth/login)
  conversation provider: anthropic
```

Everything is configured by environment variable; there is no config file.

| Variable | Default | |
| --- | --- | --- |
| `NOVA_PORT` | `8080` | listen port |
| `NOVA_DATA_DIR` | `~/.nova` | audit records and the secrets vault |
| `NOVA_RP_ID` | `localhost` | WebAuthn relying party |
| `NOVA_ORIGIN` | `http://localhost:$NOVA_PORT` | browser origin |
| `NOVA_PGHOST` / `NOVA_PGPORT` | `/tmp` / `5433` | cluster |
| `NOVA_PGDATABASE` | `nova_substrate` | **set it to `nova_alpha`** — the default is the test database (see step 2) |
| `ANTHROPIC_API_KEY` | — | conversation provider (ADR 0047) |

If the database cannot be reached, startup names the missing prerequisite and exits — a stopped
server and an absent database are different messages, because they need different fixes.

### 5. Register a passkey, then sign in

Open **http://localhost:8080/auth/login** and press **Register a passkey**, then **Sign in**.

**The first passkey is trust-on-first-use.** There is no session to authorize it against, because
none can exist yet — so whoever reaches the enrolment route first becomes James. Every later
passkey requires an existing strong session. Do not expose the port beyond localhost until you
have enrolled (ADR 0046, limitation 1).

### 6. The first useful thing

Open **BUSINESS**, then press **Open conversation** on the *Ask NOVA* card, and say something you
want remembered:

> *remember that the supplier changed their bank details*

NOVA answers and **proposes** a note. Nothing has happened yet. The scope page now offers
*N actions need your decision* — press **Review**, read the card
— it shows the exact text that will be stored — and approve. The note now appears on the scope
page and survives restart. Tasks (`what needs doing`) and new client/area scopes work the same
way: NOVA proposes, you decide.

To distrust something later, press **Revoke author** on the note. That is an `IRREVERSIBLE` act,
so approving it asks for your passkey again, and it cannot be undone.

### A database seeded before F-3

**Start Alpha on a fresh database.** The scope tree and James's grants are seeded **once**, when
the tree is empty — `wire()` does not converge an existing tree onto the current defaults, because
that would make startup a grant-*creating* path rather than a first-run one, and `I-10` keeps
grant creation to `tree_store.seed` called by James.

So a database seeded before the `revoke` right existed has `read` and `write` and nothing else.
NOVA starts cleanly, and every revocation is then refused at issuance (`I-14`), which the interface
renders as a plain *"this scope is not available to you"* — a **Revoke author** button that never
works and does not say why. Measured, not theorised.

If you have such a database and do not want to start over, add the missing grants once, as
James, on the owner connection — the same call the first run makes. It reads `NOVA_PGDATABASE`
like everything else, so export it first or it will act on the test database:

```bash
export NOVA_PGDATABASE=nova_alpha
python3 -c "
from slice.substrate import tree_store
tree = tree_store.load_tree()
missing = [('james', p, 'revoke') for p in ('/life', '/business', '/wealth')
           if tree.find_grant('james', 'revoke', '*', p) is None]
tree_store.seed([], missing)
print('added:', missing)"
```

Then restart NOVA — the tree is read once, at startup, so a grant added while it is running does
not take effect until it restarts.

### Why localhost is the perimeter

`serve()` binds `127.0.0.1` with no option to widen it, and there is no TLS. WebAuthn needs a
secure context, and `localhost` is the only origin that qualifies without a certificate. That
bind is also what closes the trust-on-first-use enrolment window. Hosting is
[ADR 0044](../../docs/decisions/0044-runtime-persistence-and-hosting.md)'s question and nothing
here implements it — do not put this behind a proxy or on a shared machine.

## Running the tests

```bash
# a real PostgreSQL instance must be reachable (see db.py for connection settings)
unset NOVA_PGDATABASE                    # the suite owns `nova_substrate`
python3 -m unittest slice.substrate.tests.test_isolation
```

**The suite TRUNCATEs the database it runs against**, so run it against `nova_substrate` and
never against your Alpha database. `unset NOVA_PGDATABASE` in any shell where you exported
`nova_alpha`, or run the tests from a different shell.

The suite **skips** when PostgreSQL is unavailable. It never passes without its subject: a green
security suite that never ran is worse than a red one — so check `db.available()` before reading
a green result as a pass.

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
| **Conversation** (`conversation.py` → seam → `ModelGateway`) | **REAL** — the interface, wired to the existing machinery ([ADR 0047](../../docs/decisions/0047-conversation-provider-is-anthropic.md), *Proposed*, resolves `D-08` for this slice). The model is downstream of the PDP and RLS, holds no authority, and the only consequence-shaped thing read from its output is a pending approval in the existing `ApprovalService`. Runnable: `python3 -m slice.substrate.app` |
| **Authentication** (`auth.py` → seam) | **REAL** — WebAuthn passkeys ([ADR 0046](../../docs/decisions/0046-authentication-is-webauthn-passkeys.md), *Proposed*). The last stand-in in the security path is gone; every substrate suite now signs in through a real ceremony |
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
