# STEP-G3 · Goal impact in the judgment — L2 (`contracts/reasoning_result.py`, `reason/l2/`)

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G2. **Amended 23 Oct 2026** (GeniOS-011 S26.U3; D7, D9, D10 in
[`08-DECISIONS.md`](08-DECISIONS.md)): unit **G3.5** lets the same judgment propose a goal for the piece of work
it reads (`L2Judgment.proposed_goal`). G4.5 admits it; the founder approves it.

**Source (MD):**
- *"Which goal could this situation affect? Through what relationship or dependency? Is the impact supported by evidence, or is it a hypothesis?"*;
- the twelve cross-correlation angles (MD §6, "Goals par correlation kaise lagega");
- *"Relationship ko binary affected=true se zyada expressive rakhna useful hai"*.


## At a glance

| | |
|---|---|
| **What** | The judgment says, per goal, whether this subject **advances**, **threatens**, **blocks** (`depends_on`) or **may matter to** (`unclear`) it — why, and on what evidence. |
| **Why** | This is MD's goal-impact reasoning, its 12 angles. Today the expert mentions goals only in prose (F02), which cannot be checked or acted on. |
| **For what** | G4 turns admitted impacts into links; G6 shows them; G9 credits outcomes to goals. |
| **How** | `GoalImpact` and `L2Judgment.goal_impacts`. Five refusal codes in `validate_judgment`; `drop_unprinted` drops a bad line. A prompt instruction. The ideal reader answers from `expected.goals`. Golden labels confirmed in the label sheet. |
| **What changes after** | `reasoning_results` carry goal impacts. An invented goal is dropped and counted. **Still shadow:** nothing a founder sees. |
| **Done when** | Labelled golden cases produce their impacts on the L2 path · every invented goal refused · unchanged sweep = 0 calls. |
| **Do not** | Score · allow a size no tool printed · fail a run because of a bad goal line · emit `goal_impacts` when empty (old hashes must hold). |

---

## 1 · What is true today

- `L2Judgment` (`contracts/reasoning_result.py:227`) carries:
  - intervention mode, confidence, options, history used, second order, decision need;
  - proposed mutations, evidence needs, coverage limitations, open conflict, deeper.
- **There is no goal field.**
- `validate_judgment(:362)` refuses or drops every line that cites what the dossier never printed (`_printed`); `drop_unprinted(:410)` keeps the result.
- The expert already writes about goals in words. F02's move ends *"…mark the brief's StartupSetu recognition goal as met"* (`01-AS-IS-CARDS` §1). Nothing can check that sentence or act on it.

## 2 · Design — who computes which angle (the model rules)

| MD angle | Who | How |
|---|---|---|
| relevance, contribution, dependency, alternative explanation, consequence, actionability, historical pattern | **the model** | words in `GoalImpact.why`, citing printed ids |
| ownership | code | the goal's `owner_seat` (G1), printed in block G |
| temporal | code | the goal's deadline vs the subject's due date — a tool line (G5) |
| magnitude | code | G5's progress, and the money tool (`11e31e45`), or "not measurable" |
| evidence, contradiction | code finds them; the model reads them | catalogue ids; `signal_conflicts` (`b8a8a43c`) |

**The output is a relation word, never a score.** The relation is one of four, with a *why*, the evidence ids,
and the basis for its size.

## 3 · Units

### G3.1 · The contract

Added to `contracts/reasoning_result.py`:

```python
GOAL_RELATIONS = ("advances", "threatens", "depends_on", "unclear")

@dataclass(frozen=True)
class GoalImpact:
    goal_ref: str                    # "goal:<id>" — must be one block G printed
    relation: str                    # GOAL_RELATIONS
    why: str                         # the model's reading, ≤ 300 chars, in the founder's words
    evidence: tuple[str, ...]        # ids the dossier printed (signals, facts, tool lines)
    size_basis: str = "not measurable"   # a tool line id from block E/G, or "not measurable"
```

- `L2Judgment.goal_impacts: tuple[GoalImpact, ...] = ()`.
- `from_mapping` reads it via `_items(raw.get("goal_impacts"), ...)`.
- `as_mapping` **omits the key when empty**, so every stored result written before G3 hashes as it did. This is the A7 rule (`23555915`).
- `texts()` adds each `why`, so the number check covers it.

New refusal codes in `validate_judgment`:

