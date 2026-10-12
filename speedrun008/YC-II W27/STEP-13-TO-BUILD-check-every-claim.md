# STEP-13 · TO BUILD · check every claim, choose the lane, ask for what is missing

**Owner:** Claude. **Depends on:** `STEP-12`. **Moves:** forbidden outputs on the golden set **→ 0**;
every sentence on a card maps to evidence or is labelled an inference; `output_lane` is **never
NULL**.

---

## 1 · What is true now

| | Evidence |
|---|---|
| A proposal validator exists | `[CODE]` `context/proposal_gate.as_gate_validator` (used by R-6) and `contracts/claim_state.model_writable_fields()` |
| The card copy has field validators only | `[CODE]` `deliver/render.py:832-887` — V-01 length, V-02 invention |
| The lane router exists and is deterministic | `[CODE]` `reason/output_lane.py` — conflict first, failed/blocked ours, insufficient context → investigation, a decision under the 6,000 bp floor → monitor, DEFER → monitor, no-action → suppress |
| The model path skips it | `[CODE]` `reason/llm_decision_maker.py:827-846` builds the decision without `output_lane` |
| The question queue exists and nothing consumes it | `[CODE]` `evidence_needs` is written (`context/evidence_need_store.py:43`, from residue `signal_unreached`); `read_open_needs`, `close_need` and the executor `capture/acquire/need_executor.run_needs` have no production caller |
| Already-done work resurfaces | `[ATLAS]` golden replay 04 — blocked |

## 2 · Why

