# STEP-06 · TO BUILD · nothing is lost silently — every item and every situation has an end state

**Owner:** Claude. **Depends on:** `STEP-05`. **Moves:** items and situations with no recorded end
state **→ 0**; card expiries with no `card_event` **9 sites → 0**.

**Checked 2026-10-07** (§8): the plan re-read against the code with STEP-02 to STEP-05 built, and the
golden set measured. Tree `yc2_w27_s06` (milestone M24, 25 units) is proposed in §8.4 and waits for
Rohit's go.

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

---

## 8 · The check of 2026-10-07 — what the 5 Oct plan got right, and wrong

Every claim was re-read by hand against `speedrun008` @ `b074c091` (STEP-02 to STEP-05 built). The
golden set was measured twice, with its cassettes and no spend (`baseline/yc2w27-s06-check/`: the
scripts, their output and `summary.txt`). Production was not read — Claude's production reads need
Rohit's permission — so production's numbers are §8.6's read-only SQL, for Harsh.

### 8.1 · Measured — on the golden set (44 cases)

| | |
|---|---|
| events with no end state | **0** — STEP-05 put every kept event in memory; parked, dropped and archived events carry their reason in `parked_events` or `event_trace` |
| cards | 25 built, **0 expired**. The golden set never expires a card, so it does not exercise the nine silent sites: units hold them, one by one (§8.4, C1) |
| active situations | **227**. Live (Admin): 89 — 17 decided, each with a change-gate row; 72 held, each with its reasons in the admission ledger. Shadow (`sales`, `support`): 125, of which 7 were decided in shadow. Unroutable (`fundraising`, no corpus): 13, of which 5 were decided in measurement. **126 have no record anywhere of how they ended** — 118 shadow, 8 unroutable |
| why live situations are held | `verified_evidence_required` on all 72; 18 also `qes_required`, 2 `source_coverage_insufficient`. Nine are `awaiting_response`. For a HELD situation, "why did it never become a card" is already answered by the admission ledger |
| what ends after admission, unrecorded | over 85 sweeps: 49 admitted, 47 compiled — 1 `no_route` (`predicate_rejected`, a `meeting_follow_through`) and 1 `incomplete` exist only as counters in one log line |

### 8.2 · The claims

| Claim (5 Oct) | Verdict (7 Oct) |
|---|---|
| the compiled lane's outcomes vanish: `run_all` discards `shadow_compile`'s return | ⚠️ partly. STEP-02 keeps the result for its skip count only (`reason/runner.py:1755-1796`); it records every DECIDED subject in `reasoning_fingerprints` (0191); and the admission gate records admit, hold and reject per live situation, with reasons (`situation_admission_decisions`, 0122). What still lives only in the log line: what ends between admission and a decision — no route, incomplete, conflict, required-missing, unsupported, no tenant pack, budget, error — and every shadow or unroutable situation |
| failures are counted, not recorded | ✅ — `reason/domain_shadow.py:1398-1434` (moved +150); `no_anchor` at `:1095` |
| nine of eleven expiry sites write nothing | ✅ — nine, at new lines: `feedback/calibrate.py:424`, `reason/composer.py:280, 309, 319, 360`, `reason/runner.py:803, 1654`, `reason/publication.py:273`, `reason/domain_shadow.py:324`. The two that write: `deliver/store.py:348` (`window.lapsed`) and `api/intelligence_routes.py:1190` (`card.dismissed`). New: History shows a card's last reason only for the kinds in `CardStore._OUTCOME_KINDS` (`deliver/store.py:566`), and `card.resolved` (the team lane) and `card.retired` (STEP-04's repair) are not among them (`03` F75) |
| [PROD] 8 `awaiting_response` situations admitted → 0 packages → 0 runs; 15 cards expired with no event | not re-measured — production. On the golden set every `awaiting_response` situation is HELD, with its reason, not admitted. §8.6 asks production the same two questions |
| `qualification_drops`: nothing reads it back; nor `publication_rejections` | ❌ stale. `qualification_drops` is read by `context/situation_bso.py:559` and `api/routes.py:2018`; `publication_rejections` by `capture/journey.py` and `GET /qualification/rejections`. And `capture/journey.event_journey` (`GET /events/{id}/journey`) already answers "why did I never see X?" for one event — but stops at Layer 1: it reads no memory run and no attention tier |
| the drain's `limit 200 … order asc` re-selects the same oldest rows every tick | ✅ — `capture/parked/drain.py:136-149`. Rows another drain owns (refetch, recapture, re-extraction) are counted and skipped where they stand, so 200 of them starve every newer row this drain could re-admit. After STEP-05's deploy, `queue_unread` files `extraction_never_ran` parks in bulk |
| (new) the same starvation in STEP-05's re-read ladder | `capture/landing/unread._FIND_PARKED` (`:146-165`) takes the newest 200 and only then drops what is not yet due (`:201-215`): 200 newer rows waiting out their backoff hide every older row that is due (`03` F74) |
| (new) a replaced card reads as an ignored one | `api/benchmarks_routes._acted_rate` (`:72`) is acted ÷ (acted + dismissed + expired), so a card expired because a newer card replaced it counts as a card nobody acted on. With a cause on every expiry the two can be told apart (`03` F76, owned by `STEP-16`) |

