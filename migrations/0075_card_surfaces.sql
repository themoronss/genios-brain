-- Which surfaces a card is valid on.
--
-- One cards row was written once, shaped for nobody, and served to the desktop app, the agent
-- gateway, Ask and the API alike. The design partner's app showed "antler.co: Residency program
-- rejected 6 Aug" inside "62 OPEN LOOPS" — a deal the card's own evidence marks `rejected`, with
-- zero momentum, past its 14 August deadline. Nothing to do, presented as something needing him.
--
-- The same text is the complete and correct answer to "what happened with Antler?". So this is not
-- a content defect: it is one row serving four questions, and no code asking which was being asked.
--
-- `ask` and `api` default to everything the system knows — suppressing a closed deal from someone
-- who explicitly asked about it is the failure there. `app` and `agent` have to be EARNED by a live
-- next step. That asymmetry is the whole design, and it is why the default below is all four: a
-- card that predates this column keeps its current behaviour until it is rebuilt.

alter table cards
    add column if not exists surfaces text[] not null default '{app,agent,ask,api}';

comment on column cards.surfaces is
  'Surfaces this card is valid on: app | agent | ask | api. app and agent require a live next step; ask and api carry everything, including closed situations.';

-- "What is actually in the app queue" is the question the app asks on every open, and it should be
-- an index scan rather than a filter over every card the org has ever held.
create index if not exists cards_surface_queue
  on cards using gin (surfaces) where state in ('queued','surfaced','snoozed','claimed');
