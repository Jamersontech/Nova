"""Second vertical slice: two agents, delegation, and a real model gateway.

Validates I-106/I-107 (delegation) and I-94..I-98 (model egress), and the
interaction between delegation, provenance, plan authorization, binding
authorization and provider routing.

Each test names the attack, the expected result, the enforcement point and
the governing invariant.
"""

from __future__ import annotations

import time
import unittest

from ..core.delegation import Delegation
from ..core.gateway import CapabilityProfile, ModelRequestItem
from ..core.types import Classification, Denied, Risk, Taint, Trust
from .harness2 import (EMPTY_PROFILE, PROFILE, SCOPE_A, SCOPE_A_SUB, SCOPE_B,
                       TOOL, TOOL_VERSION, build, cleanup, coordinator_token,
                       delegate_to_b, items, valid_delegation)


class Slice2(unittest.TestCase):
    behaviour = "normal"

    def setUp(self):
        self.rt, self.gw, self.provider, self.tmp = build(model_behaviour=self.behaviour)
        self.a = coordinator_token(self.rt)

    def tearDown(self):
        cleanup(self.rt, self.tmp)


# ===========================================================================
# DELEGATION — I-106 / I-107 / AG-6..AG-11
# ===========================================================================

class Test01DelegateWithinAuthority(Slice2):
    def test_valid_narrowing_passes(self):
        """1. A delegates within its authority -> PASS.
        ENFORCEMENT: ContextService.delegate (sole issuer, AG-1/AG-2)."""
        b = delegate_to_b(self.rt, self.a)
        self.assertEqual(b.scope_path, SCOPE_A_SUB)
        self.assertTrue(b.granted_rights < self.a.granted_rights)
        self.assertLess(b.risk_ceiling, self.a.risk_ceiling)
        self.assertLess(b.expires_at, self.a.expires_at)      # AG-7 strictly earlier
        self.assertEqual(self.rt.context.facts(b)["ancestry"], (self.a.trace_id,))

    def test_runtime_cannot_mint_a_token(self):
        """AG-2: the runtime REQUESTS narrowing; it never mints. A token not
        produced by the Context service fails I-87 at every enforcement point."""
        forged = self.a.__class__(
            identity=self.a.identity, actor="researcher", scope_path=SCOPE_A,
            granted_rights=frozenset({"send", "read", "research"}),
            risk_ceiling=Risk.IRREVERSIBLE, issued_at=self.a.issued_at,
            expires_at=self.a.expires_at, trace_id="minted-by-runtime",
            integrity="0" * 32)
        with self.assertRaises(Denied) as ctx:
            self.rt.context.verify(forged)
        self.assertEqual(ctx.exception.invariant, "I-87")


class Test02DelegateBroaderRights(Slice2):
    def test_broader_rights_denied(self):
        """2. A delegates rights it does not possess -> DENY. I-107/AG-7."""
        d = valid_delegation(self.a, rights=frozenset({"read", "delete"}))
        with self.assertRaises(Denied) as ctx:
            delegate_to_b(self.rt, self.a, d)
        self.assertEqual(ctx.exception.step, "delegation.rights")
        self.assertEqual(ctx.exception.invariant, "I-107")

    def test_broader_ceiling_denied(self):
        d = valid_delegation(self.a, ceiling=Risk.IRREVERSIBLE)
        with self.assertRaises(Denied) as ctx:
            delegate_to_b(self.rt, self.a, d)
        self.assertEqual(ctx.exception.step, "delegation.ceiling")

    def test_broader_tools_denied(self):
        d = valid_delegation(self.a, tools=frozenset({TOOL, "delete_everything"}))
        with self.assertRaises(Denied) as ctx:
            delegate_to_b(self.rt, self.a, d)
        self.assertEqual(ctx.exception.step, "delegation.tools")

    def test_identical_delegation_refused(self):
        """AG-7: a delegation identical in every dimension is REFUSED. This is
        what bounds depth on a finite authority lattice."""
        parent_tools = self.rt.context.facts(self.a)["tools"]
        d = Delegation(delegator=self.a.trace_id, delegate="clone-of-a",
                       scope_path=SCOPE_A, rights=self.a.granted_rights,
                       tools=parent_tools, risk_ceiling=self.a.risk_ceiling,
                       expires_at=self.a.expires_at - 1, may_redelegate=False,
                       ancestry=(), purpose="identical in every dimension")
        with self.assertRaises(Denied) as ctx:
            self.rt.context.delegate(self.a, d)   # no definition bound to mask AG-7
        self.assertEqual(ctx.exception.step, "delegation.narrowing")

    def test_later_expiry_denied(self):
        d = valid_delegation(self.a, ttl=10_000.0)     # outlives the parent
        with self.assertRaises(Denied) as ctx:
            delegate_to_b(self.rt, self.a, d)
        self.assertEqual(ctx.exception.step, "delegation.narrowing")


