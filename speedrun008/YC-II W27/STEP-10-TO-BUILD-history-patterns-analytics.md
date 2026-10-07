# STEP-10 · TO BUILD · history, patterns, analytics — the expert's numbers

**Owner:** Claude. **Depends on:** `STEP-09`. **Moves:** every number the expert reasons with comes
from a calculator, with its evidence and its provenance (*measured here* vs *profession's prior*),
and every *"no reply"* states which mailbox and which window it was checked against.

---

## 1 · What is true now — most of it exists and runs every sweep

| Need | What exists | Live? | Gap |
|---|---|---|---|
| A counterparty's normal reply time | `context/waiting.py:195-321` — person → firm → tenant, `party.reply_cadence_days` + basis | yes | no situation gates on it; `outbound-awaiting-reply` uses a literal 3 days; the fallback copy ignores the basis `[inference]` |
| **Your** normal reply time | none — `context/outreach_situations.py:813-816` says *"needs our own cadence, which nothing derives yet"*; reply-owed is a fixed 2 days (`:756`) | — | missing |
| The directed timeline per counterparty | rebuilt over 180 days inside `context/waiting.py` from `graph_source_refs` and `source_events` | yes | published as derived facts only; the timeline itself is not kept |
| Event ordering, gaps, silence vs prior gaps, cadence, trend, deadline ladder | `reason/reasoners/timeline_unit.py:354-580` | yes | reads only four "last seen" fields unless `timeline.events` is supplied |
| Trended metrics | `context/analytic/sampler.py:191-213` — 12 metrics incl. `relationship.response_latency_hours`, touch / inbound / outbound counts, days since contact; trends, anomalies, cohorts, peer baselines | yes | reaches the corpus only as `analytic_movement` (≤ 12 a sweep) |
| "What happened last time" | `context/correlation_history.py:269` — `derived.history.times_seen`, `prior_outcome`, `prior_card_verdict` | yes | **zero readers** in the corpus (`packs/substrate_demand.py:16-21`) |
| Reply rate | `cohort.reply_rate_bp`, per objective cohort (`context/outreach_situations.py:1095`) | yes | none per counterparty, per wave or per connector |
| Base rates, win rates | `reason/foresight.py:125-150` (Wilson bound) | brief only | Sales-shaped |
| What-if | `reason/simulation.py:130-158` | **no** — tests only | unwired |
| Delay cost, do-nothing | `reason/reasoners/cost_unit.py:155-285`, `alternative_unit.py:238-290` | only with `ranking_v2` | the corpus has no consequence field |
| Bounces | `DELIVERY_FAILURE` (`contracts/signal.py:284-299`) | never fired here | `[PROD]` 5 bounce reports junked, 8 parked |
| Coverage | capture totals; per-signal coverage NULL (bug, `STEP-18`) | partly | no card says *"checked: 1 of 2 mailboxes, 60 days"* |

## 2 · Why

Patterns and analytics are what turn *"it's been a while"* into *"Neel usually answers within a
day; it has been nine"*, and *"follow up?"* into *"after a pitch, one follow-up with real news at 7–10
days is the norm; you sent none."* The numbers must be exact — the model reasons **about** them and
never produces them.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the timeline per workstream | new `context/workstream_timeline.py` | every touch in both directions across mail, calendar and screen, ordered, with who did what and its evidence id — kept, not just reduced to derived facts |
| 3.2 | latencies | `context/waiting.py` extended | theirs per counterparty (exists) **and yours** — overall, and when they wrote first vs when you did — with sample sizes |
| 3.3 | cadence and silence | `timeline_unit.py` fed the full timeline (`timeline.events`) | *silence exceeds this file's own prior gaps* becomes a trigger for `STEP-12` |
| 3.4 | waves and campaigns | `context/outreach_situations.py` readings extended | per outreach wave: sent, bounced, replied, follow-ups, days since — the 11 Aug wave as one object |
| 3.5 | bounces | `capture/` DSN parsing → `DELIVERY_FAILURE` | the failed address and the original message it belongs to; a pitch that bounced is a fact on that investor's file |
| 3.6 | per-connector reply rate | new | Boardy: intros made, contacts who replied, calls booked |
| 3.7 | stage dwell | from `STEP-09`'s stage history | days in the current stage vs the playbook's typical duration (`typical_duration_days` exists in the situation schema and is read by nothing) |
| 3.8 | history read | `derived.history.*` handed to the dossier | *"the last time this program wrote after a silence, it was a rejection"* — when it is true |
| 3.9 | base rates with provenance | a small contract: `{value, n, source: measured_here \| playbook_prior, sparse: bool}` | a tenant number is shown only when `n` is large enough; otherwise the playbook's prior is shown **as a prior** |
| 3.10 | the coverage receipt | per workstream | which mailboxes were read, over which window, how complete — so *"no reply"* is only said when it can be proven (RULE 05) |
| 3.11 | what-if, wired | `reason/simulation.py` called by `STEP-12`'s dossier builder | *"if you send the update today vs in a week"* computed on the frozen snapshot, deterministically |

## 4 · What will happen — the numbers on two of your files `[MODELLED]`

```
Investor · Insight Partners
  timeline          27 Sep  Neel → you   (mail)          8 Oct  call booked (calendar)
  their reply time  n = 1 — too few to call normal          → shown as "first contact"
  your reply time   to investors who wrote first: ___ days (n = ___), measured here
  stage dwell       call booked · 3 days to go (5 Oct → 8 Oct)
  coverage          mrrohitswerashi@gmail.com — Gmail and Calendar, 180 days, complete

Intro · Pankaj (saka.vc) via Boardy
  timeline          3 Sep intro · 4 Sep nudge · 7 Sep nudge · then nothing
  connector rate    Boardy: 7 intros · 4 contacts replied · 1 call booked (measured here)
  silence           32 days; this file's prior gaps: 1 and 3 days → exceeds them
  playbook prior    an intro unanswered for 7 days usually dies (prior, not measured)
```

## 5 · Expected

- every number in every expert dossier traceable to a calculator and evidence ids;
- your own reply time exists, with its sample size;
- bounces appear on the file they belong to;
- every absence claim carries a coverage receipt.

## 6 · Verify

```
.venv/bin/python -m pytest tests/context/test_workstream_timeline.py tests/context/test_latency_and_cadence.py -q
#   numbers recomputed from fixtures exactly; sparse samples flagged; a prior is never labelled measured
.venv/bin/python -m pytest tests/replays -q          # the founder cases' numbers match exactly
```

## 7 · Risks

| Risk | Guard |
|---|---|
| A thin sample read as a pattern | the `sparse` flag, and the rule that a sparse tenant number is never shown as normal |
| A prior mistaken for a measurement | the `source` field is mandatory and rendered |

---

## 8 · The check of 2026-10-07 — what the 5 Oct plan got right, and wrong

Every claim above was re-read against `speedrun008` @ `79d0ff54` (STEP-08 built, STEP-09 checked) by a
read-only worker, and the claims that decide the design again by hand (§8.2, *hand*). The plan was
**measured on the golden set**: 25 of the cases it is about, replayed from their cassettes through the
real chain, their rows read before each tenant was removed — 0 cassette misses, every verdict as `03`
§F.1 recorded it then, no spend (`baseline/yc2w27-s10-check/`: `measure_numbers.py`, `sql_numbers.py`,
`cov_check.py`, `per_case_table.txt`, `summary.json`, `sql_out.json`). Production was not read. STEP-09
was built after the measurement; where it changes a number below, §8.3 says so.

### 8.1 · Measured — the golden set (intros F03–F09, F37; investors F10–F15, F42, F44; the bounce F16; programs F17, F19, F24; the hire F25; partners F26–F29)

| | Result |
|---|---|
| their reply time — the fact the cards read (`party.reply_cadence_days`) | exists on **2 of 25** cases (F17: 35.98 days, F25: 1.92), both basis `tenant`, **each from ONE real reply** — the tenant level's two-gap minimum is met by the same reply counted on the person and on the *"Thread with …"* node (`context/waiting.py` pools every node that carries `thread.last_*`). No n is written anywhere |
| your reply time | **nowhere** in the code. By SQL over the ledger: in all 44 cases one founder reply to an inbound mail exists (F14, 5.0 days, n = 1) — the golden set cannot show it at more than n = 1 |
| the corpus's *"reply cadence"* | a different number: `reason/baselines.py` stores the median gap between a person's OWN messages — how often they write — and that is what every `{baseline: reply_cadence}` rule reads. The founder's own node gets 0.04 days (n = 4) in F15: the gap between his five wave sends |
| a wave as one object (F15) | **no** — 5 `awaiting_response` readings (held at admission), 5 dormant fund situations, 5 open loops ~56 days old, 10 `analytic_movement`; no `campaign.*` fact: the founder's outbound mail publishes no qualified signal, and the wave reading inner-joins one |
| the bounce (F16) | archived at N-03 (a machine sender with no attachment) before the delivery-status parser runs; 0 `DELIVERY_FAILURE` signals; the pitch still "waiting". The ledger ties it to the original by Gmail thread (20 s apart) |
| the connector's rate (Introly, F03–F08, F37) | by SQL over the ledger: 8 introductions, 5 contacts replied, 1 call booked, the founder wrote to 0 of them — not from memory: 3 of the 8 were not in it (STEP-09 since puts all 8 there) |
| history (`derived.history.*`) | 90 rows, every one `first_time` / 1 — and published per ANCHOR while computed per (anchor, domain): a file in two domains keeps the last-sorted one's (F29) |
| coverage | per-signal coverage NULL on 28 of 28 signals (`STEP-18` B5); the golden runner seats no `connections` row, so every state situation says *"a communication source, which is not connected"* |
| what a card says about time | 22 cards; none says "usually", compares with a normal, or carries an n or a coverage line |

### 8.2 · The claims

| Claim (5 Oct) | Verdict (7 Oct) |
|---|---|
| a counterparty's normal reply time, person → firm → tenant, live | ✅ the cascade, `context/waiting.py:195-217` (*hand*). ⚠️ **counts each reply twice**: `_TIMELINE` reads `thread.last_*` on every node and the pipeline writes both on the person and on the thread node (*hand*: no node-type filter); no n written; mail only, never archived mail. Read by `outreach_situations` (awaiting, reply-owed, cohort), an angle and a card slot; no situation gates on it — `outbound-awaiting-reply` uses a literal 3 days; the value is truncated to an integer (F25's 1.92 → 1) |
| your reply time: none; reply-owed a fixed 2 days | ✅ (*hand*: `outreach_situations.py:758` `_REPLY_OWED_AFTER_DAYS = 2`, the comment at `:818`); the same fixed 2 days in the corpus (`reply-owed.yaml`) and the legacy `unanswered_email` rule |
| the timeline is rebuilt, not kept | ✅ — and rebuilt in at least four more places (the sampler over 400 days, the Support desk, `correlation_conversation`, L1's unfilled `direction` columns). Calendar and screen touches are in none |
| ordering, gaps, silence vs prior gaps in `timeline_unit` | ✅ the plugins exist; ⚠️ `timeline.events` has **no writer anywhere** (*hand*), so the unit sees one event; it runs only for compiled Admin situations |
| 12 trended metrics, live | ✅; `relationship.response_latency_hours` is THEIR latency (p50, 28 days) |
| `derived.history.*` has zero readers | ✅; ⚠️ the per-anchor overwrite above (*hand*: the fact id is prefix + node + field) |
| `cohort.reply_rate_bp` live | ⚠️ keyed on `thread.objective` free text: 0 `cohort.*` on the golden set |
| base rates (Wilson) in `foresight.py` | ⚠️ live for the brief's play win rates; Sales-shaped |
| what-if in `simulation.py`, tests only | ✅ and it cannot shift time ("today vs in a week"): its scenarios move fields, its output is the formula's utilities |
| delay cost, do-nothing | ✅ with `ranking_v2` (on); the delay cost is a constant 400 bp a day — not a measurement |
| bounces: `DELIVERY_FAILURE` never fired | ✅ (*hand*: `capture/delivery_status.py` parses; the gate's N-03 archives the report first, `gate/rules.py`); the same fix as `STEP-18` B6 |
| coverage: per-signal NULL; no "1 of 2 mailboxes, 60 days" | ✅ (*hand*: `SyncSummary` has no `source` or `started_at`, which the publisher reads); the window module exists (`capture/coverage/window.py`) but is per source, keyed on sync time, and over-counts on incremental sweeps (*"read 4 of about 3"*, F14); `l1_sync_runs.finished_at` is never written by the insert (*hand*) |
| 3.7 stage dwell from STEP-09's stages | ❌ STEP-09 builds files, not stages (§9); stages are STEP-11's |
| 3.11 what-if wired | ⚠️ would hand the expert the formula's utilities, which `06` and Rohit's 5 Oct direction refuse as the answer |

### 8.3 · New — not in the plan

| # | What | Evidence |
|---|---|---|
| N1 | two "reply cadences": their reply latency (`waiting`) and how often they write (`baselines`, what the corpus reads) | `reason/baselines.py:11, 165-198` (*hand*) |
| N2 | the double count — a tenant "normal" from one reply | `waiting.py` `_TIMELINE`; golden timelines list every message twice |
| N3 | since STEP-09 an introduction writes the turn on the person introduced: their `thread.last_inbound` is the connector's mail, so `last_heard_days` counts from the introduction — "heard from" is "heard about". Their latency is unaffected (no outbound came first); the timeline must say who WROTE (the event's actor), not whose fact it is | `STEP-09` C3 (`2c1cfbeb`) |
| N4 | automated replies skew latency: the connector "replies" in 38 s (F09); a same-thread bounce reads as a 20 s reply | F09, F16 |
| N5 | five windows over one file: correlation 45 days, campaign 90 days and 36 hours, waiting 180, the sampler 400, the backfill 60 | cited in the worker's table |
| N6 | archived mail never enters the timeline | `pipeline.py` (`not metadata_only`) |
| N7 | `packs/capabilities/deal_cooling_v2.py:83` passes `cadence_hours`; the unit reads `expected_cadence_hours` — its 336 h is ignored (Sales, on hold — not fixed) | *hand* |
| N8 | `l1_sync_runs.finished_at` takes the wall clock — a coverage read by window is not replay-deterministic | *hand* |
| N9 | the golden runner seats no connection: every state situation says the communication source is not connected | `cov_check.py` |
| N10 | `WindowCoverage.describe()` has no engine caller; no card slot carries coverage | grep |

### 8.4 · What changes in the design

1. **One reply time, counted once, with its n.** Their latency reads person nodes only; `party.reply_cadence_n`
   is written beside the days and the basis. *Normal* needs n ≥ 5 at the level used (D37); below
   it the number is shown as what it is — *"once, 1.9 days"* — never as a habit. The corpus's
   send-interval baseline is renamed for what it is, *how often they write* (D41).
2. **Your reply time** — the mirror of theirs: from an inbound mail to our next outbound in the same
   conversation, per counterparty and overall, with n; "you" is STEP-04's identity.
3. **The file's timeline is a read model, not a table** — every touch in both directions (mail; past
   meetings from the calendar), ordered, with who wrote (the event's actor — N3) and the evidence id;
   its gaps, and whether the current silence exceeds the file's own prior gaps (the trigger
   `STEP-12` reads). Served at `GET /v1/workstreams/{file}`.
