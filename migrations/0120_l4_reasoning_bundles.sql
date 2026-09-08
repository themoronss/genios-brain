-- Z4 / L4.5 · the voice — where a narrative lives, and where every model consult is receipted.
--
-- TWO TABLES, BECAUSE THEY ANSWER TWO QUESTIONS AND ONE OF THEM HAS NO BUNDLE.
--
--   l4_reasoning_bundles   what a published decision SAYS. One row per (org, decision_hash),
--                          which is doc 11 guard 2 spelled as a primary key: a re-surfaced
--                          decision cannot regenerate, because a second row for the same
--                          decision hash cannot exist.
--   l4_r_site_calls        what every consult DID. R-1, R-3 and R-5 produce no bundle at all,
--                          and a skipped consult produces nothing anywhere — so the outcome
--                          ledger cannot be a column on the bundle row. Doc 01 C5 requires
--                          "every gate outcome recorded: site id, outcome, cost", and an
--                          outcome that is only recorded when the call SUCCEEDED is the half
--                          of the record nobody needs.
--
-- WHY decision_hash IS THE KEY AND NOT run_id. The same situation re-decided on the next sweep
-- produces a new run and the SAME decision hash when nothing about the decision changed; that is
-- loop L-2 in doc 09, and the cache is what makes a re-render free. Keying on run_id would
-- regenerate a narrative every sweep for a decision that had not moved — the "prose drift across
-- a re-run" failure in doc 05 §7, paid for in dollars.
--
-- WHY THE RENDERED TEXT IS STORED BESIDE THE BUNDLE. `numbers_used` substitution happens in code
-- (ReasoningBundle.render), and the whole point of the mechanism is that a customer never sees a
-- digit the engine did not compute. Storing the rendered form means a card surface reads text
-- rather than re-running a substitution it could get wrong, and an auditor can diff the stored
-- prose against the stored numbers without a Python process.
--
-- WHY cost IS MICRO-DOLLARS AND AN INTEGER. A bundle costs about a cent, so cents cannot express
-- it and a float re-rounds differently on every worker. Micro-dollars are the same integer
-- discipline as basis points, one decimal place further out.

create table if not exists l4_reasoning_bundles (
    org_id         text        not null references orgs (id) on delete cascade,

    -- The CONTRACT decision hash (ReasoningDecision.semantic_hash), which is also what
    -- `signals.reasoning_decision_hash` carries for a compiled-lane card. The cache key.
    decision_hash  text        not null,

    -- The decision this narrative belongs to, and the action it committed to. Both are stored
    -- rather than derived so V-3 can be re-checked on the way OUT of the database as well as on
    -- the way in: a bundle read back for a decision whose action has moved is refused at the
    -- read, not rendered onto a card.
    decision_id    text        not null,
    action_id      text        not null,

    -- The run the narration was built from. Nullable: a decision can be narrated from a replay
    -- whose run row has since been purged by the 720h context TTL, and losing the pointer must
    -- not lose the prose.
    run_id         text,

    -- THE OTHER DECISION HASH, and the two are genuinely different numbers.
    --
    -- `decision_hash` above is the CONTRACT's (`ReasoningDecision.semantic_hash`) and it is the
    -- cache key, because it is the identity of the decision itself: the same situation re-decided
    -- next sweep produces a new run and the same contract hash, which is what makes a re-surfaced
    -- decision free. `reasoning_run_outputs.decision_hash` — what `signals.reasoning_decision_hash`
    -- points at — is the STORE's, hashed over its own composed material, and it changes with the
    -- run. A card surface joins on that one.
    --
    -- Keying on the store's hash instead would regenerate a narrative every sweep for a decision
    -- that had not moved; joining on the contract's would find no card at all. So both are carried,
    -- and the pointer is REFRESHED on a re-publication while the prose is not (see store.put).
    store_decision_hash text,

    bundle         jsonb       not null,
    bundle_hash    text        not null,

    -- 'llm:<model>@<version>' or 'template_fallback'. K4 measures the FALLBACK RATE off this
    -- column, which is why the vocabulary is closed in code (contracts.reasoning.require_generation)
    -- rather than left as free text here.
    generation     text        not null,

    -- What a card shows: every placeholder already replaced by its computed value.
    rendered       jsonb       not null,

    -- The V-1..V-7 outcomes, IN ORDER, for this bundle's accepted generation. Doc 05 §4 says
    -- every outcome is recorded on the trace; this is that record.
    gauntlet       jsonb       not null default '[]'::jsonb,

    -- How many generations were spent before this bundle existed. 0 for a template fallback that
    -- never called a model, 1 for a first-pass accept, 2 for an accept after the single retry.
    attempts       integer     not null default 0,
    cost_micro_usd bigint      not null default 0,

    created_at     timestamptz not null default now(),

    primary key (org_id, decision_hash)
);

