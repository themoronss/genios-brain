-- GeniOS Engine · L6 · Feedback / Calibration (Agent F). labels → counters → nudges → LVL3.
-- Arithmetic, not gradients. Every guard firing + every nudge is an ordinary row (the moat is a
-- table). F3/F4 are the only writers and both write bounded config through the L4 merge engine.

-- F5 auto-mute warden — a rule at <25% precision (with ≥12 impressions) trains the user to ignore
-- ALL cards, so it is muted per (org, rule). Armed from day one (protection outranks optimization).
create table if not exists rule_mutes (
    org_id     text not null,
    rule_id    text not null,
    active     boolean not null default true,
    reason     text,
    precision  numeric(4,3),
    impressions int,
    muted_at   timestamptz not null default now(),
    primary key (org_id, rule_id)
);

-- F3/F4 audit ledger — every threshold nudge, its before/after, cumulative offset and the
-- precision/impressions that justified it. A user who pressed Wrong can find the nudge it moved.
create table if not exists calibration_nudges (
    id          text primary key,
    org_id      text not null,
    rule_id     text not null,
    param       text not null,               -- e.g. 'gate.s_min'
    before_val  numeric,
    after_val   numeric,
    offset_cumulative numeric,
    direction   text not null,               -- loosen | tighten | mute
    precision   numeric(4,3),
    impressions int,
    created_at  timestamptz not null default now()
);
create index if not exists calibration_nudges_by_org on calibration_nudges (org_id, rule_id);

-- F8 MACV ledger — the North Star. caught→acted→resolved; distinct-deal SUM + non-deal COUNT
-- (anti-inflation double-count rule). The number the customer can verify.
create table if not exists macv_ledger (
    id            text primary key,
    org_id        text not null,
    period        text not null,             -- YYYY-MM (tenant-local, passed in — never wall-clocked)
    deal_id       text,
    amount        numeric,
    resolved_signal_id text,
    created_at    timestamptz not null default now()
);
create index if not exists macv_ledger_by_org on macv_ledger (org_id, period);
