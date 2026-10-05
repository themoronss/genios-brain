# STEP-12 · TO BUILD · the expert pass — one strong judgment per file, only when it changed

**Owner:** Claude. **Depends on:** `STEP-02` (fingerprint), `STEP-07` (brief), `STEP-09` (files),
`STEP-10` (numbers); `STEP-11` makes it better but is not a precondition (D3). **Decisions:** `06`
D1 (does the judgment decide what matters), D7 (model and cap). **Moves:** golden must-detect
**≥ 90%**, must-abstain **≥ 95%**, forbidden outputs **0**; the per-sweep decider retired for every
file the expert covers.

This is the step `05-HOW-THE-EXPERT-THINKS.md` describes. Read that first.

---

## 1 · What is true now

| | Evidence |
|---|---|
| The current decider calls itself a chief of staff — and is given almost nothing | `[CODE]` `reason/llm_decision_maker.py:479-593`: one situation, the latest **4** messages' summaries, ≤ 40 rule facts, ≤ 25 neighbour facts, the formula's baseline; **no company, no prior decisions or cards or feedback, no history beyond four messages, no timeline**. It is asked for a score per play (`:581-635`); its rationale and *missing* list are written and **read by nothing**; `output_lane` is left NULL |
| The context reasoner built for this never ran | `[CODE]` `reason/situation_reasoner.py` (R-6) behind `RSiteGate`, persisting to `situation_interpretations` (`context/interpretation_store.py:30-59`); `[PROD]` 1,839 rows, **0 with a proposal** — its L4 feature is not default-on (`platform/intelligence_onboarding.py:163-167`) and the table has no reader |
| The prose that exists never reaches the card | `[CODE]` the R-2 narrator (`reason/bundle/sweep.py:47-196`, Sonnet 5, $2/day) writes to `l4_reasoning_bundles`, read only by an API feed |
| The machinery to do this right exists | `[CODE]` the R-site runner `reason/llm_sites.run_site` (`:314-377`) with `RSiteGate` and a durable `PostgresSiteCache` (`:194-245`); the closed site list `reason/bundle/sites.py:20-56`; the replay-safe injection R-1 uses (`reason/llm_interpretation.py:250-269`, `reason/adapters/native.py:289-301`) → `reasoning_context_payloads` (`reason/store.py:688-700`) → `replay_persisted` (`reason/replay.py:145-201`) — **a decision recomputed without calling the model** |
| The seam | `[CODE]` inside `shadow_compile`, right after `build_context_slice` and the package compile (`reason/domain_shadow.py:1059-1068`) — where R-6 already sits (`:1072-1124`) |
| What a card needs to exist | `[CODE]` a full audited L4 run (`reason/authority.py:15-42, 119-265`) through `reason_native_capability` → `persist_execution` (`reason/audit.py:254-286`) → `_emit_capability_signal` (`reason/domain_shadow.py:233-408`) |

## 2 · Why

