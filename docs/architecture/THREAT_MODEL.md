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

**Audit evidence from a compromised PDP is not trustworthy.** *(Corrected 2026-08-12, M-6.)*
`I-18` requires every decision to produce an audit record — **emitted by the PDP itself**. A
compromised PDP can therefore emit false records, omit records, or record denials for accesses
it in fact allowed. **NOVA has no independent audit path for authorization decisions: none is
required by the architecture and none is designed.** The earlier claim that compromise "is
visible in the audit trail *if* the audit path is independent of the PDP" was conditional on an
independence that does not exist, and is **withdrawn** (`I-85`).

Partial mitigations that do exist: the Credential Broker performs its own binding-state and
operation checks, so a malicious allow must also defeat those to reach a secret; storage
enforcement does not consult the PDP (ADR 0017); and the PDP is deliberately simple, narrowing
the attack surface (ADR 0014).

**Practically:** PDP compromise may be detectable from *effects* — unexpected external calls,
unexplained state changes, storage-layer denials that should never have been attempted — but
**not from the authorization audit trail itself.** Independent verification and independent
audit are both undesigned; adding either is a Section 38 decision that has not been made.

**Partial mitigation added in Section 04.** [ADR 0017](../decisions/0017-isolation-independent-of-pdp.md)
requires the storage enforcement layer to derive scope restriction from the execution's bound
scope identity **without consulting the PDP** (`I-62`). A compromised PDP granting `ALLOW` for
another client's resource therefore still yields no data: the connection is bound elsewhere.
**Cross-client access is no longer available from PDP compromise alone.**

**But the independence is bounded (H-2).** Both the PDP and the scope binding derive from the
**Context Token**. They are independent *of each other*; they are not independent of the Context
service. Compromising it defeats both together — see `T-23a`. **General two-of-two independence
is not claimed.**

**Residual risk after mitigation: still systemic.** `T-19` is **reduced in blast radius, not
resolved.** A compromised PDP can still authorize destructive, irreversible and unapproved
actions *within* an execution's own scope, deny legitimate work, and lie in every other
respect. The mitigation assumes the attacker cannot subvert the scope binding — an attacker
controlling the Context service or channel establishment defeats it (`T-23a`). **Independent
verification of authorization
decisions remains undesigned**: no second opinion, no quorum, no attestation, no anomaly
detection over decision patterns. Section 04 considered and explicitly declined it as
disproportionate at NOVA's current scale (ADR 0017, option 3).

This is stated plainly rather than mitigated on paper: the architecture concentrates
authorization in one trusted component, and that concentration is the cost of having one place
where isolation is decided ([ADR 0001](../decisions/0001-layered-architecture-with-policy-spine.md),
[ADR 0014](../decisions/0014-authorization-decision-model.md)).

### T-23 Attacks on the Context Token as a root of trust
*Added 2026-08-12 following adversarial review (H-2). Split into three distinct variants
2026-08-12 following final review (F-3), because they have different defenses and are routinely
confused with each other.*

The Context Token is the single upstream input to **both** the PDP's evaluation and the storage
scope binding. Three different things can go wrong with it. Only one of them is addressed by
`I-87`.

#### T-23a — Compromise of the Context service

**Failure:** The Context service itself — the authoritative source of execution scope identity —
is compromised, or its issuance logic is subverted. It issues a **genuine** token naming Client B
for work that should be Client A. The PDP then correctly authorizes what the token says, and the
storage enforcement layer binds to Client B because that is what the token said.

**Defense:** **None sufficient.** Both the PDP and the scope binding derive from the token, so
this single compromise defeats both. The independence established by ADR 0017 is independence
*from the PDP*, not from the Context service. **`I-87` does not help here at all** — the token is
authentic; integrity detection has nothing to detect.

**Residual:** **Systemic and unmitigated.** The Context service is a critical trusted component of
the same standing as the PDP. Section 04 does not address its compromise, and no independent
verification of token issuance is designed. This is the precise limit of the ADR 0017 mitigation
and is stated so it cannot be mistaken for general two-of-two independence.

#### T-23b — Unauthorized fabrication or modification of a Context Token

**Failure:** Something that is *not* the Context service produces a token, or alters one in
flight or at rest — a compromised orchestrator widening its own scope path, an agent minting a
token for a sibling scope, a tampered token replayed at a later enforcement point.

