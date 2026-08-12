# Threat Model

**Status:** Proposed — Section 03, pending James's approval.
**Purpose:** Analyze what actually goes wrong, what defends against it, and what risk
remains.

**Nothing here is claimed impossible unless the architecture genuinely makes it so.** Where
a defense is procedural or unbuilt, that is stated.

---

## 1. Threats

### T-01 Malicious agent
**Failure:** An agent deliberately attempts to read another client, exfiltrate credentials,
or widen its authority.
**Defense:** Token scope checked at every enforcement point (`I-03`, `I-16`); rights are an
intersection (`I-07`); credentials never reach agents (`I-22`); repeated boundary attempts
are a failure condition, not a retryable error.
**Residual:** It can still do damage *within* its authorized scope. Least privilege bounds
the blast radius; it does not eliminate it.

### T-02 Confused agent
**Failure:** An agent believes it is in Client A's context while acting on Client B's
resource — the most likely real-world failure.
**Defense:** Resource ownership is checked against the token, not against the agent's belief
(`I-03`, `I-16`); context is re-validated before `EXECUTE`
([`CONTEXT_ARCHITECTURE.md`](./CONTEXT_ARCHITECTURE.md) §4); ambiguity stops rather than
guesses.
**Residual:** Low for cross-scope; **real within a scope** — a confused agent can perform the
wrong correct-looking action on the right client. Approval gates high-risk actions;
verification catches some of the rest.

### T-03 Prompt injection via client content
**Failure:** A client's repository, email, or website contains instructions the model
follows.
**Defense:** External content is data, never instruction; untrusted content may inform but
never escalate a plan (`I-40`); credentials are unreachable from the model path (`I-22`);
sandboxed coding agents hold nothing to exfiltrate.
**Residual:** **Significant and unavoidable.** Injection can still cause wrong *in-scope*
work and wasted effort. It cannot cross a client boundary or reach a credential — that is
the guarantee, and it is narrower than "injection is solved."

### T-04 Compromised integration
**Failure:** An external system returns manipulated data or is taken over.
**Defense:** All external data is untrusted with recorded provenance and low trust; contract
changes fail closed rather than adapting (`RELIABILITY_ARCHITECTURE.md`); the credential is
scoped to one service in one scope (`I-23`).
**Residual:** Poisoned data enters memory at low trust and can influence inference. Mitigated
by provenance labelling and the `PREPARE` ceiling on untrusted-influenced plans.

### T-05 Credential theft
**Failure:** An attacker obtains a credential.
**Defense:** Secrets exist only in secrets storage and only at the outbound boundary
(`I-21`, `I-22`); scoped to one node (`I-23`); expiring; individually revocable (`I-25`).
**Residual:** A compromise of secrets storage itself is catastrophic. That storage is a
deferred technology decision (`D-10`) and is the single highest-value target in the system.

### T-06 Confused deputy
**Failure:** A low-authority actor induces a high-authority component to act for it.
**Defense:** Authorization evaluates the **execution identity**, not the caller
([`SCOPE_AND_IDENTITY_MODEL.md`](./SCOPE_AND_IDENTITY_MODEL.md) §3.2); the orchestrator holds
no credentials and no authorization power (ADR 0004); rights only intersect (`I-07`).
**Residual:** Low. This is the attack the architecture is most specifically shaped against.

### T-07 Scope escalation
**Failure:** An actor obtains rights over a parent or sibling.
**Defense:** No mechanism widens authority (`I-08`); grants flow downward only (`I-04`);
only James grants (`I-10`).
**Residual:** Depends on grant hygiene. An over-broad grant issued by James is not an
escalation — it is authorized breadth, and no mechanism prevents it.

### T-08 Lateral movement
**Failure:** Reaching Client B from a foothold in Client A.
**Defense:** Siblings have no path (`I-03`, `I-04`); one sandbox per client; per-scope
credentials; per-scope caches and indexes.
**Residual:** Via a shared ancestor resource — see T-11.

### T-09 Accidental cross-client write
**Failure:** Client A's content written into Client B's scope or a shared scope.
**Defense:** Writes are scope-checked identically to reads; CLIENT-CONFIDENTIAL cannot be
promoted (`I-29`); derived items inherit the strictest source scope (`I-27`).
**Residual:** A reviewed transformation that strips identifiers incorrectly. Human review is
the control, and humans miss things.

### T-10 Poisoned memory, knowledge, or summaries
**Failure:** False information is planted and later treated as fact.
**Defense:** Provenance and trust are separate and immutable (`I-37`, `I-38`); fact status
requires supporting provenance (`I-39`); contradictions surface rather than resolve (`I-41`);
`james.stated` is never auto-superseded (`I-36`).
**Residual:** **Real.** Slow poisoning within one scope, from a consistently-wrong
integration, remains possible. Detection depends on contradiction surfacing — which fails if
nothing contradicts it.

