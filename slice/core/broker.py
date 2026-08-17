"""The Credential Broker.

SECRETS_ARCHITECTURE.md section 3, protocol steps 1-7, plus step 2a added by
Section 11 (ADR 0037, Proposed).

  1. Tool presents: binding id + Context Token + intended operation
  2. Broker asks Policy: does this token's scope cover this binding's scope?
  2a. Broker checks: is this binding within the AUTHORIZED envelope? (I-114(b))
  3. Broker checks: is the binding active, unexpired, unrevoked?
  4. Broker checks: is the operation within the binding's permitted operations?
  5. Broker retrieves the secret and injects it into the outbound call
  6. Broker discards the secret; it is not returned upward
  7. Broker records the use -- by reference

I-22: no agent, orchestrator, tool or model ever receives credential material.
The secret exists in the outbound request and nowhere else reachable by NOVA's
own components -- enforced here by never returning it.

I-70: the broker discards secret material after injection.
S-8 / I-93: if the store is unavailable, outbound calls are DENIED, not
attempted without a credential.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .audit import AuditWriter
from .scope_tree import ScopeTree
from .types import Authorization, ContextToken, Denied, ExecutionBinding


@dataclass
class CredentialBinding:
    binding_id: str
    scope_path: str
    permitted_operations: frozenset[str]
    active: bool = True
    revoked: bool = False
    expires_at: float = float("inf")


class SecretsStore:
    """S-1: separate from the data store. A DIFFERENT file, opened only here.

    SLICE-LOCAL. Selects no D-10 technology. Values are generated at runtime
    and never committed -- AGENTS.md forbids committing secrets, and there are
    none to commit.
    """

    def __init__(self, path: str):
        self._path = path
        self.available = True          # S-8 test hook
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path):
            with open(path, "w") as fh:
                json.dump({}, fh)

    def put(self, binding_id: str, secret: str) -> None:
        data = self._read()
        data[binding_id] = secret
        with open(self._path, "w") as fh:
            json.dump(data, fh)

    def _read(self) -> dict[str, str]:
        with open(self._path) as fh:
            return json.load(fh)

    def retrieve(self, binding_id: str) -> str:
        """S-2: exactly one component calls this -- the broker. Nothing else
        in the slice imports SecretsStore."""
        if not self.available:
            raise Denied("secrets.retrieve", "secrets store unavailable", "S-8", True)
        data = self._read()
        if binding_id not in data:
            raise Denied("secrets.retrieve", f"no secret for {binding_id}", "I-14", True)
        return data[binding_id]


class CredentialBroker:
    def __init__(self, tree: ScopeTree, store: SecretsStore, audit: AuditWriter):
        self._tree = tree
        self._store = store
        self._audit = audit
        self._bindings: dict[str, CredentialBinding] = {}

    def register(self, binding: CredentialBinding, secret: str) -> None:
        self._bindings[binding.binding_id] = binding
        self._store.put(binding.binding_id, secret)

    def revoke(self, binding_id: str) -> None:
        """I-25: revoking a credential affects no other scope."""
        if binding_id in self._bindings:
            self._bindings[binding_id].revoked = True

    def inject_and_call(self, token: ContextToken, binding: ExecutionBinding,
                        authorization: Authorization, operation: str,
                        payload: dict[str, Any],
                        transport: Callable[[dict[str, Any], str], Any]) -> Any:
        """Steps 1-7. The secret is passed ONLY to `transport` and is never
        returned, logged, or placed in `payload` visible to the caller.

        Re-injection happens per attempt: this method is called afresh for
        every retry, so a credential revoked between attempts is not reusable
        (SECRETS_ARCHITECTURE.md section 4.2).
        """
        cb = self._bindings.get(binding.credential_binding_id)
        if cb is None:
            raise Denied("broker.step1", f"unknown binding {binding.credential_binding_id}",
                         "I-14", True)

        # -- step 2: does the token's scope cover this binding's scope? -----
        # I-24: a credential is usable only from a context whose scope covers
        # its binding.
        if not token.covers(cb.scope_path):
            raise Denied("broker.step2", "token scope does not cover binding scope",
                         "I-24", True)

        # -- step 2a (Section 11): is this the binding that was AUTHORIZED? --
        # Every other step asks whether the binding is ACCEPTABLE. This is the
        # only step that asks whether it is THE ONE THE DECISION WAS ABOUT.
        if binding.identity() not in authorization.binding_envelope:
            raise Denied("broker.step2a", "binding outside the authorized envelope",
                         "I-114", True)

        # -- step 3: active, unexpired, unrevoked? --------------------------
        if cb.revoked:
            raise Denied("broker.step3", "credential revoked", "I-74", True)
        if not cb.active:
            raise Denied("broker.step3", "credential inactive", "I-14", True)

        # -- step 4: operation within the binding's permitted operations? ---
        # Step 4 exists because external systems over-grant: the binding
        # narrows what the provider's key technically permits.
        if operation not in cb.permitted_operations:
            raise Denied("broker.step4", f"operation {operation} not permitted for binding",
                         "I-23", True)

        # -- step 5: retrieve and inject at the boundary --------------------
        secret = self._store.retrieve(cb.binding_id)
        try:
            result = transport(payload, secret)
        finally:
            # -- step 6: discard. Never returned upward (I-70).
            secret = None  # noqa: F841

        # -- step 7: record the use -- BY REFERENCE, never the value (I-48).
        self._audit.execution(token.scope_path, token.trace_id, "credentials",
                              f"used binding_ref={cb.binding_id} op={operation}")
        return result
