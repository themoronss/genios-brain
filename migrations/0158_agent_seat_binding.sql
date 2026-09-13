-- 0158 · AGENT → SEAT BINDING (SCREEN_INTEL_P6 §3.6, §4 group B).
--
-- An agent key that reads through MCP reads AS A SEAT: every fact is filtered to what that seat
-- may see (P2 fact visibility), its moments are that seat's moments, its cards that seat's reach.
-- NULL = unbound: the key authenticates but every seat tool answers SEAT_REQUIRED.
--
-- No foreign key: org_seats is keyed (org_id, seat_id) and agent_registry.org_id is NOT NULL, so a
-- composite ON DELETE SET NULL would null the org too. The binding is validated when it is set
-- (PATCH /v1/agents/{id}/seat) and re-checked against an ACTIVE seat on every MCP request, so a
-- deactivated seat's agent stops reading at once.
alter table agent_registry add column if not exists seat_id text;

create index if not exists agent_registry_by_seat
    on agent_registry (org_id, seat_id) where seat_id is not null;