### T-11 Compromised shared resource
**Failure:** A resource shared across clients is altered maliciously.
**Defense:** Shared resources are versioned with provenance; per-descendant grants are
revocable; they contain no client data (`I-29`); reference-never-copy means one correction
propagates.
**Residual:** **Genuine blast radius.** A poisoned shared template affects every consuming
client at once. This is the price of sharing, and it argues for review on changes to shared
resources — recorded as an open risk.

### T-12 Insecure logs
**Failure:** Logs accumulate client content and become a cross-client corpus.
**Defense:** References and identifiers only (`I-48`); no secrets (`I-21`); audit records
carry metadata, not content.
**Residual:** Debug logging during development is the classic violation. Enforcement is a
review and testing concern.

### T-13 Cache leakage
**Failure:** A cache serves one scope's data to another.
**Defense:** Caches keyed by scope **and** token; never shared across scopes; invalidated on
revocation and deletion.
**Residual:** Cache-key bugs are a well-known source of exactly this. Adversarial testing
required.

### T-14 Backup leakage
**Failure:** Backups flatten scope partitioning; restoring one scope restores another's data.
**Defense:** Backups preserve partitioning; restore is scope-aware.
**Residual:** Depends on the unbuilt backup mechanism (`D-15`). **Currently unmitigated in
practice.**

### T-15 Model-provider leakage
**Failure:** Content sent to a provider is retained, logged, or trained on.
**Defense:** The gateway is the single egress chokepoint with redaction and per-scope data
policy; SECURITY-CRITICAL and credential material are never sent (`I-21`); client data is
never used for training (`I-32`).
**Residual:** **Outside NOVA's control.** Once content leaves, provider behaviour governs.
Mitigation is policy — which scopes may reach which providers — not enforcement.

### T-16 Administrator mistake
**Failure:** James grants too broadly, or approves without reading.
**Defense:** Grants are explicit, expiring where temporary, auditable, revocable; approval
requests state what changes and what it costs; approval fatigue is treated as a design
failure.
**Residual:** **Unmitigable by architecture.** The ultimate authority can authorize anything,
including a mistake. Visibility and revocability are the only defenses.

### T-17 Approval mistake
**Failure:** An approval is granted for something misunderstood.
**Defense:** One approval, one action, one time — never precedent (`I-13`); requests must be
answerable; irreversible actions require James to *initiate*, not merely consent.
**Residual:** Real. Reduced by keeping approvals rare enough to be read.

### T-18 NOVA generates an incorrect Work Order
**Failure:** NOVA specifies the wrong work, and a coding agent executes it faithfully.
**Defense:** Work Orders are risk-classified and approval-gated; underspecified orders fail
closed; output is verified and reviewed before landing; sandbox limits bound the damage
([`EXECUTION_ARCHITECTURE.md`](./EXECUTION_ARCHITECTURE.md) §2.1).
**Residual:** **New risk introduced by the ADR-0005 clarification.** A well-formed but wrong
order is harder to catch than a malformed one, and fails at machine speed. Work Order
generation quality must be evaluated (Section 41).

---

## 2. What the Architecture Genuinely Prevents

Stated narrowly, because over-claiming is itself a risk:

| Genuinely prevented | Why |
| --- | --- |
| Cross-client access via a token | No mechanism issues a token spanning siblings; containment is checked before permissions |
| An agent exfiltrating a credential | Agents never hold credential material |
| Self-escalation | Rights only intersect; only James grants |
| Silent cross-scope persistence | Aggregates are ephemeral; promotion is explicit and audited |
| An agent approving its own work | Only James approves; review agents are permanently read-only |

## 3. What It Does Not Prevent

| Not prevented | Why |
| --- | --- |
| Damage within an authorized scope | Authorization is the boundary, and it was granted |
| Injection causing wrong in-scope work | Only the boundary is guaranteed, not correctness |
| Slow memory poisoning | Detection needs contradiction, which may never arrive |
| Over-broad grants by James | The ultimate authority can authorize anything |
| Provider-side leakage after egress | Outside NOVA's control |
| Shared-resource blast radius | Inherent to sharing |
| Secrets-storage compromise | Single highest-value target; technology undecided |

---

## 4. Priorities for Later Sections

1. **Secrets storage** (`D-10`, Section 04) — the highest-value target.
2. **Physical isolation** (`D-33`, deferred) — the weakest choice makes `I-03` depend on
   query correctness.
3. **Backup partitioning** (`D-15`, Section 36) — currently unmitigated.
4. **Adversarial isolation tests** (Section 31) — every invariant is unverified until then.
5. **Work Order generation evaluation** (Section 41) — T-18.
6. **Shared-resource change review** (Section 22) — T-11.
