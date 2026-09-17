-- "Already handled" — the manager did it somewhere GeniOS could not see.
--
-- Until now the panel offered Done and Not useful, and a right-but-invisible card had to be
-- closed with one of them. Both lie in a way that matters:
--
--   Done      counts toward `nudged_then_closed`, the one number the product's value rests on
--             ("you would have missed it"). GeniOS did not cause that close and must not claim it.
--   Not useful mutes the topic for 7 days AND feeds the note back to the model as an example of
--             the kind of note to stop writing — punishing a card that was right.
--
-- So it gets its own resolution and its own feedback action. What it measures is the SOURCE
-- COVERAGE GAP: how often the manager works somewhere the product cannot see, which is the
-- number that says which connector to build next.
alter table screen_followups drop constraint if exists screen_followups_resolution;
alter table screen_followups add constraint screen_followups_resolution
    check (resolution is null or resolution in ('answered', 'done', 'dismissed', 'expired', 'handled'));

alter table moment_feedback drop constraint if exists moment_feedback_action;
alter table moment_feedback add constraint moment_feedback_action
    check (action in ('shown', 'clicked', 'acted', 'dismissed', 'wrong', 'snoozed', 'useful', 'handled'));
