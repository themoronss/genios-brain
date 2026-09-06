-- L-4 · the drain's CONVERGENCE LEDGER (doc 13, "Loops, Convergence and Invalidation").
--
-- WHAT LOOP THIS IS ABOUT. Layer 2 is the only layer with feedback inside itself: a new event
-- joins a situation -> the member set changes -> importance is recomposed -> lifecycle is
-- re-derived -> an observation is emitted -> observations are an INPUT to correlation -> back to
-- the top. Doc 13 names it L-4 and its hazard as NON-TERMINATION, with the property that makes it
-- expensive: it does not obviously not terminate. It looks like a slow sweep, then a slower one.
--
-- WHY A TABLE AND NOT AN IN-PROCESS COUNTER. `context/runner.process_pending` runs ONE pass of
-- correlate -> derive -> score -> lifecycle per sweep (doc 13's own L-1 row: "drain loop — one
-- pass per sweep"). The fixpoint iteration is therefore ACROSS sweeps, not inside one, and a
-- counter that lived in the worker would reset on every deploy, every autoscale event and every
-- background task — i.e. it would read zero on exactly the tenant whose sweeps keep restarting.
-- The gate doc 09 sets is "drains exceeding MAX_PASSES: 0 over 7 days"; seven days is longer than
-- any process here lives.
--
-- HOW THIS IS BOUNDED — the question every new table in this repo has to answer, because
-- `expertise_packages` reached 181 MB across 345 rows and put this database into read-only.
-- ONE ROW PER ORG, FOREVER. `org_id` is the primary key and the writer is a single upsert. A
-- tenant that sweeps every ten minutes for a decade holds exactly one row, updated in place.
-- There is no history here on purpose: the hash of a state that has since moved on explains
-- nothing, and the thing worth keeping — that a tenant BREACHED the pass limit, and which
-- situations were still moving when it did — is kept in `exceeded_at` and `detail` until the
-- tenant converges again.
--
-- `state_hash` IS SEMANTIC, NOT A ROW DIGEST. It is computed over the three things doc 13's
-- pseudocode hashes — situations, memberships and lifecycle states — and deliberately NOT over
-- importance scores or any `updated_at`. Scores move with `eval_time` on a quiet org (the recency
-- modifiers read the sweep instant), so a hash that included them would report every tenant as
-- non-convergent within three sweeps and the alert would be worthless on the day it mattered.
-- The columns hashed are named in `context/runner._convergence_state_hash`, which is the one
-- place that decides what "the state" means.
--
-- `passes` COUNTS ONLY UNFORCED MOVEMENT. A sweep that drained new events and changed the state
-- has an external cause and resets the counter to zero; a sweep that drained NOTHING and still
-- moved the state is a pass of the fixpoint, and that is what this column counts. Without that
-- distinction the counter would measure how busy a tenant is rather than whether their
-- derivations settle.
--
-- ORG CASCADE, and the name is in `api/account_routes._ORG_SCOPED_TABLES`. `tests/
-- test_account_erasure.py` replays every migration and fails any table carrying an `org_id` that
-- cannot be erased with its tenant. A convergence hash is a fingerprint of a tenant's situation
-- graph, which is their data, and the erasure loop runs with no try/except by design — a name
-- missing from that list leaks silently.

create table if not exists l2_convergence (
    org_id        text primary key references orgs (id) on delete cascade,
    -- the semantic fingerprint of (situations, memberships, lifecycle states) at the END of the
    -- most recent sweep. Compared with the fingerprint taken at the START of the next one.
    state_hash    text not null,
    -- consecutive sweeps that moved the state with NO new input. 0 means converged.
    passes        int  not null default 0,
    -- the sweep instant (`eval_time`), never `now()` — this table is written from a pass that
    -- takes its clock as a parameter, and a default here would be a second clock disagreeing
    -- with it at a period boundary.
    last_pass_at  timestamptz not null,
    -- set when `passes` reached MAX_PASSES. Cleared the moment the tenant converges again, so a
    -- non-null value always means "still breaching", never "breached once in 2024".
    exceeded_at   timestamptz,
    -- the receipt: both state hashes and the situation ids still moving at the breach. Doc 13:
    -- "record l2_convergence_exceeded with the org, the situations still changing, and the state
    -- hashes." Capped in the writer, never an unbounded dump of the org's situation table.
    detail        jsonb not null default '{}'
);

comment on table l2_convergence is
  'L-4 bounded-fixpoint ledger: one row per org holding the semantic state hash of its situations, memberships and lifecycle states, and how many consecutive no-input sweeps still moved it. `exceeded_at` is an alert, not a log line — a tenant that never converges has a real derivation cycle.';
