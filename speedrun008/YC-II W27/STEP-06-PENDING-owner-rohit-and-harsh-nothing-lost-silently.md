# STEP-06 · PENDING — owner Rohit (push) and Harsh (deploy, migration 0194) · nothing is lost silently — every item, every situation and every card has an end state

**Owner:** Claude. **Depends on:** `STEP-05`. **Moves:** items and situations with no recorded end
state **→ 0**; card expiries with no `card_event` **9 sites → 0**.

**✅ Built 2026-10-07** — tree block `yc2_w27_s06`, 24 units (25 drawn, 1 retired while building), crosscheck *ship*, QA §9.4. **Pending:** Rohit's push; Harsh's deploy (migration `0194`); the production numbers (§8.6, §9.5).

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

---

## 9 · Built — 2026-10-07 (`yc2_w27_s06`, 24 units green, 1 retired)

### 9.1 · What was built

| | Where | What it does |
|---|---|---|
| one way to expire a card | `platform/card_lifecycle.py` | `expire_cards` / `expire_lapsed`: the only writer of a card's `expired` state; one `card_events` row per card it moves, in the caller's transaction, with a cause from a closed vocabulary — `replaced`, `rule_cleared`, `budget_held`, `not_authorized`, `plan_gone`, `rule_muted`, `expired` (the lapse), `extension`, `subject_is_us` |
| every expiry site | `reason/runner`, `reason/composer`, `reason/publication`, `reason/domain_shadow`, `feedback/calibrate`, `deliver/store`, `api/intelligence_routes`, `scripts/repair_self_identity` | all twelve call it — the nine that wrote nothing, and the three that wrote their own event keep their kind (`window.lapsed`, `card.dismissed`, `card.retired`); an AST guard refuses a thirteenth |
| History says why | `deliver/store.CardStore._OUTCOME_KINDS` | gains `card.expired`, `card.resolved` (the team lane wrote it, History never showed it) and `card.retired` (`03` F75) |
| a situation's end after admission | migration `0194_situation_outcomes`, `reason/situation_outcome_store.py`, `reason/domain_shadow.py` | the compiled lane records what came of every admitted LIVE candidate, once per material change (keyed on its admission `decision_id`): `decided` with the change gate's word for it, or the stop and its reason — `no_route`, `incomplete`, `conflict`, `required_missing`, `unsupported`, `no_tenant_pack`, `budget_exhausted`, `error`. Written once after the pass, failing open; a measurement writes nothing; the tenant reset wipes it |
| one reader for every situation | `reason/situation_end.py`, `scripts/situation_ends.py` | every active situation, one end: `no_corpus`, `not_live` (the compiled lane's own `live_lane` answer), `held`, `rejected`, `carded`, `decided`, `stopped`, or `unrecorded` — which must be 0 |
| one end per event | `capture/journey.py` | `event_journey` now reads the memory run and the attention tier and names exactly one `end`: `not_captured`, `superseded`, `in_memory`, `failed`, `parked`, `waiting` (for the drain, the re-read, or memory), `archived` (a screen item), `stopped`, `none` |
| the drains stop starving | `capture/parked/drain.py`, `capture/landing/unread.py` | the parked drain's limited read takes only rows it re-admits (the others counted, unlimited); the re-read ladder's due test moved into its SQL (`03` F74), with the give-up path on its own read |
| the checks | `platform/receipts.py`, `scripts/pipeline_health.py` | receipts *every expired card says why* and *every admitted situation has a recorded end*; the health check *every situation and every card says how it ended*, with each live situation type that has no open card shown with the histogram of its ends (`06` D25: a line, not a red receipt) |
| the golden set | `tests/replays/test_nothing_ends_silently.py` | on every founder case: every event names its end, every active situation names its end, every expired card has its event — with a planted miss of each kind |

### 9.2 · Measured

| | Before (§8.1) | After |
|---|---|---|
| golden: active situations with no record of how they ended | 126 of 227 | **0** — each names its end; the 126 are `not_live` (118) and `no_corpus` (8) |
| golden: events with no end | 0 | 0 — now named by the journey too |
| golden: cards expired with no event | 0 of 0 (never exercised) | 0 of 0 — the twelve sites held one by one instead |
| card expiry sites that write no event | 9 of 12 | **0** — and a thirteenth fails the guard |
| what ends after admission | counters in one log line | one row per admitted candidate, with its reason |
| the golden board | 11/32 · 11/12 · Atlas 4/80 | **unchanged** (`golden_score.py --assert-recorded` exit 0) — STEP-06 changes no decision |
| production: expired cards with no event · admitted situations with no recorded end | 15 (4 Oct audit) · unmeasured | ⏳ after the deploy (§8.6) — target 0 and 0 for everything created since |

### 9.3 · Found while building — each a measurement

- **The check missed a receipt that already existed.** §8.3.5 drew *every event has an end*; receipt 44
  (*every captured event that reached no signal says where it stopped*) and STEP-05's *every kept event
  has entered memory* already hold it. `M24.C4.L-integration.V3.U03` retired with the reason.
- **A fix that would have stopped the ladder giving up.** The first ladder fix filtered the due rows in
  the SQL that `give_up_parked_extractions` also read for over-limit rows — so it gave nothing up. The
  root and capture guards caught it before the commit; the give-up path has its own read.
- **The store's first rule was wrong.** "The first outcome stays" would have kept `budget_exhausted` on a
  candidate decided the next day; the row holds the candidate's CURRENT end, and the change gate's skip
  moves only its clock.
- **A shared SQL fragment inflates the resolver.** Joining two statements from one fragment with `+` read
  as six statements with holes (`platform/table_coverage`); the two ladder reads are whole literals,
  held identical by a test.
- **Two receipt counts are decision gates** — L4 7 → 8, L5 6 → 7, each moved with its reason where it is
  pinned.
- Statement pin 2,955 → 2,955 (moves: +3, −14, +2, +1, +2, +1, +1, +4 — each measured per file and
  documented).

### 9.4 · QA

`baseline/yc2w27-s06-qa/qa_record.txt` — run 1 at `d2146f4f`, green on every tier, a database created for every check: the units 28 / 0 / 0 (4 tree checks + 24 units; 1 retired); the whole database suite 17,989 passed, 0 failed (the same four optional skips, re-listed with their reasons); the golden lane 631 passed, 87 xfailed, 0 skipped; the board matches, unchanged (must-detect 11/32, must-abstain 11/12, Atlas 4/80); 0 golden tenants left; the hermetic job 16,339 passed, 1,388 skipped (the database tests, run in tier 2), 279 deselected, 72 xfailed in 763.88s (0:12:43).

### 9.5 · The deploy, and what comes after

Migration **`0194_situation_outcomes`** ships with `0191`–`0193`; `main.py` applies it at boot, and the
new compiled lane writes it — the code must not serve without it (the boot log must name it). Nothing
to run after the deploy: every expiry carries its reason from the first sweep, every admitted situation
its end. Read §8.6's numbers before the deploy. A day after, `scripts/situation_ends.py --org …` names
every situation's end and `pipeline_health` holds both; each reads `situation_outcomes`, so neither
runs before `0194`.
