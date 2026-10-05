# STEP-06 · TO BUILD · nothing is lost silently — every item and every situation has an end state

**Owner:** Claude. **Depends on:** `STEP-05`. **Moves:** items and situations with no recorded end
state **→ 0**; card expiries with no `card_event` **9 sites → 0**.

---

## 1 · What is true now

| | Evidence |
|---|---|
| The compiled lane's outcomes vanish | `[CODE]` `reason/runner.py:1494-1498` discards `shadow_compile`'s return; its tallies (`no_route_by_reason`, `budget_exhausted`, `standing`…) exist only in a log line (`reason/domain_shadow.py:1320-1322`) |
| Failures are counted, not recorded | `[CODE]` `reason/domain_shadow.py:1248-1302` — `NoExpertiseRoute`, incomplete, conflict, required-missing, unsupported, error: counters only |
| Nine of eleven expiry sites write nothing | `[CODE]` only `deliver/store.py:322` (`window.lapsed`) and `api/intelligence_routes.py:1190` (`card.dismissed`) write a `card_event`; `feedback/calibrate.py:412`, `reason/composer.py:280, 309, 319, 360`, `reason/runner.py:666, 1406`, `reason/publication.py:273`, `reason/domain_shadow.py:323` are silent |
| What it hid | `[PROD]` 8 `awaiting_response` situations admitted → 0 packages → 0 reasoning runs, with no recorded reason; 15 cards expired with no `card_event` (2026-10-04) |
| Refusals nobody reads | `[CODE]` `qualification_drops` (nothing reads it back), `publication_rejections`; the drain's `limit 200 … order asc` re-selects the same oldest rows every tick (`capture/parked/drain.py:104-118`) |

## 2 · Why

A silent loss looks exactly like *"there was nothing there"*. Once memory holds everything
(`STEP-05`), the next failure mode is losing it quietly downstream. The Atlas's RULE 14:
*silence is a decision with a receipt.*

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | one end state per item | a view over `source_events`, `event_trace`, `parked_events`, `l2_processing_runs` | each item is exactly one of: `deep` / `skim` / `archive` · in memory (`skeleton` / `full`) · parked (reason, next retry) · failed (reason) |
| 3.2 | one outcome per situation, per material change | migration (next free number) `situation_outcomes`, keyed on `STEP-02`'s fingerprint | `no_route(reason)` · `held(reason)` · `deferred(reason)` · `suppressed(reason)` · `unchanged` · `carded(card_id)`. Written by the `domain_shadow` except branches and by the legacy lane; `run_all` returns the compiled tallies to the funnel instead of dropping them |
| 3.3 | one way to expire a card | new `platform/card_lifecycle.py` `expire_cards(conn, card_ids, *, cause)` | updates the card **and** writes `card.expired` with its cause. The nine silent sites call it. An AST guard fails on any `update cards set state='expired'` outside it |
| 3.4 | receipts that go red | `platform/receipts.py` | (a) an item with no end state after two sweeps; (b) an admitted situation type that produced no card for 7 days, shown with its outcome histogram; (c) a card expired without a `card_event` |
| 3.5 | the drain stops starving | `capture/parked/drain.py:104-118` | rotate by `refetch_next_attempt_at`, not oldest-first |

## 4 · What will happen

The question *"why did the 8 `awaiting_response` situations never become cards?"* becomes one query
with an answer — `no_route(domain_not_activated)`, or `held(source_coverage_insufficient)`, or
whatever it truly is — instead of an afternoon of tracing. And *"History: 15"* on the dashboard
gets one line per card saying why each one left.

## 5 · Expected

- items with no end state after two sweeps: **0**;
- admitted situations with no outcome row: **0**;
- expired cards with no `card_event`: **0**;
- the 7-day *"this type produces nothing"* receipt exists and names its reason.

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/platform/test_card_lifecycle.py tests/reason/test_situation_outcomes.py -q
#   each of the nine former sites, called, leaves a card.expired event — by mutation
#   the AST guard rejects a tenth site
# production, read-only:
#   select count(*) from cards c where c.state = 'expired' and not exists
#     (select 1 from card_events e where e.card_id = c.card_id and e.kind in ('card.expired','window.lapsed','card.dismissed'));  -- 0
```

## 7 · Risks

| Risk | Guard |
|---|---|
| Outcome rows every sweep bloat the database — the 9-row-receipt lesson of `7e19a1c9` | one row per **material change**, keyed on the fingerprint; `unchanged` is written once, not every sweep |
| The AST guard misses an expiry routed through a helper | the guard follows constants and call arguments — the five traps the YCW27 audits documented |
