-- GeniOS Engine · L2-7 · which SITUATION a signal came from.
--
-- ⛔ THE VALUE WAS IN SCOPE AND THROWN AWAY. `domain_shadow.shadow_compile` reads
-- `row["situation_id"]` four times within twenty lines of emitting the signal, and the emit path
-- (`_persist_live` -> `_emit_capability_signal`) never carried it — there was nowhere to put it.
-- That is `not_carried`, the class of defect L1 step 18 named: "every measured loss is a value
-- that is computed correctly and then not carried".
--
-- WHY IT MATTERS. `deliver/pipeline` loops over SIGNALS, and signals are emitted per
-- (pack, rule, node), so one situation that fires three rules becomes three cards — "Nitesh's
-- inbound messages dropping", "Nitesh Pant's touch frequency declining", "Check in with Nitesh
-- Pant". They can never merge while the builder cannot see which situation they share.
--
-- ⛔ WHY NOT `subject_node_id`. `context_situations` is unique on (org_id, correlation_id), so one
-- node carries several genuinely different situations — a support case and an admin follow-up
-- about the same person. Grouping cards by node would merge things that are not the same thing,
-- which is worse than the fan-out it fixes.
--
-- ⛔ NULLABLE, AND THE NULL IS A REAL ANSWER. A signal written before this column, and a signal
-- whose situation never formed, both read NULL — and `deliver/card_source.classify` reads that as
-- UNINTERPRETED rather than as missing. If every signal had to belong to a situation to be seen,
-- a correlator gap would become a silent disappearance, which is the exact failure L2-4 exists to
-- end. Fewer cards must come from MERGING, never from dropping.
--
-- NO FOREIGN KEY, DELIBERATELY. A situation is archived on its own lifecycle
-- (`status = archived`) while its signals stay open, and an FK would either block that archive or
-- cascade a card away from a founder who was reading it.

alter table signals add column if not exists situation_id text;

-- Partial: the only query is "open signals, grouped by the situation they came from", and an
-- index over closed rows is an index over history nobody selects.
create index if not exists signals_situation_open_idx
    on signals (org_id, situation_id)
    where status = 'open' and situation_id is not null;

comment on column signals.situation_id is
    'L2-7 · the context_situations row this signal was compiled from. NULL means uninterpreted — '
    'either written before 0182, or a signal whose situation never formed. NULL is an answer, not '
    'a gap: deliver/card_source.classify surfaces it labelled rather than dropping it.';
