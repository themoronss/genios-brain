-- L2 · `open_loops.closed_basis` — WHAT THE CLOSURE RESTS ON.
--
-- `close_loops_for_reply` closes every open loop a person has on the thread, whatever the closing
-- message said, and its call site in `pipeline.py` claims otherwise in as many words: "the ledger
-- says WHICH requests this reply answered — one row each, never the whole person". It does not.
-- They ask "what is your ARR?", we write back "let me check and get back to you", and the ledger
-- records the question as answered. `close_loops_awaited_from` has the same shape inbound: we ask,
-- they reply "will revert shortly", the ask is recorded as met.
--
-- It is the failure `read_overdue_commitments` refuses by name one module over — "Sending
-- something afterwards is not sending THE thing, and claiming otherwise is the failure BS-04
-- names: received, complete, valid and accepted are four different facts." The commitment reading
-- states that refusal and declines to close a promise on it. The loop ledger did not.
--
-- WHAT THIS DOES NOT DO. It does not hold loops open. Requiring proof of an answer before closing
-- would refuse on an ABSENCE — every reply the vocabulary cannot classify would leave an
-- obligation standing for ever, and a founder would be chased about questions answered months ago.
-- Every loop that closed yesterday closes today, at the same moment, on the same event. The column
-- records which of two things we actually observed.
--
--   'answered'  the closing message carried a kind that discharges this loop's ask, by the
--               `discharges` table in `observations/kinds.yaml` — an approval granted or blocked,
--               an intro made, a requested document sent. Six pairs, each true by definition.
--   'replied'   a message arrived and nothing in it can be said to answer the ask. The honest
--               description of every closure this system performed before now, and still the
--               great majority: "what is your ARR?" is discharged by a sentence, and no kind in
--               this vocabulary means "answered the question".
--
-- NULL ON EVERY EXISTING ROW, deliberately, and never backfilled to 'replied'. A closure recorded
-- before this column existed is one whose basis was not observed — which is a third thing, and
-- writing the majority answer onto it would manufacture evidence for thousands of rows at once.
-- Readers treat NULL as no weaker than 'replied', the same conservative direction
-- `vocabulary.owner_basis` takes for an unreadable provenance.
--
-- WHY AT WRITE TIME AND NOT DERIVED ON DEMAND. Once a closure is a flat 'closed', what the closing
-- message carried is gone: the observations survive, but which of them the closer saw, and which
-- loops it was closing at that instant, does not. Unlike a typed absence, this cannot be
-- recomputed by a later reader that finally wants it.

alter table open_loops add column if not exists closed_basis text;

-- The reads this serves ask "which of this subject's closed loops rest on contact alone", always
-- within one org and one subject. Partial, like `open_loops_awaited_from` beside it: open loops
-- carry no basis at all and are the majority of the table.
create index if not exists open_loops_closed_basis
    on open_loops (org_id, subject_node_id)
    where status = 'closed' and closed_basis is not null;
