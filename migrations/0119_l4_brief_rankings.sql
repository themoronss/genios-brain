-- Wave Z6 · seam OUT E3 — the book-level daily re-rank (doc 06 OUT-2, DLG-09).
--
-- One row per tenant per brief day, holding the ranking that pass produced and the components that
-- produced it. A table rather than a computed-on-read view for two reasons, and neither is caching:
--
--   * "BriefRanking produced daily with rank_components" is gate K6's row, and a gate whose only
--     evidence is that an endpoint would answer if somebody called it is not evidence;
--   * "why was this #1 today, and why is it #4 now" is the question a brief invites, and it cannot
--     be answered from a surface that recomputes. `ranking_hash` makes "did today's brief change"
--     a string compare, and `receipts` keeps the counts behind each penalty — three surfacings,
--     four recorded absences, second card on this account — which `rank_components` cannot carry
--     because that mapping is basis points by contract and a count is not a basis point.
--
-- `entries` is the contract shape (`BriefEntry`: decision_id, rank, book_score_bp,
-- rank_components) and `dropped` is every open decision the pass did NOT rank, with its reason —
-- a brief that silently omits a card is indistinguishable from one that never saw it.
create table if not exists l4_brief_rankings (
    org_id         text not null references orgs (id) on delete cascade,
    brief_date_key text not null,
    entries        jsonb not null default '[]',
    receipts       jsonb not null default '[]',
    dropped        jsonb not null default '[]',
    entry_count    integer not null default 0,
    model_version  text not null,
    ranking_hash   text not null,
    computed_at    timestamptz not null default now(),
    primary key (org_id, brief_date_key),
    -- YYYY-MM-DD, the same shape `BriefRanking.brief_date_key` validates. Enforced here too
    -- because a date KEY that drifts into a timestamp makes "which brief" depend on what hour it
    -- was assembled, which is the one thing a daily artifact may not depend on.
    check (brief_date_key ~ '^\d{4}-\d{2}-\d{2}$'),
    check (jsonb_typeof(entries) = 'array'),
    check (jsonb_typeof(receipts) = 'array'),
    check (jsonb_typeof(dropped) = 'array'),
    check (entry_count >= 0 and entry_count = jsonb_array_length(entries)),
    check (ranking_hash ~ '^[0-9a-f]{64}$')
);

create index if not exists l4_brief_rankings_by_day
    on l4_brief_rankings (org_id, brief_date_key desc);