| Code | When |
|---|---|
| `GOAL_NOT_PRINTED` | `goal_ref` not in the catalogue (block G) |
| `IMPACT_WITHOUT_EVIDENCE` | an empty `evidence` on `advances / threatens / depends_on` (`unclear` may stand on no evidence: that is its meaning) |
| `UNPRINTED_REF` | an evidence id the dossier never printed (the existing code) |
| `SIZE_NOT_PRINTED` | `size_basis` is neither "not measurable" nor a printed tool-line id |
| `DUPLICATE_GOAL` | the same goal twice |

- **`drop_unprinted`** drops a failing impact line and keeps the rest (the STEP-13 rule: a failing line drops, the result stays).
- **A dropped goal line never fails the run.**

### G3.2 · The prompt (`reason/l2/prompt.py`)

The schema text gains `goal_impacts`. The instruction, written once (bump `PROMPT_VERSION`):

> For each goal in block G that this subject truly bears on, say how: **advances** (it moves the goal
> forward), **threatens** (it puts the goal at risk), **depends_on** (the goal cannot move until this is
> resolved), or **unclear** (it may matter, and the evidence does not say how). Write why in one or two
> sentences a founder would say, and cite the lines it rests on. Name only goals block G printed. Leave
> out a goal the subject does not touch — most subjects touch one goal, many touch none. Never state a
> size the tools did not print.

### G3.3 · The ideal reader (`tests/replays/ideal_reader.py`)

- `l2_judgment_for` derives `goal_impacts` from a new optional case field, `expected.goals: [{goal, relation}]`, translating the goal statement to the printed `goal:` id. A case without the field answers `[]`.
- **The golden labels**, proposed here. Rohit or Harsh confirms them in the label sheet (`tests/test_golden_labels_sheet.py`):

