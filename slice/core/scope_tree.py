"""The scope tree.

SCOPE_AND_IDENTITY_MODEL.md: one unified tree. A scope is simultaneously a
context anchor, a permission boundary, a memory partition and a credential
partition. Access flows downward only by explicit grant; SIBLINGS HAVE NO
PATH (I-03).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import Denied, Risk


@dataclass
class Grant:
    """AUTHORIZATION_MODEL.md section 2. Created only by James (I-10); the
    slice has no API that lets an agent or model create one."""
    subject: str
    action: str
    resource_type: str
    scope_path: str
    max_risk: Risk
    revoked: bool = False


@dataclass
class Scope:
    path: str
    kind: str
    active: bool = True     # I-80: existence is not activation


class ScopeTree:
    def __init__(self) -> None:
        self._scopes: dict[str, Scope] = {}
        self._grants: list[Grant] = []
        self._denials: list[tuple[str, str, str]] = []   # explicit denials override grants

    # -- structure ---------------------------------------------------------

    def add_scope(self, path: str, kind: str, active: bool = True) -> Scope:
        s = Scope(path=path, kind=kind, active=active)
        self._scopes[path] = s
        return s

    def get(self, path: str) -> Scope:
        if path not in self._scopes:
            raise Denied("scope.resolve", f"unknown scope {path}", "I-79", True)
        return self._scopes[path]

    @staticmethod
    def contains(ancestor: str, descendant: str) -> bool:
        return descendant == ancestor or descendant.startswith(ancestor + "/")

    # -- grants ------------------------------------------------------------
    # I-10: only James creates grants. These methods represent James acting;
    # nothing in agent/, tools/ or integrations/ imports this module.

    def james_grants(self, subject: str, action: str, resource_type: str,
                     scope_path: str, max_risk: Risk) -> Grant:
        g = Grant(subject, action, resource_type, scope_path, max_risk)
        self._grants.append(g)
        return g

    def james_denies(self, subject: str, action: str, scope_path: str) -> None:
        self._denials.append((subject, action, scope_path))

    def revoke(self, grant: Grant) -> None:
        grant.revoked = True

    def explicit_denial(self, subject: str, action: str, scope_path: str) -> bool:
        for s, a, p in self._denials:
            if s == subject and a == action and self.contains(p, scope_path):
                return True
        return False

    def find_grant(self, subject: str, action: str, resource_type: str,
                   scope_path: str) -> Grant | None:
        """I-14: absence of a grant is a denial. This returns None rather than
        a permissive default, and every caller treats None as deny."""
        for g in self._grants:
            if (g.subject == subject and g.action == action
                    and g.resource_type == resource_type
                    and not g.revoked
                    and self.contains(g.scope_path, scope_path)):
                return g
        return None
