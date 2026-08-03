-- GeniOS Engine · L3 · at-most-one OPEN signal per (org, rule, subject). Closes the dup-signal
-- race: a webhook-triggered run and the daily sweep could both pass the cooldown check and both
-- INSERT, producing two open signals + two cards for the same deal. A partial UNIQUE index makes
-- the second INSERT a no-op (ON CONFLICT DO NOTHING) — deterministic, no advisory lock needed.
create unique index if not exists signals_one_open
    on signals (org_id, rule_id, subject_node_id)
    where status = 'open';
