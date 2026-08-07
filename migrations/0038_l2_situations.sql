-- GeniOS Engine · L2 · Situations — the object reasoning consumes instead of the graph.
--
-- A correlation says "these events are about the same thing". A situation says what that
-- thing IS: an opportunity, a support case, a relationship — with how sure we are, how
-- current it is, and what we still do not know.
--
-- ONE SITUATION PER CORRELATION. The correlation already decided the boundary; splitting
-- it further would need judgement nothing deterministic can supply, and two layers
-- drawing the same boundary differently is how a graph starts disagreeing with itself.
--
-- Almost every column here is DERIVED and rebuilt on each refresh. The exceptions are
-- the human decision (`resolved_by='human'`) and the identity of the row itself, which
-- must survive a rebuild or every downstream reference would break.

create table if not exists context_situations (
    situation_id   text primary key,
    org_id         text not null,
    correlation_id text not null,
    anchor_node_id text not null,
    situation_type text not null,       -- deal | opportunity | support_case | …
    domain         text not null,

    -- lifecycle. `dormant` is not failure: a situation that has gone quiet should stop
    -- competing for attention without being forgotten.
    status         text not null default 'active',   -- active | dormant | resolved | archived
    resolved_by    text,                             -- fact | human (they reopen differently)
    resolved_at    timestamptz,
    resolution_note text,

    -- CONFIDENCE AS A VECTOR, not one number. `overall` is the MINIMUM of the trust
    -- dimensions, never the average: they are failure modes, and averaging lets strong
    -- evidence hide the fact that we cannot identify who the situation is about.
    confidence_overall     int,
    confidence_evidence    int,   -- how much independent material backs it
    confidence_freshness   int,   -- how current that material is
    confidence_consistency int,   -- whether the sources contradict each other
    confidence_identity    int,   -- whether we are sure WHO it is about

    -- Completeness, deliberately OUTSIDE `overall`. Not knowing a close date does not
    -- make the stage we do know less true; folding it in would make absence read as
    -- doubt, which this codebase refuses everywhere else.
    coverage       int,
    missing        jsonb not null default '[]',   -- plain-language names of the gaps
    inputs         jsonb not null default '{}',   -- the arithmetic, so a score is explainable

    first_seen_at  timestamptz,
    last_seen_at   timestamptz,
    computed_at    timestamptz not null default now(),

    -- The 1:1 rule, enforced rather than assumed.
    unique (org_id, correlation_id)
);
create index if not exists context_situations_active
    on context_situations (org_id, status, confidence_overall desc);
create index if not exists context_situations_by_anchor
    on context_situations (org_id, anchor_node_id);
create index if not exists context_situations_by_domain
    on context_situations (org_id, domain, status);

alter table context_situations drop constraint if exists context_situations_org_cascade_fk;
alter table context_situations add constraint context_situations_org_cascade_fk
    foreign key (org_id) references orgs (id) on delete cascade not valid;

comment on table context_situations is
  'Assembled business situations — one per correlation. Carries state, confidence and gaps; never priority, risk or recommendation (those are decisions, made downstream).';
