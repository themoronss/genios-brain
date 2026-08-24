-- 0066 — the org's own timezone, so quiet hours can mean anything.
--
-- `AttentionProfile.timezone` defaults to "UTC" and the ONLY configured source was
-- `delivery_preferences.tz_name`, a table with zero rows. So every quiet window was evaluated in
-- UTC. For an India-based founder that makes the 21:00–08:00 politeness window run 02:30–13:30
-- IST — it covers his entire working morning and leaves 22:00–02:30 IST wide open. The exact
-- inversion of what quiet hours are for, applied silently to every tenant.
--
-- Nullable on purpose: "we have not asked this org yet" is a real state and must be
-- distinguishable from a deliberate UTC. deliver/gate.py treats the null as unknown and defers
-- interrupting sends rather than guessing a window.
alter table orgs add column if not exists timezone text;

comment on column orgs.timezone is
  'IANA zone (e.g. Asia/Kolkata). NULL = never asked; quiet hours cannot be evaluated and '
  'interrupting delivery defers rather than assuming UTC.';
