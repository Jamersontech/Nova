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

from .delegation import Delegation, check_within_parent
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
        # AG-11: the service tracks which execution identities have ENDED, so a
        # child fails closed at its NEXT enforcement point when its delegator
        # ends by completion, failure, termination, revocation or stop alike.
        self._ended: set[str] = set()
        # Per-token authority facts the ContextToken does not carry as fields.
        # Held by the sole issuer, never by the runtime (AG-1/AG-2).
        self._facts: dict[str, dict] = {}

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
        # AG-11 / V-2: a child never outlives the execution identity that
        # granted it. Checked HERE -- at the next enforcement point -- which is
        # what "fails closed at its next enforcement point" means. Not
        # retroactive; an action already completed is not undone.
        facts = self._facts.get(token.trace_id, {})
        for ancestor in facts.get("ancestry", ()):
            if ancestor in self._ended or ancestor in self._revoked:
                raise Denied("context.verify",
                             "granting execution identity has ended", "I-107", True)

    def end_execution(self, trace_id: str) -> None:
        """AG-11: normal completion, failure, termination, revocation and
        emergency stop are all the same trigger."""
        self._ended.add(trace_id)

    def facts(self, token: ContextToken) -> dict:
        """Authority facts the sole issuer holds for a token: tools, ancestry,
        may_redelegate. The runtime reads; it never writes."""
        return dict(self._facts.get(token.trace_id, {}))

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

    def issue_root_tracked(self, *args, **kwargs) -> ContextToken:
        """issue_root plus registration of the token's authority facts."""
        tools = kwargs.pop("tools", frozenset())
        may_redelegate = kwargs.pop("may_redelegate", False)
        tok = self.issue_root(*args, **kwargs)
        self._facts[tok.trace_id] = {
            "tools": frozenset(tools),
            "ancestry": (),
            "may_redelegate": bool(may_redelegate),
        }
        return tok

    def delegate(self, parent: ContextToken, delegation: Delegation,
                 delegate_allowed_context: Optional[str] = None,
                 delegate_allowed_tools: Optional[frozenset[str]] = None,
                 delegate_permissions: Optional[frozenset[str]] = None,
                 delegate_risk_ceiling: Optional[Risk] = None) -> ContextToken:
        """AG-1/AG-2: the Context service is the SOLE issuer, including narrowed
        tokens. The Agent Runtime REQUESTS; it never mints.

        AG-3: issuance verifies the request against every I-07 input --
        the parent token, the DELEGATE's agent definition, James's grants, and
        I-107's delegation constraints -- before issuing.

        AG-4: refusal is TOTAL and fail-closed. Nothing is trimmed to fit.
        """
        # The parent's own token must still be valid at issuance time.
        self.verify(parent)

        pf = self._facts.get(parent.trace_id, {})
        parent_tools = pf.get("tools", frozenset())
        parent_ancestry = pf.get("ancestry", ())
        parent_may_redelegate = pf.get("may_redelegate", False)

        if delegation.delegator != parent.trace_id:
            raise Denied("delegation.delegator",
                         "delegation does not name the presenting execution", "I-107", True)

        # I-107 / AG-7..AG-9, checked against the PARENT's actual authority.
        check_within_parent(
            delegation,
            parent_scope=parent.scope_path,
            parent_rights=parent.granted_rights,
            parent_tools=parent_tools,
            parent_ceiling=parent.risk_ceiling,
            parent_expiry=parent.expires_at,
            parent_may_redelegate=parent_may_redelegate,
            parent_ancestry=parent_ancestry,
        )

        # AG-3: the DELEGATE's own agent definition is also an I-07 input.
        # A narrow delegation to an agent whose definition does not permit it
        # is still refused -- the intersection, never the union.
        if delegate_allowed_context is not None and not ScopeTree.contains(
                delegate_allowed_context, delegation.scope_path):
            raise Denied("delegation.definition",
                         "scope exceeds delegate's Allowed Context", "I-106", True)
        if delegate_allowed_tools is not None and not delegation.tools <= delegate_allowed_tools:
            raise Denied("delegation.definition",
                         "tools exceed delegate's Allowed Tools", "I-106", True)
        if delegate_permissions is not None and not delegation.rights <= delegate_permissions:
            raise Denied("delegation.definition",
                         "rights exceed delegate's Permissions", "I-106", True)
        if delegate_risk_ceiling is not None and delegation.risk_ceiling > delegate_risk_ceiling:
            raise Denied("delegation.definition",
                         "ceiling exceeds delegate's risk ceiling", "I-106", True)

        # James-created grants must still cover every delegated right (I-10).
        for right in delegation.rights:
            if self._tree.find_grant(parent.identity, right, "*", delegation.scope_path) is None:
                raise Denied("delegation.grant", f"no grant for {right}", "I-14", True)

        now = time.time()
        trace_id = uuid.uuid4().hex
        integrity = self._sign(parent.identity, delegation.delegate, delegation.scope_path,
                               delegation.rights, delegation.risk_ceiling,
                               now, delegation.expires_at, trace_id)
        child = ContextToken(parent.identity, delegation.delegate, delegation.scope_path,
                             frozenset(delegation.rights), delegation.risk_ceiling,
                             now, delegation.expires_at, trace_id, integrity)
        self._facts[trace_id] = {
            "tools": frozenset(delegation.tools),
            "ancestry": parent_ancestry + (parent.trace_id,),
            "may_redelegate": delegation.may_redelegate,
        }
        return child
