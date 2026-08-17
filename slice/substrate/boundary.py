"""The Data-Access Boundary -- ISOLATION_ENFORCEMENT.md section 4.1.

Registered as a NOVA Core responsibility by ADR 0017 (Accepted 2026-08-13).
This module implements it; the responsibility was not invented here.

WHAT PROBLEM THIS SOLVES
------------------------
The slice's previous store exposed:

    StoreRegistry.for_scope("business/kairo/client-b")

Any code could name any scope. `runtime.py` passed `token.scope_path` and was
correct by convention -- but I-78 requires the binding to be established "only
by the Data-Access Boundary... derived solely from the Context Token's scope
path, and verified against the presented token at establishment". A method
taking a caller-supplied string is not that, and renaming it would not make it
that.

Here the scope is never a parameter. It is read out of a verified token, and
the handle returned has no method that could change it.

WHAT IS ENFORCED WHERE -- stated precisely, because the split matters
--------------------------------------------------------------------
  C-1  a query without a scope predicate cannot reach another scope
       -> enforced by PostgreSQL RLS, in the engine
  C-2  application code cannot alter its own binding mid-execution
       -> enforced HERE, by the interface. RLS cannot do this: the binding
          lives in a session setting and any code holding the connection can
          set it again. That is why the boundary owns connection acquisition.
  C-6  enforcement independent of the PDP
       -> this module never calls the PDP (I-62)

HONEST LIMIT
------------
Python has no true private state. `ScopedChannel` gives application code no
API to reach the connection or re-bind, but introspection could still reach a
name-mangled attribute. The architecture places this module in the TRUSTED
zone (SECURITY_BOUNDARIES.md section 4), where the threat model is mistake,
not a hostile in-process adversary. This is a structural guarantee against
error, not a sandbox.
"""

from __future__ import annotations

import contextlib
from typing import Any, Iterator, Optional, Sequence

import psycopg2
import psycopg2.pool

from ..core.types import ContextToken, Denied


class ScopedChannel:
    """A handle bound to exactly one scope, for the life of one transaction.

    Deliberately absent: any method that sets, widens, re-binds or reuses the
    binding; any accessor returning the connection or a cursor. I-78, I-86.
    """

    __slots__ = ("__weakref__", "_ScopedChannel__conn", "_scope_path", "_trace_id", "_closed")

    def __init__(self, conn: Any, scope_path: str, trace_id: str):
        self.__conn = conn
        self._scope_path = scope_path
        self._trace_id = trace_id
        self._closed = False

    @property
    def scope_path(self) -> str:
        """Readable so callers can record what they operated on. Not settable."""
        return self._scope_path

    def _guard(self) -> None:
        """Re-assert the binding before every statement.

        Defence in depth, not the primary control. If anything re-bound the
        session behind the boundary's back, the channel fails closed rather
        than silently reading a different scope. Cheap, and it converts a
        silent isolation failure into a loud one.
        """
        if self._closed:
            raise Denied("boundary.channel", "channel is closed", "I-78", True)
        cur = self.__conn.cursor()
        cur.execute("SELECT nova.current_scope()")
        row = cur.fetchone()
        cur.close()
        actual = row[0] if row else None
        if actual != self._scope_path:
            raise Denied(
                "boundary.binding",
                "scope binding changed inside the transaction",
                "I-78",
                True,
            )

    def fetch(self, sql: str, params: Sequence[Any] = ()) -> list[tuple]:
        self._guard()
        cur = self.__conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return rows

    def execute(self, sql: str, params: Sequence[Any] = ()) -> None:
        self._guard()
        cur = self.__conn.cursor()
        cur.execute(sql, params)
        cur.close()

    def _close(self) -> None:
        self._closed = True


class DataAccessBoundary:
    """Opens scope-bound channels. The only component permitted to do so.

    Never consults the PDP (I-62, C-6). Creates no authorization authority --
    its only failure mode is refusing to open a channel (ISOLATION_ENFORCEMENT
    section 4.1).
    """

    def __init__(self, dsn: str, context_service: Any, minconn: int = 1, maxconn: int = 4):
        self._pool = psycopg2.pool.ThreadedConnectionPool(minconn, maxconn, dsn)
        self._context = context_service

    # -- establishment ------------------------------------------------------

    def _verify(self, token: Optional[ContextToken]) -> str:
        """Derive the binding from the token, and from nothing else.

        I-79: missing, ambiguous, invalid, inconsistent or unestablishable
        scope opens no channel and denies. There is no unbound channel and no
        default scope.
        """
        if token is None:
            raise Denied("boundary.open", "no context token presented", "I-79", True)

        # I-87 -- integrity is checked before anything in the token is trusted,
        # including the scope path we are about to bind to.
        self._context.verify(token)

        if token.expired():
            raise Denied("boundary.open", "context token expired", "I-65", True)

        scope = (token.scope_path or "").strip()
        if not scope:
            raise Denied("boundary.open", "token carries no scope path", "I-79", True)
        if scope != token.scope_path:
            raise Denied("boundary.open", "scope path is not canonical", "I-79", True)
        return scope

    @contextlib.contextmanager
    def open(self, token: Optional[ContextToken]) -> Iterator[ScopedChannel]:
        """Open a scope-bound channel for the life of one transaction.

        The binding is transaction-local, so it cannot outlive the transaction
        and cannot travel back to the pool -- which is what makes pool reuse
        safe rather than merely conventional.
        """
        scope = self._verify(token)

        conn = self._pool.getconn()
        channel: Optional[ScopedChannel] = None
        try:
            conn.autocommit = False

            # A connection returning from the pool must carry nothing. If it
            # does, the pool has leaked context and the boundary refuses rather
            # than overwriting the evidence.
            cur = conn.cursor()
            cur.execute("SELECT nova.current_scope()")
            residual = cur.fetchone()[0]
            cur.close()
            if residual is not None:
                conn.rollback()
                raise Denied(
                    "boundary.open",
                    "connection carried a residual scope binding",
                    "I-78",
                    True,
                )

            # set_config(..., is_local => true) is the whole pooling story: the
            # setting reverts when the transaction ends, whether it commits or
            # rolls back. Parameterised, so the scope path is never concatenated
            # into SQL.
            cur = conn.cursor()
            cur.execute("SELECT set_config('nova.scope_path', %s, true)", (scope,))
            cur.close()

            channel = ScopedChannel(conn, scope, token.trace_id)
            yield channel
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            if channel is not None:
                channel._close()
            # Belt and braces: the transaction already discarded the binding.
            try:
                conn.rollback()
            except Exception:
                pass
            self._pool.putconn(conn)

    def close(self) -> None:
        self._pool.closeall()
