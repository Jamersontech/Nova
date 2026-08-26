"""F-7: the legacy-provenance migration guard must not fire on another schema.

`schema.sql` replaces a legacy `item.provenance text` column with the `text[]`
one `I-111` needs. The replacement is a DROP, so it is guarded -- and the guard
is the only thing standing between a restart and the silent destruction of every
row's persisted provenance.

THE DEFECT. `information_schema.columns` spans the WHOLE database. The
`ALTER TABLE item` it guards resolves through `search_path`. Unqualified, those
are two different tables: a legacy `item.provenance text` in ANY other schema
satisfied the test, and the DROP then landed on THIS schema's `item` --
destroying a populated `text[]` column, with no error and no notice, on every
startup. `apply_schema()` runs as the SUPERUSER, for which `information_schema`
hides nothing, so there is no privilege boundary limiting what it can see.

WHAT THIS SUITE PROVES, in both directions:

    1. a legacy `item.provenance text` IN THIS SCHEMA is still detected and
       still dropped -- the migration's intended behaviour is unchanged
    2. an `item.provenance text` in ANOTHER schema is NOT treated as the target
       -- this schema's populated `text[]` column survives

and, because a control that is not load-bearing proves nothing, `test_04`
INVERTS the fix: with the `current_schema()` line removed, the same fixture
destroys the column. The guard is what makes the difference.

The guard SQL is EXTRACTED FROM `schema.sql` ITSELF rather than copied here, so
this suite cannot drift away from the artifact it is asserting about.

Every test runs against real PostgreSQL, in its own throwaway database -- never
against `nova_substrate`, and never against a mock, which would prove only that
the mock behaved.

Skips without PostgreSQL -- never passes without its subject.

Run:  python3 -m unittest slice.substrate.tests.test_migration_guard_schema
"""

from __future__ import annotations

import re
import unittest

from .. import db

PROBE_DB = "nova_f7_guard_probe"

# The `text[]` value the migration must never destroy. Populated on purpose: a
# dropped EMPTY column would be a schema bug; a dropped POPULATED one is the
# loss of persisted security state (`I-38`, `I-111`).
PERSISTED = ["james.stated"]


def _guard_sql() -> str:
    """The real guard, lifted out of the shipped `schema.sql`.

    Located by its contents rather than by line number, and asserted UNIQUE --
    if a second `information_schema` guard is ever added, this suite must be
    made to say which one it means rather than silently testing the wrong one.
    """
    text = db.SCHEMA.read_text()
    blocks = [b for b in re.findall(r"DO \$\$.*?\$\$;", text, re.S)
              if "information_schema.columns" in b]
    assert len(blocks) == 1, f"expected one information_schema guard, found {len(blocks)}"
    return blocks[0]


