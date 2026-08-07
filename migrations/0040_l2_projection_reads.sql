-- GeniOS Engine · L2 · the index the projection and situation reads depend on.
--
-- `graph_facts.created_by_event_id` is the join that connects a situation's EVIDENCE to
-- the entities that evidence produced:
--
--     context_correlation_members.event_id  →  graph_facts.created_by_event_id
--
-- It is how a lens finds the people on a deal (not just the deal), and how a situation's
-- coverage sees a fact that landed on a person rather than on the anchor.
--
-- Migration 0004 declares the column and indexes `(org_id, subject_node_id, field)` and
-- `(org_id, fact_id)` — nothing on `created_by_event_id`. That was survivable while the
-- join ran once per L2 drain. It is not survivable now that it runs per API request, per
-- domain: an unindexed join against every active fact in a tenant, on a page someone
-- refreshes.
--
-- Partial on `valid_to is null` because every reader of this join asks only for current
-- facts — the historical versions are never on this path, and excluding them keeps the
-- index proportional to the live graph rather than to its whole history.

create index if not exists graph_facts_by_event
    on graph_facts (org_id, created_by_event_id)
    where valid_to is null;

comment on index graph_facts_by_event is
  'Supports evidence→entity traversal: correlation members → facts an event created. Used by context/projections.py and context/situations.py coverage.';