4. **A bounce is a fact on the file** (D38): the gate keeps a delivery-status report; the parser's
   `DELIVERY_FAILURE` becomes an observation on the address that failed and the original's thread
   (Gmail thread + recipient); the waiting facts for that recipient retire. Closes `STEP-18` B6.
5. **A wave is one object** without a qualified signal: the same sentence from the outbound extraction,
   else the same subject within 7 days to three or more outside addresses — sent, replied, bounced,
   followed up, days since.
6. **The connector's rate** from STEP-09's `introduced` edges: introductions, people who replied, calls
   booked — on the connector's file.
7. **The coverage receipt** per mailbox: B5 fixed (the sync summary says its source and start), the window
   per connection, the incremental ratio fixed; a file says what was checked — *"no reply"* only when
   the window covers it and the last sync finished.
8. **History per file**: published per (anchor, domain), so a file in two domains keeps both.
9. **Not now:** stage dwell (no stages — STEP-11, D39); what-if (it cannot shift time and speaks in the
   formula's utilities — STEP-12 decides, D39); numeric playbook priors (STEP-11 authors them — until then
   every number is *measured here*, and says so).
10. **New golden cases first** (D40): the founder replying at several speeds, the production DSN shape, two
    mailboxes — the set cannot show your reply time beyond n = 1, nor a real bounce, nor coverage.

