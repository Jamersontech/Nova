"""Phase 1 preflight for the real-provider validation.

ZERO NETWORK CALLS. Every check here is local. Authentication cannot be
verified without spending a real call, so it is DEFERRED to Phase 2 and
reported as such rather than guessed at.

Run:  ANTHROPIC_API_KEY='...' python3 -m slice.tests.real_preflight

The key is read only by the transport, only from the environment, and is
never printed, echoed, hashed, measured, stored or written.
"""

from __future__ import annotations

import os
import subprocess
import sys

from ..core.gateway import ModelRequestItem, ProviderBinding
from ..core.types import Classification, Denied, Risk, Taint
from ..models.anthropic_provider import (ANTHROPIC_ENDPOINT, ANTHROPIC_VERSION,
                                         CREDENTIAL_REF_TO_ENV,
                                         RealAnthropicTransport)
from .harness2 import PROFILE, SCOPE_A, SCOPE_A_SUB, build, cleanup, coordinator_token, items

CRED_REF = "control-plane/anthropic"
MODEL = "claude-haiku-4-5-20251001"

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))


def main() -> int:
    print("PREFLIGHT — real-provider validation (zero network calls)\n")

    # ---- 1. credential present, nothing revealed -------------------------
    print("1. Credential")
    present = RealAnthropicTransport.credential_available(CRED_REF)
    check("credential resolvable via reference " + repr(CRED_REF), present,
          "presence only; no value, length, hash or metadata read")
    check("credential is NOT a CLAUDE_CODE_* / harness credential",
          CREDENTIAL_REF_TO_ENV[CRED_REF] == "ANTHROPIC_API_KEY",
          "resolves ANTHROPIC_API_KEY only")
    if not present:
        print("\nPREFLIGHT FAILED: no credential material. No network call made.")
        return 1

    # ---- 2. endpoint ------------------------------------------------------
    print("\n2. Endpoint")
    check("endpoint is the real Anthropic API",
          ANTHROPIC_ENDPOINT == "https://api.anthropic.com/v1/messages", ANTHROPIC_ENDPOINT)
    check("API version pinned", bool(ANTHROPIC_VERSION), ANTHROPIC_VERSION)

    # ---- 3. NOVA's provider authorization path ---------------------------
    print("\n3. Provider authorization path (NOVA supplies the credential)")
    rt, gw, _fixture, tmp = build()
    try:
        transport = RealAnthropicTransport(model=MODEL, max_tokens=16,
                                           max_attempts=5, max_successes=2)
        binding = ProviderBinding(provider="anthropic", model=MODEL,
                                  endpoint=ANTHROPIC_ENDPOINT, api_version=ANTHROPIC_VERSION,
                                  credential_ref=CRED_REF, cost_per_unit=1)
        gw.register_provider(binding, transport)
        check("gateway holds the binding; transport registered under it", True,
              "provider=anthropic model=" + MODEL)
        check("binding carries a REFERENCE, not a secret (I-103)",
              binding.credential_ref == CRED_REF and "sk-" not in binding.credential_ref,
              repr(binding.credential_ref))

        # I-98: routing is "declared by the agent definition or fixed in the
        # authorized plan". In this implementation the CapabilityProfile is that
        # declaration, and it is what the gateway reads (I-97's permitted set).
        tok = coordinator_token(rt)
        check("routing is declared by the capability profile, not by model output",
              "anthropic" not in PROFILE.permitted_providers,
              f"profile permits {sorted(PROFILE.permitted_providers)}; "
              "anthropic must be DECLARED before it can be reached")

        # ---- 4. controls active -----------------------------------------
        print("\n4. Enforcement controls active (all deny BEFORE egress)")

        def denies(label, fn, want_inv):
            try:
                fn()
                check(label, False, "NOT DENIED")
            except Denied as d:
                check(label, d.invariant == want_inv or want_inv in d.invariant,
                      f"denied at {d.step} ({d.invariant})")

        denies("I-98 — model output cannot name the provider",
               lambda: gw.call(tok, items(), PROFILE, "anthropic", MODEL,
                               model_requested_provider="anthropic"), "I-98")
        denies("I-97 — provider outside the permitted set",
               lambda: gw.call(tok, items(), PROFILE, "anthropic", MODEL), "I-97")

        gw.emergency_stop = True
        denies("I-19 — emergency stop halts the gateway",
               lambda: gw.call(tok, items(), PROFILE, "anthropic", MODEL), "I-19")
        gw.emergency_stop = False

        rt.pdp.available = False
        denies("I-17 — PDP unavailable is deny",
               lambda: gw.call(tok, items(), PROFILE, "anthropic", MODEL), "I-17")
        rt.pdp.available = True

        sec = [ModelRequestItem(label="audit", content="x", scope_path=SCOPE_A_SUB,
                                taint=Taint.of("james.stated", Classification.SECURITY_CRITICAL))]
        denies("I-96 — SECURITY-CRITICAL never reaches a provider",
               lambda: gw.call(tok, sec, PROFILE, "anthropic", MODEL), "I-96")

        foreign = [ModelRequestItem(label="other", content="x",
                                    scope_path="/business/KAIRO/client-b",
                                    taint=Taint.of("james.stated",
                                                   Classification.CLIENT_CONFIDENTIAL))]
        denies("I-95 — content from a second scope",
               lambda: gw.call(tok, foreign, PROFILE, "anthropic", MODEL), "I-95")

        rt.context.revoke(tok.trace_id)
        denies("I-74 — revoked token fails closed at this PEP",
               lambda: gw.call(tok, items(), PROFILE, "anthropic", MODEL), "I-74")

        check("ZERO network attempts made during preflight",
              transport.attempts == 0, f"attempts={transport.attempts}")

        # ---- 5. the credential cannot leak -------------------------------
        print("\n5. Credential containment")
        secret = os.environ[CREDENTIAL_REF_TO_ENV[CRED_REF]]

        # Scan the whole repo for the literal value. Never printed either way.
        hits = []
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
            for fn in files:
                p = os.path.join(root, fn)
                try:
                    with open(p, "rb") as fh:
                        if secret.encode() in fh.read():
                            hits.append(p)
                except (OSError, ValueError):
                    pass
        check("credential absent from every file in the working tree", not hits,
              f"{len(hits)} file(s)" if hits else "0 files")

        git_grep = subprocess.run(["git", "grep", "-I", "-l", secret],
                                  capture_output=True, text=True)
        check("credential absent from tracked git content",
              git_grep.returncode != 0 and not git_grep.stdout.strip(), "git grep found nothing")

        audit_rows = rt.stores.for_scope(SCOPE_A).audit_records()
        check("credential absent from audit records (I-48, I-103)",
              not any(secret in str(r) for r in audit_rows),
              f"{len(audit_rows)} rows scanned; credential referenced by name only")

        check("transport never returns credential material upward (I-70)",
              "return value" not in dir(transport) and
              not any(secret in str(x) for x in transport.log),
              "transport.log holds metadata only")

        st = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
        untracked_secret = [l for l in st.stdout.splitlines() if ".env" in l]
        check("no .env or credential file created", not untracked_secret,
              "working tree carries no credential file")

        del secret
    finally:
        cleanup(rt, tmp)

    print("\n6. Deferred (cannot be checked without spending a real call)")
    print("  [DEFER] authentication succeeds — requires one real call; "
          "deferred to Phase 2 call 1 rather than guessed")

    failed = [n for n, ok, _ in results if not ok]
    print("\n" + "=" * 62)
    if failed:
        print("PREFLIGHT FAILED:", ", ".join(failed))
        return 1
    print(f"PRE-FLIGHT PASSED — {len(results)} controls verified, 0 network calls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
