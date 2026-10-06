# 02 · The plan — sections → functions → components → units

**Written for:** Harsh and the coding agent. **Read `01-CROSSCHECK.md` first** — this plan covers only
what it found open. **Read `05-HOW-THE-EXPERT-THINKS.md`** for the design the units serve.

**Build order is bottom-up.** Units first, then the component that composes them, then the function,
then the section. A parent is never started before its children are green. Each unit names the
artifact it produces and one command that exits 0. *A skip is not a pass.* Every step's detail —
what is true, how, what will happen, expected, verify, risks — is in its own `STEP-nn` file; this
page is the map.

---

## The shape

```
YC-II W27 · GeniOS as a 30-year chief of staff
│
├── S0 · Ground truth          F0.1 one base ··········· STEP-00
│                              F0.2 the exam ··········· STEP-01
├── S1 · Remember everything   F1.1 stop re-deciding ··· STEP-02
│                              F1.2 the gate keeps ····· STEP-03
│                              F1.3 who is us ·········· STEP-04
│                              F1.4 into memory ········ STEP-05
│                              F1.5 no silent loss ····· STEP-06
│                              F1.6 the re-sync ········ STEP-08
├── S2 · The expert's desk     F2.1 the brief ·········· STEP-07
│                              F2.2 workstreams ········ STEP-09
│                              F2.3 the numbers ········ STEP-10
├── S3 · Expertise             F3.1 founder playbooks ·· STEP-11
├── S4 · The expert thinks     F4.1 the pass ··········· STEP-12
│                              F4.2 check and lane ····· STEP-13
├── S5 · What you see          F5.1 the card ··········· STEP-14
│                              F5.2 the morning brief ·· STEP-15
├── S6 · Learning from you     F6.1 ·················· STEP-16
└── SX · Across                FX.1 real tests ········· STEP-17
                               FX.2 known bugs ········· STEP-18
```

| Section | Functions | Units | Owner |
|---|---:|---:|---|
| S0 Ground truth | 2 | 9 | Rohit, Harsh, Claude |
| S1 Remember everything | 6 | 33 | Claude; Harsh runs two scripts |
| S2 The expert's desk | 3 | 25 | Claude; Rohit confirms the brief |
| S3 Expertise | 1 | 6 | Claude drafts, Rohit reviews |
| S4 The expert thinks | 2 | 13 | Claude |
| S5 What you see | 2 | 11 | Claude |
| S6 Learning from you | 1 | 6 | Claude |
| SX Across | 2 | 6 + 24 bugs (U-SX-00 and B17–B24 added on 2026-10-05) | Claude, Harsh |

---

## The dependency graph

```
STEP-00 one branch ──┬──────────────────────────────────────────────────────────────┐
                     │                                                              │
STEP-01 the exam ────┼── (runs from day one; every step is scored on it) ──────────┤
                     ▼                                                              │
               STEP-02 change gate        STEP-03 gate keeps ──┐                    │
                                          STEP-04 who is us ───┤                    │
                                                               ▼                    │
                                                    STEP-05 into memory             │
                                                               ▼                    │
                                          STEP-06 no silent loss   STEP-07 brief    │
                                                               └────────┬───────────┘
                                                                        ▼
                                                    STEP-08 re-sync (Harsh)
                                                                        ▼
               STEP-11 playbooks ······(drafting from STEP-03)······ STEP-09 workstreams
                                                                        ▼
                                                               STEP-10 the numbers
                                                                        ▼
                                                               STEP-12 the expert pass
                                                                        ▼
                                                               STEP-13 check and lane
                                                                        ▼
                                                     STEP-14 the card → STEP-15 the brief
                                                                        ▼
                                                               STEP-16 learning
STEP-17 real tests and STEP-18 known bugs run alongside, inside the step whose files they touch.
```

---

# S0 · Ground truth

> **What is true now.** Two branches have each fixed half of the same files; production runs the
> other one. The golden replays exist and test strings, not the engine (`01` §5 A14).
>
> **What must be true.** One deployed branch, a recorded baseline, and an exam that drives the real
> engine and cannot skip.

### F0.1 · One base — `STEP-00`

