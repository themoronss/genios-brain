# STEP-G8 · Decision → a human decides → work for a person or an agent — L4 (`executive/`)

**Written for:** Rohit, Harsh and every coding agent.

**Status:** planned. **Needs:** G4, G7. Also GeniOS-008 L4-1.

**Source (MD):**
- *"L4 authority, approvals aur ownership handle karta hai"*;
- *"recommendation ka matlab authorized decision nahi"*;
- *"agent draft email taiyar kar sakta hai; lekin contract approve karna ya financial commitment karna bina uchit authority ke nahi"*;
- *"An agent reporting 'done' is not sufficient evidence"*.


## At a glance

| | |
|---|---|
| **What** | Every needed decision becomes a **request** a human answers. Only an approved choice becomes work. Agents act only through the existing approval, and an agent's "done" is a report. |
| **Why** | MD: a recommendation ≠ an authorization; L4 owns authority. Today `plan_commitments` creates executions from signals with no human, and nothing reads the DecisionObject Harsh writes. |
| **For what** | Accountability: every execution traces to a person's choice and carries the goal it serves. |
| **How** | Migration 0254 (`decision_requests`); `contracts/decision.py`; `executive/decisions.py`; `execution.v1` gains `goal_refs` and `decision_request_id`; the sweep skips auto-planning when `human_decides` is on; the API; the delegation result → `reported_complete`. |
| **What changes after** | With `human_decides` on, the founder answers decision requests, and nothing is planned without one. |
| **Done when** | For the switched tenant every execution traces to a human choice · agent work only through approval · an agent's done never closes a situation. |
| **Do not** | Let a model choose, route or approve · dispatch without approval · let an agent result verify. |

---

## 1 · What is true today

- **The DecisionObject is written, and nobody reads it.** Harsh's `f3cfd3c6` appends it inside each ADMITTED interpretation: `{needed, who, what, by_when}` (`context/l2_admission.interpretation_of:141`).
- **L4 plans work without a human.** `executive/sweep.plan_commitments(:173)` turns open, authoritative `signals` into executions on its own (GeniOS-008: *"L4 auto-plans from `signals`, so no human decides first"*).
- **`execution.v1` has `goal: str`** (`contracts/execution.py:385`), a text field. It has no goal id.
- **Agent delegation is built** (`executive/delegation.py`):
  - `propose(:82)` — nothing is sent;
  - `approve(:94)` — a named human pins the exact bytes, with an expiry;
  - `claim_dispatch(:112)` — at most once;
  - `record_result(:135)` — exactly once, from the named agent only;
  - *"no approval, no dispatch — ever"*.
- **The reminder ladder** (1/3/7/14, max 6) and the lifecycle (`executive/lifecycle.py`) are built.

## 2 · Design

1. **The decision inbox.** A DecisionObject with `needed = true` on an admitted, decision-lane situation becomes
   one **decision request**, one per (situation, judgment fingerprint). The request carries:
   - the question (`what`);
   - who must decide (`who`, resolved to a seat by code from the file's people and the org's seats; unresolved = the org admin, **said**);
   - the options with their trade-offs (from `L2Judgment.options`);
   - by when;
   - the goal links (G4).
