"""The application seam: HTTP request -> Context Token -> PDP -> RLS -> HTML.

This is the first place NOVA's security machinery is used BY an application
rather than by a test harness. One route, read-only, deliberately small:

    GET /scope/<path>/items

The chain, in order, with nothing skipped and nothing faked:

    HTTP request
      -> session cookie -> server-side actor identity      (stand-in for D-09)
      -> Context service issues the Context Token          (I-106, sole issuer)
      -> Data Access PEP: PolicyDecisionPoint.authorize_data_read
                                                           (I-77; ADR 0045)
      -> Data-Access Boundary opens a scope-bound channel  (I-78, I-79, I-87)
      -> query with NO application-side scope predicate    (RLS bounds it)
      -> audit row, deterministic identity, same txn       (I-93, W-1)
      -> server-rendered HTML

WHAT THE BROWSER NEVER HOLDS
----------------------------
The Context Token, the PDP's decision, database credentials, or any scope
binding. It holds one opaque session id. Authorization is server-side and the
browser is never an authority -- if it lies about the path, token issuance and
the PDP deny, and even a compromised handler reaches nothing outside the
token's scope because the channel is bound below it (I-62).

WHAT IS NO LONGER A STAND-IN
---------------------------
Authentication. `SessionStore` was a dictionary; it is gone. `auth.py` resolves
D-09 with WebAuthn passkeys and opaque server-side sessions, and the chain below
this line did not change to accommodate it -- authentication terminates at an
authenticated server identity and hands over exactly that.

A-1 IS ENFORCED HERE
--------------------
A session's strength comes from the user-verification flag inside the verified
signature. Read routes accept a single factor; every EXECUTE-class route --
writing, and deciding an approval -- requires two. The browser cannot assert
its own strength, because the flag was signed by the authenticator and checked
by the server.
"""

from __future__ import annotations

import dataclasses
import datetime
import hashlib
import html
import http.server
import pathlib
import secrets
import threading
from typing import Optional

from ..core.context_service import ContextService
from ..core.policy import PolicyDecisionPoint
from ..core.types import Denied, Risk
from .auth import AuthenticationFailed, AuthenticationService
from .boundary import DataAccessBoundary
from .write_path import REVOKE_AUTHORITY


# I-09: only James approves. The identity that may decide, checked server-side.
APPROVER_IDENTITY = "james"


def _requires_step_up(request) -> bool:
    """`I-67`: does deciding this approval need FRESH authentication?

    ONE definition, read by the route that offers a ceremony and by the route
    that demands one -- so what is challenged and what is required cannot
    disagree.

    The rule is `I-67`'s own wording and nothing else: *"IRREVERSIBLE actions
    and changes to grants, policy, classification, or credentials require fresh
    authentication, not merely a valid session"*. The risk class is the
    approval's OWN declared class, stored on the durable row when it was
    proposed; nothing the browser sends reaches this.

    ONE TOOL DECLARES `IRREVERSIBLE`: `revoke_authority` (`F-3`, ADR 0052
    element 8b). This gate was built before it existed and returned False for
    every approval NOVA could then create; it now fires, and it fires because
    the tool's declared class travelled -- declaration -> plan -> the approval
    row's `risk_class` -> here. Nothing was special-cased for it, which is the
    property that matters: the SECOND irreversible tool is gated on the day it
    lands. Which class a tool declares remains that tool's decision (`MT-6`, a
    `C3` change) and is not settled here.
    """
    return request.risk_class == Risk.IRREVERSIBLE.name

# The browser holds exactly these two, both opaque and both HttpOnly: a session
# reference and an in-flight ceremony reference. No token, no scope, no rights.
SESSION_COOKIE = "nova_session"
CEREMONY_COOKIE = "nova_ceremony"

# Section 15's generated stylesheet -- served, not duplicated.
TOKENS_CSS = pathlib.Path(__file__).resolve().parent.parent / "ui" / "tokens" / "tokens.css"