| Goal | Cases (`advances` unless marked) |
|---|---|
| Raise the seed round | F03, F10, F11, F12, F13, F15 (`threatens` — the wave gone silent), F16 (`depends_on` — the bounce), F46, F47 (`depends_on`), F50, F52, F65, F66 |
| StartupSetu recognition | F01 (`unclear` — the examiner's query is unknown), F02 |
| Accelerator and incubator programs | F17, F19, F21, F22, F24, F67 |
| Hire a Founding AI Engineer | F25 (`depends_on` — the board's ESOP approval) |
| Land design partners | F26, F27, F28, F29, F49, F51, F57 |
| **no goal** (must be counted as "not linked") | F56 (vendor renewal), every must-abstain case |
| **label at build time** (who the contact is decides which goal) | F04–F07, F09 (the connector asks about the round), F42, F44, F45, F48, F54, F55, F59–F63 |

### G3.4 · The store

`reason/l2/store` keeps the judgment whole, so the impacts travel inside `reasoning_results`. No schema change.

### G3.5 · `L2Judgment.proposed_goal` — the judgment proposes a goal (amendment, 23 Oct 2026)

**Why.** §3.1 lets the judgment name only goals block G printed. So a piece of work the company is
pursuing, with no goal of its own, can only be linked to a broad goal: an accelerator admission is an
`advances` line under "Get into accelerator and incubator programs" (§3.3), never its own goal. That is
Rohit's Antler Singapore case (23 Oct): the context was in the graph, and no goal was proposed. D9 says the
judgment may propose one; D10 says one goal per piece of work.

**The contract** (added to `contracts/reasoning_result.py`; `00-ARCHITECTURE` Goals, `GoalProposal`):

```python
@dataclass(frozen=True)
class GoalProposal:
    statement: str                   # the goal in the founder's words, <= 200 chars (the brief's line rule)
    why: str                         # why the company is pursuing it, <= 300 chars
    evidence: tuple[str, ...]        # ids the dossier printed; at least one
    parent_goal_ref: str | None = None   # "goal:<id>" block G printed, or None
    deadline: str | None = None      # a date exactly as the dossier printed it, or None
    target: str | None = None        # a number exactly as a tool line printed it, or None
    metric: str | None = None        # a key of contracts/goal.METRICS (G5), only with a target
```

- `L2Judgment.proposed_goal: GoalProposal | None = None`. It is for the request's own subject, so it names no subject; G4.5 takes `subject_ref` from the request.
- `from_mapping` reads `raw.get("proposed_goal")`; `as_mapping` **omits the key when None**, so every stored result written before G3.5 hashes as it did (the A7 rule, as `goal_impacts`).
- `texts()` adds `statement` and `why`, so the number check covers them.

New refusal codes in `validate_judgment` (the names GeniOS-011 S29.U3 uses):

| Code | When |
|---|---|
| `GOAL_PROPOSAL_NO_EVIDENCE` | an empty `evidence` |
| `UNPRINTED_REF` | an evidence id the dossier never printed (the existing code) |
| `PARENT_NOT_PRINTED` | a `parent_goal_ref` not in block G |
| `DEADLINE_NOT_PRINTED` | a `deadline` the dossier did not print |
| `TARGET_NOT_PRINTED` | a `target` no tool line printed, or a `target` without a `metric` |

- **`drop_unprinted`** sets a failing `proposed_goal` to None and keeps the rest of the judgment. A dropped proposal never fails the run; it is counted in the receipt.
- **The model never sets an owner, a status or an approver.** The contract has no field for them.

**The prompt** (`reason/l2/prompt.py`, the same `PROMPT_VERSION` bump as G3.2 when built together):

> If this subject is a piece of work the company itself is pursuing — an application, a raise from one
> fund, a hire, a partner — with an outcome it wants, and no goal in block G names that work, you may
> propose ONE goal for it in `proposed_goal`: in the founder's words, citing the lines it rests on, at
> least one of them something the company itself did (applied, replied, met). If a broad goal in block G
> covers it, name that goal as its parent. Give a deadline or a target only if the dossier printed it.
> Propose nothing when a goal in block G already names this work, or when the subject is not the company's
> own work. A proposal is only a proposal: the founder decides.

The impact line stays. A subject with its own proposed goal still writes its `advances` line to the broad
goal (§3.3), so the card keeps its goal line until the founder approves the new one.

Duplicates are refused by code at admission (G4.5), not by the prompt: block G prints only live goals
(STEP-G2 §2.1), so the model cannot see every pending proposal. If block G later prints pending proposals
apart (GeniOS-011 S29.U1), the instruction adds "or a proposal block G lists".

**The ideal reader** (`tests/replays/ideal_reader.py`): `l2_judgment_for` answers `proposed_goal` from a new
optional case field, `expected.proposed_goal: {statement, parent, deadline}`, translating `parent` (a goal
statement) to its printed `goal:` id. A case without the field answers none.

**Golden case F72 (new, synthetic, GeniOS-011 S28.U3):** *"An accelerator's partner replies with a conditional
admission, and it becomes a proposed goal"*. Founder cases cannot name Antler or Theresa
(`tests/replays/founder_case.REAL_NAMES`), so the names are invented: the founder applied to a Singapore
cohort of an accelerator that no brief line names (no goal, no in-motion line); its partner replies that a
place is offered, subject to a final partner call by a stated date. Labels:
- `expected.proposed_goal`: a statement naming the accelerator and its Singapore cohort; `parent` = "Get into
  accelerator and incubator programs"; `deadline` = the date the partner's mail states;
- `expected.goals`: `advances` on "Get into accelerator and incubator programs";
- a newsletter from the same accelerator, in the same case, proposes nothing (G4.5's own-act rule).

F72 is recorded strict-xfail and passes when G4.5 lands (GeniOS-011 S29.U4).

## 4 · LLM use and cost

- **Calls:** no new call. The same R-9 pass writes one more field.
- **Output:** ≈ 60–150 tokens (0–3 impact lines). At Sonnet-class output prices that is <$0.003 per run.

## 5 · Tests

**`tests/contracts/test_goal_impact.py`** (pure):
1. each refusal code is raised by its own case;
2. `drop_unprinted` drops only the bad line;
3. an empty `goal_impacts` keeps the stored hash of a pre-G3 result (a byte-equal fixture).

**`tests/reason/l2/test_goal_impacts_pass.py`** (PG):
1. F03 → `advances` on "Raise the seed round";
2. F56 → no impact;
3. an invented `goal:x` is dropped and counted in the receipt.

**Golden:**
- a new marking rule in `tests/replays/marking.py`: a case with `expected.goals` passes only if every expected (goal, relation) is in the run's admitted links (G4). Until G4 lands, the rule reads the result's impacts;
- the board must stay ≥ the before-score.

**Mutation proofs:** remove the `GOAL_NOT_PRINTED` check → test 3 fails; make `as_mapping` always emit the key → test 1.3 fails.

**G3.5 tests** — `tests/contracts/test_goal_proposal.py` (pure):
1. each G3.5 refusal code is raised by its own case;
2. `drop_unprinted` drops only the proposal and keeps the judgment;
3. a None `proposed_goal` keeps the stored hash of a pre-G3.5 result (a byte-equal fixture);
4. the contract has no owner, status or approver field (the dataclass fields are pinned).

**G3.5 golden:** a case with `expected.proposed_goal` passes only if the run proposes it (until G4.5: the
result's `proposed_goal`; after: a pending brief `goals` line). A case without the field is not marked on
proposals, and the board prints how many proposals the run made.

**G3.5 mutation proofs:** remove `PARENT_NOT_PRINTED` → test 1 fails; make `as_mapping` always emit
`proposed_goal` → test 3 fails.

## 6 · Flags, rollback

- **Flags:** rides `l2_reasoning`.
- **Rollback:** the prompt version before G3, and the cassettes it recorded. Stored results keep their impacts and nothing reads them.

## 7 · Done when

- the labelled golden cases produce their expected impacts on the L2 path;
- the claim check refuses every invented goal;
- (G3.5) F72's judgment proposes its goal on the ideal reader, and every proposal citing an unprinted parent, deadline or target is dropped and counted;
- an unchanged sweep makes 0 calls.

## Harsh's checklist — in order

1. **Label the golden cases:**
   - add `expected.goals` to the cases in §3.3's table;
   - label the "build time" row by reading each case (who the contact is);
   - get Rohit's confirmation in `tests/test_golden_labels_sheet.py`'s sheet.
2. **Write the tests first:**
   - `tests/contracts/test_goal_impact.py` (pure, including the byte-equal hash of a pre-G3 result);
   - `tests/reason/l2/test_goal_impacts_pass.py`.
3. **Build:**
   - `GoalImpact` + the field + `from_mapping` / `as_mapping` / `texts`;
   - the five codes in `validate_judgment`;
   - the drop in `drop_unprinted`.
4. **The prompt instruction** (§3.2, word for word); bump `PROMPT_VERSION`.
5. **Ideal reader:** `l2_judgment_for` answers `goal_impacts` from `expected.goals`, translating each statement to its printed `goal:` id.
6. **The marking rule:** `tests/replays/marking.py` reads the result's impacts until G4 lands, then the links.
7. **Re-record all cassettes** (ideal reader). The board must not drop.
8. **Mutation proofs:**
   - `GOAL_NOT_PRINTED` removed;
   - `as_mapping` always emitting the key.
9. **G3.5** (with steps 2–8 when built together, one prompt version):
   - `tests/contracts/test_goal_proposal.py` first (§5, G3.5 tests);
   - `GoalProposal`, `L2Judgment.proposed_goal`, the five codes, the drop;
   - the prompt paragraph (§3 G3.5, word for word);
   - the ideal reader's `expected.proposed_goal`; F72 labels (GeniOS-011 S28.U3 writes the case);
   - mutation proofs: `PARENT_NOT_PRINTED`, and `as_mapping` always emitting the key.
10. **Guards, push, CI, logs.**

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G3. Add `goal_impacts` to the L2 judgment, with its claim checks, the prompt instruction, the ideal reader's answer and the golden marking.

**Read first:**
- the preamble;
- `STEP-G3-goal-impact-in-the-judgment.md`;
- `contracts/reasoning_result.py` (`L2Judgment`, `validate_judgment`, `drop_unprinted`);
- `reason/l2/prompt.py`;
- `tests/replays/ideal_reader.py`, `marking.py`.

**You own:**
- `contracts/reasoning_result.py` (the G3 parts);
- `reason/l2/prompt.py`;
- `tests/replays/ideal_reader.py`, `tests/replays/marking.py`;
- the `expected.goals` field **added** to the cases listed in §3.3 (adding a field is allowed; changing any existing field is not);
- the two new test files;
- the cassettes.

**Do not touch:**
- existing expectations;
- `context/`;
- `deliver/`.

**Acceptance:**
- §5's tests;
- labelled cases produce their impacts;
- invented goals dropped;
- (G3.5) `proposed_goal` with its five codes; F72's proposal on the ideal reader;
- four mutation proofs (two for G3, two for G3.5);
- the board not lower.