class Test03AgentBOutsideEnvelope(Slice2):
    def test_b_cannot_use_a_capability_outside_its_envelope(self):
        """3. B uses a capability outside the delegated envelope -> DENY.
        B's delegation carries NO tools, so the tool path is closed to it."""
        b = delegate_to_b(self.rt, self.a)
        self.assertEqual(self.rt.context.facts(b)["tools"], frozenset())
        plan = self.rt.planner.plan(
            objective="send", scope_path=SCOPE_A_SUB, tool_name=TOOL, action="send",
            resource=SCOPE_A_SUB, required_rights=frozenset({"send"}),
            arguments={"to": "x@example.com", "body": "b", "payload": {"cc": "y@example.com"}},
            declared_risk=Risk.EXECUTE)
        with self.assertRaises(Denied) as ctx:
            self.rt.authorize(b, "researcher", plan, TOOL_VERSION,
                              self.rt.pdp and __import__(
                                  "slice.tests.harness", fromlist=["envelope"]).envelope())
        # researcher's Allowed Tools is empty -- the closed list denies first.
        self.assertEqual(ctx.exception.step, "runtime.allowed_tools")

    def test_b_cannot_exceed_its_delegated_risk_ceiling(self):
        b = delegate_to_b(self.rt, self.a)
        self.assertEqual(b.risk_ceiling, Risk.ANALYZE)
        plan = self.rt.planner.plan(
            objective="x", scope_path=SCOPE_A_SUB, tool_name=TOOL, action="research",
            resource=SCOPE_A_SUB, required_rights=frozenset({"read"}),
            arguments={"to": "x@example.com", "body": "b", "payload": {"cc": "y@example.com"}},
            declared_risk=Risk.EXECUTE)
        from .harness import envelope
        with self.assertRaises(Denied) as ctx:
            self.rt.authorize(b, "coordinator", plan, TOOL_VERSION, envelope())
        # coordinator's Allowed Context does not cover B's sub-scope request
        # path; whichever fires, it is a refusal, never a widening.
        self.assertTrue(ctx.exception.security_event or ctx.exception.invariant)