class Seam:
    """The wiring. Holds no authority of its own: every decision below is
    made by the Context service, the PDP, the boundary or RLS."""

    def __init__(self, context: ContextService, pdp: PolicyDecisionPoint,
                 boundary: DataAccessBoundary, auth: AuthenticationService,
                 write_path=None, approvals=None, tree=None, conversation=None,
                 attention=None, revocations=None):
        # The scope tree, for navigation only. Every path it offers is checked
        # against a grant before it is shown, and entering one still issues a
        # token and runs the PDP -- navigation is not authorization.
        self._tree = tree
        self._context = context
        self._pdp = pdp
        self._boundary = boundary
        self._auth = auth
        # Optional: the consequence-producing write path (write_path.WritePath).
        # The read seam predates it and works without it.
        self._writes = write_path
        # Optional: the approval experience (approval_flow.ApprovalService).
        self._approvals = approvals
        # Optional: conversation (conversation.ConversationService). The
        # transcript is in-process and per (session, scope): continuity is not
        # memory, and it dies with the process on purpose.
        self._conversation = conversation
        # Optional: the cross-scope attention view (attention.AttentionService).
        self._attention = attention
        # Optional: durable revocation of execution identities
        # (revocation.RevocationRegistry, S7-D5).
        #
        # HELD, AND STILL NOT CALLED FROM HERE -- by both halves, for two
        # different reasons.
        #
        # THE READ half of `S7-D5` needs nothing from this object:
        # `_scope_context` reads `authority_revocation` on the SAME bound
        # channel, in the SAME transaction as the items it is checking, which
        # is what makes the check a consistent snapshot rather than a window.
        # Routing that read through here would open a second channel and
        # reintroduce exactly the gap between reading an item and checking its
        # authority.
        #
        # THE WRITE half now exists -- `propose_revocation` below is `F-3`'s
        # surface -- and still does not touch this. It PROPOSES; the revocation
        # happens at the approval, inside the write path's own transaction
        # (ADR 0052 element 1 and 8d). A seam that could revoke directly would
        # be the second consequence path element 1 forbids.
        #
        # So this stays composed in and unused, which is the honest state.
        self._revocations = revocations
        self._transcripts: dict[tuple[str, str], list[dict]] = {}

    # -- the session gate (A-1) ---------------------------------------------

    def _signed_in(self, session_id: Optional[str], *, execute: bool):
        """Resolve the session and check it is strong enough for what follows.

        Returns (session, None) or (None, (status, page)). A-1: a single-factor
        session may read; anything EXECUTE-class needs two factors. Expiry and
        revocation are re-checked here on every request, which is what makes
        revocation take effect at the next decision (`I-65`).
        """
        session = self._auth.resolve(session_id)
        if session is None:
            return None, (401, _page("Not signed in",
                                     "<p>No session. <a href=\"/auth/login\">Sign in</a>.</p>"))
        if execute and not session.is_multi_factor:
            # Distinguishable on purpose: stepping up is the caller's next
            # legitimate move, not a secret.
            return None, (403, _page(
                "Stronger sign-in required",
                "<p>This action needs a second factor. Sign in again with your "
                "passkey's device verification.</p>"))
        return session, None

    # -- approvals ----------------------------------------------------------

    def _execute_token(self, session, scope_path: str,
                       rights=frozenset({"write"}), ceiling=Risk.EXECUTE):
        """A token for one consequential act. Issuance enforces grants first
        (`I-14`), and since `36b4dee` also refuses a ceiling above what those
        grants confer (`I-07`, `I-106`).

        RIGHTS AND CEILING ARE PARAMETERS, not constants (ADR 0052 element 8b).
        They default to what every existing caller asks for, so nothing changes
        for them; the approval decision derives both from the approval it is
        about to execute, because a token that cannot reach the plan's risk
        class -- or does not carry the right the plan requires -- would be
        refused by the PDP after James had already decided.

        Deriving rather than widening is the point: the ceiling comes from the
        durable approval row, and `I-106` at issuance is still the final word on
        whether James's grants permit it. Nothing here can hand out more than he
        granted.
        """
        return self._context.issue_root(
            identity=session.identity, actor=session.actor,
            scope_path=scope_path, rights=frozenset(rights),
            ceiling=ceiling, ttl=60,
        )

    def approvals_page(self, session_id: Optional[str], scope_path: str) -> tuple[int, str]:
        """What needs James's decision, in this scope."""
        if self._approvals is None:
            return 404, _page("Not found", "<p>Approvals are not enabled.</p>")
        session, refusal = self._signed_in(session_id, execute=True)
        if refusal:
            return refusal
        try:
            token = self._execute_token(session, scope_path)
            # Crash recovery, demand-driven and bounded by this token's scope.
            # Here rather than on the scope page because this is the narrowest
            # correct point: reconciling an approval WRITES to it, and this
            # route already holds a write-capable token from an EXECUTE-strength
            # session (A-1). The scope page holds a READ token, so recovering
            # there would be a write without a write right -- a new
            # authorization path, not a smaller one.
            #
            # Reconciles only what RLS admits for this scope; there is no
            # sweep. It executes and retries nothing, so a stranded approval
            # becomes an accurate record and never a resumed action.
            self._approvals.recover(token)
            requests = self._approvals.pending(token)
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        if not requests:
            body = "<p class=\"muted\">Nothing needs your decision here.</p>"
        else:
            # ADR 0048: the card must show the exact content, and the set of
            # arguments that IS the content comes from the write path's own
            # `content_leaves` -- the same function the elevation check uses.
            # Asking the write path rather than deciding here is the whole
            # point: two computations of "what counts as content" could
            # disagree, and then an elevation would claim an inspection this
            # page never offered.
            body = "".join(
                _approval_card(
                    r,
                    self._writes.content_leaves(r.tool_name)
                    if self._writes is not None else frozenset(),
                    # I-67: the card must ASK for the passkey where one is
                    # required, from the same predicate the route enforces.
                    step_up=_requires_step_up(r))
                for r in requests)
            if any(_requires_step_up(r) for r in requests):
                body += f"<script>{_STEP_UP_SCRIPT}</script>"
        return 200, _page(f"Approvals — {html.escape(scope_path)}",
                          f"<p class=\"muted\">Active context: "
                          f"<code>{html.escape(scope_path)}</code></p>{body}")

    def approval_step_up_options(self, session_id: Optional[str], scope_path: str,
                                 approval_id: str
                                 ) -> tuple[int, str, str, list[tuple[str, str]]]:
        """Begin the fresh authentication an `IRREVERSIBLE` approval needs.

        THE PURPOSE IS NOT THE BROWSER'S TO CHOOSE. It is `approval_id`, taken
        from the route the browser asked for -- so a ceremony can only ever be
        minted for the approval the caller is looking at, and `verify_step_up`
        recomputes it from the same place. A client that could name its own
        purpose could mint a challenge for a cheap approval and spend it on an
        expensive one, which is the whole reason the binding exists.

        Refuses unless the approval is reachable in this scope AND actually
        requires step-up: no ceremony is offered for an action that does not
        need one, so this route cannot become a general re-authentication
        oracle.
        """
        if self._approvals is None:
            return 404, "application/json", '{"ok":false}', []
        session, refusal = self._signed_in(session_id, execute=True)
        if refusal:
            return 401, "application/json", '{"ok":false}', []
        if session.identity != APPROVER_IDENTITY:
            return 403, "application/json", '{"ok":false}', []
        try:
            token = self._execute_token(session, scope_path)
            request = self._approvals.get(token, approval_id)
        except Denied:
            return 403, "application/json", '{"ok":false}', []
        if request is None or not _requires_step_up(request):
            return 403, "application/json", '{"ok":false}', []
        try:
            ceremony_id, options = self._auth.step_up_options(session, approval_id)
        except AuthenticationFailed:
            return 403, "application/json", '{"ok":false}', []
        return 200, "application/json", options, [
            self._cookie(CEREMONY_COOKIE, ceremony_id)]

    def decide_page(self, session_id: Optional[str], scope_path: str,
                    approval_id: str, approve: bool,
                    ceremony_id: Optional[str] = None,
                    assertion: str = "") -> tuple[int, str]:
        """Record the decision. On approval the action executes through the
        full authorization path -- this handler authorizes nothing itself."""
        if self._approvals is None:
            return 404, _page("Not found", "<p>Approvals are not enabled.</p>")
        session, refusal = self._signed_in(session_id, execute=True)
        if refusal:
            return refusal

        # I-09: only James approves. Checked server-side, from the session --
        # never from anything the browser could assert.
        if session.identity != APPROVER_IDENTITY:
            return 403, _page("Not permitted",
                              "<p>Only James can approve or deny an action.</p>")
        try:
            token = self._execute_token(session, scope_path)

            # I-67 / A-3, decided by ADR 0018: an IRREVERSIBLE action requires
            # FRESH authentication, "not merely a valid session". A-1 already
            # got us a two-factor session; this proves the human is still here,
            # now, for THIS act.
            #
            # HERE, AND DELIBERATELY NOT INSIDE `decide()`. The approval
            # machinery is untouched: I-09's single-use claim, I-112's identity
            # re-derivation and the PDP's ten steps all run exactly as before,
            # and they run only if this gate let the call through. A gate in
            # front of the act is auditable in one place; a check woven into
            # `decide()` would put an authentication concern inside the
            # authorization object.
            #
            # ONLY ON APPROVAL. Declining is not a consequential act -- it
            # writes a status and nothing else -- so requiring a ceremony to
            # say "no" would put friction on the safe answer.
            if approve:
                request = self._approvals.get(token, approval_id)

                # ADR 0052 element 8b. The token that EXECUTES must be able to
                # reach the approved plan's risk class and must carry the right
                # that plan requires -- both read from the DURABLE approval row
                # and its tool's declaration, never from the browser and never
                # assumed to be `write`/EXECUTE.
                #
                # Re-issued rather than widened: the read above needed only a
                # channel, and `I-106` at issuance is still the final word on
                # whether James's grants confer this ceiling. A revocation
                # therefore executes only where he holds a `revoke` grant, and
                # is refused at issuance -- before `decide()` -- where he does
                # not.
                if request is not None and self._writes is not None:
                    token = self._execute_token(
                        session, scope_path,
                        rights=self._writes.required_rights_for(request.tool_name),
                        ceiling=Risk[request.risk_class])

                if request is not None and _requires_step_up(request):
                    try:
                        self._auth.verify_step_up(ceremony_id, assertion,
                                                  session, approval_id)
                    except AuthenticationFailed:
                        # FAILS CLOSED, and provably: `decide()` is not
                        # reached, so the approval is not claimed, nothing
                        # executes, and no execution record is written. The
                        # approval is still pending and can be decided again.
                        return 401, _page(
                            "Fresh authentication required",
                            "<p>This action cannot be undone, so approving it "
                            "needs your passkey again. Nothing has been done.</p>"
                            f"<div class=\"actions\">"
                            f"<a href=\"/scope{html.escape(scope_path)}/approvals\">"
                            f"<button class=\"primary\" type=\"button\">"
                            f"Back to approvals</button></a></div>")

            status, outcome = self._approvals.decide(
                token, approval_id, approve, decided_by=session.actor)
        except Denied as d:
            if d.invariant == "I-09":
                return 409, _page("Already decided",
                                  "<p>This approval has already been decided.</p>")
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        if status == "denied":
            return 200, _page("Denied", "<p>Nothing was done. The action was declined.</p>")
        body = (f"<p>{html.escape(outcome.detail)} in "
                f"<code>{html.escape(scope_path)}</code></p>")
        # A scope that now exists deserves a door. The path comes from the
        # SERVER's execution outcome, never from model text.
        if outcome.detail.startswith("created /"):
            new_path = outcome.detail[len("created "):]
            body += (f"<div class=\"actions\"><a href=\"/scope{html.escape(new_path)}\">"
                     f"<button class=\"primary\" type=\"button\">"
                     f"Open {html.escape(_label(new_path))}</button></a></div>")
        return 200, _page("Approved", body)

    # -- the product: where James actually starts --------------------------

    def home_page(self, session_id: Optional[str]) -> tuple[int, str]:
        """Level 2 of USER_INTERFACE_ARCHITECTURE section 4: "see the three
        areas and current state".

        The three areas are LIFE, BUSINESS and WEALTH and there is never a
        fourth -- section 2 is explicit that businesses, clients and projects
        grow INSIDE, never beside. So this page enumerates roots; it does not
        enumerate subsystems.
        """
        session, refusal = self._signed_in(session_id, execute=False)
        if refusal:
            return refusal
        if self._tree is None:
            return 404, _page("Not found", "<p>No scope tree is loaded.</p>")

        # What needs his attention, first -- before the places he can go.
        # Composed above N independently authorized single-scope reads; see
        # attention.py. Ephemeral: rendered here and discarded.
        attention = ""
        if self._attention is not None:
            attention = _attention_section(
                self._attention.gather(session.identity, session.actor))

        areas = [p for p in self._tree.roots() if self._may_read(session, p)]
        if not areas:
            body = "<p class=\"muted\">Nothing is available to you yet.</p>"
        else:
            body = ("<h2 class=\"section\">Where things live</h2>" + "".join(
                f"<article class=\"card area\"><h3><a href=\"/scope{html.escape(p)}\">"
                f"{html.escape(_label(p))}</a></h3></article>"
                for p in areas))
        return 200, _page("NOVA", attention + body + _footer_links())

    def scope_page(self, session_id: Optional[str], scope_path: str) -> tuple[int, str]:
        """Level 3: drill into one area, business, client or life area.

        Answers the two questions section 3 says cut across the tree, for THIS
        scope: what needs my decision, and what did NOVA do. Both are read
        through the Data-Access Boundary, so both are bounded by RLS.
        """
        session, refusal = self._signed_in(session_id, execute=False)
        if refusal:
            return refusal
        if self._tree is None:
            return 404, _page("Not found", "<p>No scope tree is loaded.</p>")

        # Issuance is the first enforcement point: no grant, unknown scope or
        # inactive scope refuses here, before anything is rendered (I-14, I-80).
        try:
            token = self._context.issue_root(
                identity=session.identity, actor=session.actor,
                scope_path=scope_path, rights=frozenset({"read"}),
                ceiling=Risk.READ, ttl=60)
            self._pdp.authorize_data_read(token, scope_path)
        except (Denied, KeyError):
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        try:
            with self._boundary.open(token) as ch:
                pending = ch.fetch(
                    "SELECT count(*) FROM approval WHERE status = 'pending'")[0][0]
                tasks = ch.fetch(
                    "SELECT task_ref, title, due_on FROM task WHERE done_at IS NULL"
                    " ORDER BY due_on NULLS LAST, task_ref")
                # Notes, same shape as tasks: bounded by RLS to the token's
                # coverage, no application-side predicate. What James asked
                # NOVA to remember should be visible where he recorded it.
                notes = ch.fetch(
                    "SELECT item_ref, body FROM item ORDER BY created_at DESC, item_ref"
                    " LIMIT 20")
                # A-3a: reviewing audit records across MORE THAN ONE scope
                # requires step-up, and step-up does not exist yet. So this is
                # pinned to the exact scope rather than the token's coverage --
                # NOT an isolation control (RLS is still what bounds
                # reachability) but the line A-3a draws, enforced.
                activity = ch.fetch(
                    "SELECT written_at, category, detail FROM audit_record"
                    " WHERE scope_path = %s ORDER BY written_at DESC LIMIT 10",
                    (scope_path,))
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        children = [p for p in self._tree.children(scope_path)
                    if self._may_read(session, p)]
        return 200, _page(
            html.escape(_label(scope_path)),
            f"<p class=\"muted\">Active context: <code>{html.escape(scope_path)}</code></p>"
            + _talk_link(scope_path)
            + _decision_card(scope_path, pending)
            + _tasks_card(tasks, scope_path)
            + _notes_card(notes, scope_path)
            + _children_card(children)
            + _activity_card(activity, scope_path))

    def _may_read(self, session, scope_path: str) -> bool:
        """Navigation offers only what a grant already permits. This is a
        display filter -- entering the scope re-decides from scratch."""
        return self._tree is not None and self._tree.find_grant(
            session.identity, "read", "*", scope_path) is not None

    # -- conversation -------------------------------------------------------

    def _transcript(self, session, scope_path: str) -> list[dict]:
        return self._transcripts.setdefault((session.session_ref, scope_path), [])

    def talk_page(self, session_id: Optional[str], scope_path: str) -> tuple[int, str]:
        """The interface. One scope, one transcript, one input."""
        if self._conversation is None:
            return 404, _page("Not found", "<p>Conversation is not enabled.</p>")
        session, refusal = self._signed_in(session_id, execute=False)
        if refusal:
            return refusal
        # Entering the conversation is entering the scope: token issuance and
        # the PDP decide, exactly as for any page (I-14, I-80).
        try:
            token = self._context.issue_root(
                identity=session.identity, actor=session.actor,
                scope_path=scope_path, rights=frozenset({"read"}),
                ceiling=Risk.READ, ttl=60)
            self._pdp.authorize_data_read(token, scope_path)
        except (Denied, KeyError):
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")
        return 200, _talk_page(scope_path, self._transcript(session, scope_path))

    def talk_post(self, session_id: Optional[str], scope_path: str,
                  message: str) -> tuple[int, str]:
        """One turn. The model is never an authority: the turn's `state` is
        the server's account, and any proposal it produced is a pending
        approval that James decides on the existing approval surface."""
        if self._conversation is None:
            return 404, _page("Not found", "<p>Conversation is not enabled.</p>")
        session, refusal = self._signed_in(session_id, execute=False)
        if refusal:
            return refusal
        message = message.strip()[:2000]
        if not message:
            return 400, _page("Bad request", "<p>Say something.</p>")

        try:
            token = self._context.issue_root(
                identity=session.identity, actor=session.actor,
                scope_path=scope_path, rights=frozenset({"read"}),
                ceiling=Risk.READ, ttl=60)
        except (Denied, KeyError):
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        # Recording a proposal is EXECUTE-shaped, so it takes an EXECUTE
        # token -- issued only for a two-factor session (A-1) and only if the
        # grant exists. Absent either, the turn still answers; it just cannot
        # record a proposal, and says so.
        execute_token = None
        if session.is_multi_factor:
            try:
                execute_token = self._execute_token(session, scope_path)
            except (Denied, KeyError):
                execute_token = None

        turn = self._conversation.respond(token, scope_path, message,
                                          execute_token=execute_token)

        log = self._transcript(session, scope_path)
        log.append({"role": "james", "text": message})
        log.append({"role": "nova", "text": turn.reply, "state": turn.state,
                    "approval_id": turn.approval_id, "detail": turn.detail})
        status = 200 if turn.state in ("answered", "proposed") else 502
        if turn.state == "refused":
            status = 403
        return status, _talk_page(scope_path, log)

    # -- authentication routes (D-09) ---------------------------------------
    # These four are the ONLY places the browser talks to the authentication
    # service. Each returns (status, content_type, body, extra_headers).

    def auth_login_options(self) -> tuple[int, str, str, list[tuple[str, str]]]:
        ceremony_id, options = self._auth.login_options()
        return 200, "application/json", options, [self._cookie(CEREMONY_COOKIE, ceremony_id)]

    def auth_login(self, ceremony_id: Optional[str], credential_json: str,
                   surface: str) -> tuple[int, str, str, list[tuple[str, str]]]:
        try:
            token = self._auth.verify_login(ceremony_id, credential_json, surface)
        except AuthenticationFailed:
            # One answer for every failure. Which check failed is not the
            # caller's business.
            return 401, "application/json", '{"ok":false}', [self._clear(CEREMONY_COOKIE)]
        return 200, "application/json", '{"ok":true}', [
            self._cookie(SESSION_COOKIE, token), self._clear(CEREMONY_COOKIE)]

    def auth_enrol_options(self, session_id: Optional[str], identity: str,
                           actor: str) -> tuple[int, str, str, list[tuple[str, str]]]:
        """Bootstrap is open only while the actor has no passkey; after that,
        adding a device requires an authenticated two-factor session."""
        try:
            ceremony_id, options = self._auth.enrolment_options(
                identity, actor, authorized_by=self._auth.resolve(session_id))
        except AuthenticationFailed:
            return 403, "application/json", '{"ok":false}', []
        return 200, "application/json", options, [self._cookie(CEREMONY_COOKIE, ceremony_id)]

    def auth_enrol(self, ceremony_id: Optional[str], credential_json: str,
                   identity: str, actor: str,
                   label: str) -> tuple[int, str, str, list[tuple[str, str]]]:
        try:
            self._auth.verify_enrolment(ceremony_id, credential_json, identity, actor, label)
        except AuthenticationFailed:
            return 400, "application/json", '{"ok":false}', [self._clear(CEREMONY_COOKIE)]
        return 200, "application/json", '{"ok":true}', [self._clear(CEREMONY_COOKIE)]

    def auth_logout(self, session_id: Optional[str]) -> tuple[int, str, str, list[tuple[str, str]]]:
        session = self._auth.resolve(session_id)
        if session is not None:
            self._auth.revoke(session.session_ref)
        return 200, "text/html; charset=utf-8", _page(
            "Signed out", "<p>This session has ended.</p>"), [self._clear(SESSION_COOKIE)]

    def sessions_page(self, session_id: Optional[str]) -> tuple[int, str]:
        """A-6: James can see and end every active session."""
        session, refusal = self._signed_in(session_id, execute=True)
        if refusal:
            return refusal
        rows = "".join(
            f"<li><strong>{html.escape(s.surface or 'unnamed surface')}</strong> — "
            f"{html.escape(s.strength.replace('_', ' '))}, "
            f"expires {s.expires_at:%Y-%m-%d %H:%M} UTC"
            f"{' — this one' if s.session_ref == session.session_ref else ''}</li>"
            for s in self._auth.active_sessions(session.actor))
        return 200, _page("Sessions", f"<ul>{rows}</ul>"
                          "<form method=\"post\" action=\"/auth/logout\">"
                          "<button type=\"submit\">Sign out of this session</button></form>")

    def _cookie(self, name: str, value: str) -> tuple[str, str]:
        """HttpOnly so no script can read it; SameSite=Strict so no third-party
        page can drive a decision; Secure whenever the origin is https."""
        secure = "; Secure" if self._auth.origin.startswith("https://") else ""
        return ("Set-Cookie",
                f"{name}={value}; Path=/; HttpOnly; SameSite=Strict{secure}")

    def _clear(self, name: str) -> tuple[str, str]:
        return ("Set-Cookie", f"{name}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0")

    def items_page(self, session_id: Optional[str], scope_path: str) -> tuple[int, str]:
        """The one route. Returns (http_status, html_body)."""

        # -- identity ------------------------------------------------------
        session, refusal = self._signed_in(session_id, execute=False)
        if refusal:
            return refusal

        # -- Context Token, server-side only -------------------------------
        # Issuance is itself an enforcement point: no grant, inactive scope or
        # unknown scope refuses here (I-14, I-80), before the PDP is reached.
        try:
            token = self._context.issue_root(
                identity=session.identity, actor=session.actor,
                scope_path=scope_path, rights=frozenset({"read"}),
                ceiling=Risk.READ, ttl=60,
            )
        except (Denied, KeyError):
            # One page for "no grant", "no such scope" and "inactive": a
            # requester without access must not learn which of those it was.
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        # -- Data Access PEP (I-77; ADR 0045) ------------------------------
        try:
            self._pdp.authorize_data_read(token, scope_path)
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        # -- scope-bound read + audit, one transaction ---------------------
        try:
            with self._boundary.open(token) as ch:
                # Deliberately NO scope predicate: RLS is what bounds this.
                rows = ch.fetch(
                    "SELECT item_ref, body FROM item ORDER BY item_ref")
                # I-93: deterministic identity; the UNIQUE constraint makes a
                # retried write one logical record. Same transaction as the
                # read, so an unwritable record rolls the access back.
                event_identity = hashlib.sha256(
                    f"data_read:{token.trace_id}:{scope_path}".encode()
                ).hexdigest()[:32]
                ch.execute(
                    "INSERT INTO audit_record"
                    " (event_identity, writer, category, scope_path, trace_id, actor_ref, detail)"
                    " VALUES (%s,'W-1','data.read',%s,%s,%s,%s)"
                    " ON CONFLICT (event_identity) DO NOTHING",
                    (event_identity, scope_path, token.trace_id, session.actor,
                     f"items read count={len(rows)}"),
                )
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        # -- render --------------------------------------------------------
        items = "".join(
            f"<li><strong>{html.escape(r[0])}</strong> — {html.escape(r[1])}</li>"
            for r in rows
        ) or "<li>No items in this scope.</li>"
        body = (
            f"<p>Active context: <code>{html.escape(scope_path)}</code></p>"
            f"<ul>{items}</ul>"
        )
        return 200, _page(f"Items — {html.escape(scope_path)}", body)


    def propose_revocation(self, session_id: Optional[str], scope_path: str,
                           kind: str, ref: str) -> tuple[int, str]:
        """F-3: James points at a note or task; NOVA proposes revoking the
        authority that wrote it.

        PROPOSES ONLY. This records a pending approval and has no path to
        `RevocationRegistry` at all -- the revocation happens when James
        approves, through the write path, and nowhere else.

        THE IDENTITY IS DERIVED HERE, SERVER-SIDE, from the row itself through a
        scope-bound channel. The browser sends a row kind and a ref, never an
        execution identity: a caller naming the authority it wants revoked is
        exactly the shape every write branch already refuses. It is then PINNED
        into the approval's arguments, so `I-109`/`I-112` bind the authority
        James was shown rather than whatever the row names at decision time.

        `scope_path = %s` is bound from the CHANNEL, so the row must live in the
        scope James is standing in -- RLS bounds reachability, and this pins the
        statement to the one row he pointed at (`F-10`'s rule). A sibling's row
        is not reachable from here.
        """
        if self._writes is None or self._approvals is None:
            return 404, _page("Not found", "<p>Revocation is not enabled.</p>")
        session, refusal = self._signed_in(session_id, execute=True)
        if refusal:
            return refusal
        if session.identity != APPROVER_IDENTITY:
            return 403, _page("Not permitted",
                              "<p>Only James can propose a revocation.</p>")
        if kind not in ("item", "task"):
            return 400, _page("Bad request", "<p>Unknown row kind.</p>")

        try:
            # The ORDINARY write token -- `{"write"}` at `EXECUTE`, the same one
            # every other proposing route holds. Proposing reads one row and
            # writes a pending approval, so it needs `write`; it deliberately
            # does NOT carry `revoke`, because nothing irreversible happens
            # here and asking for that authority to propose would be asking for
            # more than the act needs. The `revoke` token is minted once, at the
            # decision, from the approval James actually decided.
            token = self._execute_token(session, scope_path)
            with self._boundary.open(token) as ch:
                table = "item" if kind == "item" else "task"
                column = "item_ref" if kind == "item" else "task_ref"
                rows = ch.fetch(
                    f"SELECT creating_authority FROM {table}"
                    f" WHERE {column} = %s AND scope_path = %s",
                    (ref, ch.scope_path))
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        # No row, or a row whose author was never recorded (`I-111` legacy).
        # Nothing to revoke and nothing to guess: fail closed.
        if not rows or rows[0][0] is None:
            return 404, _page(
                "Nothing to revoke",
                "<p>That row does not name an execution authority, so there is "
                "nothing here to revoke.</p>")
        execution_identity = rows[0][0]

        try:
            approval_id = self._approvals.propose_action(
                token, scope_path, REVOKE_AUTHORITY,
                {"execution_identity": execution_identity, "target_ref": ref},
                action_text=f"Permanently revoke the authority that wrote \u201c{ref}\u201d.",
                why_text=("Revoking marks everything that authority wrote as "
                          "impeached wherever it is read. It cannot be undone."),
                cost_text=("One revocation recorded. No content is deleted, "
                           "changed, or hidden."),
                if_wrong_text=("Content you still trust is labelled as written "
                               "by a revoked authority, and cannot be unmarked."))
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        return 200, _page(
            "Revocation proposed",
            "<p>Nothing has been revoked yet. This is waiting for your "
            "decision, and approving it will need your passkey.</p>"
            f"<p class=\"muted\"><code>{html.escape(approval_id)}</code></p>"
            f"<div class=\"actions\">"
            f"<a href=\"/scope{html.escape(scope_path)}/approvals\">"
            f"<button class=\"primary\" type=\"button\">Review it</button></a></div>")

    def write_item(self, session_id: Optional[str], scope_path: str,
                   item_ref: str, body: str) -> tuple[int, str]:
        """The write route. EXECUTE-class: the PDP's step 9 denies without
        James's approval, and the write lands under RLS WITH CHECK."""
        if self._writes is None:
            return 404, _page("Not found", "<p>Writes are not enabled.</p>")
        session, refusal = self._signed_in(session_id, execute=True)
        if refusal:
            return refusal
        if not item_ref:
            return 400, _page("Bad request", "<p>item_ref is required.</p>")

        # EXECUTE needs an EXECUTE-capable token; issuance still enforces
        # grants and scope existence first (I-14, I-80).
        try:
            token = self._context.issue_root(
                identity=session.identity, actor=session.actor,
                scope_path=scope_path, rights=frozenset({"write"}),
                ceiling=Risk.EXECUTE, ttl=60,
            )
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        try:
            outcome = self._writes.execute(token, scope_path, item_ref, body)
        except Denied as d:
            if d.invariant == "I-09":
                # Approval missing is the one denial worth distinguishing:
                # it is the caller's next legitimate step, not a secret.
                return 403, _page("Approval required",
                                  "<p>This action requires James's approval.</p>")
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        return 200, _page("Written",
                          f"<p>{html.escape(outcome.detail)} in "
                          f"<code>{html.escape(scope_path)}</code></p>")


