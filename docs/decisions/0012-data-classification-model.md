# 0012 — Six-Level Data Classification

**Status:** **Accepted**
**Proposed:** 2026-08-12 — Section 03
**Accepted:** 2026-08-12 by James, as amended in commit 0917de5
**Section:** 03

## Decision
Classify every stored item as PUBLIC, INTERNAL, CONFIDENTIAL, CLIENT-CONFIDENTIAL,
SENSITIVE-PERSONAL, or SECURITY-CRITICAL. Classification controls storage, access, memory
writes, model exposure, external transmission, logging, retention, deletion, backups, and
exports. Unclassified is not a state. No legal or regulatory requirement is invented;
requirements can later attach as constraints on existing levels.

## Context
Section 03 must define how data restrictions are expressed. The scope tree answers *where*
data lives; classification answers *what may be done with it there*.

## Problem
Scope alone is insufficient. Two items in the same client scope — a public brochure and a
health record — need different handling. Without classification, every rule must be written
per data type forever.

## Options Considered
1. **Scope only, no classification.** Fewest concepts; cannot distinguish items within a
   scope, forcing per-type rules everywhere.
2. **A single sensitivity scale (1–5).** Familiar; implies the restrictions differ only in
   strength, when client-confidentiality and personal sensitivity differ in *kind*.
3. **Six named levels by handling rules.** Expresses real differences; six levels to assign
   correctly.
4. **Free-form tags.** Maximum flexibility; no enforceable semantics, so nothing can be
   tested.

## Decision Made
Option 3.

## Reason
CLIENT-CONFIDENTIAL and SENSITIVE-PERSONAL are not points on one scale. Client data may be
summarized within its client but never promoted; sensitive-personal data may never be
summarized at all. A single scale cannot express that difference, and collapsing them would
lose exactly the protection that matters.

## Tradeoffs
**Advantages:** one mechanism controls ten concerns; derived-data inheritance becomes
mechanical (ADR 0010); future regulatory requirements attach as constraints rather than
requiring a new model; testable.
**Disadvantages:** every item needs a classification; misclassification is a real risk,
particularly at creation; six levels require judgment; SENSITIVE-PERSONAL depends on LIFE
Areas actually being marked.

## Consequences
Default inside a client scope is CLIENT-CONFIDENTIAL. Downward reclassification is a
reviewed operation never performed by an agent. Invariants `I-26`–`I-30`.

## What Would Change This
Practice showing a level is unused or that two collapse without loss — most likely INTERNAL
and CONFIDENTIAL. Adding a level for a regulatory regime would be a C3 change.