### 8.3 · What changes in the design

1. **The situation ledger records only what nothing records today.** Admission and the decision already
   have their ledgers. The new table (migration `0194_situation_outcomes`) holds one row per ADMITTED
   candidate — keyed on its admission `decision_id`, so one row per material change, written once,
   its `last_seen_at` moving — saying what came of it: `decided`, or the stop and its reason
   (`no_route`, `incomplete`, `conflict`, `required_missing`, `unsupported`, `no_tenant_pack`,
   `budget_exhausted`, `error`). Live rows only, flushed once after the pass, failing open — the change
   gate's discipline. A measurement pass still writes nothing.
2. **A shadow or unroutable situation is named, not written.** Its end is a fact of the tenant's
   activation — "`sales` is not activated", "`fundraising` has no corpus" — read when asked. Writing
   it every sweep would repeat the 9-row-receipt lesson (`7e19a1c9`).
3. **One reader says how any situation ended** — `reason/situation_end.py`: not live (why), held or
   rejected (with reasons), stopped after admission (with reason), decided (the change gate's outcome),
   carded. The 126 silent situations of §8.1 each get a named end.
4. **One way to expire a card**, as planned — and the two writers that already explain themselves, and
   STEP-04's repair script, go through it too, keeping their kinds, so the guard needs no exception;
   History gains `card.expired`, `card.resolved` and `card.retired`.
5. **An item's end is the journey's, extended** — not a new view. `capture/journey` adds the attention
   tier and the memory run, and names exactly one end per event; a receipt counts events with none.
6. **"A situation type silent for 7 days" becomes a health-check line with its histogram, not a red
   receipt** — a type can be right to stay silent; an abstention is an outcome. The receipts are the two
   things that are wrong whenever they are non-zero: an admitted situation with no recorded end, an
   expired card with no event.
7. **Both drains stop starving.** The parked drain limits only the rows it re-admits; the re-read
   ladder's due filter moves into its SQL.
8. **Not in this block.** `03` F57 (readers select words by thread membership) stays contained — an
   archive keeps no prepared text and STEP-05's metadata road writes no correlation; a reader that asks
   the outcome is `STEP-13`'s. The acted rate (F76) is `STEP-16`'s. `STEP-06` changes no decision, so
   the golden board must not move.

### 8.4 · What will be built — tree block `yc2_w27_s06` (milestone M24), proposed

| Category | Units | What |
|---|---|---|
| C1 · a card's end | 11 | `platform/card_lifecycle.expire_cards` — one statement and one `card.expired` event per card, with its cause; the nine silent sites, the two that already explain themselves and STEP-04's repair script call it; History shows every ending kind; an AST guard refuses a thirteenth site |
| C2 · a situation's end | 6 | migration `0194`, its store and the tenant reset; the compiled lane records each admitted candidate's end; `reason/situation_end.py`; `scripts/situation_ends.py` |
| C3 · an item's end | 1 | `capture/journey` names one end per event, with its attention tier and memory run |
| C4 · the checks | 4 | three receipts — every expired card says why, every admitted situation has a recorded end, every event has an end — and the health check, with the 7-day silent types |
| C5 · the drains | 2 | the parked drain and the re-read ladder stop starving |
| C6 · the golden set | 1 | the acceptance on every case, with a planted miss of each kind |

25 units. Critical path, 7: `C1` the helper → its `domain_shadow` site → `C2` the compiled lane's
record (after the table and its store) → the situation reader → its receipt → the health check → the
acceptance. One verify is uncertain until built: driving the compiled lane into each stop
(`no_route`, `incomplete`, …) on purpose — the golden set reaches two of them; the rest need a stub.

### 8.5 · Decisions

| | Question | Default |
|---|---|---|
| D24 | Cards that expired before STEP-06 carry no reason. Write one now ("expired before reasons were recorded")? | **No** — History keeps them as they are; the receipt counts cards created after `0194` is applied |
| D25 | A situation type that produced no card for 7 days: red receipt, or a health-check line with its histogram? | **The health-check line** — silence can be right |

### 8.6 · Production — the numbers to read (read-only, for Harsh, before and after the deploy)

```
-- cards expired with no event (the 4 Oct audit counted 15)
select count(*) from cards c where c.org_id = :o and c.state = 'expired' and not exists
  (select 1 from card_events e where e.org_id = c.org_id and e.card_id = c.card_id
    and e.kind in ('card.expired', 'window.lapsed', 'card.dismissed'));
-- every active situation's latest admission, by type (the 5 Oct claim: 8 awaiting_response admitted, 0 runs)
select s.domain, s.situation_type, d.outcome, d.reasons, count(*)
  from context_situations s
  left join lateral (select outcome, reasons from situation_admission_decisions x
                      where x.org_id = s.org_id and x.situation_id = s.situation_id
                      order by decided_at desc limit 1) d on true
 where s.org_id = :o and s.status in ('active', 'partial')
 group by 1, 2, 3, 4 order by 5 desc;
-- the parked drain's queue, by owner (does anything starve?)
select reason_code, status, count(*) from parked_events
 where org_id = :o and status = 'pending' group by 1, 2 order by 3 desc;
```