def _scope_trail(scope_path: str) -> str:
    """BUSINESS / KAIRO / CLIENT A -- context, not a path. Every item on the
    attention page belongs to exactly one scope and says which."""
    return " / ".join(_label("/" + p) for p in scope_path.strip("/").split("/"))


def _attention_section(a) -> str:
    """One question, answered. No charts, no scores, no ranking -- ordering is
    by due date, which is a fact rather than a judgement."""
    if a.empty:
        return ("<section class=\"attention\"><h2 class=\"section\">Needs your attention</h2>"
                "<p class=\"muted\">Nothing right now.</p></section>")

    counts = []
    if a.approvals:
        counts.append(f"{len(a.approvals)} "
                      f"approval{'s' if len(a.approvals) != 1 else ''}")
    if a.overdue:
        counts.append(f"{len(a.overdue)} overdue")
    if a.due_soon:
        counts.append(f"{len(a.due_soon)} due soon")

    rows = []
    for ap in a.approvals:
        rows.append(
            f"<li class=\"att\"><a href=\"/scope{html.escape(ap.scope_path)}/approvals\">"
            f"<span class=\"flag\">approval</span>"
            f"<span class=\"what\">{html.escape(ap.action_text)}</span>"
            f"<span class=\"where\">{html.escape(_scope_trail(ap.scope_path))}</span>"
            f"</a></li>")
    for task in a.overdue + a.due_soon:
        flag = "overdue" if task.overdue else f"{task.due_on:%d %b}"
        cls = "flag late" if task.overdue else "flag"
        rows.append(
            f"<li class=\"att\"><a href=\"/scope{html.escape(task.scope_path)}\">"
            f"<span class=\"{cls}\">{html.escape(flag)}</span>"
            f"<span class=\"what\">{html.escape(task.title)}</span>"
            f"<span class=\"where\">{html.escape(_scope_trail(task.scope_path))}</span>"
            f"</a></li>")

    summary = html.escape(" \u00b7 ".join(counts))
    listing = "".join(rows)
    areas = len(a.scopes_read)
    return (f"<section class=\"attention\">"
            f"<h2 class=\"section\">Needs your attention</h2>"
            f"<p class=\"counts\">{summary}</p>"
            f"<ul class=\"attlist\">{listing}</ul>"
            f"<p class=\"muted\">Approvals and dated tasks, from the {areas} "
            f"area{'s' if areas != 1 else ''} you can reach. Activity across more "
            f"than one area needs a stronger sign-in (A-3a) and is not shown "
            f"here.</p></section>")


