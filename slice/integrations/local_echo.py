"""A deterministic local integration.

NO NETWORK. NO REAL CREDENTIALS. It stands where a real provider would stand
and preserves the same architectural boundary: it receives an injected secret
at the call boundary, returns a result, and the secret never travels back up.

ADR 0037 (S11-D2) is what this exists to exercise honestly: a provider's
statement about its own side effect is a CLAIM, never a verified fact. This
integration can be told to claim success, claim failure, or produce an
AMBIGUOUS outcome (timeout / lost connection) -- the third being the one the
architecture insists is distinct.
"""

from __future__ import annotations

from typing import Any

from ..core.types import Classification, Outcome, Taint


class LocalEchoIntegration:
    """Behaviour is set by the test, not by chance -- deterministic by design."""

    def __init__(self, provider: str, account: str, endpoint: str, api_version: str,
                 mode: str = "success", enforces_dedup: bool = False):
        self.provider = provider
        self.account = account
        self.endpoint = endpoint
        self.api_version = api_version
        self.mode = mode                      # success | failure | unknown | partial
        self.enforces_dedup = enforces_dedup
        self.received: list[dict[str, Any]] = []
        self.secret_seen: list[str] = []
        self.side_effects: int = 0            # counts REAL effects, for duplicate detection

    def transport(self, payload: dict[str, Any], secret: str) -> Outcome:
        """The call boundary. `secret` arrives here and goes no further."""
        self.received.append(dict(payload))
        # Recorded only to prove injection happened at the boundary; a real
        # integration would place it in a header. It is never returned.
        self.secret_seen.append(secret[:4] + "...")

        base = Taint.of("integration.supplied", Classification.INTERNAL)

        if self.mode == "success":
            self.side_effects += 1
            return Outcome("success_claimed", "provider returned 200", base)

        if self.mode == "failure":
            return Outcome("failure_claimed", "provider returned 500", base)

        if self.mode == "partial":
            # A provider may PARTIALLY EXECUTE before returning failure
            # (RELIABILITY_ARCHITECTURE.md section 2, Section 11 amendment).
            self.side_effects += 1
            return Outcome("failure_claimed", "provider returned 500 after partial write", base)

        if self.mode == "unknown":
            # Timeout / lost connection: the side effect MAY have occurred.
            # This is the case the architecture refuses to collapse into
            # "failed".
            self.side_effects += 1        # it really did land; NOVA cannot know
            return Outcome("unknown", "connection lost after send", base)

        raise ValueError(f"unknown mode {self.mode}")
