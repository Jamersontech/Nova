"""Delegation records — AG-6, and the four rules AG-7..AG-10.

AGENT_GOVERNANCE.md section 3.1 gives the record; section 3.2 the rules.
I-107: delegation is strictly narrowing, acyclic, explicitly re-delegable,
and cannot outlive its delegator.

The record is a VALUE OBJECT. It is produced only by the Context service
(AG-1/AG-2) — nothing in agent/ or tools/ constructs one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .types import Denied, Risk


@dataclass(frozen=True)
class Delegation:
    """AG-6. Every field is authority-bearing except `purpose`."""
    delegator: str                      # granting execution identity
    delegate: str                       # receiving agent
    scope_path: str                     # subset of delegator's
    rights: frozenset[str]              # subset of delegator's
    tools: frozenset[str]               # subset of delegator's
    risk_ceiling: Risk                  # <= delegator's
    expires_at: float                   # strictly earlier than delegator's
    may_redelegate: bool                # explicit, DEFAULT FALSE (AG-9)
    ancestry: tuple[str, ...]           # chain of delegators above it (AG-8)
    purpose: str = ""

    def strictly_narrower_than(self, parent_scope: str, parent_rights: frozenset[str],
                               parent_tools: frozenset[str], parent_ceiling: Risk,
                               parent_expiry: float) -> bool:
        """AG-7. Narrower in at LEAST ONE authority dimension -- scope, rights,
        tools or risk ceiling -- AND strictly earlier expiry.

        A delegation identical in every dimension is refused. This is what
        bounds depth, on a finite authority lattice, which is why no numeric
        depth limit exists.
        """
        if self.expires_at >= parent_expiry:
            return False
        narrower_scope = (self.scope_path != parent_scope
                          and self.scope_path.startswith(parent_scope + "/"))
        narrower_rights = self.rights < parent_rights
        narrower_tools = self.tools < parent_tools
        narrower_ceiling = self.risk_ceiling < parent_ceiling
        return narrower_scope or narrower_rights or narrower_tools or narrower_ceiling


def check_within_parent(d: Delegation, parent_scope: str, parent_rights: frozenset[str],
                        parent_tools: frozenset[str], parent_ceiling: Risk,
                        parent_expiry: float, parent_may_redelegate: bool,
                        parent_ancestry: tuple[str, ...]) -> None:
    """AG-3 applied to a delegation request. Refusal is TOTAL and fail-closed
    (AG-4): on any mismatch no token is issued, nothing is trimmed to fit.
    """
    # -- containment: every dimension must be a subset / <= -----------------
    if not (d.scope_path == parent_scope or d.scope_path.startswith(parent_scope + "/")):
        raise Denied("delegation.scope", "delegated scope not within delegator's",
                     "I-107", True)
    if not d.rights <= parent_rights:
        raise Denied("delegation.rights", "delegated rights exceed delegator's",
                     "I-107", True)
    if not d.tools <= parent_tools:
        raise Denied("delegation.tools", "delegated tools exceed delegator's",
                     "I-107", True)
    if d.risk_ceiling > parent_ceiling:
        raise Denied("delegation.ceiling", "delegated ceiling exceeds delegator's",
                     "I-107", True)

    # -- AG-9: re-delegation is explicit, default false ---------------------
    # Checked before AG-7 because a delegate with may_redelegate=False may not
    # delegate AT ALL, however narrow the request.
    if parent_ancestry and not parent_may_redelegate:
        raise Denied("delegation.redelegate",
                     "delegator holds may_redelegate=false", "I-107", True)
    if d.may_redelegate and not parent_may_redelegate and parent_ancestry:
        raise Denied("delegation.redelegate",
                     "cannot grant may_redelegate it does not hold", "I-107", True)

    # -- AG-8: no ancestry cycles ------------------------------------------
    if d.delegate in parent_ancestry or d.delegate == d.delegator:
        raise Denied("delegation.cycle", f"{d.delegate} already in ancestry",
                     "I-107", True)

    # -- AG-7: strict narrowing --------------------------------------------
    if not d.strictly_narrower_than(parent_scope, parent_rights, parent_tools,
                                    parent_ceiling, parent_expiry):
        raise Denied("delegation.narrowing",
                     "delegation is not strictly narrower, or does not expire earlier",
                     "I-107", True)
