# Layer 1 — the eleven steps

> Read `ARCHITECTURE.md` first if you are new to Layer 1 — it is the map.
> Then `../README.md` for the working rules. `../STATUS.md` is the live state.

## The order, and why it is this order

Ranked by **measured size of the loss each one closes**, with dependencies respected — not by how
interesting the work is.

```
  1 OCR ─────────────────────────┐
     (12,13,14,15 hang off 3 and 4 — see the table)
  2 Bounce/DSN ─────────────────┐│
  3 Seam ───┬───────────────────┼┼──► 5 Coverage ──┐
            │                   ││                 │
            └──► 4 Typed claims ─┼┼──► 6 Domain ────┼──► 11 Replay harness
                      │          ││                 │
                      ├──► 7 Intent + predicates ───┤
                      ├──► 8 Importance + allocator ┤
                      ├──► 9 Directness ────────────┤
                      └──► 10 REVIEW outcome ───────┘
```

* **1 and 2 are independent** — they touch nothing else and can start immediately.
* **3 unblocks everything downstream.** Until the seam carries what L1 concluded, no later step's
  result is visible to Layer 2, so no later step can be measured end to end.
* **4 is the one that changes what L1 can represent.** Steps 7–10 all read better once claims are
  typed.
* **11 is last because it measures the other ten.**

## The steps

| # | File | Fixes | Effort | Engine |
|---|---|---|---|---|
| 1 | `step-01-ocr.md` | 159 attachments never read | hours | D |
| 2 | `step-02-bounce-dsn.md` | the benchmark's highest-value finding, deleted by design | days | D |
| 3 | `step-03-seam.md` | 8 values computed and dropped; 9 of 28 columns crossing | days | D |
| 4 | `step-04-typed-claims.md` | 7 untyped bags · 3 predicates · 48 of 49 refusals | weeks | D + L |
| 5 | `step-05-coverage.md` | no denominator — "we read N of M" is unsayable | days | D |
| 6 | `step-06-domain.md` | 815 of 889 events carry no domain | weeks | L proposes, R validates |
| 7 | `step-07-intent-predicates.md` | intent undebuggable; 4 signal types never fire | days | M + D |
| 8 | `step-08-importance-relevance.md` | every score < 4,700/10,000; 69 events unjudged | days | D |
| 9 | `step-09-directness.md` | hearsay weighs as first-hand | days | L proposes, D validates |
| 10 | `step-10-review-outcome.md` | no home for low-confidence-high-value | days | R |
| 11 | `step-11-replay-harness.md` | makes every step above empirical | weeks | D |
| 12 | `step-12-signal-states.md` | commitment fulfilment; BROKEN vs UNKNOWN | weeks | L detects, D commits |
| 13 | `step-13-identity-keys.md` | to/cc/bcc, attendees, meeting kind — P4's join | weeks | D + R |
| 14 | `step-14-temporal.md` | due/effective/resolved/superseded + reply pairs | days | D |
| 15 | `step-15-coverage-on-signal.md` | every negative claim carries its coverage | days | D |
| **16** | `step-16-source-field-coverage.md` | **fields never fetched — bcc, In-Reply-To, attendee status** | weeks | D |
| **17** | `step-17-adversarial-validation.md` | **39 scenarios · 20 failure classes · mutation + distribution + real Postgres** | weeks | D |

> **Step 16 is independent and should start early**, alongside 1 and 2. Every other step assumes
> the field is in the raw object; step 16 is the only one that checks. A field that was never
> fetched cannot be extracted, validated, scored or published — and it fails **silently**.

## The six numbers

These are the definition of "better". Every step moves at least one; a step whose number does not
move is not done.

| # | Metric | START | Target | Moved by |
|---|---|---|---|---|
| 1 | Attachments never read | 159 | 0 | step 1 |
| 2 | Columns crossing the seam | 9 of 28 | 24+ | step 3 |
| 3 | `relationship_change` surviving the floor | 1 of 49 | most | step 4 |
| 4 | Events with a non-fallback domain | 8% | set at step 6 | step 6 |
| 5 | Events never judged for relevance | 69 (31%) | <5% | step 8 |
| 6 | Benchmark objects present | 16 of 38 | 30+ | steps 2,3,4,5 → measured at 11 |

## The loop, once per step

```
MEASURE  →  PREDICT  →  CHANGE  →  RE-MEASURE  →  COMPARE
                                                     │
                            match ──► next step ◄─────┤
                                                     │
                            miss  ──► the MODEL of the system was wrong.
                                      Fix the understanding. Do not write
                                      more code against a wrong model.
```

The measurement command is the same every time, on the same frozen corpus:

```bash
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"
```

## Protected — every step obeys these

| Rule | Why |
|---|---|
| ALG-17's formula and its five weights are unchanged | the only measured quality gate L1 has; `return 5000` turns 16 tests red |
| `importance_bp` distribution holds: >50 distinct, p90−p50 > 1500 | G7's criterion |
| Integer basis points only; no float crosses a boundary | `contracts/publication.py` V-7 rejects them |
| No LLM on any scoring call path | doctrine 1 |
| No clock read inside `capture/validate/` | replay dies otherwise |
| No global boolean flags — every threshold is a per-tenant row with an owner and a date | `use_domain_compiler` was `False` in every environment while 152 capabilities sat unused |
| No working module is renamed | the group names are addresses, not a reorganisation |
| JEV is wired nowhere yet | it routes between engines; the engines must be measured first |
