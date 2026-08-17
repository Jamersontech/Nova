"""Real Anthropic provider transport — the egress boundary.

THE ONLY COMPONENT IN THE SLICE THAT TOUCHES REAL CREDENTIAL MATERIAL.

Credential discipline, mirroring SECRETS_ARCHITECTURE.md section 3 and I-103:

  * The gateway hands this transport a `credential_ref` -- a REFERENCE such as
    "control-plane/anthropic" -- never a secret. I-22: no component upstream of
    this boundary ever holds credential material.
  * The value is resolved HERE, from the process environment, at send time, and
    injected into the outbound request only.
  * It is never returned upward, never stored, never logged, never placed in an
    exception, and never written to any file (I-70, I-48).
  * Every exception raised from this module is SANITIZED: provider error text is
    passed through a filter that refuses to emit anything resembling the
    credential.

I-103: a provider credential is a CONTROL-PLANE credential. It authorizes NOVA
to talk to a provider and authorizes access to NO client scope. The scope's
authorization to reach this provider is carried by the Context Token and decided
at the gateway (I-94) -- never by the credential.

NO SECRET IS EVER WRITTEN TO THIS FILE OR ANY OTHER.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass, field

from ..core.gateway import ModelResponse
from ..core.types import Classification, Denied, Taint

ANTHROPIC_ENDPOINT = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"

# The reference the gateway's ProviderBinding carries. Resolved to an
# environment variable name here and nowhere else.
CREDENTIAL_REF_TO_ENV = {
    "control-plane/anthropic": "ANTHROPIC_API_KEY",
}


class CallBudgetExceeded(Exception):
    """Hard stop. Independent of NOVA's own I-105 budget: this is the
    OPERATOR's cap on how many real network attempts this validation may make,
    enforced in the transport so it cannot be bypassed from above."""


@dataclass
class RealAnthropicTransport:
    """Deterministic, auditable, hard-capped.

    `max_attempts` counts EVERY outbound attempt including failures --
    I-104's "cost accounting records attempts, not outcomes" applied to the
    operator's cap. `max_successes` caps completed generations separately.
    """
    model: str
    max_tokens: int = 16
    max_attempts: int = 5
    max_successes: int = 2
    timeout_s: float = 30.0

    attempts: int = 0
    successes: int = 0
    log: list[str] = field(default_factory=list)   # metadata only, never content

    # -- credential resolution -------------------------------------------

    @staticmethod
    def credential_available(credential_ref: str) -> bool:
        """Presence ONLY. Returns a bool -- never the value, never its length,
        never a hash, never any derived quantity."""
        env_name = CREDENTIAL_REF_TO_ENV.get(credential_ref)
        return bool(env_name and os.environ.get(env_name))

    @staticmethod
    def _resolve(credential_ref: str) -> str:
        """The single point at which secret material enters the process.

        The return value is passed straight into the request header and is
        never assigned to a module-level name, logged, or returned upward.
        """
        env_name = CREDENTIAL_REF_TO_ENV.get(credential_ref)
        if env_name is None:
            raise Denied("provider.credential",
                         f"unknown credential reference {credential_ref!r}",
                         "I-103", True)
        value = os.environ.get(env_name)
        if not value:
            # S-8 / I-93: the store being unavailable is a DENIAL, never an
            # uncredentialed call. The env var NAME is safe to state; the value
            # is not, and is not stated.
            raise Denied("provider.credential",
                         f"no credential material for {credential_ref!r}",
                         "S-8", True)
        return value

    # -- sanitisation ------------------------------------------------------

    @staticmethod
    def _sanitise(text: str, credential_ref: str) -> str:
        """Belt and braces. Provider error bodies should never contain the key,
        but this module refuses to propagate anything that might.

        The comparison is done WITHOUT logging, measuring or hashing the
        credential: it is read, compared, and dropped.
        """
        env_name = CREDENTIAL_REF_TO_ENV.get(credential_ref)
        secret = os.environ.get(env_name) if env_name else None
        if secret and secret in text:
            return "[provider text withheld: contained credential material]"
        return text[:200]

    # -- the boundary ------------------------------------------------------

    def __call__(self, prompt: str, credential_ref: str) -> ModelResponse:
        """Called by ModelGateway.call() AFTER every authorization control has
        passed. Reaching this function at all is the gateway's decision, never
        this transport's -- it decides nothing and can only fail (I-77)."""
        if self.attempts >= self.max_attempts:
            raise CallBudgetExceeded(
                f"operator cap reached: {self.attempts}/{self.max_attempts} attempts")
        if self.successes >= self.max_successes:
            raise CallBudgetExceeded(
                f"operator cap reached: {self.successes}/{self.max_successes} successes")

        body = json.dumps({
            "model": self.model,
            "max_tokens": self.max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        req = urllib.request.Request(
            ANTHROPIC_ENDPOINT,
            data=body,
            headers={
                "content-type": "application/json",
                "anthropic-version": ANTHROPIC_VERSION,
                # Injected at the boundary and nowhere else. The header dict is
                # local to this call and is not retained after it returns.
                "x-api-key": self._resolve(credential_ref),
            },
        )

        self.attempts += 1
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as r:
                payload = json.loads(r.read().decode())
                status = r.status
        except urllib.error.HTTPError as e:
            detail = self._sanitise(e.read().decode(errors="replace"), credential_ref)
            self.log.append(f"attempt={self.attempts} http={e.code} (error)")
            # A typed provider failure. RELIABILITY section 2: this is FAILURE,
            # distinct from UNKNOWN.
            return ModelResponse(
                text="", outcome="failure_claimed",
                taint=Taint.of("integration.supplied", Classification.INTERNAL),
                detail=f"provider returned HTTP {e.code}: {detail}")
        except TimeoutError:
            self.log.append(f"attempt={self.attempts} timeout")
            raise                      # gateway converts to UNKNOWN, never failure
        except urllib.error.URLError as e:
            self.log.append(f"attempt={self.attempts} urlerror")
            # Connection lost: the request may or may not have been received.
            # RELIABILITY section 2 -- UNKNOWN, never "failure".
            raise TimeoutError(f"connection failed: {type(e.reason).__name__}")

        self.successes += 1
        text = "".join(b.get("text", "") for b in payload.get("content", []))
        usage = payload.get("usage", {})
        self.log.append(
            f"attempt={self.attempts} http={status} model={payload.get('model')} "
            f"stop={payload.get('stop_reason')} "
            f"in={usage.get('input_tokens')} out={usage.get('output_tokens')}")

        # I-99: the gateway OVERWRITES this taint with the union computed from
        # the REQUEST. Set here only so the object is well-formed; the model's
        # own text can never influence its labels.
        return ModelResponse(
            text=text, outcome="success_claimed",
            taint=Taint.of("model.generated", Classification.INTERNAL),
            detail=f"HTTP {status}")
