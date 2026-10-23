# STEP-G1 · The goal object — L3 (`context/`) + L0 (`contracts/`)

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Amended 23 Oct 2026** (GeniOS-011 S26.U3, Rohit's decisions D7, D9–D12 in
[`08-DECISIONS.md`](08-DECISIONS.md)): unit **G1.6** adds the structured proposal fields, so a goal the L2
judgment proposes (G3.5 → G4.5) reaches the same door with its work, deadline and parent.

**Source (MD):**
- *"Store goals as first-class business objects connected to departments, people, initiatives, situations, evidence and outcomes"*;
- *"inferred goal ko silently company commitment nahi banana chahiye"*;
- the goal lifecycle *Proposed → Owner review → Approved → Active → Completed / Superseded / Cancelled*.


## At a glance

| | |
|---|---|
| **What** | A real goal object: `company_goals` plus its revisions, synced from the company brief's accepted goal lines, with an API to set owner, metric, target and deadline. |
| **Why** | Today a goal is free text in `company_brief_lines` (section `goals`). Nothing can point to it, measure it, or link a situation to it. MD N1: *goals as first-class business objects*. |
| **For what** | Every later step needs a goal **id**: G2 prints it, G3 names it, G4 links it, G6 shows it, G9 moves it. |
| **How** | The contract `contracts/goal.py`; a new migration (the next free number at build time, ≥0251); `context/goals.py` with an idempotent `sync_from_brief`, called as the first stage of every sweep; `api/goal_routes.py`. **The founder's accept on the brief stays the only approval door.** |
| **What changes after** | The golden tenant has 5 active goals with ids. A goal proposal (the drafter's, or after G4.5 the L2 judgment's) is a `proposed` goal that can never become active without the founder. **Nothing a founder sees changes yet.** |
| **Done when** | `GET /v1/goals` shows the golden tenant's 5 active goals · tests + mutation proofs green · CI green. |
| **Do not** | Make a goal active from code or a model · import `context/` from `platform/` · write goal rows on every sweep · change any prompt (G1 must cause **zero** cassette misses). |

---

## 1 · What is true today

- **Where goals live:** lines in `company_brief_lines` with `section = 'goals'`, columns at `migrations/0195_company_brief.sql:22`.
- **Statuses:** `proposed | accepted | rejected | removed` (`platform/company_brief_store.py:48-51`).
- **Who proposes:** the model drafts them (`reason/brief_drafter.py`). The founder accepts or rejects (`company_brief_store.accept:172`, `api/company_brief_routes.py:127`) or adds one directly (`add:236`).
- **The golden tenant already has five accepted goals**, in `tests/replays/specs/founder/brief/company_brief.json`:
  1. Raise the seed round
  2. StartupSetu recognition for Nimbus Labs Private Limited
  3. Get into accelerator and incubator programs
  4. Hire a Founding AI Engineer
  5. Land design partners
- **What a goal line lacks:** id for other layers, owner, metric, target, deadline, department, revisions.
- **Similar names that are something else:** `contracts/reasoning.Goal` (a reasoning run's purpose) and `contracts/execution.goal` (an execution's text). Neither is touched.
- **Two goal-shaped tables already exist.** Neither is a company goal, neither links to a situation, and G1 does not touch them:

  | Table | What it is | Who reads it |
  |---|---|---|
  | `team_milestones` (`migrations/0151_team_milestones.sql:3`, :8-21) | "a dated goal with an owner seat": `title`, `due_at`, `owner_seat_id`, an optional scope | the team readiness pass (`reason/team/readiness.py:77` `load_milestones`; `:178` turns a milestone due soon into a team item keyed `readiness:{milestone_id}`, stored in `team_situations` by `reason/team/emit.py:190`, never in `context_situations`) and `GET/POST /v1/team/milestones` (`api/team_routes.py:84`, `:94`) |
  | `seat_objectives` (`migrations/0133_seat_objectives.sql:35-52`) | one person's focus: a `domain` per seat, with an optional `valid_until` | the card queue read: cards in that domain come first for that person, nothing is hidden and no score moves (`deliver/store.py:988` `_objective_order`); set through `PUT /qualification/objectives` (`api/routes.py:2297`) |

## 2 · Design — and why that way

