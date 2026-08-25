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
from dataclasses import dataclass
from typing import Any, Optional

from ..core.broker import CredentialBroker
from ..core.policy import PolicyDecisionPoint
from ..core.types import (Approval, ArgumentEnvelope, ContextToken, Denied,
                          ExecutionBinding, Outcome, Plan, PlanStep, Risk, Taint,
                          Trust)  # noqa: F401 (Denied used by add_scope guard)
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

# Which argument addresses the record each tool writes. The transport reads it
# to build the audit event identity; recovery reads it to REBUILD that identity
# from the stored arguments. One table, so the two cannot drift -- if they did,
# recovery would look for evidence under an identity nothing ever wrote and
# would conclude "did not execute" about an action that did.
REF_ARGUMENT = {TOOL: "item_ref", ADD_TASK: "task_ref",
                COMPLETE_TASK: "task_ref", ADD_SCOPE: "scope_name"}


def execution_event_identity(trace_id: str, scope_path: str,
                             tool_name: str, ref: str) -> str:
    """I-93's deterministic identity for one data write.

    THE definition, called by both the writer and the reader. `trace_id` is a
    uuid4 that exists only inside a ContextToken, which is why the approval
    row persists it: after a restart this is otherwise unrecomputable, and an
    identity that cannot be recomputed is evidence that cannot be found.
    """
    return hashlib.sha256(
        f"data_write:{trace_id}:{scope_path}:{tool_name}:{ref}".encode()
    ).hexdigest()[:32]


# --------------------------------------------------------------------------
# ADR 0048 -- content-visible approval
# --------------------------------------------------------------------------

# The provenance term an inspected-and-approved write ADDS. It already exists
# in PROVENANCE_DEFAULT_TRUST at HIGHEST and had no writer until now; this
# introduces no vocabulary.
APPROVED_PROVENANCE = "james.approved"

# What a write plan carries when nobody said where its content came from.
# DELIBERATELY NOT `james.stated`: an absent taint is unknown, and unknown must
# never read as "James said it". LOW and non-external, so it constrains without
# tripping I-40 on a source that does not exist.
UNKNOWN_ORIGIN = "model.generated"


@dataclass(frozen=True)
class ApprovalEvidence:
    """What makes a trust elevation ATTRIBUTABLE (ADR 0048, property 4).

    Assembled by `ApprovalService.decide` from the durable approval row, and
    required by `elevate()`. It is not optional decoration: without it there is
    no answer to "why is this row trusted?", and ADR 0048 says a row with no
    answer is not trusted.

    `content_leaves` is the set of EXPRESSIVE arguments the approval card
    rendered in full. It comes from `WritePath.content_leaves()` -- the SAME
    function the renderer calls -- so "was it shown?" is one computation with
    one answer rather than a flag the UI asserts about itself.
    """
    approval_id: str
    approved_by: str
    proposed_taint: Taint
    content_leaves: frozenset[str]