A fluent, wrong card is the fastest way to lose your trust (Atlas V.5: *"a confident wrong card to
a CFO ends a pilot"*). The expert may judge; nothing it says is shown until it is checked.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | every claim has a source | new `reason/expert/verify.py`, on `context/proposal_gate` | each `fact` must cite evidence ids that resolve; each `inference` names what it is based on; each `hypothesis` stays a hypothesis. An unsupported fact is dropped; if it was decisive, the file goes to Investigation |
| 3.2 | every number is a calculation | same | every number in the expert's text must equal a calculator's output in the dossier — days, counts, dates, amounts. A mismatch is replaced by the calculator's value or the sentence is dropped (RULE 08) |
| 3.3 | the right people | same + `STEP-04` + `STEP-09` | the recipient is never us; the target is never the connector; requester and target agree with the headers |
| 3.4 | not already done | same | before any card: is there a completion event — a reply in any connected mailbox, a booked meeting, a screen item marked done — that matches this exact ask? Then suppress, with the reason (replay 04: close the exact request, never every loop with that person) |
| 3.5 | the lane | `reason/output_lane.route` | outcome from the expert's `mode` (decide → decision · investigate → insufficient context · conflict → conflict · monitor → defer · suppress → no action); confidence from the **validated evidence state**, never asserted by the model; with D1 = A, the appraisal informs stakes. `output_lane` always written |
| 3.6 | ask for what is missing | `context/evidence_needs.py`; `capture/acquire/need_executor.py` | an unknown marked high-relevance becomes an `evidence_need`: fetched if a source can answer it, otherwise **one question to you** — *"Is saka.vc a fund?"*, *"Did you reply to Maria from ceo@thegenios.com?"* — and your answer feeds the brief or the file |

## 4 · What will happen

| The expert wrote | The check does |
|---|---|
| *"Maria replied 52 days ago"* | 52 is recomputed from the timeline; it matches → kept |
| *"Neel asked for your deck"* | no span in his mail says so → dropped; if decisive → Investigation: *"What did Neel ask for?"* |
| *"Send Boardy the update"* | the target is the connector → refused; the expert's alternative (the contact) is used |
| *"Follow up with Sal"* — but you already answered Sal later in the same thread | the reply is found in your sent mail → suppressed, with the reason |

## 5 · Expected

- forbidden outputs on the golden set: **0**;
- 100% of card sentences carry an evidence id or an inference label;
- `output_lane` NULL on new signals: **0**;
- `evidence_needs` read and closed — the executor has a caller.

## 6 · Verify

```
.venv/bin/python -m pytest tests/reason/expert/test_verify.py -q
#   an uncited fact is dropped; a wrong number is corrected; a connector target is refused;
#   a completed ask is suppressed — each by mutation
.venv/bin/python -m pytest tests/replays -q          # replays 01, 02, 04, 05, 07 tighten from "must not" to "must"
```

---

## 8 · The check of 2026-10-12 — what the 5 Oct plan got right, and wrong

Re-checked claim by claim against `speedrun008` @ `c97155cd` by a read-only worker and by hand, and
measured on the golden set's 94 authored expert answers (66 files, 58 cases). Since 5 Oct, STEP-12 built
the expert and made its review the file's one decision — and with it a first check:
`contracts/expert_review.validate` refuses a review whose facts cite an id the dossier never showed, or
that writes a number the dossier does not hold. What does not exist is the check this step promised:
whether a cited mail SAYS what a fact claims, whether a number is the calculator's, whom a draft goes to,
whether the ask was already answered. And the first check refuses the WHOLE review: one bad fact sends
the file back to the per-situation path STEP-12 replaced.

### 8.1 · Measured — the golden set (94 authored answers)

| | |
|---|---|
| modes | act 58 · wait 20 · find out 8 · nothing 8 |
| facts | 472 — **196** cite a mail or a meeting, **276** only code's readings (`num:`, `loop:`, `sit:`, `pb:`, `hist:` …) |
| moves | 72, **48** with a draft; whom the draft goes to is not a field — `for_whom` is free text: 4 name us (find-out and record moves, none with a draft), 1 a connector (F09 — the connector's own ask, rightly) |
| numbers in the card's words | 6 of 282 card texts write a digit (16 numbers) — STEP-12's authoring rule (F178) |
| you, in the third person | **61 of 282** card texts — the headline, the situation, what done looks like — call you *"the founder"* (33) or *"Arjun"* (26), or name the company (3), over 34 cases: F178's second half |
| forbidden outputs | **0** since STEP-12 (8 → 0) — on answers authored to be faithful: the board measures the plumbing (STEP-12 §8.3 N8); only the live pass (`06` D50) measures a model |
| find out | 8 answers (F01, F07, F21 ×2, F22, F52, F54 ×2); F01 and F52 are must-detect cases lost because their file is held in Investigation and no card asks its question |

### 8.2 · The claims

| # | Claim (§1) | Now | Evidence |
|---|---|---|---|
| 1 | a proposal validator exists | **true, and the expert does not use it** — R-6's only (retired by STEP-12); the expert has its own (`expert_review.validate`) | `context/proposal_gate.py:122, 222`; `reason/situation_reasoner.py:241, 253` |
| 2 | the card copy has field validators only | **partly** — V-02 now checks claim by claim (`deliver/claim_validator.claims_ok`: names, numbers, dates in the corpus), no sentence carries an evidence id; and **an expert card skips both**: the pipeline passes no model, so `render_copy` returns its fallback before any validator runs | `deliver/render.py:808-809, 847-900`; `deliver/pipeline.py:503-506` |
| 3 | the lane router exists and is deterministic | **true** | `reason/output_lane.py:71-120` |
| 4 | the model path skips it | **true** — the LLM decider's decision has no lane; and four more writers leave it NULL: the legacy rule lane (live), the native publication (shadow), the deal-health composer (sales), the team emitter | `reason/llm_decision_maker.py:923-942`; `reason/runner.py:787`; `reason/publication.py`, `composer.py`, `team/emit.py` (0 mentions of `output_lane`) |
| 5 | the question queue exists and nothing consumes it | **true** — and `build_fetchers` returns `{}`, so `run_needs` would refuse even if called; the expert's unknowns are read by its prompt only | `context/evidence_need_store.py:97, 106`; `capture/acquire/need_executor.py:132, 214-225` |
| 6 | already-done work resurfaces | **partly** — replay 04 expresses 1 of 12 mutations (F38, passing); 11 are blocked | `tests/replays/specs/04-*.json`; `tests/replays/atlas_expression.py:53, 71` |

The units of §3, against what exists:

| | Unit | Now |
|---|---|---|
| 3.1 | every claim has a source | **partly** — an uncited fact, an unknown id and an ungrounded inference are refused, the whole review with them; nothing checks that a mail says what a fact claims, nothing drops one fact, nothing sends a file to Investigation when a decisive fact fails |
| 3.2 | every number is a calculation | **partly** — a number must appear *somewhere* in the dossier; "52 days" passes if any 52 is printed |
| 3.3 | the right people | **partly** — a card whose subject is us is refused (`SubjectIsUs`), the sweep skips a file whose counterparty is us, STEP-09 keeps a connector from anchoring a situation; nothing checks whom the expert's draft goes to |
| 3.4 | not already done | **partly** — our reply closes the asks in its thread (`open_loops`), a resolution claim closes its situation; no booked meeting answers an ask; nothing checks before a card |
| 3.5 | the lane | **partly** — the expert's decision routes (`decide.py:139-146, 415`); the other writers above do not; no expert mode reaches CONFLICT; any lane but DECISION emits no signal (`domain_shadow.py:259-260`) |
| 3.6 | ask for what is missing | **not built** — nothing turns a find-out review into a question; Investigation appears in `deliver/` as a label only |

### 8.3 · New — not in the plan

- **N1 · An expert card skips the card validators.** STEP-12 M33 renders the review's own words without a
  narrator, and so without V-01 and V-02: its names are checked by nothing (its numbers by the dossier's).
  Delivery cannot fix that — it never holds the dossier, so V-02 there would judge the expert against less
  than it read. The check runs where the dossier is (`reason/`), by V-02's own rule — and that rule lives in
  `deliver/`, which reasoning may not import (`tests/test_layer_topology.py`); the executive layer met the
  same wall and grew its own copy (`executive/validate.py`). The rule moves to `platform/`.
- **N2 · One bad fact undoes the review.** A refused review leaves the file uncovered: its situations go
  back to the decider and the rules. The plan's *drop the claim, keep the judgment* needs a verdict per line.
- **N3 · Whom a draft goes to is not written down.** `for_whom` is who the move serves; four of them are us
  (*"Nimbus Labs' records"*), rightly. A recipient check needs the recipient: a `to` beside every draft.
- **N4 · Which ask a move answers is not written down either** — so "already done" cannot be asked of
  *that* ask. The move names it (`answers`, a `loop:` id); code reads that ask's state when it decides.
- **N5 · A question has no road to you.** A find-out decision has no candidate (the decision contract
  forbids one), and the delivery authority requires a selected move: a question needs its own authority, its
  own signal, its own card.
- **N6 · The card speaks of you in the third person** in 61 of 282 authored texts (§8.1) — STEP-12 fixed the
  company's name, not *"the founder"*. The prompt never says *"you"* (F178).
- **N7 · The card validator reads an ordinary word that opens a sentence as an invented name.** Run over
  the authored answers, V-02's own rule dropped *"Nothing is owed"*, *"Sign in"*, *"Download the
  certificate"*, *"Accept the invite"*, *"Attaching the deck"*, *"Ahead of your partners' meeting"* — twelve
  words, each an observed failure, the way that rule's stop-list says its words are earned. The expert's
  check reads them as words (`verify.EARNED`); the card validator's own list is unchanged, so no narrator
  card is judged differently. And an id's digits (`evt_marco_0811`) are no number a claim may lean on.

### 8.4 · What changes in the design

1. **Verify, don't refuse.** `reason/expert/verify.py` checks a review line by line and keeps a verdict for
   each — kept, corrected (from, to, by which calculator) or dropped, for a closed reason. What stands
   decides. `contracts/expert_review.validate` still reports every problem; the review run refuses whole
   only a malformed answer (repaired once), its STRUCTURE — a moving mode with no move, a move resting on no
   fact of the review, a stage the playbook does not name — and a review none of whose facts stands. An
   uncited fact or an id never shown drops its own line; a number in prose no founder is shown (a
   hypothesis, a scenario) is noted, not refused (D59).
2. **A claim a move rests on quotes its mail.** The move names the facts it rests on (`rests_on`); each of
   those that cites a mail carries the words of that mail it rests on (`quote`), and code finds them there.
   Every fact's names and numbers must be on the lines it cites — the card validator's own rule, run per
   fact. A move whose ground fell is not shown: the file goes to Investigation, and its question is asked.
3. **A number is the calculator's.** A wrong number is corrected to the one its cited calculator line
   holds, or its sentence is dropped (RULE 08).
4. **A draft names its recipient** (`to`): someone the file's mail shows, never us, never the connector
   standing in for the person it introduced — then the review's own alternative is the move, if it checks.
   A draft with no recipient is withheld; the move stands.
5. **An answered ask is not raised again.** The move names the ask it answers. An ask our reply answered —
   in its thread, from any connected mailbox — is closed, so the dossier does not show it and a move cannot
   name it. What stays open after it is done is a meeting ask: a meeting on the file after it was asked
   answers it, and the move is suppressed with that meeting as the reason; the file's decision clears.
6. **You are "you".** The prompt says so, and the authored answers do; the check records a card text that
   calls you *"the founder"* or names you or the company as a party (`speaks_of_you`) — for the live pass
   to count. Rewording a card is `STEP-14`'s.
7. **A question is an output.** A held file asks ONE question on its own card (the Investigation lane,
   authorised as a question), the file's one card; your answer is kept on the file, its dossier shows it,
   its fingerprint moves, and the next sweep reviews it with your answer in front of the expert. The needs
   queue gets its reader; with no connector wired (`build_fetchers` empty, Harsh's), it refuses, counted —
   and a question to you never waits on a connector.
8. **Every writer routes its lane**, and a guard holds that no statement inserts a signal without one.

### 8.5 · What will be built — tree block `yc2_w27_s13` (M35, M36)

**M35 — nothing the expert says reaches you unchecked** (§3.1–§3.4): C1 what the check reads and writes —
the review contract's second version, the verdicts, migration `0200`; C2 the checks — the invention rule
moved where reasoning may ask it, the dossier's lines by id, and the check itself — claims, numbers, people,
an answered ask (a meeting booked since answers a meeting ask), the fate;
C3 where it runs — the prompt, the review run, the decision, the expert card saying where each of its
sentences came from; C4 the golden set — the authored answers, one re-record, the acceptance by mutation;
C5 a resolution claim names its brief (F83).

**M36 — every decision has a lane, and what is missing is asked** (§3.5, §3.6): C1 the lane on five
writers and a guard; C2 the question — its table (`0201_founder_questions`, not the needs queue: the
needs executor closes for good what no source can fetch, and a question to you is answered by you), the
store, the question's own authority, the sweep that asks (and the needs queue's reader, refusing while no
connector is wired), the question card, your answer, your answer in the dossier, and the golden set (F01,
F52); C3 the Atlas replays that tighten.

**29 units (14 in M35, 15 in M36), critical path 12.** Each unit, its artifact and its verify command are
in `tree.yaml`. The build order keeps the golden lane green: the checks are written pure first, the prompt
and the authored answers changed and re-recorded once, and only then is the check wired in.

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| D59 | A claim the check cannot support — drop the claim, or refuse the review? | drop the claim and keep the review; a move that loses its ground becomes a question | the same |
| D60 | Where does a question reach you? | its own card, one per file, the file's one card — the morning brief (`STEP-15`) lists them too | the same |
| D61 | A *conflict* mode for the expert (two sources disagree — a ruling)? | not now: no case and no measured need; the lane stays reachable from the compiled lane | not built, declared |

### 8.7 · Risks

- **A quote the model paraphrases** is dropped as misquoted, and a move resting on it becomes a question.
  The live pass (D50) says how often; the match ignores case, spacing, quote marks and punctuation.
- **A check written by the same hand as the answers** — the authored answers will pass it. The acceptance
  therefore mutates served answers, one rule at a time, and needs each mutation caught on its own case.
- **One more re-record** — the prompt changes, so every expert answer is re-recorded and the board restated
  in its five places; and in production, every file is reviewed once more after the deploy.
