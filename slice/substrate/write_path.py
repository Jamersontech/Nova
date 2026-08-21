"""The first authorized WRITE: plan -> approval -> PEP -> boundary -> WITH CHECK.

A write is a consequence-producing tool action, so unlike the read path
(ADR 0045) nothing here is a new decision sequence -- it is the EXISTING
tool-action architecture, driven for the first time against the real
datastore:

    proposed write
      -> Plan (I-112 deterministic identity)
      -> PolicyDecisionPoint.authorize_plan   -- the full ten steps;
         step 9 DENIES an EXECUTE-class plan with no approval (I-09)
      -> James's approval, held server-side, bound to the plan identity
      -> ToolPEP.invoke                       -- I-100 envelope, I-114(b)
         binding re-check, I-109 re-check, broker injection
      -> transport = the Postgres integration: a scope-bound channel from
         the Data-Access Boundary; INSERT under RLS WITH CHECK
      -> audit row in the same transaction    (I-93, W-1)

WHY THE TRANSPORT GOES THROUGH THE BOUNDARY
-------------------------------------------
The tool's side effect lands in NOVA's own datastore, so the integration is
subject to the same physical isolation as every other access: the channel is
bound to the token's scope and WITH CHECK rejects any row outside it -- even
if every application-side control above this line were bypassed. The hostile
tests drive exactly that bypass.

WHAT IS A STAND-IN
------------------
Approval CAPTURE. `ApprovalStore.james_approves` records James's act; the
surface that presents and captures approvals is Section 26's scope. I-09 is
preserved: nothing in this module can create an approval except that method,
and the PDP denies without one. The stand-in is one method, replaced when the
approval surface exists.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

from ..core.broker import CredentialBroker
from ..core.policy import PolicyDecisionPoint
from ..core.types import (Approval, ArgumentEnvelope, ContextToken, Denied,
                          ExecutionBinding, Outcome, Plan, PlanStep, Risk, Taint)  # noqa: F401 (Denied used by add_scope guard)
from ..tools.pep import ToolPEP
from ..tools.registry import ToolRegistry, ToolDefinition, CONSEQUENCE, EXPRESSIVE
from .boundary import DataAccessBoundary

TOOL = "write_item"
TOOL_VERSION = "1.0.0"
ADD_TASK = "add_task"
COMPLETE_TASK = "complete_task"
ADD_SCOPE = "add_scope"

# One lowercase path segment. The conversation marker enforces this before a
# proposal exists; the transport enforces it AGAIN because the tool can be
# driven without the conversation, and "the marker was strict" is not a
# property of this layer.
_SCOPE_NAME = __import__("re").compile(r"[a-z0-9][a-z0-9_.-]{0,63}$")


def write_item_tool() -> ToolDefinition:
    """The tool declaration, complete per ADR 0036 (totality)."""
    return ToolDefinition(
        name=TOOL, version=TOOL_VERSION, purpose="Create or update one scoped item",
        input_schema={"item_ref": "str", "body": "str"},
        output_schema={"status": "str"},
        required_rights=frozenset({"write"}),
        auth_requirements="datastore",
        risk_class=Risk.EXECUTE,
        context_requirements=frozenset({"client"}),
        error_behaviour="typed", audit_behaviour="reference-only",
        # ON CONFLICT upsert by (scope_path, item_ref): the DEDUPLICATION is
        # enforced by the provider (PostgreSQL's unique constraint), which is
        # what S11-D2 requires before declaring idempotency.
        idempotent=True, cost_profile=1,
        consequence_determining={
            "item_ref": CONSEQUENCE,   # addresses the record
            "body": EXPRESSIVE,        # prose -- MT-5, same ruling as harness
        },
    )


def add_task_tool() -> ToolDefinition:
    """Record something that needs doing, in this scope."""
    return ToolDefinition(
        name=ADD_TASK, version=TOOL_VERSION,
        purpose="Add or update one task in this scope",
        input_schema={"task_ref": "str", "title": "str", "due_on": "str"},
        output_schema={"status": "str"},
        required_rights=frozenset({"write"}),
        auth_requirements="datastore",
        risk_class=Risk.EXECUTE,
        context_requirements=frozenset({"client"}),
        error_behaviour="typed", audit_behaviour="reference-only",
        idempotent=True, cost_profile=1,
        consequence_determining={
            "task_ref": CONSEQUENCE,   # addresses the record
            # A DATE IS CONSEQUENCE-DETERMINING, not expressive. "Friday" and
            # "next month" are different commitments, and ADR 0036 rule 2 makes
            # consequence the default anyway -- only prose earns expressive.
            "due_on": CONSEQUENCE,
            "title": EXPRESSIVE,       # prose -- MT-5, same ruling as write_item
        },
    )


def complete_task_tool() -> ToolDefinition:
    """Mark one task done. Consequence-producing: it changes stored state, so
    it is EXECUTE-class and needs James's approval like any other write. That
    is the architecture working, not an oversight -- NOVA does not get to
    quietly close James's commitments."""
    return ToolDefinition(
        name=COMPLETE_TASK, version=TOOL_VERSION,
        purpose="Mark one task in this scope as done",
        input_schema={"task_ref": "str"},
        output_schema={"status": "str"},
        required_rights=frozenset({"write"}),
        auth_requirements="datastore",
        risk_class=Risk.EXECUTE,
        context_requirements=frozenset({"client"}),
        error_behaviour="typed", audit_behaviour="reference-only",
        # The UPDATE is conditional on `done_at IS NULL`, so a retry is a
        # no-op at the provider rather than a second completion.
        idempotent=True, cost_profile=1,
        consequence_determining={"task_ref": CONSEQUENCE},
    )


