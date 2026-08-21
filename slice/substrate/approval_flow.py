"""The approval experience: a human reviews a consequence-producing action.

This replaces the last stand-in between NOVA's machinery and a person using
it. Before this, `ApprovalStore.james_approves(plan_identity)` was a method a
test called. Now James sees what the action will do and decides.

    propose  -> a pending approval, stating the five things
                USER_INTERFACE_ARCHITECTURE.md section 6 requires
    review   -> a server-rendered page
    decide   -> approve or deny, recorded with who and when
    execute  -> on approve, through the EXISTING WritePath, which re-runs
                authorize_plan in full

NOTHING HERE AUTHORIZES ANYTHING. The approval is an input to the PDP's step
9, not a substitute for it. On approval the action still goes through
authorize_plan's ten steps, the ToolPEP, the broker and the Data-Access
Boundary, and still lands under RLS WITH CHECK. If the PDP is unavailable, an
approved action fails closed exactly as an unapproved one does.

THE BINDING (I-109, I-112)
--------------------------
A pending approval stores the plan's deterministic identity AND the arguments
that produced it. At execution the plan is RECONSTRUCTED from those arguments
and its identity re-derived: if it does not match what James saw, the approval
does not apply. So an approval cannot be pointed at a different action, and a
stored request cannot be edited into authorizing something else.

Approvals live in the `approval` table, which carries RLS like every other
scoped table -- so an approval is reachable only from a channel bound to its
own scope. That is free isolation, inherited rather than designed.

SINGLE USE (I-09)
-----------------
An approval is James's act for ONE execution. It is spent when it authorizes
one, and `approval.consumed_at` records that durably. The claim is a single
`UPDATE ... WHERE consumed_at IS NULL ... RETURNING`, so concurrency is
PostgreSQL's problem rather than ours: exactly one caller updates a row, and
a loser updates none and is denied before anything executes.

Spending happens at USE, not at completion. A failed execution therefore
leaves the approval spent and requires a fresh decision -- the fail-closed
direction, and the reason this needs none of Phase 2's recovery machinery.
"""

from __future__ import annotations

import dataclasses
import json
import secrets
from typing import Any, Optional

from ..core.types import ContextToken, Denied, Outcome, Risk
from .boundary import DataAccessBoundary
from .write_path import TOOL, WritePath

PENDING, APPROVED, DENIED = "pending", "approved", "denied"


@dataclasses.dataclass(frozen=True)
class ApprovalRequest:
    """What James is shown. The five section-6 fields, plus what binds it."""
    approval_id: str
    scope_path: str
    plan_identity: str
    risk_class: str
    status: str
    action_text: str
    why_text: str
    cost_text: str
    if_wrong_text: str
    item_ref: str
    body: str
    requested_by: str
    decided_by: Optional[str] = None
    tool_name: str = TOOL
    arguments: Optional[dict] = None

    def plan_arguments(self) -> dict:
        """The arguments the plan is rebuilt from. `write_item` reads the
        original two columns -- they are its authoritative storage and were
        so before any other tool existed -- everything else reads
        `arguments`. Both are compared against the stored plan identity, so
        tampering with either is caught."""
        if self.tool_name == TOOL:
            return {"item_ref": self.item_ref, "body": self.body}
        return dict(self.arguments or {})


