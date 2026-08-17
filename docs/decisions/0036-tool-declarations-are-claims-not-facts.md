# 0036 — Tool Declarations Are Claims, Not Facts

**Status:** **Accepted** — 2026-08-15
**Proposed:** 2026-08-14 — Section 10
**Accepted:** 2026-08-15 — by James, at the ADR Decision Gate, on implementation evidence from the three vertical slices
**Section:** 10
**Resolves:** `S10-D1`

## Decision

**A tool definition's security-relevant fields are claims made by the tool, not verified facts about
it. Where a claim is absent, incomplete, or unparseable, the enforcement point assumes the most
consequential interpretation.**

**No new invariant is created.** `I-100` already requires consequence-determining arguments to be
checked against the envelope and already says *"Tools declare which arguments are
consequence-determining, and one that does not is not registered."* `MT-6` already refuses to
register an incomplete definition. **What was undefined is what makes a declaration complete** — and
that is a definition belonging in the document that specifies the field
(`TOOL_AND_INTEGRATION_ARCHITECTURE.md` §2), exactly as Section 09 defined *source identity* inside
`PROVENANCE_AND_TRUST.md` §2 rather than minting an invariant for it. `I-100` remains the governing
security invariant and becomes harder to defeat.

Concretely, three rules:

**1. Argument classification is total, or the tool is not registered.** A tool's
`consequence-determining args` declaration must classify **every argument in its input schema** as
either consequence-determining or expressive. A schema argument the declaration does not mention
makes the definition incomplete, and `MT-6` already refuses to register an incomplete definition.
**Totality reaches every leaf the schema exposes** — a structured argument classified as one unit
would otherwise hide a consequential field inside an expressive object, so either every leaf is
classified or the object is consequence-determining as a whole. **And a schema change re-opens the
question:** a newly added argument is unclassified, so the new tool version is not registered until
it is classified, and the check cannot be skipped by growing the schema after approval.

**2. The default is consequence-determining, not expressive.** An argument that is present but
unclassified, or whose classification cannot be parsed, is treated as **consequence-determining**
and checked against the envelope (`I-100`). Section 05's declaration was opt-in — declare which
arguments *are* consequential. **This inverts it:** every argument is consequential unless
explicitly declared otherwise.

**3. The same default governs the other security-relevant claims.** An absent or unparseable
`risk class` does not default to a low class — the action is denied until a class is derivable,
which is `I-101` **already stated** and is restated here only so the rule reads as one rule. An
absent or unparseable `idempotency` claim means **not idempotent**, so the reliability layer does
not auto-retry (`RELIABILITY_ARCHITECTURE.md`). An absent `required rights` declaration is not an
empty requirement — the definition is incomplete and is not registered.

**What this decision does not claim.** It does **not** verify that a declaration matches the tool's
actual behaviour. Nothing in NOVA can do that without understanding what the tool does, and the only
components capable of that judgement are models, which `I-101`, `I-102` and `I-110` all bar from
this role. **A tool that declares `body` expressive when its implementation parses `body` for
recipients is not detected by this decision, and is recorded as a residual (`T-37`).**

## Context

Section 05 added `consequence-determining args` to the tool definition so `I-100` could check an
argument value against the envelope the authorization fixed.
`TOOL_AND_INTEGRATION_ARCHITECTURE.md` §2 already required `required rights: minimum permissions —
no more`, a `risk class`, and mandatory `idempotency`; §6 makes adding a tool C2 and changing its
risk class or rights C3.

## Problem

**Every security-relevant property of a tool is declared by the tool, and each one is an input to
authorization.** `required rights` feeds the PDP's grant lookup; `risk class` is the floor `I-101`
raises from and the trigger for approval; `idempotency` decides whether the reliability layer may
retry a side effect; `consequence-determining args` decides what `I-100` checks; `cost profile`
feeds `I-105`.

**The stated verification is procedural.** §2 says an over-broad declaration is *"a defect, caught
in review and by permission tests"* — but permission tests can only exercise **declared** rights,
and review is James reading a declaration, not observing behaviour.

**Over-declaration and under-declaration are different failure classes, and the repository has only
addressed one.** Section 08's cross-section analysis established that a tool declaring *more* than
it needs is **authorized breadth** — James approved it, `T-16` records it as unmitigable, and that
is a governance matter rather than a security hole. **Under-declaration is the opposite failure:**
the tool does **more than its declaration says**, so the system acts beyond what was authorized.
That is the failure class *"the system gave something more than James authorized"*, and James
approving the definition does not help, because he approved a claim about the tool rather than the
tool.

**The silent case is the one that matters.** `send_email(to, subject, body, attachments)` declares
`to` and `attachments` consequence-determining and says nothing about `body`. Under Section 05's
opt-in reading, `body` is unchecked. If the implementation or the provider treats content in `body`
as addressing — a `cc:` directive, an auto-fetched URL — then `body` determines what the action
affects, `I-100` faithfully checks the wrong fields, and **every enforcement point passes**. Nobody
lied; the declaration was simply silent, and silence read as "harmless".

## Options Considered

1. **Status quo — opt-in declaration, trust the definition.** Zero cost. Leaves every unmentioned
   argument unchecked and makes silence the most dangerous possible declaration.