1. **The brief stays the door.** A goal is born when a brief `goals` line is ACCEPTED, by the founder or by
   their edit. A *proposed* brief goal line (the drafter's, or the L2 judgment's through G3.5 → G4.5) is an
   **inferred goal waiting for approval**. No second approval UI, and no way for a model to make a goal
   active (MD invariant 2). D11 (23 Oct 2026) confirms this door for both proposers.
2. **The goal table is synced FROM the brief, every sweep, idempotently.** `context/goals.sync_from_brief`
   runs at the start of `_run_l2_chain`:
   - it reads accepted and pending goal lines;
   - it upserts goals keyed by `brief_line_id`;
   - it cancels the goal of a removed or rejected line.

   Why a sync and not a hook inside `company_brief_store.accept`: `platform/` must not import `context/`
   (the layer-dependency guard). The golden runner seeds briefs through `company_brief_store.add`, so a hook
   would miss them. The sync writes **only when something changed** (the free tier — memory: the 500 MB lesson).
3. **The goal's own fields** (metric, target, deadline, owner, department) are edited on the goal, through the goal API.
   The brief line keeps the words. A revision row records every change.
4. **Department (D1)** defaults to the tenant's founder-facing live domain. That is `founder_office` when live, else
   `admin`; read from `platform/l3_activation`. It is editable per goal.

## 3 · Units

### G1.1 · Contract `genios_engine/contracts/goal.py` (new)

```python
GOAL_STATUSES = ("proposed", "approved", "active", "completed", "superseded", "cancelled")
GOAL_SOURCES = ("founder", "brief", "inferred")   # founder = added by the founder; brief = drafter line the
                                                  # founder accepted; inferred = a pending proposal
LIVE_GOAL = frozenset({"approved", "active"})

@dataclass(frozen=True)
class Goal:
    org_id: str
    goal_id: str                 # stable_ref("goal", {"org": org_id, "line": brief_line_id})
    statement: str               # the brief line's words, ≤ 200 chars
    department: str              # a live domain (D1)
    status: str                  # GOAL_STATUSES
    source: str                  # GOAL_SOURCES
    brief_line_id: str | None = None
    owner_seat: str | None = None
    parent_goal_id: str | None = None
    metric: str | None = None    # a key of contracts/goal.METRICS (G5) or None = not measurable
    metric_params: Mapping[str, Any] = field(default_factory=dict)
    baseline: Decimal | None = None
    target: Decimal | None = None
    unit: str | None = None
    starts_on: date | None = None
    deadline: date | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    revision: int = 1
```

**Refused in `__post_init__`** (a `GoalError` with a code, as `CompanyBriefError` does):
- an empty statement, or one over 200 characters;
- an unknown status or source;
- `status in LIVE_GOAL` while `approved_by is None` → `UNAPPROVED_LIVE`;
- `source == "inferred"` with `status != "proposed"` and no `approved_by` → `INFERRED_SELF_APPROVED`;
- a `target` with no `metric` → `TARGET_WITHOUT_METRIC`;
- `deadline < starts_on` → `DEADLINE_BEFORE_START`;
- `metric` not in `METRICS` → `UNKNOWN_METRIC`.

**`status` is derived on sync:**
- `active` when approved and `starts_on` is None or has passed;
- `approved` when approved and `starts_on` is in the future;
- `completed` / `superseded` / `cancelled` are set by G1.4 or G9 only.

### G1.2 · Migration `migrations/<next free ≥0251>_company_goals.sql` (new)

The number is the next free one **at build time**, at least `0251`: `0250` is `0250_screen_followup_read_path.sql`
(`93ea3cbe`), and local-only STEP-13b branches also hold a `0250_expert_review_attempts.sql`. Find it with the
check command in `00-START-HERE.md` (Migrations), which reads every branch. That is the 0191 → 0212 lesson.

