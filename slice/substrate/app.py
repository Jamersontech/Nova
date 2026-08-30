"""NOVA, runnable. The composition root and nothing else.

    python3 -m slice.substrate.app

Every object constructed here already exists and is already tested; this file
invents nothing. It is the one place the real wiring is written down:

    schema        -> db.apply_schema()                    (owner role)
    scope tree    -> tree_store.load_tree()               (control role)
    identity      -> auth.AuthenticationService           (WebAuthn, D-09)
    tokens        -> core.context_service.ContextService  (sole issuer, I-106)
    decisions     -> core.policy.PolicyDecisionPoint
    isolation     -> boundary.DataAccessBoundary + RLS    (app role)
    writes        -> write_path.WritePath -> ToolPEP -> broker
    approvals     -> approval_flow.ApprovalService
    conversation  -> conversation.ConversationService -> ModelGateway
    provider      -> models.anthropic_provider.RealAnthropicTransport
                     (registered ONLY when ANTHROPIC_API_KEY is present;
                      absent, conversation fails closed and says so)

CONFIGURATION -- environment only, no config framework:

    NOVA_PORT         listen port                (default 8080)
    NOVA_RP_ID        WebAuthn relying-party id  (default localhost)
    NOVA_ORIGIN       browser origin             (default http://localhost:PORT)
    NOVA_DATA_DIR     audit + secrets directory  (default ~/.nova)
    ANTHROPIC_API_KEY conversation provider credential (ADR 0047); resolved
                      only inside the transport at send time (I-103)

FIRST RUN: the scope tree is seeded with the three areas -- LIFE, BUSINESS,
WEALTH (USER_INTERFACE_ARCHITECTURE section 2) -- and read/write grants for
James, only when the tree is empty. Then open /auth/login and register a
passkey. Bootstrap is trust-on-first-use (ADR 0046 limitation 1): do not
expose the port beyond localhost until enrolment is done.
"""

from __future__ import annotations

import dataclasses
import os
import pathlib

from ..core.audit import AuditWriter
from ..core.broker import CredentialBinding, CredentialBroker, SecretsStore
from ..core.budget import BudgetLedger
from ..core.context_service import ContextService
from ..core.gateway import ModelGateway, ProviderBinding
from ..core.policy import PolicyDecisionPoint
from ..core.store import StoreRegistry
from ..models.anthropic_provider import (ANTHROPIC_ENDPOINT, ANTHROPIC_VERSION,
                                         RealAnthropicTransport)
from . import db, tree_store
from .approval_flow import ApprovalService
from .attention import AttentionService
from .auth import AuthenticationService
from .boundary import DataAccessBoundary
from .revocation import RevocationRegistry
from .conversation import (CONVERSATION_MODEL, PROVIDER, ConversationService)
from .seam import Seam, serve
from .write_path import (ALL_TOOLS, PostgresItemIntegration, WritePath, TOOL)
from ..tools.pep import ToolPEP
from ..tools.registry import ToolRegistry

CRED_REF = "control-plane/anthropic"

DEFAULT_SCOPES = [("/life", "domain", None),
                  ("/business", "domain", None),
                  ("/wealth", "domain", None)]
# I-10: James's grants, written by `tree_store.seed` on the OWNER connection.
# `revoke` is seeded like any other right and confers `Risk.IRREVERSIBLE`
# through `READ_RIGHTS` -- ADR 0052 element 8c, using the existing mechanism
# rather than a new one. It is a SEPARATE right precisely so `write` stays
# EXECUTE: an EXECUTE grant must not authorize an irreversible act.
DEFAULT_GRANTS = [("james", path, right)
                  for path, _, _ in DEFAULT_SCOPES
                  for right in ("read", "write", "revoke")]


class ScopedWritePath(WritePath):
    """One parameterization, not a parallel system: the datastore credential
    binding is per-scope (I-24 -- a token covers only bindings at or below its
    own scope), so the binding id is derived from the scope instead of fixed
    at construction. `wire()` registers one binding per scope to match."""

    def binding_for(self, scope_path: str, tool_name: str = TOOL):
        return dataclasses.replace(super().binding_for(scope_path, tool_name),
                                   credential_binding_id=f"db-item-write{scope_path}")


