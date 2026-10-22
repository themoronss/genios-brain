# 09 · Harsh — the handover: how to build GeniOS-009 from this folder

**Written for:** Harsh, and any coding agent Harsh hands a step to.

**From:** Rohit, with Claude, 22 Oct 2026.

**One line:** GeniOS-009 makes **goals** the thing GeniOS organises around. Every business situation is
linked to the goal it moves. The card says which goal. A check-in tells "done and proven" from "said done"
and from "we could not see". A human decides before work is created, and only verified outcomes move a goal.

---

## 1 · What this is, and why we are doing it

| Question | Answer |
|---|---|
| **What** | Ten build steps, G0 to G9, on top of the GeniOS-008 architecture (L1 → L6). Each step has its own `STEP-Gn-*.md` file. |
| **Why** | Today GeniOS sees situations and makes good cards: 63 of 67 golden cases pass, one card per subject, versions instead of pings (`01-AS-IS-CARDS.md`). But it has **no idea what the company is trying to achieve**. Goals are free-text lines in the company brief that nothing can link to. No card says what is at stake. A "done" click and a proven outcome look the same. A silent mailbox and a disconnected mailbox look the same. |
| **For what (whom it serves)** | The founder: they see their work grouped under their goals (raise the round, get recognised, hire, land partners). Each card says which goal it moves. They are never told something is overdue when GeniOS simply could not see. |
| **Source** | Rohit's *Goal Achievement Loop* document, `source/GeniOS-Goal-Achievement-Loop-Chat.md`. What we take from it and what we reject: `05-THE-SOURCE.md`. |
| **What it is not** | Not a new architecture. Not a rebuild of the card. Not more model calls: G1–G9 add **no new model call site**. The goal is read inside the existing L2 judgment (R-9). |

## 2 · Read this folder in this order (≈ 45 minutes)

1. `00-START-HERE.md` — the step table and status.
2. `05-THE-SOURCE.md` — what the document asks; the 8 new requirements N1–N8.
3. `01-AS-IS-CARDS.md` — what the cards are today, measured.
4. `06-CARDS-TARGET.md` — what the cards will be, field by field, and the board.
5. `07-LOOPS.md` — how goals, situations and the reasoning, context and learning loops connect to the code.
6. `02-PLAN.md` — the summary of G0–G9.
7. `08-DECISIONS.md` — the 8 decisions. **Ask Rohit for the open ones before G1.**
8. `11-GLOSSARY.md` — every term used here, in one line each.
9. **Then the one STEP file you are building**, top to bottom.

## 3 · How every STEP file is laid out

Each `STEP-Gn-*.md` has the same sections, in this order:

| Section | What it gives you |
|---|---|
| **At a glance** | what · why · for what · how · what changes after · done when · do not |
| Source (MD) | the lines of Rohit's document it implements |
| 1 · What is true today | the code as it is, with `file:line` |
| 2 · Design | the decisions, and why each was made that way |
| 3 · Units | every file and function to write or change; contracts and SQL written out |
| 4 · LLM use and cost | where the model is used (mostly nowhere new) and what it costs |
| 5 · Tests | test files, cases, golden cases, and the mutation proof for each rule |
| 6 · Flags, rollout, rollback | the per-tenant switch and the one-line way back |
| 7 · Done when | the exit condition |
| **Harsh's checklist** | the steps in order, with commands |
| **Brief for a coding agent** | a cold-start prompt you can paste to an agent for that step |

## 4 · The order — and why this order

```
G0 the ground ──► G1 goal object ──► G2 goals in what L2 reads ──► G3 goal impact in the judgment
                                                                          │
G6 goal on the card + board ◄── G5 goal progress ◄── G4 goal ↔ situation links ◄┘
        │
        ▼
G7 check-in states ──► G8 a human decides, then work ──► G9 verified outcomes move goals
```

| Order | Why it has to be in this place |
|---|---|
| **G0 first** | CI is red on `21b7ae10` (19 tests). On a red head you cannot tell your regression from an inherited one. Also: the goal reaches a card only through the L2 card path (`l2_cards`), so that path must be live on one tenant. |
| **G1 before G2** | Nothing can point at a goal that has no id. |
| **G2 before G3** | The model can only name goals it was shown, and the claim check refuses any other. |
| **G3 before G4** | A link is the ADMITTED form of an impact line; no impact, no link. |
| **G4 + G5 before G6** | The card's goal line is built from admitted links plus measured progress, never from raw model text. |
| **G6 before G7** | The check-in state is shown on the card and on the board. |
| **G7 before G8** | An agent's or a person's "done" must have somewhere to land that is not "resolved". |
| **G8 before G9** | Progress comes from verified outcomes of human-approved work. |

Each step is **built beside the old path, in shadow, behind a per-tenant switch** (GeniOS-008 `01-RULES`
Rule 2). Nothing a founder sees changes until its switch is on.

## 5 · The rules (the ones that have cost us before)