def add_scope_tool() -> ToolDefinition:
    """Create one child scope under the scope the plan names.

    The PARENT is the plan's scope_path -- the same slot every other tool
    uses -- so the approval binds it through I-109/I-112 like any other
    resource, and the channel the write lands through is bound to it. The
    child is parent + "/" + scope_name, computed in the transport from the
    CHANNEL's scope, never from a payload-supplied path: WITH CHECK on the
    `scope` table is what refuses a child anywhere the binding does not
    cover, proven against the engine before this tool was written.

    NO GRANT IS CREATED OR TOUCHED. James's existing grant at an ancestor
    covers the new descendant by containment (find_grant/contains), verified
    empirically. I-10 is untouched: this tool has no path to the `grant`
    table at all.
    """
    return ToolDefinition(
        name=ADD_SCOPE, version=TOOL_VERSION,
        purpose="Create one empty child scope under this scope",
        input_schema={"scope_name": "str", "kind": "str"},
        output_schema={"status": "str"},
        required_rights=frozenset({"write"}),
        auth_requirements="datastore",
        risk_class=Risk.EXECUTE,
        context_requirements=frozenset({"client"}),
        error_behaviour="typed", audit_behaviour="reference-only",
        # UNIQUE (scope_path) + ON CONFLICT DO NOTHING: the provider enforces
        # that a retry is one scope, which is what idempotent=True claims.
        idempotent=True, cost_profile=1,
        consequence_determining={
            # BOTH are consequence-determining: the name addresses what will
            # exist, and the kind is recorded structure. The envelope pins
            # each to the exact approved value (I-100).
            "scope_name": CONSEQUENCE,
            "kind": CONSEQUENCE,
        },
    )


ALL_TOOLS = (write_item_tool, add_task_tool, complete_task_tool, add_scope_tool)


class ApprovalStore:
    """Approvals by plan identity. I-09: only James's act creates one.

    SINGLE USE. An approval authorizes ONE execution. Once it has been spent
    -- `consume()` -- `for_plan` refuses it forever, so a later plan that
    happens to hash the same cannot ride it.

    Why this exists in memory at all when the `approval` table is durable: a
    plan identity is deterministic over (scope, tool, arguments), so the SAME
    identity is re-derived every time the same action is requested. Without
    the spent-set, an approval recorded here stayed valid for the life of the
    process, and any path reaching `execute_action` with matching arguments --
    including the direct write route in `seam.py` -- found it and satisfied
    step 9 with no new human act. The durable `approval.consumed_at` column is
    the authority; this is the same rule enforced at the object the PDP
    actually reads, so the two cannot disagree within a process.

    What this is NOT: a ban on ever approving the same action twice. James may
    legitimately decide to write the same item again next week. That arrives as
    a NEW approval row, atomically claimed against `consumed_at`, and
    re-arms the identity here. The distinction between a new decision and a
    replay is the durable row, not the identity -- which is exactly why the
    database is the authority and this is only its in-process shadow.
    """

    def __init__(self) -> None:
        self._by_plan: dict[str, Approval] = {}

    def james_approves(self, plan_identity: str) -> Approval:
        """James's approval of ONE plan -- not standing, names no source.
        Capture surface is Section 26's scope; this records the act.

        Re-arms an identity previously spent: a fresh decision is a fresh
        approval. Nothing here is automatic -- reaching this method at all
        required a human act (I-09).
        """
        a = Approval(approval_id=f"appr-{plan_identity[:12]}", standing=False)
        self._by_plan[plan_identity] = a
        return a

    def for_plan(self, plan_identity: str) -> Optional[Approval]:
        """Look WITHOUT spending. Not for the execution path -- reading and
        then spending is two steps, and concurrent callers can both pass the
        read before either reaches the spend. Use `take`."""
        return self._by_plan.get(plan_identity)

    def take(self, plan_identity: str) -> Optional[Approval]:
        """Spend the approval and return it, in ONE indivisible step.

        `dict.pop` is atomic, so of N concurrent callers exactly one receives
        the approval and the rest receive None -- and None is denied by step 9.
        This is the whole of the in-process single-use rule: a separate
        look-then-spend pair was measurably racy, returning four executions
        from one approval when the window between the two was widened.

        Spent by USE, not by completion. A failed execution leaves the
        approval spent and requires a fresh decision: the fail-closed
        direction (I-09), and why this needs none of Phase 2's recovery
        machinery.
        """
        return self._by_plan.pop(plan_identity, None)