def _label(scope_path: str) -> str:
    """A scope path is machinery; a name is what James reads."""
    return scope_path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").upper()


def _footer_links() -> str:
    return ("<p class=\"muted\"><a href=\"/auth/sessions\">Sessions</a></p>")


def _talk_link(scope_path: str) -> str:
    """Conversation is the interface, so it is first on the page."""
    return (f"<article class=\"card\"><h2>Ask NOVA</h2>"
            f"<p class=\"muted\">Talk about what is in this scope, or ask for a "
            f"note to be recorded.</p><div class=\"actions\">"
            f"<a href=\"/scope{html.escape(scope_path)}/talk\">"
            f"<button class=\"primary\" type=\"button\">Open conversation</button>"
            f"</a></div></article>")


def _revoke_control(scope_path: str, kind: str, ref: str) -> str:
    """F-3's entry point: one control, on the row it concerns.

    A plain form, deliberately. It PROPOSES -- the irreversible act happens at
    the approval, behind a passkey -- so this button is no more dangerous than
    any other proposal, and dressing it up as one would misrepresent both ends.

    The browser sends the row KIND and REF it is looking at, never an execution
    identity: the server reads that off the row itself.
    """
    return (f"<form method=\"post\" action=\"/scope{html.escape(scope_path)}/revoke\" "
            f"style=\"display:inline\">"
            f"<input type=\"hidden\" name=\"kind\" value=\"{html.escape(kind)}\">"
            f"<input type=\"hidden\" name=\"ref\" value=\"{html.escape(ref)}\">"
            f"<button type=\"submit\">Revoke author</button></form>")


