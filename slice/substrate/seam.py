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


# I-09: only James approves. The identity that may decide, checked server-side.
APPROVER_IDENTITY = "james"

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
                 write_path=None, approvals=None):
        self._context = context
        self._pdp = pdp
        self._boundary = boundary
        self._auth = auth
        # Optional: the consequence-producing write path (write_path.WritePath).
        # The read seam predates it and works without it.
        self._writes = write_path
        # Optional: the approval experience (approval_flow.ApprovalService).
        self._approvals = approvals

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

    def _execute_token(self, session, scope_path: str):
        """An EXECUTE-ceiling token. Issuance enforces grants first (I-14)."""
        return self._context.issue_root(
            identity=session.identity, actor=session.actor,
            scope_path=scope_path, rights=frozenset({"write"}),
            ceiling=Risk.EXECUTE, ttl=60,
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
            requests = self._approvals.pending(token)
        except Denied:
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        if not requests:
            body = "<p class=\"muted\">Nothing needs your decision here.</p>"
        else:
            body = "".join(_approval_card(r) for r in requests)
        return 200, _page(f"Approvals — {html.escape(scope_path)}",
                          f"<p class=\"muted\">Active context: "
                          f"<code>{html.escape(scope_path)}</code></p>{body}")

    def decide_page(self, session_id: Optional[str], scope_path: str,
                    approval_id: str, approve: bool) -> tuple[int, str]:
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
            status, outcome = self._approvals.decide(
                token, approval_id, approve, decided_by=session.actor)
        except Denied as d:
            if d.invariant == "I-09":
                return 409, _page("Already decided",
                                  "<p>This approval has already been decided.</p>")
            return 403, _page("Not available", "<p>This scope is not available to you.</p>")

        if status == "denied":
            return 200, _page("Denied", "<p>Nothing was done. The action was declined.</p>")
        return 200, _page("Approved",
                          f"<p>{html.escape(outcome.detail)} in "
                          f"<code>{html.escape(scope_path)}</code></p>")

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


def _approval_card(r) -> str:
    """The five things USER_INTERFACE_ARCHITECTURE.md section 6 requires, and
    the statement that NOVA is not the approving authority (I-09).

    Approve and Deny are separate forms: one action each, no default, and no
    script. The browser posts a decision; it does not make one.
    """
    def field(label: str, value: str) -> str:
        return (f"<div class=\"field\"><span class=\"label\">{html.escape(label)}</span>"
                f"<span>{html.escape(value)}</span></div>")

    return f"""
    <article class="card">
      <span class="risk">{html.escape(r.risk_class)}</span>
      <h2>{html.escape(r.action_text)}</h2>
      {field("in scope", r.scope_path)}
      {field("why approval is needed", r.why_text)}
      {field("what it costs", r.cost_text)}
      {field("if this is wrong", r.if_wrong_text)}
      {field("requested by", r.requested_by)}
      <p class="muted">Only James can approve this. NOVA prepared the request;
         it cannot approve it.</p>
      <div class="actions">
        <form method="post" action="/scope{html.escape(r.scope_path)}/approvals/{html.escape(r.approval_id)}">
          <input type="hidden" name="decision" value="approve">
          <button type="submit" class="primary">Approve</button>
        </form>
        <form method="post" action="/scope{html.escape(r.scope_path)}/approvals/{html.escape(r.approval_id)}">
          <input type="hidden" name="decision" value="deny">
          <button type="submit">Decline</button>
        </form>
      </div>
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
button:focus-visible { outline: var(--nova-border-emphasis) solid
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

        if self.path.startswith("/scope/") and self.path.endswith("/approvals"):
            scope_path = "/" + self.path[len("/scope/"):-len("/approvals")].strip("/")
            status, body = _Handler.seam.approvals_page(self._session(), scope_path)
            self._respond(status, body)
            return

        prefix, suffix = "/scope/", "/items"
        if not (self.path.startswith(prefix) and self.path.endswith(suffix)):
            self._respond(404, _page("Not found", "<p>Unknown route.</p>"))
            return
        scope_path = "/" + self.path[len(prefix):-len(suffix)].strip("/")

        status, body = _Handler.seam.items_page(self._session(), scope_path)
        self._respond(status, body)

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

        # /scope/<path>/approvals/<approval_id>
        if self.path.startswith("/scope/") and "/approvals/" in self.path:
            head, _, approval_id = self.path.partition("/approvals/")
            scope_path = "/" + head[len("/scope/"):].strip("/")
            approve = (form.get("decision") or [""])[0] == "approve"
            status, page = _Handler.seam.decide_page(
                self._session(), scope_path, approval_id, approve)
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
