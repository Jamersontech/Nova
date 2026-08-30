"""`I-07` / `I-106`: a token may not exceed the ceiling its grant confers.

THE GAP THIS CLOSES. `issue_root` checked that a grant EXISTED for every
requested right and never looked at what that grant permitted. A grant carries
a `max_risk`; nothing compared the requested ceiling against it. So a `write`
grant conferring `EXECUTE` would issue a token at `IRREVERSIBLE` for the
asking, and the PDP -- which trusts the token's ceiling at step 6 -- would then
authorize an irreversible act on it.

Nothing failed. `Grant.max_risk` was written and never read: three occurrences
in the whole repository, all of them the dataclass field, its constructor
parameter and the constructor call. The field looked like a control and was a
comment.

WHY IT MATTERS BEYOND THE FIELD BEING DEAD. `I-07` makes an execution's
authority the INTERSECTION of agent definition, granting identity, token and
risk ceiling -- *"No mechanism produces a union"* -- and a token above its own
grant is precisely such a union. `I-106` requires issuance to refuse any
request whose resulting token would exceed James-created grants (`I-10`).
Neither held on the ceiling axis.

THE SHAPE OF THE FIX, and why it is not a new kind of control: every other axis
was already enforced at issuance. The agent definition's context, rights and
ceiling; a grant's scope (via `find_grant`'s containment) and its rights (via
the loop). Only a grant's ceiling was unchecked. This is the missing third of
an existing triple.

DENY, NEVER CLAMP. `AG-4`: refusal is total and *"Nothing is trimmed to fit."*
A silently lowered ceiling would hand back a token the caller never asked for
and never checked -- which is how an escalation becomes a downgrade nobody
notices.

No database: `ScopeTree` and `ContextService` are in-memory, and the control
lives entirely at issuance. There is nothing here that a PostgreSQL fixture
would make more real.

Run:  python3 -m unittest slice.tests.test_grant_ceiling
"""

from __future__ import annotations

import unittest

from ..core.context_service import ContextService
from ..core.scope_tree import ScopeTree
from ..core.types import Denied, Risk

DOMAIN = "/business"
CLIENT = "/business/client-a"
DEEPER = "/business/client-a/project"


