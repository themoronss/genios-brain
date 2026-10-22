# 02 · The plan — goals, check-ins and outcomes on top of GeniOS-008

**Written for:** Rohit, Harsh and every coding agent.

**The detailed build spec is one file per group:** `STEP-G0-the-ground.md` … `STEP-G9-outcomes-move-goals.md`,
listed in [`00-START-HERE.md`](00-START-HERE.md). This file is the summary; where the two differ, the STEP
file wins.

**Status: PLAN ONLY.** Nothing in this file is built. Rohit opens each group (GeniOS-008 `01-RULES`
Rule 4). Every item names:
- what was expected;
- what is true now;
- how;
- why that way;
- what it changes;
- how it is verified.

**Target:** [`../GeniOS-008/00-ARCHITECTURE.md`](../GeniOS-008/00-ARCHITECTURE.md) plus the new requirements
N1–N8 in [`05-THE-SOURCE.md`](05-THE-SOURCE.md).

**Rules carried over from GeniOS-008:**
- the new path is built **beside** the old one;
- the golden set compares them;
- the switch happens only when the new path is at least as good;
- one writer per file;
- each unit has its own tests plus a mutation proof;
- CI runs the full suites (memory: full-suites-are-ci-and-harsh).

---

## G0 · Prerequisites — nothing below starts until these hold

| # | Item | True now | Done when |
|---|---|---|---|
| G0.1 | CI green on `speedrun008` | **RED** on `21b7ae10`. golden-pg: 10 cassette misses (F03 F07 F14 F24 F55 F56). database: 9 (F13/F29 re-decided on an unchanged sweep, a gate-count mismatch, a statement timeout). The last green run was `8ccf9a08`. | the CI run on the pushed head is green |
| G0.2 | the L2 path makes cards for one tenant | `l2_cards` exists, never default-on (`de795bb8`). Measured 22 Oct (`01` §1): 63 of 67 pass on both paths, the same four fail; F15 fails differently on the L2 path (5 held cards instead of 1) | F15 fixed on the L2 path; Rohit names the tenant; `l2_cards` is on; one week of side-by-side shows no lost card |
| G0.3 | admission decides that a situation exists | `l2_admissions` is shadow; 9 L3 writers still form situations before reasoning | GeniOS-008 L3-1 for at least the investor/intro type (`02-MIGRATION-PLAN` §4 order) |
| G0.4 | Rohit's decisions D1–D5 | open | answered, or defaults taken ([`08-DECISIONS.md`](08-DECISIONS.md)) |

## G1 · The goal object — L3 (`context/`) + L0 contract

- **Expected:** a goal is a typed, revisioned, approved object (N1).
- **True now:** goals are free-text lines in `company_brief_lines` (section `goals`):
  - the model drafts them (`reason/brief_drafter.py`);
  - the founder accepts or rejects (`api/company_brief_routes.py`, `platform/company_brief_store.py`);
  - `contracts/reasoning.Goal` and `contracts/execution.goal` are something else (a run's purpose, an execution's text).

**How:**

| Unit | What | Where |
|---|---|---|
| G1.1 | `contracts/goal.py` with the fields below | new |
| G1.2 | migration `company_goals` + `company_goal_revisions`, append-only revisions, org cascade FK, erasure list | `migrations/` next free number |
| G1.3 | `context/goals.py`: `sync_from_brief` (idempotent, writes only on change), `active_goals`, `revise` (compare-and-set), `set_status` | new |
| G1.4 | **promotion**: an ACCEPTED brief `goals` line becomes a goal (`source=founder` or `brief`); a drafter proposal not yet accepted becomes `status=proposed, source=inferred`. Done by `goals.sync_from_brief` as the first stage of every sweep. It is **not** a hook in `platform/company_brief_store` (`platform/` must not import `context/`; see `STEP-G1` §2) | `api/routes._run_l2_chain` stage `l3.goals_sync` |
| G1.5 | API: list, edit target/owner/deadline/metric, complete or cancel. Approval of an inferred goal stays on the brief's existing decide route | `api/` new `goal_routes.py` |

The fields of `contracts/goal.py`:
- `goal_id`, `org_id`, `department` (= domain, D1), `parent_goal_id`
- `statement`, `owner_seat`
- `metric`, `baseline`, `target`, `unit`, `deadline`
- `status`: one of `proposed | approved | active | completed | superseded | cancelled`
- `source`: one of `founder | brief | inferred`
- `evidence_refs`, `approved_by`, `approved_at`, `revision`

**Why that way.** The approval door already exists: the founder accepts brief lines. The document's
"inferred goal ≠ approved goal" (§5 invariant 2) is exactly the drafter-proposes, founder-accepts split
we already run. A goal without a metric is allowed: `metric` is nullable, and its progress then reads
"unknown", never 0.

