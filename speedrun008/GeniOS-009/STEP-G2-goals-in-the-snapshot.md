# STEP-G2 · Goals in what L2 reads — L3 → L2 (`reason/l2/`)

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G1.

**Source (MD):**
- *"Context Adapter: L3 se relevant ContextSnapshot… goals, entities, relationships, active situations"*;
- *"Goal-impact reasoning: Situation ka company ke goals… se kya relation hai?"*;
- *"Leadership ne revenue target badla: kai departmental goals aur situation priorities affect ho sakte hain"*.


## At a glance

| | |
|---|---|
| **What** | Show the approved goals to the L2 judgment as a new dossier **block G**, with ids. Make a goal change re-open exactly the subjects it should. |
| **Why** | The model cannot reason about a goal it is not shown with an id, and the claim check cannot verify a goal named in prose. Today an edited goal re-reasons nothing: goals are not in the fingerprint. |
| **For what** | G3 (the model names goals by id) and G9 (the goal subject). |
| **How** | `Snapshot.goals` / `linked`. `dossier._goals` as block G, after F. Goal ids into the catalogue. `fingerprint_of` gains `goal_set` and `linked_goals`, only when the tenant has a live goal. A new trigger `goal_changed`. One prompt paragraph. Dossier and prompt versions bumped. |
| **What changes after** | Each L2 prompt of a tenant with goals carries ≈ 200–300 more tokens (≈ +2–4% per run). A new or cancelled goal re-judges each open subject once; an edited goal re-judges only its linked subjects. The board is unchanged. |
| **Done when** | Golden green with block G · an unchanged sweep makes 0 calls · adding a goal re-judges each open subject exactly once. |
| **Do not** | Pick "relevant" goals in code · print proposed goals · change the text of blocks A–F · let an unchanged sweep call the model. |

---

## 1 · What is true today

- **The L2 dossier has six blocks**, A–F (`reason/l2/dossier.py:37`): signals · context · history · expertise and the file · tools · coverage.
- **Goals reach the model only as words** inside block D's company brief (`company_brief.prompt_block`). They have no ids, so nothing the model says about a goal can be checked, and nothing can be linked.
- **The change gate** (`reason/l2/sweep.fingerprint_of:74`) fingerprints signals, file parts, need states, the due rung, open conflicts and the versions of model, prompt, dossier and plan. **Goals are not in it**: an approved or edited goal re-reasons nothing.

## 2 · Design

1. **A new block G · THE GOALS**, printed after F, so blocks A–F keep their text byte for byte:

   ```
   # G · THE GOALS — what the company is trying to achieve (approved by the founder)
   goal:g_7c1… Raise the seed round · department founder_office · owner you · deadline 31 Dec 2026
                · progress: unknown — no countable metric
   goal:g_19a… StartupSetu recognition for Nimbus Labs Private Limited · deadline — · progress: unknown
   …
   Linked to this subject before: goal:g_7c1… (advances, since 3 Sep)
   ```

   - **Which goals:** every LIVE goal of the tenant, at most `MAX_GOALS_PRINTED = 8`, ordered by deadline. A tenant has few goals (the brief caps lines per section). Choosing the "relevant" goals in code would be a judgment, and judgment is the model's (memory: llm-as-the-expert-not-the-formula). Above 8: the goals already linked to this subject first, then by deadline. The rest are named in a `truncated` line, never cut silently (the brief's own budget rule).
   - **The ids go into the catalogue** (`DossierCatalogue.evidence_ids`) so the claim check of G3 can refuse an unprinted goal.
   - **Progress is printed only from G5**, else "unknown — <why>". It is never computed in the dossier.
   - **The proposed goals are not printed.** The model reasons against approved goals only (MD invariant 2).
2. **The fingerprint gains goals**, in two parts:
   - `goal_set` = `goals.goal_set_digest(active goals)`, the ids only. A goal **added or cancelled** changes every subject's fingerprint. Each subject is re-judged once, bounded by `MAX_PER_PASS`, nearest due first; the rest wait for the next sweep (the watermark rule).
   - `linked_goals` = sorted `(goal_id, revision)` of goals linked to this subject (G4). An **edited target or deadline** re-judges only the subjects linked to that goal.

   Both keys are added **only when the tenant has a live goal**, so a tenant with none fingerprints exactly as before (the `b8a8a43c` idiom).
3. **A new trigger.** `contracts/reasoning_result.TRIGGER_GOAL_CHANGED = "goal_changed"` is recorded on the `L2Request` when the fingerprint moved only by its goal keys, so the receipt says why the run happened.

## 3 · Units

