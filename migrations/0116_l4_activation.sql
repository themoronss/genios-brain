-- Z0 / G-07 · the Layer 4 pilot switch — per tenant AND per FEATURE.
--
-- WHY FIVE FEATURES AND NOT ONE BOOLEAN. Doc 07 prints the table with five independently
-- flippable features and doc 00's Law 5 is written against the counterexample that is still in
-- the tree: `platform/config.use_domain_compiler = False`, set in no environment, never true
-- anywhere, 152 capabilities dark. Layer 1 answered that with `l1_semantic_activation`
-- (migrations 0085 + 0090), Layer 2 with `l2_v2_activation` (0106) and Layer 3 with
-- `l3_activation` (0107); this table is their Layer 4 sibling and is deliberately spelled the way
-- `07-Contracts.md` spells it.
--
-- WHY THE KEY IS (org_id, feature) AND NOT org_id. The five features are five different amounts
-- of behaviour and they land in five different waves:
--
--   roster_v2   Z1 — the staged unit roster runs through the selector instead of the six units
--                    `reason/adapters/expertise.py:189` hardcodes.
--   ranking_v2  Z3 — six-key utility including importance, and the priority override demoted
--                    from a verdict to a 70/30 prior.
--   bundle      Z4 — the ReasoningBundle narrative is generated for published decisions.
--   critique    Z6 — the critique seam scores an external agent's proposed action (advisory).
--   brief       Z6 — the book-level daily re-rank with `rank_components`.
--
-- A one-row-per-tenant boolean could not express "the roster is awake on this tenant, the
-- narrative is not", which is the exact state waves Z1..Z4 pass through. It would also make the
-- K-gates unreadable: K1a measures a tenant with `roster_v2` on and `ranking_v2` off, and K4
-- measures a tenant with `bundle` on — the same tenant, in the same fortnight, in two different
-- states that one column cannot hold.
--
-- REVERSIBLE, AND THE ROW SURVIVES THE REVERSAL. `disabled_at` is STAMPED, never deleted, for the
-- reason migration 0090 earned it three layers down and 0107 repeated one layer down: K7 reads a
-- SEVEN-DAY pilot window, and a window that silently contains a mid-week switch-off is a diff
-- nobody can read. "Live" is `disabled_at is null`, and every read filters on exactly that.
--
-- WHAT THIS TABLE IS NOT. It is not a kill switch for Layer 4 itself — every tenant keeps running
-- the reasoning engine exactly as it runs today with no row here at all. Every feature above is
-- ADDITIVE, and the fail-closed reads in `platform/l4_activation.py` mean an unreadable table
-- puts every tenant back in the state every tenant is in now.

create table if not exists l4_activation (
    -- One row per (tenant, feature). "Is the narrative on for this org?" is a two-part question,
    -- so it is a two-part key.
    org_id       text not null references orgs (id) on delete cascade,

    -- Which feature. Validated in `platform/l4_activation.require_feature` rather than by a check
    -- constraint here, for the reason 0107 gives about domains: a sixth feature is a WAVE, not a
    -- schema event, and a check constraint would make adding one require a migration — which is
    -- how a feature ends up switched on by somebody editing SQL by hand.
    feature      text not null,

    -- WHEN. Not-null with a default, as doc 07 prints it. The first enabling is KEPT across a
    -- re-activation of a live row: "since when has this tenant been on the pilot" is the question
    -- the seven-day K7 report is read against, and an upsert that refreshed this would answer
    -- with the date of the last click instead.
    enabled_at   timestamptz not null default now(),

    -- WHO. Not-null for the reason all three sibling tables keep it: a tenant whose decisions
    -- changed needs an answer to "who decided this and when", and a switch table holding only an
    -- org id can produce neither.
    enabled_by   text not null,

    -- WHY THIS TENANT. The fourth column L1's activation rule earned in migration 0090. "Who" and
    -- "when" without "why" leaves the next operator guessing whether an org is a deliberate
    -- design partner or a leftover from a debugging session.
    notes        text,

    -- THE REVERSAL, STAMPED. Null means live. See the header.
    disabled_at  timestamptz,
    disabled_by  text,

    updated_at   timestamptz not null default now(),

    primary key (org_id, feature)
);

-- The engine's own read, on the hot path of every reasoning run: "is ranking_v2 live for this
-- tenant". The primary key already covers (org_id, feature); this partial index is what keeps the
-- cross-tenant read — "every org with this feature live" — from scanning stamped-off rows.
create index if not exists l4_activation_live
    on l4_activation (feature, org_id) where disabled_at is null;

comment on table l4_activation is
  'Layer 4 pilot activation. Per tenant, PER FEATURE (roster_v2, ranking_v2, bundle, critique, brief), never a config boolean (Law 5; 07-Contracts.md G-07). Read fail-closed by platform/l4_activation.py; written only by the /admin/l4-activation routes.';
comment on column l4_activation.feature is
  'Which Layer 4 v2 feature is live for this tenant: roster_v2 (Z1), ranking_v2 (Z3), bundle (Z4), critique (Z6), brief (Z6). Validated in platform/l4_activation.require_feature, not by a check constraint — a sixth feature is a wave, not a schema event.';
comment on column l4_activation.disabled_at is
  'When this (org, feature) was switched back off. Null means live. The row is kept rather than deleted so a seven-day K7 window containing a mid-window switch-off can say so.';
comment on column l4_activation.notes is
  'Why this tenant, and this feature, were chosen for the pilot.';