-- "Which decisions has this tenant narrated today, and how many fell back" — K4's two rates, and
-- the sweep's own "what still needs a bundle" read.
create index if not exists l4_reasoning_bundles_org_created
    on l4_reasoning_bundles (org_id, created_at desc);

-- The card surface's join: signals.reasoning_decision_hash -> this narrative.
create index if not exists l4_reasoning_bundles_store_hash
    on l4_reasoning_bundles (org_id, store_decision_hash) where store_decision_hash is not null;

create table if not exists l4_r_site_calls (
    id             bigserial   primary key,
    org_id         text        not null references orgs (id) on delete cascade,

    -- 'R-1'..'R-5'. Free text with the vocabulary enforced in reason/bundle/sites.py, for the
    -- reason 0116 gives about features: a sixth site is a wave, not a schema event.
    site           text        not null,

    -- ran | cached | skipped_not_activated | skipped_precondition | skipped_budget |
    -- skipped_no_client | failed_generation | failed_validation | force_failed.
    -- A SKIP IS A ROW. That is the whole reason this table exists rather than a counter: "the
    -- narrative was quiet yesterday" and "the narrative was refused by the budget yesterday" are
    -- different facts and a rate over successful calls cannot tell them apart.
    outcome        text        not null,
    tier           text        not null,

    -- What the consult was keyed on (decision hash / fact digest). Not unique: a cache MISS and
    -- the RAN row that follows it are two facts about the same key.
    cache_key      text        not null,
    model          text,

    input_tokens   integer     not null default 0,
    output_tokens  integer     not null default 0,
    cost_micro_usd bigint      not null default 0,
    attempts       integer     not null default 0,

    -- Why it ended the way it did — the gauntlet checks that failed, the precondition that was
    -- absent, the budget that was spent.
    reason_codes   jsonb       not null default '[]'::jsonb,

    created_at     timestamptz not null default now()
);

-- The per-org daily budget read (doc 11 guard 1) runs on every consult, so it gets the index the
-- gate's hot path needs: today's rows for one tenant.
create index if not exists l4_r_site_calls_org_created
    on l4_r_site_calls (org_id, created_at desc);

comment on table l4_reasoning_bundles is
  'Layer 4.5 · the customer-facing reasoning narrative for ONE published decision, keyed on the decision hash so a re-surfaced decision never regenerates (11-Cost-Model guard 2). Written only by reason/bundle; the decision it narrates is fixed before this row exists.';
comment on column l4_reasoning_bundles.store_decision_hash is
  'reasoning_run_outputs.decision_hash for the run this was narrated from — what signals.reasoning_decision_hash points at, and NOT the same number as decision_hash (which is the contract hash and the cache key). Refreshed when the same decision is re-published; the prose is not.';
comment on column l4_reasoning_bundles.generation is
  'llm:<model>@<version> or template_fallback. K4 measures the fallback rate on this column; the vocabulary is closed in contracts.reasoning.require_generation.';
comment on table l4_r_site_calls is
  'Every consult the Layer 4 LLM policy gate made or REFUSED — one row per outcome including skips, per 01-Group-L4.1 C5. The per-org daily narrative budget is summed from cost_micro_usd here.';
