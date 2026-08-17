"""Shared fixture: a real enrolled passkey and a real signed-in session.

Every substrate suite now reaches the application through THIS, so none of them
can pass against a session that a dictionary handed out. The server half is
`py_webauthn` doing real verification; only the authenticator is software.
"""

from __future__ import annotations

import base64
import json

from ..auth import AuthenticationService
from .softauthn import SoftAuthenticator

RP_ID = "nova.local"
ORIGIN = "https://nova.local"


def service() -> AuthenticationService:
    return AuthenticationService(RP_ID, "NOVA", ORIGIN)


def _challenge(options_json: str) -> bytes:
    raw = json.loads(options_json)["challenge"]
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def enrol(auth: AuthenticationService, identity: str, actor: str,
          label: str = "test key", authorized_by=None) -> SoftAuthenticator:
    key = SoftAuthenticator()
    ceremony, options = auth.enrolment_options(identity, actor,
                                               authorized_by=authorized_by)
    auth.verify_enrolment(ceremony, key.register(_challenge(options), RP_ID, ORIGIN),
                          identity, actor, label)
    return key


def sign_in(auth: AuthenticationService, key: SoftAuthenticator,
            user_verified: bool = True, surface: str = "test surface") -> str:
    """Returns the opaque session value the browser would hold."""
    ceremony, options = auth.login_options()
    assertion = key.authenticate(_challenge(options), RP_ID, ORIGIN,
                                 user_verified=user_verified)
    return auth.verify_login(ceremony, assertion, surface=surface)