def wire(data_dir: str, rp_id: str, origin: str) -> Seam:
    """Everything, wired once. Returns the Seam ready to serve."""
    db.apply_schema()

    tree = tree_store.load_tree()
    if not tree.paths():
        tree_store.seed(DEFAULT_SCOPES, DEFAULT_GRANTS)
        tree = tree_store.load_tree()

    # SEEDING IS FIRST-RUN ONLY, and deliberately stays that way.
    #
    # A tree that already exists is NOT converged onto `DEFAULT_GRANTS`. That
    # was tried and reverted: `wire()` is handed whatever tree the caller
    # seeded, so converging here would push THIS module's defaults onto trees
    # that deliberately hold a different grant set, and would make startup a
    # grant-CREATING path that runs every time rather than once. `I-10` keeps
    # grant creation to `tree_store.seed`, called by James -- turning the
    # composition root into a second writer is the wrong direction for one
    # missing right.
    #
    # The consequence, stated rather than worked around: a database seeded
    # before a right existed never receives it, and `F-3`'s revocation is then
    # refused at issuance (`I-14`). The Alpha path is a FRESH database, where
    # the seed above writes `read`, `write` and `revoke` together -- see
    # README.md, "A database seeded before F-3".

    context = ContextService(tree, secret=os.urandom(32))
    audit = AuditWriter(StoreRegistry(os.path.join(data_dir, "audit")))
    pdp = PolicyDecisionPoint(tree, context, audit)
    boundary = DataAccessBoundary(db.app_dsn(), context)
    auth = AuthenticationService(rp_id, "NOVA", origin)

    vault = SecretsStore(os.path.join(data_dir, "secrets", "vault.json"))
    broker = CredentialBroker(tree, vault, audit)
    for path in tree.paths():
        broker.register(
            CredentialBinding(binding_id=f"db-item-write{path}", scope_path=path,
                              permitted_operations=frozenset(
                                  t().name for t in ALL_TOOLS)),
            secret="datastore-" + os.urandom(8).hex())

    registry = ToolRegistry()
    for tool in ALL_TOOLS:
        registry.register(tool())
    pep = ToolPEP(registry, broker, context, audit)
    # S7-D5 / I-111. ONE registry, at the composition root, over the same
    # boundary as everything else -- no privileged connection, no second
    # authorization path. Constructed HERE, before the integration, because
    # F-3's transport writes the revocation on the channel it already holds so
    # the registry row and its W-1 audit record share one transaction.
    revocations = RevocationRegistry(boundary, context)
    integration = PostgresItemIntegration(boundary, revocations=revocations)

    def on_scope_created(path: str, kind: str) -> None:
        """Post-commit, ADD_SCOPE only. Two things a new scope needs to be
        immediately usable, done with the EXISTING mechanisms: the shared
        in-process tree learns the path (the Context service, PDP, seam and
        attention all hold this same object), and the broker gets the
        per-scope datastore binding every other scope got at startup.
        NO grant is created -- James's ancestor grant covers the descendant
        by containment, verified by test. Not a hot-reload system."""
        tree.add_scope(path, kind)
        broker.register(
            CredentialBinding(binding_id=f"db-item-write{path}", scope_path=path,
                              permitted_operations=frozenset(
                                  t().name for t in ALL_TOOLS)),
            secret="datastore-" + os.urandom(8).hex())

    integration.on_scope_created = on_scope_created
    writes = ScopedWritePath(pdp, registry, pep, broker,
                             integration, "unused-see-subclass")
    approvals = ApprovalService(boundary, writes)

    budget = BudgetLedger()
    gateway = ModelGateway(lambda: pdp.available, context, audit, budget=budget)
    if RealAnthropicTransport.credential_available(CRED_REF):
        # Conversation caps: roomier than the validation run's, still hard.
        transport = RealAnthropicTransport(model=CONVERSATION_MODEL,
                                           max_tokens=1024,
                                           max_attempts=500, max_successes=500)
        gateway.register_provider(
            ProviderBinding(provider=PROVIDER, model=CONVERSATION_MODEL,
                            endpoint=ANTHROPIC_ENDPOINT,
                            api_version=ANTHROPIC_VERSION,
                            credential_ref=CRED_REF, cost_per_unit=1),
            transport)
    # No credential -> no registration -> the gateway denies with "no provider
    # binding registered" and conversation reports it could not answer. Fail
    # closed and say so; never a mock response in production wiring.

    conversation = ConversationService(gateway, pdp, boundary, approvals,
                                       budget=budget)
    attention = AttentionService(tree, context, pdp, boundary)
    # The same registry the write path holds, handed to the seam so the
    # revoking surface can PROPOSE. The read half does not go through it: the
    # conversation reads `authority_revocation` on its own bound channel, in
    # the same transaction as the rows it is checking.
    return Seam(context, pdp, boundary, auth, write_path=writes,
                approvals=approvals, tree=tree, conversation=conversation,
                attention=attention, revocations=revocations)


def main() -> int:
    port = int(os.environ.get("NOVA_PORT", "8080"))
    rp_id = os.environ.get("NOVA_RP_ID", "localhost")
    origin = os.environ.get("NOVA_ORIGIN", f"http://localhost:{port}")
    data_dir = os.environ.get("NOVA_DATA_DIR",
                              str(pathlib.Path.home() / ".nova"))
    pathlib.Path(data_dir).mkdir(parents=True, exist_ok=True)

    if not db.available():
        # The prerequisite that is MISSING, not merely that one is. See
        # `db.diagnose()`: a missing database and a stopped server used to
        # print the same sentence.
        print(f"NOVA: {db.diagnose()}")
        print("     See slice/substrate/README.md -- 'First run (local Alpha)'.")
        return 1

    seam = wire(data_dir, rp_id, origin)
    provider = "anthropic" if RealAnthropicTransport.credential_available(CRED_REF) \
        else "ABSENT (set ANTHROPIC_API_KEY; conversation will refuse until then)"
    server, bound = serve(seam, port)
    print(f"NOVA listening on {origin}  (sign in at {origin}/auth/login)")
    print(f"  conversation provider: {provider}")
    try:
        # serve() runs the server in a daemon thread; hold the process open.
        import threading
        threading.Event().wait()
    except KeyboardInterrupt:
        server.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