- **U-S0-01** push `speedrun008` · *owner* Rohit · *verify* `git ls-remote origin speedrun008`
- **U-S0-02** merge with `harsh/mvp`, full suite green · *owner* Harsh · *verify* `git rev-list --left-right --count` → `0 0`; `pytest -q`
- **U-S0-03** the baseline: `pipeline_health.py` + `scripts/workstream_funnel.py` outputs kept in `baseline/` · *verify* both exit 0 and their output is committed

### F0.2 · The exam — `STEP-01`

- **U-S0-04** ≥ 40 founder specs · `tests/replays/specs/founder/*.json`
- **U-S0-05** the engine-driving runner · `tests/replays/engine_runner.py` · *verify* refuses to run without `GENIOS_TEST_DATABASE_URL`
- **U-S0-06** `RecordedLLM` cassettes · `tests/replays/harness.py` · *verify* a cassette miss fails
- **U-S0-07** strict xfails made real · `tests/replays/test_golden_replays.py`
- **U-S0-08** Postgres in CI · `.github/workflows/ci.yml`
- **U-S0-09** scoreboard + live eval · `scripts/golden_score.py`, `scripts/golden_eval.py`
- *why this way* — the CP-0 rule of the Secret War audit: freeze fixtures and a measured baseline before changing the architecture, or nobody can tell whether intelligence improved

---

# S1 · Remember everything

> **What is true now.** ~27 of 395 mails and 2 of 34 meetings are in memory; 258 mails have no
> content; recovery is a flag flip; the model re-decides ~1,400 times a day on unchanged evidence.
>
> **What must be true.** Every kept item is in memory with its end state; nothing is deleted at the
> gate; nothing is re-decided without new evidence; *us* means the same thing everywhere.

### F1.1 · Stop re-deciding — `STEP-02`

- **U-S1-01** material fingerprint · `reason/fingerprint.py` · *verify* `tests/reason/test_material_fingerprint.py`
- **U-S1-02** fingerprint store · migration · *verify* applied on the scratch DB
- **U-S1-03** compiled-lane gate · `reason/domain_shadow.py`
- **U-S1-04** legacy-lane gate · `reason/runner.py`
- **U-S1-05** no model for shadow runs · `reason/orchestrator.py`, `reason/decision_maker.py`
- **U-S1-06** a DEFER keeps the card · `reason/runner.py:1116-1125`
- **U-S1-07** counter and health check · `platform/funnel.py`, `scripts/pipeline_health.py`
- *outcome* `l4_llm_decision` + `l4_llm_r1` ~1,400/day → < 100
- ✅ *built 2026-10-06* as tree block `yc2_w27_s02` (13 units, `STEP-02` §9). Not built: U-S1-05 —
  a shadow row skips when nothing changed, but still pays the model when its inputs do (§9.6)

### F1.2 · The gate keeps everything — `STEP-03`

- **U-S1-08** attention tier · migration + `capture/pipeline.py`
- **U-S1-09** noise becomes a feature · `capture/gate/rules.py`, `capture/connectors/composio.py`
- **U-S1-10** content kept for every tier, TTL from D4 · `capture/pipeline.py:179-187, 1609-1631`
- **U-S1-11** known people and connectors · `rules.py:269-284`, `composio.py:575`
- **U-S1-12** the AI filter decides attention, with the brief · `capture/gate/relevance.py` (after `STEP-07`)
- **U-S1-13** keep the S2 reason · `capture/gate/gate.py:133-135`
- **U-S1-14** promotion of archived mail · `capture/pipeline.py` + F1.4's re-run
- *outcome* new mail with its content deleted: 258 → 0
- ✅ *built 2026-10-06* as tree block `yc2_w27_s03` (17 units, `STEP-03` §9): U-S1-08 and U-S1-10
  built (an archive keeps its payload, **not** its prepared text — F57); U-S1-09 in part — the
  N-codes are now the archive's reason, `light_junk` still decides how much is fetched; U-S1-13 was
  already true in production (`llm_junk_unconfident` keeps its reason, `STEP-03` §8.2). Moved:
  U-S1-11 → `STEP-04`/`07`, U-S1-12 → `STEP-07`, U-S1-14 → `STEP-05`

### F1.3 · Who is us — `STEP-04`

- **U-S1-15** `platform/self_identity.py` · **U-S1-16** `org_self_identities` · **U-S1-17** one caller + AST guard · **U-S1-18** thread naming · **U-S1-19** repair script · **U-S1-20** card guard
- *outcome* cards with you as the subject → 0