**Changes:** goals become rows that other layers can point at.

**Verify:**
- accepting a brief goal line creates one active goal;
- accepting it twice creates one goal (idempotent);
- a rejected line creates none;
- an inferred goal is never `active` without `approved_by`;
- the tenant erasure removes the goal tables;
- a mutation proof on each rule.

## G2 · Goals in the snapshot — L3 → L2

- **Expected:** L2 reasons with the company's goals in view (N3).
- **True now:** the brief's goal lines reach prompts as text (`company_brief.prompt_block`), with no ids.
- **How:**
  - `reason/l2/snapshot.read_snapshot` adds the active goals that touch the subject's domain;
  - `reason/l2/dossier.build_l2_dossier` prints them as their own block with ids (`goal:<id>`), metric, target, deadline and current progress (from G5);
  - **trigger:** a goal approved, revised or cancelled re-opens the subjects linked to it (G4). It does so by entering the goal's revision into the fingerprint of linked subjects only.
- **Why that way:** the change gate is the single place that decides "re-reason". Putting the goal revision into the fingerprint re-reasons exactly the linked subjects, once.
- **Verify:**
  - a subject with no goal in its domain fingerprints as before (golden board unchanged);
  - approving a goal re-judges its linked subjects once, then 0 calls;
  - cassettes are re-recorded with the ideal reader (no spend).

## G3 · Goal impact in the judgment — L2 (`reason/l2/`)

- **Expected:** L2 says which goal a situation moves, how, and how sure it is (N2, N3).
- **True now:** `L2Judgment` (`contracts/reasoning_result.py`) has no goal field.
- **How:**
  - add `goal_impacts: tuple[GoalImpact, ...]` to `L2Judgment`. Each `GoalImpact` holds:
    - `goal_ref` (must be a `goal:` id the dossier printed);
    - `relation` — one of `advances | threatens | depends_on | unclear`;
    - `why`;
    - `evidence` (ids);
    - `size_basis` (the tool line it stands on, or "not measurable");
  - `reason/l2/prompt.py` asks for it in the judgment's own words;
  - the claim check refuses an unprinted goal id, and refuses a size the tools did not print;
  - the result hash omits the field when it is empty, so older rows hash the same.
- **Why that way:** the model judges meaning (relevance, contribution, dependency); code owns numbers (`00-ARCHITECTURE` model rules). A relation word, not a score.
- **Verify:**
  - a golden case written for it: the investor intro (F03) is linked to a "raise the seed round" goal as `advances`;
  - the declined intro (F64) is linked to nothing;
  - an invented goal id is refused by the check (mutation proof);
  - the board is unchanged elsewhere.

## G4 · Goal ↔ situation links — L3 admission (`context/l2_admission.py`)

- **Expected:** links are accepted state, with history, many-to-many (N2).
- **True now:** admission decides admit, hold or reject per situation; nothing about goals.
- **How:**
  - on ADMIT, each `GoalImpact` whose goal is `active` writes a `goal_situation_links` row;
  - a revision bump on change; the row closes when the situation resolves;
  - a goal that is `proposed` or `cancelled` → the link is HELD with a reason, never written;
  - written in the L2 pass's one transaction (the admission savepoint, as `fb429b78`).
- **Why that way:** the document's "L2 proposes, L3 admits" (§5 invariant 7) applies to relations as much as to situations.
- **Verify:**
  - an admitted judgment writes its link once per fingerprint;
  - HOLD writes none;
  - a resolved situation closes its links;
  - PG test + a mutation proof.

## G5 · The goal progress tool — L2 tools (`reason/l2/tools.py`)

- **Expected:** progress is computed, never guessed.
- **True now:** the tools compute dates, money and baselines; no goal arithmetic.
- **How:** for a goal whose metric the graph can count (e.g. closed deals, amount raised, applications submitted), compute `actual / target` with n and basis (the `contracts/measured` shape). Otherwise the progress is `unknown` with the reason.
- **Verify:**
  - pure tests;
  - a goal with no countable metric reads `unknown`;
  - the dossier line is printed only when measured.

## G6 · The goal on the card — L5 (`deliver/`)

- **Expected:** the card shows what goal is at stake (N1–N3, and [`06-CARDS-TARGET.md`](06-CARDS-TARGET.md)).
- **True now:**
  - the gold card already has situation, subject and role, what remains, why now, recommended, alternative, wait or stop, outcome window, success signal, do-nothing consequence, lane and confidence vector (migration 0065, STEP-14);
  - no goal line.
