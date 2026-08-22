"""Durable revocation of an execution identity (S7-D5, I-111).

WHY THIS EXISTS. `ContextService` already tracks revoked execution identities
-- in a set, in memory. That is enough to fail an in-flight token closed at its
next enforcement point, which is what `I-74` needs. It is NOT enough for
`S7-D5`, which says retrieval must surface whether the authority that created a
stored item was later revoked: the set empties on restart, so every revoked
authority would read as clean the next morning, and every item it wrote would
silently become usable in model context again.

So the durable record is the authority, and the in-memory set is a cache of it.

A NEGATIVE REGISTRY. Presence means revoked. Absence means not-revoked ONLY
when the lookup was complete and authorized for that identity; where
completeness cannot be established the reader withholds the item instead of
concluding anything (`conversation.ConversationService._establish`). This class
owns the writing half of that; it deliberately owns none of the reading.

SCOPED, LIKE EVERYTHING ELSE. Revoking is an authorized act in a scope: it goes
through the caller's own token and the Data-Access Boundary, so RLS decides
where the record lands and who can later see it. There is no privileged
connection here, no cross-scope write, and no new authorization path -- which is
why a revocation cannot be recorded for a scope the caller cannot already reach.

NOT ITEM LINEAGE. A revocation outlives the items its authority created. ADR
0013's cascade deletes an item and what derives from it; an authority's
revocation derives from nothing and is not deleted with them. Deleting every
item an authority wrote must never make that authority read as un-revoked, and
`nova_app` holds no DELETE on this table precisely so that "the application
never issues DELETE" is not the only thing standing in the way.
"""

from __future__ import annotations

from ..core.types import ContextToken
from .boundary import DataAccessBoundary


class RevocationRegistry:
    """Records revoked execution identities durably, through the boundary."""

    def __init__(self, boundary: DataAccessBoundary, context=None):
        self._boundary = boundary
        # Optional: the sole issuer, so the in-memory cache it consults for
        # in-flight tokens agrees with what was just made durable. The registry
        # is authoritative either way -- this only stops the two disagreeing
        # inside one process.
        self._context = context

    def revoke(self, token: ContextToken, execution_identity: str,
               revoked_by: str) -> None:
        """Record that `execution_identity` is revoked, in the token's scope.

        Idempotent: revoking twice is one row, and the FIRST revocation time is
        kept. Moving the timestamp forward on a re-revoke would let a later
        write quietly narrow the window in which an authority is considered
        revoked, which is a downgrade dressed as a no-op.
        """
        with self._boundary.open(token) as ch:
            ch.execute(
                "INSERT INTO authority_revocation"
                " (execution_identity, scope_path, revoked_by)"
                " VALUES (%s,%s,%s)"
                " ON CONFLICT (execution_identity) DO NOTHING",
                (execution_identity, ch.scope_path, revoked_by))
        if self._context is not None:
            self._context.revoke(execution_identity)

    def is_revoked(self, token: ContextToken, execution_identity: str) -> bool:
        """Presence check, through the same bound channel.

        Callers must not read a `False` here as "established not revoked"
        unless they have separately established that a record for this identity
        WOULD be visible from this scope. That judgement belongs to the reader
        that knows the item, not to this method -- see `_establish`.
        """
        with self._boundary.open(token) as ch:
            return bool(ch.fetch(
                "SELECT 1 FROM authority_revocation WHERE execution_identity = %s",
                (execution_identity,)))
