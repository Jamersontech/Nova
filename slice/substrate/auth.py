"""Real authentication (D-09): WebAuthn passkeys, opaque server-side sessions.

This replaces the last stand-in in NOVA's end-to-end security path. Everything
below it -- Context Token issuance, the PDP, the Data-Access Boundary, RLS --
is unchanged. Authentication terminates at ONE fact:

    an authenticated server-side identity

and hands that fact to the seam. It decides nothing else. `I-13` restated:
passing authentication grants nothing.

WHY WEBAUTHN
------------
`A-2` requires a primary factor that resists replay by an attacker who has
induced James to authenticate against a system they control. WebAuthn provides
that by construction rather than by policy: the authenticator signs over the
hash of the relying-party ID and the browser's own origin, so an assertion
produced at an attacker's origin does not verify here. No shared secret is
ever transmitted, so there is nothing to phish.

`A-1` requires two independent factors for any session that can reach EXECUTE.
A passkey with user verification supplies possession (the authenticator) and a
second factor checked on the device (biometric or PIN). The authenticator
reports this in the UV bit of authenticatorData, which is inside the signed
payload. So the strength of a session is not asserted by the client -- it is
read out of a signature the server verified.

    UV set     -> multi_factor  -> may reach EXECUTE (approvals, writes)
    UV not set -> single_factor -> READ only, must step up (A-1, A-3)

WHAT IS NOT BUILT, DELIBERATELY
-------------------------------
No user administration, no organisations, no invitations, no SSO, no OAuth
layer, no account dashboard. `A-5` -- one human identity is James's -- makes
all of that premature, and `Q-04` says a multi-user PRODUCT is not to be built.

THE PROTOCOL IS NOT IMPLEMENTED HERE
------------------------------------
Signature verification, COSE key decoding, RP-ID hashing, flag and counter
checks are `py_webauthn`'s. Writing those by hand would be the single worst
place in this repository to have an original idea.

WHAT THIS MODULE MAY REACH
--------------------------
`nova_auth`, whose privileges cover `auth_credential` and `auth_session` and
nothing else. Authentication necessarily runs BEFORE a Context Token exists, so
it cannot go through the Data-Access Boundary -- `I-78` is untouched because no
scope-bound channel is opened here, and the privilege split means this path
cannot reach scoped data even if it wanted to.

STATED LIMITATIONS
------------------
1. BOOTSTRAP IS TRUST-ON-FIRST-USE. The first passkey for an actor may be
   enrolled without an existing session, because otherwise no session could
   ever exist. Every subsequent passkey requires an authenticated multi-factor
   session. Whoever reaches the enrolment route first, on a system with no
   credential, becomes James. In deployment that window is closed by not
   exposing the route until enrolment is done; that is an operational control,
   and it is not claimed to be more than one.
2. NO ATTESTATION IS VERIFIED. Registration accepts `none` attestation, so
   NOVA does not establish WHICH authenticator model holds the key. `A-2` is
   about replay resistance and does not require attestation; device allow-lists
   are a Section 31 concern.
3. NO STEP-UP RE-AUTHENTICATION (`A-3`). Session strength is fixed at login.
   IRREVERSIBLE actions and changes to grants, policy or credentials require a
   FRESH authentication, which is not implemented -- and no IRREVERSIBLE path
   exists yet to require it. Recorded, not claimed.
4. NO RECOVERY FLOW (`A-4`). Losing every passkey means losing access. That is
   the safe direction to fail, and a recovery path is the most attacked surface
   in any authentication system; it is not built speculatively.
5. IDLE TIMEOUT IS NOT IMPLEMENTED. Expiry is absolute, which is what the model
   requires; idle timeout is described there as additional, not a substitute.
"""

from __future__ import annotations

import base64
import dataclasses
import datetime
import hashlib
import json
import secrets
import threading
from typing import Optional

import webauthn
from webauthn.helpers import options_to_json
from webauthn.helpers.structs import (AuthenticatorSelectionCriteria,
                                      PublicKeyCredentialDescriptor,
                                      ResidentKeyRequirement,
                                      UserVerificationRequirement)

from . import db

# A-1. The two strengths a session can have, and what each may reach.
SINGLE_FACTOR = "single_factor"
MULTI_FACTOR = "multi_factor"

# Absolute, not extended by activity.
SESSION_LIFETIME = datetime.timedelta(hours=12)
# A ceremony is short-lived by design: a challenge that outlives the interaction
# is a replay window.
CEREMONY_LIFETIME = datetime.timedelta(minutes=5)


class AuthenticationFailed(Exception):
    """One error for every failure mode. Which check failed is not the
    caller's business: distinguishing "no such credential" from "bad
    signature" from "expired challenge" is an enumeration oracle."""