class PostgresItemIntegration:
    """The integration: writes land through the Data-Access Boundary.

    The injected secret arrives at the call boundary per the broker protocol
    and goes no further; the datastore credential itself is held by the
    boundary's pool, never by this class and never by the tool.
    """

    def __init__(self, boundary: DataAccessBoundary):
        self._boundary = boundary
        self.side_effects = 0
        # Post-commit hook for ADD_SCOPE only: the composition root uses it to
        # teach the in-process tree about the new scope and register its
        # datastore credential binding. NOT a general hot-reload system, and
        # None everywhere that does not need it.
        self.on_scope_created = None

    def transport_for(self, token: ContextToken, tool_name: str = TOOL):
        """The transport for one tool. Every branch below writes through the
        SAME scope-bound channel and names `ch.scope_path` -- never a scope
        from the payload -- so WITH CHECK refuses anything else regardless of
        which tool ran."""

        def transport(payload: dict[str, Any], secret: str) -> Outcome:
            with self._boundary.open(token) as ch:
                if tool_name == ADD_TASK:
                    ref = payload["task_ref"]
                    ch.execute(
                        "INSERT INTO task (task_ref, scope_path, actor_ref, title, due_on)"
                        " VALUES (%s,%s,%s,%s, NULLIF(%s,'')::date)"
                        " ON CONFLICT (scope_path, task_ref)"
                        " DO UPDATE SET title = EXCLUDED.title, due_on = EXCLUDED.due_on",
                        (ref, ch.scope_path, token.actor, payload["title"],
                         payload.get("due_on", "")))
                    detail, said = f"task_ref={ref}", f"added task {ref}"
                elif tool_name == ADD_SCOPE:
                    ref = payload["scope_name"]
                    kind = payload.get("kind", "place")
                    if not _SCOPE_NAME.fullmatch(ref):
                        raise Denied("tool.add_scope",
                                     "scope name is not one lowercase path segment",
                                     "I-100", True)
                    # The child hangs off the CHANNEL's scope. A payload cannot
                    # name a parent, and WITH CHECK refuses anything the
                    # binding does not cover -- the engine is the authority.
                    new_path = f"{ch.scope_path}/{ref}"
                    ch.execute(
                        "INSERT INTO scope (scope_path, kind, parent_path)"
                        " VALUES (%s,%s,%s)"
                        " ON CONFLICT (scope_path) DO NOTHING",
                        (new_path, kind, ch.scope_path))
                    detail, said = f"scope={new_path}", f"created {new_path}"
                elif tool_name == COMPLETE_TASK:
                    ref = payload["task_ref"]
                    # Conditional on done_at IS NULL: a retry is a no-op at the
                    # provider, which is what `idempotent=True` claims.
                    ch.execute(
                        "UPDATE task SET done_at = now()"
                        " WHERE task_ref = %s AND done_at IS NULL", (ref,))
                    detail, said = f"task_ref={ref}", f"completed task {ref}"
                else:
                    ref = payload["item_ref"]
                    # The row's scope is the CHANNEL's scope -- the transport
                    # cannot name another one, and WITH CHECK would refuse it.
                    ch.execute(
                        "INSERT INTO item (item_ref, scope_path, body)"
                        " VALUES (%s, %s, %s)"
                        " ON CONFLICT (scope_path, item_ref)"
                        " DO UPDATE SET body = EXCLUDED.body",
                        (ref, ch.scope_path, payload["body"]))
                    detail, said = f"item_ref={ref}", f"wrote {ref}"

                event_identity = hashlib.sha256(
                    f"data_write:{token.trace_id}:{ch.scope_path}:{tool_name}:{ref}".encode()
                ).hexdigest()[:32]
                ch.execute(
                    "INSERT INTO audit_record"
                    " (event_identity, writer, category, scope_path, trace_id, actor_ref, detail)"
                    " VALUES (%s,'W-1','data.write',%s,%s,%s,%s)"
                    " ON CONFLICT (event_identity) DO NOTHING",
                    (event_identity, ch.scope_path, token.trace_id, token.actor,
                     f"{tool_name} {detail}"),
                )
            # The `with` block above has committed. Only now -- with the row
            # durable -- does the composition root learn about a new scope.
            if tool_name == ADD_SCOPE and self.on_scope_created is not None:
                self.on_scope_created(new_path, kind)
            self.side_effects += 1
            return Outcome("success_claimed", said, Taint.of("integration.supplied"))
        return transport