This is the one thing you asked for: GeniOS thinking about your company like a 30-year expert.
Everything before this step makes the thinking possible; everything after it makes it safe to show.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the dossier | new `reason/expert/dossier.py` | for one file: the brief (`STEP-07`) · the timeline with evidence ids (`STEP-10` 3.1, via `context/bounded_read.py`, whose only caller today is a health check) · open asks and roles (`STEP-09`) · the numbers with provenance (`STEP-10`) · the playbook, accepted or labelled draft (`STEP-11`) · prior judgments and what came of them (`situation_interpretations`, `card_events`, verdicts, `derived.history.*`) · the coverage receipt · a what-if from `reason/simulation.py`. Bounded; truncation reported, never silent |
| 3.2 | the thinking checklist | new `reason/expert/checklist.py` | Plane R's Groups 1–4 compiled into the prompt's sections, in order: establish what is true → frame, and the rival frames → expected vs actual (from the playbook) → patterns and counter-patterns, with their provenance → the unknowns that would change the answer → **scenarios**: do nothing · act now · best · worst · signals to watch → appraisal of stakes, urgency and reversibility, each with its reasons → mode of intervention → best next move, an alternative, a wait-or-stop rule, *done when* → the draft |
| 3.3 | the call | a new site `SITE_EXPERT_REVIEW` in `reason/bundle/sites.py`; run through `llm_sites.run_site` + `RSiteGate` + `PostgresSiteCache` keyed on `STEP-02`'s fingerprint | D7: Sonnet-class by default, Opus-class for high-stakes files; a per-org daily dollar cap — the decider and R-1 have **none** today. A new L4 feature, `expert_review`, armed per tenant. Truncation detected via `stop_reason` (`2caf88aa`) |
| 3.4 | the output contract | new `contracts/expert_review.py` | the Atlas's `reasoning_result` shape (L2·O): `facts[{claim, evidence}]` · `inferences[{claim, based_on}]` · `hypotheses[{proposition, needs}]` · `unknowns[{question, relevance}]` · `frames{primary, rivals}` · `expected_vs_actual` · `scenarios{do_nothing, act, best, worst, signals_to_watch}` · `appraisal{stakes, urgency, reversibility, reasons}` · `mode` · `next_move{who, what, for_whom, by_when}` · `alternative` · `wait_or_stop` · `done_when` · `draft`. Schema-checked; one repair on syntax only, never on substance |
| 3.5 | into the decision, replayably | `reason/adapters/native.py`; `reason/decision_maker.py` | the validated result (after `STEP-13`) is injected into the snapshot as `expert.*` facts with evidence refs **before** execution, exactly as R-1 does. The decision maker reads them deterministically: `mode` → outcome; with D1 = A, `appraisal` → the importance and urgency inputs; the confidence comes from the validated evidence, never from the model. Persisted with the run → **replay recomputes without the model** |
| 3.6 | retire the per-sweep decider | `reason/llm_decision_maker.enabled_for`; `reason/orchestrator.py:252-263` | for a file the expert covers, the old decider and R-1 are not called. Elsewhere they stay behind `STEP-02`'s gate until each lane is covered |
| 3.7 | R-6 and R-2 | `reason/situation_reasoner.py`; `reason/bundle/` | R-6's persistence (`situation_interpretations`) becomes the expert's record — finally with a reader. R-2's prose is superseded by the expert's own explanation |

## 4 · What will happen — Insight Partners, 5 Oct

```
trigger      a meeting with insightpartners.com in 3 days, on a file with no judgment since 27 Sep
gate         fingerprint changed (the 3-days-to-meeting bucket) → one call
dossier      brief v3 · timeline: 27 Sep Neel → you; invite; 8 Oct call · open asks: ___ (from his mail)
             numbers: first contact · your investor reply time ___ (n = ___) · last mail to any investor 26 Aug (40 days)
             playbook (draft): first investor call at pre-seed — traction, team, why now, round; a pre-read helps
expert       frame: first call with a top-tier fund; rival: an exploratory chat with no fund intent
             unknown: does Neel lead deals at your stage?   scenarios: prepared vs unprepared
             appraisal: high stakes, time-bound, reversible  mode: decide
             next move: send a one-page pre-read by 7 Oct; alternative: send it after the call
             done when: the call happens and the agreed next step is logged
check        every claim cites the mail, the invite or a calculator (STEP-13)
lane         Decision (from the mode and the validated evidence)
card         one card, with the pre-read drafted — STEP-14
next sweep   nothing changed → no call (STEP-02)
```

## 5 · Expected

| Measure | Before | After |
|---|---|---|
| Golden must-detect (recorded cassettes) | measured in `STEP-01` | **≥ 90%** |
| Golden must-abstain | measured | **≥ 95%** |
| Forbidden outputs (self as subject, connector as target, invented number, recap of an unconfirmed meeting) | measured | **0** |
| Expert calls a day, this org | — | ~10–30, the files that changed `[MODELLED]` |
| Spend a day | ~$7 today | within D7's cap; ~$2–3 expected `[MODELLED]` |
| Replay of an expert-backed decision | — | identical, **zero** model calls |

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/reason/expert -q
#   the dossier is bounded and reports truncation; the checklist renders every section;
#   a schema-invalid answer is repaired once, a substantive one never; the injected facts make
#   replay_persisted return the same decision with NoLLM
.venv/bin/python -m pytest tests/replays -q                    # recorded cassettes
.venv/bin/python scripts/golden_eval.py --live --model <D7>    # the live scorecard, before any rollout
```

## 7 · Risks

| Risk | Guard |
|---|---|
| A fluent, wrong judgment | `STEP-13` checks every claim and every number before anything is shown |
| Cost runs away | the fingerprint (one call per change), the per-org cap, the overflow queue |
| The model drifts between versions | the cassette suite fails on any prompt change; a model change is a deliberate re-record with the live scorecard attached |
| Rule 02 of the Atlas | D1 — the amendment is explicit, and numbers, permissions and recipients still never come from the model |