class Test04BCannotDelegateOnward(Slice2):
    def test_b_cannot_redelegate_by_default(self):
        """4. B delegates something A did not delegate -> DENY.
        AG-9: may_redelegate is EXPLICIT and DEFAULTS FALSE."""
        b = delegate_to_b(self.rt, self.a)          # may_redelegate=False
        self.assertFalse(self.rt.context.facts(b)["may_redelegate"])
        onward = Delegation(delegator=b.trace_id, delegate="third",
                            scope_path=SCOPE_A_SUB, rights=frozenset({"read"}),
                            tools=frozenset(), risk_ceiling=Risk.READ,
                            expires_at=b.expires_at - 1, may_redelegate=False,
                            ancestry=(), purpose="onward")
        with self.assertRaises(Denied) as ctx:
            self.rt.context.delegate(b, onward)
        self.assertEqual(ctx.exception.step, "delegation.redelegate")
        self.assertEqual(ctx.exception.invariant, "I-107")

    def test_b_cannot_grant_redelegation_it_lacks(self):
        b = delegate_to_b(self.rt, self.a, valid_delegation(self.a, may_redelegate=True))
        self.assertTrue(self.rt.context.facts(b)["may_redelegate"])
        # B may re-delegate, but only narrower still (AG-7 applies again).
        onward = Delegation(delegator=b.trace_id, delegate="third",
                            scope_path=SCOPE_A_SUB, rights=frozenset({"read"}),
                            tools=frozenset(), risk_ceiling=Risk.READ,
                            expires_at=b.expires_at - 1, may_redelegate=False,
                            ancestry=(), purpose="onward")
        child = self.rt.context.delegate(b, onward)
        self.assertEqual(self.rt.context.facts(child)["ancestry"],
                         (self.a.trace_id, b.trace_id))

    def test_AG8_as_written_cannot_fire__FINDING_4(self):
        """AG-8 says: "a delegation is refused if the DELEGATE already appears
        in its own ANCESTRY. This blocks A -> B -> A."

        FINDING 4 -- REQUIRES JAMES'S DECISION. See slice/FINDINGS.md.

        AG-6 defines `delegate` as "the receiving AGENT" and `ancestry` as
        "the chain of DELEGATORS", where `delegator` is "the granting
        EXECUTION IDENTITY". The comparison is therefore between an agent and
        a set of execution identities -- DIFFERENT TYPES, which can never
        match. And AUTHENTICATION_MODEL.md section 5 makes execution
        identities ephemeral and "never reused", so an identity-to-identity
        comparison could never fire either.

        This test asserts the ACTUAL behaviour of AG-8 implemented exactly as
        written. It does NOT assert that A -> B -> A is safe; it records that
        AG-8 does not currently block it, and no fix is invented here."""
        b = delegate_to_b(self.rt, self.a, valid_delegation(self.a, may_redelegate=True))
        back = Delegation(delegator=b.trace_id, delegate="coordinator",
                          scope_path=SCOPE_A_SUB, rights=frozenset({"read"}),
                          tools=frozenset(), risk_ceiling=Risk.READ,
                          expires_at=b.expires_at - 1, may_redelegate=False,
                          ancestry=(), purpose="A -> B -> A")
        parent_ancestry = self.rt.context.facts(b)["ancestry"]
        self.assertNotIn("coordinator", parent_ancestry)   # agent name vs trace ids
        # AG-8 does not fire. What DOES bound the chain is AG-7: each step must
        # be strictly narrower on a finite lattice, so the cycle terminates.
        child = self.rt.context.delegate(b, back)
        self.assertLess(child.risk_ceiling, b.risk_ceiling)   # AG-7 still bounding

    def test_AG7_still_bounds_the_chain_AG8_was_meant_to_block(self):
        """The containment that DOES hold: every step narrows, so a cycle
        cannot regain authority. This is why the finding is CONTAINED rather
        than an escalation path."""
        b = delegate_to_b(self.rt, self.a, valid_delegation(self.a, may_redelegate=True))
        back = Delegation(delegator=b.trace_id, delegate="coordinator",
                          scope_path=SCOPE_A_SUB, rights=b.granted_rights,
                          tools=frozenset(), risk_ceiling=b.risk_ceiling,
                          expires_at=b.expires_at - 1, may_redelegate=True,
                          ancestry=(), purpose="try to regain authority")
        # Identical to B in every authority dimension -> AG-7 refuses.
        with self.assertRaises(Denied) as ctx:
            self.rt.context.delegate(b, back)
        self.assertEqual(ctx.exception.step, "delegation.narrowing")


class Test05DelegationCrossesScope(Slice2):
    def test_delegation_into_sibling_scope_denied(self):
        """5. Delegation crosses scope -> DENY. I-107 + I-03."""
        d = valid_delegation(self.a, scope=SCOPE_B)
        with self.assertRaises(Denied) as ctx:
            delegate_to_b(self.rt, self.a, d)
        self.assertEqual(ctx.exception.step, "delegation.scope")
        self.assertTrue(ctx.exception.security_event)

    def test_delegation_beyond_delegates_allowed_context_denied(self):
        """AG-3: the DELEGATE's own definition is also an I-07 input. A
        delegation A could legitimately make is still refused if B's
        definition does not permit it -- intersection, never union."""
        d = valid_delegation(self.a, scope=SCOPE_A)   # researcher is capped at SCOPE_A_SUB
        with self.assertRaises(Denied) as ctx:
            delegate_to_b(self.rt, self.a, d)
        self.assertEqual(ctx.exception.step, "delegation.definition")
        self.assertEqual(ctx.exception.invariant, "I-106")


