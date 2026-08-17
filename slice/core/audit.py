"""Audit writer.

ADR 0023 writer authorities:
  W-1  the execution's own authorization      -> execution records
  W-2  the authorization decision itself      -> allow / deny / approval-required
  W-3  control-plane                          -> concerns no client scope

I-93: audit-write failure is FAIL-CLOSED for access. If a required record
cannot be durably written, the authorization resolves to deny and the
execution does not start.
"""

from __future__ import annotations

import time

from .store import StoreRegistry
from .types import Denied

CONTROL_PLANE = "/__control"


class AuditWriter:
    def __init__(self, stores: StoreRegistry):
        self._stores = stores
        self.fail_writes = False   # test hook for I-93; never a production switch

    def write(self, writer: str, category: str, scope_path: str,
              trace_id: str, detail: str) -> int:
        if writer not in ("W-1", "W-2", "W-3"):
            raise Denied("audit.write", f"unknown writer authority {writer}", "ADR-0023")
        target = CONTROL_PLANE if writer == "W-3" else scope_path
        if self.fail_writes:
            # I-93: the caller must fail closed. We raise rather than return a
            # status, so a caller cannot ignore it by forgetting to check.
            raise Denied("audit.write", "audit unwritable", "I-93", True)
        store = self._stores.for_scope(target)
        return store.append_audit(time.time(), writer, category, target, trace_id, detail)

    def decision(self, scope_path: str, trace_id: str, outcome: str, detail: str) -> int:
        """W-2: the record of an authorization decision is written under the
        authority of that decision -- allow, deny and approval-required alike."""
        return self.write("W-2", f"decision.{outcome}", scope_path, trace_id, detail)

    def execution(self, scope_path: str, trace_id: str, category: str, detail: str) -> int:
        """W-1: written under the execution's own authorization."""
        return self.write("W-1", category, scope_path, trace_id, detail)
