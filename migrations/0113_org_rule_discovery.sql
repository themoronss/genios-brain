-- L3.2-U1 · N-3 — the Organization-brain discovery receipt, and the tenant's declared locale.
--
-- WHY A RECEIPT TABLE AT ALL. N-3's proposals are content-addressed, so re-reading a document
-- cannot duplicate a rule — `publisher.persist` answers 'unchanged' and the run is a no-op. What
-- content addressing CANNOT record is the document that produced NOTHING: a policy the model read
-- and found no binding rule in, a wiki page refused at the kind gate, an extraction that failed.
-- Without a row those three are indistinguishable from a document nobody ever looked at, so the
-- unit would re-pay a T2 extraction for every unreadable file on every canon write, forever, and
-- nobody could answer "did we read this policy?".
--
-- `version_key` IS PART OF THE PRIMARY KEY, and that is the supersession contract. L1 mints the
-- dedup key from (source_object_id, content_version), so EDITING a policy and re-submitting it
-- produces a new key — the document is read again, its rules re-proposed, and the old brain entry
-- superseded by version+1. Re-submitting UNCHANGED content produces the same key and is skipped.
-- Keying on event_id alone would make an edited policy permanently unreadable; keying on nothing
-- would make an unchanged one permanently re-read.
--
-- `counters` IS THE REFUSAL LEDGER'S SUMMARY. Every individual refusal is also a row in
-- `learning_input_rejections` (migration 0046) with its named reason. This column is the
-- arithmetic for one document — candidates in, rules out, refusals by reason — so the J4 gate's
-- "every refusal named and counted" is answerable with one read instead of an aggregation.
--
-- ORG CASCADE. `tests/test_account_erasure.py` replays every migration and fails any table
-- carrying an `org_id` that cannot be erased with its tenant. This is a record of which of the
-- tenant's own documents were read, so it dies with the tenant; the table is also named in
-- `api/account_routes._ORG_SCOPED_TABLES`, which is what makes /reset clear it too. That loop
-- runs with no try/except, so a name missing from it leaks silently.

create table if not exists org_rule_discovery_runs (
    org_id       text not null references orgs (id) on delete cascade,
    event_id     text not null,                 -- the canon SourceEvent that was read
    version_key  text not null,                 -- L1's dedup key = (source_object_id, content hash)
    kind         text not null,                 -- the normalised internal_kind
    outcome      text not null,                 -- ran | kind_not_rule_bearing | extractor_failed
    counters     jsonb not null default '{}'::jsonb,
    ran_at       timestamptz not null default now(),
    primary key (org_id, event_id, version_key)
);

-- The sweep's only read: "rule-bearing canon events for this tenant with no receipt at their
-- current version". The anti-join is on (org_id, event_id, version_key), which the primary key
-- already serves; this index is for the "what has this tenant had read, most recent first"
-- console read, which has no other path.
create index if not exists org_rule_discovery_runs_by_time
    on org_rule_discovery_runs (org_id, ran_at desc);

-- -------------------------------------------------------------------------------------------
-- THE TENANT'S DECLARED LOCALE. Same shape and same reasoning as `orgs.timezone` (migration
-- 0066): declared by the company, never inferred.
--
-- ALG-10 (`capture/validate/money.py`) needs it and refuses without it. "$50,000" is USD, CAD,
-- AUD, NZD, SGD or HKD, and the parser returns AMBIGUOUS_SEPARATOR rather than picking the
-- majority currency — which is correct, because the alternative is an approval threshold
-- denominated in a currency nobody chose, and that threshold decides who has to sign. Until a
-- tenant declares one, a dollar threshold is refused with a COUNTED `threshold_unparseable`,
-- which is visible in `learning_input_rejections`; an unambiguous symbol (₹, €, £) parses with
-- no locale at all, so the Indian and European corpora are unaffected.
alter table orgs add column if not exists locale text;
comment on column orgs.locale is
  'The tenant''s declared BCP-47 locale (en-US, en-IN, de-DE). Disambiguates shared currency symbols for ALG-10. NULL means undeclared — never guessed, and an ambiguous amount is refused rather than assumed.';
