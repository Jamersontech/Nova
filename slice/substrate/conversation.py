"""Conversation: the interface, wired to the systems that already exist.

USER_INTERFACE_ARCHITECTURE.md is blunt about what this is: "Conversation is
not a section -- it is the interface. NOVA is primarily talked to." Everything
built before this was the looking half. This is the asking half, and it is
deliberately a THIN seam over existing machinery rather than a new system:

    ask       -> the existing Data Access PEP, Data-Access Boundary and RLS
                 gather what this scope knows; the existing ModelGateway
                 (I-94..I-99) carries the question to the provider
    propose   -> the model may emit ONE strict marker; the server parses it
                 and calls the EXISTING ApprovalService.propose -- which is
                 the same as doing nothing until James decides
    act       -> never from here. Deciding stays on the approval surface, and
                 execution stays PDP -> ToolPEP -> boundary -> RLS WITH CHECK

WHAT THE MODEL IS, AND IS NOT
-----------------------------
The model is an interpreter of James's words, not an actor. Its output:

  * cannot reach the database -- the transport receives (prompt, credential
    reference) and nothing else; there is no connection to hold
  * cannot select its own provider, model, or routing (I-98)
  * cannot supply provenance, risk class, or authority (I-99, I-101)
  * cannot execute anything -- the ONLY consequence-shaped thing the server
    reads out of it is a proposal marker, and a proposal is a pending
    approval: inert until James approves that exact plan identity (I-112)
  * cannot claim completion -- action state shown to James comes from the
    SERVER's execution results, never from model prose. A model saying
    "done" is rendered as untrusted text; the page's action state says
    what actually happened.

SCOPE AWARENESS IS THE TOKEN, NOT A PROMPT TRICK
------------------------------------------------
The conversation is bound to the scope James is standing in. The scope
context handed to the model is read through the same authorized path as any
page render: PDP data-read decision, scope-bound channel, RLS. So the model
can only ever be shown what the token could reach anyway -- a sibling scope's
data is not omitted from the prompt by discipline, it is unreachable
(I-03, I-95).

WHAT IS DELIBERATELY ABSENT
---------------------------
No memory, no cross-scope aggregation, no vector store, no agent framework,
no streaming, no second approval path. The transcript lives in process
memory and dies with it -- continuity is a future capability, not a hidden
table.
"""

from __future__ import annotations

import dataclasses
import hashlib
import re
from typing import Optional

from ..core.gateway import CapabilityProfile, ModelGateway, ModelRequestItem
from ..core.types import Classification, ContextToken, Denied, Risk, Taint
from .approval_flow import ApprovalService
from .boundary import DataAccessBoundary
from .establishment import establish
from .write_path import (ADD_SCOPE, ADD_TASK, COMPLETE_TASK, TOOL,
                         UNKNOWN_ORIGIN)

# ---------------------------------------------------------------------------
# D-08, resolved for Conversation (ADR 0047). This block is the application's
# ENTIRE knowledge of the provider: a name, a model, and a profile. I-98's
# shape -- routing declared ahead of time, never chosen by model output.
# ---------------------------------------------------------------------------
PROVIDER = "anthropic"
CONVERSATION_MODEL = "claude-sonnet-5"
CONVERSATION_PROFILE = CapabilityProfile(
    name="conversation",
    permitted_providers=frozenset({PROVIDER}),
    permitted_models=frozenset({CONVERSATION_MODEL}),
)

# I-105: every execution carries a ceiling. Per conversation turn, in gateway
# cost units (prompt characters at the binding's rate). Exhaustion terminates
# and escalates -- the gateway will not quietly truncate to fit (AG-15).
TURN_BUDGET = 200_000

# The ONLY structured things the server reads out of model text. Strict on
# purpose: anything that does not match EXACTLY is prose, not a proposal.
# Each maps to ONE existing tool; the model cannot name a tool itself.
_REF = r'([A-Za-z0-9][A-Za-z0-9_.-]{0,63})'
_MARKERS = (
    (TOOL, re.compile(r'\[\[PROPOSE_NOTE ref="' + _REF +
                      r'" body="([^"\n]{1,1000})"\]\]')),
    (ADD_TASK, re.compile(r'\[\[PROPOSE_TASK ref="' + _REF +
                          r'" title="([^"\n]{1,300})" due="(\d{4}-\d{2}-\d{2}|)"\]\]')),
    (COMPLETE_TASK, re.compile(r'\[\[COMPLETE_TASK ref="' + _REF + r'"\]\]')),
    # The name class is DELIBERATELY narrower than _REF: one lowercase path
    # segment, because it becomes part of a scope path. The kind is a closed
    # set -- anything else is prose.
    (ADD_SCOPE, re.compile(r'\[\[PROPOSE_SCOPE name="([a-z0-9][a-z0-9_.-]{0,63})"'
                           r' kind="(area|business|client|account|place)"\]\]')),
)
_ANY_MARKER = re.compile(r'\[\[[A-Z_]+[^\]]*\]\]')