| Unit | File | Change |
|---|---|---|
| G2.1 | `reason/l2/snapshot.py` | `Snapshot` gains `goals: tuple[Goal, ...]` and `linked: tuple[tuple[str, int, str], ...]` (goal_id, revision, relation). `read_snapshot(...)` reads them through `context/goals.active_goals` and `context/goal_links.links_for_subject` (G4; empty until G4 is built). |
| G2.2 | `reason/l2/dossier.py` | `TITLES["G"]`; `_goals(snapshot, cite) -> str`; appended to the block order; `L2_DOSSIER_VERSION` bumped. The `goal:` ids go into `cite.seen`. |
| G2.3 | `reason/l2/sweep.py` | `fingerprint_of(..., goals=snapshot.goals, linked=snapshot.linked)` adds `goal_set` and `linked_goals` when there are live goals. The trigger is set to `goal_changed` when only those moved. |
| G2.4 | `contracts/reasoning_result.py` | `TRIGGER_GOAL_CHANGED`, added to the triggers tuple |
| G2.5 | `reason/l2/prompt.py` | one paragraph in the instructions: *"Block G lists the company's approved goals. Read the subject against them in G3's field; never invent a goal, never treat a proposed goal as the company's."* `PROMPT_VERSION` bumped |

## 4 · LLM use and cost

- **Calls:** no new call. The same R-9 judgment reads one more block.
- **Tokens:** about 40 per goal line, so 5 goals ≈ 200–300 input tokens per run. F03's run cost 29,560 µ$ (measured 22 Oct), so that is ≈ +2–4% per run.
- **Re-judging:** a goal added or cancelled re-judges every open subject once, ≈ open subjects × $0.03 for that sweep, then 0 calls.

## 5 · Tests

**`tests/reason/l2/test_goals_block.py`** (PG):
1. a tenant with no live goal → the dossier text and fingerprint are identical to before (a byte-equal assertion against a fixture recorded before G2);
2. with 5 goals → block G lists 5 lines with `goal:` ids, and the ids are in the catalogue;
3. with 10 goals → 8 printed, linked ones first, and a `truncated` line naming 2;
4. a proposed goal is never printed.

**`tests/reason/l2/test_goal_fingerprint.py`** (pure):
1. adding a goal changes every subject's fingerprint;
2. editing a goal's deadline changes only a linked subject's;
3. no goals → the fingerprint is unchanged from the pre-G2 value.

**Golden:**
- every cassette whose prompt now carries block G misses. Re-record all with the ideal reader (`scripts/golden_eval.py --record`, no spend), then the resync and the door;
- the board must be unchanged: block G adds reading, not a verdict;
- `test_an_unchanged_sweep_costs_nothing` must stay green: a second sweep with unchanged goals makes 0 calls.

**Mutation proofs:**
- leave the goal ids out of the catalogue → G3's unprinted-goal test fails;
- drop the "only when live goals" guard → test 1 fails.

## 6 · Flags, rollout, rollback

- **Flags:** rides `l2_reasoning`. Block G is printed only where the L2 pass runs.
- **Rollback:** return `""` from `_goals` and drop the two fingerprint keys (one commit). The cassettes recorded before G2 replay again.

## 7 · Done when

- golden green with block G on every L2 prompt of the golden tenant;
- an unchanged sweep makes 0 calls;
- adding a goal re-judges each open subject exactly once.

## Harsh's checklist — in order

1. **Record a fixture first:** the dossier text and the fingerprint of one subject on a tenant **without** goals, before any change. It is test 1's byte-equal baseline.
2. **Write the tests first:**
   - `tests/reason/l2/test_goals_block.py` (PG);
   - `tests/reason/l2/test_goal_fingerprint.py` (pure).
3. **Build:**
   - `reason/l2/snapshot.py` (read the goals; `linked` stays empty until G4);
   - `dossier.py` (`TITLES['G']`, `_goals`, the version bump);
   - `sweep.fingerprint_of`;
   - `contracts/reasoning_result.TRIGGER_GOAL_CHANGED`;
   - the `prompt.py` paragraph and the version bump.
4. **Re-record every golden cassette** with the ideal reader (`scripts/golden_eval.py --record`, all cases), then the resync and the door. Expect every L2-path key to change; the **board must not move**.
5. **Run `test_an_unchanged_sweep_costs_nothing`** on a fresh DB: the second sweep must make 0 calls.
6. **Mutation proofs:**
   - goal ids left out of the catalogue → G3's test fails (write it as a guard now);
   - the "only when live goals" guard dropped → test 1 fails.
7. **Guards, hermetic, push, CI. Update** `03-LOG` (cassette count re-recorded) and `04-FOR-HARSH`.

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G2. Add dossier block G (the approved goals, with ids) and the goal keys of the L2 fingerprint.

**Read first:**
- the preamble;
- `STEP-G2-goals-in-the-snapshot.md`;
- `reason/l2/dossier.py`, `snapshot.py`, `sweep.py` (`fingerprint_of`), `prompt.py`;
- `context/goals.py` (from G1).

**You own:**
- `reason/l2/snapshot.py`, `reason/l2/dossier.py`, `reason/l2/sweep.py` (`fingerprint_of` and the trigger only), `reason/l2/prompt.py`;
- `contracts/reasoning_result.py` (the trigger constant only);
- the two new test files;
- the re-recorded cassettes.

**Do not touch:**
- blocks A–F's text;
- the expert pass (`reason/expert/`);
- any case expectation.

**Acceptance:**
- the byte-equal no-goal test;
- 0 calls on an unchanged sweep;
- the golden board unchanged;
- two mutation proofs.
