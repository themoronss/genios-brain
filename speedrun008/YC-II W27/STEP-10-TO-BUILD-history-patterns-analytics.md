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