# F-13 / `S7-D5`. The per-row revocation label. ONE constant, so the marker the
# block renders and the marker anything asserts about it cannot drift.
#
# Deliberately not a `[[MARKER]]`: those are the grammar the SERVER parses out
# of MODEL output, and this travels the other way. Deliberately not a
# provenance term either -- revocation is a later fact ABOUT an authority, not
# an origin, and `I-38` makes provenance immutable.
_REVOKED_MARK = "  [creating authority revoked]"


def _mark(revoked: bool) -> str:
    """The label, or nothing. Deterministic and per row (F-13)."""
    return _REVOKED_MARK if revoked else ""

_INSTRUCTIONS = """\
You are NOVA, James's private operating system. You are speaking with James \
inside ONE scope of his life; the scope path and its current data are below. \
Answer from that data. If the data does not contain the answer, say so plainly \
-- do not invent records.

You cannot perform actions. If James asks for something to be recorded or \
changed, reply normally and then emit EXACTLY one final line, one of:
[[PROPOSE_NOTE ref="short-ref" body="the note text"]]
[[PROPOSE_TASK ref="short-ref" title="what needs doing" due="YYYY-MM-DD"]]
[[COMPLETE_TASK ref="the-existing-task-ref"]]
[[PROPOSE_SCOPE name="lowercase-name" kind="client"]]
Use PROPOSE_SCOPE when James mentions a NEW client, business, life area or \
account that needs a place of its own inside this scope -- a scope is where \
its notes and tasks will live. kind must be one of: area, business, client, \
account, place. The name must be lowercase, no spaces (use hyphens).
Use PROPOSE_TASK when something needs to be DONE, with a due date if James \
gave one (otherwise due=""). Use COMPLETE_TASK only with a task ref that \
appears in the data below. That line is a request for James's approval, not \
an action. Never state or imply that an action has been performed, and never \
emit a marker unless James asked for something to be recorded or changed."""


# What James is told when NOVA has no conversation provider registered. Written
# HERE, as prose for a human, rather than passed through from a `Denied` --
# denial reasons are internal and some are security events.
PROVIDER_UNCONFIGURED = ("No conversation provider is configured, so NOVA could "
                         "not answer. Set ANTHROPIC_API_KEY and restart NOVA.")


@dataclasses.dataclass(frozen=True)
class Turn:
    """One exchange, as the server knows it. `state` is the SERVER's account
    of what happened -- model prose never sets it.

        answered     information only; nothing was proposed or done
        proposed     a pending approval now exists; approval_id says which
        unavailable  the model could not be reached / outcome unknown, which
                     includes NOT BEING CONFIGURED -- `detail` says which
        refused      authorization denied the turn
    """
    state: str
    reply: str
    approval_id: Optional[str] = None
    detail: str = ""


