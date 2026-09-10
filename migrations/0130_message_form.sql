-- L1.4.6 · THE SHAPE OF WHAT WE SENT, so an outcome can one day be attributed to it.
--
-- THE SENTENCE THAT COULD NOT BE SAID. "Rohit, ten 600-word emails to investors got no replies;
-- the four-line ones got three." In this database those two weeks are byte-for-byte the same
-- shape — a set of `thread.last_outbound` timestamps and a `thread.days_waiting`. There is no
-- number anywhere that differs between them, so the advice cannot be derived, cannot be
-- evidenced, and cannot be gated on by any authored situation. The corpus already asks for it
-- and cannot have it: `Sales Expertise/heuristics/cold_email/reply-rate-beats-open-rate-always
-- .yaml` says *"Judge every change to a cold-email programme on reply rate per person"*, and its
-- only usable condition is `{exists: thread.last_outbound}`.
--
-- WHY COLUMNS AND NOT A NEW TABLE. The text is ALREADY HERE. `clean_text` sits in this row under
-- a 180-day retention clock, and `_envelope_direction` is already computed at
-- `capture/pipeline.py:445` and thrown away after the tier decision. Every number below is
-- derived from bytes this table holds at the moment it holds them: zero extra capture, zero
-- extra network, nothing new asked of any connector.
--
-- THESE ARE FEATURES, NOT CONTENT, and that is a privacy improvement rather than a cost. A word
-- count is not a message. When `purge_expired` deletes `clean_text` at 180 days the counts may
-- outlive it, because five integers about a message cannot reconstruct the message — which is
-- precisely what makes a year-long "your emails got longer and your replies got fewer" honest
-- to compute without retaining a year of anybody's mail.
--
-- WHAT THEY MAY NOT BECOME. A correlation between length and replies is an OBSERVATION about a
-- pattern, never a cause and never a verdict about a person. Two counts and a reply rate cannot
-- see the deal, the relationship or the week. Any card built on these must say what it measured
-- and over how many sends, and `FX-36`'s rule stands: operational intelligence may show explicit
-- dependencies and constraints, not accusatory inferences about people.
--
-- NULL IS THE HONEST DEFAULT. Every column is nullable and every existing row keeps NULL. A zero
-- word count would read as "they sent an empty message"; NULL reads as "this message predates
-- the measurement", which is what is true.

alter table prepared_content add column if not exists direction        text;
alter table prepared_content add column if not exists body_chars       int;
alter table prepared_content add column if not exists body_words       int;
alter table prepared_content add column if not exists paragraph_count  int;
alter table prepared_content add column if not exists question_count   int;

-- The roll-up reads (direction, created_at) for one org and nothing else.
create index if not exists prepared_content_form
    on prepared_content (org_id, direction, created_at);
