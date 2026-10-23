# 07 · Goals: from free-text lines to objects that every card moves

**Written for:** coding agents (units) and Rohit (one decision).
**Fixes:** "no card carries a goal", "the Goals page shows lines with no progress", and "goals have to be typed by hand". Rohit, 23 Oct: *"aise bar bar goals manually nhi dal sakte"*.
**Target:** the `/preview` Goals page. 10 goals, each with a category, a progress basis and the cards that move it, plus 2 proposals approved in one click. The goal-by-goal table (how the brain should produce each one) is in [GeniOS-011 07 §2 "The 10 goals"](../GeniOS-011/07-IDEAL-PREVIEW-LIVE.md).
**Architecture:** [GeniOS-008 00-ARCHITECTURE](../GeniOS-008/00-ARCHITECTURE.md) (amended by S26.U3 ✅ `742859dd`) and [GeniOS-009](../GeniOS-009/) G1–G9. The goal object lives in L3. L2 **proposes** goals and states each move's `GoalImpact`. L3 **admits** a proposal as `proposed`. A human approves. L5 shows the goal on the card.

---

## What exists today, and how it got here

| Piece | Where | What it does |
|---|---|---|
| A "goal" | `company_brief_lines` with `section = 'goals'`, status `accepted` (migration 0195; `contracts/company_brief.py:38`) | one line of free text. No id other than the line's, no target, no progress, no link to any situation or card. |
| How goals reach the model | `CompanyBrief.prompt_block()`, the brief block of the dossier | as prose under "Goals now" |
| Proposals | pending brief lines, made by `reason/brief_drafter.draft_company_brief` (`:247-293`), weekly, via `reason/brief_review.run_company_brief_reviews` (`:62`, called from `api/routes.py:1678`) | **S27.U1 ✅** (`bb0060b7`): the drafter now runs for every tenant and sees files, open situations and in-motion lines (`reason/brief_patterns.py` `_SITUATIONS`/`_IN_MOTION`/`_GOALS` `:143-168`, at most 25 each), and proposes **one goal per piece of work** (`_one_goal_per_work` `:216`). Prompt v4, `MAX_TOKENS 4000`, thinking off. |
| Accepting | `POST /v1/company-brief/proposals/{line_id}/decide` (`api/company_brief_routes.py:127`), account owner only (`require_account_owner`) | the line becomes `accepted` |
| Goal routes | none. `GET /v1/goals` is planned (the dashboard's `src/lib/api-goals.ts` says so) but not built | — |
| Goal tables | none. `GoalProposal` / `GoalImpact` do not exist in `contracts/`. (`contracts/reasoning.py:371` `Goal` is the generic L4 request goal, unrelated.) The note reserving migrations ≥ 0251 for goals is stale: 0251 is `daily_health`. | — |
| Goals page | dashboard `src/product/internal/dashboard/goals/live.ts` `liveGoalsView`: accepted lines become goal cards with target "Not set yet", progress unknown, `cards: []`, `tags: []`; pending lines become "goals to finalise" (4 questions packed into the line, ≤ 200 characters) | it shows lines, not goals |
| Home | `homepage/sections/genios-at-work.tsx:658` `const goals = sample ? SAMPLE_GOALS : []` | live goals are always empty |
| Cards page | ~`src/app/dashboard/cards/page.tsx:925`: "Not linked to a goal yet", hard-coded | — |

**Why it is like this:** GeniOS-009 planned the goal loop (G0–G9) with the weekly drafter as the only source of proposals, and the drafter read memory *patterns*, never the graph's work. So even after G1–G9 a workstream could not become a goal on its own: a plan gap recorded in [GeniOS-011 01](../GeniOS-011/01-WHAT-WENT-WRONG.md). S26.U3 amended the plan so L2 proposes; S27.U1 is the interim.

---

## The goal object (what S28 builds)

The authority is [GeniOS-008 00-ARCHITECTURE "Goals"](../GeniOS-008/00-ARCHITECTURE.md) (amended 23 Oct with Rohit's yes, S26.U3). Summarised here so an agent can build without reading three folders; **if this summary and the architecture disagree, the architecture wins.**

**The goal object (L3 owns it), table `company_goals`, every change a new revision row:**

| Field | Meaning |
|---|---|
| `goal_id` | stable id other layers point to (`goal:<id>` in a prompt) |
| `statement` | the founder's words, ≤ 200 characters |
| `status` | `proposed` → `approved` → `active` → `completed` · `superseded` · `cancelled` |
| `source` | `founder` · `brief` (a drafter line the founder accepted) · `inferred` (a proposal still waiting) |
| `department` | a live domain of the tenant |
| `owner_seat`, `metric`, `target`, `deadline`, `parent_goal_id` | set by a person, or proposed and shown before approval; **never chosen by a model** |
| `subject_ref`, `evidence_refs` | for an inferred goal: the piece of work (`file:<id>`) and the lines it cites |
| `approved_by`, `approved_at` | required for `approved`/`active` by a check constraint |

**Rules that shape the units:**
- **One goal per piece of work** (D10): one application, one raise, one hire, one partner. A broad goal stays; a goal for one piece of work may name it as its parent.
- **The door is the company brief** (D11). A goal is born when a brief `goals` line is accepted. A proposed goal is a pending brief line, and L3 syncs `company_goals` from the brief every sweep. One approval path: `POST /v1/company-brief/proposals/{line_id}/decide`, owner only, one click.

**`GoalImpact`** (L2 writes it on a move, L3 admits it as a link): `goal_ref` (only a goal block G printed), `relation` (`advances` · `threatens` · `depends_on` · `unclear`, a word, never a score), `why`, `evidence`, `size_basis`. L3 writes a `goal_situation_links` row only when the situation is ADMITTED and the goal is approved or active.

**`GoalProposal`** (L2 proposes, L3 admits, a human approves): `statement`, `subject_ref` (filled by code, never named by the model), `why`, `evidence` (at least one is the company's own act), optional `parent_goal_ref`, `deadline`, `target`, `metric`. At most one per judgment, none when a printed goal already names the work. **L3 admission** (`context/goal_admission`) HOLDs a duplicate, a proposal over the weekly cap (D12: 3 a week per tenant), or one with no evidence of the company's own act; an ADMIT writes a **pending** brief `goals` line, never an approved goal.

**Two additions this folder proposes** (each needs the architecture amended, Rule 1.4, Rohit's yes):
- `category` on the goal (see N2 below);
- a **progress basis** shown with each goal: `counted` (n of m from linked situations), `unknown` (with why: "the portal is not readable"), or `blocked` (with what is missing: "no billing source"). This is how G5 (S30.U2) presents progress; it is computed, never stored as a model's number.

---

## The units, in order

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S26.U1** | Rohit | The goal decisions | default (recommended): L2 proposes one goal per workstream in motion; Rohit approves in one click; an approved goal never changes without him; the drafter stays as a weekly second source until S29 lands. A skipped decision takes its default. | logged | 🔒 Rohit |
| **S27.U3** | Claude (dashboard, dummy first) | Home and Goals page show the brief's goals and proposals | Home reads `GET /v1/company-brief` instead of `[]`; the Goals page shows proposals with approve/reject. `/preview` is the dummy: Rohit confirms "make it like /preview" before real files change. | Home shows the accepted goal lines | ⬜ |
| **S27.U4** | Rohit | Read and decide the drafter's proposals | — | — | 🔒 |
| **S28.U1** | Claude | Goal contract and tables | `contracts/goals.py` (the goal object, `GoalImpact`, `GoalProposal` exactly as the architecture defines them), migration **next free number at merge time** (0252 is claimed by S34.U3; run `ls migrations` before naming) creating `company_goals` (revision rows), `goal_situation_links`, and the check constraint on `approved_by`; the L3 sync that builds `company_goals` from brief `goals` lines every sweep | a fresh DB has the tables; an accepted goals line appears as an `approved` goal on the next sweep; a pending line appears as `proposed` and is never printed to the model as the company's goal | ⬜ |
| **S28.U2** | Claude | Read routes; approval stays on the brief door | `GET /v1/goals` (goals with status, department, category, progress and linked card ids) and `GET /v1/goals/{id}`. Approval and rejection stay on `POST /v1/company-brief/proposals/{line_id}/decide` (one door, D11); the goal carries its `line_id` so every surface can call it in one click | the dashboard reads goals without parsing brief lines | ⬜ |
| **S28.U3** | Claude | Golden case F72 and the reconsideration spec | a synthetic accelerator that passed and offered to reconsider (no real names) | F72 is in the golden set | ⬜ |
| **S29.U1** | Claude | Block G in the dossier | live goals with ids, and pending proposals listed apart, in both dossiers | the judgment can cite a `goal_id` | ⬜ |
| **S29.U2** | Claude | `GoalImpact` in the judgment | every move states which goal it moves and how; the claim check verifies the cited goal exists | the golden investor case carries `goal_id` + `advances` | ⬜ |
| **S29.U3** | Claude | L2 proposes a goal, L3 admits it as a proposal | when a judged file is in motion and no printed goal names it, the `ReasoningResult` carries one `GoalProposal`; `context/goal_admission` (new) ADMITs, HOLDs or REJECTs by code (duplicate, weekly cap of 3, no own-act evidence); an ADMIT writes a **pending** brief `goals` line | the synthetic reconsideration case produces one pending line citing its file; a second judgment on the same file produces none | ⬜ |
| **S29.U4** | Claude | F72 green, with mutation proofs | — | — | ⬜ |
| **S30.U1** | Claude | Goal ↔ situation links on ADMIT | an ADMITted situation whose move carries `GoalImpact` on a live goal gets a `goal_situation_links` row | — | ⬜ |
| **S30.U2** | Claude | Goal progress | `counted` from linked situations' states (e.g. "3 of 7 programme steps done"); `unknown` and `blocked` carry their reason; recomputed when a link changes | the 10 preview-shaped synthetic goals show the right basis | ⬜ |
| **S31.U1** | Claude | Cards carry `goal_refs` and a goal line | a `cards.goal_refs` column (in S28.U1's migration or the next), filled from the move's `GoalImpact`; `GET /cards` and `GET /cards/{id}` return it; the card writer (S34.U3) writes the goal line from it | a card on a linked situation returns its goal | ⬜ |
| **S31.U2** | Claude | Goal board on the Cards route, behind `goal_board` | cards grouped by goal | — | ⬜ |
| **S31.U3** | Claude (dashboard, dummy first) | Goal row, proposed-goal chip, Home "goals waiting" | per `/preview` | Rohit approves the local render | ⬜ |
| **N2** (from 07) | Claude | Categories | see below | — | ⬜ |
| **S32–S33** | Claude + Rohit | check-in states, human decides, outcomes move goals, the North Star | later; not needed to match `/preview` | — | ⬜ |

---

## Categories (N2), made general

Rohit's eight categories (investment, funding, business, sales, projects, progress, process, hiring) are how **a founder** sorts Admin work. Another customer's Admin will sort differently. So the category must not be hard-coded in the engine.

| Piece | Where | Rule |
|---|---|---|
| The list | each domain declares its categories in Plane D: `Domain Expertise/Admin Expertise/registry/category-map.yaml` (new, reviewed like any Plane D file) | Admin's default list is Rohit's eight; a tenant may rename through the brief, never in code |
| The map | the same file maps each capability (and each work kind: investor → investment, program → funding, intro → business, customer → sales, hiring → hiring, compliance → process, vendor → process) to a category | an unmapped capability gives `null`, never a guess |
| Where it is computed | by code, at compile time (`packs/compiler/`) for capabilities, and from the work kind for files | the model never picks a category |
| Where it is stored | `cards.category` (via `deliver/card_builder.py`) and `company_goals.category` (a goal's category is its subject's work kind, editable by the owner; an architecture amendment, Rohit's yes) | — |
| Where it is read | `GET /cards`, `GET /v1/goals`; the dashboard's filter chips (N3) | — |
| Test | a test pins every map entry to an existing capability | — |

Note: the dashboard already has an `AdminTag` type with 8 fixed tags (`src/product/internal/dashboard/goals/types.ts:88-90`) that live goals never fill (`tags: []`). N3 replaces it with the brain's `category`.

---

## After this file: what should be true

1. A goal is an object with an id, a category, a state and a progress basis.
2. L2 proposes goals from work in motion; Rohit approves in one click; nobody types goals by hand.
3. Every card on linked work shows the goal it moves.
4. The Goals page shows goals → their cards; Home shows them too.

**Expected after Step 6:** all 10 goals and the 2 proposals of `/preview`, and `i1` with its goal line. Record what actually appears in [13-LOG](13-LOG.md).