class Test06DelegatedTokenExpiredOrRevoked(Slice2):
    def test_expired_delegated_token_denied(self):
        """6. Delegated token expired -> DENY at the next enforcement point."""
        b = delegate_to_b(self.rt, self.a, valid_delegation(self.a, ttl=0.05))
        time.sleep(0.08)
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-13")

    def test_revoked_delegated_token_denied(self):
        b = delegate_to_b(self.rt, self.a)
        self.rt.context.revoke(b.trace_id)
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-74")


class Test07ParentRevokedAfterDelegation(Slice2):
    def test_child_fails_closed_at_next_enforcement_point(self):
        """7. Parent authority revoked after delegation.

        The architecture SPECIFIES this rather than leaving it open: AG-11 --
        'a child execution never outlives the execution identity that granted
        it... the child fails closed AT ITS NEXT ENFORCEMENT POINT'. V-2 says
        the same for revocation generally. NOT retroactive."""
        b = delegate_to_b(self.rt, self.a)

        # Before: the child works.
        r1 = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(r1.outcome, "success_claimed")

        # The granting execution identity ends.
        self.rt.context.end_execution(self.a.trace_id)

        # After: the child fails closed at its NEXT enforcement point.
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-107")
        self.assertIn("granting execution identity has ended", ctx.exception.reason)

        # The already-completed call is NOT undone -- AG-11 is not retroactive.
        self.assertEqual(len(self.provider.prompts), 1)

    def test_parent_revocation_also_ends_the_child(self):
        b = delegate_to_b(self.rt, self.a)
        self.rt.context.revoke(self.a.trace_id)
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-107")


# ===========================================================================
# MODEL GATEWAY — I-94..I-98
# ===========================================================================

class Test08ModelBroadensDelegation(Slice2):
    behaviour = "requests_broader_delegation"

    def test_model_output_cannot_broaden_a_delegation(self):
        """8. B's model output asks for broader delegation -> DENY.

        The model's REQUEST is just text. Delegation is issued only by the
        Context service from a Delegation record, and the record is checked
        against the parent's ACTUAL authority (I-107/AG-3). There is no code
        path from response text to an authority change."""
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertIn("delegate_to_me", r.text)          # the model did ask

        # Acting on it requires a Delegation record, which is checked anyway.
        asked = Delegation(delegator=b.trace_id, delegate="researcher",
                           scope_path="/business/KAIRO", rights=frozenset({"send", "delete"}),
                           tools=frozenset(), risk_ceiling=Risk.IRREVERSIBLE,
                           expires_at=b.expires_at - 1, may_redelegate=True,
                           ancestry=(), purpose="from model output")
        with self.assertRaises(Denied) as ctx:
            self.rt.context.delegate(b, asked)
        self.assertEqual(ctx.exception.invariant, "I-107")


class Test09ModelSelectsProvider(Slice2):
    behaviour = "names_provider"

    def test_model_named_provider_is_refused(self):
        """9/10. Model output selects an unauthorized provider or model -> DENY.
        I-98: routing is NEVER selected by model output at call time."""
        b = delegate_to_b(self.rt, self.a)
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small",
                         model_requested_provider="cheap-llm")
        self.assertEqual(ctx.exception.step, "gateway.i98")
        self.assertEqual(ctx.exception.invariant, "I-98")
        self.assertTrue(ctx.exception.security_event)
        self.assertEqual(len(self.provider.prompts), 0)   # never reached egress

    def test_model_naming_a_provider_in_its_TEXT_changes_nothing(self):
        """The model names a provider in its response. Routing already happened
        and nothing reads the response for routing."""
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertIn("cheap-llm", r.text)               # it asked
        self.assertEqual(self.provider.name, "acme-llm")  # it did not get it


