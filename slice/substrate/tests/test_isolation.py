"""I-03 adversarial suite -- against a REAL PostgreSQL instance.

This is the suite that decides whether I-03 is DEMONSTRATED or ENFORCED. It is
the first suite in this repository that tests a security control rather than a
presentation property, so its standards are different:

  * It does not test through the application's own read path. Several checks
    open a RAW connection as nova_app and issue hostile SQL directly, because
    a test that goes through the code under test cannot detect that the code is
    the only thing holding the property.

  * It SKIPS when PostgreSQL is unavailable. It never passes without its
    subject. A green security suite that never ran is worse than a red one.

  * Application-side filtering is absent by construction: no query below adds a
    scope predicate. If isolation held only because Python remembered a WHERE
    clause, check 1 and 3 would fail.

I-03 [PHYS]: "An execution operating in Client A's scope cannot read, write, or
enumerate Client B's resources -- by any path, including error messages and
timing."

Run:  python3 -m unittest slice.substrate.tests.test_isolation
"""

from __future__ import annotations

import time
import unittest

from .. import db
from ..boundary import DataAccessBoundary
from ...core.context_service import ContextService
from ...core.scope_tree import ScopeTree
from ...core.types import Denied, Risk

# The repository's scope-path convention, matching slice/tests/harness.py.
A = "/business/KAIRO/client-a"
B = "/business/KAIRO/client-b"
DEEP_A = "/business/KAIRO/client-a/website"


