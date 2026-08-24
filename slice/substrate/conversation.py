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
from ..core.types import (Classification, ContextToken, Denied, Risk, Taint,
                          Trust)
from .approval_flow import ApprovalService
from .boundary import DataAccessBoundary
from .write_path import ADD_SCOPE, ADD_TASK, COMPLETE_TASK, TOOL

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


@dataclasses.dataclass(frozen=True)
class Turn:
    """One exchange, as the server knows it. `state` is the SERVER's account
    of what happened -- model prose never sets it.

        answered     information only; nothing was proposed or done
        proposed     a pending approval now exists; approval_id says which
        unavailable  the model could not be reached / outcome unknown
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

    @staticmethod
    def _establish(rows, revoked):
        """I-111's read half: restore the persisted security state, or withhold.

        An item reaches the model ONLY when every component of its security
        state was actually recorded and can be checked. Each of these is a
        separate reason to withhold, and none of them is recoverable by
        inference -- which is the point. Guessing any of them would invent
        authority at read time, and `I-110` exists to forbid exactly that.

            provenance / trust / classification NULL  unknown taint
            delegation_ancestry NULL                  unknown lineage
            creating_authority NULL                   unknown author
            ancestry non-empty                        ancestors' revocation
                                                      state is NOT
                                                      establishable from this
                                                      scope (I-03/I-86), so the
                                                      lookup is incomplete
            creating_authority in `revoked`           revoked author (S7-D5)

        The ancestry rule is the subtle one. A delegate's ancestors may have
        executed in BROADER scopes, whose revocation records a channel bound
        here cannot see. "Could not check" must never become "not revoked", so
        a non-empty ancestry withholds rather than guesses. An EMPTY ancestry
        is different in kind: the item was created by a root execution whose
        scope is this row's own scope, so its revocation record -- if any --
        is necessarily visible here, and absence is a complete answer.

        Legacy rows (written before I-111) have NULL throughout and are
        withheld by the first rule. They are not backfilled, not assumed to be
        `james.stated`, and not treated as trusted.
        """
        kept, withheld = [], 0
        for ref, body, provenance, trust, classification, ancestry, author in rows:
            if (provenance is None or trust is None or classification is None
                    or ancestry is None or author is None
                    or ancestry            # ancestors unestablishable from here
                    or author in revoked):
                withheld += 1
                continue
            kept.append((ref, body, Taint(frozenset(provenance), Trust(trust),
                                          Classification(classification))))
        return kept, withheld

    def _scope_context(self, token: ContextToken, scope_path: str):
        """What this scope knows, gathered EXACTLY as a page render would:
        PDP data-read decision first, then a scope-bound channel, no
        application-side predicate, audit in the same transaction. The model
        is downstream of the same controls as a screen."""
        self._pdp.authorize_data_read(token, scope_path)
        with self._boundary.open(token) as ch:
            # I-111: the persisted security state comes back WITH the row. It
            # is not recomputed, and it is not assumed from the fact that the
            # row is in NOVA's own database.
            rows = ch.fetch(
                "SELECT item_ref, body, provenance, trust, classification,"
                " delegation_ancestry, creating_authority"
                " FROM item ORDER BY item_ref")
            # Revocation is looked up ONCE, for the authorities this scope's
            # own rows name, through this same bound channel (S7-D5). RLS is
            # the completeness boundary: an authority whose revocation record
            # lives outside this scope is not visible here, which is exactly
            # why an unestablishable lookup fails closed below rather than
            # being read as "not revoked".
            revoked = {r[0] for r in ch.fetch(
                "SELECT execution_identity FROM authority_revocation")}
            items, withheld = self._establish(rows, revoked)
            tasks = ch.fetch(
                "SELECT task_ref, title, due_on FROM task WHERE done_at IS NULL"
                " ORDER BY due_on NULLS LAST, task_ref")
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
                 f"conversation context items={len(items)}"
                 + (f" withheld={withheld}" if withheld else "")))
        lines = [f"Scope: {scope_path}",
                 f"Pending approvals awaiting James: {pending}"]
        if tasks:
            lines.append("Open tasks in this scope (ref, title, due):")
            lines += [f"  - {ref} | {title} | due {due or 'no date'}"
                      for ref, title, due in tasks]
        else:
            lines.append("No open tasks in this scope.")
        if items:
            lines.append("Notes in this scope:")
            lines += [f"  - {ref}: {body}" for ref, body, _ in items]
        else:
            lines.append("This scope has no notes yet.")
        if withheld:
            # Said plainly rather than hidden: NOVA reports that it cannot
            # vouch for something, instead of quietly answering as though the
            # scope were emptier than it is. The content is NOT included.
            lines.append(f"{withheld} note(s) in this scope are withheld: their"
                         " provenance, trust or creating authority cannot be"
                         " established, so they are not shown to the model.")
        # I-99 / I-111: the block's taint is the union of what went INTO it.
        # The base covers NOVA's own reading of its own records (scope path,
        # task titles, pending count); each included item contributes the taint
        # that was actually persisted with it. Union takes the LOWEST trust and
        # the STRICTEST classification, so nothing here can raise trust.
        base = Taint.of("james.stated", Classification.CONFIDENTIAL)
        taint = Taint.union(base, *[t for _, _, t in items]) if items else base
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
            return Turn("refused", "", detail=d.reason)
        if response.outcome != "success_claimed":
            return Turn("unavailable", "",
                        detail=f"model outcome: {response.outcome}")

        return self._interpret(response.text, scope_path, execute_token)

    def _interpret(self, text: str, scope_path: str,
                   execute_token: Optional[ContextToken]) -> Turn:
        """Parse the ONE marker; everything else is prose. The marker is
        stripped from what James reads either way -- what he sees about a
        proposal is the SERVER's approval card, built from the stored
        approval row, never the model's own description of it."""
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
                    if_wrong_text="A task you did not want appears in this scope.")
            elif tool_name == ADD_SCOPE:
                name, kind = ref, match.group(2)
                approval_id = self._approvals.propose_action(
                    execute_token, scope_path, ADD_SCOPE,
                    {"scope_name": name, "kind": kind},
                    action_text=f"Create \u201c{name}\u201d as a new place in this scope.",
                    why_text=("Creating a place changes NOVA's structure. "
                              "Nothing may grow the tree without your approval."),
                    cost_text="One empty scope created. Nothing else changes.",
                    if_wrong_text="An empty place exists that you can simply ignore.")
            elif tool_name == COMPLETE_TASK:
                approval_id = self._approvals.propose_action(
                    execute_token, scope_path, COMPLETE_TASK, {"task_ref": ref},
                    action_text=f"Mark task \u201c{ref}\u201d done.",
                    if_wrong_text="A task still outstanding is recorded as finished.")
            else:
                approval_id = self._approvals.propose(
                    execute_token, scope_path, ref, match.group(2))
        except Denied as d:
            return Turn("answered", prose, detail=f"proposal refused: {d.reason}")
        return Turn("proposed", prose, approval_id=approval_id)