**Defense:** **`I-87` — required, unimplemented.** A consuming component must be able to detect
modification after issuance or fabrication by a non-issuer, and must refuse the token if that
cannot be established; the refusal is recorded, no binding is opened, and access is denied
(`I-78`, `I-79`). This is a **detection** requirement. **Forgery is not claimed to be
impossible**, and no mechanism is selected
([`AUTHENTICATION_MODEL.md`](./AUTHENTICATION_MODEL.md) §6).

**Residual:** **Real until the mechanism exists.** `I-87` is `[PHYS]` — a requirement on a future
component, not a property NOVA has. Until it is implemented and verified (Section 31), this
variant is undefended in practice. Detection also says nothing about a token that is genuine but
was obtained by other means; scope narrowing (`I-07`, `I-12`) and expiry bound that, imperfectly.

#### T-23c — Compromise of the token-integrity mechanism itself

**Failure:** Whatever eventually provides the `I-87` property is compromised — its verification
path, its trust anchors, or the component performing the check. Fabricated tokens then pass
inspection and are accepted as genuine, which collapses T-23b into T-23a.

**Defense:** **None designed.** `I-87` introduces a new trusted component, and Section 04 selects
no mechanism and therefore specifies no protection for it. Stated explicitly so that adding token
integrity is not mistaken for a net reduction in trusted surface: it moves trust, it does not
remove it.

**Residual:** **Accepted and unaddressed in Section 04.** The mechanism, its custody, and its own
threat model are deferred with `D-09` / `D-33`.

### T-20 Stolen or compromised human session
*Added 2026-08-12 — Section 04.*

**Failure:** An attacker obtains a valid session on one of James's devices and acts as him.
**Defense:** Multi-factor with a phishing-resistant primary factor (`I-64`); sessions are
per-surface, absolutely expiring, enumerable and individually revocable (`I-65`); step-up
requires **fresh** authentication for irreversible actions and for changes to grants, policy or
credentials (`I-67`); emergency stop ends all sessions.
**Residual:** A session stolen on a device James is actively using can perform anything below
the step-up line without further challenge. Step-up narrows the window; it does not close it.
Voice is the weakest surface and is capped at `PREPARE`.

#### T-20a — Compromise of James's audit-reading session
*Added 2026-08-13 (`H-2`). **This is where the "compromised audit reader" case lives.** Under
`S4-P2` Option D there is no audit-reader component — the reader is James — so his session is the
audit corpus's exposure surface, and it belongs here rather than in a separate entry.*

**Failure:** An attacker holding a valid session on one of James's devices reads audit records.

**Defense:** **Two boundaries, deliberately unequal.**

| Attempted | Outcome |
| --- | --- |
| **Read audit for a scope the session can reach** | **Succeeds.** Single-scope audit reading is at normal session strength (`H-1` Option 3, `A-3a`) |
| **Review audit across more than one scope** | **Requires step-up** — fresh authentication, not merely a valid session (`I-67`, `A-3a`). The cross-client audit corpus sits behind that boundary |
| **Reach audit through a component** | **Fails.** No component holds audit-read capability (`I-89`, `E-13`); there is nothing to compromise instead of the session |
| **Alter or delete audit to cover tracks** | **Fails.** Append-only, including by James (`I-47`) |
| **Read client content from audit** | **Fails.** Audit carries references and identifiers, never content (`I-48`) |

**Residual:** **A compromised session exposes the audit of the scope or scopes that session can
reach without step-up** — in practice, single-scope reads. The **cross-client audit corpus is
additionally protected by the step-up boundary**, so an attacker who cannot step up cannot
aggregate across scopes. That boundary is the whole of the additional protection: an attacker who
*can* step up — because James is actively authenticating on a compromised device — reaches
everything he reaches. `H-1` Option 3 was chosen knowing this; it narrows the corpus exposure
without making routine oversight require a challenge every time.

### T-21 Authentication recovery abuse
*Added 2026-08-12 — Section 04.*

**Failure:** An attacker takes the account through the recovery path rather than the front door
— historically the most-attacked route in any authentication system.
**Defense:** Recovery must be at least as strong as primary authentication, rate-limited,
notified, and audited (`I-67`, `A-4`).
**Residual:** **Real and structural.** Recovery exists because James can lose his device, and
any usable recovery path is by definition an alternative way in. Strength parity bounds it; it
does not eliminate it. The provider choice (`D-09`) will materially affect this.

### T-22 Break-glass abuse
*Added 2026-08-12 — Section 04.*

