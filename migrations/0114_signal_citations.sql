-- GeniOS Engine · L3 wave Y1 last mile — the expert's own words reach the card's row.
--
-- CLG-08 attaches heuristics to `ReasoningDecision.citations`, byte-identical to the authored
-- artifact and re-validated by the contract at the decision. Nothing then wrote them anywhere:
-- `reason/audit.py`'s decision_core carries the outcome, the hash and the uncertainty and not the
-- citations, and `signals` had no column for them — so the quote died in memory one hop before the
-- surface that exists to show it, and J5's headline row ("a card carrying a heuristic/rule
-- citation") was not merely unmet, it was unreachable.
--
-- The rule half already lands: a blocking rule's quoted statement travels in
-- `signals.rejected_candidates` (migration 0070) and renders as `alternatives_rejected`. This is
-- the same shape for the claim half, and deliberately the same shape — one jsonb column on the
-- signal, written by the one writer that owns the compiled lane.
--
-- Nullable with no default: a legacy-lane signal has no citations and must read as ABSENT rather
-- than as an empty bibliography, which is a different claim.
alter table signals add column if not exists citations jsonb;

comment on column signals.citations is
    'L3 CLG-08 citation material for this decision: [{artifact_id, artifact_class, statement, '
    'statement_hash, source_ref}]. Statements are quoted verbatim from Domain Expertise/ and the '
    'contract re-checks statement_hash at the decision; a renderer may quote but never paraphrase. '
    'NULL on legacy-lane signals, which carry no compiled expertise.';
