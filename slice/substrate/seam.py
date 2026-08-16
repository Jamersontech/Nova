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

WHAT IS A STAND-IN
------------------
Authentication. `SessionStore` maps an opaque id to a server-side actor; the
real provider is D-09 (deferred) and A-1/A-2's factors cannot be satisfied by
a test fixture. The stand-in is confined to this one class so the D-09
resolution replaces it without touching the chain below.
"""

from __future__ import annotations

import dataclasses
import hashlib
import html
import http.server
import secrets
import threading
from typing import Optional

from ..core.context_service import ContextService
from ..core.policy import PolicyDecisionPoint
from ..core.types import Denied, Risk
from .boundary import DataAccessBoundary


@dataclasses.dataclass(frozen=True)
class SessionRecord:
    """Server-side identity. The browser sees only the opaque id."""
    session_id: str
    identity: str      # the grantee the PDP checks grants against (I-10)
    actor: str         # explicit actor identity -- never assumed (Q-04)


class SessionStore:
    """Opaque-cookie session store. STAND-IN for D-09 -- see module docstring."""

    def __init__(self) -> None:
        self._sessions: dict[str, SessionRecord] = {}

    def create(self, identity: str, actor: str) -> str:
        sid = secrets.token_urlsafe(32)
        self._sessions[sid] = SessionRecord(sid, identity, actor)
        return sid

    def resolve(self, session_id: Optional[str]) -> Optional[SessionRecord]:
        if not session_id:
            return None
        return self._sessions.get(session_id)


class Seam:
    """The wiring. Holds no authority of its own: every decision below is
    made by the Context service, the PDP, the boundary or RLS."""

    def __init__(self, context: ContextService, pdp: PolicyDecisionPoint,
                 boundary: DataAccessBoundary, sessions: SessionStore,
                 write_path=None):
        self._context = context
        self._pdp = pdp
        self._boundary = boundary
        self._sessions = sessions
        # Optional: the consequence-producing write path (write_path.WritePath).
        # The read seam predates it and works without it.
        self._writes = write_path

    def items_page(self, session_id: Optional[str], scope_path: str) -> tuple[int, str]:
        """The one route. Returns (http_status, html_body)."""

        # -- identity ------------------------------------------------------
        session = self._sessions.resolve(session_id)
        if session is None:
            return 401, _page("Not signed in", "<p>No session.</p>")

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
        session = self._sessions.resolve(session_id)
        if session is None:
            return 401, _page("Not signed in", "<p>No session.</p>")
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


def _page(title: str, body: str) -> str:
    """Server-rendered, self-contained, no scripts, no token material."""
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        f"<title>{title}</title></head><body><h1>{title}</h1>{body}</body></html>"
    )


# ---------------------------------------------------------------------------
# Minimal HTTP host -- stdlib only, no framework, no router architecture.
# ---------------------------------------------------------------------------

class _Handler(http.server.BaseHTTPRequestHandler):
    seam: Seam  # set by serve()

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        prefix, suffix = "/scope/", "/items"
        if not (self.path.startswith(prefix) and self.path.endswith(suffix)):
            self._respond(404, _page("Not found", "<p>Unknown route.</p>"))
            return
        scope_path = "/" + self.path[len(prefix):-len(suffix)].strip("/")

        cookie = self.headers.get("Cookie", "")
        session_id = None
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "nova_session":
                session_id = value
        status, body = _Handler.seam.items_page(session_id, scope_path)
        self._respond(status, body)

    def do_POST(self) -> None:  # noqa: N802 (stdlib naming)
        import urllib.parse
        prefix, suffix = "/scope/", "/items"
        if not (self.path.startswith(prefix) and self.path.endswith(suffix)):
            self._respond(404, _page("Not found", "<p>Unknown route.</p>"))
            return
        scope_path = "/" + self.path[len(prefix):-len(suffix)].strip("/")

        length = int(self.headers.get("Content-Length", "0") or "0")
        form = urllib.parse.parse_qs(self.rfile.read(length).decode())
        item_ref = (form.get("item_ref") or [""])[0]
        body = (form.get("body") or [""])[0]

        cookie = self.headers.get("Cookie", "")
        session_id = None
        for part in cookie.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "nova_session":
                session_id = value
        status, page = _Handler.seam.write_item(session_id, scope_path, item_ref, body)
        self._respond(status, page)

    def _respond(self, status: int, body: str) -> None:
        data = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        # The browser is a renderer, not a store of authority.
        self.send_header("Cache-Control", "no-store")
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