@dataclasses.dataclass(frozen=True)
class AuthenticatedSession:
    """The authenticated server identity, and nothing else.

    Deliberately carries NO authorization state: no rights, no scope, no
    grants, no ceiling. Those are the Context service's and the PDP's, derived
    fresh per request from the identity below (`I-13`).
    """
    session_ref: str          # SHA-256 of the cookie value -- not the value
    identity: str             # the grantee the PDP checks grants against
    actor: str                # the acting identity
    strength: str             # SINGLE_FACTOR | MULTI_FACTOR (A-1)
    surface: str
    established_at: datetime.datetime
    expires_at: datetime.datetime

    @property
    def is_multi_factor(self) -> bool:
        return self.strength == MULTI_FACTOR


def _ref(session_token: str) -> str:
    """What is stored. The browser holds the value; the database holds this."""
    return hashlib.sha256(session_token.encode()).hexdigest()


class _Ceremonies:
    """In-flight challenges. Single-use, expiring, server-side.

    Deliberately in memory: a challenge is meaningless after five minutes and
    a restart invalidating in-flight logins is correct behaviour, not a bug.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._open: dict[str, tuple[bytes, str, datetime.datetime]] = {}

    def start(self, challenge: bytes, purpose: str) -> str:
        ceremony_id = secrets.token_urlsafe(24)
        with self._lock:
            self._open[ceremony_id] = (challenge, purpose,
                                       _now() + CEREMONY_LIFETIME)
        return ceremony_id

    def take(self, ceremony_id: Optional[str], purpose: str) -> bytes:
        """Consume. A challenge is valid exactly once, for one purpose."""
        with self._lock:
            entry = self._open.pop(ceremony_id or "", None)
        if entry is None:
            raise AuthenticationFailed("no such ceremony")
        challenge, entry_purpose, expires = entry
        if entry_purpose != purpose or _now() >= expires:
            raise AuthenticationFailed("ceremony expired")
        return challenge


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class AuthenticationService:
    """WebAuthn registration and login; opaque, revocable server-side sessions.

    Replaces `seam.SessionStore`. The seam calls `resolve()` exactly as before;
    what changed is that a session now exists only because a signature verified.
    """

    def __init__(self, rp_id: str, rp_name: str, origin: str,
                 dsn: Optional[str] = None):
        self.rp_id = rp_id
        self.rp_name = rp_name
        self.origin = origin
        self._dsn = dsn or db.auth_dsn()
        self._ceremonies = _Ceremonies()

    # -- storage -------------------------------------------------------------

    def _connect(self):
        import psycopg2
        conn = psycopg2.connect(self._dsn)
        conn.autocommit = True
        return conn

    # -- enrolment -----------------------------------------------------------

    def has_credential(self, actor: str) -> bool:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM auth_credential WHERE actor_ref=%s LIMIT 1",
                            (actor,))
                return cur.fetchone() is not None
        finally:
            conn.close()

    def enrolment_options(self, identity: str, actor: str,
                          authorized_by: Optional[AuthenticatedSession] = None
                          ) -> tuple[str, str]:
        """Begin registering a passkey. Returns (ceremony_id, options_json).

        The FIRST credential for an actor may be enrolled with no session --
        there is no other way to bootstrap (limitation 1 in the module
        docstring). Every later one requires an authenticated multi-factor
        session, so adding a device is itself a consequential act.
        """
        if self.has_credential(actor):
            if authorized_by is None or not authorized_by.is_multi_factor \
                    or authorized_by.actor != actor:
                raise AuthenticationFailed("enrolment requires a strong session")

        options = webauthn.generate_registration_options(
            rp_id=self.rp_id, rp_name=self.rp_name,
            user_id=actor.encode(), user_name=identity, user_display_name=identity,
            authenticator_selection=AuthenticatorSelectionCriteria(
                # A-1: the second factor is verified on the device and reported
                # in a signed flag. Required, not preferred.
                user_verification=UserVerificationRequirement.REQUIRED,
                resident_key=ResidentKeyRequirement.REQUIRED,
            ),
        )
        return self._ceremonies.start(options.challenge, "register"), \
            options_to_json(options)

    def verify_enrolment(self, ceremony_id: Optional[str], credential_json: str,
                         identity: str, actor: str, label: str = "") -> str:
        """Verify and store the passkey. Returns its credential id."""
        challenge = self._ceremonies.take(ceremony_id, "register")
        try:
            verified = webauthn.verify_registration_response(
                credential=credential_json,
                expected_challenge=challenge,
                expected_rp_id=self.rp_id,
                expected_origin=self.origin,
                require_user_verification=True,
            )
        except Exception as exc:                      # library raises its own types
            raise AuthenticationFailed("registration rejected") from exc

        credential_id = base64.urlsafe_b64encode(verified.credential_id).decode().rstrip("=")
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth_credential"
                    " (credential_id, actor_ref, identity, public_key, sign_count, label)"
                    " VALUES (%s,%s,%s,%s,%s,%s)",
                    (credential_id, actor, identity,
                     memoryview(verified.credential_public_key),
                     verified.sign_count, label))
        finally:
            conn.close()
        return credential_id

    # -- login ---------------------------------------------------------------

    def login_options(self) -> tuple[str, str]:
        """Begin a login. Names no user: discoverable credentials mean the
        authenticator supplies the identity, so an unauthenticated caller
        cannot use this route to learn who exists."""
        options = webauthn.generate_authentication_options(
            rp_id=self.rp_id,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        return self._ceremonies.start(options.challenge, "authenticate"), \
            options_to_json(options)

    def verify_login(self, ceremony_id: Optional[str], credential_json: str,
                     surface: str = "") -> str:
        """Verify the assertion and establish a session.

        Returns the opaque session value ONCE -- it is never stored, never
        logged, and never recoverable from the database.
        """
        challenge = self._ceremonies.take(ceremony_id, "authenticate")
        try:
            raw_id = json.loads(credential_json)["id"]
        except Exception as exc:
            raise AuthenticationFailed("malformed credential") from exc

        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT actor_ref, identity, public_key, sign_count"
                    " FROM auth_credential WHERE credential_id=%s", (raw_id,))
                row = cur.fetchone()
            if row is None:
                raise AuthenticationFailed("authentication rejected")
            actor, identity, public_key, sign_count = row

            try:
                verified = webauthn.verify_authentication_response(
                    credential=credential_json,
                    expected_challenge=challenge,
                    expected_rp_id=self.rp_id,
                    expected_origin=self.origin,
                    credential_public_key=bytes(public_key),
                    credential_current_sign_count=sign_count,
                    # NOT required here, deliberately. A-1 says a single factor
                    # MAY open a READ-only session; rejecting UV-less
                    # assertions outright would make every session
                    # multi-factor and the strength gate below dead code -- a
                    # check that cannot fail is not a control. The UV flag is
                    # read out of the verified signature instead, and the seam
                    # refuses EXECUTE without it.
                    require_user_verification=False,
                )
            except Exception as exc:
                raise AuthenticationFailed("authentication rejected") from exc

            # Clone detection: a non-zero counter that did not advance means two
            # authenticators hold the same key. py_webauthn raises above; this
            # records the advance so it can.
            with conn.cursor() as cur:
                cur.execute("UPDATE auth_credential SET sign_count=%s WHERE credential_id=%s",
                            (verified.new_sign_count, raw_id))

            # Strength comes from the SIGNED UV flag, not from anything the
            # client asserted alongside it.
            strength = MULTI_FACTOR if verified.user_verified else SINGLE_FACTOR
            session_token = secrets.token_urlsafe(32)
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO auth_session (session_ref, actor_ref, identity,"
                    " strength, surface, credential_id, expires_at)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (_ref(session_token), actor, identity, strength, surface,
                     raw_id, _now() + SESSION_LIFETIME))
            return session_token
        finally:
            conn.close()

    # -- the seam's interface ------------------------------------------------

    def resolve(self, session_token: Optional[str]) -> Optional[AuthenticatedSession]:
        """The one method the seam calls. Returns None for absent, unknown,
        expired or revoked -- all four are the same answer to the caller."""
        if not session_token:
            return None
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_ref, identity, actor_ref, strength, surface,"
                    " established_at, expires_at FROM auth_session"
                    " WHERE session_ref=%s AND revoked_at IS NULL AND expires_at > now()",
                    (_ref(session_token),))
                row = cur.fetchone()
        finally:
            conn.close()
        return AuthenticatedSession(*row) if row else None

    # -- A-6: enumerable and revocable ---------------------------------------

    def active_sessions(self, actor: str) -> list[AuthenticatedSession]:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT session_ref, identity, actor_ref, strength, surface,"
                    " established_at, expires_at FROM auth_session"
                    " WHERE actor_ref=%s AND revoked_at IS NULL AND expires_at > now()"
                    " ORDER BY established_at", (actor,))
                rows = cur.fetchall()
        finally:
            conn.close()
        return [AuthenticatedSession(*r) for r in rows]

    def revoke(self, session_ref: str) -> None:
        """Takes effect at the next decision (`I-65`): every request resolves
        the session afresh, so there is no window in which a revoked session
        keeps working."""
        self._update("UPDATE auth_session SET revoked_at=now()"
                     " WHERE session_ref=%s AND revoked_at IS NULL", (session_ref,))

    def revoke_all(self, actor: str) -> None:
        """Emergency stop ends every session (SECURITY_OPERATIONS §4)."""
        self._update("UPDATE auth_session SET revoked_at=now()"
                     " WHERE actor_ref=%s AND revoked_at IS NULL", (actor,))

    def _update(self, sql: str, args: tuple) -> None:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, args)
        finally:
            conn.close()