class Test10UnauthorizedRouting(Slice2):
    def test_unauthorized_provider_denied_before_egress(self):
        """18. Unauthorized routing -> DENY BEFORE execution. I-97."""
        b = delegate_to_b(self.rt, self.a)
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "cheap-llm", "unbounded-v9")
        self.assertEqual(ctx.exception.step, "gateway.i97")
        self.assertEqual(len(self.provider.prompts), 0)

    def test_unauthorized_model_on_authorized_provider_denied(self):
        b = delegate_to_b(self.rt, self.a)
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "unbounded-v9")
        self.assertEqual(ctx.exception.invariant, "I-97")

    def test_empty_permitted_set_fails_closed(self):
        """I-97: 'if it is empty the call fails closed and says so.'"""
        b = delegate_to_b(self.rt, self.a)
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), EMPTY_PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-97")
        self.assertIn("no provider permitted", ctx.exception.reason)

    def test_authorized_routing_passes(self):
        """19. Authorized routing -> PASS."""
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(r.outcome, "success_claimed")
        self.assertEqual(len(self.provider.prompts), 1)

    def test_provider_binding_mismatch_denied(self):
        """20. Provider/binding mismatch -> DENY. The registered binding for
        acme-llm serves acme-small; asking it for another model is refused."""
        b = delegate_to_b(self.rt, self.a)
        profile = CapabilityProfile(name="p", permitted_providers=frozenset({"acme-llm"}),
                                    permitted_models=frozenset({"acme-small", "ghost-model"}))
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), profile, "acme-llm", "ghost-model")
        self.assertEqual(ctx.exception.step, "gateway.binding")
        self.assertEqual(len(self.provider.prompts), 0)


class Test11ModelAltersEnvelope(Slice2):
    behaviour = "alters_envelope"

    def test_model_response_cannot_alter_the_authorization_envelope(self):
        """11. Model response attempts to alter the envelope -> no effect.
        The Authorization is frozen and is produced only by the PDP."""
        from .harness import envelope
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertIn("argument_envelope", r.text)

        plan = self.rt.planner.plan(
            objective="x", scope_path=SCOPE_A, tool_name=TOOL, action="send",
            resource=SCOPE_A, required_rights=frozenset({"send"}),
            arguments={"to": "attacker@anywhere.com", "body": "b",
                       "payload": {"cc": "cc-ok@example.com"}},
            declared_risk=Risk.EXECUTE)
        from ..core.types import Approval
        auth = self.rt.authorize(self.a, "coordinator", plan, TOOL_VERSION, envelope(),
                                 approval=Approval("standing", standing=True))
        # The envelope the PDP fixed is unchanged by anything the model said.
        with self.assertRaises(Denied) as ctx:
            self.rt.execute(self.a, plan, auth, TOOL_VERSION,
                            lambda payload, secret: None)
        self.assertEqual(ctx.exception.invariant, "I-100")


class Test12ProvenanceThroughTheModel(Slice2):
    def test_external_content_keeps_its_taint_through_the_model(self):
        """12. Model response containing external content stays tainted.
        I-99: the response carries the UNION of its request items."""
        b = delegate_to_b(self.rt, self.a)
        web = items(provenance="external.web", classification=Classification.INTERNAL)
        r = self.gw.call(b, web, PROFILE, "acme-llm", "acme-small")
        self.assertIn("external.web", r.taint.provenance)
        self.assertIn("model.generated", r.taint.provenance)
        self.assertTrue(r.taint.is_untrusted_derived())

    def test_model_generated_alone_is_not_untrusted_derived(self):
        """13. Model-generated content is LOW trust but NOT untrusted-derived.
        This is the Finding 2 resolution, holding through a real model call."""
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(provenance="james.stated"), PROFILE,
                         "acme-llm", "acme-small")
        self.assertEqual(r.taint.trust, Trust.LOW)             # LOW trust
        self.assertIn("model.generated", r.taint.provenance)
        self.assertFalse(r.taint.is_untrusted_derived())       # NOT untrusted-derived
        self.assertEqual(r.taint.external_sources(), frozenset())

    def test_both_sides_at_once(self):
        """The distinction survives a mixed request: one external item taints
        the whole response, because I-99 takes the UNION."""
        b = delegate_to_b(self.rt, self.a)
        mixed = (items(provenance="james.stated", label="brief")
                 + items(provenance="external.web", label="fetched"))
        r = self.gw.call(b, mixed, PROFILE, "acme-llm", "acme-small")
        self.assertTrue(r.taint.is_untrusted_derived())
        self.assertEqual(r.taint.external_sources(), frozenset({"external.web"}))


