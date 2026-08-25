-- NOVA substrate schema -- ADR 0044 (Proposed).
--
-- Six tables. No domain tables: tasks, clients, projects, businesses and
-- wealth belong to Sections 19-28 and would be speculative here.
--
-- The security-relevant content of this file is the role split and the RLS
-- policies. Everything else is ordinary DDL.
--
--   nova_owner  owns the tables. Migrations only. Never used by request code.
--   nova_app    the application role. NOBYPASSRLS, NOSUPERUSER, not an owner.
--
-- A table OWNER bypasses RLS unless FORCE ROW LEVEL SECURITY is set, and a
-- superuser bypasses it unconditionally. Both are silent: every application
-- test would still pass while isolation was absent. That is why the split is
-- explicit here and asserted by test rather than assumed.

-- ---------------------------------------------------------------------------
-- Roles
-- ---------------------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nova_owner') THEN
        CREATE ROLE nova_owner LOGIN;
    END IF;
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nova_app') THEN
        -- NOBYPASSRLS and NOSUPERUSER are the load-bearing attributes.
        CREATE ROLE nova_app LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
    -- Authentication runs before any Context Token exists, so it cannot go
    -- through the Data-Access Boundary. It gets its own identity instead, with
    -- privileges on the two auth tables and nothing else.
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nova_auth') THEN
        CREATE ROLE nova_auth LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
    -- The scope tree and its grants ARE the permission model, so something has
    -- to read them before any scope binding can exist. That reader is this
    -- role, at startup only, never in the request path. It is NOT a bypass:
    -- see the control-plane policies below.
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nova_control') THEN
        CREATE ROLE nova_control LOGIN NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;

-- ---------------------------------------------------------------------------
-- The scope binding
-- ---------------------------------------------------------------------------

CREATE SCHEMA IF NOT EXISTS nova AUTHORIZATION nova_owner;

-- Reads the transaction-local binding the Data-Access Boundary established.
-- Returns NULL when unset, which every policy below treats as "deny" -- there
-- is no default scope (I-79).
CREATE OR REPLACE FUNCTION nova.current_scope() RETURNS text
    LANGUAGE sql STABLE
    AS $$ SELECT nullif(current_setting('nova.scope_path', true), '') $$;

-- Scope containment, matching ContextToken.covers(): a binding reaches its own
-- scope and everything below it. Siblings have no path (I-03).
--
-- starts_with() rather than LIKE: LIKE would treat % and _ in a scope path as
-- wildcards, which is a pattern-injection hazard in the one predicate that must
-- never be wrong.
CREATE OR REPLACE FUNCTION nova.in_scope(row_scope text) RETURNS boolean
    LANGUAGE sql STABLE
    AS $$
        SELECT nova.current_scope() IS NOT NULL
           AND (row_scope = nova.current_scope()
                OR starts_with(row_scope, nova.current_scope() || '/'))
    $$;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