def _tasks_card(rows: list, scope_path: str) -> str:
    """The third of the three views USER_INTERFACE_ARCHITECTURE section 3
    names: what needs doing. Open tasks only, soonest first, overdue marked --
    a list James has to filter himself is a list he stops reading."""
    if not rows:
        return ("<article class=\"card\"><h2>Nothing to do here</h2>"
                "<p class=\"muted\">No open tasks in this scope.</p></article>")
    today = datetime.date.today()
    entries = []
    for ref, title, due in rows:
        if due is None:
            when = "<span class=\"muted\">no date</span>"
        elif due < today:
            when = f"<span class=\"overdue\">overdue \u2014 {due:%d %b}</span>"
        else:
            when = f"<span class=\"muted\">{due:%d %b}</span>"
        entries.append(f"<li>{html.escape(title)} {when} "
                       f"<code>{html.escape(ref)}</code> "
                       f"{_revoke_control(scope_path, 'task', ref)}</li>")
    return (f"<article class=\"card\"><h2>What needs doing</h2>"
            f"<ul>{''.join(entries)}</ul></article>")


def _notes_card(rows: list, scope_path: str) -> str:
    """What James asked NOVA to remember, in this scope. Absent entirely when
    empty -- an empty notes card is furniture, not information."""
    if not rows:
        return ""
    entries = "".join(
        f"<li>{html.escape(body)} <code>{html.escape(ref)}</code> "
        f"{_revoke_control(scope_path, 'item', ref)}</li>"
        for ref, body in rows)
    return (f"<article class=\"card\"><h2>Notes</h2><ul>{entries}</ul></article>")


def _decision_card(scope_path: str, pending: int) -> str:
    """Approvals are "surfaced where the work is… never buried"
    (USER_INTERFACE_ARCHITECTURE section 3)."""
    if not pending:
        return ("<article class=\"card\"><h2>Nothing needs your decision</h2>"
                "<p class=\"muted\">NOVA is not waiting on you here.</p></article>")
    word = "action" if pending == 1 else "actions"
    return (f"<article class=\"card\"><span class=\"risk\">awaiting you</span>"
            f"<h2>{pending} {word} need your decision</h2>"
            f"<div class=\"actions\"><a href=\"/scope{html.escape(scope_path)}/approvals\">"
            f"<button class=\"primary\" type=\"button\">Review</button></a></div></article>")


def _children_card(children: list) -> str:
    if not children:
        return ""
    items = "".join(
        f"<li><a href=\"/scope{html.escape(p)}\">{html.escape(_label(p))}</a></li>"
        for p in children)
    return f"<article class=\"card\"><h2>Inside</h2><ul>{items}</ul></article>"


def _activity_card(rows: list, scope_path: str) -> str:
    """What NOVA did here. One scope only -- A-3a puts cross-scope review
    behind step-up, and step-up does not exist yet, so the cross-scope view is
    deliberately absent rather than quietly ungated."""
    if not rows:
        entries = "<li class=\"muted\">Nothing has happened here yet.</li>"
    else:
        entries = "".join(
            f"<li><code>{when:%Y-%m-%d %H:%M}</code> — "
            f"<strong>{html.escape(category)}</strong> {html.escape(detail)}</li>"
            for when, category, detail in rows)
    return (f"<article class=\"card\"><h2>What NOVA did here</h2>"
            f"<ul>{entries}</ul>"
            f"<p class=\"muted\">This scope only. Reviewing activity across more "
            f"than one scope requires a stronger sign-in (A-3a), which NOVA does "
            f"not yet offer.</p></article>")