**Failure:** The recovery path intended for availability failure is used — by an attacker or
under pressure — as an authorization bypass.
**Defense:** Human-only, time-boxed, loudly recorded, scoped to service recovery, on a separate
credential path rotated after every use, and explicitly **never** a bypass of authorization or
client isolation (`I-75`).
**Residual:** **Accepted deliberate weakness.** An attacker obtaining break-glass credentials
obtains recovery-level access. `B-3` loudness depends on a notification path that may itself be
degraded during exactly the incident break-glass exists for.

### T-24 Compromised Policy Enforcement Point
*Added 2026-08-13 following the final pre-approval review (R-5). `T-19` covers a lying PDP and
`T-23` covers the token root; nothing covered a compromised **enforcer**.*

**Failure:** One of the five enforcement points
([`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md) §2) is compromised and stops doing
its job — it does not ask the PDP, ignores a `DENY`, skips the token-integrity check (`I-87`), or
forwards a call it should have refused. Unlike `T-19`, the PDP may be perfectly healthy; its
answer is simply not consulted or not obeyed.

**Defense:** **Partial, and it differs sharply by which point is compromised.**

| Compromised point | What is lost | What still holds |
| --- | --- | --- |
| **Data access PEP** | Grants, risk ceiling, classification, conditions on the read/write path | **Cross-client isolation holds — but only once `D-33` is implemented and verified.** Structural storage isolation sits beneath the PEP, never consults it, and restricts to the bound scope (`I-77`, `R-9`, ADR 0016). **`I-60`–`I-63` are `[PHYS]` and unbuilt**, so **today a compromised Data access PEP does yield cross-client data**; the confinement is a property of the future implemented system, not the present one |
| **Tool call PEP** | Risk-class and scope checks on tool invocation | The Credential Broker performs its **own** scope check (`S-3`, broker step 2) rather than trusting the caller |
| **Credential PEP** | The scope check at credential request | Binding state, expiry, revocation and permitted-operation checks are the broker's own (steps 3–4), and are not the PEP's to skip |
| **Orchestration / Agent Runtime PEP** | Narrowing on dispatch; an agent could receive a token it should not have | Rights remain an intersection (`I-07`); no mechanism widens authority (`I-08`); the downstream points still run |

**Residual:** **Real and only partly bounded.** A compromised PEP is an authorization failure
*within* the scope it is bound to, and nothing detects it from the authorization trail — the same
limit `I-85` records for the PDP. What Section 04 provides is that **no single compromised
enforcement point yields cross-client data — once `D-33` is implemented and the Section 31
isolation tests have run.** *(Qualified 2026-08-13, `M-A`. The earlier text asserted this in the
present tense; `I-60`–`I-63` are `[PHYS]` and unbuilt, so **until then this containment does not
exist** and a compromised Data access PEP is a cross-client exposure.)* Independent verification of
enforcement-point behaviour is **undesigned**, exactly as it is for the PDP. Detection would be
from effects, not from records.

### T-25 Compromised Data-Access Boundary
*Added 2026-08-13 following the final pre-approval review (R-5). Section 04 registers this as a
new TRUSTED-zone responsibility ([ADR 0017](../decisions/0017-isolation-independent-of-pdp.md),
**Proposed**); registering a trusted component without a threat entry is the gap this closes.*

**Failure:** The component holding the storage scope binding is compromised. It binds a channel
to Client B for work whose Context Token says Client A, opens an unbound channel, widens a
binding mid-execution, or opens one channel spanning several scopes — each prohibited by `I-61`,
`I-78`, `I-79` and `I-86`, and each available to a component that no longer honours them.

**Defense:** **None sufficient, and this must be stated plainly.** The Data-Access Boundary *is*
the mechanism that makes `R-1`/`R-2` real. There is no second component checking its work: the
Data Access PEP above it asks the PDP about the *requested* scope, not about which partition the
channel actually reaches, and the storage layer applies whatever binding it is given. `I-78`
requires the binding to be verified against the presented token at establishment — but that check
is performed **by the boundary itself**, so a compromised boundary is checking its own work.

**Residual:** **Systemic and unmitigated, and of the same standing as `T-19` and `T-23a`.**
Compromise yields cross-client access directly. This is the cost of concentrating the binding in
one trusted place — the same trade ADR 0001 makes for the PDP — and Section 04 designs no
independent verification of it. It is recorded so that the Data-Access Boundary is understood as
a **third** critical trusted component alongside the PDP and the Context service, not as
infrastructure.

### T-26 Compromised Observability component
*Added 2026-08-13, after James decided `S4-P1` (Option A) and `S4-P2` (Option D). Written against
the architecture as decided — **not** against a cross-scope audit writer, which the decision
prohibits.*

**Failure:** The Observability responsibility — which collects and routes audit events — is
compromised. The attacker seeks to read other clients' audit records, forge records to conceal
activity, or destroy evidence of an incident.

**Defense:** **Bounded by construction, in three separate ways.**

| Attempted | Outcome | Why |
| --- | --- | --- |
| **Read another client's audit** | **Fails** | Observability holds **no** audit-read capability at all. There is no centralized audit reader and no component with universal or cross-scope audit-read capability (`I-89`, `E-13`). It is not a reader of the corpus it routes |
| **Read the audit it just wrote** | **Fails** | Write confers no read over that partition or any other (`E-12c`, `I-88`) |
| **Forge records across every scope** | **Fails** | There is no blanket cross-scope audit-write capability under any of the three authorities: `W-1` is bound to the execution's single scope (`I-88`), `W-2` to the scope one decision concerned (`I-91`), `W-3` to the control-plane partition, which holds no client records (`I-92`). Control-plane writer compromise is `T-27` |
| **Forge records in a scope it currently serves** | **Succeeds, bounded** | Within a scope whose execution-scoped capability it currently holds, a compromised writer can append false records. This is the residual below |
| **Read the audit it routes** | **Fails** | No component holds audit-read capability; the reader is James (`I-89`, `E-13`). **The compromised-audit-reader case is `T-20a`**, not this entry |
| **Amend or delete records to hide an incident** | **Fails** | Audit is append-only (`I-47`). There is no amendment and no deletion operation to compromise |
| **Retain capability for later use beyond the execution** | **Fails** | Capability lifetime is the execution's lifetime; it does not stand beyond it (`E-12b`) |
| **Read client data via the audit path** | **Fails** | Audit records carry references and identifiers, never client content (`I-48`), and a record in one scope's partition may not disclose a sibling's identifiers (`E-11`) |

**Residual: real, and narrower than it would otherwise be.**

1. **Forgery within currently held scopes.** A compromised Observability component can append
   false records to the scopes whose **execution-scoped** capabilities it holds at the time of
   compromise (`E-12b`, `I-88`). Under `I-47` those records are **permanent** — they cannot be
   removed, only contradicted by a later record. The blast radius is the union of the scopes it is
   currently serving, **not the tree** — and it cannot acquire capability for a scope it is not
   serving. Capability lifetime is the execution's lifetime, so the window closes as those
   executions end.
1a. **The bootstrap window is retired.** `S4-P6` (Option A) removed the capability-release
   decision entirely, so there is no release that can succeed while its record fails. The window
   that `E-12d` described no longer exists — not mitigated, but absent.
2. **Suppression by omission.** Routing is where events pass; a compromised router can **drop**
   events so that a real action produces no record. `I-18` requires a record to be produced, but
   nothing independently verifies that every produced record arrives. **This is not addressed**,
   and it parallels the `I-85` limit for the PDP: the audit trail cannot prove its own
   completeness.
3. **Detection is from effects, not from the trail.** As with `T-19` and `T-24`, a compromised
   audit path cannot be detected by reading the audit path.

**What `S4-P1`/`S4-P2` actually bought:** had the permissive option been taken, this entry would
read *"permanent forged-audit injection across every scope, undetectable and irreversible."*
Instead the same compromise is confined to the scopes the component currently serves, and yields
**no read access whatever**. Suppression by omission remains, and is the honest gap.

### T-27 Compromised control-plane audit writer
*Added 2026-08-13 (`S4-P9`). [ADR 0023](../decisions/0023-audit-record-writer-authority.md) creates a
control-plane audit partition; registering a new concentration without a threat entry is the defect
these reviews keep finding.*

**Failure:** A component authorized to write control-plane audit records is compromised. It seeks to
forge provisioning, grant, revocation, incident or break-glass records, to suppress them, or to reach
client audit through the control plane.

**Defense:**

| Attempted | Outcome | Why |
| --- | --- | --- |
| **Reach any client audit partition** | **Fails** | The control-plane partition is not a node in the client scope tree and holds no client-scope records (`I-92`). Writing there confers nothing over any client partition — this is what makes `S4-P1` hold by construction |
| **Read the control-plane partition** | **Fails** | Write is not read (`E-12c`); reading any partition is James only (`I-89`) |
| **Forge control-plane records** | **Succeeds, bounded** | Within the control-plane partition. The residual below |
| **Amend or delete** | **Fails** | Append-only (`I-47`) |
| **Read client content** | **Fails** | Control-plane records carry no client-scope content, identifiers or resource references (`I-48`, `E-11`, `I-92`) |
| **Suppress a record to avoid failing closed** | **Fails to help the attacker** | A missing mandatory record makes the operation fail closed (`I-93`) — suppression denies, it does not permit |

**Residual: real and bounded to the control plane.** A compromised control-plane writer can append
false provisioning, grant, revocation or incident records, permanently under `I-47`. That is a
genuine concentration — these are the records that establish whether a client scope was correctly
isolated before activation (`I-80`) and who holds what authority. **It yields no client partition and
no client data.**

**Suppression by omission remains unaddressed here as everywhere** (`T-26`): nothing independently
verifies that a produced control-plane record arrived. `I-93` ensures a *known* write failure fails
the operation closed; it does not detect a writer that silently drops records while reporting
success.

### T-28 Injected tool arguments
*Added 2026-08-14 — **PROPOSED**, Section 05. Authority
[ADR 0025](../decisions/0025-model-output-is-an-untrusted-derivation.md) and
[ADR 0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md).*

**Failure:** Untrusted content reaches a model; the model's output fills a tool argument; the
action executes with a target, recipient, magnitude or destination the attacker chose. **The
authorization that permitted the action had already been granted** — the request pipeline
authorizes the plan before Tool Selection and Execution, so argument *values* are fixed after it.
Schema validation passes: `recipient: "attacker@example.com"` is a valid string.

**Defense:** Consequence-determining arguments are checked against the authorization's envelope at
the tool enforcement point (`I-100`); an out-of-envelope value is a denial and a security event
(`SECURITY_BOUNDARIES.md` §6); an in-envelope value derived from untrusted content is ceilinged at
`PREPARE` and requires approval naming the source (`I-40`, `I-58`). Detection of "derived from
untrusted content" rests on taint propagation through model output (`I-99`).

**Residual:** **Significant.** `T-03`'s residual is unchanged and this narrows only *reach*, never
*influence*: injection can still cause wrong in-scope work with in-envelope arguments. Two further
gaps are real — **an over-wide envelope silently restores the whole attack**, and **a taint-labelling
bug is an authorization bug** while looking like nothing at all. Both are unverified until
Section 31. This threat existed before Section 05 and was **unnamed**, which is the more honest
statement than calling it new.

### T-29 Compromised Model Gateway
*Added 2026-08-14 — **PROPOSED**, Section 05.*

**Failure:** The gateway is compromised. It is the single egress chokepoint for every model call,
it performs redaction, it holds provider credentials, and after Section 05 it is an enforcement
point. A compromised gateway can disclose the content of every model call it handles, skip
redaction while reporting it applied, and use the provider credentials it holds.

**Defense:** It **decides nothing** — it is an enforcement point and enforcement can only deny
(`I-77`), so it cannot widen the permitted provider set or authorize a call the PDP denied. Its
provider credentials authorize **no client scope** (`I-103`), so holding them yields nothing about
any scope. It holds no client-scope credential, no data-key material, and no audit-read capability
(`I-89`). It sees only what is sent through it.

**Residual:** **Real and concentrated.** "Only what is sent through it" is every model call NOVA
makes — a substantial disclosure surface, and one that spans scopes over time even though no single
request does (`I-95`). **`I-96` is exactly as strong as the component enforcing it**, and a
compromised gateway reporting successful redaction is indistinguishable from a working one. This is
the same class of exposure `I-85` records for the PDP: a component's own report is not evidence of
its integrity. Making the gateway an enforcement point **created no new capability** — it already
held the content and the credentials — but it does make the concentration explicit.

### T-30 Provider-side correlation across scopes
*Added 2026-08-14 — **PROPOSED**, Section 05.*

**Failure:** One provider credential serves every scope permitted to use that provider, so the
provider sees every scope's traffic as one customer and can correlate across clients — the
boundary NOVA works hardest to hold, observed from outside it.

**Defense:** None that NOVA can enforce. Content is redacted and classification-filtered before
egress (`I-96`), one request never mixes scopes (`I-95`), and `PR-2` requires a contractual
no-training commitment.

**Residual:** **Accepted, not mitigated** ([ADR 0027](../decisions/0027-provider-credentials-are-control-plane-credentials.md)).
Per-scope provider accounts would not remove it — network origin, billing relationship and timing
correlate anyway — and would add operational surface for no isolation gain inside NOVA. This
extends `T-15`: once content leaves, provider behaviour governs. Whether attestation, contract, or
self-hosting closes any of it is `D-39`.

### T-31 Routing and fallback coercion
*Added 2026-08-14 — **PROPOSED**, Section 05.*

**Failure:** A request reaches a provider the scope's data policy does not permit. Two routes:
injected content persuades the model to request a different profile or provider; or the primary
provider is unavailable and failover reaches for whatever is up — the moment a degraded system is
most likely to make exactly this mistake.

**Defense:** Profile, provider and model are **declared, never generated** (`I-98`), so model
output is not a routing input. Data policy **filters the candidate set** rather than being weighed
against cost and latency, and the filter applies identically to failover, reroute and retry; an
empty permitted set fails closed (`I-97`). Each attempt is separately authorized, so failover
inherits no prior allow (`I-104`).

**Residual:** Availability is genuinely reduced — a scope whose only permitted provider is down
cannot proceed, and Section 05 accepts that rather than degrading. Correctness of the permitted set
depends on `PR-3` and `PR-4`, which are provider assurances NOVA cannot verify (`D-39`).

### T-32 Verifier capture
*Added 2026-08-14 — **PROPOSED**, Section 05.*

**Failure:** A model check reports success on a result that is wrong — because the checker is the
same model reading the same injected content, or because the check was treated as evidence and used
to discharge an approval or lower a risk class.

**Defense:** A model check **never** promotes epistemic status, satisfies an approval, or lowers a
class (`I-102`, `I-09`, `I-101`). Above `PREPARE` the checker is a different call and a different
instance and does not receive the producing call's untrusted inputs unlabelled. Structurally,
review agents are permanently read-only (`AGENT_ARCHITECTURE.md` §1) and Verification is a distinct
stage against declared success criteria.

**Residual:** **Correlated failure is not solved.** A different provider is *preferred and not
required*, because requiring it would make verification unavailable wherever one permitted provider
exists (`I-97`) — and a silently skipped check is worse than a same-provider one. So the same
provider may serve both calls and may fail the same way. NOVA's verification above `PREPARE` rests
on declared success criteria, structural read-only review, and James — **not** on a model checking
a model.

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
| Cross-client access via a compromised PDP **alone** | Storage enforcement is independent of the PDP ([ADR 0017](../decisions/0017-isolation-independent-of-pdp.md)) — **once `D-33` is implemented**; unverified until then |

## 3. What It Does Not Prevent

| Not prevented | Why |
| --- | --- |
| Damage within an authorized scope | Authorization is the boundary, and it was granted |
| Injection causing wrong in-scope work | Only the boundary is claimed, not correctness |
| Slow memory poisoning | Detection needs contradiction, which may never arrive |
| Over-broad grants by James | The ultimate authority can authorize anything |
| Provider-side leakage after egress | Outside NOVA's control |
| Provider-side correlation of one scope's traffic with another's ¹ | One provider credential serves many scopes; per-scope accounts would not remove it (`T-30`) |
| Injection choosing an *in-envelope* argument value ¹ | `I-100` bounds reach, never influence (`T-28`) |
| A model check that is wrong in the same way as the call it checks ¹ | A different provider is preferred, not required (`T-32`) |
| Shared-resource blast radius | Inherent to sharing |
| Secrets-storage compromise | Single highest-value target; technology undecided |

> ¹ ***PROPOSED — added by Section 05, not yet accepted*** *(2026-08-14; authority ADRs
> [0025](../decisions/0025-model-output-is-an-untrusted-derivation.md),
> [0026](../decisions/0026-model-verification-is-corroboration.md),
> [0027](../decisions/0027-provider-credentials-are-control-plane-credentials.md) and
> [0028](../decisions/0028-section-05-amendments-to-accepted-architecture.md)).* **No row in §2 is
> added by Section 05.** Section 05 prevents nothing new; it names an unenforced boundary, bounds
> what an injected argument can reach, and states three residuals that were previously unstated.

---

## 4. Priorities for Later Sections

1. **Secrets storage** (`D-10`, Section 04) — the highest-value target.
2. **Physical isolation** (`D-33`, deferred) — the weakest choice makes `I-03` depend on
   query correctness.
3. **Backup partitioning** (`D-15`, Section 36) — currently unmitigated.
4. **Adversarial isolation tests** (Section 31) — every invariant is unverified until then.
5. **Work Order generation evaluation** (Section 41) — T-18.
6. **Shared-resource change review** (Section 22) — T-11.
