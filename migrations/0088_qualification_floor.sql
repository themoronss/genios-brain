-- L1.6.8-U1 (ALG-18) · the qualification FLOOR and its ledger. Three tables, one idea:
-- **a drop is a decision, and a decision that left no record is indistinguishable from a bug.**
--
-- THE DEFECT THIS CLOSES. Doc 06 states it outright — *"there is no floor at all (grep for a
-- qualification threshold in gate/relevance.py returns nothing)"* — so every signal ESQE
-- detected travelled onward at equal standing, and the ~92% that is not business-relevant was
-- paid for at every layer above. The floor is the cut. What makes the cut safe to make is not
-- the threshold, it is these tables: *"why did GeniOS never see X?"* has to have an answer, and
-- the answer is a row carrying the computed importance, every component that produced it, and a
-- reference to the payload the signal was read from.
--
-- WHY THE FLOOR IS A TABLE AND NOT A CONSTANT. Doc 06's failure-mode list ends on it: *"floor
-- tuning is a per-tenant setting with an owner and a changelog, never a global constant edit."*
-- A startup's floor is not an enterprise's — a five-person company's $8K renewal outranks a
-- bank's — and a module constant hands both the same cut-off and no way to move it without a
-- deploy. `owner` is who answers for the number and `qualification_floor_changes` is why it is
-- what it is; an unattributed threshold that quietly halved a tenant's signal volume is the
-- incident this column exists to prevent.
--
-- ORG CASCADE on all three: `tests/test_account_erasure.py` replays every migration statically
-- and fails any table with an `org_id` that cannot be erased with its tenant. The drop ledger
-- holds the tenant's own subject lines and amounts in `components`/`payload_ref`, so this is not
-- a formality. All three are also listed in `api/account_routes._ORG_SCOPED_TABLES`, which is
-- what makes /reset erase them as well as account deletion.

create table if not exists org_qualification_floors (
    org_id      text primary key references orgs (id) on delete cascade,
    floor_bp    integer not null,
    -- WHO answers for this number. Never null: a floor with no owner is the global constant
    -- again, wearing a row.
    owner       text not null,
    note        text not null default '',
    updated_at  timestamptz not null default now(),
    constraint org_qualification_floors_bp_range check (floor_bp between 0 and 10000)
);

-- Append-only. One row per change, including the first one; the current value lives above and
-- the reason it moved lives here, because "the floor was raised and misses started" is only
-- diagnosable if the raise left a date and a name behind.
create table if not exists qualification_floor_changes (
    change_id   text primary key,
    org_id      text not null references orgs (id) on delete cascade,
    from_bp     integer,                      -- null = the tenant had no floor row before
    to_bp       integer not null,
    changed_by  text not null,
    reason      text not null default '',
    changed_at  timestamptz not null default now()
);

create index if not exists qualification_floor_changes_by_org
    on qualification_floor_changes (org_id, changed_at desc);

-- THE LEDGER. One row per signal the floor refused.
--
-- `components` is the whole `importance_components` map from L1.6.7 — the five weighted terms,
-- the authority multiplier and the baseline used — stored rather than recomputed, because a
-- weight change next month must not silently re-explain a drop that was made under the old
-- ones. `payload_ref` is `prepared_content:<id>` or `raw_payload:<event_id>`, the same
-- `prefix:id` provenance form ALG-14 matches on, so the dropped signal is RECONSTRUCTABLE and
-- not merely regrettable.
--
-- `retain_until` is doc 06's "payload retained 90d" written as a date on the row that promises
-- it. The ledger's writer extends `raw_payloads.expires_at` to at least this instant in the
-- same transaction — a ledger row pointing at a body the 30-day emitted TTL already deleted
-- would be a receipt for a payload nobody can fetch.
create table if not exists qualification_drops (
    drop_id            text primary key,
    org_id             text not null references orgs (id) on delete cascade,
    signal_id          text not null,
    event_id           text not null,
    signal_type        text not null,
    predicate          text not null,
    subject_key        text not null,
    importance_bp      integer not null,
    importance_version text not null,
    floor_bp           integer not null,
    components         jsonb not null default '{}'::jsonb,
    payload_ref        text,
    evaluated_at       timestamptz not null,
    retain_until       timestamptz not null,
    constraint qualification_drops_below_floor check (importance_bp < floor_bp)
);

-- "What did this tenant not see, most recently first" is the whole read.
create index if not exists qualification_drops_by_org on qualification_drops (org_id, evaluated_at desc);
-- "Why did this event produce nothing" — the support question, answered from the event id a
-- founder can actually name.
create index if not exists qualification_drops_by_event on qualification_drops (org_id, event_id);

comment on table qualification_drops is
  'L1.6.8 (ALG-18) drop ledger: one row per signal refused by the tenant floor, carrying the importance components and a payload ref so the drop is reconstructable. Written by capture/esqe/qualification.py; erased with the tenant (org cascade + api/account_routes._ORG_SCOPED_TABLES).';
comment on column qualification_drops.drop_id is
  'sha256 over org_id : signal_id : floor_bp : importance_bp. Content-addressed so a replayed sweep upserts its own row instead of appending a second copy of one refusal; evaluated_at is deliberately NOT in the digest.';
comment on column qualification_drops.components is
  'The importance_components map exactly as L1.6.7 produced it. Stored, never recomputed: a weight change must not re-explain an old drop.';
comment on table org_qualification_floors is
  'L1.6.8 per-tenant qualification floor in basis points. Default 2500 when no row exists — see capture/esqe/qualification.DEFAULT_FLOOR_BP.';
