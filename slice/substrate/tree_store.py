"""The scope tree, as data rather than a fixture.

Until now NOVA's scope tree was built in Python by whichever test needed it.
The `scope` and `grant` tables existed and nothing read them. That is the gap
this closes: the tree James actually has is stored, and the application loads
it at startup.

THE BOOTSTRAP PROBLEM, AND WHY THIS IS NOT A BYPASS
---------------------------------------------------
`scope` and `grant` define WHERE the boundaries are. A scope-bound channel
cannot be opened until the tree that decides the binding has been read, so the
first read cannot itself be scope-bound. That is a genuine ordering problem,
not an excuse.

It is solved with PostgreSQL's own mechanism rather than around it: a policy
attached TO `nova_control` permits SELECT on those two tables, and to that role
only. `nova_app` is unaffected and still sees only `scope_isolation`. The
control role is read-only, holds no privilege on `item`, `approval` or
`audit_record`, and is used HERE ONLY -- at startup, never in a request.

`I-78` is untouched: no scope-bound channel is opened in this module.

WHAT IS STILL A LIMITATION
--------------------------
The tree is loaded ONCE, at startup. A grant added or revoked in the database
does not take effect until the application reloads. `I-65` (revocation takes
effect at the next decision) is satisfied for SESSIONS, which are resolved per
request; it is NOT satisfied for grants. Cheap to fix -- reload on write, or
per-request load -- and deliberately not fixed speculatively, because the only
writer today is James at setup time.
"""

from __future__ import annotations

from typing import Iterable, Optional

from ..core.scope_tree import ScopeTree
from ..core.types import Risk
from . import db

# I-10: only James creates grants. Nothing in agent/, tools/ or integrations/
# imports this module, and there is no route that writes to it.
#
# THE RIGHT NAME IS HOW A CEILING IS CONFERRED. The `grant` table stores
# (actor_ref, scope_path, right_name) and no ceiling column, so a grant's
# `max_risk` is derived here and nowhere else. That is why `revoke` is a
# separate right rather than a wider `write`: raising `write` would raise ONE
# shared entry and with it every write grant on every scope (ADR 0052
# element 8).
#
# `revoke` is the only IRREVERSIBLE right NOVA has. `I-67` keys on that class,
# and after `36b4dee` `issue_root` refuses a token whose ceiling exceeds what
# these grants confer -- so an `EXECUTE` write grant cannot reach an
# irreversible act, which is precisely what element 8 requires.
READ_RIGHTS = {"read": Risk.READ, "write": Risk.EXECUTE,
               "revoke": Risk.IRREVERSIBLE}


def load_tree(dsn: Optional[str] = None) -> ScopeTree:
    """Read the persisted scope tree and its grants into a ScopeTree.

    Startup only. The returned tree is what the Context service and the PDP
    consult; this function makes no authorization decision of its own.
    """
    import psycopg2

    tree = ScopeTree()
    conn = psycopg2.connect(dsn or db.control_dsn())
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT scope_path, kind FROM scope ORDER BY scope_path")
            for path, kind in cur.fetchall():
                tree.add_scope(path, kind)
            cur.execute("SELECT actor_ref, scope_path, right_name FROM \"grant\""
                        " ORDER BY id")
            for actor, path, right in cur.fetchall():
                tree.james_grants(actor, right, "*", path,
                                  READ_RIGHTS.get(right, Risk.READ))
    finally:
        conn.close()
    return tree


def seed(scopes: Iterable[tuple[str, str, Optional[str]]],
         grants: Iterable[tuple[str, str, str]],
         dsn: Optional[str] = None) -> None:
    """Write the tree. **James acting**, not the application.

    Deliberately takes the OWNER connection and has no HTTP route: `I-10` says
    only James creates grants, and the cheapest way to honour that is for the
    application to have no code path that can.
    """
    import psycopg2

    conn = psycopg2.connect(dsn or db.superuser_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for path, kind, parent in scopes:
                cur.execute(
                    "INSERT INTO scope (scope_path, kind, parent_path)"
                    " VALUES (%s,%s,%s) ON CONFLICT (scope_path) DO UPDATE"
                    " SET kind=EXCLUDED.kind, parent_path=EXCLUDED.parent_path",
                    (path, kind, parent))
            for actor, path, right in grants:
                cur.execute(
                    "INSERT INTO \"grant\" (actor_ref, scope_path, right_name)"
                    " VALUES (%s,%s,%s)", (actor, path, right))
    finally:
        conn.close()
