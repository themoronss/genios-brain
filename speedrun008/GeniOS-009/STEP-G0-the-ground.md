# STEP-G0 · The ground — green CI, the L2 card path on one tenant, admission that decides existence

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Blocks:** G1–G9.

**Why first.** Every later step changes prompts, the card or the situation. On a red head we cannot tell
a regression we caused from one we inherited. A goal link on a shadow-only card path can never reach a
founder.

**Source (MD):** *"Pehle contracts, provenance aur context snapshots reliable… sophisticated reasoning se
reliability nahi milegi"* — the priority order P0 → P2 in the document's §12.


## At a glance

| | |
|---|---|
| **What** | Three things before any goal work: **(1)** CI green on `speedrun008`; **(2)** the L2 card path (`l2_cards`) live on one tenant; **(3)** L3 admission decides that a situation exists, for one type (investor intro / outreach). |
| **Why** | CI is red on `21b7ae10` (19 tests), and a red head hides whatever the next change breaks. The goal can reach a founder only through the L2 card path. The MD's core rule, *L2 proposes, L3 admits*, still runs in shadow only. |
| **For what** | So every later step is measured against a green baseline, and its output actually reaches a card. |
| **How** | Attribute each failure to the commit that caused it. Re-record the cassettes that missed (ideal reader, no spend). Fix the code defects: F13/F29 re-decided, the gate counter, the ladder timeout. Then switch `l2_cards` on for D6's tenant. Then make outreach situations **seeds** that only an ADMIT makes visible. |
| **What changes after** | CI is green. Rohit's org sees cards written by the L2 judgment. An investor-intro situation exists only after L3 admits it. The situation-writer ratchet goes 9 → 8. |
| **Done when** | CI green on the pushed head · `l2_score` loses 0 cases · one type admitted by L3 · decisions D1–D8 logged. |
| **Do not** | Edit a case's expectation · push on red · switch more than one situation type · turn `l2_cards` on for any tenant but D6's. |

---

## G0.1 · CI green on `speedrun008`

**Today** (run of 21 Oct on `21b7ae10`; `8ccf9a08` was green on all three jobs):

| Job | Failing test | Case | Error |
|---|---|---|---|
| golden-pg | `test_an_unchanged_sweep_costs_nothing` | F03 F07 F14 F24 | `CassetteMiss` at the expert site |
| golden-pg | `test_a_held_file_asks_once` | F03 F07 F14 F24 F55 F56 | `CassetteMiss` at the expert / r1 site |
| database | `test_a_dark_file_is_a_line` | F30 F55 | AssertionError + a cassette miss at r1 |
| database | `test_the_compiled_lane_skips_an_unchanged_subject` | F13 F29 | re-decided on an unchanged sweep |
| database | `test_the_gate_is_counted::test_the_compiled_lanes_skips_reach_the_sweep` | — | count mismatch |
| database | `test_the_ladder_never_starves_pg::…two_hundred_waiting_ones…` | — | statement timeout |

**How, unit by unit:**

| Unit | What | How | Done when |
|---|---|---|---|
| G0.1.a | Find which commit moved each prompt | For each missed key, run the case alone (`pytest tests/replays -k F03`). Bisect `8ccf9a08..21b7ae10` over these commits, which change prompt inputs: `0d5939d1` (junk prompt + re-records), `b8a8a43c` (open conflicts in block F), `e5eee70e` (need states in the fingerprint), `de795bb8`, `66c1f473`, `cfed4502` (R-9 reads the brief). | each miss is attributed to one commit, written in `03-LOG` |
| G0.1.b | Re-record the misses | `scripts/golden_eval.py --record F03 F07 F14 F24 F55 F56` (the ideal reader, no spend), then the resync and the door (memory: a-recording-replays-in-its-keys-frame). **Never edit a case's expectation to pass.** | `pytest tests/replays` green locally on a fresh DB |
| G0.1.c | F13 / F29 re-decided on an unchanged sweep | Compare the compiled lane's fingerprint inputs across the two sweeps (`reason/change_gate.py`, `fingerprint.py`); find the input that moves without new evidence. Suspects: `b8a8a43c` names conflicts in the fingerprint; `ae5b5c7a` changes derived `valid_from`. | fixed in code; the test unchanged |
| G0.1.d | Gate count mismatch | Read the expected vs actual dict in the failure; a new skip reason was added without its counter (`e5eee70e` A1–A3 moved the gate before the reads) | counter added with its reason |
| G0.1.e | Ladder statement timeout | `capture/` refetch ladder query on PG; check whether 0248's indexes were applied in the CI DB and whether the query plan uses them (`EXPLAIN`) | under the timeout, with the index used |

