-- WHICH LAPTOP DID THIS SPEND COME FROM.
--
-- NUMBERED 0212, NOT 0191, AND THE REASON IS A MERGE. `speedrun008` — the YC-II W27 programme —
-- is 636 commits ahead of `harsh/mvp` and already carries 0191…0211, starting with
-- `0191_reasoning_fingerprints.sql`. Writing this as 0191 on `harsh/mvp` would have put two
-- different migrations under one number in two branches that are meant to merge, and a
-- migration's number is its identity: `schema_migrations` keys on the filename and a checksum,
-- so the second 0191 to arrive is either skipped as "already applied" or refused. Taking the next
-- number past speedrun008's highest keeps the merge a fast-forward on this file.
--
-- `llm_costs` has carried `seat_id` since 0175, and that answered "which PERSON". It is not
-- enough for screen intelligence, measured on the design-partner org 12 Oct 2026: three devices
-- are registered and ALL THREE sit on one seat (`seat_owner`), because two people sign the
-- desktop app in with the same account. So the spend for a lane whose whole job is to read one
-- person's screen is attributable to a seat that is really two laptops, and the question the
-- owner actually asked — "ye Harsh ke MacBook se aaya ya Rohit ke MacBook se" — has no answer in
-- the ledger at all.
--
-- `device_id` is the answer, and the device is already known at the call site: every screen
-- request arrives on a device token and `moment_routes.Principal` carries `device_id` through
-- the request it authenticates.
--
-- NULL keeps an honest meaning, the same one `seat_id` gave it: work that belongs to no single
-- device. The hourly memory batch and the weekly seat profile are background sweeps over data
-- several devices contributed — inventing a device there would be a lie that reads like a fact.
alter table llm_costs add column if not exists device_id text;

-- The question is always "per org, over a window", then drilled into. Both drills — by seat and
-- by device — hang off that same prefix.
create index if not exists llm_costs_org_device_at on llm_costs (org_id, device_id, created_at);

comment on column llm_costs.device_id is
  'Device whose request caused this call; NULL for background work that serves no single device.';
