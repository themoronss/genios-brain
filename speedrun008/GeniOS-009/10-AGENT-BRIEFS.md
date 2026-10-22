# 10 · Briefing a coding agent on a GeniOS-009 step

**Written for:** Harsh, when handing a step, or part of one, to a coding agent.

**How to brief:** paste **§1 below first**, then the **"Brief for a coding agent"** section at the end of the
step's `STEP-Gn-*.md`. The agent then has everything it needs without asking.

A brief that needs a follow-up question was written badly. Fix the brief here, not in chat.

---

## 1 · The common preamble (paste this first, every time)

```text
You are working in the GeniOS repository (Python 3.11 in CI, 3.13 locally; FastAPI; SQLAlchemy Core; Postgres).
GeniOS reads a founder's mail and calendar and turns them into "cards": one card per business situation,
saying what is going on and the best next move. The architecture has six layers, always named with their
package: L1 Enterprise Signals capture/ · L2 Reasoning reason/ + packs/ · L3 Context Graph context/ ·
L4 Executive executive/ · L5 Delivery deliver/ · L6 Learning feedback/. L2 proposes, L3 admits.

You are building one step of GeniOS-009 (goals, check-ins, outcomes). The plan lives in
speedrun008/GeniOS-009/. Before writing code, read, in this order:
  1. speedrun008/GeniOS-009/09-HARSH-HANDOVER.md §5 (the rules) and §6 (the commands)
  2. speedrun008/GeniOS-009/11-GLOSSARY.md
  3. the STEP file named in your task, top to bottom
  4. every file the STEP's "What is true today" section cites, at the line it cites

Rules you must follow:
  - Change only the files your task lists as yours. If another file must change, stop and say which and why.
  - Write the test first, see it fail for the right reason, then write the code.
  - Every rule you add gets a mutation proof: remove the rule, run its test, see it fail, restore.
    Run mutations with PYTHONDONTWRITEBYTECODE=1 and delete __pycache__ after restoring.
  - Never edit a golden case's expectation (tests/replays/specs/founder/*.json "expected"/"forbidden") to make a
    test pass. If a prompt changed, cassettes are re-recorded with:
        scripts/golden_eval.py --record <case ids>   (the ideal reader; no spend)
  - No new model call site. The model may only write the fields the STEP names, inside the existing L2 judgment.
    A model never scores, routes, picks a recipient, decides for a human, or does arithmetic.
  - Unknown is never 0 and never "overdue". Say what is missing.
  - Every upsert writes only on change (… where (…) is distinct from (…)).
  - New org-scoped table: references orgs (id) on delete cascade + the erasure list in api/account_routes.py
    + the account-delete cascade test + a reader for table_coverage.
  - Migration number: the next free one after checking both origin/speedrun008 and origin/harsh/mvp.
  - Never read or write a production database. Use the scratch DB in GENIOS_TEST_DATABASE_URL.
  - Do not push, do not merge, do not switch a feature on for any tenant. Harsh does those.

When you finish, report:
  1. the files changed, and why each;
  2. the exact test commands you ran and their last lines of output (pass/fail counts);
  3. each mutation proof: what you removed, which test went red, and confirmation it is restored;
  4. any golden case whose result changed, with before → after;
  5. a draft line for speedrun008/GeniOS-009/03-LOG.md;
  6. anything you could not do, and why. A skip is not a pass.
```

## 2 · Splitting a step between two agents

Split **by file, never by function**. One writer per file.

| Step | A natural split |
|---|---|
| G0 | G0.1 (CI) · G0.2 (`l2_cards` + F15) · G0.3 (outreach admission). Three agents, in that order, because each needs the previous green. |
| G1 | contract + migration + `context/goals.py` · API routes + tests |
| G3 | contract + validation · prompt + ideal reader + golden labels |
| G6 | `card_lines` + `card_builder` + claim validator · `deliver/board.py` + the API |
| G8 | contract + migration + `executive/decisions.py` · API + the delegation hook |

**The seam between the two halves** is the contract in the STEP file. Freeze it first: write and commit the
dataclass. Then hand out the two halves.

## 3 · Checking what comes back

**The agent's "it passes" is not evidence.** Re-run its commands yourself and read the output. Then check:
- the mutation proofs, by doing one yourself;
- `git diff --stat`: only the files its brief allowed;
- golden: `python -m tests.replays.l2_score` reports `new path loses 0`.
