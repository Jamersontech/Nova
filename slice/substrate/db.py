"""Cluster configuration and schema application for the substrate slice.

SLICE-LOCAL. This is how the tests reach a real PostgreSQL instance; it is not
deployment tooling and selects no hosting product. ADR 0044 records the
hosting decision; nothing here implements it.

Two connection identities, deliberately separated:

    OWNER  nova_owner  -- DDL and migrations. Never used by request handling.
    APP    nova_app    -- NOBYPASSRLS, NOSUPERUSER, not a table owner.
                          The only identity the Data-Access Boundary uses.

The separation is the point. A single connection identity that could both
migrate and serve requests would make the RLS configuration advisory.
"""

from __future__ import annotations

import os
import pathlib

SCHEMA = pathlib.Path(__file__).with_name("schema.sql")

HOST = os.environ.get("NOVA_PGHOST", "/tmp")
PORT = os.environ.get("NOVA_PGPORT", "5433")
DBNAME = os.environ.get("NOVA_PGDATABASE", "nova_substrate")


def _dsn(user: str, dbname: str = "") -> str:
    return f"host={HOST} port={PORT} dbname={dbname or DBNAME} user={user}"


def owner_dsn() -> str:
    """Privileged. Migrations only."""
    return _dsn(os.environ.get("NOVA_PGOWNER", "nova_owner"))


def app_dsn() -> str:
    """The application identity. Subject to RLS."""
    return _dsn(os.environ.get("NOVA_PGAPPUSER", "nova_app"))


def control_dsn() -> str:
    """The control-plane reader: SELECT on `scope` and `grant`, nothing else.
    Used once at startup to load the permission model, never in the request
    path. Not a bypass -- a policy names this role for exactly those reads."""
    return _dsn(os.environ.get("NOVA_PGCONTROLUSER", "nova_control"))


def auth_dsn() -> str:
    """The authentication identity. Privileges on the two auth tables and
    nothing else -- authentication runs before a Context Token exists, so it
    cannot go through the Data-Access Boundary and must not be able to reach
    scoped data. Asserted by test."""
    return _dsn(os.environ.get("NOVA_PGAUTHUSER", "nova_auth"))


def superuser_dsn() -> str:
    """Cluster bootstrap only -- creating the database and applying schema.sql.

    Present so the adversarial suite can also PROVE that the application role
    is not this one.
    """
    return _dsn(os.environ.get("NOVA_PGSUPERUSER", "postgres"))


def available() -> bool:
    """True when a real PostgreSQL instance is reachable.

    The adversarial suite SKIPS rather than passes when this is False. A
    security suite that silently succeeds without its subject is worse than no
    suite -- it reports a property nothing tested.
    """
    try:
        import psycopg2
    except ImportError:
        return False
    try:
        conn = psycopg2.connect(superuser_dsn(), connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False


def diagnose() -> str:
    """WHY the cluster is not usable, in one actionable line. Startup only.

    `available()` answers yes or no, and that was all the operator ever saw. The
    two failures a first run actually hits -- no server running, and no
    `nova_substrate` database -- were reported IDENTICALLY, because
    `superuser_dsn()` names the database, so a missing database looks exactly
    like a missing server. Measured, not assumed: both printed "no PostgreSQL
    instance reachable", which sends someone to restart a server that is
    already running.

    So this asks the maintenance database as a second question. Nothing here
    creates, migrates or connects on behalf of the application -- it is
    diagnosis, and it returns a string.
    """
    try:
        import psycopg2
    except ImportError:
        return "psycopg2 is not installed -- pip install psycopg2-binary"

    superuser = os.environ.get("NOVA_PGSUPERUSER", "postgres")
    try:
        psycopg2.connect(superuser_dsn(), connect_timeout=3).close()
        return ""
    except Exception as exc:
        detail = (str(exc).strip().splitlines() or [""])[0]

    # The server answered for `postgres` but not for ours: the DATABASE is what
    # is missing, and creating it is a different command from starting a server.
    try:
        psycopg2.connect(_dsn(superuser, "postgres"), connect_timeout=3).close()
        return (f"the server is running, but database {DBNAME!r} does not exist"
                f" -- create it:  createdb -h {HOST} -p {PORT} {DBNAME}")
    except Exception:
        pass

    return f"no PostgreSQL server at host={HOST} port={PORT} -- {detail}"


def apply_schema() -> None:
    """Apply schema.sql as the superuser. Idempotent."""
    import psycopg2

    conn = psycopg2.connect(superuser_dsn())
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(SCHEMA.read_text())
    conn.close()


def reset_data() -> None:
    """Empty the tables between tests, as the owner. Never as nova_app."""
    import psycopg2

    conn = psycopg2.connect(superuser_dsn())
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute('TRUNCATE item, task, "grant", approval, audit_record, scope,'
                    ' actor, auth_credential, auth_session,'
                    ' authority_revocation RESTART IDENTITY')
    conn.close()
