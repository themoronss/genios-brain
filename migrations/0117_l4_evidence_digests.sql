-- Z2 / Group L4.3 · the permanent evidence digest, and the historic id map.
--
-- WHY THIS EXISTS. `reasoning_context_payloads` carries a 720h TTL, which is correct: a bounded
-- context payload holds derived values about real people and it should not live forever. But
-- after the purge a stored decision can prove WHICH evidence it used and no longer WHAT that
-- evidence said — so a year-old card cannot be re-justified, which is the entire point of the
-- evidence layer (doc 03, S3). The fix doc 03 prints is two lifetimes, not one:
--
--     { evidence_id, value_digest, unit_ref, rendered_text[:120], observed_at_key }   forever
--     { full payload }                                                               720h
--
-- WHAT IS NOT CHANGING. `reason/store.py` is content-addressed, hash-verified and FAILS CLOSED
-- when a payload does not match its hash. None of that is weakened here and the digest is
-- explicitly NOT a fallback for a failed payload verification: while the payload lives, the
-- payload is what is verified, and the digest rows are re-derived from it and compared. The
-- digest lane engages only when the payload is genuinely ABSENT, and when it does the replay
-- LABELS ITSELF `digest_verified` instead of quietly returning less.
--
-- WHY THE DIGEST ITSELF IS HASH-ANCHORED. A digest bolted on carelessly is a new way to accept
-- a bad payload: verify the rows against nothing, and a tampered row is indistinguishable from a
-- real one exactly when the payload is gone and there is nothing to check it against.
-- `evidence_digest_hash` below is the content address of the whole SET, and it is bound to
-- `payload_hash` — which already sits inside `context_hash`, which is inside the snapshot id. So
-- a digest set cannot be transplanted onto another snapshot, and a single edited row fails the
-- set hash.

alter table reasoning_context_snapshots
    add column if not exists evidence_digest_hash text;

-- Nullable on purpose. Every snapshot written before this migration has no digest set, and
-- back-filling one at migration time would mean minting digests inside a schema change for
-- payloads that may already have expired. They are minted instead on the live paths that touch
-- those rows: `put_context_snapshot` for new snapshots, and `purge_expired_context_payloads`
-- for historic ones — which is the strongest possible placement, because it means no payload can
-- ever be deleted without leaving its digest behind.
comment on column reasoning_context_snapshots.evidence_digest_hash is
  'Content address of this snapshot''s permanent evidence digest SET, bound to payload_hash (reason/evidence.digest_set_hash). Null only for snapshots written before migration 0117 whose payload has not yet been swept.';

create table if not exists reasoning_evidence_digests (
    -- BOTH cascades, deliberately. The composite FK below erases these rows with their snapshot;
    -- this direct one erases them with the ACCOUNT, and `tests/test_account_erasure.py` proves
    -- the path rather than accepting a name on an allowlist. This table is the one place where a
    -- fact's rendered text outlives its payload, so "does account deletion definitely reach it"
    -- must be answerable from the schema alone.
    org_id              text not null references orgs (id) on delete cascade,
    context_snapshot_id text not null,

    -- The single canonical identity from `reason/evidence.evidence_id` (DLG-11). Historic rows
    -- keep whatever id their lane minted; `reasoning_evidence_id_map` below maps those forward
    -- rather than rewriting them, because rewriting an id inside an immutable, hash-verified
    -- payload would invalidate every hash that payload participates in.
    evidence_id         text not null,

    field               text not null,
    context_scope       text not null default 'root'
        check (context_scope in ('root', 'neighbor')),

    -- The permanent proof. `semantic_hash` of the evidence value, under the same canonical
    -- encoder every other hash in Layer 4 uses.
    value_digest        text not null check (value_digest ~ '^[0-9a-f]{64}$'),

    -- Doc 03's 120 characters: enough to re-read the claim in a card, short enough that this
    -- table stays small and carries no bulk PII. Bounded in code AND here, because the size
    -- argument is also the privacy argument and one of the two must not be able to drift.
    rendered_text       text not null check (char_length(rendered_text) <= 120),

    observed_at_key     text not null,
    source_ref_id       text,
    independence_group  text,

    -- WHICH UNITS OBSERVED THIS (S1). Stamped by `persist_complete` from the run's
    -- hash-verified reasoner results, NOT written at snapshot time: a snapshot is built before
    -- any unit has run, so a unit_ref written then would be a guess about the future. It is
    -- deliberately outside `digest_hash` — one content-addressed snapshot can serve several
    -- runs, and a per-run column inside a per-snapshot content address would make the set hash
    -- move for a reason that is not tampering. It stays verifiable anyway: it is re-derivable
    -- from `reasoning_reasoner_results`, which the replay verifier already hashes.
    unit_refs           jsonb not null default '[]'::jsonb
        check (jsonb_typeof(unit_refs) = 'array'),

    -- The content address of this row's immutable half.
    digest_hash         text not null check (digest_hash ~ '^[0-9a-f]{64}$'),

    created_at          timestamptz not null default now(),

    primary key (org_id, context_snapshot_id, evidence_id),
    foreign key (org_id, context_snapshot_id)
        references reasoning_context_snapshots (org_id, context_snapshot_id)
        on delete cascade
);

-- "Everywhere this fact was used" — the cross-lane read that three id seeds made impossible.
create index if not exists reasoning_evidence_digests_by_evidence
    on reasoning_evidence_digests (org_id, evidence_id);

comment on table reasoning_evidence_digests is
  'Layer 4 permanent evidence digest (doc 03 S3). One short row per evidence id per context snapshot; outlives the 720h payload TTL so a year-old decision can still be re-justified. Written in the same transaction as the payload it describes, and in the same transaction as the purge that removes it.';

-- The historic id map. Three lanes minted three ids for one fact; `reason/evidence.evidence_id`
-- now mints one. The old ids are NOT rewritten — they are embedded in immutable, hash-verified
-- payloads and rewriting one would invalidate every hash that payload feeds. They are mapped.
create table if not exists reasoning_evidence_id_map (
    org_id              text not null references orgs (id) on delete cascade,
    legacy_evidence_id  text not null,
    evidence_id         text not null,
    context_snapshot_id text not null,

    -- Which historic seed produced the legacy id, when it can be told. 'historic' when the row
    -- was recovered from a stored payload and the originating lane cannot be proven from it —
    -- an honest label beats a guessed one in a table whose whole job is provenance.
    lane                text not null default 'historic',

    mapped_at           timestamptz not null default now(),
    primary key (org_id, legacy_evidence_id)
);

create index if not exists reasoning_evidence_id_map_forward
    on reasoning_evidence_id_map (org_id, evidence_id);

comment on table reasoning_evidence_id_map is
  'Maps a pre-0117 lane-specific evidence id to the single canonical id from reason/evidence.evidence_id (DLG-11, doc 03 S2). Historic decisions replay against this mapping rather than against a silently different id.';
