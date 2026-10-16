# STEP-13b · TO BUILD · the GeniOS Engine in the expert's hands — data, engine and its own expertise, cheap models first

**Owner:** Claude. **Decision:** `06` D64 (Rohit, 12 Oct: go — planned after STEP-13 closes, built after STEP-14).
**Depends on:** `STEP-13`; built after `STEP-14`, `STEP-16` and `STEP-15` on the files they share (§8.5).
**Moves:** the share of a cheap model's reviews the check holds **79% → under 50%**; the authored answers whose
dossier prints an engine line **22 → at least 57 of 94**; every review line says whether it came from the file, the
engine or the expert's own experience; a stronger model is asked only when a cheaper one's answer fails the check.

---

## 1 · The ask, and what is true now

Rohit, 12 Oct: *"hme genios model agnostic banana hai... haiku and sonnet se bhi best results mil jaye.... in case opus
is needed then results better aaye....but jarruat kam pade costly models ki ... GeniOS Engine ka matlab domain
expertise graph (all parts) and reasoning expertise graph ... aur inke sath LLM hoga and Data Sources honge ... LLM
parallely GeniOS Engine & Data & khud ki reasoning se results dega... na ki sirf GeniOS Engine me jo likha hai utna
hi".*

In the product's words: L2's expert (`reason/expert`, Plane R's one review per file) reasons from **three sources at
once** — the file's **data** (L1 Signals and the L3 Context Graph, as its dossier), the **GeniOS Engine** (L2 Plane D's
Domain Expertise — `packs/` — and Plane R's Reasoning Expertise — the reasoning units, `reason/reasoners`) — and its
**own** thirty years, each labelled, so the check verifies what is checkable and you see where every line came from.
Cheap models first; Opus only when needed.

| | Claim (the brief) | Evidence |
|---|---|---|
| 1 | the prompt opens with `_ONLY` — *"Use only the dossier. What you know of the world is not evidence about this file."* | `[CODE]` `reason/expert/prompt.py:66`, first of `RULES` `:94-95`; `PROMPT_VERSION` `expert-review.v3` `:49` |
| 2 | the dossier carries the mail and meetings, people, numbers, history, what-if, the kind's playbook and your answers — not the capabilities, rules, patterns or constraints of the file's situations, nor the units' outputs | `[CODE]` `reason/expert/dossier.py:61-71` (sections), `:560-595` (`read_parts`), `:577` (`playbook_for(work.work_kind)`) |
| 3 | the check verifies facts against dossier lines by id; an inference or pattern is labelled; the model's own knowledge has no labelled channel (crosscheck X53) | `[CODE]` `reason/expert/verify.py:838-893` (`_fact`), `:895-904` (`_grounds`); `contracts/expert_review.py:80, 445-458` |
| 4 | the model and its sites: R-7, Sonnet-class, $2 a day (D7); `golden_eval.py --live --site expert --model <id> --spend-ok`; D65 up to $20 | `[CODE]` `reason/bundle/sites.py:42-46, 56-64`; `reason/bundle/budget.py:54`; `scripts/golden_eval.py:1-30, 115-140`; `06` D7, D65 |
| 5 | STEP-14 owns `dossier.py`, `verify.py`, `review.py`, `decide.py`; STEP-16 `prompt.py`, `fingerprint.py`, `triggers.py`; STEP-15 also touches the expert | `[PLAN]` `baseline/yc2w27-s14/tree_s14.yaml`, `-s16/tree_s16.yaml`, `-s15/tree_s15.yaml` |
| 6 | the Domain Expertise is `packs/compiler.compile(bso, context_slice)` in `reason/domain_shadow` | `[CODE]` `reason/domain_shadow.py:1711` |
| 7 | the Reasoning Expertise is the 21 reasoning units | `[CODE]` `reason/reasoners/__init__.py:44-60` (17 core + Temporal, Relationship, SignalComposition, Planning) |

## 2 · Why

A cheap model fails a strict check in ways a strong model does not, and the first live pass says how: **not in its
judgment, in its format** (§8.1). The engine already knows what a professional knows about an investor, a programme,
a filing — and the expert reads only the kind's playbook, on 22 of 94 authored answers' files. And when the expert
knows something no line of the dossier says, the check has no place to put it but the bin. Rohit's direction asks
for all three, labelled: that is what makes a Haiku review checkable and a Sonnet review rarely necessary.

## 3 · How

| # | Unit | Where (layer) | What |
|---|---|---|---|
| 3.1 | every data line citable | `reason/expert/dossier.py` (L2 reading L3) | the file's head, each line of the brief, what was checked, each section's "none", and what the company said of itself on another file (`06` D63) carry ids |
| 3.2 | the engine for a file | new `packs/compiler/engine_reader.py` (L2 Plane D), new `reason/expert/file_units.py` (Plane R) | the Domain Expertise of the file's situations and kind — read ungated, labelled (D3) — and the situation-level units' readings, in two dossier sections, each line an id |
| 3.3 | the expert's own | `contracts/expert_review.py`, `reason/expert/prompt.py` | `own` lines — practice, base rate, counter-pattern — in words, never a fact, never a number; inferences and patterns may rest on engine and own lines; the move may rest on an inference |
| 3.4 | the check reads three sources | `contracts/claim_check.py`, `reason/expert/verify.py` | engine ids held as evidence ids; a fact resting only on the engine or on itself drops; every line labelled data · engine · own; a line cited by its words resolves to its id; the advice's own timing is the advice's |
| 3.5 | an engine change re-thinks a file | `reason/expert/fingerprint.py`, `triggers.py`, `sweep.py` | the fingerprint names the engine the file reads and the ladder, not the model; `engine_moved` and `self_moved` triggers; a version change keeps a file covered |
| 3.6 | cheap models first | `contracts/model_ladder.py`, `reason/expert/ladder.py`, `reason/bundle/sites.py`, `budget.py`, `migrations/0250` | Haiku → its answer repaired once with the check's verdicts → Sonnet → (Opus, D1); every attempt kept and counted, one day's budget |
| 3.7 | every model scored | `scripts/golden_eval.py` | the live scorecard per model and for the ladder: board, fates, drop reasons, misquote rate, engine and own lines, cost; a kept pass re-judged with no spend |

## 4 · What will happen

| Today (Haiku 4.5, the live pass of 12 Oct) | After |
|---|---|
| F10 — *"Is it so: 'The file's whose_move is ours: we owe the reply'? It is not in what it cites."* The fact cited `Whose move: ours` by its words; the move is held, the file asks you a question it already answered | the head line is `[file:whose_move]`; the fact cites it; the move to write to Kiran stands on it |
| F10's pattern cites *"Gompers, Gornall, Kaplan & Strebulaev, NBER Working Paper 22587"* — dropped, ungrounded | an `own` line — for instance *"a fund that liked the first call and goes quiet has usually decided"* — labelled *from experience*, beside the engine's `[pb:…investors_do_not_chase]` |
| F52's file asks *"Check the current count of paying customers against Gautam's bar of ten"* — your own 12 Sep mail to Nandini says *"we crossed 12 paying customers"*, on another file | that mail is `[self:…]` in Ridgeline's dossier; the file is reviewed again (`self_moved`); the move is to tell Gautam the bar is met, quoting both |
| 26 authored answers' files hold an investor situation and print no playbook — the brief names no kind for them | the investor capability's failure modes (*"Treating a pass as terminal"*), its playbooks and heuristics are in the engine section, each `[cap:…]` / `[pb:…]`, "not yet reviewed" |
| a held Haiku review is a question to you | it is asked once more of Haiku with what the check dropped; then of Sonnet; you see the question only when both fail |

## 5 · Expected

- on the golden set (no spend): every authored answer stands; **≥ 57 of 94** authored answers' dossiers print an engine
  line (22 today); every investor file prints the investor playbook; forbidden **0**, must-abstain **13/13**,
  must-detect never backwards;
- on the live passes (`06` D65): Haiku's held share **< 50%** (68 of 86 valid today); `unknown_evidence` drops
  **430 → < 50**; the ladder's must-detect **≥** Sonnet-alone's at a lower cost per review; forbidden **0** on every model.

## 6 · Verify

```
.venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s13b/validate_tree_s13b.py"            # the block parses, every dependency resolves
GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q \
    tests/replays/test_the_engine_is_in_the_experts_hands.py tests/replays/test_cheap_models_first.py
.venv/bin/python scripts/golden_eval.py --assert-scorecards "speedrun008/YC-II W27/scores/s13b.json"   # the lead's kept live passes meet §5
```

---

## 8 · The check of 2026-10-12 — what exists, and the design

Checked claim by claim against `yc2w27-s13b-plan` @ `d3c1bb3c` (the integration line: STEP-13 with its fixes, STEP-17,
STEP-18), by reading the code and running it on fresh scratch databases (pg2, 55433: `s13b_live1`, `s13b_units2`,
`s13b_f52`, `s13b_f52b`, `s13b_golden`, `s13b_golden2`, `s13b_golden3`). No model was called; production was not read.
The scripts are in `baseline/yc2w27-s13b/`: `replay_live_pass.py` (a kept live pass replayed with no spend, read back
from `expert_reviews`), `measure_engine_reach.py` (the 94 authored answers against the corpus), `measure_units.py`
(the compiled lane with the expert off) and `validate_tree_s13b.py`.

### 8.1 · Measured

**The first live pass — Haiku 4.5 on the expert site, every other site from its cassette, at `7d88ef25`** (the lead's
run: 19 pass / 28 fail / 11 not expressible, recall 0.235, precision 0.693, 2 forbidden, $2.17; `scores/2026-10-12-
claude-haiku-4-5-20251001-expert.json` in the s13-lanes worktree), replayed here from its kept answers (56 of 58 cases
replay; F14 and F45 miss at the expert site; every replayed verdict equals the scorecard's). The lead's own replay
(`scratchpad/live/haiku_fates.json`) agrees in every count.

| | |
|---|---|
| reviews | **92**: 86 valid, 3 refused (nothing stands), 3 failed (a proposed kind still malformed after its repair) |
| fates of the 86 valid | **68 held**, 18 shown — act 47 (42 held, 5 shown), find out 27 (26 held), wait 12 (all shown: no move to hold) |
| why held | **42** a fact the move rests on cites something the file does not show · 11 a number · 10 a name · 3 the move's words · 2 unquoted |
| the 42 | every one fell ONLY on dossier lines that carry no id, cited by their words (a fact may cite several kinds): a section title 17 (`THE FILE` 76 times across all facts, `WHAT WAS CHECKED` 30), a head line 10 (*"Kind of work: not named by the brief"*, *"Whose move: ours"*, *"We have not written in this file"*, *"No playbook for this file: …"*), the brief 7 (`cb-98491dabb34d` 33 times, *"Raise · Banyan Seed Fund — written to in the seed wave"*), the mailbox 7 (`conn_golden_gmail` 33), the dossier's version 5 (`dossier.v1` 43) |
| lines dropped | 430 `unknown_evidence` (288 facts, 74 proposed kinds, 58 `rests_on`, 10 `answers`) · 142 `wrong_number` (47 doing-nothing, 22 facts, 20 moves, 20 drafts, 18 done-whens, 15 situations) · 78 `unsupported` (*"UTC"*, *"API"*, *"Two"*, *"Done"*, *"By"*, *"Silence"*, *"Log"* read as invented names) · 68 + 55 inferences and patterns ungrounded |
| `rests_on` | 55 of 58 drops name an **inference** (`inference:2`); two name an engine heuristic (`pb:…investors_do_not_chase`) — the contract admits `fact:N` only (`expert_review.py:245-253, 490-494`) |
| its own knowledge | patterns citing *"Gompers, Gornall, Kaplan & Strebulaev, NBER Working Paper 22587, 2016"*, *"professional knowledge of investor behavior"*, *"professional practice in business development"* — all dropped; **164** base-rate patterns (the authored answers: 36) |
| modes, over 110 answers | find out **40** (authored 8 of 94), act 58, wait 12, nothing **0** (authored 8) |
| tokens | 615,718 in, 310,052 out; median out **2,729**, max **3,990** of the 4,000 ceiling (12 answers over 3,500; the ceiling was sized for 800-1,600, `sites.py:92-98`) |
| the same volumes at other prices | Sonnet-5 **$4.33**, Opus-5 **$10.83** (the dry run's ideal-reader estimate: $2.17 and $5.44, `golden_eval.py --dry-run --site expert --model …`); the costliest of the 110 answers would cost **$0.151** at Opus prices, over the expert's $0.10 per-call ceiling |

So for a cheap model the gap is **format and the check's reading of advice prose, not judgment** (the lead's reading of
the same rows, 12 Oct): of 47 *act* reviews 42 are held, and 42 of the 68 held fell on a line the dossier gave no id.

**The authored answers against the engine** (`measure_engine_reach.py`, no database): 94 answers over 53 cases, 66 files.

| | |
|---|---|
| cite an engine line today | **22** — the kind's playbook (`pb:`), on the 22 files whose brief line names a kind (investor 7, program 15); 72 print no playbook |
| would print one, lower bound | **57** — the kind's capability doctrine, or a situation routed to a corpus situation with no predicate (43: `account_admin` → `admin.sit.live_account_admin`, `admin_contact` → `admin.sit.live_admin_contact`) |
| would print one, upper bound | **79** — a situation routed to an owner capability in a switched-on corpus, predicates aside (83 with `also_serves`) |
| an investor situation and no playbook | **26** — `investor_relationship` routes to `founder_office.fundraising.investor_relations` (predicate `absent: commitment.due_at`), whose spine is the investor playbook; the dossier reads the playbook by the brief's kind only |
| routed only to a switched-off corpus | 5 (Sales `opportunity`, a support case); neither the kind nor a live route: 11 |
| by case — answers · today · lower · upper | F01 1·0·0·1 · F02 3·0·3·3 · F03 1·0·1·1 · F04 1·0·1·1 · F05 2·0·2·2 · F06 2·0·2·2 · F07 2·0·2·2 · F08 2·0·2·2 · F09 1·0·0·1 · F10 1·1·1·1 · F11 1·1·1·1 · F12 1·1·1·1 · F13 1·1·1·1 · F14 2·2·2·2 · F15 15·0·0·15 · F16 1·0·0·1 · F17 2·2·2·2 · F19 2·2·2·2 · F20 1·1·1·1 · F21 2·2·2·2 · F22 1·1·1·1 · F23 2·2·2·2 · F24 3·3·3·3 · F25 2·0·0·0 · F26 1·0·0·0 · F27 1·0·0·0 · F28 1·0·0·0 · F29 2·0·2·2 · F30 1·0·0·0 · F31 1·1·1·1 · F35 1·1·1·1 · F36 1·0·0·0 · F37 1·0·0·1 · F38 1·0·1·1 · F39 1·0·1·1 · F40 1·0·1·1 · F41 1·0·1·1 · F42 1·1·1·1 · F43 1·0·0·1 · F44 1·0·0·1 · F45 2·0·2·2 · F46 1·0·0·1 · F47 1·0·0·1 · F48 2·0·2·2 · F49 1·0·1·1 · F50 1·0·0·1 · F51 1·0·1·1 · F52 2·0·0·1 · F53 2·0·0·0 · F54 5·0·5·5 · F55 4·0·2·3 · F57 2·0·2·2 · F58 1·0·1·1 |
| what the authored answers cite | facts: `evt` 225, `num` 142, `sit` 84, `hist` 71, `loop` 54, `pb` 22; patterns: `pb` 57, `hist` 28, `num` 28, `wave` 15; 54 of 101 patterns cite the playbook |

**The compile and the units, with the expert switched off** (`measure_units.py`, the ideal reader, six cases — F01,
F02, F24, F45, F52, F55): of **33** admission decisions the L2 publisher admitted **3** (F02's two `account_admin`, one of
F24's) and HELD 30 — `verified_evidence_required` on 28, `qes_required` on 11 (a decision may carry both) — and a held
situation never reaches `compiler.compile` (`reason/domain_shadow.py:1678`, `if not publication.admitted … continue`).
Packages: **2**, on F02 only. The units ran on F02's two compiled situations (14 of 18 completed; Opportunity, Resource, Scheduling and Timeline skipped,
`no_declared_input_available`) and through the legacy lane on F24, F52 and F55 (Relationship and Temporal
`insufficient_context`). On F01 and F45 — an investor file each — nothing compiled and no unit ran. With the expert on,
a covered situation stands down even before that (`:1688-1693`).

**The golden lane on the integration line.** `tests/replays/test_founder_cases.py` at `d3c1bb3c` on a fresh database:
**53 failed, 180 passed, 1 xfailed** — every case with an expert answer; those read (F02, F10, F37, F45, F52) miss
their cassette at the expert site. The s13-lanes line holds a fix and a re-record after the live pass's commit
(`fb45cfd1`, `8acb8377`) that the integration line does not. The cause is not established here (s13b-F15).

### 8.2 · The claims

| # | Claim | Now | Evidence |
|---|---|---|---|
| 1 | the prompt opens with `_ONLY` | **true** — the first rule; the prompt opens with the role and the dossier | `prompt.py:57-66, 94-95, 220-232` |
| 2 | the dossier lacks the capabilities, rules, patterns and constraints of the file's situations, and the units' outputs | **true, and narrower than that**: it carries the KIND's capability's playbooks and heuristics as `pb:` (22 of 94 answers' files) and nothing of any situation's capability; nor that capability's doctrine — its question, outcomes and failure modes are printed nowhere (`playbook_reader` reads stages, moves and heuristics only); and its own head, brief, coverage and "none" lines carry no id, so they cannot be cited at all (§8.1) | `dossier.py:200-231, 288-290, 341-372, 375-415, 577`; `packs/compiler/playbook_reader.py:206-263` |
| 3 | facts checked by id; inferences and patterns labelled; own knowledge unlabelled (X53) | **true** — an inference or pattern rests on dossier ids or `fact:N`, else drops `ungrounded`; there is no own channel. *Crosscheck X53* is in no branch (`git log --all -S X53`: empty) — the claim is verified from the code, not from the crosscheck | `verify.py:838-904`; `expert_review.py:80, 190-200, 445-458` |
| 4 | R-7, Sonnet-class, $2/day; the live command; D65 $20 | **true** — and "no Opus tier exists, and none is added" is written into the site's comment and pinned by three tests; the per-call ceiling is $0.10 | `sites.py:42-46`; `tests/reason/expert/test_the_expert_site_and_feature.py:30-33`; `test_tiers_and_the_cache_key.py:65`; `tests/reason/test_llm_policy.py:250`; `budget.py:54` |
| 5 | STEP-14 owns four files, STEP-16 three, STEP-15 touches the expert | **partly** — STEP-16 also edits `dossier.py` (M46.C4.U03, M47.C2.U02), `verify.py` (M46.C4.U06) and `claim_check.py` (M46.C4.U01) and takes `expert-review.v4`; STEP-15 edits `reason/expert/store.py` (M44.C2.U01), `reason/bundle/sites.py` and `budget.py` (M45.C1), `scripts/golden_eval.py` (M45.C5.U01) | the three baseline trees |
| 6 | the Domain Expertise is `compiler.compile(bso, context_slice)` | **true as code, never reached by the expert**: the expert runs first in the sweep (`reason/runner.py:1899-1917`); a covered situation stands down before the compile; a held one never gets there — 3 of 33 admission decisions admitted on six golden cases, 2 packages. And the Founder Office capabilities are drafts, so on the live (admission-gated) compile they never route | `domain_shadow.py:1676-1693, 1711`; `capability_resolver.py:595-760`; `Founder Office Expertise/…/capability.yaml` (`status: draft`) |
| 7 | the Reasoning Expertise is the 21 units | **true** — and they run only inside a compiled or legacy reasoning run, never for a file | `reasoners/__init__.py:44-60`; §8.1 |

### 8.3 · New — findings

Provisional ids; the lead mints the `03` numbers.

| Id | Finding | Evidence | Owner |
|---|---|---|---|
| s13b-F1 | **A cheap model's reviews are held for format, not judgment**: 68 of 86 valid Haiku reviews held, 42 on a fact citing a dossier line that has no id — the head, the brief, the coverage, a section title, a mailbox | §8.1; `dossier.py:205-231` | M37.C3.U01, M37.C4.U04 |
| s13b-F2 | **A move may rest on facts only**: 55 of Haiku's 58 `rests_on` drops name an inference, two an engine heuristic | `expert_review.py:245-253, 490-494` | M37.C1.U02 |
| s13b-F3 | **The expert's own knowledge is thrown away**: patterns citing a paper or "professional knowledge" drop `ungrounded`; 164 base-rate patterns to the authored 36 | `verify.py:895-904` | M37.C1.U02, C3.U04, C4.U01 |
| s13b-F4 | **The check reads ordinary words as invented names**: *UTC, API, Two, Done, By, Silence, Log* — 78 lines `unsupported` | `verify.py:107-121` (`EARNED`) | M37.C4.U02 |
| s13b-F5 | **The advice's own timing reads as a claim**: 142 `wrong_number`, 87 of them in doing-nothing, the move and its draft (*"within 24 hours"*) | `verify.py:945-952` | M37.C4.U05 |
| s13b-F6 | **A deploy that moves the prompt or dossier version AND the check version together uncovers every untouched file**: the fingerprint moves (no row), nothing triggered, and a last review checked under the old version is counted `unchecked` and handed back to the compiled lane — STEP-14 (`check.v2`) and STEP-16 (`expert-review.v4`) would do it together | `sweep.py:161-174, 184-191` | M37.C5.U03 |
| s13b-F7 | **No engine reaches a covered file — and almost none reaches any file**: covered situations stand down before the compile; held ones never get there (3 of 33 admission decisions admitted, six cases); packages and compiled units on one case | §8.1; `domain_shadow.py:1678-1693` | M37.C2 (read ungated, by route) |
| s13b-F8 | **The playbook is read by the brief's kind only**: 26 answers' files hold an investor situation routed to the investor capability and print no playbook | `dossier.py:577`; §8.1 | M37.C2.U01 |
| s13b-F9 | **The capabilities' doctrine is printed nowhere** — the investor capability's six failure modes (*"Reading the relationship as a deal"*, *"Treating a pass as terminal"*, *"Single-threading a fund"*) never reach the expert | `playbook_reader.py:206-263`; `investor-relations/capability.yaml` | M37.C2.U01 |
| s13b-F10 | **The fingerprint names the model** — a ladder would re-key a file per rung | `fingerprint.py:91-92`; `sweep.py:157-158` | M37.C5.U01 |
| s13b-F11 | **D48 as answered and the triggers disagree**: Rohit's answer reviews a file again "when its dossier changed"; the brief's, playbook's and prompt's versions ride along (tested); and STEP-13's own unit text says a prompt change re-reviews every file | `triggers.py:21-25`; `test_a_review_says_what_triggered_it.py:81-88`; `tree.yaml` `yc2_w27_s13/M35.C3.L-interface.V0.U04` | M37.C5.U02 |
| s13b-F12 | **An Opus rung contradicts D7 and two ceilings**: no Opus tier (three tests); $0.10 a call, under Opus's measured worst case $0.151 | §8.2 claim 4 | M38.C1.U02, U03 (s13b-D1) |
| s13b-F13 | **The expert's output ceiling is near its measured answers**: median 2,729, max 3,990 of 4,000; the sizing said 800-1,600 — engine sections and own lines push it further | `sites.py:92-98`; §8.1 | M38 (ceiling per rung, measured on the post-s13b pass) |
| s13b-F14 | **The company's own record reaches no file** (D63, F52): your 12 Sep *"we crossed 12 paying customers"* is on Vertex's file, and Ridgeline's asks you for it | `tests/replays/specs/founder/F52.json`; `03` §F (F52) | M37.C2.U04, C3.U03, C5.U02 |
| s13b-F15 | **The integration line's golden lane is red**: 53 of 58 founder cases miss at the expert site at `d3c1bb3c` (fresh pg2); the s13-lanes line has `fb45cfd1` and `8acb8377` after `7d88ef25`; yet Haiku's answers recorded at `7d88ef25` replay at `d3c1bb3c` on 56 of 58 — cause unverified | §8.1 | the lead (before any STEP-13b re-record) |
| s13b-F16 | **Two plans claim F59-F61**: STEP-14 (F59-F64) and STEP-16 (F59-F61). STEP-13b adds no case | the two baseline trees | the lead |
| s13b-F17 | **Haiku asks more and never says "nothing"**: find out 40 of 110 (authored 8 of 94), nothing 0 (8) | §8.1 | the post-s13b live pass |
| s13b-F18 | **`exists:` reads a path nobody declared missing as a definite FALSE, not UNKNOWN**: on an anchor holding no facts at all, `admin.sit.money_owed_either_way`'s whole `when` (`[{exists: commitment.due_at}]`) is FALSE and the situation is silently dropped — never shown, never named "may apply" — because `_typed_absence`'s sibling `exists:` branch (unlike `absent:`) has no `unknowable_fields`/`missing_fields` escape hatch; it is the same root cause as F7's "FALSE is silent" by design, but on a situation whose ENTIRE route depends on one `exists:` check with nothing else behind it, meaning a file with no `commitment.due_at` fact at all (not merely an unread one) reads as "this never applies" rather than "not checked" | `context_adapter.py:657-688` (the branch itself); `tests/packs/test_the_engine_reader.py::test_an_account_file_reads_admin_s_unconditional_route_and_its_rule` (caught a wrong test assumption against this, not a code defect — the engine reader's own behaviour is correct given the adapter) | M37.C2.U01 (engine_for reads it correctly); the adapter's gap is `context_adapter.py`'s own, pre-existing and out of STEP-13b's file list |
| s13b-F19 | **`core.signal_composition` is absent from the one wired-up reasoning roster**: `reason/adapters/expertise.py`'s `_ROSTER` (~L340-460) declares dependency edges and config for 20 of the 21 non-legacy units — context, temporal, relationship, timeline, dependency, constraint, policy, risk, opportunity, impact, cost, resource, scheduling, tradeoff, alternative, priority, confidence, validation, recommendation, planning — but never `core.signal_composition` (`SignalCompositionReasoner`, one of STEP-13b's own twelve situation-level units, tree.yaml M37.C2.L-logic.V1.U03). Nothing names what fields it would need or what it would depend on; it has never run inside a compiled pass either, by the same roster's own account | `reason/adapters/expertise.py` (grep `"core\."`, L340-460); `reasoners/__init__.py:58` (`SignalCompositionReasoner` in `SUPPLEMENTARY_UNITS`) | M37.C2.U03 — blocks a confident required_fields/dependencies choice for this one unit specifically; the other eleven have a reference to copy |
| s13b-F20 | **The Opus rung's $0.20 per-call ceiling cannot be met at its own ceiling**: Opus 5.5 cannot turn thinking off (`context/llm/client` `can_be_off=False`), so the expert's 6,000-token ceiling carries its headroom (9,500 tokens), and the budget prices a consult at its CEILING (`estimate_micro_usd`) — 9,500 × $25 a million is already $0.2375 before one input token; the rung (off for every tenant, s13b-D1) would be refused on every file. The $0.20 is the plan's number from Haiku's measured worst case at Opus prices ($0.151), which was an actual cost, not a ceiling price | `budget.EXPERT_RUNG_PER_CALL`; `tests/reason/expert/test_every_rung_spends_one_day.py` (held as a test) | M38.C1.L-contract.V1.U03 — the lead's Opus pass sets the number before the rung is switched on |

### 8.4 · The design

**1 · Three sources, one dossier, every line an id.** The dossier stays the one thing the expert reads, in one fixed
order, bounded, every cut counted (STEP-12's rules). Three changes:

- **The data, citable.** Every line the expert leans on carries an id: the head — `[file:kind]`, `[file:role]`,
  `[file:whose_move]`, `[file:introduced_by]`, `[file:first_touch]`, `[file:last_touch]`, `[file:domains]`; each line of
  the brief — `[brief:<line id>]`, `[brief:company]`; what was checked — `[cov:<mailbox>]`, `[cov:last_mail]`; each
  section's "none" — `[none:promises]`, `[none:playbook]`, `[none:we_wrote]`, `[none:touch]`; and what the company said
  of itself on another file (D63) — `[self:<event>]`, with its words, quotable as a touch is.
- **The engine — Domain Expertise.** *WHAT THE GENIOS ENGINE KNOWS ABOUT ITS SITUATIONS*, after *WHAT A PROFESSIONAL
  KNOWS*: for each of the file's situations, the corpus situations its registries route it to in your switched-on
  corpora, each one's predicate read by the compiler's own three-state evaluator (`ContextAdapter.matches`) over the
  anchor's facts — TRUE prints, UNKNOWN is named *may apply*, FALSE is silent — and for each that applies its owner
  capability's question and failure modes `[cap:<capability>#q|#f<n>]`, its signals of progress and decay
  `[sig:<situation>]`, the capability's playbooks and heuristics `[pb:<artifact>]` (the kind's spine stays where it is
  printed today), its rules `[rule:<artifact>]` with each compiled constraint's verdict `[cons:<rule>]` (holds, fails,
  unknown), its mental models and frameworks `[frame:<artifact>]`; and what your brains learned for the file's subjects —
  `[org:…]`, `[pat:…]`, `[pref:…]` — active at the dossier's instant. **Read, never gated** (D3, s13b-D6): admission
  gates what may carry authority on a card, not what the expert may read; an unreviewed line says so. Read by ROUTE,
  not through the published situation: the publisher holds most situations (F7), and a held situation is still the
  file's. Read only for a file due for review (at most ten a pass); every file's route key — the content hashes of what
  it would read — computed for its fingerprint.
