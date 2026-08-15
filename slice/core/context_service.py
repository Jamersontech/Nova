"""The Context service -- the SOLE issuer of Context Tokens (I-106).

The Agent Runtime REQUESTS narrowing; it never mints. A runtime-minted token
fails I-87's integrity detection at every enforcement point.

Before issuing, Context refuses any request whose resulting token would exceed
ANY of:
  - the requesting execution's own integrity-verified token
  - the named agent definition's Allowed Context / Allowed Tools / Permissions
  - James-created grants (I-10)
  - the delegation constraints of I-107

Refusal is TOTAL and fail-closed. There is no partial issuance.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from typing import Optional

from .scope_tree import ScopeTree
from .types import ContextToken, Denied, Risk


class ContextService:
    def __init__(self, tree: ScopeTree, secret: bytes):
        self._tree = tree
        # I-87 stands in as an HMAC over the token's fields. This provides
        # DETECTION of modification, which is what CT-1 requires; it does not
        # claim unforgeability. The key lives only here.
        self._secret = secret
        self._revoked: set[str] = set()

    # -- integrity ---------------------------------------------------------

    def _sign(self, identity: str, actor: str, scope_path: str,
              rights: frozenset[str], ceiling: Risk,
              issued_at: float, expires_at: float, trace_id: str) -> str:
        raw = "|".join([identity, actor, scope_path, ",".join(sorted(rights)),
                        str(int(ceiling)), f"{issued_at:.6f}", f"{expires_at:.6f}", trace_id])
        return hmac.new(self._secret, raw.encode(), hashlib.sha256).hexdigest()[:32]

    def verify(self, token: ContextToken) -> None:
        """Every enforcement point calls this. I-87: a modified or fabricated
        token is DETECTED here, not trusted."""
        expected = self._sign(token.identity, token.actor, token.scope_path,
                              token.granted_rights, token.risk_ceiling,
                              token.issued_at, token.expires_at, token.trace_id)
        if not hmac.compare_digest(expected, token.integrity):
            raise Denied("context.verify", "token integrity failure", "I-87", True)
        if token.trace_id in self._revoked:
            raise Denied("context.verify", "token revoked", "I-74", True)
        if token.expired():
            raise Denied("context.verify", "token expired", "I-13", False)

    def revoke(self, trace_id: str) -> None:
        """V-2: in-flight executions holding a revoked token fail closed at
        their NEXT enforcement point -- not retroactively."""
        self._revoked.add(trace_id)

    # -- issuance ----------------------------------------------------------

    def issue_root(self, identity: str, actor: str, scope_path: str,
                   rights: frozenset[str], ceiling: Risk, ttl: float = 300.0,
                   agent_allowed_context: Optional[str] = None,
                   agent_allowed_rights: Optional[frozenset[str]] = None,
                   agent_risk_ceiling: Optional[Risk] = None) -> ContextToken:
        """I-106: verified at issuance against the agent definition and grants.

        I-07: the result is the INTERSECTION of agent definition, granting
        identity, token and risk ceiling. No mechanism here produces a union.
        """
        scope = self._tree.get(scope_path)
        if not scope.active:
            raise Denied("context.issue", f"scope {scope_path} not active", "I-80", True)

        # Agent definition bound (AGENT_GOVERNANCE.md section 2). Refuse, never trim.
        if agent_allowed_context is not None and not ScopeTree.contains(agent_allowed_context, scope_path):
            raise Denied("context.issue", "scope exceeds agent Allowed Context", "I-106", True)
        if agent_allowed_rights is not None and not rights <= agent_allowed_rights:
            raise Denied("context.issue", "rights exceed agent Permissions", "I-106", True)
        if agent_risk_ceiling is not None and ceiling > agent_risk_ceiling:
            raise Denied("context.issue", "ceiling exceeds agent risk ceiling", "I-106", True)

        # James-created grants must cover every requested right (I-10, I-14).
        for right in rights:
            if self._tree.find_grant(identity, right, "*", scope_path) is None:
                raise Denied("context.issue", f"no grant for right {right}", "I-14", True)

        now = time.time()
        expires = now + ttl
        trace_id = uuid.uuid4().hex
        integrity = self._sign(identity, actor, scope_path, rights, ceiling, now, expires, trace_id)
        return ContextToken(identity, actor, scope_path, frozenset(rights), ceiling,
                            now, expires, trace_id, integrity)

    def narrow(self, parent: ContextToken, scope_path: str,
               rights: frozenset[str], ceiling: Risk,
               ttl: float) -> ContextToken:
        """I-107: delegation is STRICTLY narrowing and expires strictly
        earlier. The runtime calls this; it cannot mint."""
        self.verify(parent)
        if not parent.covers(scope_path):
            raise Denied("context.narrow", "scope not covered by parent", "I-107", True)
        if not rights <= parent.granted_rights:
            raise Denied("context.narrow", "rights not narrower than parent", "I-107", True)
        if ceiling > parent.risk_ceiling:
            raise Denied("context.narrow", "ceiling not narrower than parent", "I-107", True)
        now = time.time()
        expires = now + ttl
        if expires >= parent.expires_at:
            raise Denied("context.narrow", "child must expire strictly earlier", "I-107", True)
        strictly_narrower = (scope_path != parent.scope_path
                             or rights < parent.granted_rights
                             or ceiling < parent.risk_ceiling)
        if not strictly_narrower:
            raise Denied("context.narrow", "delegation is not strictly narrower", "I-107", True)
        integrity = self._sign(parent.identity, parent.actor, scope_path, rights,
                               ceiling, now, expires, parent.trace_id)
        return ContextToken(parent.identity, parent.actor, scope_path, frozenset(rights),
                            ceiling, now, expires, parent.trace_id, integrity)