def elevate(taint: Taint, evidence: ApprovalEvidence) -> Taint:
    """ADR 0048's ONE elevation construction. One production call site.

    ADDITIVE, never a rewrite: `I-38` and `I-110` both hold that provenance is
    immutable and a promotion RECORDS a judgement rather than erasing origin.
    So `model.generated` survives -- an approved item stays distinguishable
    from something James typed himself -- and `james.approved` is added beside
    it.

    NOT `Taint.union`: union takes the LOWEST trust (`I-99`), so unioning
    HIGHEST into a set containing `model.generated` yields LOW. Elevation is
    therefore impossible through the ordinary combinator, which is `I-110`
    working as written -- raising trust is an explicit act, never a side
    effect of composition.

    CLASSIFICATION IS NOT TOUCHED. An approval is evidence about
    trustworthiness, not about sensitivity; `I-27`'s strictest-wins result
    carries through unchanged.
    """
    if not evidence.content_leaves:
        raise Denied("approval.elevate",
                     "no inspected content backs this elevation", "I-110", True)
    return Taint(
        provenance=taint.provenance | {APPROVED_PROVENANCE},
        trust=Trust.HIGHEST,
        classification=taint.classification,
    )


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

    def james_approves(self, plan_identity: str,
                       names_sources: frozenset[str] = frozenset()) -> Approval:
        """James's approval of ONE plan -- not standing. Capture surface is
        Section 26's scope; this records the act.

        `names_sources` is `I-40`'s requirement, not a convenience: a plan
        influenced by EXTERNAL content cannot exceed PREPARE without an
        approval NAMING THE SOURCE. The caller passes the sources actually
        present in the taint James was shown, and the approval card names
        those same sources -- an approval naming a source James never saw
        would be the dishonesty ADR 0048 exists to prevent, wearing I-40's
        clothes. Default empty, so a caller that says nothing names nothing.

        Re-arms an identity previously spent: a fresh decision is a fresh
        approval. Nothing here is automatic -- reaching this method at all
        required a human act (I-09).
        """
        a = Approval(approval_id=f"appr-{plan_identity[:12]}",
                     names_sources=frozenset(names_sources), standing=False)
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

    def _ancestry_of(self, token: ContextToken) -> tuple[str, ...]:
        """I-111's delegation ancestry, from the SOLE ISSUER's own record.

        The Context service holds authority facts the token does not carry
        (AG-1/AG-2). A token issued by `delegate` has an ancestry entry; one
        issued by `issue_root` has no entry at all -- and cannot be a delegate,
        because only `delegate` produces child tokens. So an absent entry means
        ROOT, i.e. ancestry `[]`, not "unknown".

        The distinction matters: `[]` persists as "established, no delegation",
        while `None` would persist as NULL and fail closed at retrieval.
        """
        context = getattr(self._boundary, "_context", None)
        facts = getattr(context, "facts", None)
        if facts is None:
            # No issuer to ask. We cannot establish ancestry, and inventing
            # `[]` here would assert "no delegation" on no evidence.
            return None
        return tuple(facts(token).get("ancestry", ()))

    def transport_for(self, token: ContextToken, tool_name: str = TOOL,
                      taint: Optional[Taint] = None,
                      evidence: Optional[ApprovalEvidence] = None):
        """The transport for one tool. Every branch below writes through the
        SAME scope-bound channel and names `ch.scope_path` -- never a scope
        from the payload -- so WITH CHECK refuses anything else regardless of
        which tool ran.

        `evidence` is present ONLY when `taint` was elevated (ADR 0048). It is
        not consulted to decide anything -- that decision was made and made
        once in `execute_action` -- it is recorded, so the elevation can be
        answered for afterwards. Passing it does not cause an elevation and
        omitting it does not prevent one; it is the audit half.

        It is recorded inside the `write_item` branch rather than here, because
        that branch is the only one that stores the I-111 columns and so the
        only place an elevation can be real (F-8).
        """

        def transport(payload: dict[str, Any], secret: str) -> Outcome:
            with self._boundary.open(token) as ch:

                def record_elevation(ref: str, detail: str) -> None:
                    """I-110's requirement that a promotion RECORDS or does not
                    happen -- ONE definition, called ONLY from a branch that has
                    just persisted the taint.

                    F-8 established the property this preserves: an elevation
                    audit exists if and only if a row carries the elevated
                    taint. F-8 achieved it by placing the record inside the one
                    branch that stored a taint; ADR 0049 gives `task` the same
                    five columns, so a second branch now stores one too. The
                    CONDITION has not moved -- the set of rows meeting it grew,
                    which is what ADR 0049 means. Extracting the record here
                    rather than copying it keeps a single definition of "an
                    elevation happened"; `complete_task` and `add_scope` store
                    no taint, do not call this, and therefore still cannot
                    emit one.
                    """
                    if evidence is None or taint is None:
                        return
                    ch.execute(
                        "INSERT INTO audit_record"
                        " (event_identity, writer, category, scope_path, trace_id, actor_ref, detail)"
                        " VALUES (%s,'W-1','trust.elevation',%s,%s,%s,%s)"
                        " ON CONFLICT (event_identity) DO NOTHING",
                        (hashlib.sha256(
                            f"trust_elevation:{token.trace_id}:{ch.scope_path}"
                            f":{tool_name}:{ref}".encode()).hexdigest()[:32],
                         ch.scope_path, token.trace_id, token.actor,
                         # The seven things I-110 names, in one line: the row,
                         # its prior immutable provenance, the evidence relied
                         # on, the authority responsible, the resulting trust,
                         # and -- in the row's own columns -- the trace.
                         f"{tool_name} {detail}"
                         f" from={sorted(evidence.proposed_taint.provenance)}"
                         f" trust_from={evidence.proposed_taint.trust.name}"
                         f" to={int(taint.trust)}({taint.trust.name})"
                         f" approval={evidence.approval_id}"
                         f" approved_by={evidence.approved_by}"
                         f" inspected={sorted(evidence.content_leaves)}"),
                    )

                if tool_name == ADD_TASK:
                    ref = payload["task_ref"]
                    # ADR 0049: the title is CONTENT, so its security state is
                    # written WITH it, from the plan the PDP authorized and the
                    # token -- never from the payload, exactly as `write_item`
                    # takes it.
                    #
                    # ONE STATEMENT, and the DO UPDATE list carries all five
                    # columns beside `title`. That is what makes row-level
                    # provenance sound without a history table: the upsert
                    # destroys the previous title, and it must destroy that
                    # title's provenance in the same breath. A replacement
                    # title inheriting its predecessor's taint would be a
                    # laundering path of its own.
                    ancestry = self._ancestry_of(token)
                    ch.execute(
                        "INSERT INTO task (task_ref, scope_path, actor_ref, title, due_on,"
                        " provenance, trust, classification,"
                        " delegation_ancestry, creating_authority)"
                        " VALUES (%s,%s,%s,%s, NULLIF(%s,'')::date, %s,%s,%s,%s,%s)"
                        " ON CONFLICT (scope_path, task_ref)"
                        " DO UPDATE SET title = EXCLUDED.title,"
                        " due_on = EXCLUDED.due_on,"
                        " provenance = EXCLUDED.provenance,"
                        " trust = EXCLUDED.trust,"
                        " classification = EXCLUDED.classification,"
                        " delegation_ancestry = EXCLUDED.delegation_ancestry,"
                        " creating_authority = EXCLUDED.creating_authority",
                        (ref, ch.scope_path, token.actor, payload["title"],
                         payload.get("due_on", ""),
                         sorted(taint.provenance) if taint else None,
                         int(taint.trust) if taint else None,
                         int(taint.classification) if taint else None,
                         list(ancestry) if ancestry is not None else None,
                         token.trace_id))
                    detail, said = f"task_ref={ref}", f"added task {ref}"
                    record_elevation(ref, detail)
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
                    # I-111: the security state is written WITH the row, from
                    # the execution context -- never from the payload, which
                    # is why none of these five values is read from `payload`.
                    # The plan's taint is what authorization was decided
                    # against; persisting anything else would record a
                    # different security state than the one that was checked.
                    ancestry = self._ancestry_of(token)
                    ch.execute(
                        "INSERT INTO item (item_ref, scope_path, body,"
                        " provenance, trust, classification,"
                        " delegation_ancestry, creating_authority)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                        " ON CONFLICT (scope_path, item_ref)"
                        " DO UPDATE SET body = EXCLUDED.body,"
                        " provenance = EXCLUDED.provenance,"
                        " trust = EXCLUDED.trust,"
                        " classification = EXCLUDED.classification,"
                        " delegation_ancestry = EXCLUDED.delegation_ancestry,"
                        " creating_authority = EXCLUDED.creating_authority",
                        (ref, ch.scope_path, payload["body"],
                         sorted(taint.provenance) if taint else None,
                         int(taint.trust) if taint else None,
                         int(taint.classification) if taint else None,
                         list(ancestry) if ancestry is not None else None,
                         token.trace_id))
                    detail, said = f"item_ref={ref}", f"wrote {ref}"

                    # ADR 0048's elevation, recorded through the SAME helper
                    # the task branch uses -- one definition, called only from
                    # branches that just stored a taint (F-8, preserved).
                    record_elevation(ref, detail)

                # The SAME derivation recovery uses. Written in this
                # transaction, so the row exists if and only if the side
                # effect above committed -- which is what makes an
                # interrupted execution decidable rather than a guess.
                event_identity = execution_event_identity(
                    token.trace_id, ch.scope_path, tool_name, ref)
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
                        arguments: dict[str, Any],
                        taint: Optional[Taint] = None) -> Plan:
        """I-112: deterministic identity over the tool AND its arguments, so
        two different tools -- or the same tool with different arguments --
        are two different plans and one approval never covers the other.

        `taint` is the HONEST origin of this plan's content -- the union of
        what the proposer read, plus the proposer's own provenance. It used to
        be the constant `Taint.of("james.stated")`, which meant every write
        persisted as HIGHEST regardless of what produced it and left
        `policy.py`'s I-40 branch reading synthetic state (ADR 0048).

        THE TAINT IS NOT PART OF THE IDENTITY, and must not become part of it:
        `I-112` lists the material changes that mint a new plan as *a step,
        resource, right, risk class, scope, tool, or cost* -- taint is carried
        by the plan, not hashed into it. That is what lets `decide()`
        reconstruct a plan from stored arguments and match the identity James
        approved without having to reproduce the taint as well.

        NEVER PASS AN ELEVATED TAINT HERE. The plan's taint is what the PDP
        authorizes against; elevation happens after authorization, at one call
        site in `execute_action`, and going the other way would re-break I-40
        from the opposite direction.

        Absent taint is UNKNOWN, and unknown is `model.generated` at LOW --
        never `james.stated`. A caller that does not know where content came
        from does not get to say James said it.
        """
        return Plan(
            steps=(PlanStep(action=tool_name, resource=scope_path,
                            tool_name=tool_name,
                            required_rights=frozenset({"write"}),
                            arguments=dict(arguments)),),
            required_rights=frozenset({"write"}),
            declared_risk=Risk.EXECUTE,
            scope_path=scope_path,
            taint=taint if taint is not None else Taint.of(UNKNOWN_ORIGIN),
            cost_estimate=1,
        )

    def plan_for(self, scope_path: str, item_ref: str, body: str,
                 taint: Optional[Taint] = None) -> Plan:
        return self.plan_for_action(scope_path, TOOL,
                                    {"item_ref": item_ref, "body": body}, taint)

    def content_leaves(self, tool_name: str) -> frozenset[str]:
        """The EXPRESSIVE arguments of one tool -- ADR 0048's "content".

        THE SINGLE SOURCE OF TRUTH, called by both the approval card that
        renders them and the elevation check that requires them to have been
        rendered. One function, one answer: "was the content shown?" cannot
        drift from "what counts as content", because nothing computes either
        of them separately.

        ADR 0036 already drew this line and drew it the right way round:
        CONSEQUENCE is the default and EXPRESSIVE is the exception a tool must
        declare. So prose -- an item's body, a task's title -- is EXPRESSIVE,
        while identifiers and dates are CONSEQUENCE and are pinned by the
        ArgumentEnvelope instead (`I-100`).

        EMPTY MEANS NO ELEVATION IS POSSIBLE. `complete_task` and `add_scope`
        persist no prose at all, so there is nothing for James to inspect and
        nothing an inspection could vouch for. That is a property of the tool,
        not a check that could be forgotten.
        """
        definition = self._registry.get(tool_name, TOOL_VERSION)
        return frozenset(leaf for leaf in definition.leaves()
                         if not definition.is_consequence_determining(leaf))

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
                       tool_name: str, arguments: dict[str, Any],
                       taint: Optional[Taint] = None,
                       evidence: Optional[ApprovalEvidence] = None) -> Outcome:
        """Authorize, then execute. No database write occurs before
        authorize_plan has succeeded -- the transport is not even constructed
        until the PEP, and the PEP requires the authorization object.

        `taint` is the honest origin of the content; `evidence` is what ADR
        0048 requires before that content may be persisted as trusted. Both
        arrive from `ApprovalService.decide`, which read them off the durable
        approval row. A caller supplying neither gets an unelevated write --
        the default, not a failure.
        """
        plan = self.plan_for_action(scope_path, tool_name, arguments, taint)
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

        # ===== ADR 0048's ELEVATION POINT -- the only one =====
        #
        # HERE, and deliberately nowhere else: after `authorize_plan` returned
        # and after the approval was atomically taken. Downstream of the PDP,
        # so the decision was made against the HONEST taint and an elevation
        # can never widen what was authorized; upstream of the transport, so
        # the integration is handed a finished value rather than a judgement.
        #
        # All four conditions, and no default that supplies any of them:
        #   approval  -- a human act happened (I-09); `take()` returns None on
        #                a replay, so a spent approval elevates nothing
        #   evidence  -- the durable row carried the taint James was shown.
        #                NULL there means unknown, and unknown is not a licence
        #   leaves    -- the tool HAS prose to inspect. complete_task and
        #                add_scope have none and can never reach elevation
        #   (elevate itself re-checks the leaves and raises rather than
        #    quietly returning the input, so the guard cannot rot into a no-op)
        #
        # Anything missing => `plan.taint` persists unchanged. That is ADR
        # 0048's default: the write still happens, it is simply not trusted.
        persisted, elevation = plan.taint, None
        if approval is not None and evidence is not None and evidence.content_leaves:
            persisted, elevation = elevate(plan.taint, evidence), evidence

        return self._pep.invoke(
            token, plan, plan.steps[0], authorization,
            resolve_binding=lambda name, scope: self.binding_for(scope, name),
            # I-111: the security state recorded with the row. It is the taint
            # authorization was decided against, plus -- and only where ADR
            # 0048's evidence exists -- the elevation that evidence supports.
            transport=self._integration.transport_for(token, tool_name,
                                                      taint=persisted,
                                                      evidence=elevation),
            tool_version=TOOL_VERSION,
            provider_enforces_dedup=True,
        )

    def execute(self, token: ContextToken, scope_path: str,
                item_ref: str, body: str,
                taint: Optional[Taint] = None) -> Outcome:
        return self.execute_action(token, scope_path, TOOL,
                                   {"item_ref": item_ref, "body": body}, taint)
