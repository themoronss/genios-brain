-- Card render provenance: WHY a card shipped as a template stub instead of a written draft.
--
-- 37 of this org's 41 cards carry render_mode='raw_slot' with an empty artifact body, and from
-- the `cards` table alone those two very different worlds are indistinguishable:
--
--   (a) the LLM was never wired into the sweep   → zero spend, zero output
--   (b) the LLM ran and the validator rejected it → full spend, zero output
--
-- They differ by the entire card-render bill. `deliver/render.py` already computes the reject
-- code (V-01 length cap, V-02 invention guard) and the exact offending token, then throws both
-- away: only `card_events.detail` kept the code, and nothing kept the token. Persisting them on
-- the row makes the fallback rate attributable from stored data instead of from a log scrape.

alter table cards add column if not exists reject_code text;
alter table cards add column if not exists reject_detail text;

comment on column cards.reject_code is
  'Why the written draft was refused: V-01 (over length cap) | V-02 (invention guard) | null (accepted, or the renderer never ran — see render_mode).';
comment on column cards.reject_detail is
  'The specific violation, e.g. the token the invention guard flagged. Diagnostic only; never shown to a user.';

-- The operational question is always "what share of this sweep fell back, and why", so index
-- the shape that answers it rather than the code on its own.
create index if not exists cards_render_provenance
  on cards (org_id, render_mode, reject_code);
