-- 0181 · the conversation a signal was qualified inside.
--
-- THE DEFECT: five values Layer 1 computed CORRECTLY and then did not carry.
--
-- `ThreadContext` reconstructs which conversation, whose turn, which turn and how deep — and its
-- own docstring says what happened to all of it: *"NONE of it reached S4"*. That was fixed. The
-- value then stopped ONE SEAM LATER: `NormalizedSignal.thread` sits in `build_signal` and the
-- builder never read it, so `qualified_signals` has no idea what conversation a signal came from.
--
-- It is the same leak step 14 found in `domain_hints`, where the builder rebuilt a value by hand
-- and dropped `confidence_bp` on the way, and it is the plan's whole diagnosis said out loud:
-- *"every measured loss is a value that is computed correctly and then not carried."*
--
-- WHAT IT BUYS. Four of the benchmark's eighteen misses turn on exactly these columns, all of them
-- classed `not_carried`: message_direction, ball_in_court, turn_index and activity_count. Eleven of
-- the eighteen are that class. Layer 2 scores attention on `ball_in_court = 'us'` and today
-- recomputes a weaker answer from Gmail labels because L1's answer never arrives.
--
-- WHY thread_key AND subject_key BOTH. They answer different questions. `subject_key` is ALG-22's
-- "what is this ABOUT" and resolves to an entity or a CRM record at rungs 1-3, falling to the
-- thread only at rung 4. `thread_key` is "WHICH CONVERSATION". Neither is derivable from the other,
-- and a join on the wrong one silently merges two subjects or splits one conversation.
--
-- NULLABLE, AND NULL MEANS UNKNOWN. Every signal written before this carries no conversation, and
-- the honest reading of that is "we do not know". `direction` in particular must stay nullable: a
-- NOT NULL DEFAULT 'inbound' would state the exact falsehood the code refuses to state — with no
-- identity for "us" every message looks inbound, which is how a product's own onboarding mail got
-- modelled as a prospect asking for a demo.
--
-- turn_index AND thread_depth ARE ONLY CORRECT SINCE STEP 16. Before it no connector stated a
-- thread position, so every event read turn 0 of 1. Rows written before that deploy carry the old
-- reading and cannot be repaired without a re-sync — see speedrun008 step 16 §4.
--
-- Idempotent: add-if-not-exists, safe to re-run.
alter table qualified_signals
    add column if not exists thread_key    text,
    add column if not exists direction     text,
    add column if not exists turn_index    integer,
    add column if not exists thread_depth  integer,
    add column if not exists ball_in_court text;

-- "What is this tenant waiting on us for" is the question attention scoring asks, and it asks it
-- per org. Partial, because `unknown` is the default reading and carries no information: indexing
-- it would put most of the table in the index to answer a question about the rest.
create index if not exists qualified_signals_ball_in_court
    on qualified_signals (org_id, ball_in_court)
 where ball_in_court in ('us', 'them');

-- Grouping a conversation's signals is the join Layer 2 could not make: with no thread key, two
-- messages of one thread produced two subjects nothing downstream could bring together.
create index if not exists qualified_signals_thread_key
    on qualified_signals (org_id, thread_key)
 where thread_key is not null;
