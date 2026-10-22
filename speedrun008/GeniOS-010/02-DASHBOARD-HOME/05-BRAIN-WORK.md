# 02.5 · Brain work the dashboard needs

**Written for:** Harsh.

The dashboard already draws every one of these. Today each shows "not measured yet", a preview, or a sample. Each item below names:
- what is missing;
- where in the brain;
- the smallest change that makes the screen true;
- which file on the dashboard side reads it.

They are ordered by what a customer sees first.

| # | What | Why it matters on screen | Size |
|---|---|---|---|
| B1 | Goals: `GET /v1/goals` with progress | Section 1 (this month's goal) and the "Goals formed" card are sample / 0 until this exists | GeniOS-009 G1 + G5. See `03-GOALS/README.md` |
| B2 | AER / HIR weekly rollup | Section 2 is readiness-only until this exists | new route, `03-AER-HIR.md` §4; needs fixed `completed_by` kinds, G7 and G8 |
| B3 | Rename the old `intervention_rate` | Two different numbers share one name | small, `03-AER-HIR.md` §3 |
| B4 | Per-workspace `active` on `/v1/expertise/domains` | The Expertise page marks Sales/Support "Active" for a workspace that has them off | small, `01-NAVIGATION` §3 |
| B5 | Weekly change counts in `home-summary` | "What changed this week" can't show facts learned or updated live | small |
| B6 | Cards raised this week, counted in the brain | `/activity` lists live cards only, capped at 100 | small |
| B7 | `policy_safe` when nothing was decided | A fresh workspace reads "0% Policy-safe actions" | one line |
| B8 | Screen: per-item read path, memory time, popup and card links; week counts | The Screen page cannot say how an item was read, which popup or card it led to, or how many screens were read/skipped | `../05-SCREEN/README.md` §5 (expanded 22 Oct) |
| B9 | Drop the hard-coded notice | `snapshot.notice` "Your company is becoming more proactive." is no longer shown | one line, plus delete `notice-board.tsx` on the dashboard |

---

## B5 · Weekly change counts in `home-summary`

**Today:** "What changed this week" can only show people and companies new or updated (from `/activity`), situations, relationships active and commitments. The facts lines, the biggest number, exist only in the sample.

**Add to `home_summary()`** in `api/home_routes.py`:

```python
"changes": {
  "facts_added":      count graph_facts      where created in 7 days and status='active',
  "facts_updated":    count graph_facts      superseded in 7 days (valid_to set in the window),
  "entities_added":   count graph_nodes      person/company, version = 1, valid_from in 7 days,
  "entities_updated": count graph_nodes      person/company, version > 1, valid_from in 7 days,
  "by_source": { "<source>": facts_added_from_that_source, ... }   # join created_by_event_id → source_events.source
}
```

**Dashboard side:**
- in `live.ts · changes()`, push these as `ChangeRow`s when `summary.changes` exists;
- add `delta` when a previous-week value is also returned;
- the sample rows in `data.ts · sampleContextFlow.changes` already have this shape.

## B6 · Cards raised this week

**Today:** the count comes from `/activity` `insight_generated` in 7 days. That route lists only live cards (not expired or resolved) and caps at 100 rows.

**Add** `"cards_7d": {"critical": n, "high": n, "standard": n}` to `home_summary`, counted from `cards.created_at` over all states.

**Dashboard side:** prefer it over the `/activity` count in `live.ts · cardsThisWeek` and `cardsByUrgency`.

## B7 · `policy_safe`

`home_summary` sets `policy_safe = 100 if decisions_7d else 0`. On a workspace with no decisions this week the strip reads **0% Policy-safe actions**, which reads as a failure.

**Change:** return `None` when nothing was decided. The dashboard then renders "—".

Better still, measure it: the share of gated actions this week that passed every hard rule. Do that if the gate log has it.

## B8 · Screen: links and counts

Expanded on 22 Oct, when the Screen page was rebuilt. The full field list is `../05-SCREEN/README.md` §5:
- per follow-up: `read_by` (rule · quick read · hourly batch), `graph_written_at`, the `moment_id` of its popup, and `card_ids[]` (cards whose evidence includes its `observation_id`);
- per card: `screen_items[]`, the same join the other way;
- per seat, per week, on `/v1/seats/me/weekly-report`: `screens_read`, `screens_skipped`, `threads_to_memory`, `cards_from_screen`.

`screen/live.ts` maps each field when it appears; until then the page says "not served yet" in their place.

## B9 · The old notice

`snapshot.notice` (title "Your company is becoming more proactive.", summary, highlights) is hard-coded in `home_summary`.

The dashboard stopped rendering it on Rohit's word: *"pata nahi kya hai exactly"*. Drop it from the response, then delete `sections/notice-board.tsx` and the `intelligenceSnapshot` sample in `data.ts`.

## Already right, no change needed

- `/integrations/status` per-source `recordsPulled / factsExtracted / entitiesExtracted` and `freshness`. "Where it comes from" reads them as they are.
- `network-health`, `first-scan`, `weekly-report`, `/v1/agents`, `/v1/delegations`.