```sql
create table if not exists company_goals (
    org_id          text        not null references orgs (id) on delete cascade,
    goal_id         text        not null,
    statement       text        not null,
    department      text        not null,
    status          text        not null,
    source          text        not null,
    brief_line_id   text,
    owner_seat      text,
    parent_goal_id  text,
    metric          text,
    metric_params   jsonb       not null default '{}'::jsonb,
    baseline        numeric,
    target          numeric,
    unit            text,
    starts_on       date,
    deadline        date,
    approved_by     text,
    approved_at     timestamptz,
    revision        int         not null default 1,
    created_at      timestamptz not null,
    updated_at      timestamptz not null,
    primary key (org_id, goal_id),
    constraint company_goals_status_ck check (status in
        ('proposed','approved','active','completed','superseded','cancelled')),
    constraint company_goals_source_ck check (source in ('founder','brief','inferred')),
    constraint company_goals_live_is_approved_ck check
        (status not in ('approved','active') or approved_by is not null)
);
create unique index if not exists company_goals_one_per_line
    on company_goals (org_id, brief_line_id) where brief_line_id is not null;
create index if not exists company_goals_live
    on company_goals (org_id, status) where status in ('approved','active');

create table if not exists company_goal_revisions (
    org_id      text        not null references orgs (id) on delete cascade,
    goal_id     text        not null,
    revision    int         not null,
    goal        jsonb       not null,          -- the whole goal as it became
    changed_by  text        not null,          -- seat id, 'brief_sync', or 'g9_outcome'
    why         text        not null,
    changed_at  timestamptz not null,
    primary key (org_id, goal_id, revision)
);
```

- Append both tables to the tenant erasure list (`api/account_routes.py`).
- Append both to the account-delete cascade test, and to `table_coverage` with a reader.

### G1.3 · Store `genios_engine/context/goals.py` (new)

| Function | Does | Writes |
|---|---|---|
| `sync_from_brief(conn, org_id, *, at) -> SyncCounts` | Reads every `goals` line. ACCEPTED → upsert a goal (`source = 'founder'` if `proposed_by == 'founder'`, else `'brief'`; `approved_by = decided_by`, `approved_at = accepted_at`). PROPOSED → upsert `source = 'inferred', status = 'proposed'`. REMOVED or REJECTED → set its goal `cancelled`, `why = 'brief line removed'`. Words changed on an accepted line → a new revision. | **Only rows whose content changed** (`on conflict … do update … where … is distinct from …`, the `34779fe0` idiom); a revision row per change |
| `active_goals(conn, org_id, *, at) -> tuple[Goal, ...]` | Goals with `status in LIVE_GOAL`, ordered by deadline (nulls last), then statement | — |
| `goal(conn, org_id, goal_id) -> Goal \| None` | One goal | — |
| `revise(conn, *, org_id, goal_id, by, at, why, **fields) -> Goal` | Validates through `Goal`; `revision + 1`; a revision row; compare-and-set on `revision` (a stale edit raises `GOAL_STALE`) | yes |
| `set_status(conn, *, org_id, goal_id, status, by, at, why) -> Goal` | completed / superseded / cancelled; a revision row | yes |
| `goal_set_digest(goals) -> str` | `stable_ref("goals", sorted((g.goal_id, g.revision) for g in goals))` — used by G2 | — |

Called from `api/routes._run_l2_chain`, as the first stage, `with stage("l3.goals_sync", org_id)`. Wrapped:
a failure is logged and counted in `failed_passes` (Harsh `7297b31a`) and never stops the sweep.

### G1.4 · API `genios_engine/api/goal_routes.py` (new, mounted in `api/routes.py`)

| Route | Body | Does |
|---|---|---|
| `GET /v1/goals` | — | live and proposed goals with progress (G5) and open linked situations (G4) |
| `PATCH /v1/goals/{goal_id}` | `{revision, owner_seat?, department?, metric?, metric_params?, baseline?, target?, unit?, starts_on?, deadline?, why}` | `goals.revise`; 409 on a stale revision |
| `POST /v1/goals/{goal_id}/status` | `{status: completed\|cancelled, why}` | `goals.set_status` |

- Approving or rejecting an inferred goal stays on the existing brief route (`/v1/company-brief/proposals/{line_id}/decide`). The next sweep syncs it.
- `org_admin` seats only, the same check as `executive/delegation.seat_is_org_admin`.

### G1.6 · Structured proposal fields at the door (amendment, 23 Oct 2026)

**Why.** A brief `goals` line holds words and evidence only. A goal proposed for one piece of work must also
carry *which* work, its parent goal, and the deadline or target the sources stated, so the founder sees
them before approving and the goal keeps them after. Without these fields the L2 proposal (G4.5) would
arrive as bare words, and the dedupe could not tell that two proposals rest on the same file. (Units
G1.1–G1.4, then G1.6: the number is the one GeniOS-011 cites; there is no G1.5.)

