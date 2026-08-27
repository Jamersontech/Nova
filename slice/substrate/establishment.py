"""The five establishment rules -- ONE definition, at the layer they belong to.

`I-111`'s read half, lifted OUT of `conversation.py` unchanged. Nothing about
the rules is new here and nothing about them is different: this module holds the
same function that has always decided whether a persisted row's security state
can be established, at the only layer from which every caller can reach it.

WHY IT MOVED, WHICH IS A DEPENDENCY FACT AND NOT A PREFERENCE
------------------------------------------------------------
The function's entire dependency set is `Taint`, `Trust` and `Classification`.
It takes rows and a revoked set as plain arguments and touches no channel, no
PDP, no boundary, no SQL and no `self`. It was already pure; it was simply
parked above the modules that need it.

`conversation.py` imports `ApprovalService`, so `approval_flow.py` importing the
rules back out of `conversation.py` would be a cycle:

    approval_flow -> conversation -> approval_flow

Not because of what the rules NEED, but because of where they SAT. A leaf that
depends only on `core.types` has one correct home, and this is it:

    core.types  <-  establishment  <-  conversation
                                   <-  approval_flow

WHY ONE DEFINITION MATTERS MORE THAN THE TIDINESS
-------------------------------------------------
The alternative was to restate the rules wherever they are needed. Two
definitions of "establishable" can drift, and a drift would make one caller
disagree with another about whether a row's authority is known -- the same
hazard `F-13`'s single `_REVOKED_MARK` constant exists to prevent, one level
up. So the rules are shared rather than copied, deliberately.

WHAT DID NOT CHANGE
-------------------
Everything. The body and docstring below are the ones that were in
`conversation.py`, verbatim; the only edit is the function's name.
`ConversationService._establish` remains, delegating here, so both production
call sites and the test that calls it directly are untouched.

This module decides no authorization, opens no channel, and reads nothing. It
classifies rows a caller has already read through its own authorized path.
"""

from __future__ import annotations

from ..core.types import Classification, Taint, Trust


def establish(rows, revoked):
    """I-111's read half: restore the persisted security state, or withhold.

    Returns `(kept, withheld)`, where each kept row is
    `(ref, content, taint, revoked_authority)` -- the restored taint, and
    BESIDE it a structured flag for a fact that is not part of the taint.

    UNKNOWN AND REVOKED ARE DIFFERENT (F-13). That distinction is the whole
    of `S7-D5` -- ADR 0033 §4, and `MEMORY_MODEL.md` §4 rule 8.

    WITHHELD -- the security state CANNOT BE ESTABLISHED. Each of these is
    a separate reason, and none is recoverable by inference; guessing any
    of them would invent authority at read time, which `I-110` forbids.

        provenance / trust / classification NULL  unknown taint
        delegation_ancestry NULL                  unknown lineage
        creating_authority NULL                   unknown author
        ancestry non-empty                        ancestors' revocation
                                                  state is NOT
                                                  establishable from this
                                                  scope (I-03/I-86), so the
                                                  lookup is incomplete

    The ancestry rule is the subtle one. A delegate's ancestors may have
    executed in BROADER scopes, whose revocation records a channel bound
    here cannot see. "Could not check" must never become "not revoked", so
    a non-empty ancestry withholds rather than guesses. An EMPTY ancestry
    is different in kind: the item was created by a root execution whose
    scope is this row's own scope, so its revocation record -- if any --
    is necessarily visible here, and absence is a complete answer.

    Legacy rows (written before I-111) have NULL throughout and are
    withheld by the first rule. They are not backfilled, not assumed to be
    `james.stated`, and not treated as trusted.

    LABELLED -- the authority IS established, and is established as
    REVOKED. `MEMORY_MODEL.md` §4 rule 8 and ADR 0033 §4 (`S7-D5`): such a row
    is "RETAINED... and its revocation state is EXPOSED at retrieval.
    Nothing is automatically deleted, downgraded, invalidated, promoted, or
    reclassified... The CONSUMING AUTHORITY decides", because "revocation
    happens for many reasons and only some impeach what was learned".

    This USED to withhold, in the same branch as the five unknowns above.
    That applied a rule for UNKNOWN state to KNOWN state: nothing here is
    unestablishable -- the revocation record was found. F-13 separates
    them.

    WHY A FLAG AND NOT PROVENANCE. Revocation is not an ORIGIN; it is a
    later fact ABOUT an authority. Putting it in `provenance` would make a
    set `I-38` calls immutable change after the fact, and would read as if
    the content came from somewhere it did not. Trust and classification
    are untouched for the same reason rule 8 gives: revocation "does not
    re-weight". The row is returned exactly as it was established, plus one
    additional fact about it.
    """
    kept, withheld = [], 0
    for ref, body, provenance, trust, classification, ancestry, author in rows:
        if (provenance is None or trust is None or classification is None
                or ancestry is None or author is None
                or ancestry):          # ancestors unestablishable from here
            withheld += 1
            continue
        kept.append((ref, body, Taint(frozenset(provenance), Trust(trust),
                                      Classification(classification)),
                     author in revoked))
    return kept, withheld
