-- Y0 / E-03 · the Layer 3 pilot switch — per tenant AND per DOMAIN.
--
-- WHY A TABLE AND NOT THE BOOLEAN THAT IS ALREADY THERE. `platform/config.py` carries
-- `use_domain_compiler: bool = False`. It is set in NO environment, has never been true anywhere,
-- and the codebase's own comments record what it cost: 152 capabilities dark. Law 5 of the Layer 3
-- doctrine is written directly against it — "activation is per-tenant, per-domain; never a global
-- boolean — `use_domain_compiler=False` is the standing counterexample". Layer 1 answered this the
-- same way (`l1_semantic_activation`, migrations 0085 + 0090) and Layer 2 after it
-- (`l2_v2_activation`, migration 0106); this table is their Layer 3 sibling, deliberately spelled
-- the way `05-Contracts-ExpertisePackage.md` spells it.
--
-- THIS MIGRATION DOES NOT RETIRE THE GLOBAL FLAG, AND MUST NOT. `use_domain_compiler` stays exactly
-- as it is until the first pilot passes J5, then survives one release as a read-only kill switch,
-- then is deleted (doc 06, "Activation & retirement of the global flag"). Deleting a kill switch in
-- the same change that installs the thing it kills leaves a cutover with no way back.
--
-- WHY THE KEY IS (org_id, domain) AND NOT org_id. V1 scope is the ADMIN domain only — Globe's own
-- V1 discipline — while the Sales and Customer Support corpora stay compiled and stamped and
-- inactive. One row per tenant would make "Admin on, Sales off" unexpressible, and the only way to
-- express it would then be to not ship Sales, which is a corpus decision being taken by a schema.
--
-- THE ORDERING THIS TABLE MUST NOT BE USED TO VIOLATE: Y1 (typed consumers) before Y5 (this flip).
-- Flipping activation before rules, heuristics, models and frameworks have runtime readers produces
-- the fake success `reason/adapters/expertise.py` warns about in its own docstring — "activation
-- would LOOK successful while producing generic output". The switch is not the unlock; the weld is.
--
-- REVERSIBLE, AND THE ROW SURVIVES THE REVERSAL. `disabled_at` is STAMPED, never deleted, for the
-- reason migration 0090 earned it one layer down: J5 reads a SEVEN-DAY pilot window, and a window
-- that silently contains a mid-week switch-off is a diff nobody can read. "Live" is
-- `disabled_at is null`, and every read filters on exactly that predicate.

create table if not exists l3_activation (
    -- One row per (tenant, domain). The compiler asks "compile the admin corpus for this org?" and
    -- that is a two-part question, so it is a two-part key.
    org_id       text not null references orgs (id) on delete cascade,

    -- Which corpus. Validated in `platform/l3_activation.require_domain` rather than by a check
    -- constraint here: the corpus is authored content under `Domain Expertise/` and a fourth domain
    -- is an authoring event, not a schema event. A check constraint would make adding one require a
    -- migration, which is how a domain ends up activated by editing SQL by hand.
    domain       text not null,

    -- WHEN. Not-null with a default, as the plan prints it. The first enabling is KEPT across a
    -- re-activation of a live row: "since when has this tenant been on the pilot" is the question
    -- the seven-day J5 report is read against, and an upsert that refreshed this would answer with
    -- the date of the last click instead.
    enabled_at   timestamptz not null default now(),

    -- WHO. Not-null for the reason both sibling tables keep it: a tenant whose compiled output
    -- changed needs an answer to "who decided this and when", and a switch table holding only an
    -- org id can produce neither.
    enabled_by   text not null,

    -- WHY THIS TENANT. The fourth column L1's activation rule earned in migration 0090. "Who" and
    -- "when" without "why" leaves the next operator guessing whether an org is a deliberate design
    -- partner or a leftover from a debugging session.
    notes        text,

    -- THE REVERSAL, STAMPED. Null means live. See the header.
    disabled_at  timestamptz,
    disabled_by  text,

    updated_at   timestamptz not null default now(),

    primary key (org_id, domain)
);

-- The compiler's own read, on the hot path of every sweep: "is the admin corpus live for this
-- tenant". The primary key already covers (org_id, domain); this partial index is what keeps the
-- cross-tenant read — "every org with this domain live" — from scanning stamped-off rows.
create index if not exists l3_activation_live
    on l3_activation (domain, org_id) where disabled_at is null;

comment on table l3_activation is
  'Layer 3 pilot activation. Per tenant, PER DOMAIN, never a config boolean (Law 5; 05-Contracts-ExpertisePackage.md E-03). The compiler live pass reads this instead of platform/config.use_domain_compiler, which stays as a read-only kill switch until J5 has held for 14 days. Written only by an admin path; read by the domain compiler.';
comment on column l3_activation.domain is
  'Which authored corpus is live for this tenant: admin (V1 scope), sales, customer_support. Validated in platform/l3_activation.require_domain, not by a check constraint — a fourth domain is an authoring event, not a schema event.';
comment on column l3_activation.disabled_at is
  'When this (org, domain) was switched back off. Null means live. The row is kept rather than deleted so a seven-day J5 window containing a mid-window switch-off can say so.';
comment on column l3_activation.notes is
  'Why this tenant, and this domain, were chosen for the pilot.';