class WritePath:
    """Wires the EXISTING authorization machinery to the real datastore."""

    def __init__(self, pdp: PolicyDecisionPoint, registry: ToolRegistry,
                 pep: ToolPEP, broker: CredentialBroker,
                 integration: PostgresItemIntegration,
                 credential_binding_id: str):
        self._pdp = pdp
        self._registry = registry
        self._pep = pep
        self._integration = integration
        self._cred_id = credential_binding_id
        self.approvals = ApprovalStore()

    # -- the proposed execution, deterministic (I-112) ----------------------

    def plan_for_action(self, scope_path: str, tool_name: str,
                        arguments: dict[str, Any]) -> Plan:
        """I-112: deterministic identity over the tool AND its arguments, so
        two different tools -- or the same tool with different arguments --
        are two different plans and one approval never covers the other."""
        return Plan(
            steps=(PlanStep(action=tool_name, resource=scope_path,
                            tool_name=tool_name,
                            required_rights=frozenset({"write"}),
                            arguments=dict(arguments)),),
            required_rights=frozenset({"write"}),
            declared_risk=Risk.EXECUTE,
            scope_path=scope_path,
            taint=Taint.of("james.stated"),
            cost_estimate=1,
        )

    def plan_for(self, scope_path: str, item_ref: str, body: str) -> Plan:
        return self.plan_for_action(scope_path, TOOL,
                                    {"item_ref": item_ref, "body": body})

    def binding_for(self, scope_path: str, tool_name: str = TOOL) -> ExecutionBinding:
        """I-114: the concrete substrate, resolved before the decision. The
        tool is part of the binding identity, so an approval for one tool's
        binding does not cover another's."""
        return ExecutionBinding(
            tool_name=tool_name, tool_version=TOOL_VERSION,
            integration_id="int-postgres-items", provider="postgresql",
            account="nova_substrate", endpoint="local:5433", api_version="16",
            credential_binding_id=self._cred_id, scope_path=scope_path,
        )

    # -- the full authorized execution --------------------------------------

    def execute_action(self, token: ContextToken, scope_path: str,
                       tool_name: str, arguments: dict[str, Any]) -> Outcome:
        """Authorize, then execute. No database write occurs before
        authorize_plan has succeeded -- the transport is not even constructed
        until the PEP, and the PEP requires the authorization object."""
        plan = self.plan_for_action(scope_path, tool_name, arguments)
        binding = self.binding_for(scope_path, tool_name)

        # I-100: the envelope pins every CONSEQUENCE-DETERMINING argument to
        # the exact value authorized. Which arguments those are is READ FROM
        # THE TOOL'S OWN DECLARATION rather than listed here, so a new tool
        # cannot arrive with an under-specified envelope by omission.
        definition = self._registry.get(tool_name, TOOL_VERSION)
        envelope = ArgumentEnvelope(
            allowed_values={
                leaf: frozenset({str(arguments.get(leaf, ""))})
                for leaf in definition.leaves()
                if definition.is_consequence_determining(leaf)
            },
            magnitude_ceilings={},
        )
        # Taken, not read: the approval is spent in the same indivisible step
        # that obtains it, so no second caller -- concurrent or later -- can
        # obtain the same one. A replay of the identical plan gets None and is
        # denied by step 9 below, through the ordinary machinery with no
        # special case for it.
        approval = self.approvals.take(plan.identity())

        # The full ten steps. Step 9 denies EXECUTE with no approval (I-09).
        authorization = self._pdp.authorize_plan(
            token, plan, {tool_name: binding}, envelope,
            cost_ceiling=10, approval=approval,
        )

        return self._pep.invoke(
            token, plan, plan.steps[0], authorization,
            resolve_binding=lambda name, scope: self.binding_for(scope, name),
            transport=self._integration.transport_for(token, tool_name),
            tool_version=TOOL_VERSION,
            provider_enforces_dedup=True,
        )

    def execute(self, token: ContextToken, scope_path: str,
                item_ref: str, body: str) -> Outcome:
        return self.execute_action(token, scope_path, TOOL,
                                   {"item_ref": item_ref, "body": body})