- **Verify:** push to `speedrun008`; read the run through the public API (memory: claude-pushes-and-keeps-github-synced). All three jobs must be green.
- **Owner:** D-question for Rohit — Harsh on `harsh/mvp`, or Claude on `speedrun008`. One writer per file.

## G0.2 · The L2 card path for one tenant (`l2_cards`)

**Today:**
- `l2_cards` needs `l2_reasoning` + `expert_review` + a live L3 domain, and is never on by default (`de795bb8`);
- measured 22 Oct (`01-AS-IS-CARDS` §1): 63/67 pass on both paths, the same four fail;
- **F15 regresses in shape on the L2 path**: 5 held investigation cards instead of the 1 expected.

**How:**

| Unit | What | Where |
|---|---|---|
| G0.2.a | **F15: one card for the investor wave, not one per fund.** The case expects exactly one card about all five funds (`expected.workstream`: *"investor wave — who to follow up, with what, who to close"*). It is `blocked_on` 03 F169 / 06 D57: each fund's file is reviewed once ("wait"), and its eight weeks of silence never again. Today's path makes 0 cards (the block); the L2 path makes 5 held cards (the same block, plus no wave grouping). The fix is the wave: one subject over the files of one kind with the same unanswered ask (`reason/l2/inputs.read_subjects` gains a *wave* subject). The file-level silence re-check is 06 D57's. **This is also the first goal-shaped card**: the wave belongs to the goal "Raise the seed round" (G3). Keep the case strict-xfail until the wave lands; never edit its expectation. | `reason/l2/inputs.py`, `reason/l2/sweep.py` |
| G0.2.b | **The held wording is an engineer's sentence**: *"We held the one we found: a fact your move rests on quotes nothing from the mail it cites."* Write it in the reader's words: *"I could not find the line in their mail that this move depends on — can you confirm…?"* | `reason/expert/verify.py` / `deliver/render.py` held copy |
| G0.2.c | Switch `l2_cards` on for **D6's tenant** (default: Rohit's org), with a one-line way back (`platform/l4_activation` off) | ops, `04-FOR-HARSH` |
| G0.2.d | One week side by side: `scripts/l2_shadow_report.py` + the funnel; no card that today's path shows may be missing on the new path | report in `03-LOG` |

**Verify:**
- `python -m tests.replays.l2_score` reports *"new path loses 0 case(s) today passes"*;
- F15 stays strict-xfail until the wave subject (G0.2.a) lands, then passes on the new path.

## G0.3 · Admission decides that a situation exists — one type first

**Today:**
- 9 writers in `context/` form a situation row before any reasoning (GeniOS-008 L3-2);
- `context/l2_admission.decide` runs in shadow, after the row exists;
- with no seed, a `create` is HELD at subject level.

**How** (GeniOS-008 `02-MIGRATION-PLAN` §4: "switch ONE situation type — awaiting reply / outreach first"):
1. For the **investor intro / outreach** type, `context/outreach_situations` stops writing `context_situations` directly. It writes a **seed** row (`status='seed'`), which is invisible to cards.
2. An ADMIT on the seed (create, update or unchanged) flips it to `active`. HOLD keeps it a seed with its reason; REJECT ends it (`archived`, `resolved_by='admission'`).
3. A `create` with no seed (subject-level HOLD today) mints the row on ADMIT.
4. The ratchet (`CI guard: situation writers`) drops from 9 to 8.