def _talk_page(scope_path: str, log: list) -> str:
    """Server-rendered transcript. The honesty rules live HERE: what James is
    told about actions comes from each turn's server-side `state`, never from
    model prose -- a model claiming "done" is just text in a bubble."""
    turns = []
    for entry in log:
        if entry["role"] == "james":
            turns.append(f"<div class=\"turn you\"><span class=\"label\">you</span>"
                         f"<p>{html.escape(entry['text'])}</p></div>")
            continue
        state = entry.get("state", "answered")
        text = html.escape(entry["text"]) if entry["text"] else ""
        block = [f"<div class=\"turn nova\"><span class=\"label\">nova</span>"]
        if text:
            block.append(f"<p>{text}</p>")
        if state == "proposed":
            # The card is the SERVER's statement. Deciding happens on the
            # existing approval surface -- no second approval path.
            block.append(
                f"<p class=\"pending\">I need your approval before I do this. "
                f"<a href=\"/scope{html.escape(scope_path)}/approvals\">"
                f"Review and decide</a>.</p>")
        elif state == "unavailable":
            block.append("<p class=\"pending\">I couldn\u2019t reach the model, so "
                         "nothing was answered and nothing was done.</p>")
        elif state == "refused":
            block.append("<p class=\"pending\">I couldn\u2019t complete that: the "
                         "request was not authorized. Nothing was done.</p>")
        if entry.get("detail") and state in ("answered",):
            block.append(f"<p class=\"muted\">{html.escape(entry['detail'])}</p>")
        block.append("</div>")
        turns.append("".join(block))
    chat = "".join(turns) or "<p class=\"muted\">Ask NOVA about this scope.</p>"
    body = (
        f"<p class=\"muted\">Active context: <code>{html.escape(scope_path)}</code>"
        f" \u2014 <a href=\"/scope{html.escape(scope_path)}\">back to this scope</a></p>"
        f"<section class=\"chat\" aria-label=\"Conversation\">"
        f"{chat}"
        f"</section>"
        f"<form method=\"post\" action=\"/scope{html.escape(scope_path)}/talk\" class=\"say\">"
        f"<label class=\"label\" for=\"m\">Message</label>"
        f"<input id=\"m\" name=\"message\" required maxlength=\"2000\" autocomplete=\"off\">"
        f"<button type=\"submit\" class=\"primary\">Send</button></form>")
    return _page(f"NOVA \u2014 {html.escape(_label(scope_path))}", body)


def _approval_card(r, content_leaves=frozenset(), step_up: bool = False) -> str:
    """The five things USER_INTERFACE_ARCHITECTURE.md section 6 requires, the
    EXACT CONTENT the action will persist (ADR 0048), and the statement that
    NOVA is not the approving authority (I-09).

    Approve and Deny are separate forms: one action each, no default, and no
    script. The browser posts a decision; it does not make one.

    CONTENT VISIBILITY (ADR 0048, properties 1 and 2). Every EXPRESSIVE
    argument is rendered here, VERBATIM and COMPLETE. Before this, a note's
    body was stored on the approval row and never shown: James approved
    `Write item "x" in this scope.` while the bytes that would be persisted --
    written by a model, from context he could not see -- stayed invisible. An
    approval given without sight of the content cannot be evidence about the
    content, and ADR 0048 makes that the difference between a trusted row and
    an untrusted one.

    NO TRUNCATION, and no summary. A shortened body is a different body, and
    approving it would vouch for something other than what is stored. The
    marker grammar already caps a body at 1000 characters and a title at 300
    (`conversation.py`), so "render all of it" is a bounded promise.

    `content_leaves` is supplied by the caller from `WritePath.content_leaves`
    rather than decided here -- one definition of "what is content", shared
    with the elevation check, so this page cannot show less than the check
    assumes was shown.
    """
    def field(label: str, value: str) -> str:
        return (f"<div class=\"field\"><span class=\"label\">{html.escape(label)}</span>"
                f"<span>{html.escape(value)}</span></div>")

    arguments = r.plan_arguments()
    content = "".join(
        field(f"exact {leaf.replace('_', ' ')} to be saved", str(arguments.get(leaf, "")))
        for leaf in sorted(content_leaves) if leaf in arguments)

    # I-40: where the content derives from an EXTERNAL source, approving names
    # that source. James is told which -- an approval naming a source he was
    # never shown would satisfy the policy while defeating its purpose.
    taint = r.taint()
    sources = sorted(taint.external_sources()) if taint is not None else []
    source_field = (field("outside sources this draws on", ", ".join(sources))
                    if sources else "")

    # I-67 / A-3. Said before the button, not after it: James should know the
    # action cannot be undone BEFORE he reaches for his passkey, not while the
    # authenticator is already prompting him.
    #
    # The Approve button becomes a script hook; Decline stays a plain form,
    # because declining is not consequential and must never be harder than
    # approving. If the script does not run, Approve submits nothing and the
    # server-side gate refuses anyway -- the page failing closed twice.
    action = f"/scope{html.escape(r.scope_path)}/approvals/{html.escape(r.approval_id)}"
    if step_up:
        notice = ("<p class=\"muted\">This action cannot be undone, so approving "
                  "it needs your passkey again — a valid sign-in is not enough.</p>")
        approve_control = f"""
        <form method="post" action="{action}" id="f-{html.escape(r.approval_id)}">
          <input type="hidden" name="decision" value="approve">
          <input type="hidden" name="assertion" value="">
          <button type="button" class="primary"
                  onclick="stepUpApprove('{html.escape(r.approval_id)}','{action}')">
            Approve with passkey</button>
        </form>"""
    else:
        notice = ""
        approve_control = f"""
        <form method="post" action="{action}">
          <input type="hidden" name="decision" value="approve">
          <button type="submit" class="primary">Approve</button>
        </form>"""

    return f"""
    <article class="card">
      <span class="risk">{html.escape(r.risk_class)}</span>
      <h2>{html.escape(r.action_text)}</h2>
      {content}
      {source_field}
      {field("in scope", r.scope_path)}
      {field("why approval is needed", r.why_text)}
      {field("what it costs", r.cost_text)}
      {field("if this is wrong", r.if_wrong_text)}
      {field("requested by", r.requested_by)}
      <p class="muted">Only James can approve this. NOVA prepared the request;
         it cannot approve it.</p>
      {notice}
      <div class="actions">
        {approve_control}
        <form method="post" action="{action}">
          <input type="hidden" name="decision" value="deny">
          <button type="submit">Decline</button>
        </form>
      </div>
      <p class="muted" id="s-{html.escape(r.approval_id)}" role="status"></p>
    </article>"""