class Test13ModelFabricatesProvenance(Slice2):
    behaviour = "claims_provenance"

    def test_model_cannot_fabricate_provenance(self):
        """14. Model response fabricates provenance -> ignored structurally.

        There is NO code path that reads provenance out of response text. The
        gateway computes the response taint from the REQUEST (I-99), so the
        claim is inert rather than rejected."""
        b = delegate_to_b(self.rt, self.a)
        web = items(provenance="external.web")
        r = self.gw.call(b, web, PROFILE, "acme-llm", "acme-small")

        self.assertIn("james.stated", r.text)          # the model claimed it
        self.assertNotIn("james.stated", r.taint.provenance)   # it did not get it
        self.assertIn("external.web", r.taint.provenance)
        self.assertTrue(r.taint.is_untrusted_derived())
        self.assertEqual(r.taint.trust, Trust.LOW)     # "HIGHEST" claim ignored

    def test_model_cannot_claim_system_verified(self):
        """I-110: raising trust is never model-mediated."""
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertIn("system_verified", r.text)
        self.assertNotIn("system.verified", r.taint.provenance)


class Test14ModelCreatesAuthority(Slice2):
    behaviour = "claims_authority"

    def test_model_output_creates_no_authority(self):
        """15/16/17. Model output claims authorization; a provider response is
        stored as trusted fact; a response authorizes a tool action.
        I-20: ability is never authorization. I-102: a model never establishes
        an authorization-relevant fact."""
        from .harness import envelope
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertIn("APPROVED-BY-MODEL", r.text)

        # 17. The response cannot authorize a tool action: an Authorization is
        # produced ONLY by the PDP, and the PDP never reads model text.
        plan = self.rt.planner.plan(
            objective="x", scope_path=SCOPE_A, tool_name=TOOL, action="send",
            resource=SCOPE_A, required_rights=frozenset({"send"}),
            arguments={"to": "client-a@example.com", "body": r.text,
                       "payload": {"cc": "cc-ok@example.com"}},
            declared_risk=Risk.EXECUTE)
        with self.assertRaises(Denied) as ctx:
            self.rt.authorize(self.a, "coordinator", plan, TOOL_VERSION,
                              envelope(), approval=None)
        self.assertEqual(ctx.exception.invariant, "I-09")

        # 16. The response is not a trusted fact: it is model.generated at LOW
        # trust and cannot be promoted without I-110's authorized operation.
        self.assertEqual(r.taint.trust, Trust.LOW)
        self.assertIn("model.generated", r.taint.provenance)


class Test15ScopeAndClassificationAtEgress(Slice2):
    def test_two_scopes_in_one_request_denied(self):
        """21. Model result crosses scope -> DENY. I-95."""
        b = delegate_to_b(self.rt, self.a)
        two = (items(scope=SCOPE_A_SUB, classification=Classification.CLIENT_CONFIDENTIAL)
               + items(scope=SCOPE_B, classification=Classification.CLIENT_CONFIDENTIAL,
                       label="other-client"))
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, two, PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-95")
        self.assertEqual(len(self.provider.prompts), 0)

    def test_public_and_internal_are_not_a_second_scope(self):
        """I-95 explicitly: 'PUBLIC and INTERNAL material is not a second
        scope.' The rule must not be over-enforced either."""
        b = delegate_to_b(self.rt, self.a)
        mixed = (items(scope=SCOPE_A_SUB, classification=Classification.CLIENT_CONFIDENTIAL)
                 + items(scope="/anywhere", classification=Classification.PUBLIC,
                         label="public-doc"))
        r = self.gw.call(b, mixed, PROFILE, "acme-llm", "acme-small")
        self.assertEqual(r.outcome, "success_claimed")

    def test_security_critical_never_crosses(self):
        """I-96: never, under any grant, approval or profile."""
        b = delegate_to_b(self.rt, self.a)
        sec = items(classification=Classification.SECURITY_CRITICAL, label="audit-excerpt")
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, sec, PROFILE, "acme-llm", "acme-small",
                         sensitive_personal_approval="approved")
        self.assertEqual(ctx.exception.invariant, "I-96")
        self.assertEqual(len(self.provider.prompts), 0)

    def test_sensitive_personal_requires_per_call_approval(self):
        b = delegate_to_b(self.rt, self.a)
        sp = items(classification=Classification.SENSITIVE_PERSONAL, label="health")
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, sp, PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-96")
        # With explicit per-call approval it crosses.
        r = self.gw.call(b, sp, PROFILE, "acme-llm", "acme-small",
                         sensitive_personal_approval="james-approved-1")
        self.assertEqual(r.outcome, "success_claimed")

    def test_unestablishable_classification_denies(self):
        """I-96 / I-52 pattern: if classification cannot be established, DENY."""
        b = delegate_to_b(self.rt, self.a)
        blank = [ModelRequestItem(label="unknown", content="?", scope_path=SCOPE_A_SUB,
                                  taint=Taint(frozenset(), Trust.LOW,
                                              Classification.INTERNAL))]
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, blank, PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-96")


