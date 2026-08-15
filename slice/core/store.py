"""Per-scope storage.

SLICE-LOCAL MECHANISM. One SQLite file per scope node. This is the
"per-scope physical separation" family named in ISOLATION_ENFORCEMENT.md
section 3.1 -- chosen so I-03 is enforced by CONSTRUCTION in the slice rather
than by query correctness.

It selects neither D-02 nor D-33a. See slice/README.md for exactly what this
does and does not prove.

I-86: no channel is bound to more than one scope. Enforced here by giving
each scope its own connection and refusing to hold two open at once for a
join.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from typing import Optional

from .types import Denied


class ScopeStore:
    """A connection bound to exactly ONE scope. There is deliberately no API
    that opens a second scope's database from an instance of this class."""

    def __init__(self, root: str, scope_path: str):
        self.scope_path = scope_path
        self._root = root
        safe = scope_path.strip("/").replace("/", "__") or "root"
        os.makedirs(root, exist_ok=True)
        self._path = os.path.join(root, f"scope__{safe}.sqlite3")
        # check_same_thread=False + a lock: SLICE-LOCAL. The architecture
        # expects concurrent descendants (AG-10, AG-13); SQLite thread
        # affinity is a property of this fixture, not of NOVA.
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init()

    def _init(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS items (
                id          TEXT PRIMARY KEY,
                scope_path  TEXT NOT NULL,
                body        TEXT NOT NULL,
                taint       TEXT NOT NULL   -- I-111: persisted, not derived on read
            );
            CREATE TABLE IF NOT EXISTS audit (
                seq         INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          REAL NOT NULL,
                writer      TEXT NOT NULL,  -- W-1 | W-2 | W-3 (ADR 0023)
                category    TEXT NOT NULL,
                scope_path  TEXT NOT NULL,
                trace_id    TEXT NOT NULL,
                detail      TEXT NOT NULL
            );
            """
        )
        self._conn.commit()

    # -- items -------------------------------------------------------------

    def put_item(self, item_id: str, scope_path: str, body: str, taint_row: str) -> None:
        if not self._in_scope(scope_path):
            # I-03 / I-86: a write naming another scope is refused here, not
            # merely filtered. The store cannot reach another scope's file.
            raise Denied("store.put", f"{scope_path} outside {self.scope_path}", "I-03", True)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO items (id, scope_path, body, taint) VALUES (?,?,?,?)",
                (item_id, scope_path, body, taint_row),
            )
            self._conn.commit()

    def get_item(self, item_id: str) -> Optional[tuple[str, str, str]]:
        row = self._conn.execute(
            "SELECT scope_path, body, taint FROM items WHERE id=?", (item_id,)
        ).fetchone()
        return row if row else None

    def _in_scope(self, scope_path: str) -> bool:
        return scope_path == self.scope_path or scope_path.startswith(self.scope_path + "/")

    # -- audit -------------------------------------------------------------

    def append_audit(self, ts: float, writer: str, category: str,
                     scope_path: str, trace_id: str, detail: str) -> int:
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO audit (ts, writer, category, scope_path, trace_id, detail)"
                " VALUES (?,?,?,?,?,?)",
                (ts, writer, category, scope_path, trace_id, detail),
            )
            self._conn.commit()
            return int(cur.lastrowid or 0)

    def audit_records(self) -> list[tuple]:
        return self._conn.execute(
            "SELECT seq, ts, writer, category, scope_path, trace_id, detail FROM audit ORDER BY seq"
        ).fetchall()

    def close(self) -> None:
        self._conn.close()


class StoreRegistry:
    """Opens one ScopeStore per scope. I-89: there is deliberately NO method
    here that reads across scopes -- reconstructing a cross-scope view is N
    separate per-scope reads by the caller, never an aggregating query."""

    def __init__(self, root: str):
        self._root = root
        self._open: dict[str, ScopeStore] = {}

    def for_scope(self, scope_path: str) -> ScopeStore:
        if scope_path not in self._open:
            self._open[scope_path] = ScopeStore(self._root, scope_path)
        return self._open[scope_path]

    def close(self) -> None:
        for s in self._open.values():
            s.close()
        self._open.clear()
