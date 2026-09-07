-- BLG-18 · situation importance, STORED — the four columns that make H5 measurable.
--
-- WHY COLUMNS AND NOT A COMPUTATION. Doc 07 step 6 asks that "why is this a 7400?" be answerable
-- from STORED data without recomputation, and doc 09's H5 gate measures the answer as a
-- DISTRIBUTION over a tenant (`scripts/situation_importance_distribution.py`). A number that
-- exists only inside `reason/domain_shadow`'s loop can be neither audited nor measured: the
-- distribution that recorded 193 of 223 signals sharing one score was invisible for exactly that
-- reason — every unit test around it passed while the aggregate was useless.
--
-- WHY ON `context_situations` AND NOT A NEW TABLE. The composition is 1:1 with the situation and
-- is rewritten by the same idempotent sweep that rewrites its confidence vector
-- (`context/situations.refresh_situations`). A side table would need its own lifecycle, its own
-- cascade and its own join, and would let a situation and its importance drift apart — which is
-- the state `importance_source` exists to make impossible one field up.
--
-- NULLABLE, DELIBERATELY. A tenant whose sweep has not run since this migration has NO composed
-- importance, and that is a different fact from "composed, and it came out neutral". The gate
-- reads the null share as unmeasured rather than as a pass, and `situation_bso` falls back to the
-- pre-composition behaviour when the column is null — the same tri-state discipline
-- `coverage_ready` keeps two layers down.
--
-- NO CLOCK IN `importance_components`. The JSONB body is `ComposedImportance.as_record()`, which
-- carries no `eval_time`, no age and no `computed_at`: it reaches
-- `BusinessSituationObject.metadata`, `to_semantic_dict` hashes that into the expertise package's
-- content address, and a per-sweep value there mints a fresh ~238 kB package row per situation per
-- sweep. That mechanism put 995 MB on one tenant and took the project read-only.

alter table context_situations
    -- The composed 0..10000 answer. `importance_components->>'base_bp'` is Layer 1's number
    -- before the L2 modifiers, so the two are always comparable without a second query.
    add column if not exists importance_bp int,
    -- `importance.IMPORTANCE_VERSION`. The composer's weights will move; a stored number whose
    -- version is unknown cannot be re-derived, only re-guessed.
    add column if not exists importance_version text,
    -- `ComposedImportance.as_record()` verbatim: base, corroboration, all six modifier terms
    -- (fired or not, each with its reason and its receipt), the cap, the coverage penalty and the
    -- clamp delta. H5's "populated 100%" row is a count over this column.
    add column if not exists importance_components jsonb,
    -- L2.5.1-U1's SIXTH confidence axis, reported beside `coverage` and deliberately NOT folded
    -- into `confidence_overall`: a five-member cohort does not make the situation less true, it
    -- makes the IMPORTANCE that leaned on it less certain. `situations.COVERAGE_UNKNOWN` is the
    -- not-applicable sentinel, and null here means the sweep predates this column.
    add column if not exists confidence_analytic int;

-- The gate's own read: importance, descending, per tenant. Without it the distribution report is
-- a sequential scan of every situation the tenant has ever had.
create index if not exists context_situations_by_importance
    on context_situations (org_id, importance_bp desc nulls last);
