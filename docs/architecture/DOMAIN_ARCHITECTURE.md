# Domain Architecture

**Status:** **Active** — Section 02, approved by James 2026-08-12.
**Resolves:** **M-1** (LIFE undefined) and **M-2** (multi-business model) from the Section 1
final audit.
**Extends:** [`../DOMAIN_MODEL.md`](../DOMAIN_MODEL.md), which defined the business branch.
Nothing there is replaced; this document generalizes it so LIFE and WEALTH fit the same
rules.

---

## 1. The Unifying Idea: One Scope Tree

Section 1 defined Business → Client → Project → Environment. The obvious but wrong move
now would be to invent a parallel hierarchy for LIFE and a third for WEALTH. That triples
the permission logic, the memory rules, and the isolation surface.

Instead, all three domains are **subtrees of one scope tree**, governed by identical rules.

```text
NOVA                                    root scope
├── LIFE                                domain scope
│   ├── Area: School                    area scope
│   ├── Area: Health                    area scope
│   └── Area: Travel                    area scope
├── BUSINESS                            domain scope
│   ├── KAIRO                           business scope
│   │   ├── Client A                    client scope
│   │   │   └── Website Project         project scope
│   │   │       └── Production          environment scope
│   │   └── Client B                    client scope
│   └── Business B                      business scope
└── WEALTH                              domain scope
    └── Account Group                   wealth scope
```

**A scope is four things at once:**

| As a… | It means |
| --- | --- |
| Context anchor | The "where am I working" of a request |
| Permission boundary | The unit rights are granted over |
| Memory partition | Memory written here is readable only here and below |
| Credential partition | Credentials are scoped to a node, never global |

**The access rule, stated once and applied everywhere:**

> Access flows **downward only**, and only when **explicitly granted**. Holding a scope
> grants nothing about a sibling and nothing about a parent.

Client A and Client B are siblings — there is no path between them. LIFE and BUSINESS are
siblings — personal information does not flow into client work. This is the same rule
doing all of that work.

---

## 2. LIFE — Resolving M-1

### 2.1 The shape

LIFE does not have clients, and forcing it into Client → Project → Environment would be a
distortion. LIFE decomposes into **Areas**, and Areas hold **Threads**.

```text
LIFE
└── Area                 an ongoing part of James's life
    └── Thread           a specific concern within it, with a beginning and usually an end
        └── Items        tasks, events, documents, notes, messages
```

**Area** — a durable division of personal life. Examples: School, Health, Travel,
Relationships, Home, Personal Projects, Admin/Finance-adjacent. Areas are long-lived and
few. They are permission and memory boundaries.

**Thread** — a bounded concern inside an Area. "Autumn semester enrolment", "Japan trip
in March", "Annual health check". A Thread is LIFE's analogue of a Project: it has a
beginning, an end, work items, and its own small memory.

**Item** — the atoms: tasks, calendar events, documents, notes, contacts, messages. Items
are the *same entity types* used in BUSINESS ([`DATA_ARCHITECTURE.md`](./DATA_ARCHITECTURE.md)),
not personal-life-specific duplicates.

### 2.2 Why Area → Thread rather than more structure

The brief lists school, tasks, calendar, relationships, travel, health, routines, personal
projects, documents, communications, planning, and goals. Most of these are **not
containers** — they are either Areas (school, health, travel, relationships) or Item types
(tasks, calendar events, documents, communications) or cross-cutting views (planning,
goals, routines).

Turning each into a structural level would produce a deep, rigid hierarchy for a part of
life that is inherently fluid. Two levels plus typed items is enough, and it means LIFE
reuses the entire Business machinery — tasks, documents, memory, agents, permissions —
rather than requiring its own.

**Goals and routines are not containers.** A goal is a durable Item that Threads reference;
a routine is a recurring Workflow. Both are views across Areas, not levels within one.

### 2.3 Sensitivity within LIFE

Some Areas are more sensitive than any business data — health and relationships in
particular. LIFE therefore supports a **sensitivity marking** on Areas and Items that:

- excludes them from proactive surfacing unless James is in that Area's context,
- requires explicit context to be readable at all, even by NOVA's own agents,
- is never summarized into cross-domain memory.

This is the mechanism that prevents "NOVA mentions a medical appointment while drafting a
client email." Detail is deferred to Section 37 (Privacy & Data Governance).

### 2.4 What LIFE gets from the shared platform

Tasks, documents, calendar, communications, memory, agents, workflows, notifications, and
approvals are **platform capabilities**, not business capabilities. LIFE uses the same ones.
Nothing in LIFE is bespoke except its Area/Thread shape and its sensitivity rules.

---

## 3. BUSINESS — Resolving M-2

### 3.1 Shared platform, isolated contexts

The requirement is multiple independent businesses without duplicated infrastructure. The
resolution:

> **One platform. Many isolated scope subtrees. No per-business infrastructure.**

Adding Business B creates **scope nodes and configuration** — not a second orchestrator, a
second agent runtime, a second tool registry, or a second deployment.

```text
Shared platform (single instance of each):
  Identity · Context · Policy · Orchestration · Agent Runtime
  Capability Registry · Model Gateway · Memory · Event Bus
  Approval · Observability

Per-business (data and configuration only):
  scope subtree · clients · projects · environments
  credentials · integrations · business memory
  agent grants · workflow definitions · branding
```

### 3.2 What lives at which level

This is the table that prevents the most common multi-tenant mistake — putting something
at the wrong level and discovering it years later.

