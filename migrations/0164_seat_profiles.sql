-- 0164 · SEAT PROFILES + FOLLOW-UP SNOOZE (P10 nudges).
--
-- `seat_profiles`  the weekly manager profile (reason/moments/seat_profile.py): ≤ 5 short plain
--                  lines the one screen judge can read — the manager's likely role, key people,
--                  usual work hours, what to ignore. Built from the seat's OWN data only (its
--                  screen follow-ups, thread verdicts and "not useful" notes; `facts` keeps those
--                  inputs) by one model call at most once a week per seat, lazily from the
--                  screen-insight request path (never a periodic task). Private to the seat.
create table if not exists seat_profiles (
    org_id    text not null references orgs(id) on delete cascade,
    seat_id   text not null,
    profile   text,
    facts     jsonb not null default '{}',
    built_at  timestamptz not null default now(),
    primary key (org_id, seat_id)
);

-- `snoozed_at`  set when the person moved the nudge (POST /v1/followups/{id}/snooze): a later
--               sighting of the same topic refreshes the note / due but keeps the snoozed
--               `nudge_at` instead of recomputing it.
alter table screen_followups add column if not exists snoozed_at timestamptz;