class ApprovalService:
    """Proposes, presents and records decisions on consequence-producing work."""

    def __init__(self, boundary: DataAccessBoundary, writes: WritePath):
        self._boundary = boundary
        self._writes = writes

    # -- propose -------------------------------------------------------------

    def propose(self, token: ContextToken, scope_path: str,
                item_ref: str, body: str) -> str:
        """Record a pending approval for one exact write. Writes nothing else."""
        return self.propose_action(
            token, scope_path, TOOL, {"item_ref": item_ref, "body": body},
            action_text=f"Write item \u201c{item_ref}\u201d in this scope.",
            if_wrong_text="The item holds the wrong content until it is corrected.")

    def propose_action(self, token: ContextToken, scope_path: str,
                       tool_name: str, arguments: dict[str, Any],
                       action_text: str, if_wrong_text: str,
                       cost_text: str = "One row written or updated. No spend.",
                       why_text: str = ("Writing changes stored data. Reading it "
                                        "was autonomous; changing it is not.")) -> str:
        """Record a pending approval for one exact action, of any tool."""
        plan = self._writes.plan_for_action(scope_path, tool_name, arguments)
        approval_id = "ap-" + secrets.token_hex(8)

        with self._boundary.open(token) as ch:
            ch.execute(
                "INSERT INTO approval (approval_id, actor_ref, scope_path,"
                " binding_identity, risk_class, plan_identity, status,"
                " action_text, why_text, cost_text, if_wrong_text, item_ref, body,"
                " tool_name, arguments)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (approval_id, token.actor, ch.scope_path,
                 self._writes.binding_for(scope_path, tool_name).identity(),
                 plan.declared_risk.name, plan.identity(), PENDING,
                 # The five things section 6 requires, in plain language.
                 action_text, why_text, cost_text, if_wrong_text,
                 arguments.get("item_ref"), arguments.get("body"),
                 tool_name, json.dumps(arguments)),
            )
        return approval_id

    # -- read ----------------------------------------------------------------

    _COLUMNS = ("approval_id, scope_path, plan_identity, risk_class, status,"
                " action_text, why_text, cost_text, if_wrong_text, item_ref, body,"
                " actor_ref, decided_by, tool_name, arguments")

    def _row_to_request(self, row) -> ApprovalRequest:
        return ApprovalRequest(*row)

    def pending(self, token: ContextToken) -> list[ApprovalRequest]:
        """Pending approvals in the token's scope. No cross-scope aggregation:
        I-86 forbids joining across scopes at the storage layer."""
        with self._boundary.open(token) as ch:
            rows = ch.fetch(
                f"SELECT {self._COLUMNS} FROM approval WHERE status = %s"
                " ORDER BY created_at", (PENDING,))
        return [self._row_to_request(r) for r in rows]

    def get(self, token: ContextToken, approval_id: str) -> Optional[ApprovalRequest]:
        with self._boundary.open(token) as ch:
            rows = ch.fetch(
                f"SELECT {self._COLUMNS} FROM approval WHERE approval_id = %s",
                (approval_id,))
        return self._row_to_request(rows[0]) if rows else None

    # -- decide --------------------------------------------------------------

    def decide(self, token: ContextToken, approval_id: str, approve: bool,
               decided_by: str) -> tuple[str, Optional[Outcome]]:
        """Record James's decision, and on approval execute the action.

        Returns (status, outcome). The outcome is None for a denial -- a
        denied approval produces no side effect at all.
        """
        request = self.get(token, approval_id)
        if request is None:
            # Out of scope or nonexistent are the same answer: RLS already
            # made the row unreachable, and distinguishing them would leak.
            raise Denied("approval.get", "no such approval", "I-03", True)
        if request.status != PENDING:
            raise Denied("approval.decide", "approval already decided", "I-09", False)

        if not approve:
            with self._boundary.open(token) as ch:
                ch.execute(
                    "UPDATE approval SET status=%s, decided_at=now(), decided_by=%s"
                    " WHERE approval_id=%s", (DENIED, decided_by, approval_id))
            return DENIED, None

        # I-112 / I-109: reconstruct the plan from the stored arguments and
        # require the identity James saw. A request edited after the fact --
        # or pointed at another action -- no longer matches and cannot execute.
        plan = self._writes.plan_for_action(request.scope_path, request.tool_name,
                                            request.plan_arguments())
        if plan.identity() != request.plan_identity:
            raise Denied("approval.decide",
                         "plan identity differs from the approved plan", "I-112", True)

        # SINGLE USE (I-09), claimed atomically. The decision and the spending
        # of it are ONE statement: `consumed_at IS NULL` in the predicate means
        # PostgreSQL admits exactly one winner, so two concurrent decisions on
        # the same approval cannot both proceed to execute. RETURNING is how we
        # learn whether we were the winner -- a second caller updates zero rows
        # and is denied here, before anything executes.
        with self._boundary.open(token) as ch:
            claimed = ch.fetch(
                "UPDATE approval SET status=%s, decided_at=now(), decided_by=%s,"
                " consumed_at=now()"
                " WHERE approval_id=%s AND status=%s AND consumed_at IS NULL"
                " RETURNING approval_id",
                (APPROVED, decided_by, approval_id, PENDING))
        if not claimed:
            raise Denied("approval.decide",
                         "approval already spent", "I-09", True)

        # I-09's act, recorded. The PDP still decides: this is an INPUT to
        # step 9, and execute() re-runs the full ten steps below it.
        self._writes.approvals.james_approves(plan.identity())
        outcome = self._writes.execute_action(token, request.scope_path,
                                              request.tool_name,
                                              request.plan_arguments())
        return APPROVED, outcome