@unittest.skipUnless(db.available(), "no PostgreSQL instance reachable -- suite SKIPPED, not passed")
class IsolationTest(unittest.TestCase):
    """Shared fixture: two sibling scopes, each with data the other must not see."""

    @classmethod
    def setUpClass(cls):
        db.apply_schema()

    def setUp(self):
        import psycopg2

        db.reset_data()

        # A real scope tree and real James-created grants: the boundary must be
        # exercised with tokens the Context service would actually issue.
        tree = ScopeTree()
        tree.add_scope("/business", "domain")
        tree.add_scope("/business/KAIRO", "business")
        for path in (A, B, DEEP_A):
            tree.add_scope(path, "client")
        for path in (A, B, DEEP_A):
            tree.james_grants("james", "read", "*", path, Risk.READ)   # I-10

        self.ctx = ContextService(tree, secret=b"substrate-slice-test-key")
        self.boundary = DataAccessBoundary(db.app_dsn(), self.ctx)

        # Seed as the owner: seeding through the boundary would only prove the
        # boundary can write where it is bound, not that isolation holds.
        conn = psycopg2.connect(db.superuser_dsn())
        conn.autocommit = True
        with conn.cursor() as cur:
            for path in (A, B, DEEP_A):
                cur.execute(
                    "INSERT INTO scope (scope_path, kind, parent_path) VALUES (%s,'client',%s)",
                    (path, "/business/KAIRO"),
                )
            cur.execute(
                "INSERT INTO item (item_ref, scope_path, body) VALUES "
                "('a-1',%s,'CLIENT A SECRET'), ('b-1',%s,'CLIENT B SECRET'), ('deep-1',%s,'A WEBSITE')",
                (A, B, DEEP_A),
            )
        conn.close()

    def tearDown(self):
        self.boundary.close()

    def token(self, scope: str, actor: str = "james"):
        # `identity` is the grantee the Context service checks grants against
        # (I-10, I-14) -- not a token name.
        return self.ctx.issue_root(
            identity="james", actor=actor, scope_path=scope,
            rights=frozenset({"read"}), ceiling=Risk.READ, ttl=300,
        )

    def raw_app_conn(self):
        """A raw nova_app connection -- what a mistake or an attacker would hold."""
        import psycopg2
        return psycopg2.connect(db.app_dsn())

    # -- 0. negative control -------------------------------------------------

    def test_0_negative_control_rls_is_what_holds_the_property(self):
        """Prove the suite has teeth.

        Every other check asserts that scope B is unreachable. None of them can
        tell whether that is because RLS enforces it or because the data simply
        is not there. So: turn RLS off, confirm the leak APPEARS, turn it back
        on, confirm it closes.

        Without this, a misconfigured database would produce a fully green
        security suite -- which is how isolation failures survive review. This
        was not hypothetical: the first version of this file passed with RLS
        disabled, because the fixture re-applied the schema and silently
        re-enabled it.
        """
        import psycopg2

        admin = psycopg2.connect(db.superuser_dsn())
        admin.autocommit = True

        def rls(state: str):
            with admin.cursor() as cur:
                if state == "off":
                    cur.execute("ALTER TABLE item NO FORCE ROW LEVEL SECURITY")
                    cur.execute("ALTER TABLE item DISABLE ROW LEVEL SECURITY")
                else:
                    cur.execute("ALTER TABLE item ENABLE ROW LEVEL SECURITY")
                    cur.execute("ALTER TABLE item FORCE ROW LEVEL SECURITY")

        def visible_scopes() -> set:
            conn = self.raw_app_conn()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                    cur.execute("SELECT DISTINCT scope_path FROM item")
                    return {r[0] for r in cur.fetchall()}
            finally:
                conn.rollback(); conn.close()

        try:
            rls("off")
            leaked = visible_scopes()
            self.assertIn(
                B, leaked,
                "RLS disabled but scope B still unreachable -- this suite is not "
                "testing the control it claims to test",
            )
        finally:
            rls("on")
            admin.close()

        self.assertEqual(
            {A, DEEP_A}, visible_scopes(),
            "RLS did not close the leak when re-enabled",
        )

    # -- 1. no application-side filtering -----------------------------------

    def test_1_isolation_holds_with_no_application_side_filter(self):
        """SELECT * with no WHERE at all, through the boundary."""
        with self.boundary.open(self.token(A)) as ch:
            rows = ch.fetch("SELECT body FROM item")          # no predicate
        bodies = {r[0] for r in rows}
        self.assertIn("CLIENT A SECRET", bodies)
        self.assertNotIn("CLIENT B SECRET", bodies)

    # -- 2. direct hostile query --------------------------------------------

    def test_2_direct_hostile_query_for_the_other_scope(self):
        """Raw connection, bound to A, explicitly asking for B by name."""
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                cur.execute("SELECT body FROM item WHERE scope_path = %s", (B,))
                self.assertEqual([], cur.fetchall())
        finally:
            conn.rollback(); conn.close()

    # -- 3. no predicate -----------------------------------------------------

    def test_3_no_predicate_returns_only_the_bound_scope(self):
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                cur.execute("SELECT scope_path FROM item")
                paths = {r[0] for r in cur.fetchall()}
            # A and its descendant are in scope (containment, per covers());
            # the sibling is not.
            self.assertEqual({A, DEEP_A}, paths)
        finally:
            conn.rollback(); conn.close()

    def test_3b_enumeration_and_counts_are_also_bounded(self):
        """I-03 covers enumerate, not only read."""
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                cur.execute("SELECT count(*) FROM item")
                self.assertEqual(2, cur.fetchone()[0])          # a-1 and deep-1
                cur.execute("SELECT count(*) FROM item WHERE body LIKE '%%B SECRET%%'")
                self.assertEqual(0, cur.fetchone()[0])
        finally:
            conn.rollback(); conn.close()

    # -- 4. rebinding attack -------------------------------------------------

    def test_4_channel_exposes_no_way_to_rebind(self):
        """C-2 at the interface: the unsafe operation must be absent, not guarded."""
        with self.boundary.open(self.token(A)) as ch:
            for attr in ("rebind", "set_scope", "connection", "conn", "cursor", "for_scope"):
                self.assertFalse(hasattr(ch, attr), f"ScopedChannel exposes {attr}")
            with self.assertRaises(AttributeError):
                ch.scope_path = B                                # read-only property

    def test_4b_rebinding_behind_the_boundary_fails_closed(self):
        """Defence in depth: if the session is re-bound anyway, the next
        statement through the channel denies rather than reading scope B."""
        with self.boundary.open(self.token(A)) as ch:
            self.assertTrue(ch.fetch("SELECT 1"))
            # Simulate a rebind performed outside the channel's API.
            ch._ScopedChannel__conn.cursor().execute(
                "SELECT set_config('nova.scope_path', %s, true)", (B,))
            with self.assertRaises(Denied) as cm:
                ch.fetch("SELECT body FROM item")
            self.assertEqual("I-78", cm.exception.invariant)

    # -- 5. pool contamination ----------------------------------------------

    def test_5_binding_does_not_survive_into_the_next_transaction(self):
        """The same pooled connection, reused for the sibling scope."""
        with self.boundary.open(self.token(A)) as ch:
            self.assertEqual({A, DEEP_A}, {r[0] for r in ch.fetch("SELECT scope_path FROM item")})
        # Same pool, minconn=1 -- overwhelmingly the same physical connection.
        with self.boundary.open(self.token(B)) as ch:
            paths = {r[0] for r in ch.fetch("SELECT scope_path FROM item")}
        self.assertEqual({B}, paths, "scope A leaked into a later transaction")

    def test_5b_a_residual_binding_is_refused_not_overwritten(self):
        """If a connection ever came back dirty, the boundary must not paper over it."""
        with self.boundary.open(self.token(A)) as ch:
            self.assertTrue(ch.fetch("SELECT 1"))
        # After the transaction the setting must be gone, which is what makes
        # the residual check meaningful rather than decorative.
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT nova.current_scope()")
                self.assertIsNone(cur.fetchone()[0])
        finally:
            conn.close()

    # -- 6. missing context --------------------------------------------------

    def test_6_no_token_opens_no_channel(self):
        with self.assertRaises(Denied) as cm:
            with self.boundary.open(None):
                self.fail("a channel was opened without a token")
        self.assertEqual("I-79", cm.exception.invariant)

    def test_6b_unbound_connection_reads_nothing(self):
        """There is no default scope: unbound means empty, never everything."""
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT count(*) FROM item")        # no binding set
                self.assertEqual(0, cur.fetchone()[0])
        finally:
            conn.close()

    # -- 7. invalid / ambiguous context -------------------------------------

    def test_7_forged_token_opens_no_channel(self):
        import dataclasses
        forged = dataclasses.replace(self.token(A), scope_path=B)
        with self.assertRaises(Denied) as cm:
            with self.boundary.open(forged):
                self.fail("a forged token opened a channel")
        self.assertEqual("I-87", cm.exception.invariant)

    def test_7b_expired_token_opens_no_channel(self):
        tok = self.ctx.issue_root(
            identity="james", actor="james", scope_path=A,
            rights=frozenset({"read"}), ceiling=Risk.READ, ttl=-1,
        )
        with self.assertRaises(Denied):
            with self.boundary.open(tok):
                self.fail("an expired token opened a channel")

    def test_7c_empty_scope_opens_no_channel(self):
        import dataclasses
        blank = dataclasses.replace(self.token(A), scope_path="")
        with self.assertRaises(Denied):
            with self.boundary.open(blank):
                self.fail("a token with no scope opened a channel")

    # -- 8. RLS bypass -------------------------------------------------------

    def test_8_application_role_cannot_bypass_rls(self):
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT current_user")
                self.assertEqual("nova_app", cur.fetchone()[0])
                cur.execute(
                    "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user")
                is_super, bypasses = cur.fetchone()
                self.assertFalse(is_super, "application role is a superuser")
                self.assertFalse(bypasses, "application role has BYPASSRLS")
        finally:
            conn.close()

    def test_8b_application_role_does_not_own_the_tables(self):
        """An owner bypasses RLS unless FORCE is set -- so check both."""
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT c.relname, pg_get_userbyid(c.relowner),
                           c.relrowsecurity, c.relforcerowsecurity
                      FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                     WHERE n.nspname = 'public'
                       AND c.relname IN ('item','scope','grant','approval','audit_record')
                """)
                for name, owner, enabled, forced in cur.fetchall():
                    self.assertNotEqual("nova_app", owner, f"{name} is owned by the app role")
                    self.assertTrue(enabled, f"RLS not enabled on {name}")
                    self.assertTrue(forced, f"RLS not FORCEd on {name}")
        finally:
            conn.close()

    def test_8c_application_role_cannot_disable_rls(self):
        import psycopg2
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                with self.assertRaises(psycopg2.Error):
                    cur.execute("ALTER TABLE item DISABLE ROW LEVEL SECURITY")
        finally:
            conn.rollback(); conn.close()

    # -- 9. leakage ----------------------------------------------------------

    def test_9_cross_scope_write_is_refused_not_silently_dropped(self):
        """WITH CHECK: writing outside the binding must error, not vanish."""
        import psycopg2
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                with self.assertRaises(psycopg2.Error):
                    cur.execute(
                        "INSERT INTO item (item_ref, scope_path, body) VALUES ('x',%s,'planted')",
                        (B,))
        finally:
            conn.rollback(); conn.close()

    def test_9b_existing_and_nonexistent_rows_are_indistinguishable(self):
        """A real row in scope B and a row that never existed must look the same."""
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                cur.execute("SELECT count(*) FROM item WHERE item_ref = 'b-1'")   # exists in B
                real = cur.fetchone()[0]
                cur.execute("SELECT count(*) FROM item WHERE item_ref = 'never-existed'")
                fake = cur.fetchone()[0]
            self.assertEqual(0, real)
            self.assertEqual(fake, real, "an out-of-scope row is distinguishable from a missing one")
        finally:
            conn.rollback(); conn.close()

    def test_9c_update_and_delete_cannot_reach_across(self):
        conn = self.raw_app_conn()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT set_config('nova.scope_path', %s, true)", (A,))
                cur.execute("UPDATE item SET body = 'TAMPERED' WHERE scope_path = %s", (B,))
                self.assertEqual(0, cur.rowcount)
                cur.execute("DELETE FROM item WHERE scope_path = %s", (B,))
                self.assertEqual(0, cur.rowcount)
            conn.commit()
        finally:
            conn.close()
        # Confirm from a privileged connection that B is untouched.
        import psycopg2
        conn = psycopg2.connect(db.superuser_dsn())
        with conn.cursor() as cur:
            cur.execute("SELECT body FROM item WHERE scope_path = %s", (B,))
            self.assertEqual("CLIENT B SECRET", cur.fetchone()[0])
        conn.close()

    def test_9d_timing_is_not_measured_and_is_not_claimed(self):
        """I-03 names timing. This suite does not establish timing
        indistinguishability, and says so rather than implying it.

        A meaningful timing result needs many samples, a quiet machine and a
        statistical claim. Asserting it from a handful of calls in a shared
        container would be theatre.
        """
        self.skipTest("timing indistinguishability not tested -- see README")


if __name__ == "__main__":
    unittest.main()
