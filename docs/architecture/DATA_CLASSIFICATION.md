# Data Classification

**Status:** Proposed — Section 03, pending James's approval.
**Purpose:** A flexible classification model that determines how information may be stored,
accessed, remembered, logged, exposed to models, transmitted, retained, and deleted.

**No legal or regulatory requirements are invented here.** The model is built so that such
requirements can be attached later as constraints on existing levels
([ADR 0012](../decisions/0012-data-classification-model.md)).

---

## 1. Levels

| Level | Contains | Default scope reach |
| --- | --- | --- |
| **PUBLIC** | Information already public | Any scope |
| **INTERNAL** | NOVA's own operational data, non-sensitive preferences | Owning scope and below |
| **CONFIDENTIAL** | James's business information not belonging to a client | Owning scope and below |
| **CLIENT-CONFIDENTIAL** | Anything belonging to or identifying a client | Owning client scope only — **never upward** |
| **SENSITIVE-PERSONAL** | Health, relationships, and marked LIFE Areas | Owning area only — never aggregated, never summarized upward |
| **SECURITY-CRITICAL** | Audit records, policy, grants, provenance | Owning scope; append-only; never model-exposed |
| **CREDENTIAL** | Secret material | **Not stored in NOVA at all** — see §4 |

**Levels are not ordered by "how secret."** They are ordered by *what may be done with
them*, which is why CLIENT-CONFIDENTIAL and SENSITIVE-PERSONAL are separate levels rather
than degrees of one — their restrictions differ in kind, not in strength.

---

## 2. What Classification Controls

| Concern | PUBLIC | INTERNAL | CONFIDENTIAL | CLIENT-CONF. | SENSITIVE-PERS. | SECURITY-CRIT. |
| --- | --- | --- | --- | --- | --- | --- |
| Stored in owning scope | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Readable below owning scope | ✅ | ✅ | ✅ | ✅ | ✅ | grant only |
| **Promotable upward** | ✅ | grant | grant | **❌ never** | **❌ never** | ❌ |
| Included in aggregation | ✅ | ✅ | grant | **identifying parts ❌** | **❌ never** | ❌ |
| Summarizable | ✅ | ✅ | ✅ | within scope only | **❌ never** | ❌ |
| Written to memory | ✅ | ✅ | ✅ | owning scope only | owning area only | ❌ |
| Sent to a model | ✅ | ✅ | ✅ | scoped call only | explicit approval | **❌ never** |
| Transmitted externally | ✅ | grant | grant | to that client only | **❌ never** | ❌ |
| Appears in logs | ✅ | ✅ | redacted | **references only** | **references only** | metadata only |
| Included in exports | ✅ | ✅ | ✅ | per-client export only | explicit | separate export |

**Two columns to read carefully.** CLIENT-CONFIDENTIAL cannot be promoted upward — this is
what makes a KAIRO-level summary of Client A's work an explicit, audited elevation rather
than a side effect. SENSITIVE-PERSONAL cannot be summarized at all, which is what prevents
health information from surfacing anywhere it was not deliberately sought.

---

## 3. Assigning Classification

- **Every stored item carries a classification.** Unclassified is not a state; the default
  for anything created inside a client scope is CLIENT-CONFIDENTIAL.
- **Classification is assigned at creation**, from the creating scope and the source's own
  classification.
- **Derived items inherit the strictest classification among their sources**
  ([ADR 0010](../decisions/0010-derived-data-inheritance.md)). Combining PUBLIC and
  CLIENT-CONFIDENTIAL yields CLIENT-CONFIDENTIAL.
- **Reclassification downward is a reviewed operation** — never automatic, never performed
  by an agent, always audited. Downward reclassification is declassification, and it is the
  single most dangerous routine operation in the model.
- Reclassification upward (more restrictive) is always permitted.

---

## 4. Credential Material Is Not a Classification Level

CREDENTIAL appears in the table for completeness, but it is **not data NOVA stores**. Secret
material lives only in secrets storage, reachable only by the Credential Broker
([ADR 0009](../decisions/0009-credentials-are-references.md)).

Treating credentials as "very confidential data" would imply they could be stored, logged,
or remembered with sufficient protection. They cannot be stored anywhere in the data
model at all. What NOVA holds is a **binding** — a reference — classified SECURITY-CRITICAL.

---

## 5. Sensitivity Marking

LIFE Areas may carry a sensitivity marking that raises every item within them to
SENSITIVE-PERSONAL ([`DOMAIN_ARCHITECTURE.md`](./DOMAIN_ARCHITECTURE.md) §2.3).

**The residual risk is honest:** protection depends on the Area being marked. An unmarked
health Area is only CONFIDENTIAL. Mitigations — defaults for recognised categories, and
prompting James when unmarked content looks sensitive — are deferred to Section 37, and the
gap is recorded in [`KNOWN_RISKS.md`](./KNOWN_RISKS.md).