1. **One writer per file.** If Claude and you both touch a step, split by file, never by function.
2. **Never edit a golden case's expectation to make it pass.** A prompt change makes cassettes miss. Re-record with the ideal reader (no spend):

   ```
   GENIOS_TEST_DATABASE_URL=<scratch> .venv/bin/python scripts/golden_eval.py --record F03 F07 …
   ```

   The board can only move deliberately, written in `03-LOG.md`.
3. **Mutation proof for every rule.** Remove the rule, and its test must go red. Run the mutation with
   `PYTHONDONTWRITEBYTECODE=1` and delete `__pycache__` after restoring: a restored mutant can stay in the
   bytecode and run on.
4. **Migration numbers:** take the next free number **after checking both branches**
   (`git ls-tree origin/harsh/mvp migrations/` and `origin/speedrun008`). The 0191 → 0212 renumber is why.
   Every new org-scoped table needs:
   - `references orgs (id) on delete cascade`;
   - an entry in the erasure list (`api/account_routes.py`);
   - an entry in the cascade test;
   - a reader for `table_coverage`.
5. **Write only on change.** Every upsert has `… where (…) is distinct from (…)` (your `34779fe0` idiom). The 500 MB tier is the reason.
6. **A model never scores, routes, picks a recipient, decides for a human, or does arithmetic**
   (`GeniOS-008/00-ARCHITECTURE.md` "The model rules"). In GeniOS-009 the model only writes `goal_impacts`
   (G3) and `done_when` (G7), inside the existing R-9 judgment, and both are claim-checked.
7. **Unknown is never 0 and never "overdue".** Missing coverage is said, never filled in.
8. **Layer names:** product number + package. Write `L3 · context/goals.py`, never a bare digit from another numbering.

## 6 · The commands you will use

```bash
# 0. your scratch Postgres (never production — the golden runner refuses a production host)
export GENIOS_TEST_DATABASE_URL=postgresql+psycopg://postgres:<pw>@127.0.0.1:<port>/<scratch_db>

# 1. a step's own tests
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -q tests/context/test_goals_sync.py

# 2. the repo-wide guards (root + platform) before a commit of a group
.venv/bin/python -m pytest -q tests/test_*.py tests/platform

# 3. CI's hermetic job, without a database (skips must say "GENIOS_TEST_DATABASE_URL not set")
env -u GENIOS_TEST_DATABASE_URL .venv/bin/python -m pytest -q -m "not golden"

# 4. the golden set (what CI's golden-pg job runs)
GENIOS_GOLDEN_REQUIRED=1 .venv/bin/python -m pytest -q tests/replays tests/test_golden_labels_sheet.py
.venv/bin/python scripts/golden_score.py --assert-recorded "speedrun008/YC-II W27/03-FINDINGS.md"

# 5. old path vs L2 path, side by side (no spend, nothing recorded)
.venv/bin/python -m tests.replays.l2_score            # or: … l2_score F03 F15

# 6. every card the golden set makes, both paths, as JSON (this folder's measurement)
.venv/bin/python speedrun008/GeniOS-009/measurements/card_dump.py "$PWD" /tmp/cards.json [F03 …]
python3 speedrun008/GeniOS-009/measurements/card_report.py /tmp/cards.json summary   # or: cards | diff

# 7. after a push: read CI through the public API
curl -s "https://api.github.com/repos/themoronss/genios-brain/actions/runs?branch=speedrun008&per_page=3"
curl -s "https://api.github.com/repos/themoronss/genios-brain/actions/runs/<run_id>/jobs"
curl -s "https://api.github.com/repos/themoronss/genios-brain/check-runs/<job_id>/annotations"
```

## 7 · How to report a step done

1. **The step's "Done when" holds**, with the command output in hand. "It passes" without the output is not done.
2. **`03-LOG.md`** gets one new line: date · step · what changed · evidence (commit, CI run id, test counts).
   It is append-only; a correction is a new line.
3. **`04-FOR-HARSH.md`** gets that group's row updated:
   - migrations applied;
   - the switch and on which tenant;
   - what you saw;
   - how to roll back.
4. **`00-START-HERE.md`**: the step's status moves (planned → building → built → switched on).
   Rename the file `STEP-Gn-DONE-….md` only when its switch is on for a tenant and a week ran clean.
5. **Re-run the card dump** (§6.6) and note in `03-LOG` what changed on the board. **The board may only get better.**

## 8 · Who decides what

| Decision | Who |
|---|---|
| D1–D8 (`08-DECISIONS.md`) | Rohit. A default stands if unanswered. |
| The golden goal labels (`STEP-G3` §3.3, the "label at build time" row) | You label them in the label sheet; Rohit confirms |
| Turning a switch on for a tenant | Rohit names the tenant; you switch it on |
| `macv_ledger` value rule (D4) | Rohit; G9's value part waits for it |
| Anything that changes `GeniOS-008/00-ARCHITECTURE.md` | Rohit only |
