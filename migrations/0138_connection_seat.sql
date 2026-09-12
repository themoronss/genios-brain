-- 0138 · PER-SEAT CONNECTIONS — a member's own mailbox is their own connection.
--
-- Until now every connection belonged to the ORG (`ownership_type` defaulted to 'workspace' and
-- nothing ever wrote anything else), and its Composio `user_id` was the org id, so an org could
-- hold exactly one Gmail. A seat connection records WHOSE it is: `seat_id` names the seat, its
-- Composio user id is `{org_id}:{seat_id}` (a separate Composio account per member), and the
-- seat's address is the `mailbox_owner` its messages' visibility is built from.
--
-- NULL seat_id = a workspace connection = exactly today's behaviour.
alter table connections add column if not exists seat_id text;

-- Normalise before constraining: a row with no seat is a workspace connection whatever the free
-- text column says (nothing wrote anything but the default, so this is expected to touch nothing).
update connections set ownership_type = 'workspace'
 where seat_id is null and ownership_type is distinct from 'workspace';

do $$
begin
    if not exists (select 1 from pg_constraint where conname = 'connections_ownership_check') then
        alter table connections add constraint connections_ownership_check
            check (ownership_type in ('workspace', 'seat')
                   and ((ownership_type = 'seat') = (seat_id is not null)));
    end if;
end $$;

create index if not exists connections_by_seat on connections (org_id, seat_id);
