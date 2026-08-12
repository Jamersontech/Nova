# Threat Model

**Status:** **Active** — Section 03, approved by James 2026-08-12 (as amended, commit 0917de5).
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
intersection (`I-07`); NOVA issues no credential material to agents (`I-22`), with ingress
stripped and scanned at the capability boundary (`I-51`); repeated boundary attempts are a
failure condition, not a retryable error.
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
never escalate a plan (`I-40`); NOVA issues no credential to the model path (`I-22`);
untrusted provenance is preserved into Work Orders (`I-58`).
**Residual:** **Significant and unavoidable.** Injection can still cause wrong *in-scope*
work and wasted effort. It cannot cross a client boundary through a token, and NOVA will not
hand it a credential — that is the claim, and it is narrower than "injection is solved."
A sandboxed coding agent **does** hold narrow expiring secrets by design (ADR 0005), so
injection inside a sandbox can reach those specific credentials for their lifetime.

### T-04 Compromised integration
**Failure:** An external system returns manipulated data or is taken over.
**Defense:** All external data is untrusted with recorded provenance and low trust; contract
changes fail closed rather than adapting (`RELIABILITY_ARCHITECTURE.md`); the credential is
scoped to one service in one scope (`I-23`).
**Residual:** Poisoned data enters memory at low trust and can influence inference. Mitigated
by provenance labelling and the `PREPARE` ceiling on untrusted-influenced plans.

### T-05 Credential theft
**Failure:** An attacker obtains a credential.
**Defense:** NOVA issues no secret to an agent; secrets exist only in secrets storage and at
the outbound boundary (`I-21`, `I-22`); scoped to one node (`I-23`); expiring; individually
revocable (`I-25`); tool responses declare and strip credential-shaped fields, with boundary
scanning (`I-51`).
**Residual:** **Ingress is real and not prevented.** A credential can still arrive via an
integration response, an error payload echoing headers, a sandbox environment variable, a
subprocess listing, a generated file, a screenshot, or text James pastes. Detection is
best-effort; scanning cannot recognise every secret format. External coding agents hold real
narrow secrets by design (ADR 0005). Compromise of secrets storage itself is catastrophic and
its technology is undecided (`D-10`).

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
nothing contradicts it. Injected content also *persists* in memory and keeps influencing
retrieval; quarantine and revalidation ([`MEMORY_MODEL.md`](./MEMORY_MODEL.md) §4.1) contain
this but do not remove it.

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
**Defense:** Backups preserve partitioning; restore is scope-aware; restoration consults
tombstones and re-applies deletion before restored data becomes available (`I-55`).
**Residual:** Depends on the unbuilt backup mechanism (`D-15`). **Currently unmitigated in
practice**, and `I-55` is marked `[PHYS]` — it is a requirement on a mechanism that does not
yet exist.

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

### T-19 Compromised Policy Decision Point
*Added 2026-08-12 following adversarial review.*

**Failure:** The PDP itself is compromised and returns malicious `ALLOW` decisions. Every
enforcement point obeys, because obeying the PDP is what they are for. Scope containment,
default deny, risk ceilings, and credential scoping all pass — the checks are performed by
the compromised component.

**Defense:** **None that is sufficient.** Fail-closed behaviour (`I-17`) protects against a
PDP that is *unavailable, unresponsive, or erroring* — it says nothing about one that is
*lying*. A compromised PDP is authoritative by construction.

Partial mitigations that exist: PDP compromise is visible in the audit trail *if* the audit
path is independent of the PDP (`I-18`, `I-47`); the Credential Broker performs its own scope
check, so a malicious allow must also defeat the broker to reach a secret; and the PDP is
deliberately simple, narrowing the attack surface (ADR 0014).

**Residual risk: systemic and unmitigated.** Compromise of the PDP is a **total** authorization
failure. **Independent verification of authorization decisions is not designed** — there is no
second opinion, no quorum, no out-of-band attestation, and no anomaly detection over decision
patterns. Adding any of these is a Section 04/38 decision that has not been made.

This is stated plainly rather than mitigated on paper: the architecture concentrates
authorization in one trusted component, and that concentration is the cost of having one place
where isolation is decided ([ADR 0001](../decisions/0001-layered-architecture-with-policy-spine.md),
[ADR 0014](../decisions/0014-authorization-decision-model.md)).

---

## 2. What the Architecture Genuinely Prevents

Stated narrowly, because over-claiming is itself a risk:

| Genuinely prevented | Why |
| --- | --- |
| Cross-client access via a token | No mechanism issues a token spanning siblings; containment is checked before permissions |
| An agent exfiltrating a credential **obtained through NOVA's issuance path** | NOVA issues no credential material to agents. Credentials arriving by *ingress* are a detected-and-contained incident, not a prevented event ([ADR 0009](../decisions/0009-credentials-are-references.md)) |
| Self-escalation | Rights only intersect; only James grants |
| Silent cross-scope persistence | Aggregates are ephemeral; promotion is explicit and audited |
| An agent approving its own work | Only James approves; review agents are permanently read-only |

## 3. What It Does Not Prevent

| Not prevented | Why |
| --- | --- |
| Damage within an authorized scope | Authorization is the boundary, and it was granted |
| Injection causing wrong in-scope work | Only the boundary is claimed, not correctness |
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