# Layout only. Every colour, size and space is a Section 15 token
# (ADR 0041) -- no visual value is declared here.
_STYLE = """
body { background: var(--nova-color-surface-base); color: var(--nova-color-text-primary);
       font-family: var(--nova-type-family-ui); font-size: var(--nova-type-size-body);
       line-height: var(--nova-type-leading-normal); margin: 0;
       padding: var(--nova-space-section); }
h1 { font-size: var(--nova-type-size-title); margin: 0 0 var(--nova-space-gutter) 0; }
h2 { font-size: var(--nova-type-size-lead); margin: 0 0 var(--nova-space-snug) 0; }
code { font-family: var(--nova-type-family-code); }
.muted { color: var(--nova-color-text-muted); font-size: var(--nova-type-size-caption); }
.card { background: var(--nova-color-surface-raised);
        border: var(--nova-border-width) solid var(--nova-color-border-strong);
        border-radius: var(--nova-radius-card); padding: var(--nova-space-gutter);
        margin-bottom: var(--nova-space-gutter); box-shadow: var(--nova-elevation-modal);
        max-width: 46rem; }
.risk { display: inline-block; color: var(--nova-color-risk-contextual);
        background: var(--nova-color-risk-contextual-soft);
        border: var(--nova-border-width) solid var(--nova-color-risk-contextual);
        border-radius: var(--nova-radius-pill);
        padding: var(--nova-space-tight) var(--nova-space-snug);
        font-size: var(--nova-type-size-caption);
        letter-spacing: var(--nova-type-tracking-label); text-transform: uppercase;
        margin-bottom: var(--nova-space-snug); }
.field { display: flex; flex-direction: column; gap: var(--nova-space-tight);
         margin-bottom: var(--nova-space-snug); }
.label { color: var(--nova-color-text-muted); font-size: var(--nova-type-size-caption);
         letter-spacing: var(--nova-type-tracking-label); text-transform: uppercase; }
.actions { display: flex; gap: var(--nova-space-tight);
           margin-top: var(--nova-space-gutter); }
button { font-family: var(--nova-type-family-ui); font-size: var(--nova-type-size-body);
         color: var(--nova-color-text-secondary);
         background: var(--nova-color-surface-inset);
         border: var(--nova-border-width) solid var(--nova-color-border-strong);
         border-radius: var(--nova-radius-control);
         padding: var(--nova-space-tight) var(--nova-space-gutter);
         min-height: var(--nova-control-target); cursor: pointer; }
button.primary { background: var(--nova-color-accent-base);
                 color: var(--nova-color-text-oncolor);
                 border-color: var(--nova-color-accent-base); }
.chat { display: flex; flex-direction: column; gap: var(--nova-space-snug);
        max-width: 46rem; margin-bottom: var(--nova-space-gutter); }
.turn { background: var(--nova-color-surface-raised);
        border: var(--nova-border-width) solid var(--nova-color-border-strong);
        border-radius: var(--nova-radius-card);
        padding: var(--nova-space-snug) var(--nova-space-gutter); }
.turn.you { background: var(--nova-color-surface-inset); }
.turn p { margin: var(--nova-space-tight) 0 0 0; }
.pending { color: var(--nova-color-risk-contextual); }
.overdue { color: var(--nova-color-risk-contextual); }
.section { font-size: var(--nova-type-size-lead);
           letter-spacing: var(--nova-type-tracking-label); text-transform: uppercase;
           color: var(--nova-color-text-muted); margin: 0 0 var(--nova-space-snug) 0; }
.attention { max-width: 46rem; margin-bottom: var(--nova-space-section); }
.counts { color: var(--nova-color-text-secondary); margin: 0 0 var(--nova-space-snug) 0; }
.attlist { list-style: none; padding: 0; margin: 0;
           border-top: var(--nova-border-width) solid var(--nova-color-border-subtle); }
.att a { display: grid; grid-template-columns: 7rem 1fr auto;
         gap: var(--nova-space-gutter); align-items: baseline;
         padding: var(--nova-space-snug) 0; text-decoration: none;
         color: var(--nova-color-text-primary);
         border-bottom: var(--nova-border-width) solid var(--nova-color-border-subtle);
         min-height: var(--nova-control-target); }
.att a:hover .what { text-decoration: underline; }
.flag { color: var(--nova-color-text-muted); font-size: var(--nova-type-size-caption);
        letter-spacing: var(--nova-type-tracking-label); text-transform: uppercase; }
.flag.late { color: var(--nova-color-risk-contextual); }
.where { color: var(--nova-color-text-muted); font-size: var(--nova-type-size-caption);
         letter-spacing: var(--nova-type-tracking-label); text-transform: uppercase; }
.card.area { padding: var(--nova-space-snug) var(--nova-space-gutter); }
.card.area h3 { font-size: var(--nova-type-size-lead); margin: 0; }
.att a:focus-visible { outline: var(--nova-border-emphasis) solid
                       var(--nova-color-border-accent); outline-offset: 0; }
@media (max-width: 40rem) {
  .att a { grid-template-columns: 1fr; gap: var(--nova-space-tight); }
}
.say { display: flex; gap: var(--nova-space-tight); align-items: center;
       max-width: 46rem; }
.say input { flex: 1; font-family: var(--nova-type-family-ui);
       font-size: var(--nova-type-size-body);
       color: var(--nova-color-text-primary);
       background: var(--nova-color-surface-inset);
       border: var(--nova-border-width) solid var(--nova-color-border-strong);
       border-radius: var(--nova-radius-control);
       padding: var(--nova-space-tight) var(--nova-space-snug);
       min-height: var(--nova-control-target); }
button:focus-visible, .say input:focus-visible { outline: var(--nova-border-emphasis) solid
                       var(--nova-color-border-accent);
                       outline-offset: var(--nova-space-tight); }
"""


# The ONE page in NOVA that carries a script, and the reason is not a
# preference: WebAuthn is a browser API and there is no server-rendered way to
# reach an authenticator. It is a light island in an otherwise server-rendered
# application (D-13 unchanged -- no framework is introduced), and it holds no
# authority: it moves bytes between the authenticator and the server, and the
# server decides.
#
# A-5 is why no identity appears anywhere below: one human identity is James's,
# so there is no username field, and the login ceremony names no user at all.
_LOGIN_SCRIPT = """
const b64u = {
  dec: s => Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')), c => c.charCodeAt(0)),
  enc: b => btoa(String.fromCharCode(...new Uint8Array(b)))
              .replace(/\+/g,'-').replace(/\//g,'_').replace(/=+$/,'')
};
async function ceremony(optionsUrl, submitUrl, kind) {
  const status = document.getElementById('status');
  try {
    const options = await (await fetch(optionsUrl)).json();
    options.challenge = b64u.dec(options.challenge);
    if (options.user) options.user.id = b64u.dec(options.user.id);
    for (const list of [options.allowCredentials, options.excludeCredentials])
      if (list) list.forEach(c => c.id = b64u.dec(c.id));
    const credential = kind === 'create'
      ? await navigator.credentials.create({ publicKey: options })
      : await navigator.credentials.get({ publicKey: options });
    const r = credential.response;
    const payload = {
      id: credential.id, rawId: b64u.enc(credential.rawId), type: credential.type,
      clientExtensionResults: {},
      response: kind === 'create'
        ? { clientDataJSON: b64u.enc(r.clientDataJSON),
            attestationObject: b64u.enc(r.attestationObject) }
        : { clientDataJSON: b64u.enc(r.clientDataJSON),
            authenticatorData: b64u.enc(r.authenticatorData),
            signature: b64u.enc(r.signature),
            userHandle: r.userHandle ? b64u.enc(r.userHandle) : null }
    };
    const done = await fetch(submitUrl, { method: 'POST', body: JSON.stringify(payload) });
    if (!done.ok) { status.textContent = 'Not accepted.'; return; }
    status.textContent = kind === 'create' ? 'Passkey registered. Sign in.' : 'Signed in.';
    if (kind === 'get') location.href = '/auth/sessions';
  } catch (e) { status.textContent = 'Not accepted.'; }
}
"""


# The SECOND script island, and the last one. Same reason as the first: an
# authenticator is reachable only through a browser API. It holds no authority
# whatsoever -- it moves an assertion from the authenticator into a form field
# the server then verifies, and every decision about that assertion is made in
# `verify_step_up`.
#
# It names no approval it was not handed, chooses no purpose (the server derives
# that from the URL), and cannot make the request succeed: a page that skipped
# this entirely would post no assertion and be refused server-side.
#
# The b64url helpers are repeated from `_LOGIN_SCRIPT` rather than shared. That
# is deliberate: factoring them out would edit the login path, which this change
# is required to leave exactly as it was, and eight lines of base64 is a cheaper
# price than a regression in the only route that establishes a session.
_STEP_UP_SCRIPT = """
const b64uS = {
  dec: s => Uint8Array.from(atob(s.replace(/-/g,'+').replace(/_/g,'/')), c => c.charCodeAt(0)),
  enc: b => btoa(String.fromCharCode(...new Uint8Array(b)))
              .replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'')
};
async function stepUpApprove(approvalId, action) {
  const status = document.getElementById('s-' + approvalId);
  const form = document.getElementById('f-' + approvalId);
  status.textContent = 'Waiting for your passkey…';
  try {
    const options = await (await fetch(action + '/stepup/options')).json();
    options.challenge = b64uS.dec(options.challenge);
    if (options.allowCredentials)
      options.allowCredentials.forEach(c => c.id = b64uS.dec(c.id));
    const credential = await navigator.credentials.get({ publicKey: options });
    const r = credential.response;
    form.assertion.value = JSON.stringify({
      id: credential.id, rawId: b64uS.enc(credential.rawId), type: credential.type,
      clientExtensionResults: {},
      response: { clientDataJSON: b64uS.enc(r.clientDataJSON),
                  authenticatorData: b64uS.enc(r.authenticatorData),
                  signature: b64uS.enc(r.signature),
                  userHandle: r.userHandle ? b64uS.enc(r.userHandle) : null }
    });
    form.submit();
  } catch (e) { status.textContent = 'Not accepted. Nothing has been done.'; }
}
"""