| Level | Owns | Never owns |
| --- | --- | --- |
| **NOVA (root)** | Platform services, tool *definitions*, model routing policy, James's identity, global preferences | Any business or client data |
| **Domain** (LIFE/BUSINESS/WEALTH) | Domain-wide policy, domain memory, cross-business views | Client specifics |
| **Business** (e.g. KAIRO) | Clients, business-level integrations, business memory, brand, offerings, business agents | Another business's anything |
| **Client** | Projects, client contacts, client communications, client documents, client memory | Another client's anything |
| **Project** | Work: tasks, deliverables, workflows, project documents, project memory | Live infrastructure |
| **Environment** | Deployment target: source, config, hosting, domains, environment credentials | Business-level decisions |

**Tools are defined once at root and *bound* per scope.** A "send email" tool exists once;
KAIRO/Client A's binding of it resolves to Client A's mailbox credential. This is how tools
are reusable across businesses without ever mixing them — the tool is shared, the
credential and the data are not.

### 3.3 Adding a business

Adding Business B is a configuration operation: create the scope node, define its clients,
attach its credentials, grant agents into it. No code changes, no new services, no schema
migration. If adding a business ever requires more than this, the isolation model has been
violated somewhere and that is a defect.

### 3.4 KAIRO

KAIRO is one business scope among several — never the default, never a synonym for
"business". Its specific architecture is Section 21. The
[`EXECUTION_ARCHITECTURE.md`](./EXECUTION_ARCHITECTURE.md) worked example uses KAIRO
because it is the business that exists today, not because it is privileged.

### 3.5 Shared Resources

*Added 2026-08-12 per James's clarification to [ADR 0002](../decisions/0002-unified-scope-tree.md).*

Businesses accumulate reusable material: site templates, component libraries, playbooks,
brand assets, standard operating procedures. NOVA must support sharing these **without
duplicating client data and without weakening client isolation.**

**A shared resource is placed at the nearest common ancestor and referenced downward.**

```text
KAIRO                              ← shared resource lives here
├── shared: template · component library · SOP
├── Client A → references downward       ✅
└── Client B → references downward       ✅
              Client A ⇄ Client B        ❌ no path, unchanged
```

This uses the existing downward-access rule rather than adding an exception.

**Placement is not authorization.** *(Added 2026-08-12 per James.)* The diagram shows
**where** a shared resource lives, not **who** may read it:

> Placement at a common ancestor does not imply universal descendant access. A shared
> resource must have explicit authorization for each consuming descendant scope, or an
> explicitly defined policy granting access to a specified set of descendants. Ancestor
> placement is a location/modeling rule, not an access grant.

Placing a resource at the KAIRO scope does **not** make it readable by every KAIRO client.
Creating a shared resource and authorizing its consumers are two distinct operations; grants
are per-descendant, auditable, and individually revocable. A policy covering a *set* of
descendants is permitted only where that set is explicitly defined and deliberately chosen —
never as a default. Default remains deny.

Without this rule, ancestor placement would be an implicit broadcast: promoting anything to
a business scope would silently expose it to every client beneath. That is exactly the
ambient authority the access rule exists to prevent.

Three further constraints keep it safe:

1. **Reference, never copy.** Children reference the resource; they receive no duplicate.
   One update propagates instead of drifting into divergent per-client copies.
2. **No client-identifying data in a shared resource.** Placing client material at a shared
   scope is memory elevation — explicit, permissioned, audited
   ([`MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md`](./MEMORY_AND_KNOWLEDGE_ARCHITECTURE.md) §3).
   A template is shareable; a template containing Client A's copy is not.
3. **Sharing is deliberate, never ambient.** A resource is shared because it was placed at a
   shared scope — not because two clients need something similar. Reads remain attributable
   to the child scope that made them.

**Still prohibited:** one client's resource read from another's context; a scope with two
parents; a "shared" resource that is really one client's material relabelled; and **sharing
a credential** — credentials remain scoped to exactly one node. Shared capability never
means shared access.

This generalizes the tool-binding pattern (§3.2) from tools to any resource.

---

## 4. WEALTH

WEALTH is defined here only as far as the scope tree requires; its substance is Section 23,
and `Q-02` (what WEALTH covers) remains open.

```text
WEALTH
└── Account Group        e.g. Personal, Business-held, Long-term
    └── Position / Account / Asset
```

Two rules are established now because they are structural:

1. **WEALTH is read-mostly by default.** Financial actions are high-impact or irreversible
   and default to requiring explicit approval ([`PERMISSION_ARCHITECTURE.md`](./PERMISSION_ARCHITECTURE.md)).
2. **WEALTH may read across domains; domains may not read WEALTH.** Wealth analysis
   legitimately needs business revenue and personal expenses. The reverse — a client
   project agent reading net worth — has no legitimate use. This is an explicit,
   audited, one-directional grant, and the only such exception in the architecture.

---

## 5. Cross-Domain Work

Some requests genuinely span domains ("how much did the Japan trip cost against this
quarter's KAIRO income?"). These are handled by **explicit cross-scope grants** evaluated
by Policy, not by giving any agent ambient global vision:

- The request is decomposed into per-scope sub-requests, each with its own token.
- Results are aggregated at the Orchestration layer, above the isolated executions.
- The aggregation itself is recorded as a cross-domain access in the audit trail.

This preserves "globally intelligent, locally isolated" literally: intelligence is global
at the top, access is isolated at the bottom.

---

## 6. Open Questions

`Q-01` (which businesses beyond KAIRO), `Q-02` (WEALTH scope), and `Q-04` (multi-user) remain
open in [`../decisions/DEFERRED_DECISIONS.md`](../decisions/DEFERRED_DECISIONS.md). The
architecture above does not depend on their answers — it accommodates any answer — which is
why Section 2 could proceed without them. A new LIFE question, `Q-07`, is added there.
