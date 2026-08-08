-- GeniOS Engine · Layer 5.2 — a delivery no longer requires a card.
--
-- Before the control plane, every outbox row WAS a card push, so `delivery_outbox.card_id` was
-- NOT NULL. Under 0043 the ExecutionObject is the authority and cards are a subordinate read-model
-- (a reminder/escalation delivery has an execution but no card at all). So the column becomes
-- optional. Shipped as its own migration rather than editing 0043 in place — applied migrations
-- are immutable and checksummed.
alter table delivery_outbox alter column card_id drop not null;
