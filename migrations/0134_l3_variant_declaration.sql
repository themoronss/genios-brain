-- L3.0-U3 · which authored BUSINESS-MODEL / OFFERING variants a tenant's domain runs under.
--
-- THE LANE THAT WAS NEVER SELECTED. The corpus holds 127 variant documents — model.yaml,
-- offering.yaml, vertical.yaml — loaded, integrity-checked and pinned by a test, and
-- `packs/compiler/knowledge_retriever._resolve_variants` chooses among them on metadata keys
-- (`model_ids`, `offering_ids`, …) that NO ENGINE MODULE, ROUTE, SCRIPT OR MIGRATION WRITES.
-- So the AI agency on `customer_support` gets the canonical corpus byte-identical to the
-- pure-SaaS tenant next door, and the card reasons about a shared artefact they do not have.
--
-- ONE COLUMN HERE, NOT A NEW TABLE. `l3_activation` is the only per-(org_id, domain) table in
-- the engine, already has an admin writer, an audit trail, a stamped-off reversal and the J5
-- report. `'[]'` means "declared nothing", which every existing row reads as on day one.
--
-- WHY THE DECLARATION MUST STAY OFF THE SITUATION UNLESS IT IS NON-EMPTY. The compiler reads
-- `contracts/situation.BusinessSituationObject`, whose `content_key()` hashes the WHOLE
-- metadata dict. A key written empty on every situation would re-mint `semantic_hash` ->
-- `expertise_id` -> a fresh ~238 kB `expertise_packages` row PER SITUATION — the exact
-- mechanism of the 995 MB incident this codebase documents in four places. The reader below
-- writes the key only when a tenant has declared something.

alter table l3_activation
    add column if not exists variant_ids jsonb not null default '[]'::jsonb;
