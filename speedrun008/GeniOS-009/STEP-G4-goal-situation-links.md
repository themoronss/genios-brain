# STEP-G4 · Goal ↔ situation links — L3 admission (`context/`)

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G3, G0.3.

**Source (MD):**
- *"L2 relationships aur possible impact reason karta hai; L3 unhe accepted, traceable relationships ke roop mein maintain karta hai"*;
- *"Ek situation multiple goals ko affect kar sakti hai. Ek goal multiple situations se influence ho sakta hai"*;
- *"agar evidence insufficient hai, toh ise confirmed causal relationship ki tarah store nahi karna chahiye"*.


## At a glance

| | |
|---|---|
| **What** | The admitted, accepted-state form of a goal impact: `goal_situation_links`, many-to-many, with history. |
| **Why** | MD: *L2 proposes, L3 admits*. A relation is state, and state is L3's. A model output alone must never be a link. |
| **For what** | G2 (linked goals in the fingerprint), G5 (counted progress), G6 (the goal line), G9 (which goal an outcome moves). |
| **How** | A pure `links_of` per admission (the table in §2). `write_links` inside the admission savepoint. `close_links` / `close_links_of_ended`. The interpretation records the goal impacts. |
| **What changes after** | Admitted situations carry their goal links. A non-live goal gets none. An ended situation leaves no open link. **Still invisible to the founder.** |
| **Done when** | The labelled golden situations carry their links · no link to a non-live goal · no open link on an ended situation. |
| **Do not** | Write a link on HOLD/REJECT, to a non-live goal, or for a subject-level (`'-'`) admission · rewrite unchanged links. |

---

## 1 · What is true today

- `context/l2_admission.decide(:76)` is pure. Per (subject, situation) it returns an `Admission`: ADMIT, HOLD or REJECT, with op, reason and lane.
- `write_admissions(:128)` upserts it to `l2_admissions` (0249); `record_interpretations(:176)` appends a `situation_interpretations` row for each ADMIT.
- Both run in the L2 pass's one transaction, inside a savepoint (`fb429b78`).
- **Nothing about goals.**

## 2 · Design

1. **A link is accepted state, not a model output.** It is written only when its situation's judgment is
   ADMITTED and its goal is LIVE.
2. **Per impact line:**

| Situation admission | Goal status | Relation | Link decision |
|---|---|---|---|
| ADMIT | live (approved / active) | advances · threatens · depends_on | **write**, `state = 'held_evidence'` if `evidence` is empty, else `'linked'` |
| ADMIT | live | unclear | **write**, `state = 'unclear'` (shown as "may matter", never asserted) |
| ADMIT | proposed / cancelled / completed / superseded | any | **hold**: no row, a reason in the receipt (`goal_not_live`) |
| HOLD or REJECT | any | any | **no row**; the subject's earlier links stay as they were |
| ADMIT of `close` (the situation ends) | — | — | **close** every open link of that situation (`closed_at`, `closed_why = 'situation closed'`) |

3. **One row per (situation, goal)**, upserted, with a revision bump only when the relation, why or evidence changed. It grows with situations, never with sweeps: the 500 MB rule (Harsh `480f7cd4`).
4. **Subject-level** (`situation_id = '-'`, a seed with no row yet) writes no link. A link always names a real situation.

## 3 · Units

### G4.1 · Migration `migrations/0251_goal_situation_links.sql`

```sql
create table if not exists goal_situation_links (
    org_id              text        not null references orgs (id) on delete cascade,
    goal_id             text        not null,
    situation_id        text        not null,
    subject_ref         text        not null,
    relation            text        not null,
    state               text        not null,
    why                 text        not null,
    evidence            jsonb       not null default '[]'::jsonb,
    size_basis          text,
    result_fingerprint  text        not null,
    revision            int         not null default 1,
    linked_at           timestamptz not null,
    updated_at          timestamptz not null,
    closed_at           timestamptz,
    closed_why          text,
    primary key (org_id, goal_id, situation_id),
    constraint gsl_relation_ck check (relation in ('advances','threatens','depends_on','unclear')),
    constraint gsl_state_ck check (state in ('linked','held_evidence','unclear'))
);
create index if not exists gsl_open_by_goal on goal_situation_links (org_id, goal_id) where closed_at is null;
create index if not exists gsl_open_by_subject on goal_situation_links (org_id, subject_ref) where closed_at is null;
```