class ConversationService:
    """Holds no authority. Every decision below is the PDP's, the gateway's,
    the boundary's, RLS's, or -- for anything with consequence -- James's."""

    def __init__(self, gateway: ModelGateway, pdp, boundary: DataAccessBoundary,
                 approvals: Optional[ApprovalService], budget=None,
                 provider: str = PROVIDER, model: str = CONVERSATION_MODEL,
                 profile: CapabilityProfile = CONVERSATION_PROFILE):
        self._gateway = gateway
        self._pdp = pdp
        self._boundary = boundary
        self._approvals = approvals
        self._budget = budget
        self._provider = provider
        self._model = model
        self._profile = profile

    # -- the scope's knowledge, through the authorized read path ------------

    # `I-111`'s read half now lives in `establishment.py`, so `approval_flow`
    # can reach the SAME rules without importing this module -- which would be
    # a cycle, since this module imports `ApprovalService`. Nothing about the
    # rules changed; only where they live did.
    #
    # The name is KEPT, and kept as a staticmethod, because it is the calling
    # convention two production call sites below and one test already use.
    # Preserving it is what makes this a move rather than a rewrite.
    _establish = staticmethod(establish)

    def _scope_context(self, token: ContextToken, scope_path: str):
        """What this scope knows, gathered EXACTLY as a page render would:
        PDP data-read decision first, then a scope-bound channel, audit in the
        same transaction. The model is downstream of the same controls as a
        screen.

        ONE SCOPE'S CONTENT, NOT A SUBTREE'S (F-12, `I-95`). The content reads
        carry an explicit `scope_path = %s`, which is NOT the isolation control
        -- RLS is, and it is still what makes another scope's rows unreachable.
        It is the DECOMPOSITION rule, exactly as `attention.py` states it: a
        token covers its descendants, so without the predicate a conversation
        at a parent assembled every descendant's rows into ONE model request,
        and two sibling clients' CLIENT-CONFIDENTIAL content left NOVA
        correlated in one buffer to one provider. Measured before this existed.

        Containment and isolation are different properties and both hold here.
        Containment is unchanged: the token may still cover descendants, and
        ancestor-to-descendant authorization for reads and writes elsewhere is
        untouched. Isolation is what this predicate expresses -- covered
        content may be reached, but sibling content may not be CORRELATED in
        one provider request (`I-95`, `CROSS_SCOPE_DATA_RULES` §2 and §6,
        `CONTEXT_ARCHITECTURE` §6, `SECURITY_BOUNDARIES` §3). Cross-scope work
        reaching a model is N single-scope calls aggregated above them; this
        method is one of those calls.

        UNIFORM ACROSS SIBLINGS, with no scope-kind special case: `I-95` says
        "sibling content", not "client content", and reasoning about `kind`
        here would be a second security semantics the architecture does not
        have.

        The subtree-wide counts below are deliberately UNCHANGED. A count in
        which no scope is identifiable is permitted aggregation
        (`CROSS_SCOPE_DATA_RULES` §3), and narrowing them is not part of the
        decomposition rule.

        The predicate is bound from `ch.scope_path` -- the channel's own
        binding, established by the Data-Access Boundary from a verified token
        -- and never from a payload, a model-supplied argument, a ref, or any
        caller-supplied string. A caller naming its own scope is the shape
        every write branch already refuses."""
        self._pdp.authorize_data_read(token, scope_path)
        with self._boundary.open(token) as ch:
            # I-111: the persisted security state comes back WITH the row. It
            # is not recomputed, and it is not assumed from the fact that the
            # row is in NOVA's own database.
            rows = ch.fetch(
                "SELECT item_ref, body, provenance, trust, classification,"
                " delegation_ancestry, creating_authority"
                " FROM item WHERE scope_path = %s ORDER BY item_ref",
                (ch.scope_path,))
            # Revocation is looked up ONCE, for the authorities this scope's
            # own rows name, through this same bound channel (S7-D5). RLS is
            # the completeness boundary: an authority whose revocation record
            # lives outside this scope is not visible here, which is exactly
            # why an unestablishable lookup fails closed below rather than
            # being read as "not revoked".
            revoked = {r[0] for r in ch.fetch(
                "SELECT execution_identity FROM authority_revocation")}
            items, withheld = self._establish(rows, revoked)
            # ADR 0049: a task title is CONTENT, so it comes back with the same
            # five columns an item does and goes through the SAME `_establish`.
            # That method never inspects the content field -- it passes it
            # through untouched -- so a task's (title, due_on) travels exactly
            # where an item's body does. One establishment rule, one taint
            # representation; a second would be a second trust model.
            task_rows = ch.fetch(
                "SELECT task_ref, title, due_on, provenance, trust, classification,"
                " delegation_ancestry, creating_authority"
                " FROM task WHERE done_at IS NULL AND scope_path = %s"
                " ORDER BY due_on NULLS LAST, task_ref",
                (ch.scope_path,))
            tasks, tasks_withheld = self._establish(
                [(r[0], (r[1], r[2]), r[3], r[4], r[5], r[6], r[7])
                 for r in task_rows], revoked)
            # F-13 / `S7-D5`. REVOKED and UNESTABLISHABLE are different facts,
            # counted separately here and reported separately below. Collapsing
            # them is what the previous version did, and it made the withheld
            # sentence FALSE for a revoked row: its provenance, trust and
            # creating authority are all established -- the authority is
            # established AS REVOKED.
            revoked_items = sum(1 for *_, rev in items if rev)
            revoked_tasks = sum(1 for *_, rev in tasks if rev)
            pending = ch.fetch(
                "SELECT count(*) FROM approval WHERE status = 'pending'")[0][0]
            event_identity = hashlib.sha256(
                f"conversation_read:{token.trace_id}:{scope_path}".encode()
            ).hexdigest()[:32]
            ch.execute(
                "INSERT INTO audit_record"
                " (event_identity, writer, category, scope_path, trace_id, actor_ref, detail)"
                " VALUES (%s,'W-1','data.read',%s,%s,%s,%s)"
                " ON CONFLICT (event_identity) DO NOTHING",
                (event_identity, scope_path, token.trace_id, token.actor,
                 f"conversation context items={len(items)} tasks={len(tasks)}"
                 + (f" withheld={withheld + tasks_withheld}"
                    if withheld or tasks_withheld else "")
                 # F-13: recorded separately, never folded into `withheld`.
                 # A revoked row was RETAINED, so counting it as withheld
                 # would make the audit record say the opposite of what
                 # happened.
                 + (f" revoked_authority={revoked_items + revoked_tasks}"
                    if revoked_items or revoked_tasks else "")))
        lines = [f"Scope: {scope_path}",
                 f"Pending approvals awaiting James: {pending}"]
        if tasks:
            lines.append("Open tasks in this scope (ref, title, due):")
            lines += [f"  - {ref} | {title} | due {due or 'no date'}{_mark(rev)}"
                      for ref, (title, due), _, rev in tasks]
        else:
            lines.append("No open tasks in this scope.")
        if items:
            lines.append("Notes in this scope:")
            lines += [f"  - {ref}: {body}{_mark(rev)}"
                      for ref, body, _, rev in items]
        else:
            lines.append("This scope has no notes yet.")
        if revoked_items or revoked_tasks:
            # The rows above are SHOWN, with their recorded state unchanged.
            # What NOVA adds is one further fact, and it deliberately draws no
            # conclusion from it: `MEMORY_MODEL.md` §4 rule 8 reserves that
            # judgement for the consuming authority, because "revocation
            # happens for many reasons and only some impeach what was learned".
            parts = ([f"{revoked_items} note(s)"] if revoked_items else []) + \
                    ([f"{revoked_tasks} task(s)"] if revoked_tasks else [])
            lines.append(f"{' and '.join(parts)} above are marked"
                         f" {_REVOKED_MARK.strip()}: the execution identity that"
                         " created them was later revoked. They are retained and"
                         " shown with their recorded provenance, trust and"
                         " classification UNCHANGED -- revocation is not a"
                         " judgement about the content. Treat it as information,"
                         " not as authority to act or to refuse: what it means"
                         " is decided where a consequential action is"
                         " authorized, never here.")
        if withheld or tasks_withheld:
            # Said plainly rather than hidden: NOVA reports that it cannot
            # vouch for something, instead of quietly answering as though the
            # scope were emptier than it is. The content is NOT included.
            #
            # Counted separately because they are different objects to James:
            # a withheld task is still on his attention surface and still
            # completable, while a withheld note is simply not shown here.
            #
            # This sentence now covers ONLY unestablishable rows. A revoked
            # authority is established, and is labelled above instead.
            parts = ([f"{withheld} note(s)"] if withheld else []) + \
                    ([f"{tasks_withheld} task(s)"] if tasks_withheld else [])
            lines.append(f"{' and '.join(parts)} in this scope are withheld:"
                         " their provenance, trust or creating authority cannot"
                         " be established, so they are not shown to the model."
                         " They remain visible to James and, for tasks, remain"
                         " completable.")
        # I-99 / I-111: the block's taint is the union of what went INTO it.
        # Each included item AND each included task contributes the taint that
        # was actually persisted with it: ADR 0049 made a task title content, so
        # it carries its origin into this union like anything else. Union takes
        # the LOWEST trust and the STRICTEST classification, so nothing here
        # raises trust.
        #
        # THE BASE COVERS WHAT NOTHING ELSE ATTRIBUTES: the headers, the pending
        # count, the withheld message -- and the SCOPE PATH. It used to be
        # `james.stated` alone, justified as "NOVA's own facts". ADR 0050 (F-11)
        # records why that premise no longer holds: `add_scope` lets a MODEL
        # choose a path segment, so part of the path is not NOVA's own fact and
        # not something James stated.
        #
        # The correction is the I-99 union with UNKNOWN_ORIGIN -- the term
        # `write_path` already defines for "nobody said where this came from",
        # DELIBERATELY not `james.stated`. Union takes the lowest trust, so the
        # block reads LOW.
        #
        # COARSE ON PURPOSE. ADR 0050 rules a scope name CONTROL/ADDRESSING, so
        # `scope` carries no provenance and there is nothing from which to
        # reconstruct which segment a model chose. Inventing one is precisely
        # what `I-110` forbids, so this says only what is known: some of this
        # block is NOVA's and James's own framing, and some of it may not be.
        # Every scope block therefore reads LOW, including for scopes James
        # created himself -- the honest cost of declining to invent provenance.
        #
        # A RESTRICTION, NOT A PROMOTION. `I-110`'s closing sentence -- "lowering
        # trust is not governed by this invariant" -- is why lowering is not
        # gated like elevation.
        #
        # NOT AN `I-40` CHANGE: neither term is in `EXTERNAL_PROVENANCE`, so
        # `is_untrusted_derived()` still fires on external content and only on
        # external content. Classification stays CONFIDENTIAL so the gateway's
        # `I-95` still sees scoped material rather than ambient INTERNAL text.
        base = Taint.union(
            Taint.of("james.stated", Classification.CONFIDENTIAL),
            Taint.of(UNKNOWN_ORIGIN, Classification.CONFIDENTIAL),
        )
        # A revoked row contributes EXACTLY what it always did. `S7-D5`: the
        # row is retained and not re-weighted, so its taint joins this union
        # unchanged -- revocation is carried beside the taint, never inside it.
        contributed = [t for _, _, t, _ in items] + [t for _, _, t, _ in tasks]
        taint = Taint.union(base, *contributed) if contributed else base
        return "\n".join(lines), taint

    # -- one turn ------------------------------------------------------------

    def respond(self, token: ContextToken, scope_path: str, message: str,
                execute_token: Optional[ContextToken] = None) -> Turn:
        """One question in, one honest account out.

        `token` is the READ-ceiling token for this request; `execute_token`
        (present only when the session may act, A-1) is used for exactly one
        thing: recording a proposal as a pending approval. Neither goes
        anywhere near the model.
        """
        try:
            context, context_taint = self._scope_context(token, scope_path)
        except Denied as d:
            return Turn("refused", "", detail=d.reason)

        if self._budget is not None:
            self._budget.open_root(token.trace_id, TURN_BUDGET)

        # The request the gateway authorizes, item by item (I-94):
        #   - instructions: NOVA's own fixed text
        #   - scope data: what this scope knows. Its taint is the I-99 UNION
        #     of the RESTORED taints of the items it contains (I-111) -- not
        #     `james.stated` because the rows live in NOVA's database. One
        #     `external.web` note at LOW trust drags the whole block to LOW,
        #     which is the point: the block is a derivation of its inputs, and
        #     `I-100`'s untrusted-derived ceiling is evaluated against it.
        #     CONFIDENTIAL at minimum: it is client-scope content leaving for a
        #     provider, and the gateway's I-95 one-scope rule must see it as
        #     scoped material, not ambient INTERNAL text.
        #   - the message: James's words, verbatim.
        items = [
            ModelRequestItem("instructions", _INSTRUCTIONS, scope_path,
                             Taint.of("james.stated", Classification.INTERNAL)),
            ModelRequestItem("scope-data", context, scope_path, context_taint),
            ModelRequestItem("message", f"James says: {message}", scope_path,
                             Taint.of("james.stated", Classification.CONFIDENTIAL)),
        ]
        try:
            response = self._gateway.call(token, items, self._profile,
                                          self._provider, self._model,
                                          risk=Risk.ANALYZE)
        except Denied as d:
            # A PROVIDER THAT IS NOT REGISTERED IS A CONFIGURATION FACT, NOT AN
            # AUTHORIZATION DECISION ABOUT JAMES -- and saying otherwise sends
            # him to check permissions he already holds. Measured on a real
            # first run with no `ANTHROPIC_API_KEY`: the gateway denied at
            # `gateway.binding`, this returned "refused", and the page told him
            # "the request was not authorized", which was false.
            #
            # `gateway.binding` is the ONLY step keyed on, and it is raised in
            # exactly two places, both of them about the binding table rather
            # than about the caller: no provider registered at all, and a
            # binding that does not serve the requested model. Every other
            # denial -- routing, classification, emergency stop, one-scope,
            # cost, and everything the PDP raises before the gateway -- still
            # returns "refused", because those ARE decisions about this
            # request.
            #
            # `unavailable` already means "the model did not answer and nothing
            # was done", which is exactly true here; reusing it keeps the
            # fail-closed shape and adds no new state. What changes is that the
            # DETAIL is a sentence written here, never `d.reason`, so no
            # internal denial text reaches the page.
            if d.step == "gateway.binding":
                return Turn("unavailable", "", detail=PROVIDER_UNCONFIGURED)
            return Turn("refused", "", detail=d.reason)
        if response.outcome != "success_claimed":
            return Turn("unavailable", "",
                        detail=f"model outcome: {response.outcome}")

        return self._interpret(response.text, scope_path, execute_token,
                               context_taint)

    def _interpret(self, text: str, scope_path: str,
                   execute_token: Optional[ContextToken],
                   context_taint: Optional[Taint] = None) -> Turn:
        """Parse the ONE marker; everything else is prose. The marker is
        stripped from what James reads either way -- what he sees about a
        proposal is the SERVER's approval card, built from the stored
        approval row, never the model's own description of it.

        ADR 0048: a proposal's content is MODEL TEXT, and its honest taint is
        the block the model read (`context_taint`) derived through its own
        `model.generated` provenance -- union of sources, lowest trust (I-99).
        That taint is recorded with the approval and is what the PDP later
        decides against. It is emphatically NOT `james.stated`: James has not
        said anything yet, and will not have until he reads the card."""
        proposal_taint = (context_taint.derive("model.generated")
                          if context_taint is not None else None)
        tool_name, match = None, None
        for candidate, pattern in _MARKERS:
            found = pattern.search(text)
            if found:
                tool_name, match = candidate, found
                break
        # Strip EVERY marker-shaped thing, matched or not: a malformed or
        # invented marker is not an action, and it is not shown to James as
        # though it were one either.
        prose = _ANY_MARKER.sub("", text).strip()
        if match is None:
            return Turn("answered", prose)

        if self._approvals is None or execute_token is None:
            # A proposal the session cannot record is reported, not silently
            # dropped and not sneaked through a weaker path.
            return Turn("answered", prose,
                        detail="a proposal was suggested but this session "
                               "cannot record one")
        ref = match.group(1)
        try:
            if tool_name == ADD_TASK:
                title, due = match.group(2), match.group(3)
                approval_id = self._approvals.propose_action(
                    execute_token, scope_path, ADD_TASK,
                    {"task_ref": ref, "title": title, "due_on": due},
                    action_text=(f"Add task \u201c{title}\u201d"
                                 + (f", due {due}." if due else ", with no due date.")),
                    if_wrong_text="A task you did not want appears in this scope.",
                    taint=proposal_taint)
            elif tool_name == ADD_SCOPE:
                name, kind = ref, match.group(2)
                approval_id = self._approvals.propose_action(
                    execute_token, scope_path, ADD_SCOPE,
                    {"scope_name": name, "kind": kind},
                    action_text=f"Create \u201c{name}\u201d as a new place in this scope.",
                    why_text=("Creating a place changes NOVA's structure. "
                              "Nothing may grow the tree without your approval."),
                    cost_text="One empty scope created. Nothing else changes.",
                    if_wrong_text="An empty place exists that you can simply ignore.",
                    taint=proposal_taint)
            elif tool_name == COMPLETE_TASK:
                approval_id = self._approvals.propose_action(
                    execute_token, scope_path, COMPLETE_TASK, {"task_ref": ref},
                    action_text=f"Mark task \u201c{ref}\u201d done.",
                    if_wrong_text="A task still outstanding is recorded as finished.",
                    taint=proposal_taint)
            else:
                approval_id = self._approvals.propose(
                    execute_token, scope_path, ref, match.group(2),
                    taint=proposal_taint)
        except Denied as d:
            return Turn("answered", prose, detail=f"proposal refused: {d.reason}")
        return Turn("proposed", prose, approval_id=approval_id)