**What.**

| Part | Change |
|---|---|
| `contracts/goal.py` | `GoalProposalFields` (frozen): `subject_ref` (`file:<id>`), `why` (≤ 300 chars), `evidence_refs` (ids), `proposed_by` (`drafter` · `l2_judgment`), and optional `parent_goal_id`, `deadline`, `target`, `metric`. `from_mapping` / `as_mapping`. Refused: an unknown key (`UNKNOWN_FIELD`), a deadline that is not an ISO date (`BAD_DEADLINE`), a `target` without `metric` (`TARGET_WITHOUT_METRIC`, as G1.1), an empty `evidence_refs` (`PROPOSAL_WITHOUT_EVIDENCE`) |
| migration (with G1.2, the same next free number) | `alter table company_brief_lines add column if not exists goal_proposal jsonb;` with `check (goal_proposal is null or section = 'goals')`. `company_goals` gains `subject_ref text` and `evidence_refs jsonb not null default '[]'::jsonb` |
| `platform/company_brief_store.py` | `propose(..., goal_proposal=None)` validates it through `GoalProposalFields` and stores it; refused on any section but `goals`. `pending()` returns it. `accept()` keeps it unchanged. **This is the one G1 unit that touches the store**; G1.1–G1.4 still do not |
| `context/goals.sync_from_brief` | copies the fields onto the goal: `subject_ref`, `evidence_refs`, `parent_goal_id`, `deadline`, `target`, `metric`. A pending line → `source = 'inferred'`, `status = 'proposed'`, `approved_by` null. An accepted line → `approved_by = decided_by`, the fields kept |
| the drafter (`reason/brief_drafter`) | may fill `subject_ref` and `evidence_refs` from the work its goal rests on (`brief_patterns.work_of`, `file:<id>`, since GeniOS-011 S27.U1). Optional; its words and evidence do not change |

**The door does not change.** The founder approves in one click on
`POST /v1/company-brief/proposals/{line_id}/decide` with `{"decision": "accept"}` (owner only,
`require_account_owner`; `text` is optional). A rejection keeps the work quiet for `REJECTED_QUIET_DAYS = 90`
(`platform/company_brief_store.py`). Owner, metric and target are edited afterwards on the goal
(`PATCH /v1/goals/{goal_id}`, G1.4).

**Never active without a human.** `approved_by` comes only from the brief line's `decided_by`, which only
`accept` sets. Neither `proposed_by` nor anything inside `goal_proposal` is ever read as an approver.

## 4 · LLM use

**None in G1.** A goal is created by a human accept and synced by code. A model only *proposes*: the brief
drafter today (with the work in motion since GeniOS-011 S27.U1, the interim path), and the L2 judgment once
G3.5 and G4.5 are built (D7, D9). G1.6 adds fields to the door, no call.

## 5 · Tests

**`tests/context/test_goals_sync.py`** (PG):
1. an accepted goal line → one `active` goal, `approved_by` = the decider;
2. syncing twice → still one goal, and the second sync writes 0 rows (tuple `xmin` unchanged);
3. a pending drafter line → `proposed`, `source = 'inferred'`, never active;
4. a rejected or removed line → its goal is `cancelled` with a revision row;
5. edited words on an accepted line → revision 2, with the old words in the revision row;
6. the golden brief → exactly 5 active goals with those statements;
7. (G1.6) a pending line with a `goal_proposal` → a `proposed` goal carrying its `subject_ref`, `parent_goal_id` and `deadline`, `approved_by` null;
8. (G1.6) the same line accepted in one click (no `text`) → `active`, `approved_by` = the decider, the fields kept;
9. (G1.6) a `goal_proposal` on an `in_motion` line → refused by the store and by the check constraint.

**`tests/contracts/test_goal_contract.py`** (pure): each refusal code in G1.1 is raised by its own case.

**`tests/api/test_goal_routes.py`:** PATCH with a stale revision → 409; a non-admin → 403.

**Account delete:** the cascade test includes both tables.

