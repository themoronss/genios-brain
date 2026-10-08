# STEP-10 · PENDING — owner Rohit (push; D42–D44) and Harsh (deploy, no migration; the health check after one sweep) · history, patterns, analytics — the expert's numbers

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

---

## 9 · Built — 2026-10-07/08 (tree `yc2_w27_s10`, 31 units: 18 drawn, 8 found while building, 3 found by the crosscheck, 2 found by QA)

On Rohit's go of 7 Oct with D36–D41 as recommended. 39 commits on `speedrun008`, `c26a2ce7` …
`65faa860`: the lead built 20 units; six worktree workers built 11 (bounces, coverage, the connector's
rate and history, the rename, the gate and connector follow-ups, the wave), and every one was
re-verified on the lead branch — its tests run there and its own mutation set re-run against the
integrated code — before it was taken.

### 9.1 · What was built

| | Where | What it does |
|---|---|---|
| a number says what it rests on | `contracts/measured.py` | `Measured(value, n, basis, source, unit, stat, k)`; `NORMAL_AT = 5` (D37); three kinds — a median is a habit only at five (*"once: 1.92 days"*, *"2 times, median 2 days — too few to call normal"*, *"usually 2 days (n=5, person)"*), a rate says *"k of n"* and is never a habit, a count is exact and zero is *"none"*; `median_of`, `rate_of`, `count_of` |
| their reply time, counted once | `context/waiting.py` | person nodes only (a thread node's facts are the same messages again — the double count, D36); a normal only where a level holds five replies, written with its n and basis; a normal the evidence no longer carries is retired; an introduction is the connector's mail, never the person's |
| a reply in its own conversation (found) | the same | each gap measured inside its thread and pooled — a new topic on another thread is no reply, and your answer is measured from the mail it answers (`03` F103) |
| your reply time | the same | the mirror: per counterparty (`party.our_reply_*`) and overall on the tenant node (`derived.our_reply_*`), each at five answers |
| a bounce ends the wait (found) | the same | a counterparty whose latest mail from us bounced is not waited on; a thread only when every outside recipient of our last mail bounced; a newer mail is a new wait |
| one meaning for *reply cadence* | `reason/baselines.py` and 49 files | how often a person writes is `write_interval` — 77 corpus thresholds moved, values unchanged, the published pack 1.5.0 → 1.5.1 (D41) |
| the file's timeline | `context/workstream_timeline.py` | every touch both ways — mail by who WROTE it, a meeting once at its current start, never a cancelled one; the gaps, the usual gap with its n, whether the silence outlasts every gap the file closed; meetings still to come listed as booked |
| the file's numbers (found) | `context/workstream_numbers.py` | per person: their reply time and yours at any n, the normals that hold (with their level), a bounce; per file: your normal overall, the mailboxes its mail came through, whether *"no reply"* may be said, and every wave its people were sent with what came of it there (found by the crosscheck) |
| one file, readable | `api/workstream_routes.py` | `GET /v1/workstreams/{file_id}` — the file, its timeline, its numbers; another tenant's file and an unknown id are the same 404; nothing written |
| history per file | `context/correlation_history.py` | published per (anchor, domain) — a file in two domains keeps both pasts |
| a bounce kept and read | `capture/gate/rules.py`, `gate.py`, `connectors/composio.py` | a report the parser recognises is never archived by N-01…N-04 nor judged by the junk filter (two found units); its attached original is not a document of its own |
| a bounce on the file | `context/delivery.py` | `delivery_failure` on the address and the original's thread, `delivery.status = failed` on the address (D38; `STEP-18` B6) |
| the connector's rate | `context/workstreams.py` | on a connector's file: the people it introduced (a count), the share who wrote back themselves, the share who met us (rates) |
| a wave | `context/correlation_conversation.find_waves` | one outreach to three or more outside people within seven days, by its sentence or else its subject — sent, replied, bounced, followed up, days since |
| the coverage receipt | `capture/acquire/sync_runner.py`, `capture/coverage/window.py`, `context/coverage_receipt.py` | the sync summary says its source and finish (`STEP-18` B5); coverage per mailbox over its own window; a file's receipt and `covers` — *"no reply"* only when a mailbox's window reaches back and a completed sync has looked since |
| the bundle on written coverage (found) | `capture/esqe/bundle.py` | coverage, once written, crashed signal bundling — fixed (`03` F102) |
| a bounce while it stands (crosscheck) | `context/workstream_numbers.py` | the latest report behind the address's `failed`, read through its references — a second report only corroborates the first one's fact, whose time is the first report's; shown only while nothing has passed between us since: they wrote, or we wrote again |
| a read that fails says so (crosscheck) | `capture/coverage/window.py`, `context/coverage_receipt.py` | each coverage read in a savepoint, with a warning naming the tenant and the mailbox — on Postgres a failed statement had aborted every read after it, silently |
| the golden runner, cold and clean (QA) | `tests/replays/engine_runner.py` | a run starts with no memory of who an earlier run's tenant knew (`routes._SENDER_CACHE`, `03` F119); a run that raises removes its tenant even when asked to keep it |
| the health check | `scripts/pipeline_health.check_every_normal_says_its_n` | fails while a reply time written as a normal has no n or fewer than five; names the file |
| the golden set | `tests/replays/` | the runner seats the founder's mailboxes as production has them (N9); a message may arrive in a second mailbox; three new cases (F45–F47, D40); fifteen cassettes re-recorded, each diff read; the acceptance `test_every_number_says_its_n.py` |

### 9.2 · Measured — the golden set

| | Before STEP-10 | After |
|---|---|---|
| their reply time | F17 *35.98 days* and F25 *1.92 days* as tenant normals built from ONE reply counted twice, written on everyone, no n | *"once: 35.98 days"*, *"once: 1.92 days"* (n = 1); no normal on anyone |
| your reply time | nowhere | F45: *"usually 1.5 days (n=6, person)"* with Meera — written as your normal with her, and overall |
| a bounce | archived at the gate (F16) | kept and read, on the fund's file, its wait ended — F16, and F47 in Gmail's shape (its original never a document) |
| the outreach wave (F15) | five unrelated readings | one wave: sent 5, 0 of 5 replied, bounced or followed up, 56.3 days since |
| coverage | no file named a mailbox; the runner seated none | every file names its mailbox and its 60-day window; F46's answer in the other mailbox is in the file |
| the board (`03` §F.1) | must-detect 12/32 · must-abstain 11/12 · forbidden 4 · Atlas 4/80; lost at the gate 1 | must-detect **13/35** (9 not expressible) · 11/12 · 4 · 4/80; lost at the gate **0**, in reasoning 12 |

Mutations, each unit against its own test (the lead's): 15/15 and 16/16 (your reply time), 11/11 (three
kinds), 6/6 (per conversation), 20/21 + 1 equivalent (the timeline), 13/13 (the numbers), 8/8 (the
waves), 6/6 (the route), 12/13 + the redundant filter deleted (a bounce ends the wait), 8/9 + 1
equivalent (the health check), 2/2 (the bundle); the workers' as listed in the crosscheck. After the
crosscheck and QA: 11/13 + 2 equivalent (a bounce while it stands — the `valid_to` / `status` pair, which
a supersede sets together), 6/6 and 7/7 (the reads that fail), 1/1 on both tests (the cold start), 3/3
(the kept tenant).

### 9.3 · Decided while building

- **Stored normals stay at five; below it the file computes the number from the ledger and shows it
  with its n** — D37's *"shown as what it is"* without ever writing a habit a reader could misuse.
- **Both reply times per conversation** — the plan said so for yours (§8.4); the same rule for theirs,
  or the two would not be mirrors.
- **Three kinds of number in the contract** — a rate worded as a median read *"usually 0.625 ratio"*.
- **The bounce is L1's own `delivery_failure` kind** — one name for one meaning; and `service`, which
  the pipeline has minted since L3-0A, is declared in the node vocabulary.
- **A thread's wait ends on a bounce only when every outside recipient of our last mail bounced.**
- **The rename landed at 49 files** — the worker's 40-file rule stopped it as a proposal; D41 is exactly
  this change. The corpus's prose and the generated book are the authors' (D44, `03` F106).
- **The golden runner seats the mailboxes** — the coverage receipt could not be tested otherwise, and
  production has them.

### 9.4 · Found while building — `03` F102–F118

Fixed: **F102** (the bundle crashed on written coverage), **F103** (reply times across a merged
timeline), **F116** (the scratch database's shared memory), **F119** (the golden runner remembered an
earlier run's tenant, §9.5). Open, each named with its owner: the compiled
corpus lane never receives baselines (F104), two corpus rules compare unlike units (F105), the corpus
book cannot be regenerated (F106), the reply-owed threshold is still two days (F107 → D42), a finished
backfill reads partial in one window read (F108), a receipt cannot name its mailbox's address (F109),
coverage counts objects against messages (F110), the campaign rule counts a colleague (F111), a Bcc'd
pitch forms no wave (F112), history's prior outcome is per anchor (F113), a connector that only
introduces shows its rate nowhere (F114 → D43), four capture tests are sensitive to load (F115), the
connector's fast path still primes the filter for a report (F117), a body-only report reads as an
out-of-office (F118), two older coverage reads swallow a failed statement as X3's did (F120). The
crosscheck (`.trace/reports/crosscheck-yc2_w27_s10-20261008T044214Z.md`) found three, and two are built: a
stored bounce outlived a later exchange in the file's display and showed the first report's time (X1 —
`M29.C3.L-logic.V2.U06`); the coverage reads swallowed a failed statement, which on Postgres aborts every
read after it (X3 — `M29.C5.L-logic.V1.U06`, `V2.U05`); and the route reads the whole tenant for one file
(X2 — declared: fine at the pilot's ~500 mails; scope the reads to the file's people when a tenant needs
it).

### 9.5 · QA

Green on every tier on the second run, at `65faa860` (`baseline/yc2w27-s10-qa/qa_record.txt`; every
database check on a database created for it):

| Tier | Run 1, at `d0496989` | Run 2, at `65faa860` |
|---|---|---|
| the tree and the units' own verifies | 30 pass / 0 fail / 0 skip (26 units) | 35 pass / 0 fail / 0 skip (31 units) |
| the whole suite on Postgres | **4 failed**, 18,880 passed, 4 skipped, 89 xfailed | 18,911 passed, 4 skipped (the known four, re-listed with their reasons), 89 xfailed |
| the golden lane, `GENIOS_GOLDEN_REQUIRED=1` | 776 passed, 87 xfailed, 0 skipped | 782 passed, 87 xfailed, **0 skipped** |
| the board against `03` §F.1 | matches | matches — must-detect **13/35**, must-abstain 11/12, forbidden 4, Atlas 4/80 |
| the hermetic job | 16,719 passed, 1,779 skipped | 16,720 passed, 1,800 skipped (1,796 need a database; tier 2 ran them), 72 xfailed |

**Run 1 was red on the whole suite only.** F45's cassette missed twice at the relevance site
(`test_the_gate_deletes_nothing…[F45]`, key `679dd0acaf92…`; `test_we_are_never_the_subject[F45]`, key
`fea5a51d5ba5…`), and two activation-list tests then failed on the tenant the miss left switched on. The
golden lane and the case alone replayed it exactly. The cause (`03` F119), measured before any fix:
`api/routes._SENDER_CACHE` holds each tenant's known counterparties for five minutes of process memory,
and the runner's `cold_start` never emptied it — seeded with what a finished F45 run knows, the next run
asks exactly `fea5a51d5ba5…`; expired before F45's second sweep, exactly `679dd0acaf92…`. And
`run_case(keep=True)` kept the tenant of a run that raised. Fixed test-first in `M29.C6.L-integration.V0.U05`
and `V0.U06`; the crosscheck's X1 and X3 landed before run 2 as well, and the whole run was repeated.

### 9.6 · After the deploy — Rohit, then Harsh

1. **No migration.** The deploy registers the published pack 1.5.1 (1.5.0's bytes are immutable).
2. **Numbers move on the first sweep, once.** Every *"they usually reply in X days"* that rested on
   fewer than five replies goes (D36); their reply time is now measured per conversation; the waiting
   facts of a bounced counterparty retire. Each subject whose request changed is re-decided once by the
   change gate — as a new company brief is — so the first sweep after the deploy spends more decisions.
3. **A delivery report is kept and read from the deploy on**; its attached original is not a document.
4. **Harsh:** after one sweep, `pipeline_health` — *every reply time written as a normal says its n* must
   pass (`08` §4.8); keep the output with `GET /v1/workstreams/{file_id}` for one investor's file.
5. **Decisions waiting** (`06`): **D42** (the reply-owed threshold from your reply time), **D43** (a
   connector's rate on its named entry), **D44** (corpus rules meant as their reply time); and the label
   rows 45–47 (`golden-labels.md`), Claude's answers until Rohit gives his.