### F1.4 · Every kept item enters memory — `STEP-05`

- **U-S1-21** left joins in `_pull` · **U-S1-22** the skeleton path + `skeleton` status · **U-S1-23** metadata-only memory for archived mail · **U-S1-24** meetings stay meetings · **U-S1-25** recovery is a real re-run · **U-S1-26** `scripts/reprocess_stranded.py` (Harsh runs) · **U-S1-27** screen follow-ups create weak people
- *outcome* ≥ 95% of kept items in memory; 34 meeting nodes

### F1.5 · Nothing lost silently — `STEP-06`

- **U-S1-28** item end-state view · **U-S1-29** `situation_outcomes` · **U-S1-30** `platform/card_lifecycle.expire_cards` + AST guard · **U-S1-31** red receipts · **U-S1-32** drain rotation
- *outcome* 0 items without an end state; 0 silent expiries

### F1.6 · The re-sync — `STEP-08`

- **U-S1-33** `scripts/refetch_dropped.py` (Claude writes, Harsh runs) · *verify* the read-only count of content-less mail events → 0

---

# S2 · The expert's desk

> **What is true now.** No prompt carries any company context; the work in motion has no
> representation; most of the numbers exist but none reaches a judgment, and your own reply time
> does not exist.
>
> **What must be true.** A brief you confirmed is in every prompt; every piece of work has one file
> with a stage, open asks and whose move it is; every number the expert sees is calculated and
> carries its provenance.

### F2.1 · The brief — `STEP-07`

- **U-S2-01** contract · **U-S2-02** composer over existing stores · **U-S2-03** the drafter (one Sonnet-class call, from patterns) · **U-S2-04** the confirm screen · **U-S2-05** in every prompt + AST guard · **U-S2-06** weekly diffs as proposals

### F2.2 · Workstreams — `STEP-09`

- **U-S2-07** workstream on existing tables · **U-S2-08** deterministic grouping, intro split per contact · **U-S2-09** the reader's proposal fields · **U-S2-10** the verifier · **U-S2-11** stages from playbooks, *proposed* until accepted · **U-S2-12** `ASK_KINDS` completed · **U-S2-13** weekly open-lane proposals · **U-S2-14** `GET /workstreams`

### F2.3 · The numbers — `STEP-10`

- **U-S2-15** timeline · **U-S2-16** latencies, yours included · **U-S2-17** cadence and silence from the full timeline · **U-S2-18** waves · **U-S2-19** bounces · **U-S2-20** per-connector rate · **U-S2-21** stage dwell · **U-S2-22** history read · **U-S2-23** base rates with provenance · **U-S2-24** coverage receipt · **U-S2-25** what-if wired

---

# S3 · Expertise

> **What is true now.** Fundraising expertise sits in Sales and can never be live; programs, intros,
> compliance and hiring have no situations; the consequence, success and window fields are runtime
> defaults.
>
> **What must be true.** Six reviewed capabilities in one founder domain, each passing its own cases.

### F3.1 · Founder playbooks — `STEP-11`

- **U-S3-01** fundraising · **U-S3-02** programs and applications · **U-S3-03** networking and intros · **U-S3-04** compliance · **U-S3-05** hiring · **U-S3-06** meetings (reuse Admin)
- each: situations, stages with durations, patterns and counter-patterns, wait and stop rules, playbooks, the three authored runtime fields, ≥ 10 cases
- *verify* `Domain Expertise/_tools/validate.py`; `tests/packs/test_the_corpus_answers_its_own_cases.py`

---

# S4 · The expert thinks

> **What is true now.** A per-sweep scorer with four messages of context; a context reasoner that
> has never run; no material-change gate; no claim check on a model's reasoning.
>
> **What must be true.** One strong-model judgment per changed file — framed, tested against
> patterns and history, with scenarios and a best move — checked sentence by sentence, replayable
> without the model.

### F4.1 · The pass — `STEP-12`

- **U-S4-01** dossier · **U-S4-02** thinking checklist from Plane R · **U-S4-03** `SITE_EXPERT_REVIEW` behind `RSiteGate` with a dollar cap · **U-S4-04** output contract · **U-S4-05** replay-safe injection · **U-S4-06** retire the per-sweep decider per covered file · **U-S4-07** R-6's table gets its reader

### F4.2 · Check and lane — `STEP-13`

