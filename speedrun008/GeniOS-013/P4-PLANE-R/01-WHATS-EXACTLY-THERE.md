# P4 · Plane R (reasoning) · 01 · What's exactly there

**The part:** how a professional *thinks*:
- the model as the expert;
- the reasoning patterns it applies, with their conditions;
- the calculators that do the arithmetic it must not guess;
- the order in which it judges, and what wins when two rules disagree;
- the citations it must give;
- the patterns learned from this company.

It covers judging a business situation, judging a goal, and the correlate and analyse passes. Plane R never stores and never renders: P2 keeps, P5 shows.

**Read at:** `speedrun008` `71c50f56`.

---

## 1 · In the product, Plane R exists in three forms

### A · The 23 reasoning units: deterministic scorers in the compiled lane (`genios_engine/reason/reasoners/`)

| Group | Units |
|---|---|
| 1 · Situation understanding | context, timeline, dependency, constraint |
| 2 · Business evaluation | risk, opportunity, impact, priority, confidence |
| 3 · Optimisation | trade-off, resource, scheduling, cost, policy |
| 4 · Decision support | alternative, validation, recommendation |
| Supplementary | legacy rule, legacy score gate, temporal, relationship, signal composition, planning |

- They are scheduled by `reason/orchestrator.py` ("Layer 4 · Part 1") for capabilities that name them. They publish basis-point scores to the Decision Maker.
- Their principles are good and written. From the timeline unit: "without a declared cadence there is no such thing as overdue"; "no date is 0, never 5,000".
- **The model paths use one of the 23:** the expert pass imports `ConstraintReasoner`. The L2 pass uses none.

### B · Plane R's Groups 1–4, compiled into the expert's prompt (`reason/expert/prompt.py`, 248 lines)

- **The checklist "a 30-year chief of staff does, in order":**
  1. what is true;
  2. the frame and the rival frames;
  3. expected against actual, from the playbook's stage;
  4. patterns and counter-patterns, with their provenance;
  5. what is not known;
  6. the scenarios (doing nothing, acting now, the best, the worst, the signals to watch);
  7. the appraisal (stakes, urgency, reversibility);
  8. the mode;
  9. the next move, an alternative, when to wait or stop, what done looks like;
  10. the draft.
- **A rules list:** only what is printed; cite; quote exactly; ground every claim; no numbers of its own; the stage from the playbook; levels; mode; move; and **"the playbook is a prior about this kind of work, not a fact about this file"**.
- The L2 judge (`reason/l2/prompt.py`) builds on this prompt.

### C · The L2 tool gateway: calculators (`reason/l2/tools.py`, 115 lines, GeniOS-008 R7)

- "The arithmetic the model is never asked to do": how long since the newest signal, **whose turn it is**, the nearest due date and whether it has passed, how many of their messages wait behind our last one.
- Each result is printed under a `tool:` id, so the model can cite it and the check can hold a repeated number to its line.
- "This is where the 23 formula reasoners' useful arithmetic belongs … as EVIDENCE."
- It runs in the L2 pass, **which is in shadow**.

### Also in the product

- **The claim check** (`reason/expert/verify.py`, `contracts/claim_check`): it held **66 of 86** results (P2 F1).
- **`reason/l2/plan.py`**: how much to think (shallow, standard, deep), from measured inputs.
- **`reason/moments/`**: screen insights, follow-ups, reply drafts.
- **`reason/llm_sites.py`**: the register of every place a model is called.
- **Company patterns (L6, `packs/brains/`):** behaviour distillation, adaptive leases, organisation discovery. The founder's own numbers per stage ("yours", `stage_dwell`) are printed beside the playbook's prior in the expert dossier.

## 2 · In the notebook: one prompt, written by hand

| Piece | File | What it holds |
|---|---|---|
| Situation judge | `nb/judge.py` (SYSTEM) | The order of judging (who is involved → what it is and its stage → the questions, asks and promises, and whether a later mail settled each → claims → whose move → next expected → status → frame and summary → is the founder needed now). Rules on ids, quotes and absence. **Five "chief of staff" rules written into the prompt** (follow-up after a call is ours; an answer must answer; three unanswered = a decision; a renewal within 7 days = a decision; ask rather than assume), introduced as "apply it; **the playbook, when printed, is more specific**" |
| The page's shape | `nb/contracts.JUDGE_SCHEMA` | Fields in judging order. Trimmed to the largest shape the API compiles (6 unions; "" for empty text) |
| Relating everything | `nb/relate.py` | One model call over all 421 situations: goals, links, merges, and notes on the whole picture. Code finds two things on its own: numbers we told different people ("one number everywhere") and mail that never arrived |
| The check | `nb/checks.py` | P2's admission, change by change |
| Model | `nb/llm.py` | claude-sonnet-5, thinking off (production parity) |
| Calculators | none | The model reads dates in UTC and works out time, turns and gaps itself |
| Company patterns | none | |

**Measured on `b2`:**
- 377 pages judged, $5.85;
- 41 pages said the founder is needed;
- 115 changes held, the largest groups being "the closing mail is older than the opening" (14), "not printed" (13), "a claim of ours must come from our outbound mail" (11) and "the page itself cites this mail" (11).

The notes it wrote on the whole picture were good, for example:
- "the traction-number problem is systemic";
- "outbound mail is bouncing to at least 5 critical contacts";
- "the intro platform holds about 150 pieces of work, mostly stale";
- "several rejections invited reapplication, none actioned".