-- Actors are not scoped: an actor exists above the scope tree, and scoping the
-- actor table would make identity itself invisible across scopes.
--
-- Q-04: identity is explicit rather than assumed. This does NOT make NOVA
-- multi-user -- there are no roles, teams or invitations -- it only avoids
-- hard-coding one actor into the data model. I-09 is untouched: an actor is
-- not thereby an approver.
CREATE TABLE IF NOT EXISTS actor (
    id           bigserial PRIMARY KEY,
    actor_ref    text NOT NULL UNIQUE,
    display_name text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS scope (
    id          bigserial PRIMARY KEY,
    scope_path  text NOT NULL UNIQUE,
    kind        text NOT NULL,
    parent_path text,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS "grant" (
    id         bigserial PRIMARY KEY,
    actor_ref  text NOT NULL,
    scope_path text NOT NULL,
    right_name text NOT NULL,
    granted_at timestamptz NOT NULL DEFAULT now()
);

-- I-109 binds ten properties. The binding identity is stored rather than the
-- properties themselves: I-93's deterministic construction is what makes an
-- approval comparable at execution time.
CREATE TABLE IF NOT EXISTS approval (
    id                bigserial PRIMARY KEY,
    approval_id       text NOT NULL UNIQUE,
    actor_ref         text NOT NULL,
    scope_path        text NOT NULL,
    binding_identity  text NOT NULL,
    risk_class        text NOT NULL,
    created_at        timestamptz NOT NULL DEFAULT now()
);

-- The fields USER_INTERFACE_ARCHITECTURE.md section 6 requires an approval
-- request to state "in plain language: what will happen, in which scope, why
-- it needs approval, what it costs, and what happens if it is wrong".
-- Added as columns rather than a second table: an approval request IS an
-- approval awaiting a decision, and splitting them would make the pending and
-- decided states two things that must be kept in step.
--
-- `plan_identity` is what binds the decision to one exact action (I-112).
-- The arguments are stored so the plan can be RECONSTRUCTED at execution and
-- its identity compared -- an approval whose plan no longer hashes the same
-- does not apply (I-109).
ALTER TABLE approval
    ADD COLUMN IF NOT EXISTS plan_identity  text,
    ADD COLUMN IF NOT EXISTS status         text NOT NULL DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS action_text    text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS why_text       text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS cost_text      text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS if_wrong_text  text NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS item_ref       text,
    ADD COLUMN IF NOT EXISTS body           text,
    ADD COLUMN IF NOT EXISTS decided_at     timestamptz,
    ADD COLUMN IF NOT EXISTS decided_by     text,
    -- Which tool the approved plan runs, and its arguments. Added when the
    -- second consequence-producing tool arrived: an approval was previously
    -- describable by (item_ref, body) because there was only one thing NOVA
    -- could do. `tool_name` defaults to the original tool so existing rows
    -- reconstruct exactly as before.
    ADD COLUMN IF NOT EXISTS tool_name      text NOT NULL DEFAULT 'write_item',
    ADD COLUMN IF NOT EXISTS arguments      jsonb,
    -- ADR 0048. The HONEST taint of the content at proposal time -- the union
    -- of what the proposer read plus its own provenance -- serialized with the
    -- existing `Taint.to_row()`. No new serialization, no content hash (the
    -- plan identity already hashes every argument), no `content_visible` flag
    -- (a flag is the UI's claim about itself; visibility is derived from the
    -- tool's own EXPRESSIVE declaration instead).
    --
    -- It is stored rather than recomputed because an elevation must be
    -- attributable to the taint James was actually shown. Recomputing it at
    -- execution would read a scope that may have changed since he looked.
    --
    -- NULLABLE, and NULL means UNKNOWN: rows written before ADR 0048 have no
    -- recorded taint, so they execute at the derived taint and can never
    -- elevate. Not backfilled -- inventing evidence of an inspection that may
    -- never have happened is precisely what ADR 0048 forbids.
    ADD COLUMN IF NOT EXISTS proposed_taint text,
    -- SINGLE USE (I-09). An approval is James's act for ONE execution, not a
    -- durable permission. NULL means unspent; once set it is never cleared,
    -- and no path re-offers the row. The column is the DURABLE half of the
    -- rule; `WHERE ... AND consumed_at IS NULL` in an UPDATE ... RETURNING is
    -- what makes claiming it atomic, so two concurrent decisions cannot both
    -- observe it unspent. Additive: existing rows default to NULL, i.e.
    -- unspent, which is what they were.
    ADD COLUMN IF NOT EXISTS consumed_at    timestamptz,
    -- CRASH RECOVERY. The trace_id of the token that claimed this approval,
    -- written in the SAME statement as the claim. `audit_record.event_identity`
    -- for a data write is derived from that trace_id, and a trace_id is a
    -- uuid4 living only in the token -- so without this column a recovering
    -- process cannot rebuild the identity, and cannot tell an interrupted
    -- execution that landed from one that never ran.
    --
    -- It is a LOOKUP KEY FOR EVIDENCE, never an input to a decision: nothing
    -- reads it to authorize anything, and recovery has no execution path.
    ADD COLUMN IF NOT EXISTS execution_trace_id text;

-- ---------------------------------------------------------------------------
-- Authentication (D-09) -- ABOVE the scope tree
-- ---------------------------------------------------------------------------
-- A session is established BEFORE any scope is chosen, so these tables carry no
-- scope_path and no RLS policy, for the same reason `actor` does not: scoping
-- identity would make it invisible from the scopes that need it.
--
-- They are instead isolated by PRIVILEGE. `nova_auth` may touch these two
-- tables and nothing else; `nova_app` may touch everything else and NOT these.
-- The split is the point: authentication runs before a Context Token exists and
-- therefore cannot go through the Data-Access Boundary, so it must not hold a
-- connection that could reach scoped data (I-78 is untouched -- no scope-bound
-- channel is opened here).

CREATE TABLE IF NOT EXISTS auth_credential (
    id            bigserial PRIMARY KEY,
    credential_id text NOT NULL UNIQUE,   -- base64url, as the authenticator gave it
    actor_ref     text NOT NULL,
    identity      text NOT NULL,
    public_key    bytea NOT NULL,         -- COSE key. NOT a secret: it is public.
    sign_count    bigint NOT NULL DEFAULT 0,
    label         text NOT NULL DEFAULT '',
    created_at    timestamptz NOT NULL DEFAULT now()
);

-- `session_ref` is the SHA-256 of the opaque value the browser holds -- never
-- the value itself. A dump of this table yields no usable session: the column
-- is a verifier, not a credential.
--
-- A-6: sessions are individually enumerable and revocable. Expiry is ABSOLUTE
-- and is not extended by activity.
CREATE TABLE IF NOT EXISTS auth_session (
    id             bigserial PRIMARY KEY,
    session_ref    text NOT NULL UNIQUE,
    actor_ref      text NOT NULL,
    identity       text NOT NULL,
    strength       text NOT NULL,          -- A-1: single_factor | multi_factor
    surface        text NOT NULL DEFAULT '',
    credential_id  text,
    established_at timestamptz NOT NULL DEFAULT now(),
    expires_at     timestamptz NOT NULL,
    revoked_at     timestamptz
);

-- What needs doing. USER_INTERFACE_ARCHITECTURE section 3 names three views
-- that cut across the tree "because they answer questions James actually
-- asks": what needs my decision (approval), what did NOVA do (audit_record),
-- and WHAT NEEDS DOING -- this table.
--
-- One table, not five. No projects, no assignees, no priorities, no labels,
-- no recurrence: a task is a thing to do, in a scope, optionally by a date,
-- and eventually done. Everything else is speculation until James's own use
-- shows otherwise.
--
-- Why not an `item`: a due date and a completion state must be QUERYABLE --
-- "what is open here, soonest first" is not answerable from prose. That is
-- the only reason this table exists.
CREATE TABLE IF NOT EXISTS task (
    id         bigserial PRIMARY KEY,
    task_ref   text NOT NULL,
    scope_path text NOT NULL,
    actor_ref  text,
    title      text NOT NULL,
    due_on     date,
    done_at    timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_path, task_ref)
);

-- ADR 0049 / I-111: a TASK TITLE IS CONTENT, not control state.
--
-- `add_task_tool()` has always declared `title` EXPRESSIVE -- "prose, same
-- ruling as write_item" (ADR 0036) -- and ADR 0048's approval card renders it
-- as content for James to inspect. Every layer above storage already treated
-- it as content; only this table disagreed, and the taint computed for a task
-- was discarded at the INSERT. A title can carry a factual claim in imperative
-- grammar -- "call the supplier, their bank details changed to X" -- so
-- treating all titles as safe control state laundered attacker-controlled
-- facts into model context as james.stated/HIGHEST once the original source
-- was deleted. Measured before this existed.
--
-- The same five columns as `item`, with the same meanings, deliberately not
-- reinterpreted. NULL is unknown throughout, which is what makes a row written
-- before ADR 0049 structurally distinguishable from one whose state was
-- genuinely recorded.
--
-- ROW-LEVEL, and no history table (ADR 0049's Model 1). The existing upsert
-- keeps ONE row per (scope_path, task_ref) and destroys the previous title
-- outright, so there is no superseded version that could become detached from
-- its provenance -- provided the write updates these columns in the SAME
-- statement as the title, which it does.
--
-- No guard is needed here, unlike `item.provenance`: no conflicting column of
-- another type ever existed on this table. Existing rows are NOT backfilled --
-- inventing provenance for a title nobody recorded one for is the assumption
-- I-110 forbids.
ALTER TABLE task
    ADD COLUMN IF NOT EXISTS provenance          text[],
    ADD COLUMN IF NOT EXISTS trust               smallint,
    ADD COLUMN IF NOT EXISTS classification      smallint,
    ADD COLUMN IF NOT EXISTS delegation_ancestry text[],
    ADD COLUMN IF NOT EXISTS creating_authority  text;

-- I-93: every mandatory audit record carries a deterministic event identity, so
-- an uncertain write is retried and de-duplicated by identity rather than
-- producing a second event. The UNIQUE constraint is that rule, enforced.
CREATE TABLE IF NOT EXISTS audit_record (
    id             bigserial PRIMARY KEY,
    event_identity text NOT NULL UNIQUE,
    writer         text NOT NULL,
    category       text NOT NULL,
    scope_path     text NOT NULL,
    trace_id       text NOT NULL,
    actor_ref      text,
    detail         text NOT NULL,
    written_at     timestamptz NOT NULL DEFAULT now()
);

-- One scoped payload table. This is what the adversarial suite tries to reach
-- across scopes.
CREATE TABLE IF NOT EXISTS item (
    id         bigserial PRIMARY KEY,
    item_ref   text NOT NULL,
    scope_path text NOT NULL,
    actor_ref  text,
    body       text NOT NULL,
    provenance text NOT NULL DEFAULT '',
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (scope_path, item_ref)
);

-- ---------------------------------------------------------------------------
-- I-111 -- the security state that must survive persistence
-- ---------------------------------------------------------------------------
-- `I-111`: provenance, taint and delegation ancestry survive persistence and
-- are RESTORED at retrieval. Persistence must not discard provenance, collapse
-- multiple sources into one, raise trust, or replace `I-99`'s union with the
-- latest writer alone. Each concept therefore gets its own column: packing them
-- into one field would make the schema unable to say what it holds, and would
-- reintroduce the delimiter encoding this design rejects.
--
-- EVERY COLUMN IS NULLABLE ON PURPOSE. NULL means "unknown / unestablishable",
-- and it is the only thing that makes rows written before I-111 structurally
-- distinguishable from rows whose security state was genuinely recorded. A
-- NOT NULL DEFAULT would erase that distinction and make an assumption
-- permanent and unauditable.
--
--   provenance          NULL = unknown; {} = established empty; else I-99 union
--   trust               NULL = unknown; else Trust (0..3), the LOWEST contributor
--   classification      NULL = unknown; else Classification (0..5), STRICTEST (I-27)
--   delegation_ancestry NULL = unknown; {} = NO delegation; else the ordered chain
--   creating_authority  NULL = unknown; else the execution identity that wrote it
--
-- `provenance` was previously an unused `text` column: zero readers, zero
-- writers, zero tests, no data. A set-valued union cannot be represented in it,
-- and NOT NULL cannot represent "unknown", so it is REPLACED rather than
-- reinterpreted. The replacement is guarded on the column's current type, so
-- re-applying this file never drops a populated text[] column -- an unguarded
-- DROP+ADD here would silently destroy provenance on every startup.
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns
               WHERE table_name = 'item' AND column_name = 'provenance'
                 AND data_type = 'text') THEN
        ALTER TABLE item DROP COLUMN provenance;
    END IF;
END
$$;

ALTER TABLE item
    ADD COLUMN IF NOT EXISTS provenance          text[],
    ADD COLUMN IF NOT EXISTS trust               smallint,
    ADD COLUMN IF NOT EXISTS classification      smallint,
    ADD COLUMN IF NOT EXISTS delegation_ancestry text[],
    ADD COLUMN IF NOT EXISTS creating_authority  text;

-- S7-D5 / I-111: retrieval must surface whether the authority that created an
-- item was later REVOKED. A revocation set held in memory cannot do that -- it
-- empties on restart, and every revoked authority would silently read as clean.
--
-- A NEGATIVE registry: presence means revoked. Absence means not-revoked ONLY
-- when the lookup was complete and authorized for that identity; an
-- unestablishable lookup is "unknown", and unknown fails closed. That
-- distinction is the whole security property, and it is made in code, not here.
--
-- SCOPED like every other scoped table: an authority's revocation is visible
-- from its own scope and its ancestors, never from a sibling. There is NO
-- cross-scope exception -- if an ancestor's revocation state cannot be read
-- from the authorized scope, the item fails closed instead.
--
-- Revocation is AUTHORITY state, not item lineage: it is deliberately outside
-- ADR 0013's item cascade, because deleting the items an authority created
-- must never make that authority read as un-revoked.
CREATE TABLE IF NOT EXISTS authority_revocation (
    id                 bigserial PRIMARY KEY,
    execution_identity text NOT NULL UNIQUE,
    scope_path         text NOT NULL,
    revoked_at         timestamptz NOT NULL DEFAULT now(),
    revoked_by         text NOT NULL
);

-- Ownership is explicit: nova_owner owns, nova_app never does. Left implicit,
-- the tables would be owned by whichever role ran this file, and if that were
-- ever the application role, RLS would be bypassable by ownership.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['actor', 'scope', 'grant', 'approval', 'audit_record',
                             'item', 'task', 'auth_credential', 'auth_session',
                             'authority_revocation']
    LOOP
        EXECUTE format('ALTER TABLE %I OWNER TO nova_owner', t);
    END LOOP;
END
$$;

-- ---------------------------------------------------------------------------
-- Row-Level Security
-- ---------------------------------------------------------------------------
-- ENABLE applies the policy to everyone except the owner; FORCE applies it to
-- the owner too. Both are set so that ownership is not a silent bypass.

DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['scope', 'grant', 'approval', 'audit_record', 'item', 'task',
                             'authority_revocation']
    LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
        EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
        EXECUTE format('DROP POLICY IF EXISTS scope_isolation ON %I', t);
        EXECUTE format(
            'CREATE POLICY scope_isolation ON %I
                 USING (nova.in_scope(scope_path))
                 WITH CHECK (nova.in_scope(scope_path))', t);
    END LOOP;
END
$$;

-- actor carries no scope_path and is deliberately not scope-isolated.

-- The control-plane read. `scope` and `grant` define where the boundaries ARE,
-- which is a genuine bootstrap problem: a scope-bound channel cannot be opened
-- until the tree that decides the binding has been read.
--
-- Solved with the engine's own mechanism rather than around it. These policies
-- are attached TO ONE ROLE, so PostgreSQL applies them to `nova_control` and to
-- nothing else. `nova_app` still sees only `scope_isolation` and is still
-- bounded by it -- asserted by test, in both directions.
--
-- nova_control is READ-ONLY on exactly these two tables, holds no privilege on
-- `item`, `approval` or `audit_record`, and is used only when the application
-- starts. It is NOT NOBYPASSRLS as a formality: it genuinely cannot bypass RLS,
-- it is simply named by a policy that permits the read it needs.
DROP POLICY IF EXISTS control_plane_read ON scope;
CREATE POLICY control_plane_read ON scope FOR SELECT TO nova_control USING (true);
DROP POLICY IF EXISTS control_plane_read ON "grant";
CREATE POLICY control_plane_read ON "grant" FOR SELECT TO nova_control USING (true);

-- ---------------------------------------------------------------------------
-- Privileges
-- ---------------------------------------------------------------------------
-- nova_app gets DML only. No DDL, no ownership, no role administration.

GRANT USAGE ON SCHEMA public, nova TO nova_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    actor, scope, "grant", approval, audit_record, item, task TO nova_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nova_app;

-- Revocation is APPEND-ONLY for the application role: SELECT and INSERT, never
-- UPDATE, never DELETE. Enforced by PRIVILEGE rather than by the application
-- declining to issue the statement, because "no code path does that today" is
-- not a control -- a future path, or a compromised one, would face nothing.
--
-- Why it matters here specifically: this registry signals by PRESENCE. A
-- deleted or edited revocation row would turn a revoked authority back into an
-- apparently clean one, and every item it created would silently become usable
-- in model context again. The absence of DELETE is what makes "absence means
-- not revoked" safe to rely on.
GRANT SELECT, INSERT ON authority_revocation TO nova_app;
REVOKE UPDATE, DELETE, TRUNCATE ON authority_revocation FROM nova_app;
GRANT EXECUTE ON FUNCTION nova.current_scope(), nova.in_scope(text) TO nova_app;

-- nova_auth reaches the two auth tables and NOTHING else. Deliberately no
-- grant on item, approval, audit_record, scope or "grant": a compromised
-- authentication path holds a connection that cannot read scoped data at all.
-- Asserted by test, not assumed.
GRANT USAGE ON SCHEMA public TO nova_auth;
GRANT SELECT, INSERT, UPDATE ON auth_credential, auth_session TO nova_auth;
GRANT USAGE, SELECT ON SEQUENCE auth_credential_id_seq, auth_session_id_seq TO nova_auth;

-- The generic `scope_isolation` policy still applies to this role as well --
-- permissive policies are OR'd, not replaced -- so it must be able to EVALUATE
-- that predicate even though `control_plane_read` is what admits its rows.
-- Granting EXECUTE on two boolean predicates widens no data access.
GRANT USAGE ON SCHEMA public, nova TO nova_control;
GRANT EXECUTE ON FUNCTION nova.current_scope(), nova.in_scope(text) TO nova_control;
GRANT SELECT ON scope, "grant" TO nova_control;

-- ...and nova_app must NOT reach them. Authentication state is not application
-- data; the application role having it would make the privilege split cosmetic.
REVOKE ALL ON auth_credential, auth_session FROM nova_app;
