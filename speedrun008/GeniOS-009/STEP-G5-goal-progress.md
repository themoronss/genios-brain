# STEP-G5 · Goal progress — L2 tools (`reason/l2/tools.py`) + L3 reads

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G1, G4.

**Source (MD):**
- *"Exact calculations → tested code"*;
- *"Goal progress, goal achievement aur task completion alag hain"*;
- *"missing data ko zero impact nahi maanna chahiye"*.


## At a glance

| | |
|---|---|
| **What** | Goal progress computed by code: **measured** (a registered metric), **counted** (open links by relation; verified outcomes join from G9), or **unknown**, with the reason. |
| **Why** | MD: *exact calculations → tested code*; *missing data ko zero impact nahi maanna*. The model may cite progress; it never invents it. |
| **For what** | Block G (G2), the size basis of an impact (G3), the goal line and the board header (G6), goal-at-risk and completion (G9). |
| **How** | The `METRICS` registry (`files_at_stage`, `manual`; `verified_outcomes` is added by G9); `context/goal_progress.progress_of`; `tools.goals_tool`, printed with line ids; the API returns progress. |
| **What changes after** | Every live goal shows counted progress. Goals with a metric show measured progress. **Nothing ever reads 0 for "we don't know".** |
| **Done when** | §5 tests green · the golden tenant's goals all show counted progress · no path turns unknown into 0. |
| **Do not** | Add a metric without its own tests · return 0 for unknown · let the model compute. |

---

## 1 · What is true today

- `reason/l2/tools.run_tools(:35)` computes dates, reply hours and money (`amounts_tool:85`, Harsh `11e31e45`). Each result is a `ToolResult` printed in block E, with an id the claim check knows.
- `contracts/measured.Measured` holds a number with its n and its basis (STEP-10).
- **No goal arithmetic exists.** The golden goals have no metric ("Raise the seed round" has no number on it).

## 2 · Design

1. **A goal's progress is measured or it is unknown, never guessed.** Three outcomes:
   - `measured`: actual, target, the share, n and basis;
   - `counted`: the goal's open linked situations by relation — always available. From G9 it also counts verified outcomes;
   - `unknown`: with the reason, e.g. "no countable metric", "metric source not connected".
2. **Metrics are a closed registry**, `contracts/goal.METRICS`. Each one is a counter code can run on the graph, with its parameters. Version 1 has two. The third, `verified_outcomes`, ships with G9, because its table (`goal_progress_events`) is created and written there:

| Metric key | Counts | Params | Example |
|---|---|---|---|
| `files_at_stage` | workstream files of a kind whose stage is at or past a stage | `{kind, stage}` | investor files at "term sheet" |
| `verified_outcomes` *(added by G9)* | G9 progress events of this goal | `{}` | design partners signed: 3 |
| `manual` | the founder's own number, entered through PATCH `/v1/goals/{id}` with a date | `{}` | amount committed: ₹1.2 Cr |

   A new metric is a reviewed code change with its own tests, never a model's idea.
3. **`counted` is printed for every live goal**, measured or not. Example: *"3 open situations: 2 advance it, 1 threatens it"* (from G9: *"…; 0 verified outcomes"*). That is a fact the model can reason with, not a judgment.

## 3 · Units

| Unit | File | Does |
|---|---|---|
| G5.1 | `contracts/goal.py` | `METRICS` (the three keys + param schemas); `GoalProgress(state, actual, target, share_bp, n, basis, counted: Mapping[str, int], why)` |
| G5.2 | `context/goal_progress.py` (new) | `progress_of(conn, org_id, goal, *, at) -> GoalProgress`: runs the metric's counter on the graph (bounded queries, org-scoped); counts open links by relation (G4) and progress events (G9) |
| G5.3 | `reason/l2/tools.py` | `goals_tool(progress_by_goal) -> ToolResult`, printed in block G (G2) with a tool-line id per goal, so a `GoalImpact.size_basis` can cite it (G3) |
| G5.4 | `api/goal_routes.py` | `GET /v1/goals` returns `progress` per goal |

## 4 · LLM use

**None.** Calculators only. The model may cite a progress line; it may never state a number the line did not print (the number check).

## 5 · Tests

**`tests/context/test_goal_progress.py`:**
1. no metric → `unknown` with "no countable metric", and `counted` still filled;
2. `files_at_stage` on a fixture graph → the exact count, with n;
3. `manual` → the founder's number and its date as the basis;
4. a missing connector for the metric's source → `unknown`, never 0.

**`tests/reason/l2/test_goals_tool.py`:** the printed line ids are in the catalogue; a size cited from an unprinted line is refused (G3 `SIZE_NOT_PRINTED`).

**Mutation proof:** return 0 instead of `unknown` → test 4 fails.

## 6 · Done when

- every live goal shows `counted`;
- goals with a metric show `measured`;
- no path turns unknown into 0.

## Harsh's checklist — in order

1. **Tests first:**
   - `tests/context/test_goal_progress.py` (cases 1–4);
   - `tests/reason/l2/test_goals_tool.py`.
2. **Contract:** `METRICS` + `GoalProgress` in `contracts/goal.py`.
3. **`context/goal_progress.py`:**
   - `progress_of`, with bounded, org-scoped queries;
   - do **not** read `goal_progress_events` here: that table does not exist until G9. G9 adds the `verified_outcomes` metric and the verified count.
4. **`reason/l2/tools.goals_tool`.** Wire it into block G (G2's `_goals` prints the progress line and its id).
5. **The API:** `GET /v1/goals` returns progress.
6. **Mutation proof:** return 0 for unknown → test 4 fails.
7. **Re-record cassettes** if block G's text changed (it now prints progress lines); the board is unchanged.
8. **Guards, push, CI, logs.**

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G5. Compute goal progress (measured / counted / unknown) and print it in block G with tool-line ids.

**Read first:**
- the preamble;
- `STEP-G5-goal-progress.md`;
- `reason/l2/tools.py`;
- `contracts/measured.py`;
- `context/goals.py`, `context/goal_links.py`.

**You own:**
- `contracts/goal.py` (`METRICS`, `GoalProgress`);
- `context/goal_progress.py`;
- `reason/l2/tools.py` (`goals_tool`);
- `reason/l2/dossier.py` (the progress line in block G only);
- `api/goal_routes.py` (the progress field);
- the two test files;
- the cassettes.

**Do not touch:**
- the money tool;
- blocks A–F.

**Acceptance:**
- unknown is never 0;
- printed ids are in the catalogue;
- a mutation proof.