2. **Require independent verification of declarations.** Strongest in principle. Requires a
   component that understands what a tool does; the only candidates are models, and `I-101`,
   `I-102` and `I-110` all bar a model from establishing an authorization-relevant fact. It would
   create the new trust dependency doing exactly the work the architecture forbids.
3. **Invert the default and require totality**, treating absent or unparseable claims as maximally
   consequential. Removes the silent case without claiming semantic verification.
4. **Constrain tools structurally** — permit only tools whose consequences are mechanically derivable
   from their schema. Would exclude most useful integrations, since a mail API's consequences are a
   property of the provider, not the signature.

## Decision Made

Option 3.

## Reason

**This is the repository's existing default-closed pattern applied to declarations.** `I-14` makes
absence of a grant a denial. `I-52` makes unavailable classification resolve to the strictest
applicable level. `I-79` makes a missing scope a denial rather than a default scope. `I-93` makes an
unwritable audit record fail the operation closed. **Every one of these says the same thing: the
absence of information is not permission.** The tool declaration was the one place where absence
read as "not consequential", and this aligns it with everything else.

**Totality is what makes the default meaningful.** Inverting the default alone would let a
definition omit the schema argument entirely; requiring the classification to cover every schema
argument means the author must make a decision about each one, and `MT-6` already refuses an
incomplete definition, so no new refusal mechanism is created.

**Option 2 was rejected on the same ground Sections 05–09 rejected model-mediated judgement.** A
declaration verifier would have to know what the tool does. That is semantic understanding, the only
available source is a model, and `I-102` and `I-110` exist precisely to stop a model establishing
facts that authorization depends on. Building it would introduce a trust dependency that the rest of
the architecture is organised to avoid.

**And the honest limit is stated rather than engineered around.** This closes the *silent*
under-declaration. It does not close the *wrong* one. Sections 05–09 each ended with a residual of
this shape — over-wide argument envelopes, over-wide agent envelopes, over-wide plan envelopes — and
this is the same family: **a declaration the architecture can bound but cannot validate.**

## Tradeoffs

**Advantages:** the silent case disappears; declarations align with `I-14`/`I-52`/`I-79`'s
default-closed pattern; no new component, verifier, or trust dependency; `MT-6`'s existing refusal
carries the totality rule; no new governance class.

**Disadvantages:** **tool authoring becomes materially heavier** — every argument needs a
justified classification, and expressive arguments must be argued for rather than assumed. The
predictable failure mode is authors classifying everything consequence-determining to avoid thought,
which makes envelopes wide and pushes work toward approval, the same pressure ADR 0030 records for
agent creation. **Existing declarations written under the opt-in reading become incomplete**, so
this is a breaking change for any tool defined before it. And **the wrong-declaration case remains
entirely open** — a tool that mis-classifies deliberately or by error is undetected.

## Consequences

- `TOOL_AND_INTEGRATION_ARCHITECTURE.md` §2 is amended; `THREAT_MODEL.md` gains `T-37`;
  `KNOWN_RISKS.md` §3.10 records the residuals. **This ADR carries its own amendment list (below)**
  rather than minting a separate amendments ADR — the surface is three documents and one decision,
  and Sections 07 and 09 set the precedent for folding.
- **`I-100` is unchanged in substance and becomes harder to defeat**: it still checks
  consequence-determining arguments against the envelope; what changes is which arguments qualify.
- **`I-101` is unchanged**: the tool's declared risk class remains a floor the context may raise,
  and an underivable class denies rather than defaulting low.
- **The consequence of a tool is partly a property of its *binding*, not only its definition** — the
  same `send_email` reaches different providers per scope (§1), and provider behaviour is not in the
  definition. **Recorded and deliberately not resolved: this belongs to Section 11 (Integration
  Architecture).**

## The amendments

**All were accepted by James on 2026-08-15 together with this ADR**, at the ADR Decision Gate.

| # | Document | Section / status | Change |
| --- | --- | --- | --- |
| 1 | `TOOL_AND_INTEGRATION_ARCHITECTURE.md` §2 | 02 · Active | New §2.1: declaration totality; default consequence-determining; claims-not-facts rule |
| 2 | `THREAT_MODEL.md` | 03 · Active | `T-37`. `T-16`'s residual **not reduced** |
| 3 | `KNOWN_RISKS.md` §3.10 | 03 · Active | Section 10 residuals |

**`INVARIANTS.md` is deliberately not amended.** No new invariant is created; `I-01`–`I-113` are
byte-identical to their accepted text. `I-14`, `I-52`, `I-79`, `I-100`, `I-101`, `I-102`, `I-110`
and `I-113` are all untouched — `I-100` and `MT-6` govern, and this ADR defines what satisfying
them requires.

**One correction of an earlier defect, in the same block.** §2's Section 05 amendment note is
headed *"ACCEPTED by James 2026-08-14"* but still closes *"both **Proposed**; the field is removed
and the accepted list restored if they are rejected."* ADRs 0025 and 0028 **are** Accepted; the
closing line is a stale marking left by the Section 05 acceptance pass, of the same kind Section 04
left behind. It is corrected here because Section 10 amends this exact block. **No text changes
meaning** — only the status label is brought into line with the ADRs it cites.

## What Would Change This

A means of validating a declaration against behaviour that does not rest on a model's judgement —
for example a tool contract the external provider itself attests to. That would argue for
verification in addition to the default, never for restoring silence as a safe declaration.
