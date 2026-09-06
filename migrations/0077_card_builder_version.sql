-- A card's presentation is a BUILD PRODUCT, and until now it had no version.
--
-- `cards_one_per_signal` plus `on conflict (signal_id) do nothing` meant the first card ever
-- built for a signal was the last: improving the slot vocabulary, the render prompt or the
-- authored copy changed nothing a user could see, because every affected card already existed.
-- Every fix upstream of delivery was invisible by construction.
--
-- Stamping the builder identity on the row is what makes "this card was composed by an older
-- builder" a fact the claim can read, so a stale card can be refreshed in place — keeping its
-- card_id, its queue state and anything the user did to it — instead of being duplicated or
-- frozen. NULL means "built before this column existed", which is stale by definition.
alter table cards add column if not exists builder_version text;

create index if not exists cards_builder_version on cards (org_id, builder_version);
