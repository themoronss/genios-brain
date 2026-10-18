-- 0230 · morning_briefs, morning_brief_marks — one brief per seat per local day, and your mark on a line
-- (STEP-15, the morning brief; §8.4 items 4-5, tree `yc2_w27_s15` M44.C1.L-contract.V1.U02).
--
-- WHY. Four morning surfaces existed and none read a file (`03` s15-F14); nothing kept a brief, so "what
-- changed since yesterday's" had nothing to compare with (STEP-15 §8.2, 3.1). A brief is composed once for a
-- seat's local day, at 08:00 in the org's timezone (`06` D9), on whichever tick comes first — and served at
-- `GET /v1/executive/morning`, which composes on read if no tick did.
--
-- THE ROW IS THE CLAIM. `(org_id, seat_id, local_date)` is the key: two replicas composing at once write one
-- row, and the second finds the first's (`insert … on conflict do nothing`, then read). It is also the
-- ARTIFACT: the lines with their sections, words, sources and the check's verdicts; the whole brief as
-- `contracts/morning_brief.Brief.as_mapping` (read back equal); the digest of the day's material; how it was
-- written — the template, written (T1, checked line by line) or escalated (T2, once) — and why; the model, tier
-- and cost; when.
--
-- THE TEMPLATE SPENDS NOTHING AND NAMES NO MODEL, and no brief is written on T3 (`06` s15-D1: never Opus).
--
-- A MARK — useful, or not useful with your words — is one per line per person, a later mark replacing it
-- (the latest standing). Recorded only: STEP-16 turns marks into proposals you accept. A mark belongs to a kept
-- brief: deleting the brief takes its marks.
--
-- Additive; both are erased by `/reset` (`api/account_routes._ORG_SCOPED_TABLES`, marks first) and cascade
-- with the tenant.

create table if not exists morning_briefs (
    org_id           text        not null references orgs (id) on delete cascade,
    seat_id          text        not null,
    local_date       date        not null,
    timezone         text        not null,
    as_of            timestamptz not null,
    composed_at      timestamptz not null default now(),
    one_line         text        not null,
    lines            jsonb       not null,
    brief            jsonb       not null,
    material_digest  text        not null,
    written_by       text        not null,
    why              text        not null,
    model            text,
    tier             text,
    cost_micro_usd   bigint      not null default 0,

    primary key (org_id, seat_id, local_date),

    constraint morning_briefs_written_by_check
        check (written_by in ('template', 'written', 'escalated')),
    constraint morning_briefs_tier_check
        check (tier is null or tier in ('T1', 'T2')),
    constraint morning_briefs_template_spends_nothing_check
        check (written_by <> 'template' or (cost_micro_usd = 0 and model is null and tier is null)),
    constraint morning_briefs_cost_check
        check (cost_micro_usd >= 0),
    constraint morning_briefs_words_check
        check (btrim(one_line) <> '' and btrim(why) <> '' and jsonb_typeof(lines) = 'array')
);

-- "The seat's last brief before a day" — what changed since it.
create index if not exists morning_briefs_by_seat
    on morning_briefs (org_id, seat_id, local_date desc);

create table if not exists morning_brief_marks (
    org_id      text        not null references orgs (id) on delete cascade,
    line_id     text        not null,
    marked_by   text        not null,
    seat_id     text        not null,
    local_date  date        not null,
    mark        text        not null,
    words       text,
    marked_at   timestamptz not null,

    primary key (org_id, line_id, marked_by),

    foreign key (org_id, seat_id, local_date)
        references morning_briefs (org_id, seat_id, local_date) on delete cascade,

    constraint morning_brief_marks_mark_check
        check (mark in ('useful', 'not_useful')),
    -- "not useful, because ___": the words say why, and only a not-useful mark has them.
    constraint morning_brief_marks_words_check
        check ((mark = 'not_useful') = (coalesce(btrim(words), '') <> ''))
);

create index if not exists morning_brief_marks_by_brief
    on morning_brief_marks (org_id, seat_id, local_date);

comment on table morning_briefs is
  'STEP-15: one morning brief per seat per local day — the claim (a second composer finds it) and the artifact: lines with sources and verdicts, the brief as kept, the material digest, how it was written and why, model, tier, cost.';
comment on table morning_brief_marks is
  'STEP-15: your mark on a brief line — useful, or not useful with your words — one per line per person, the latest standing. Recorded only; STEP-16 learns from it.';
