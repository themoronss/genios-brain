-- L2 · `open_loops.awaited_from_node_id` — WHO OWES THE ANSWER.
--
-- WHAT THE LEDGER COULD SAY BEFORE THIS. `contracts/open_loop.open_loop_id` states the identity
-- plainly: a loop is "WHO asked, WHAT KIND of thing they asked for, and WHERE the ask lives".
-- Three of the four verbs in `open_loops.py` work on that identity and they are correct. The
-- fourth — closing — has only ever had one shape: `close_loops_for_reply`, keyed on the SUBJECT,
-- and its own docstring says what it is for: "OUR outbound reply closes this person's open loops".
--
-- So the ledger is complete in exactly one direction. THEY ask, the loop opens on them, WE reply,
-- it closes. In the other direction it opens and never closes: an ask we send is extracted from
-- an outbound event whose `content_subject` is the mailbox owner, so the loop opens on US — which
-- is right, we did ask — and then nothing can ever close it, because `close_loops_for_reply` is
-- called only on the outbound leg and only ever with the RECIPIENT as its subject. Their reply
-- arrives, is processed as inbound, and touches no loop at all.
--
-- Measured consequence on the pilot: every question the founder put to an investor is still open,
-- months later, including the ones that were answered the same week — while the investors who
-- genuinely owe an answer are indistinguishable from those who do not, because the only thing the
-- ledger knows about our asks is that we made them.
--
-- WHY A NEW COLUMN AND NOT A NEW SUBJECT. Re-pointing our asks onto the recipient would have been
-- the smaller diff and it is wrong twice over. It contradicts the identity the contract declares
-- — the subject is who ASKED — and it collides: `open_loop_id` hashes (org, subject, kind,
-- thread), so a question they asked us and a question we asked them, in the same thread, of the
-- same kind, would hash to ONE loop id and the second would silently bump the first's ask_count.
-- The subject stays who asked. This column adds who is waited ON, which is the fact that was
-- missing, and every existing loop id keeps its value.
--
-- NULL IS THE HONEST DEFAULT AND IT MEANS TWO DIFFERENT THINGS, deliberately conflated because
-- both behave identically: an ask recorded before this column existed, and an ask whose answerer
-- the writer would have to guess. A mail to seven investors on one thread is ONE loop — that is
-- what (subject, kind, thread) means — and one column cannot name seven people. Rather than pick
-- one of them or invent a fan-out table for a case nobody has asked to close, the writer sets
-- this only when there is exactly one external recipient, and leaves it null otherwise. A null
-- loop behaves exactly as every loop behaves today: it opens, it bumps, and only an explicit
-- subject-keyed close can shut it.
--
-- Backward compatibility is total. `close_loops_for_reply` is untouched and still closes by
-- subject, so every row that exists today closes on exactly the event it closes on today. The new
-- reader only ever matches rows this column is non-null on, and no such row existed before this
-- migration ran.

alter table open_loops add column if not exists awaited_from_node_id text;

-- Partial, like `open_loops_subject` above it: the only query this serves asks "which OPEN loops
-- is this person the answerer of", on the inbound leg of a single event. Closed loops and null
-- answerers are dead weight in that index and are the overwhelming majority of the table.
create index if not exists open_loops_awaited_from
    on open_loops (org_id, awaited_from_node_id)
    where status = 'open' and awaited_from_node_id is not null;