- **How:**
  - `cards` gets `goal_refs jsonb` and a rendered `goal_line` ("Moves: Raise the seed round — advances; 2 of 5 funds in diligence");
  - the board groups cards by goal, then by lane ([`06-CARDS-TARGET.md`](06-CARDS-TARGET.md) §3);
  - a card with no linked goal is shown under "Not linked to a goal", **counted, never hidden** (the `card_source` law).
- **Verify:**
  - render tests;
  - a card with a goal shows it;
  - one without is counted under "not linked";
  - the claim validator refuses a goal line not backed by an admitted link.

## G7 · Check-in states — L3 / L4 / L5

- **Expected:** verified ≠ reported; unknown ≠ overdue; conflicted; withdrawn (N4).
- **True now:**
  - card endings already separate VERIFIED from REPLIED, TAKEN, LAPSED, CLEARED, UNRECORDED (`context/file_outcomes.py`);
  - situations have `status` + `resolved_by`;
  - coverage receipts exist but the check-in does not read them.
- **How:**
  - the judgment writes a `definition_of_done` (one line, its evidence kind);
  - `context_situations` gets `resolution_state`: one of `open | reported_complete | verified_complete | overdue | unknown | conflicted | withdrawn`;
  - verified requires an evidence ref of the definition's kind;
  - before "overdue", the coverage receipt for the source and window must be complete, or the state is `unknown`;
  - the execution ladder (1/3/7/14 days) becomes the check-in clock.
- **Why that way:** the card ending vocabulary is already right and measured. G7 lifts it to the situation so a goal can read it.
- **Verify:**
  - a reported "done" with no artifact stays `reported_complete`;
  - a connector-down window gives `unknown`;
  - the artifact arriving flips to `verified_complete`;
  - mutation proofs.

## G8 · Decision → a human decides → delegation — L4 (`executive/`)

- **Expected:** delegation to people and agents within authority (N5).
- **True now:**
  - Harsh writes the DecisionObject on `situation_interpretations` (`f3cfd3c6`) with no reader;
  - `executive/sweep.py` auto-plans from `signals`;
  - `executive/delegation.py` has the four verbs (propose, approve, dispatch, result) and "no approval, no dispatch";
  - the execution ladder exists.
- **How:**
  - GeniOS-008 L4-1: L4 reads decision-ready DecisionObjects;
  - a human approves, rejects, defers or chooses;
  - the execution carries `goal_refs`;
  - agent steps go through `delegation.py` unchanged;
  - the old auto-plan path stays beside it until the switch rule holds.
- **Verify:**
  - no execution exists without a human decision row;
  - an agent dispatch without approval is refused (existing tests);
  - `goal_refs` travel to the execution.

## G9 · Outcome → goal progress → learning — L6 (`feedback/`)

- **Expected:** a verified outcome moves the goal; learning is governed (N6, N7).
- **True now:**
  - `execution_outcomes` and `situation_outcomes` are written; nothing moves a goal;
  - `macv_ledger` has no writer;
  - the behaviour and adaptive learning units are stubs.
- **How:**
  - a `verified_complete` situation or a verified execution outcome appends a `goal_progress_events` row (goal, situation, evidence, delta when measurable);
  - G5 reads it;
  - a learning candidate is filed through `feedback/brain_pipeline` (repetition, conflict and freshness checks; never one observation);
  - `macv_ledger` only after Rohit's D4.
- **Verify:**
  - one verified outcome adds one progress event;
  - a reported one adds none;
  - a single correction never publishes a brain entry (existing governance tests + new).

---

## Order and gates

```
G0 (CI green → l2_cards one tenant → admission gates one type → decisions)
 → G1 + G2   goals exist and L2 sees them              [shadow: no card change]
 → G3 + G4 + G5   L2 links situations to goals; L3 admits the links   [shadow]
 → golden: old vs new, side by side — the goal link must not lose a card
 → G6   the card shows the goal; the board groups by goal   [per tenant flag]
 → G7   check-in states on the situation
 → G8   L4 reads the DecisionObject; a human decides
 → G9   outcomes move goals; governed learning
```

Each arrow is one group:
- each unit has its own tests and a mutation proof;
- root + platform guards run per group (memory: guards-per-group);
- the group is pushed, and the CI run is read;
- [`03-LOG.md`](03-LOG.md) gets a line;
- [`04-FOR-HARSH.md`](04-FOR-HARSH.md) gets the flags, migrations and rollback.

## Not doing (and why)

- **Persona brain:** not in the Atlas (D3, default later).
- **A retrieval ranking formula:** exact reads first (`05-THE-SOURCE` §4).
- **A model in L3:** the model rules.
- **Sales / Support goals:** those domains stay off until Rohit opens them.
