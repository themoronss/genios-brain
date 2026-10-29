# P1 · Orchestrator · 01 · What's exactly there

**The part:** what runs, when, for which business situation, in what order, at what cost. That covers the four loops (Onboard, Evolve, Act, Maintain), the triggers, the clock, the budget, and the record of each run. The Orchestrator never judges anything and never stores a conclusion.

**Read at:** `speedrun008` `71c50f56` for the product. The notebook is the local prototype (`Local Database (Rohit_Org_GV2)/notebook/nb/`).

---

## 1 · In the product: four things are called a sweep, and three of them reason

```
platform/scheduler.py      a daemon thread inside the API process, on an interval
  └─ api/routes.run_sync_sweep        capture: pull mail, calendar and other sources for every org
       └─ reason/runner.run_all       "L3 after the graph updates": one call per org per sweep
            1. goals: context/goals.sync_from_brief       (GeniOS-012 S28: the brief is the one door)
            2. THE EXPERT PASS, first                      reason/expert/sweep.expert_pass
            3. THE L2 JUDGMENT PASS, in shadow             reason/l2/sweep
            4. the domain compiler pass (cutover flag)     reason/domain_shadow + packs/compiler
            5. the legacy pack lanes                       reason/runner.run (rules per pack)
            6. narration                                   end of run_all
api /context/sweep, /cards/sweep (internal cron)          card_lifecycle.expire_lapsed, maintenance
api /context/reason (owner)                               the same run_all, on demand
```

### What each pass does

| Pass | File | When it looks at a file | What it writes | Budget |
|---|---|---|---|---|
| **Expert pass** | `reason/expert/sweep.py` (382 lines), `triggers.py` (200 lines) | Only when something changed. **first_look**: never judged. **new_evidence**: a mail, a meeting or a booking it hasn't seen. **date_closing_in**: the next meeting or promised date moved a rung closer. **reply_overdue**: their move, and the quiet passed their usual reply time. **past_normal**: a number crossed what is normal for the file. Nearest deadline first | Expert reviews that decide the file's situations for the compiled lane (`06` D1); cards of kind `expert.file_review` | Its own day budget, bounded per pass |
| **L2 judgment pass** (GeniOS-008) | `reason/l2/sweep.py` (567 lines), `plan.py` | Only the subjects a new L1 bundle touched since its watermark, plus evidence that was asked for and arrived (`new_evidence`) | `reasoning_results` with receipts, **in shadow**: "it writes NOTHING the lanes below read" | Depth from `plan.py`: shallow (1 call), standard (1–2), deep (up to 3) |
| **Domain compiler** | `reason/domain_shadow.py`, `packs/compiler` | Active L2 situations, per activated domain | Shadow packages; live only under `use_domain_compiler` | Shared |
| **Legacy pack lanes** | `reason/runner.run` (`runner.py` is 2,157 lines) | Every pack applied to the org (sales, general, admin, customer_support) | Signals → cards (the old rule cards) | The org's daily signal budget, shared across packs |

### The other "orchestrator"

`reason/orchestrator.py` (367 lines) is "Layer 4 · Part 1, the Reasoning Orchestrator". It is a deterministic scheduler for the 23 reasoning units of the compiled lane. It decides which units run, in what order, and what happens on failure. It does not schedule passes or loops. The same word means two different things in this repo.

### Activation and switches

The passes are turned on and off by a mix of settings and per-tenant rows:
- settings: `use_domain_compiler`;
- per-tenant rows: `l1_seam_enabled`, `platform/l3_activation.activated_domains`;
- L4 features: `expert_review`, `l2_reasoning`.

`reason/cutover.py` lists **seven** switches for the L2 cutover and warns that "any one alone leaves the system in a state that looks working and is not".

### The change gate and the record of what ran

- `reason/change_gate.py` skips a subject only when nothing its decision depends on has moved (the fingerprint is unchanged).
- `reason/fingerprint_store.py` keeps the fingerprints.
- `platform/daily_health.py` reports per tenant whether the scheduled sweeps ran.

### Measured in the copy (the [06](../06-MEASUREMENTS.md) queries, 28 Oct)

- **138 of 138** L2 runs were started by new mail; **none** by a date or by silence.
- The brain's own budget is about **$2 a day**, so about **12 files are judged a day**.
- **80 of 264** files have ever been judged.
- **16 of 20** re-judgments happened with no new mail in between.
- The intro platform's file was **stopped 31 times before starting** (too big), and was never judged.
- **Three card makers** ran in the same sweep: 38 cards from old signal rules, 33 from old situation rules, 31 from the brain (22 of those "held"), 1 other.

## 2 · In the notebook (the local prototype)

| Piece | File | What it does |
|---|---|---|
| Commands | `nb/cli.py` | `evidence`, `recover`, `company`, `parties`, `works`, `judge`, `relate`, `cards`, `export`, `scorecard`, `compare`, `update`, `all` |
| A build | `nb/config.BuildSettings` | One instant (`as_of`), one model, one budget cap, optional dry run. The first command that writes records the instant and the model; a different `--as-of` or `--model` is refused, so a different instant or model means a new build id |
| Order of `all` | `cli.run_all` | evidence → recover archived text → company page → parties → situations (works) → judge each situation → relate (goals, links, merges, plus two code-built situations) → judge again (merged, linked, new) → cards → export, scorecard, compare |
| Moving forward in time | `nb/update.py` | Takes a build to a later instant: places new threads, re-judges touched situations. It still uses its own **older copy** of the grouping rules |
| Model calls | `nb/llm.py` | One gateway. Every call is priced before it is sent (a worst-case reservation), logged in `notebook.runs` with its cost, retried on transient errors, and refused above the cap. The cap is summed over **all** builds |
| Concurrency | `judge.run(workers=N)` | N situations judged in parallel. Ours first (situations where we wrote or something was asked), then newest first |
| Clock | `BuildSettings.as_of` | Every read of mail and meetings is bounded by it; meetings ahead are visible only if the copy knew them by then (`known_at`). The time is shown to the model in **UTC only** |

### Measured on build `b2` (as of 23 Oct, 01:40 UTC)

| Step | Calls | Cost | Time |
|---|---|---|---|
| Company page | 1 | $0.096 | 1 min |
| Parties | 9 | $0.664 | 2 min |
| Situations (works) | 107 | $1.109 | 2.7 min |
| Judge, 378 situations, 8 workers (+ 12-situation sample and grammar probes) | 401 | $6.366 | about 25 min |
| Relate (+ 2 code-built situations judged) | 1 + 2 | $0.172 | 2.7 min |
| Judge again (10 situations) | 10 | in the judge line | 1.3 min |
| Cards, export, scorecard, compare | none | $0 | seconds |
| **Total** | | **$8.41** | about 40 min |

There is no scheduler, no trigger and no loop beyond the commands a person runs.