**Verify:**
- golden: every intro case (F03–F09, F37, F48, F59–F64) gives the same board;
- a PG test: a seed never reaches a card until admitted;
- a mutation proof: skipping the admission makes the seed visible, and the test catches it.

## G0.4 · Decisions

Rohit answers D1–D8 in [`08-DECISIONS.md`](08-DECISIONS.md), or the defaults stand.

## Done when

- CI green;
- `l2_cards` on for one tenant, losing 0 cases;
- one situation type admitted by L3;
- decisions recorded in `03-LOG`.

## Harsh's checklist — in order

1. **Start from `harsh/mvp` `21b7ae10`**, which is local `speedrun008` on Rohit's machine. `git log --oneline -1` must show it.
2. **Run each failing test alone** on a fresh scratch DB, e.g.
   `GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q tests/replays/test_an_unchanged_sweep_costs_nothing.py -k F03 -rfE`.
3. **Find the commit for each cassette miss:**
   `git bisect start 21b7ae10 8ccf9a08`, then `git bisect run <the single-case command>`.
   Write each `test → commit` pair in `03-LOG.md`.
4. **Re-record the misses** (no spend):
   `.venv/bin/python scripts/golden_eval.py --record F03 F07 F14 F24 F55 F56`.
   Then run the whole golden lane (handover §6.4). **Never edit an expectation.**
5. **F13 / F29 "re-decided on an unchanged sweep":**
   - print the compiled lane's fingerprint inputs for both sweeps (a temporary log, never committed) and diff them;
   - fix the input that moves without new evidence;
   - `tests/reason/test_the_compiled_lane_skips_an_unchanged_subject.py` must pass unchanged.
6. **The gate counter:** add the missing skip reason's counter (`tests/reason/test_the_gate_is_counted.py`).
7. **The ladder timeout:** `EXPLAIN ANALYZE` the refetch-ladder query on the CI-sized fixture; make it use 0248's indexes.
8. **Before pushing:**
   - root + platform guards: `pytest -q tests/test_*.py tests/platform`;
   - hermetic: `env -u GENIOS_TEST_DATABASE_URL pytest -q -m "not golden"`.
9. **Push** to `speedrun008` (fast-forward only); read CI (handover §6.7). **Stop here until all three jobs are green.**
10. **G0.2:**
    - the F15 wave subject, or keep F15 strict-xfail and log it;
    - fix the held-card wording;
    - `python -m tests.replays.l2_score` → `new path loses 0`;
    - switch `l2_cards` on for D6's tenant;
    - one week of `scripts/l2_shadow_report.py`, with the result in `03-LOG`.
11. **G0.3:**
    - outreach writes seeds; ADMIT flips them to active;
    - the PG test + mutation proof;
    - the ratchet list drops to 8;
    - golden intro cases unchanged.
12. **Update** `03-LOG`, `04-FOR-HARSH` (G0 row) and `00-START-HERE` (status).

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G0.1. Make CI green on `speedrun008` (head `21b7ae10`) without weakening any test.

**Read first:**
- the common preamble (`10-AGENT-BRIEFS.md` §1);
- `STEP-G0-the-ground.md` §G0.1;
- `.github/workflows/ci.yml`.

**You own:**
- the cassettes under `tests/replays/specs/founder/cassettes/` (re-recorded only through `scripts/golden_eval.py --record`);
- the code file(s) where F13/F29's moving fingerprint input lives (`reason/change_gate.py` / `reason/fingerprint.py`, or where you trace it);
- the gate counter's module;
- the ladder query's module;
- nothing else without saying why first.

**Do not touch:**
- any case JSON's `expected` / `forbidden`;
- any test assertion;
- `00-ARCHITECTURE.md`.

**Steps:** checklist items 2–8 above.

**Acceptance:**
- the six CI commands in `ci.yml` pass locally;
- every re-recorded case was re-recorded by the ideal reader;
- each fix has a mutation proof.

**Report:** the preamble's 6 points, plus the `test → commit` table.
