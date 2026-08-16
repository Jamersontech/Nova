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
    ADD COLUMN IF NOT EXISTS decided_by     text;

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

-- Ownership is explicit: nova_owner owns, nova_app never does. Left implicit,
-- the tables would be owned by whichever role ran this file, and if that were
-- ever the application role, RLS would be bypassable by ownership.
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY['actor', 'scope', 'grant', 'approval', 'audit_record', 'item']
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
    FOREACH t IN ARRAY ARRAY['scope', 'grant', 'approval', 'audit_record', 'item']
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

-- ---------------------------------------------------------------------------
-- Privileges
-- ---------------------------------------------------------------------------
-- nova_app gets DML only. No DDL, no ownership, no role administration.

GRANT USAGE ON SCHEMA public, nova TO nova_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON
    actor, scope, "grant", approval, audit_record, item TO nova_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO nova_app;
GRANT EXECUTE ON FUNCTION nova.current_scope(), nova.in_scope(text) TO nova_app;
