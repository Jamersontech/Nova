# NOVA Domain Model

**Status:** Active — established in Section 01.
**Purpose:** Define the permanent domain concepts NOVA organizes work around, and the
boundaries between them. Detailed data modelling belongs to Section 03; permission
enforcement belongs to Section 04.

---

## 1. Conceptual Hierarchy

```text
BUSINESS
    ↓
CLIENT
    ↓
PROJECT
    ↓
ENVIRONMENT
```

These concepts are distinct and must remain distinct.

- A business is **not** a client.
- A client is **not** a project.
- A project is **not** an environment.
- An environment is **not** a credential.

They must not be collapsed into one another because doing so initially appears easier.

---

## 2. Businesses

NOVA must support multiple independent businesses. There must never be an assumption
that James has only one business.

```text
BUSINESS
│
├── KAIRO
├── BUSINESS B
├── BUSINESS C
└── FUTURE BUSINESS
```

Each business must eventually be capable of having its own clients, projects, finances,
operations, documents, communications, systems, integrations, workflows, agents, and
environments. Detailed implementation belongs to Section 20.

---

## 3. KAIRO

One of James's businesses is **KAIRO**.

The spelling is always **KAIRO** — K-A-I-R-O. Never *CAIRO*, *Cairo*, *Kairo*, or
*Kairos*, unless referring to something entirely unrelated to this business.

KAIRO's work currently includes website development, business systems, Google review
systems, email automation, SMS campaigns, business automation, and digital services.
These examples are not necessarily exhaustive.

KAIRO must remain a distinct business context inside NOVA. It is one business among
several, not a synonym for "business" and not the default context for unrelated work.
KAIRO's own architecture is Section 21.

---

## 4. Clients

A client is an external party a business does work for.

```text
KAIRO
│
├── Client A
│   ├── Website Project
│   ├── Google Review Project
│   └── Automation Project
│
├── Client B
│   ├── Website Project
│   └── SMS Project
│
└── Client C
```

A client belongs to exactly one business context. Two clients of the same business are
peers, not neighbours with shared access.

---

## 5. Client Isolation

Client isolation is a foundational security requirement, not a UI convention.

Client A must never accidentally access Client B's credentials, files, databases, source
code, websites, communications, contacts, analytics, documents, API connections,
configuration, private information, or project information.

Isolation must eventually be enforced through:

- data boundaries
- authorization
- credential boundaries
- environment boundaries
- permission systems

It must **not** depend merely on hiding information in the interface. An interface that
omits data while the underlying query could return it is not isolation.

Enforcement mechanisms are designed in Sections 03, 04, and 22.

---

## 6. Projects

A project represents a defined body of work for a client.

```text
Client A  →  Website Project
Client A  →  SMS Automation Project
Client B  →  Google Review Project
```

A project may eventually contain tasks, deadlines, deliverables, files, conversations,
code, workflows, integrations, environments, and documentation. None of these systems are
implemented in Section 01; project and task management is Section 24.

---

## 7. Environments

An environment is the technical context in which a project operates.

```text
KAIRO
 ↓
Client A
 ↓
Website Project
 ↓
Client A Website Environment
```

An environment may eventually contain source code, deployment configuration, databases,
hosting, domains, analytics, email, SMS, automation, API connections, credentials, and
infrastructure.

Two clients using the same technology do **not** thereby share an environment. Shared
technology is not shared context.

---

## 8. Credentials and External Accounts

NOVA will eventually interact with many external services — email, SMS, Google services,
hosting, domains, analytics, CRMs, payment platforms, automation platforms, databases,
cloud services, APIs, and social platforms.

Credentials are independent security objects, scoped to the smallest appropriate context:

```text
NOVA
 ↓
Permission System
 ↓
Business
 ↓
Client
 ↓
Project / Environment
 ↓
Specific Credential
 ↓
Specific Tool
```

Foundational rules, binding from now on:

- Never hard-code secrets.
- Never commit secrets to Git.
- Never place secrets in documentation.
- Never expose secrets unnecessarily to AI agents.
- Never assume one client's credentials can be used for another client.
- Scope credentials to the smallest appropriate context.

The credential system itself is not implemented in Section 01. It belongs to Section 04,
with integration specifics in Section 11.