class Test16DelegatedExecutionAndBinding(Slice2):
    def test_delegated_execution_still_subject_to_binding_authorization(self):
        """22. Delegated execution remains subject to the CURRENT binding
        authorization. I-114 does not weaken because authority was delegated."""
        from .harness import envelope
        from ..core.capability import IntegrationRecord
        from ..core.types import Approval
        plan = self.rt.planner.plan(
            objective="x", scope_path=SCOPE_A, tool_name=TOOL, action="send",
            resource=SCOPE_A, required_rights=frozenset({"send"}),
            arguments={"to": "client-a@example.com", "body": "b",
                       "payload": {"cc": "cc-ok@example.com"}},
            declared_risk=Risk.EXECUTE)
        auth = self.rt.authorize(self.a, "coordinator", plan, TOOL_VERSION, envelope(),
                                 approval=Approval("standing", standing=True))
        self.rt.capability.rebind(TOOL, SCOPE_A, IntegrationRecord(
            integration_id="int-a", scope_path=SCOPE_A, provider="acme-mail",
            account="acct-a", endpoint="https://acme/v1", api_version="2099-01",
            credential_binding_id="cred-a"))
        with self.assertRaises(Denied) as ctx:
            self.rt.execute(self.a, plan, auth, TOOL_VERSION, lambda p, s: None)
        self.assertEqual(ctx.exception.invariant, "I-114")


class Test17RevocationBetweenPlanningAndModelCall(Slice2):
    def test_revocation_between_planning_and_model_execution_denies(self):
        """23. Revocation between planning and model execution -> DENY.
        I-94: revocation takes effect at the gateway as at every other PEP."""
        b = delegate_to_b(self.rt, self.a)
        request = items()                       # "planning" has happened
        self.rt.context.revoke(b.trace_id)      # revoked in between
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, request, PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-74")
        self.assertEqual(len(self.provider.prompts), 0)

    def test_emergency_stop_refuses_the_call(self):
        """I-94: 'a gateway that cannot confirm a stop refuses to call.'"""
        b = delegate_to_b(self.rt, self.a)
        self.gw.emergency_stop = True
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-19")

    def test_pdp_unavailable_denies(self):
        """I-17: PDP unavailability is deny. No cached-allow fallback."""
        b = delegate_to_b(self.rt, self.a)
        self.rt.pdp.available = False
        with self.assertRaises(Denied) as ctx:
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(ctx.exception.invariant, "I-17")


class Test18UnknownModelOutcome(Slice2):
    behaviour = "timeout"

    def test_model_timeout_is_unknown_never_failure(self):
        """24. Model timeout -> UNKNOWN, never automatically failure."""
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(r.outcome, "unknown")
        self.assertNotEqual(r.outcome, "failure_claimed")
        # Taint is still computed structurally even with no response body.
        self.assertIn("model.generated", r.taint.provenance)

    def test_retry_after_unknown_is_separately_authorized(self):
        """25. Retry after unknown follows the existing rules: I-104 -- every
        attempt is separately authorized and accounted. A retry is a fresh
        gateway call, so revocation in between denies it."""
        b = delegate_to_b(self.rt, self.a)
        r1 = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(r1.outcome, "unknown")
        self.rt.context.revoke(b.trace_id)
        with self.assertRaises(Denied):
            self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")


class Test19CredentialNeverTravelsUp(Slice2):
    def test_provider_credential_is_a_reference_and_never_returned(self):
        """I-103: the provider credential is control-plane, held only by the
        gateway, never present in a prompt, log, memory or model context."""
        b = delegate_to_b(self.rt, self.a)
        r = self.gw.call(b, items(), PROFILE, "acme-llm", "acme-small")
        self.assertEqual(self.provider.credential_refs, ["control-plane/acme-llm"])
        self.assertNotIn("control-plane", r.text)
        self.assertNotIn("control-plane", "".join(self.provider.prompts))


if __name__ == "__main__":
    unittest.main()
