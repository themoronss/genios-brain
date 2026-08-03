-- GeniOS Engine · L5 · Delivery (Agent E). card = f(signal, play, template): a deterministic
-- composition rendered by exactly one temp-0 call, behind an invention validator. One card per
-- signal, one owner, one push. Every state transition is timestamped — the round trip L6 eats.

-- card.v1 — everything a surface needs, nothing it does not (§5.10). 1:1 with a signal.
create table if not exists cards (
    card_id           text primary key,
    signal_id         text not null,                 -- provenance; card carries presentation
    org_id            text not null,
    assignee          text,                          -- resolved by E3; null = 'unrouted' admin queue
    domain            text not null default 'sales',
    level             text not null,                 -- descriptive|diagnostic|predictive|prescriptive
    urgency_band      text not null,                 -- standard|high|critical (E2, from pack cuts)
    headline          text not null,                 -- ≤60, validated at render (Law 3)
    situation         text not null,                 -- ≤140, validated at render
    score             int  not null,                 -- S (mirror of signal.score)
    score_block       jsonb not null default '{}',   -- {S,U,I,R,C,inputs} — travels whole
    actions           jsonb not null default '[]',   -- the 4 buttons + play_id/artifact_ready
    why               jsonb not null default '[]',   -- fact refs + spans, ≥2 inline (Law 2)
    context_tags      text[] not null default '{}',  -- app:* url_domain:* tool paths — on-device matcher only
    artifact          jsonb,                          -- the pre-rendered draft (Run Play opens from cache)
    render_mode       text not null default 'llm',   -- llm | raw_slot (invention/length fallback)
    config_snapshot_id text,                          -- the L4 snapshot the source signal scored under
    template_version  text,                           -- pack template id+version used (Law 1 provenance)
    state             text not null default 'built',  -- built|queued|surfaced|snoozed|claimed|acted|resolved|expired
    snooze_until      timestamptz,
    created_at        timestamptz not null default now(),
    expires_at        timestamptz not null,           -- +7d; expired = delivered-not-resolved (ignore rate)
    resolved_at       timestamptz
);
create unique index if not exists cards_one_per_signal on cards (signal_id);
create index if not exists cards_queue on cards (org_id, assignee, state);

-- Queue state machine — every transition, its cause, its timestamp (§5.12). The fixture list
-- for the round-trip acceptance test; L6 reads card.surfaced.cause to prove context lift.
create table if not exists card_events (
    id          text primary key,
    card_id     text not null,
    org_id      text not null,
    kind        text not null,      -- card.created|card.surfaced|human.card_action|ui.requeued|card.snooze_wake|agent.claim|agent.result|human.override|success.detected|window.lapsed|notification.suppressed
    cause       text,               -- rotation|push|context_match|notification_tap|dashboard | button type | reason
    actor_id    text,               -- human seat, agent_id, or 'system'
    detail      jsonb not null default '{}',
    occurred_at timestamptz not null default now()
);
create index if not exists card_events_by_card on card_events (card_id, occurred_at);

-- E9 agent claims — a 15-minute exclusive lock over a signal's card. First writer wins (409
-- on double claim); execution stays on the customer's side, GeniOS only hands over the artifact.
create table if not exists agent_claims (
    signal_id   text primary key,
    card_id     text not null,
    org_id      text not null,
    agent_id    text not null,
    claimed_at  timestamptz not null default now(),
    expires_at  timestamptz not null,               -- claimed_at + 15 min
    released_at timestamptz,
    result      text,                                -- done|failed|null(open)
    result_detail jsonb
);

-- Tenant seats — the active human owners a card can route to (§5.13). "Internal actor with an
-- active seat" (resolution rule 2) is verifiable only against this table; everyone else falls
-- through to the admin queue. Seeded per tenant; role drives who sees all queues vs their own.
create table if not exists org_seats (
    org_id     text not null,
    seat_id    text not null,                       -- stable user id
    email      text,                                -- for actor→seat matching
    role       text not null default 'member',      -- admin | member
    active     boolean not null default true,
    created_at timestamptz not null default now(),
    primary key (org_id, seat_id)
);
create index if not exists org_seats_by_email on org_seats (org_id, lower(email));

-- Per-agent metering — every read/claim/result increments the monthly counter the $15 unit
-- bills (§5.16), same counter family as the L1 write path. One billing view.
create table if not exists agent_metering (
    org_id      text not null,
    agent_id    text not null,
    period      text not null,                       -- YYYY-MM (tenant-local), passed in, never wall-clocked here
    reads       int  not null default 0,
    claims      int  not null default 0,
    results     int  not null default 0,
    primary key (org_id, agent_id, period)
);