### 8.5 · What will be built — tree block `yc2_w27_s10` (milestone M29), proposed

M28 stays reserved for STEP-09's files going live (D2). 18 units in 6 categories:

| Category | Units | What |
|---|---|---|
| C1 · numbers that say their n | 4 | `contracts/measured` (`{value, n, basis, source, sparse}`); `waiting` counts a reply once and writes n; your reply time; the corpus's send interval renamed (D41) |
| C2 · the file's timeline | 3 | `context/workstream_timeline` (touches both ways, who wrote, gaps, silence vs prior gaps); `GET /v1/workstreams/{file}`; history published per (anchor, domain) |
| C3 · a bounce on the file | 2 | the gate keeps a delivery-status report; `DELIVERY_FAILURE` → an observation on the failed address and the original's thread, waiting retired |
| C4 · waves and the connector's rate | 2 | a wave from outbound mail; the connector's introductions / replies / calls |
| C5 · the coverage receipt | 3 | B5 (the sync summary's source and start); coverage per mailbox, the ratio fixed; the file's receipt |
| C6 · the golden set | 4 | the new cases (D40); the re-record and the board; the health check *every number a file shows carries its n and basis*; the acceptance — every number on a file traceable, with its n |

Critical path, 6 units: the contract → a reply counted once → the file's timeline → `GET /v1/workstreams/{file}` → the re-record → the acceptance.

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| D36 | Fix the double count before anything reads the reply time? It changes live *"they usually reply in X days"* lines | **Yes, first** — today a "normal" can rest on one reply counted twice | yes |
| D37 | When is a measured number *normal*? | **n ≥ 5 at the level used**, n and basis always shown; below it, *"too few to say"* | n ≥ 5 |
| D38 | Bounces: keep them at the gate and put them on the file? | **Yes** — closes `STEP-18` B6; cards for them wait for STEP-14 | yes |
| D39 | Stage dwell (3.7) and what-if (3.11) now? | **No** — no stages exist (STEP-11), and what-if answers in the formula's utilities (STEP-12 decides) | no |
| D40 | New golden cases before the numbers? | **Yes** — your reply speeds, the production DSN shape, two mailboxes; the board is re-scored and recorded | yes |
| D41 | One meaning for *reply cadence*? | **Their reply time**; the corpus's send interval renamed *how often they write*, every rule that reads it moved with it, guarded | yes |

### 8.7 · Risks

| Risk | Guard |
|---|---|
| fixing the double count moves live numbers on cards | D36; the golden board re-scored; F17's and F25's lines read before and after |
| a thin sample shown as a pattern | the contract's `sparse` flag; a test that a sparse number never renders as "normal" |
| a new per-sweep fact makes the change gate re-decide every sweep | facts that move each sweep stay out of the fingerprint (`reason/fingerprint.py` ladders only `days`/`_hours`); `tests/replays/test_an_unchanged_sweep_costs_nothing.py` |
| the rename of *reply cadence* breaks corpus rules | one rename, every reader moved in the same unit, the corpus ratchet tests |
| the gate keeping bounces lets a DSN flood in | only a report the parser recognises (`is_delivery_status`); never on its attached original |