**Mutation proofs** (`PYTHONDONTWRITEBYTECODE=1` — memory: a-restored-mutant-can-stay-in-the-bytecode):
- drop the `approved_by` check → test 3 fails;
- drop the `is distinct from` guard → test 2 fails;
- skip the cancel branch → test 4 fails;
- (G1.6) make the sync read `proposed_by` as the approver for a line with a `goal_proposal` → test 7 fails (the
  goal turns live without a human; `company_goals_live_is_approved_ck` would not catch it, because
  `approved_by` is set);
- (G1.6) drop the section check in `propose` → test 9 fails.

**Golden:** board unchanged. The sync adds rows, and no prompt reads goals yet; G2 is where prompts change.

## 6 · Flags, rollout, rollback

- **Flags:** none. Data only; no prompt and no card changes.
- **Rollback:** remove the `l3.goals_sync` stage call. The tables stay (additive).

## 7 · Done when

- the golden tenant shows 5 active goals in `GET /v1/goals`;
- (G1.6) a pending goal line with structured fields syncs to a `proposed` goal with those fields, and only the founder's accept makes it live;
- every test above passes with its mutation proof;
- CI is green.

## Harsh's checklist — in order

1. **Confirm D1, D2 and D7 with Rohit** (`08-DECISIONS.md`); otherwise the defaults stand.
2. **Pick the migration number** with the check command in `00-START-HERE.md` (Migrations): the next free one, ≥0251.
3. **Write the contract first:**
   - `tests/contracts/test_goal_contract.py` (one case per refusal code, §3 G1.1), red;
   - then `contracts/goal.py`, green.
4. **Write the migration** (§3 G1.2) and apply it on the scratch DB the way every other migration is applied.
   Check with `select 1 from information_schema.tables where table_name = 'company_goals'`.
5. **Write the PG tests first:** `tests/context/test_goals_sync.py` (§5, cases 1–6). Then `context/goals.py`.
6. **Call `goals.sync_from_brief`** as the first stage of `api/routes._run_l2_chain`:
   - `with stage("l3.goals_sync", org_id)`;
   - wrapped, so a failure counts in `failed_passes` and never stops the sweep.
7. **The API:** `api/goal_routes.py` + `tests/api/test_goal_routes.py`; mount it in `api/routes.py`.
8. **Register both tables** in:
   - the erasure list (`api/account_routes.py`);
   - the cascade test;
   - `table_coverage` (the reader is `active_goals`).
9. **Mutation proofs** (§5):
   - the `approved_by` check;
   - `is distinct from`;
   - the cancel branch.
10. **Golden:** `pytest tests/replays`. **Zero** cassette misses expected; a miss means G1 touched a prompt, so find it.
11. **G1.6** (after 1–10): `GoalProposalFields` in `contracts/goal.py`; the `goal_proposal` column and the two
    `company_goals` columns in the same migration; `propose(goal_proposal=…)` and `pending()` in
    `platform/company_brief_store.py`; the copy in `sync_from_brief`; tests 7–9 and their two mutations.
12. **Before pushing:** guards + hermetic; then push and read CI.
13. **Update** `03-LOG`, `04-FOR-HARSH` and `00-START-HERE`.

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G1. Build the goal object, synced from the company brief, and its API.

**Read first:**
- the preamble;
- `STEP-G1-the-goal-object.md`;
- `platform/company_brief_store.py` (`accept`, `add`, `accepted`, `pending`);
- `migrations/0195_company_brief.sql`;
- `contracts/company_brief.py`;
- `tests/replays/specs/founder/brief/company_brief.json`.

**You own (create):**
- `contracts/goal.py`, `migrations/<next free ≥0251>_company_goals.sql`, `context/goals.py`, `api/goal_routes.py`;
- `tests/contracts/test_goal_contract.py`, `tests/context/test_goals_sync.py`, `tests/api/test_goal_routes.py`.

**You may change (one line each):**
- `api/routes.py` — the stage call and the router mount;
- `api/account_routes.py` — the erasure list;
- the cascade test's table list.

**Do not touch:**
- `platform/company_brief_store.py`, except G1.6's `propose(goal_proposal=…)` and `pending()`;
- any prompt or dossier;
- `deliver/`, `reason/`.

**Acceptance:**
- §5's tests green;
- three mutation proofs;
- the golden tenant has 5 active goals;
- 0 cassette misses.
