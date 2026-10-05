# STEP-16 · TO BUILD · learning from you — your feedback and real outcomes change the next judgment

**Owner:** Claude. **Depends on:** `STEP-14`, `STEP-15`. **Moves:** a correction you make changes the
next decision on that file — and the change can be replayed and audited.

---

## 1 · What is true now

| | Evidence |
|---|---|
| Most feedback reasons cannot be saved | `[CODE]` 8 of 11 *"wrong because"* reasons return 500 — `migrations/0034:168, 189` allows only 3 |
| No feedback exists | `[PROD]` `card_feedback_verdicts` 0, `human_events` 0 |
| A learned preference has nowhere to go | `[CODE]` `user_model_proposals` has no writer; `user_models` has no reader in reasoning |
| Outcomes are not watched for founder plays | `[CODE]` an execution is monitored only when `success_events` is non-empty (`executive/execution.py:136-138`); compiled plays set none `[inference]` |
| The open lane waits for a person who is never asked | `[CODE]` review and promotion are on demand only (`capture/semantic/open_lane.py:36-39`, `api/admin_routes.py:792`); `[PROD]` 118 waiting |
| Calibration cannot run | `[CODE]` `feedback/calibrate.py:109` filters `card_level`, which `reason/authority.py:329` never projects — every weekly run errors (since 10 Sep) |
| Learning governance has three known stops | `[ATLAS]` Organization approval does not publish (`approved_unpublished`); a policy reload drops its block lists; an Adaptive proposal cannot carry an expiry — the Secret War audit's `RC-7` |

## 2 · Why

A 30-year expert is not born; she learns *your* company. Every correction should make the next
morning better — and nothing should be learned from a single click or a silence.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | every reason can be saved | migration (next free number) | the `0034` CHECK widened to all 11 reasons |
| 3.2 | feedback becomes a proposal, never a rule | `feedback/`; `user_model_proposals` | *"not useful — I never want Boardy's newsletters"* → a brief proposal; *"wrong — this is not an investor"* → a workstream correction. You accept; then it applies. One click is never enough to learn a pattern |
| 3.3 | outcomes close loops | `executive/collect.py`; `STEP-09` | a reply arrives, a meeting is booked, an application advances → the file's stage moves, the exact ask closes, the card resolves **with the outcome recorded** |
| 3.4 | patterns update | `STEP-10` | your reply time, Boardy's conversion, a program's typical stage time — recomputed from outcomes, in the behaviour brain, **observe-only** (Atlas V.3) |
| 3.5 | the open lane is reviewed weekly | the learning sweep (`api/routes.py:1310`) | recurring unclassified kinds are proposed to you as new stages or kinds; accepted ones flow into `STEP-11`'s playbooks |
| 3.6 | calibration repaired, in shadow — **moved ahead into tree `yc2_w27/M18`** (Rohit's "B1", 2026-10-05) | `reason/authority.py:329-332`; `feedback/calibrate.py`; `platform/l4_activation.py`; `api/routes.py` | the shadow switch lands before the column: `run_calibration(apply=False)` records `would_mute` / `would_recover` / `would_nudge` and writes nothing else; `calibration_apply` is fail-closed and not default-on. **Arming stays here**, after `STEP-18` B22–B24 (a muted rule's cards vanish unexplained; a mute never lifts; any applied mute or nudge hides every open card of the pack) and `06` D13 |

## 4 · What will happen

You mark *"not useful — Theresa asked for updates only with real news; don't push me"*. That
becomes one proposal: *Antler / Theresa: send only on a material milestone.* You accept it. From
then on her file is Monitor until a milestone lands in your mail — and the next brief says so
under *Watching*, not under *Needs you*.

## 5 · Expected

- every feedback reason saves (0 × 500);
- an accepted correction changes the next judgment on that file, provably (replay shows the delta);
- a resolved file records its real outcome;
- the open lane is reviewed every week.

## 6 · Verify

```
GENIOS_TEST_DATABASE_URL=… .venv/bin/python -m pytest tests/feedback -q      # the 27 tests that have never run, run
.venv/bin/python -m pytest tests/feedback/test_a_correction_changes_the_next_decision.py -q
```
