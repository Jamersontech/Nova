"""What needs James's attention, across the scopes he is authorized to see.

NOVA's first cross-scope capability. Cross-scope is the highest-risk area in
the model -- CROSS_SCOPE_DATA_RULES.md opens by saying every mechanism must be
examined with one question: *could this become a side channel from one scope
into another?* -- so this module does the one thing the accepted architecture
already prescribes, and nothing more.

THE SHAPE, WHICH IS NOT NEW
---------------------------
`I-86`: *"No access channel is bound to more than one scope... Cross-scope work
uses serial single-scope channels, aggregated above the executions."*
CROSS_SCOPE_DATA_RULES §2, for aggregation: *"Decompose per scope; aggregate
above; result is ephemeral."*

So, per authorized scope, IN TURN:

    grant check -> Context Token -> Data Access PEP -> ONE bound channel
                -> read -> audit -> channel fully closed -> next scope

and only then, above all of them, an in-memory compose. There is no query that
spans scopes, no privileged reader, no new table, and no moment at which two
bound channels exist. The reads are serial by construction: each is a `with`
block that commits and returns its connection to the pool before the next
begins.

WHY THERE IS NO SCOPE PARAMETER
-------------------------------
`gather()` takes an identity, not a scope. The set of scopes it visits is
derived from the tree and filtered by grant, so there is no input through
which a caller could name a scope, widen the set, or ask for one it does not
hold. A hostile path cannot expand a result set it cannot address.

WHY ACTIVITY IS ABSENT, DELIBERATELY
------------------------------------
`I-67`/`I-89`: reviewing audit records across more than one scope requires
step-up authentication, because it aggregates the cross-client audit corpus.
Step-up does not exist yet (ADR 0046, limitation 3). Audit records are
therefore NOT read here -- approvals and tasks are ordinary scoped data and
carry no such rule. The cap is stated on the page rather than silently
applied.

WHY THE MODEL NEVER SEES THIS
-----------------------------
`I-95`: no model request carries content from more than one scope. This
aggregate is two or more scopes in one buffer by definition, so it is a
server-rendered page and never a conversation answer. Nothing in this module
touches the gateway.

WHAT IS NEVER PERSISTED
-----------------------
The aggregate. CROSS_SCOPE_DATA_RULES §3 prohibits writing client-identifying
content above the client scope, and §2 requires the result to be ephemeral.
It is computed per request, rendered, and discarded -- there is no table, no
cache, and no write path out of this module.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
from typing import Optional

from ..core.context_service import ContextService
from ..core.scope_tree import ScopeTree
from ..core.types import Denied, Risk
from .boundary import DataAccessBoundary

# A task with no date is not time-pressing and is not attention. Kept out so
# the page answers one question rather than becoming a task list.
DUE_SOON_DAYS = 7


@dataclasses.dataclass(frozen=True)
class PendingApproval:
    scope_path: str
    approval_id: str
    action_text: str
    why_text: str
    risk_class: str


@dataclasses.dataclass(frozen=True)
class DueTask:
    scope_path: str
    task_ref: str
    title: str
    due_on: datetime.date
    overdue: bool


@dataclasses.dataclass(frozen=True)
class Attention:
    """The composed answer. Ephemeral: built per request, never stored."""
    approvals: tuple[PendingApproval, ...]
    overdue: tuple[DueTask, ...]
    due_soon: tuple[DueTask, ...]
    scopes_read: tuple[str, ...]

    @property
    def empty(self) -> bool:
        return not (self.approvals or self.overdue or self.due_soon)


class AttentionService:
    """Holds no authority. Every scope it reports on was independently
    authorized by the Context service and the PDP, and independently bounded
    by the Data-Access Boundary and RLS."""

    def __init__(self, tree: ScopeTree, context: ContextService, pdp,
                 boundary: DataAccessBoundary):
        self._tree = tree
        self._context = context
        self._pdp = pdp
        self._boundary = boundary
        # Test instrumentation only: how many separate bound channels the last
        # gather opened. Nothing reads it in production.
        self.channels_opened = 0

    def gather(self, identity: str, actor: str,
               today: Optional[datetime.date] = None) -> Attention:
        """One authorized read per scope, in turn, then compose above them."""
        today = today or datetime.date.today()
        horizon = today + datetime.timedelta(days=DUE_SOON_DAYS)

        approvals: list[PendingApproval] = []
        overdue: list[DueTask] = []
        due_soon: list[DueTask] = []
        visited: list[str] = []
        self.channels_opened = 0

        for scope_path in self._tree.paths():
            # 1. Does James hold read access here? This is a CHEAP SKIP, not
            #    the enforcement: removing it changes no result, because
            #    issuance below refuses an ungranted scope on the same rule
            #    (I-14). It exists so the common case does not mint a token
            #    and take a denial for every scope James cannot see.
            if self._tree.find_grant(identity, "read", "*", scope_path) is None:
                continue
            try:
                # 2-3. Issuance enforces grants and activation (I-14, I-80);
                #      the Data Access PEP then decides the read (I-77,
                #      ADR 0045) -- including explicit denials, which issuance
                #      does not check.
                token = self._context.issue_root(
                    identity=identity, actor=actor, scope_path=scope_path,
                    rights=frozenset({"read"}), ceiling=Risk.READ, ttl=60)
                self._pdp.authorize_data_read(token, scope_path)
            except (Denied, KeyError):
                # A scope that refuses is skipped, not reported and not
                # distinguished -- the page must not become an oracle for
                # which scopes exist but are denied.
                continue

            try:
                rows_a, rows_t = self._read_one_scope(token, scope_path, horizon)
            except Denied:
                continue

            visited.append(scope_path)
            for approval_id, action_text, why_text, risk_class in rows_a:
                approvals.append(PendingApproval(scope_path, approval_id,
                                                 action_text, why_text, risk_class))
            for task_ref, title, due_on in rows_t:
                task = DueTask(scope_path, task_ref, title, due_on,
                               overdue=due_on < today)
                (overdue if task.overdue else due_soon).append(task)

        # 8. Aggregate ABOVE the executions, in memory, from results that were
        #    each already authorized. Nothing here re-decides anything.
        overdue.sort(key=lambda t: (t.due_on, t.scope_path, t.task_ref))
        due_soon.sort(key=lambda t: (t.due_on, t.scope_path, t.task_ref))
        approvals.sort(key=lambda a: (a.scope_path, a.approval_id))
        return Attention(tuple(approvals), tuple(overdue), tuple(due_soon),
                         tuple(visited))

    def _read_one_scope(self, token, scope_path: str, horizon: datetime.date):
        """4-6. ONE channel, one scope, opened and fully closed here.

        The `scope_path = %s` predicate is NOT the isolation control -- RLS is,
        and it is still what makes another scope's rows unreachable. It is the
        DECOMPOSITION rule: a token covers its descendants, so without it a
        parent's read would also return its children's rows and the same task
        would be counted under two scopes. I-86 requires one scope per
        execution, and this is that requirement expressed in the query.
        """
        with self._boundary.open(token) as ch:
            self.channels_opened += 1
            rows_a = ch.fetch(
                "SELECT approval_id, action_text, why_text, risk_class"
                " FROM approval WHERE status = 'pending' AND scope_path = %s"
                " ORDER BY created_at", (scope_path,))
            rows_t = ch.fetch(
                "SELECT task_ref, title, due_on FROM task"
                " WHERE done_at IS NULL AND scope_path = %s"
                "   AND due_on IS NOT NULL AND due_on <= %s"
                " ORDER BY due_on, task_ref", (scope_path, horizon))
            # I-49: recorded per scope touched. A cross-scope review leaves a
            # record in each scope it read, not one record above them.
            event_identity = hashlib.sha256(
                f"attention_read:{token.trace_id}:{scope_path}".encode()
            ).hexdigest()[:32]
            ch.execute(
                "INSERT INTO audit_record"
                " (event_identity, writer, category, scope_path, trace_id, actor_ref, detail)"
                " VALUES (%s,'W-1','data.read',%s,%s,%s,%s)"
                " ON CONFLICT (event_identity) DO NOTHING",
                (event_identity, scope_path, token.trace_id, token.actor,
                 f"attention approvals={len(rows_a)} tasks={len(rows_t)}"))
        # The channel is closed and its connection returned before the caller's
        # loop reaches the next scope. Serial by construction (I-86).
        return rows_a, rows_t