@unittest.skipUnless(db.available(), "PostgreSQL is not available")
class MigrationGuardIsSchemaQualified(unittest.TestCase):

    # -- throwaway database -------------------------------------------------

    def _connect(self, dbname: str):
        import psycopg2
        conn = psycopg2.connect(
            db.superuser_dsn().replace(f"dbname={db.DBNAME}", f"dbname={dbname}"))
        conn.autocommit = True
        return conn

    def setUp(self):
        admin = self._connect(db.DBNAME)
        with admin.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {PROBE_DB}")
            cur.execute(f"CREATE DATABASE {PROBE_DB}")
        admin.close()
        self.conn = self._connect(PROBE_DB)

    def tearDown(self):
        self.conn.close()
        admin = self._connect(db.DBNAME)
        with admin.cursor() as cur:
            cur.execute(f"DROP DATABASE IF EXISTS {PROBE_DB}")
        admin.close()

    # -- fixtures -----------------------------------------------------------

    def _sql(self, statement: str, args=None):
        with self.conn.cursor() as cur:
            cur.execute(statement, args)

    def _legacy_column(self):
        """The state the migration EXISTS to correct: `provenance text`."""
        self._sql("CREATE TABLE public.item (item_ref text, provenance text)")
        self._sql("INSERT INTO public.item VALUES ('r1', 'legacy')")

    def _current_column(self):
        """The state the migration must LEAVE ALONE: a populated `text[]`."""
        self._sql("CREATE TABLE public.item (item_ref text, provenance text[])")
        self._sql("INSERT INTO public.item VALUES ('r1', %s)", (PERSISTED,))

    def _foreign_legacy_column(self):
        """Another schema, holding exactly what the unqualified guard matched."""
        self._sql("CREATE SCHEMA other")
        self._sql("CREATE TABLE other.item (item_ref text, provenance text)")

    def _run_guard(self, sql=None):
        self._sql(sql if sql is not None else _guard_sql())

    def _columns(self, table: str = "public.item") -> list[str]:
        schema, name = table.split(".")
        with self.conn.cursor() as cur:
            cur.execute("SELECT column_name FROM information_schema.columns"
                        " WHERE table_schema = %s AND table_name = %s", (schema, name))
            return sorted(r[0] for r in cur.fetchall())

    def _provenance_value(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT provenance FROM public.item WHERE item_ref = 'r1'")
            return cur.fetchone()[0]

    # -- direction 1: the intended behaviour is unchanged --------------------

    def test_01_a_legacy_column_in_this_schema_is_still_dropped(self):
        """The migration still migrates. Qualifying the guard must not turn it
        off -- a fix that silently disabled the DROP would leave a `text`
        column where `I-111` needs `text[]`."""
        self._legacy_column()
        self._run_guard()
        self.assertNotIn("provenance", self._columns())

    def test_02_the_guard_is_still_idempotent_on_an_already_migrated_column(self):
        """Re-applying `schema.sql` is the ordinary case: every startup does it.
        A populated `text[]` column is not legacy and must survive untouched."""
        self._current_column()
        self._run_guard()
        self._run_guard()
        self.assertIn("provenance", self._columns())
        self.assertEqual(self._provenance_value(), PERSISTED)

    # -- direction 2: another schema is not the target -----------------------

    def test_03_a_legacy_column_in_another_schema_is_not_treated_as_the_target(self):
        """F-7 itself. `other.item.provenance text` exists; THIS schema's
        column is the current `text[]` one and is populated. The guard must not
        read the foreign column as evidence about this one."""
        self._current_column()
        self._foreign_legacy_column()
        self._run_guard()
        self.assertIn("provenance", self._columns())
        self.assertEqual(self._provenance_value(), PERSISTED,
                         "persisted provenance was destroyed by a column in"
                         " another schema")

    def test_04_INVERSION_without_the_qualification_the_column_is_destroyed(self):
        """The control is load-bearing, proven by removing it.

        Same fixture as `test_03`, guard with the `current_schema()` line
        stripped -- i.e. the code exactly as it shipped before this fix. If this
        test ever stops destroying the column, the qualification has stopped
        being what protects it and this suite is no longer testing anything.
        """
        unqualified = re.sub(r"\s*WHERE table_schema = current_schema\(\)\s*\n\s*AND ",
                             "\n               WHERE ", _guard_sql())
        self.assertNotIn("current_schema()", unqualified)
        self.assertIn("information_schema.columns", unqualified)

        self._current_column()
        self._foreign_legacy_column()
        self._run_guard(unqualified)
        self.assertNotIn("provenance", self._columns(),
                         "the unqualified guard did not reproduce F-7 -- the"
                         " inversion proves nothing")

    def test_05_the_foreign_table_is_never_the_one_altered(self):
        """The DROP resolves through `search_path`, so the guard's own subject
        was never the foreign table. Stated explicitly: after a correct run,
        BOTH tables are exactly as they were."""
        self._current_column()
        self._foreign_legacy_column()
        self._run_guard()
        self.assertEqual(self._columns("public.item"), ["item_ref", "provenance"])
        self.assertEqual(self._columns("other.item"), ["item_ref", "provenance"])

    # -- the shipped artifact ------------------------------------------------

    def test_06_the_shipped_schema_carries_the_qualification(self):
        """Structural, against `schema.sql` on disk: the qualification is in the
        file the application actually applies, in the same predicate as the
        table-name test, not somewhere adjacent."""
        guard = _guard_sql()
        self.assertIn("table_schema = current_schema()", guard)
        self.assertIn("table_name = 'item'", guard)
        self.assertIn("column_name = 'provenance'", guard)
        self.assertIn("data_type = 'text'", guard)
        self.assertLess(guard.index("table_schema = current_schema()"),
                        guard.index("ALTER TABLE item DROP COLUMN provenance"),
                        "the qualification must gate the DROP, not follow it")


if __name__ == "__main__":
    unittest.main()