2. **A human chooses**: approve option N · reject · defer to a date · choose another wording. The choice is
   stored with who, when and what they saw (the request's hash).
3. **Only an approved choice becomes an execution** (`execution.v1`), carrying `goal_refs` and
   `decision_request_id`. An action whose owner is an agent goes through `delegation.propose` → the
   founder's `approve` → `claim_dispatch` → `record_result`, unchanged.
4. **An agent's "done" is a report.** `record_result(ok=True)` sets the situation's check-in to `reported_complete` (G7), never `verified_complete`. Verification needs the evidence of `done_when`.
5. **The old auto-planner stays beside the new path** (the cutover rule). Per tenant, `human_decides` switches L4's input from `signals` to decision requests. Then `plan_commitments` skips that tenant, and a test proves it.

## 3 · Units

| Unit | File | Change |
|---|---|---|
| G8.1 | `migrations/0254_decision_requests.sql` | `decision_requests (org_id, request_id, situation_id, interpretation_id, fingerprint, question, decider_seat, decider_said, options jsonb, by_when date, goal_refs jsonb, state text check in ('open','approved','rejected','deferred','expired'), choice jsonb, decided_by, decided_at, seen_hash, created_at)`, PK `(org_id, request_id)`, unique `(org_id, situation_id, fingerprint)`; an org cascade |
| G8.2 | `contracts/decision.py` (new) | `DecisionRequest`, `HumanChoice`; refusals: a choice naming an option that does not exist, an approval by a seat that is not the decider or an org admin |
| G8.3 | `executive/decisions.py` (new) | `open_requests_from_interpretations(conn, org_id, *, at)` — idempotent on (situation, fingerprint), writes only new ones; `decide(conn, *, org_id, request_id, choice, by, at, seen_hash)` — compare-and-set on `state = 'open'`; `to_execution(conn, request, choice, *, at) -> ExecutionObject` |
| G8.4 | `contracts/execution.py` | `ExecutionObject.goal_refs: tuple[str, ...] = ()` and `decision_request_id: str \| None = None`; omitted from the mapping when empty (old rows hash the same) |
| G8.5 | `executive/sweep.py` | `plan_commitments` skips tenants with `human_decides` on; `open_requests_from_interpretations` runs instead |
| G8.6 | `api/decision_routes.py` (new) | `GET /v1/decisions?state=open`; `POST /v1/decisions/{id}` with `{choice, option_index?, defer_to?, words?, seen_hash}`; 409 when the request moved since it was seen |
| G8.7 | `executive/delegation.py` | `record_result(ok=True)` also calls `context/checkin.report(...)` → `reported_complete` |
| G8.8 | `platform/l4_activation.py` | feature `human_decides`, per tenant |

## 4 · LLM use

**None.** The model wrote the options inside the judgment (G3's pass). Routing to a decider, the choice and the
execution are code and humans (`00-ARCHITECTURE`: *"L4 Executive — model: wording only; never: a model
deciding"*).

## 5 · Tests

**`tests/executive/test_decision_requests.py`** (PG):
1. an admitted decision-lane interpretation → one open request; the same fingerprint again → none;
2. no human decision → no execution exists (the core invariant);
3. approval by a non-decider, non-admin seat → refused;
4. approve option 2 → an execution with that option's move, `goal_refs` and `decision_request_id`;
5. a request moved after it was seen → 409, no execution;
6. with `human_decides` on, `plan_commitments` plans nothing for that tenant.

**`tests/executive/test_agent_done_is_a_report.py`:** an agent's `record_result(ok=True)` → `reported_complete`, never resolved.

**Existing delegation tests stay green:** no dispatch without approval; at most once.

**Mutation proofs:**
- let `to_execution` run without a choice → test 2 fails;
- let the agent result set `verified_complete` → the report test fails.

## 6 · Flags, rollback

- **Flags:** `human_decides`, per tenant.
- **Rollback:** the flag off returns L4 to `plan_commitments`. The requests stay as history.

## 7 · Done when

- for the switched tenant, every execution traces to a human choice;
- agent work goes only through approval;
- an agent's "done" never closes a situation.

## Harsh's checklist — in order

1. **Migration** 0254 (the number check, the cascade, the erasure list).
2. **Tests first:**
   - `tests/executive/test_decision_requests.py` (cases 1–6);
   - `tests/executive/test_agent_done_is_a_report.py`.
3. **`contracts/decision.py`**; **`contracts/execution.py`** (the two new fields, omitted when empty, so old hashes hold).
4. **`executive/decisions.py`:**
   - `open_requests_from_interpretations` (idempotent);
   - `decide` (compare-and-set);
   - `to_execution`.
5. **`executive/sweep.py`:**
   - skip `plan_commitments` for tenants with `human_decides`;
   - run `open_requests_from_interpretations` instead.
6. **`api/decision_routes.py`** (409 on a moved request).
7. **`executive/delegation.record_result(ok=True)`** → `context/checkin.report(...)`.
8. **Existing delegation tests stay green.** Mutation proofs:
   - an execution without a choice;
   - an agent result that verifies.
9. **Guards, push, CI, logs.** Switch `human_decides` on per tenant, with Rohit.

## Brief for a coding agent

Paste `10-AGENT-BRIEFS.md` §1 first, then this.

**Task:** STEP-G8. Turn DecisionObjects into decision requests a human answers, create executions only from approved choices, and make an agent's "done" a report.

**Read first:**
- the preamble;
- `STEP-G8-a-human-decides-then-delegation.md`;
- `context/l2_admission.interpretation_of`;
- `executive/sweep.py` (`plan_commitments`), `executive/delegation.py`;
- `contracts/execution.py`.

**You own:**
- `migrations/0254_decision_requests.sql`;
- `contracts/decision.py`;
- `contracts/execution.py` (two fields);
- `executive/decisions.py`;
- `executive/sweep.py` (the skip and the call only);
- `executive/delegation.py` (`record_result`'s hook only);
- `api/decision_routes.py`;
- `platform/l4_activation.py` (the feature constant);
- the tests.

**Do not touch:**
- the delegation state machine;
- `reason/`.

**Acceptance:**
- §5's tests;
- the existing delegation tests;
- two mutation proofs.