- **U-S4-08** claim check · **U-S4-09** number check · **U-S4-10** role check · **U-S4-11** already-done check · **U-S4-12** lane via `reason/output_lane.route` · **U-S4-13** evidence needs consumed

---

# S5 · What you see

### F5.1 · The card — `STEP-14`

- **U-S5-01** one file, one card · **U-S5-02** living card with versions · **U-S5-03** gold shape · **U-S5-04** clean copy prompt · **U-S5-05** contract check · **U-S5-06** screen reminders (D8)

### F5.2 · The morning brief — `STEP-15`

- **U-S5-07** the day's inputs · **U-S5-08** ordering with guard rails · **U-S5-09** the summary ladder · **U-S5-10** delivery (D9) · **U-S5-11** feedback per line

---

# S6 · Learning from you — `STEP-16`

- **U-S6-01** every reason saves · **U-S6-02** feedback → proposals · **U-S6-03** outcomes close loops · **U-S6-04** patterns update, observe-only · **U-S6-05** weekly open-lane review · **U-S6-06** calibration repaired, in shadow

# SX · Across — `STEP-17`, `STEP-18`

- **U-SX-00** the database suite green — **first**, added by the `STEP-00` re-do (`STEP-17` §3.0; now the 16 units of tree `yc2_w27/M16`) · **U-SX-01** Postgres in CI (in `STEP-01`) · **U-SX-02** every statement `EXPLAIN`ed · **U-SX-03** write paths that cannot write · **U-SX-04** health gate in deploy · **U-SX-05** this folder's step-status test
- the bugs of `STEP-18`, each with its probe — B1–B16 from the analysis, B17–B19 from the `STEP-00` re-do, B20–B24 from the root-cause runs of 2026-10-05
- ⛔ **the next block is in `tree.yaml` as `yc2_w27`** — M16 (database suite), M17 (B17–B20), M18 (B1, in shadow), M19 (`STEP-01`); 43 units, proposed, awaiting Rohit's go (`00-START-HERE.md`)

---

## Phase exits — what must be true before the next phase starts

| After | Exit gate |
|---|---|
| S0 | one branch deployed; baseline kept; `golden_score.py` prints a before-score |
| S1 | 0 deletions at the gate; ≥ 95% of kept items in memory; 0 re-decisions without new evidence; 0 self-subject cards; re-sync done |
| S2 | brief accepted; every brief workstream has one file; every number in a dossier traceable |
| S3 | six capabilities accepted, cases green |
| S4 | golden must-detect ≥ 90%, must-abstain ≥ 95%, forbidden 0 — on cassettes **and** in the live eval |
| S5 | 0 duplicate cards per subject; the morning brief runs daily |
| S6 | a correction provably changes the next judgment |

## Cost — what the model will do, and what it will cost `[MODELLED]`

| Site | Today, calls a day | After | Model |
|---|---:|---:|---|
| the per-sweep decider + R-1 | ~1,400 | **0** for covered files | — |
| the AI filter | ~250, one mail at a time | 5–20, ambiguous middle only, batched, with the brief | Haiku 4.5 |
| reading (`l1_extract`) | ~70 | 20–40 — every `deep` item once | Haiku 4.5 |
| **the expert pass** | 0 | **10–30** — changed files only | Sonnet-class; Opus-class for high stakes (D7) |
| the morning brief | 0 | 1 | Sonnet-class |
| card copy, R-2 narrator | ~50 | 0–30 — folded into the expert's output | Haiku / — |
| screen, relevance, resolution — unchanged | ~240 | ~240 | Haiku 4.5 |
| **total** | **~2,000** | **~250–300** | ≈ **$2–3 / day** (vs ≈ $7), list prices as in `04` §2.9 |

## What this plan deliberately does not do

- **Activate Sales or Support.** The founder domain is its own (`06` D2).
- **Hand any decision to a formula.** The deterministic decider stays what it is — a fallback and a
  replay mechanism, not the judge.
- **Let the model produce a number, a permission or a recipient.** Every number is calculated; every
  send needs your approval.
- **Turn on autonomous sending or agent handoff.** The expert drafts; you send. The agent handoff
  stays HTTP 501 until its own protocol exists (Secret War replay 08).
- **Author every capability at once.** Six, deep, each passing its own cases — the audit's own
  warning against volume before quality.