The table needs four more entries:
- the tenant erasure list (`api/account_routes.py`);
- the account-delete cascade test;
- `table_coverage`, whose readers are G2 (`links_for_subject`), G5 (`open_links_for_goal`) and G6 (the card's goal line).

### G4.2 · `genios_engine/context/goal_links.py` (new)

| Function | Pure? | Does |
|---|---|---|
| `links_of(admission, result, goals: Mapping[str, Goal]) -> tuple[LinkDecision, ...]` | pure | the table in §2 for one admission |
| `write_links(conn, decisions, *, at) -> int` | — | one upsert statement; `on conflict … do update … where (relation, why, evidence) is distinct from …` with `revision = revision + 1` |
| `close_links(conn, *, org_id, situation_id, at, why) -> int` | — | closes the open links |
| `links_for_subject(conn, org_id, subject_ref) -> tuple[(goal_id, revision, relation), ...]` | — | G2's read |
| `open_links_for_goal(conn, org_id, goal_id) -> list[Row]` | — | G5, G6, the goals API |
| `close_links_of_ended(conn, org_id, *, at) -> int` | — | a sweep step: closes the links of situations that ended outside the L2 pass (a human close, a statement resolution, dormancy, `df3c2aa8`) |

### G4.3 · The call site (`reason/l2/sweep.py`, the write step G1)

Inside the same admission savepoint:

```
admissions = admission.decide(...)
admission.write_admissions(conn, admissions, at=now)
admission.record_interpretations(conn, ...)
goals = {g.goal_id: g for g in goals_mod.active_goals(conn, org_id, at=now)}   # read once per pass
goal_links.write_links(conn, [d for a in admissions for d in goal_links.links_of(a, result_for[a], goals)], at=now)
```

Then `close_links_of_ended` is called once per sweep, after the pass.

### G4.4 · The interpretation

`interpretation_of` (`l2_admission.py:141`) gains `goal_impacts`: the admitted lines, so the situation's
append-only history says which goals it touched at each judgment (Atlas v2 L3: *"append a new interpretation,
never overwrite"*).

## 4 · LLM use

**None.** Admission is code.

## 5 · Tests

**`tests/context/test_goal_links.py`:**
1. (pure) each row of §2's table, one case each;
2. (PG) an admitted judgment writes one link; the same fingerprint again writes 0 rows (`xmin` unchanged);
3. (PG) the same goal, a changed `why` → revision 2;
4. (PG) a HOLD writes none, and earlier links stay;
5. (PG) the situation closed by a human → `close_links_of_ended` closes its links;
6. (PG) a proposed goal → no row and the `goal_not_live` reason.

**Golden:** the G3 marking rule now reads the admitted links. F03's run must hold one open `advances` link to "Raise the seed round".

**Mutation proofs:**
- drop the live-goal check → test 6 fails;
- drop the `is distinct from` → test 2 fails;
- skip `close_links_of_ended` → test 5 fails.

## 6 · Flags, rollback

- **Flags:** rides `l2_reasoning` (shadow: nothing a person sees reads links until G6).
- **Rollback:** skip the `write_links` call; the table stays.

## 7 · Done when

- the golden tenant's admitted situations carry the labelled links;
- no link exists to a non-live goal;
- an ended situation leaves no open link.

## Harsh's checklist — in order

1. **Migration** (§3 G4.1) with the number check, plus the erasure list, the cascade test and `table_coverage`.
2. **Tests first:** `tests/context/test_goal_links.py`:
   - case 1 is pure: one row of §2's table each;
   - cases 2–6 are PG.
3. **Build `context/goal_links.py`** (§3 G4.2).
4. **The call site** in `reason/l2/sweep.py`, inside the admission savepoint (§3 G4.3). Call `close_links_of_ended` once per sweep, after the pass.
5. **`interpretation_of`** gains `goal_impacts` (§3 G4.4). It is append-only, so a pre-G4 interpretation is untouched.
6. **Switch the G3 marking rule** to read admitted links. F03 must hold one open `advances` link to "Raise the seed round".
7. **Mutation proofs:**
   - the live-goal check;
   - `is distinct from`;
   - `close_links_of_ended`.
8. **Guards, push, CI, logs.**

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G4. Write goal ↔ situation links on ADMIT, close them when the situation ends, and read them for G2.

**Read first:**
- the preamble;
- `STEP-G4-goal-situation-links.md`;
- `context/l2_admission.py` (all of it);
- the admission call site in `reason/l2/sweep.py`.

**You own:**
- `migrations/0251_goal_situation_links.sql` (or the next free number), `context/goal_links.py`, `tests/context/test_goal_links.py`;
- in `reason/l2/sweep.py`, only the lines that call `goal_links`;
- `context/l2_admission.interpretation_of` (the `goal_impacts` key).

**Do not touch:**
- `decide()`'s admit / hold / reject logic;
- `deliver/`.

**Acceptance:**
- the §2 table fully covered;
- idempotent writes (`xmin`);
- three mutation proofs;
- F03's link.