- **The engine — Reasoning Expertise.** *WHAT THE REASONING UNITS MEASURED*, after *ITS NUMBERS*: the twelve
  situation-level units run in shadow over the file's anchor — no decision, nothing persisted, no model — each `[ru:<unit>]`
  with its LEVEL (never basis points: levels, not scores), its reason codes and the evidence ids its findings cite, or
  why it has none; the nine that judge compiled plays named once as not run (s13b-D3).

**2 · The prompt — three sources and the expert's own, each labelled** (the version after STEP-16's v4). `_ONLY` becomes
two rules: *a FACT is about this file and cites what the dossier shows of it — the engine and your own expertise are
never facts about this file*; and *reason from all three — the file, the GeniOS Engine and your own thirty years; write
your own knowledge as `own` lines, a practice, a base rate, a counter-pattern, in words, no number, no name of this
file; where you disagree with the engine, say so in an inference citing both.* An engine line is a prior about the
work; a learned line is the company's own history. The schema gains `own`, the move's `guided_by` (the engine or own
lines it follows) and `rests_on: inference:N`. One worked example of the format, with ids no dossier prints and no
digit. No model is named.

**3 · The check verifies engine ids as it verifies evidence ids.** An engine id must be printed, and a line citing it
holds that line's names and numbers by the card validator's rule. A fact citing only engine or own lines drops
(`engine_is_no_fact`); an own line with a digit (`own_states_a_number`) or a name of the file (`own_names_the_file`)
drops; an own line grounds an inference or pattern only beside a standing data line; `rests_on: inference:N` rests on
that inference's standing facts. Every line is labelled **data · engine · own · mixed** by code, and the engine lines the
standing lines cite are kept with their words on the check, so the card (STEP-14's gold shape) and a replay say where
each sentence came from — *your file*, *the engine: the investor playbook, not yet reviewed*, *from experience* — with
no corpus of that day. Two slips of format stop costing a review: a line cited by its own words, printed exactly once,
resolves to its id (counted); a duration in the advice's own words that agrees with its `by_when` is the advice's.
Ordinary words stop reading as names.

**4 · The fingerprint names the engine — and the ladder, not the model.** `who_decides`: the ladder's version, the
prompt's and the dossier's (a climb never re-keys a file); `engine`: the route key, the learned brains' snapshot, the
units' roster version; `self`: the company record's newest line. Two triggers: `engine_moved` — the engine the file
reads changed since its last review (D48 as Rohit answered it: the dossier changed, so the file is thought again — only
the files it touches); `self_moved` — a file whose last review asked you a question, and the company's record has
spoken since (F52). The prompt's and the check's versions alone still ride along, and a version change keeps an
untouched file covered (F6).

**5 · The ladder — cheap models first.** A file's review goes up the rungs: **Haiku-class** first; an answer that fails
the check *for the writer's own fault* — malformed after its syntax repair, cut at the ceiling, nothing standing, a
move held on a fact cited wrongly, a headline that fails, a draft to us or to the connector — is **asked once more on
its own rung with the check's verdicts** (crosscheck X32, s13b-D4); only a repaired answer that still fails climbs to
**Sonnet-class**; **Opus-class** only when both fail and only if you allow the rung (s13b-D1). A review held for the
file's own state — an answered ask, a find-out review asking its own question — never climbs. When every rung fails,
the best fate stands (shown > suppressed > held > refused). Every attempt is kept (`0250`), priced at its own rung,
inside the expert's one day ($2, D7); a rung refused for want of budget carries the file, said. The rung order is
configuration and the prompt names no model, so the ladder can start at Sonnet for a tenant without a line of code
(s13b-D2).

**What it costs, a review, at the measured volumes** (5.6k tokens in, 2.8k out): Haiku $0.020, a Haiku repair $0.020,
Sonnet $0.039, Opus $0.098. The ladder pays only when Haiku rarely fails: Haiku + p₁·repair + p₂·Sonnet < Sonnet, p₁
the share of Haiku's answers that fail and p₂ the share still failing after their repair. **On today's dossier (p₁ =
0.80, 74 of 92) it is cheaper than Sonnet alone only if the repair cures more than nine failures in ten.** M37 is what
makes M38 pay: with p₁ = 0.4 the repaired answer must fail under 29% of the time. The scorecard decides (M38.C4.U02).

**6 · Every model scored** (`scripts/golden_eval.py`). Beside the board: each review's fate, the drop reasons, the
misquote rate, the `unknown_evidence` rate, the lines that came from the engine and from the expert's own, tokens and
cost — per model and for the ladder, which rung answered and why it climbed; `--replay-live` re-judges a kept pass with
no spend (this check's own measurement, made a command).

**7 · What does not change.** No unit writes a brain, mutes a rule, arms calibration or touches the `distinct_days`
gate (the engine reader issues no write, an AST guard holds it); numbers stay the calculators' (RULE 08) — an engine or
unit line's numbers are lines like any other; a card is STEP-14's to shape; the compiled lane is untouched.

### 8.5 · What will be built — tree block `yc2_w27_s13b` (M37, M38), proposed

Written to `baseline/yc2w27-s13b/tree_s13b.yaml` for the lead to merge into `tree.yaml` — the tree guard then counts one
block more (`tests/test_tree_ids_are_addressable.py`). ⛔ **This file turns one guard red**: `tests/test_the_plan_folder_is_
consistent.py::test_the_folder_has_its_step_files` holds the folder to exactly `STEP-00`…`STEP-18` (`:73-76`); with
`STEP-13b` it fails (measured: 1 failed, 75 passed). A test is not this plan's to edit — the lead restates the guard
(or the file's name) in the merge. `validate_tree_s13b.py`, 12 Oct:

```
parsed: block yc2_w27_s13b, 38 units — M37 24, M38 14
depends_on: 72 named, 18 distinct in other blocks, every one resolved
critical path inside the block (16 units): M37.C1.L-contract.V0.U01 → M37.C2.L-logic.V1.U01 → M37.C2.L-data.V2.U02
  → M37.C2.L-integration.V3.U05 → M37.C3.L-interface.V4.U01 → V5.U02 → V6.U03 → M37.C4.L-logic.V7.U01 → V8.U02
  → V9.U04 → V10.U05 → M38.C2.L-integration.V11.U03 → V12.U05 → M37.C6.L-integration.V13.U03
  → M38.C4.L-integration.V14.U01 → V15.U02
```

**M37 — the GeniOS Engine in the expert's hands** (24 units): C1 what the expert is handed and writes — the engine
read's contract, the review's third version (`own`, `guided_by`, `rests_on: inference:N`), the check's next version ·
C2 reading the engine — the Domain Expertise by route (`packs/compiler/engine_reader`), what the brains learned, the
units' readings (`reason/expert/file_units`), the company's own record (`context/company_record`), the parts read ·
C3 the dossier and the prompt — every line citable, the engine and units sections, the company's record, the prompt ·
C4 the check — three sources, ordinary words, a line cited by its words, the advice's own timing, the decision's
source labels · C5 when the expert thinks again — the fingerprint, two triggers, a version change keeps a file covered ·
C6 the golden set — the authored answers, the dossiers re-measured, ONE re-record, the acceptance by mutation.

**M38 — cheap models first** (14 units): C1 the rungs (Opus only with D1), one day for every rung, the attempts table
`0250`, the ladder's rule (`contracts/model_ladder` — *climb*, never *escalate*: the executive's reminder ladder owns
that word) · C2 the attempts kept, one review up the ladder with its repair, the review run, the doors per rung, the
pass · C3 the per-model scorecard, `--replay-live`, `--ladder` and `--assert-scorecards` · C4 the acceptance by scripted
rungs (no spend), and the lead's kept live passes against §5.

**What comes after what, and why.** Built after STEP-14 (D64: it shares the dossier, the check and the prompt) — and
after STEP-16 and STEP-15 on the files they also edit, each unit naming the last of theirs on its file:

| File | Waits for | Why |
|---|---|---|
| `reason/expert/dossier.py` | STEP-14 M42.C2.L-interface.V3.U04 · STEP-16 M47.C2.L-logic.V4.U02 | one writer: the card's versions, your corrections and their outcomes print first; this step adds ids to every line they print |
| `reason/expert/verify.py` · `contracts/claim_check.py` | STEP-14 M43.C2.L-logic.V1.U01, M43.C1.L-contract.V0.U02 · STEP-16 M46.C4.L-logic.V3.U06, M46.C4.L-contract.V0.U01 | the check's `check.v2` and *never silently* land first; this step's version follows |
| `reason/expert/prompt.py` | STEP-16 M46.C4.L-interface.V0.U02 | STEP-16 takes `expert-review.v4`; this step's is the next |
| `reason/expert/fingerprint.py` · `triggers.py` | STEP-16 M46.C4.L-logic.V3.U04 · V4.U05 | your corrections join the fingerprint and get their trigger first |
| `reason/expert/review.py` · `decide.py` | STEP-14 M43.C2.L-integration.V2.U03 · V3.U04 | the card lines and the gold render block first; the ladder and the source labels then |
| `reason/expert/store.py` · `reason/bundle/sites.py` · `budget.py` · `scripts/golden_eval.py` | STEP-15 M44.C2.L-data.V0.U01 · M45.C1.L-contract.V0.U01, V1.U02 · M45.C5.L-integration.V0.U01 | the brief's reader, its R-8/R-8E sites and budget, its live look come first |
| the cassettes (one re-record) | STEP-14 M43.C6.L-integration.V3.U09 · STEP-16 M47.C4.L-integration.V5.U07 — and s13b-F15 resolved | the board restated once, after theirs |

Built now, beside them (new files only): `contracts/engine_read`, the review contract's third version,
`contracts/model_ladder`, `0250`, `packs/compiler/engine_reader`, `reason/expert/file_units`, `context/company_record`.
Migration `0250` (STEP-14 `0220`-`0221`, STEP-15 `0230`, STEP-16 `0240`-`0242`; `0210`-`0211` exist). No new golden
case (F16).

**The live passes — the lead's (`06` D65; each on a fresh scratch database, its cost printed):**

```
# now, before STEP-13b — the baseline on today's dossier (Sonnet is running, the lead's)
GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:scratch@127.0.0.1:55433/<fresh> GENIOS_GOLDEN_LIVE_KEY=… \
  .venv/bin/python scripts/golden_eval.py --live --site expert --model claude-sonnet-5 --spend-ok      # ≈ $4.33
#   Haiku: done ($2.17). Opus on every case ≈ $10.83 — not recommended; Opus on the cases both fail, after M38:
.venv/bin/python scripts/golden_eval.py --live --site expert --model claude-opus-5 --spend-ok F03 F10 …  # ≈ $0.10 a review
#   re-judge any kept pass, no spend:
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "speedrun008/YC-II W27/baseline/yc2w27-s13b/replay_live_pass.py" \
  "speedrun008/YC-II W27/scores/<date>-<model>-expert" <out.json>

# after M37 and M38 — [MODELLED]: ≈ 8k tokens in a review (the engine sections bounded near 2k), 2.8k out, 110 reviews,
# a repair on the share that fails (p₁ 0.3-0.8, p₂ 0.15-0.6)
… scripts/golden_eval.py --live --site expert --model claude-haiku-4-5-20251001 --spend-ok          # ≈ $2.4-3.4
… scripts/golden_eval.py --live --site expert --model claude-sonnet-5 --spend-ok                    # ≈ $4.8-5.8
… scripts/golden_eval.py --live --site expert --ladder T1,T2 --max-usd 8 --spend-ok                 # ≈ $3.9-7.3, by the climbs
… scripts/golden_eval.py --assert-scorecards "speedrun008/YC-II W27/scores/s13b.json"               # no spend
```

D65's $20 holds the baseline (Haiku $2.17 + Sonnet ≈ $4.33) and STEP-15's look (< $1) with ≈ $12.5 left; the three
post-s13b passes need ≈ $11-16.5 `[MODELLED]` (s13b-D8).

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| s13b-D1 | An Opus rung — amend `06` D7 ("Sonnet-class only")? | **yes, as the third rung only**: asked only when a repaired Sonnet answer still fails the check, inside the same $2 day, $0.20 a call; switched on for a tenant only after the lead's Opus pass on the residual cases shows it passes where Sonnet held | T1 and T2 only (D7 as answered) |
| s13b-D2 | Where the ladder starts | **Haiku**, once M37 has landed and the post-s13b passes meet M38.C4.U02's targets (Haiku held < 50%, the ladder cheaper than Sonnet per review, must-detect no lower); otherwise Sonnet — configuration, no code | Sonnet (D7) |
| s13b-D3 | The reasoning units in the dossier | **the twelve situation-level units, per due file, in shadow**, their levels and reasons printed; the nine that judge plays named as not run | the same |
| s13b-D4 | One repair with the check's verdicts before a climb (crosscheck X32) | **yes** — a Haiku repair ≈ $0.020 against a Sonnet call ≈ $0.039, and most failures are format (§8.1) | climb at once |
| s13b-D5 | May the expert's own line reach your card? | **yes, labelled *from experience***, as the why beside a fact of your file — never alone, never a number, never a name | the check and the scorecard keep it; the card does not show it |
| s13b-D6 | The engine read ungated — the Founder Office's capabilities are drafts | **yes**: D3's rule for the playbook, extended to every corpus line — read, labelled *not yet reviewed*; admission still gates a card | the same |
| s13b-D7 | `06` D63 — what the company says of itself on another file | **in every file's dossier**, from our own sent mail, citable; it re-thinks only a file whose last review asked you a question | the same |
| s13b-D8 | The live passes' budget | **$15 more** for the three post-s13b passes (Haiku, Sonnet, the ladder: ≈ $11-16.5 `[MODELLED]`), beside D65's $20 | within D65: after s13b, Haiku and the ladder only; Sonnet compared from its pre-s13b pass, said |
| s13b-D9 | A citation by a line's own words — read it as the line? | **yes**, a line printed exactly once, counted on the scorecard | as today: dropped |
| s13b-D10 | A duration in the advice's own words ("within 24 hours") | **the advice's**, when it agrees with the move's `by_when`; corrected to it when not; a count about the file still held to its lines | as today: dropped as a wrong number |
| s13b-D11 | The order against STEP-14, -15 and -16 | **after each on its shared files** (§8.5), the new-file units now; one re-record after theirs | the same |

### 8.7 · Risks

- **The dossier grows** — the engine sections, the ids, the company's record: ≈ 40% more tokens in `[MODELLED]`, and Haiku's answers
  already reach 3,990 of the 4,000-token ceiling. Bounded per family and counted; the ceiling re-sized per rung from the
  post-s13b pass, never guessed.
- **A cheap model leaning on the engine as fact.** The check drops a fact resting only on the engine, and a move left with
  no data fact is held, then repaired, then climbs. The scorecard counts how often.
- **The predicate evaluator without a published situation.** If `ContextAdapter` cannot be fed the anchor's facts
  without an admitted object, every predicate reads UNKNOWN: only the unconditional routes print (the lower bound, 57 of
  94), and the rest are named *may apply* — never shown unchecked.
- **What the brains learned reaches a decision.** An Adaptive lease born of a week of *bad timing* clicks would be in front
  of the expert; it is labelled, its expiry judged at the dossier's instant, and nothing here writes one.
- **Every file thought again at the deploy** — no review has yet seen an engine line, so the first `engine_moved` re-reviews
  every file the engine reaches once (a version change alone re-thinks nothing, F6): ten a pass, $2 a day, nearest
  deadline first, the rest carried and said. Production's file count was not read.
- **The re-record rides on a red lane** (s13b-F15): the integration line's founder cases miss today; this step's one
  re-record comes after STEP-14's second and STEP-16's, on a green lane.
- **A rule written by the hand that authors the answers.** The acceptance mutates served answers, one rule at a time, each
  caught on its own case, with the check switched off as the negative control; and only the live passes measure a model.
- **The ladder may cost more than Sonnet** (§8.4 item 5) until Haiku's failures fall; the targets say so and the rung
  order is configuration.
- **Unverified here**: why F14 and F45 miss when Haiku's answers are replayed; the cause of s13b-F15; production's share of
  held situations (the six golden cases held 30 of 33 admission decisions).
