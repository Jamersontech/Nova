"""A software authenticator, for tests only. It plays the security key.

WHAT THIS IS AND IS NOT
-----------------------
This is the CLIENT half of a WebAuthn ceremony: it holds a real P-256 key and
produces real ECDSA signatures over the real signed payload. The SERVER half --
signature verification, RP-ID hashing, flag checks, counter checks, COSE
decoding -- is `py_webauthn`, unchanged and unmocked.

That split is the point. Nothing here can make a bad assertion verify. The
hostile cases in the suite are produced by making this authenticator misbehave
(wrong origin, wrong RP, replayed challenge, absent user verification, a
regressed counter) and then asserting the real verifier rejects it.

It is not a security control and is not shipped.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import struct

import cbor2
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec

UP = 0x01   # user present
UV = 0x04   # user verified -- A-1's second factor, reported inside the signature
AT = 0x40   # attested credential data included


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


class SoftAuthenticator:
    """One passkey. Real key material, real signatures."""

    def __init__(self, aaguid: bytes = b"\x00" * 16):
        self._key = ec.generate_private_key(ec.SECP256R1())
        self.credential_id = os.urandom(32)
        self.aaguid = aaguid
        self.sign_count = 0

    # -- the COSE public key the relying party stores ------------------------

    def _cose_key(self) -> bytes:
        numbers = self._key.public_key().public_numbers()
        return cbor2.dumps({
            1: 2,        # kty: EC2
            3: -7,       # alg: ES256
            -1: 1,       # crv: P-256
            -2: numbers.x.to_bytes(32, "big"),
            -3: numbers.y.to_bytes(32, "big"),
        })

    # -- the signed payload --------------------------------------------------

    def _auth_data(self, rp_id: str, flags: int, attested: bool) -> bytes:
        data = hashlib.sha256(rp_id.encode()).digest()
        data += bytes([flags])
        data += struct.pack(">I", self.sign_count)
        if attested:
            key = self._cose_key()
            data += self.aaguid + struct.pack(">H", len(self.credential_id))
            data += self.credential_id + key
        return data

    def _client_data(self, kind: str, challenge: bytes, origin: str) -> bytes:
        return json.dumps({
            "type": kind,
            "challenge": b64u(challenge),
            "origin": origin,
            "crossOrigin": False,
        }).encode()

    # -- ceremonies ----------------------------------------------------------

    def register(self, challenge: bytes, rp_id: str, origin: str,
                 user_verified: bool = True) -> str:
        """The `navigator.credentials.create()` result, as JSON."""
        flags = UP | AT | (UV if user_verified else 0)
        auth_data = self._auth_data(rp_id, flags, attested=True)
        attestation = cbor2.dumps(
            {"fmt": "none", "attStmt": {}, "authData": auth_data})
        return json.dumps({
            "id": b64u(self.credential_id),
            "rawId": b64u(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64u(
                    self._client_data("webauthn.create", challenge, origin)),
                "attestationObject": b64u(attestation),
            },
            "clientExtensionResults": {},
        })

    def authenticate(self, challenge: bytes, rp_id: str, origin: str,
                     user_verified: bool = True,
                     advance_counter: bool = True) -> str:
        """The `navigator.credentials.get()` result, as JSON.

        `user_verified=False` produces a single-factor assertion; a regressed
        counter (`advance_counter=False`) is what a cloned authenticator looks
        like. Both exist so the suite can prove the server rejects them.
        """
        if advance_counter:
            self.sign_count += 1
        flags = UP | (UV if user_verified else 0)
        auth_data = self._auth_data(rp_id, flags, attested=False)
        client_data = self._client_data("webauthn.get", challenge, origin)
        signature = self._key.sign(
            auth_data + hashlib.sha256(client_data).digest(),
            ec.ECDSA(hashes.SHA256()))
        return json.dumps({
            "id": b64u(self.credential_id),
            "rawId": b64u(self.credential_id),
            "type": "public-key",
            "response": {
                "clientDataJSON": b64u(client_data),
                "authenticatorData": b64u(auth_data),
                "signature": b64u(signature),
                "userHandle": None,
            },
            "clientExtensionResults": {},
        })
