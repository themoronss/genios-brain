-- 0195 · company_brief_lines, company_brief_reviews — the founder's company brief (STEP-07).
--
-- WHY. No model prompt carried any company context — that the founder is raising, that a recognition
-- application is live, that an intro agent works for them, which portal's mail always matters
-- (`speedrun008/YC-II W27/` STEP-07 §1, §8). The brief is that context, and it is the FOUNDER's: a
-- line counts only once it is accepted. The plan's first idea, four existing stores, could not hold
-- it: `user_model_proposals` is per-person persona JSON that nothing writes, canon may never reach the
-- graph, and `org_mission_critical_entities` holds organisation names only (STEP-07 §8.2).
--
-- ONE ROW PER LINE, AND NOTHING IS DELETED. A line is proposed (by the drafter, the weekly review, or
-- the founder), then accepted, rejected, or — once accepted — removed. Its timestamps say when, so the
-- brief in force at any instant can be rebuilt, and every judgment can be traced to the brief it read.
-- `proposed_text` keeps the proposal's own words when the founder edited it before accepting.
--
-- A connector names the address it writes from; a watchlist line names a domain; a key person may
-- name an address. The gate treats each as a known sender (W-07).
--
-- THE RESET KEEPS IT. Like `org_self_identities`, the brief is what the tenant told us about itself —
-- authored, not derived — so `/reset` leaves both tables in place.

create table if not exists company_brief_lines (
    org_id         text        not null references orgs (id) on delete cascade,
    line_id        text        not null,
    section        text        not null,
    text           text        not null,
    address        text,
    domain         text,
    status         text        not null,
    proposed_by    text        not null,
    proposed_text  text,
    evidence       jsonb       not null default '[]'::jsonb,
    proposed_at    timestamptz not null,
    decided_by     text,
    decided_at     timestamptz,
    accepted_at    timestamptz,
    removed_at     timestamptz,

    primary key (org_id, line_id),

    constraint company_brief_lines_section_check
        check (section in ('company', 'goals', 'in_motion', 'people', 'connectors', 'watchlist',
                           'preferences')),
    constraint company_brief_lines_status_check
        check (status in ('proposed', 'accepted', 'rejected', 'removed')),
    constraint company_brief_lines_text_check
        check (length(btrim(text)) between 1 and 200 and position(E'\n' in text) = 0),
    constraint company_brief_lines_address_check
        check (address is null or (address = lower(btrim(address)) and position('@' in address) > 1)),
    constraint company_brief_lines_domain_check
        check (domain is null or (domain = lower(btrim(domain)) and position('.' in domain) > 0
                                  and position('@' in domain) = 0)),
    constraint company_brief_lines_connector_check
        check (section <> 'connectors' or address is not null),
    constraint company_brief_lines_watchlist_check
        check (section <> 'watchlist' or domain is not null),
    constraint company_brief_lines_decided_check
        check ((status = 'proposed') = (decided_at is null)),
    constraint company_brief_lines_accepted_check
        check ((status in ('accepted', 'removed')) = (accepted_at is not null)),
    constraint company_brief_lines_removed_check
        check ((status = 'removed') = (removed_at is not null))
);

create index if not exists company_brief_lines_by_status
    on company_brief_lines (org_id, status);

comment on table company_brief_lines is
  'STEP-07: the founder''s company brief, one row per line — proposed, accepted, rejected or removed, never deleted. Only accepted lines reach a prompt.';

-- The weekly review (STEP-07 §3.6): one claim per tenant per ISO week, so every replica may call it on
-- every heavy tick and a week is reviewed once.
create table if not exists company_brief_reviews (
    org_id       text        not null references orgs (id) on delete cascade,
    week_key     text        not null,
    started_at   timestamptz not null,
    finished_at  timestamptz,
    outcome      text,
    proposed     integer     not null default 0,

    primary key (org_id, week_key),

    constraint company_brief_reviews_proposed_check
        check (proposed >= 0)
);

comment on table company_brief_reviews is
  'STEP-07: the weekly company-brief review — one row per tenant per ISO week; what it proposed.';