def _login_page() -> str:
    return _page("Sign in to NOVA",
                 "<p>NOVA authenticates with a passkey. There is no password to "
                 "phish and nothing typed that could be replayed.</p>"
                 "<div class=\"actions\">"
                 "<button class=\"primary\" onclick=\"ceremony("
                 "'/auth/login/options','/auth/login','get')\">Sign in</button>"
                 "<button onclick=\"ceremony("
                 "'/auth/enrol/options','/auth/enrol','create')\">Register a passkey</button>"
                 "</div><p class=\"muted\" id=\"status\" role=\"status\"></p>"
                 f"<script>{_LOGIN_SCRIPT}</script>")


def _page(title: str, body: str) -> str:
    """Server-rendered, self-contained, no scripts, no token material."""
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{title}</title>"
        "<link rel=\"stylesheet\" href=\"/static/tokens.css\">"
        f"<style>{_STYLE}</style></head>"
        f"<body><main><h1>{title}</h1>{body}</main></body></html>"
    )


# ---------------------------------------------------------------------------
# Minimal HTTP host -- stdlib only, no framework, no router architecture.
# ---------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    seam: Seam  # set by serve()

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        # Route on the path alone. No handler reads a query parameter -- every
        # decision comes from the session and the tree -- so a query string
        # must neither reach one nor turn a valid route into a 404.
        self.path = self.path.split("?", 1)[0]

        if self.path == "/auth/login/options":
            self._respond_raw(*_Handler.seam.auth_login_options())
            return
        if self.path == "/auth/login":
            self._respond(200, _login_page())
            return
        if self.path.startswith("/auth/enrol/options"):
            self._respond_raw(*_Handler.seam.auth_enrol_options(
                self._session(), APPROVER_IDENTITY, APPROVER_IDENTITY))
            return
        if self.path == "/auth/sessions":
            self._respond(*_Handler.seam.sessions_page(self._session()))
            return

        if self.path == "/" or self.path == "":
            self._respond(*_Handler.seam.home_page(self._session()))
            return

        if self.path == "/static/tokens.css":
            try:
                css = TOKENS_CSS.read_bytes()
            except OSError:
                self._respond(404, _page("Not found", "<p>No stylesheet.</p>"))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/css; charset=utf-8")
            self.send_header("Content-Length", str(len(css)))
            self.end_headers()
            self.wfile.write(css)
            return

        # /scope/<path>/approvals/<approval_id>/stepup/options -- BEFORE the
        # approvals-list route below, which would otherwise not match, and
        # before the catch-all /scope/<path>. I-67's ceremony, and the only
        # GET that starts one outside /auth.
        suffix = "/stepup/options"
        if self.path.startswith("/scope/") and self.path.endswith(suffix) \
                and "/approvals/" in self.path:
            head, _, tail = self.path.partition("/approvals/")
            scope_path = "/" + head[len("/scope/"):].strip("/")
            approval_id = tail[:-len(suffix)]
            self._respond_raw(*_Handler.seam.approval_step_up_options(
                self._session(), scope_path, approval_id))
            return

        if self.path.startswith("/scope/") and self.path.endswith("/approvals"):
            scope_path = "/" + self.path[len("/scope/"):-len("/approvals")].strip("/")
            status, body = _Handler.seam.approvals_page(self._session(), scope_path)
            self._respond(status, body)
            return

        if self.path.startswith("/scope/") and self.path.endswith("/talk"):
            scope_path = "/" + self.path[len("/scope/"):-len("/talk")].strip("/")
            self._respond(*_Handler.seam.talk_page(self._session(), scope_path))
            return

        prefix, suffix = "/scope/", "/items"
        if self.path.startswith(prefix) and self.path.endswith(suffix):
            scope_path = "/" + self.path[len(prefix):-len(suffix)].strip("/")
            self._respond(*_Handler.seam.items_page(self._session(), scope_path))
            return

        # /scope/<path> -- one scope. Last, so the specific routes above win.
        if self.path.startswith(prefix):
            scope_path = "/" + self.path[len(prefix):].strip("/")
            self._respond(*_Handler.seam.scope_page(self._session(), scope_path))
            return

        self._respond(404, _page("Not found", "<p>Unknown route.</p>"))

    def _cookie(self, wanted: str) -> Optional[str]:
        for part in self.headers.get("Cookie", "").split(";"):
            name, _, value = part.strip().partition("=")
            if name == wanted:
                return value
        return None

    def _session(self) -> Optional[str]:
        return self._cookie(SESSION_COOKIE)

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        import urllib.parse

        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode()

        if self.path == "/auth/login":
            self._respond_raw(*_Handler.seam.auth_login(
                self._cookie(CEREMONY_COOKIE), raw,
                surface=self.headers.get("User-Agent", "")[:120]))
            return
        if self.path.startswith("/auth/enrol"):
            self._respond_raw(*_Handler.seam.auth_enrol(
                self._cookie(CEREMONY_COOKIE), raw,
                APPROVER_IDENTITY, APPROVER_IDENTITY, label=""))
            return
        if self.path == "/auth/logout":
            self._respond_raw(*_Handler.seam.auth_logout(self._session()))
            return

        form = urllib.parse.parse_qs(raw)

        if self.path.startswith("/scope/") and self.path.endswith("/talk"):
            scope_path = "/" + self.path[len("/scope/"):-len("/talk")].strip("/")
            message = (form.get("message") or [""])[0]
            self._respond(*_Handler.seam.talk_post(self._session(), scope_path, message))
            return

        # /scope/<path>/revoke -- F-3. PROPOSES; it revokes nothing.
        if self.path.startswith("/scope/") and self.path.endswith("/revoke"):
            scope_path = "/" + self.path[len("/scope/"):-len("/revoke")].strip("/")
            self._respond(*_Handler.seam.propose_revocation(
                self._session(), scope_path,
                (form.get("kind") or [""])[0], (form.get("ref") or [""])[0]))
            return

        # /scope/<path>/approvals/<approval_id>
        if self.path.startswith("/scope/") and "/approvals/" in self.path:
            head, _, approval_id = self.path.partition("/approvals/")
            scope_path = "/" + head[len("/scope/"):].strip("/")
            approve = (form.get("decision") or [""])[0] == "approve"
            # The step-up assertion, if the page collected one. The CEREMONY id
            # comes from the cookie, exactly as login's does -- never from the
            # form, so the browser cannot pair an assertion with a ceremony it
            # chose. Empty for every ordinary approval, which is why nothing
            # about the existing flow changes.
            status, page = _Handler.seam.decide_page(
                self._session(), scope_path, approval_id, approve,
                ceremony_id=self._cookie(CEREMONY_COOKIE),
                assertion=(form.get("assertion") or [""])[0])
            self._respond(status, page)
            return

        prefix, suffix = "/scope/", "/items"
        if not (self.path.startswith(prefix) and self.path.endswith(suffix)):
            self._respond(404, _page("Not found", "<p>Unknown route.</p>"))
            return
        scope_path = "/" + self.path[len(prefix):-len(suffix)].strip("/")

        item_ref = (form.get("item_ref") or [""])[0]
        body = (form.get("body") or [""])[0]
        status, page = _Handler.seam.write_item(self._session(), scope_path, item_ref, body)
        self._respond(status, page)

    def _respond(self, status: int, body: str) -> None:
        self._respond_raw(status, "text/html; charset=utf-8", body, [])

    def _respond_raw(self, status: int, content_type: str, body: str,
                     extra_headers: list) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        # The browser is a renderer, not a store of authority.
        self.send_header("Cache-Control", "no-store")
        for name, value in extra_headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:  # tests stay quiet
        pass


def serve(seam: Seam, port: int = 0) -> tuple[http.server.ThreadingHTTPServer, int]:
    """Start the seam on localhost. Returns (server, bound_port)."""
    _Handler.seam = seam
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, server.server_address[1]