class GrantCeilingTest(unittest.TestCase):

    def setUp(self):
        self.tree = ScopeTree()
        self.tree.add_scope(DOMAIN, "domain")
        self.tree.add_scope(CLIENT, "client")
        self.tree.add_scope(DEEPER, "place")
        # Exactly what `tree_store.READ_RIGHTS` confers in production:
        #   read -> READ,  write -> EXECUTE
        self.tree.james_grants("james", "read", "*", CLIENT, Risk.READ)
        self.tree.james_grants("james", "write", "*", CLIENT, Risk.EXECUTE)
        self.context = ContextService(self.tree, secret=b"grant-ceiling-suite")

    def issue(self, rights, ceiling, scope=CLIENT, identity="james", **kw):
        return self.context.issue_root(
            identity=identity, actor="james", scope_path=scope,
            rights=frozenset(rights), ceiling=ceiling, ttl=60, **kw)

    def assert_refused(self, rights, ceiling, scope=CLIENT, **kw):
        with self.assertRaises(Denied) as caught:
            self.issue(rights, ceiling, scope, **kw)
        return caught.exception

    # =======================================================================
    # The escalation, refused
    # =======================================================================

    def test_01_a_read_grant_cannot_obtain_an_execute_ceiling(self):
        """`read` confers `READ`. Asking for `EXECUTE` on it is an escalation
        across the boundary between looking and acting."""
        denial = self.assert_refused({"read"}, Risk.EXECUTE)
        self.assertEqual(denial.invariant, "I-106")

    def test_02_a_write_grant_cannot_obtain_an_irreversible_ceiling(self):
        """The case measured before the fix: `write` confers `EXECUTE`, and a
        token at `IRREVERSIBLE` was issued for the asking. ADR 0052 element 8
        turns on this being impossible -- an `EXECUTE` grant must not authorize
        an irreversible act."""
        denial = self.assert_refused({"write"}, Risk.IRREVERSIBLE)
        self.assertEqual(denial.invariant, "I-106")

    def test_03_the_denial_is_a_security_event_and_names_what_was_exceeded(self):
        """Marked `security_event`, like the agent-narrowing denials beside it:
        a request for authority above one's grant is a boundary violation, not
        a retryable error."""
        denial = self.assert_refused({"write"}, Risk.IRREVERSIBLE)
        self.assertTrue(denial.security_event)
        self.assertIn("IRREVERSIBLE", denial.reason)
        self.assertIn("EXECUTE", denial.reason)
        self.assertIn("write", denial.reason)

    def test_04_a_read_grant_cannot_obtain_irreversible_either(self):
        self.assertEqual(
            self.assert_refused({"read"}, Risk.IRREVERSIBLE).invariant, "I-106")

    # =======================================================================
    # Everything legitimate still issues -- the half that makes it a control
    # rather than a wall
    # =======================================================================

    def test_05_a_request_equal_to_the_grant_ceiling_succeeds(self):
        self.assertEqual(self.issue({"write"}, Risk.EXECUTE).risk_ceiling,
                         Risk.EXECUTE)
        self.assertEqual(self.issue({"read"}, Risk.READ).risk_ceiling, Risk.READ)

    def test_06_a_lower_request_succeeds(self):
        for ceiling in (Risk.PREPARE, Risk.ANALYZE, Risk.READ):
            with self.subTest(ceiling=ceiling.name):
                self.assertEqual(
                    self.issue({"write"}, ceiling).risk_ceiling, ceiling)

    def test_07_the_production_issuance_patterns_are_unchanged(self):
        """What the seam and attention actually ask for. If either of these
        ever refuses, the fix has broken the application rather than the
        escalation."""
        self.assertIsNotNone(self.issue({"write"}, Risk.EXECUTE))   # _execute_token
        self.assertIsNotNone(self.issue({"read"}, Risk.READ))       # attention/read

    # =======================================================================
    # Intersection, not union
    # =======================================================================

    def test_08_the_bound_is_the_highest_ceiling_any_requested_right_confers(self):
        """A token's ceiling is a MAXIMUM over the acts it may authorize, not a
        per-right promise. A `{read, write}` token legitimately reaches EXECUTE
        -- the EXECUTE-class acts under it need `write`, granted at EXECUTE --
        and that combination is the ordinary shape of an authorized execution.

        Requiring every right to confer the ceiling would refuse it, denying the
        application rather than the escalation. What stays impossible is a
        ceiling NO grant confers.
        """
        self.assertIsNotNone(self.issue({"read", "write"}, Risk.EXECUTE))
        self.assertEqual(
            self.assert_refused({"read", "write"}, Risk.IRREVERSIBLE).invariant,
            "I-106")

    def test_08b_a_lone_read_right_is_still_bounded_by_READ(self):
        """The other side of the same rule: without a right conferring more,
        there is nothing to raise the bound."""
        self.assertEqual(
            self.assert_refused({"read"}, Risk.EXECUTE).invariant, "I-106")

    def test_09_a_missing_grant_is_still_I14_not_a_ceiling_failure(self):
        """The two refusals stay distinct: absent authority is `I-14`, and
        excessive authority is `I-106`. Collapsing them would make the audit
        record say the wrong thing about what went wrong."""
        self.assertEqual(
            self.assert_refused({"admin"}, Risk.READ).invariant, "I-14")

    # =======================================================================
    # The lookup path cannot be walked around
    # =======================================================================

    def test_10_scope_inheritance_carries_the_grant_ceiling_with_it(self):
        """A grant at an ancestor covers descendants -- and confers the same
        ceiling there. Reaching a deeper scope must not shed the bound: if it
        did, the fix would be bypassable by asking one level down."""
        self.assertIsNotNone(self.issue({"write"}, Risk.EXECUTE, scope=DEEPER))
        self.assertEqual(
            self.assert_refused({"write"}, Risk.IRREVERSIBLE, scope=DEEPER).invariant,
            "I-106")

    def test_11_a_broader_grant_elsewhere_does_not_lift_this_scope(self):
        """A second identity's generous grant is not this identity's. The
        lookup is keyed on subject, so nothing here leaks sideways."""
        self.tree.james_grants("mallory", "write", "*", DOMAIN, Risk.IRREVERSIBLE)
        self.assertEqual(
            self.assert_refused({"write"}, Risk.IRREVERSIBLE).invariant, "I-106")

    def test_12_a_revoked_grant_confers_nothing(self):
        """`find_grant` skips revoked grants, so a revoked high grant cannot
        supply a ceiling. Checked because the ceiling now depends on WHICH
        grant answers, not merely on one existing."""
        high = self.tree.james_grants("james", "purge", "*", CLIENT,
                                      Risk.IRREVERSIBLE)
        self.assertIsNotNone(self.issue({"purge"}, Risk.IRREVERSIBLE))
        self.tree.revoke(high)
        self.assertEqual(
            self.assert_refused({"purge"}, Risk.IRREVERSIBLE).invariant, "I-14")

    def test_13_the_tracked_issuer_is_bound_by_the_same_rule(self):
        """`issue_root_tracked` delegates to `issue_root`, so it must inherit
        the check rather than route around it."""
        with self.assertRaises(Denied) as caught:
            self.context.issue_root_tracked(
                identity="james", actor="james", scope_path=CLIENT,
                rights=frozenset({"write"}), ceiling=Risk.IRREVERSIBLE, ttl=60)
        self.assertEqual(caught.exception.invariant, "I-106")

    # =======================================================================
    # The agent-definition axis still narrows, and still only narrows
    # =======================================================================

    def test_14_agent_ceiling_narrowing_still_refuses(self):
        """The pre-existing `I-106` check, unchanged by this work."""
        denial = self.assert_refused({"write"}, Risk.EXECUTE,
                                     agent_risk_ceiling=Risk.PREPARE)
        self.assertEqual(denial.invariant, "I-106")
        self.assertIn("agent risk ceiling", denial.reason)

    def test_15_an_agent_ceiling_cannot_WIDEN_past_the_grant(self):
        """The direction that matters. A generous agent definition is still
        capped by James's grant -- narrowing mechanisms narrow, and never
        licence. `I-106`, `I-107`."""
        self.assertEqual(
            self.assert_refused({"write"}, Risk.IRREVERSIBLE,
                                agent_risk_ceiling=Risk.IRREVERSIBLE).invariant,
            "I-106")

    def test_16_agent_rights_and_context_narrowing_are_untouched(self):
        self.assertIn("agent Permissions",
                      self.assert_refused({"write"}, Risk.EXECUTE,
                                          agent_allowed_rights=frozenset({"read"})).reason)
        self.assertIn("Allowed Context",
                      self.assert_refused({"write"}, Risk.EXECUTE,
                                          agent_allowed_context=DEEPER).reason)

    # =======================================================================
    # INVERSION -- the check is what refuses
    # =======================================================================

    def test_17_INVERSION_without_the_comparison_the_escalation_succeeds(self):
        """Re-runs issuance with the grant raised to `IRREVERSIBLE` -- the only
        difference being what the grant confers. It issues. So the refusal in
        `test_02` comes from the comparison against the grant, not from
        something incidental about `IRREVERSIBLE` tokens."""
        self.tree.james_grants("james", "purge", "*", CLIENT, Risk.IRREVERSIBLE)
        token = self.issue({"purge"}, Risk.IRREVERSIBLE)
        self.assertEqual(token.risk_ceiling, Risk.IRREVERSIBLE,
                         "a grant that DOES confer IRREVERSIBLE was refused -- "
                         "the check is over-broad and the inversion proves nothing")


if __name__ == "__main__":
    unittest.main()
