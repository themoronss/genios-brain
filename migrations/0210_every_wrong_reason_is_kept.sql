-- 0210 · every "wrong because" reason a card offers is kept (STEP-18 B3, `yc2_w27_s18`
-- M48.C1.L-contract.V0.U01).
--
-- THE DEFECT. `0034` wrote the reason rule into both verdict ledgers as an unnamed CHECK —
-- `cause <> 'wrong' or (reason is not null and reason in ('not_relevant', 'wrong_facts',
-- 'bad_timing'))`. The vocabulary then grew to eleven (`contracts/learning_attribution.WrongReason`):
-- the card offers all eleven (`deliver/card_builder`), the route accepts all eleven
-- (`api/intelligence_routes._FB_WRONG_REASONS` = `deliver/actions.WRONG_REASONS`), and eight of them
-- reached the INSERT inside the founder's own write and were refused by the database — a 500, and the
-- verdict lost. The three old spellings are unchanged: a judgment already recorded grades as it did.
--
-- WHAT IT ARMS: NOTHING. Calibration reads these rows in shadow (`06` D13 — `calibration_apply` is
-- never default-on); the Adaptive lease counts `bad_timing` rows only, so a new reason only adds to
-- its denominator; precision's roles per reason are `feedback/attribution`'s map, which already names
-- all eleven.
--
-- ADDITIVE. A constraint is dropped and a looser one added, so the previous image — which writes
-- only the three — runs against this schema unchanged (`tests/platform/test_the_code_can_always_be_
-- rolled_back.py`). The old rule is found by what it says, not by the name Postgres gave it, because
-- an unnamed CHECK's name is the server's choice; the new one is named, so the next change can say
-- which it means. Idempotent: a second run finds the old rule gone and replaces the named one.

do $$
declare
    t text;
    old record;
begin
    foreach t in array array['card_feedback_verdicts', 'card_feedback_revisions'] loop
        for old in
            select conname from pg_constraint
             where conrelid = format('public.%I', t)::regclass and contype = 'c'
               and pg_get_constraintdef(oid) like '%reason%'
               and pg_get_constraintdef(oid) like '%bad_timing%'
               and conname <> t || '_reason_vocabulary'
        loop
            execute format('alter table %I drop constraint %I', t, old.conname);
        end loop;
    end loop;
end $$;

-- The house pattern (`tests/platform/test_migrations_apply.py`): `add constraint` is not idempotent
-- in Postgres, so each is preceded by its own `drop constraint if exists`.
alter table card_feedback_verdicts drop constraint if exists card_feedback_verdicts_reason_vocabulary;
alter table card_feedback_verdicts add constraint card_feedback_verdicts_reason_vocabulary
    check (cause <> 'wrong' or
           (reason is not null and reason in (
               'not_relevant', 'wrong_facts', 'bad_timing',
               'misread_source', 'stale_data', 'wrong_subject', 'bad_link',
               'bad_reasoning', 'wrong_playbook', 'wrong_person', 'badly_written')));

alter table card_feedback_revisions drop constraint if exists card_feedback_revisions_reason_vocabulary;
alter table card_feedback_revisions add constraint card_feedback_revisions_reason_vocabulary
    check (cause <> 'wrong' or
           (reason is not null and reason in (
               'not_relevant', 'wrong_facts', 'bad_timing',
               'misread_source', 'stale_data', 'wrong_subject', 'bad_link',
               'bad_reasoning', 'wrong_playbook', 'wrong_person', 'badly_written')));
