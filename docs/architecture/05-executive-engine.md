> **Created:** 2026-08-07 · **Status:** Reference — frozen target vision
> **Source:** `GeniOS Theory II.pdf` — "Layer 5: Executive Engine"

# Layer 5 — Executive Engine

**One responsibility:** operationalize a decision. Reasoning answers *"what should
happen?"*; the Executive Engine answers **"how do we make it happen?"** — and it
**never changes the decision.** It does **not** think or decide; that is Layer 4's job
(there is only one place thinking happens).

**Current code:** `genios_engine/executive/` — interpret, planning, communication,
assignment, authority, execution, execution_guard, execution_store, validate, brief,
verbs, modes, summary, memory, explain, reminder, escalation, monitor, lifecycle,
collect, sweep.

## Scope: Decision Intelligence + operationalization — NOT automation

GeniOS produces **execution-ready intelligence**; it never executes workflows itself.
The author's boundary for the Executive Engine's *output*:

- ✅ What is happening · why it matters · what to do · how urgent · on what evidence ·
  what happens if nothing is done.
- ❌ *Who* does it / *when* / *which tool* / *which agent* → these are **Delivery
  (Layer 5.2)** concerns, not decision intelligence.

## Units (same one-engine-many-units pattern)

```text
Executive Engine
├── Decision Interpreter Unit
├── Execution Planning Unit
├── Communication Planning Unit
├── Execution Validation Unit          ← added: suppress stale/superseded actions
├── Execution Object Builder
├── Reminder Unit                      ← executive (business-relevance), not calendar
├── Monitoring Unit
├── Escalation Unit
├── Execution Tracking Unit            ← execution state machine
└── Feedback Collection Unit           ← feeds Layer 6
```

Every unit follows the standard framework: `Input → Validator → Retriever → Planner →
Builder → Executor → Output`.

### 1. Decision Interpreter Unit
Parses the Decision Object (never modifies it) into an execution context: goal,
priority, deadline, dependencies, expected result, execution type.

### 2. Execution Planning Unit ⭐
"How exactly should this decision be executed?" — turns one decision into an ordered,
executable plan (collect metrics → update deck → generate email → review → send →
track reply). Components: Task/Dependency/Sequence/Resource/Owner/Deadline planners.

### 3. Communication Planning Unit
"How should this intelligence be communicated?" — chooses message strategy/tone per
audience (founder → short notification; team → Slack; customer → professional email;
API → JSON). Still **no LLM** — it selects the strategy, not the words.

### 4. Execution Validation Unit ⭐ (the "true executive partner" guard)
**Before** anything is delivered, verify the plan is still valid: is the situation
still active? already handled by a human? deadline passed? context changed enough to
invalidate? superseded by a higher-priority decision? Prevents stale recommendations
and needless notifications (e.g. GeniOS was about to remind you to send an investor
update at 9:15 — but you already sent it at 9:10 → suppress).

### 5. Execution Object Builder ⭐ (the layer's output)
Builds one standardized **Execution Object** every downstream system consumes:

```json
{ "goal": "...", "priority": "High", "actions": ["...","..."],
  "deadline": "Today", "monitor": true, "remind": true,
  "escalate_after": "3 days", "delivery": ["dashboard","extension"] }
```

### 6. Reminder Unit ⭐⭐ (a key differentiator)
An **executive** reminder, not a calendar reminder — driven by **business relevance,
not time**: *"You promised 314 Capital an update; it's been 4 months; this is hurting
fundraising momentum; recommend sending today."* Inputs: decision status, situation,
execution status, priority, deadline, context changes.

### 7–10. Monitoring · Escalation · Execution Tracking · Feedback Collection
Monitoring: did execution happen? Escalation: strategy over time (notify → remind →
escalate → critical). Execution Tracking: the state machine (Created → Pending →
Running → Waiting → Blocked → Completed → Archived). Feedback Collection: accepted /
ignored / modified / executed / failed — feeds Layer 6.

## LLM usage in Layer 5

Only where language quality matters — writing emails, rewriting Slack messages,
summarizing a decision for an executive, adapting tone. **Never** for deciding whether
to remind, priorities, escalation, or execution steps — those stay deterministic.

## Storage

Execution state, temporary reminders, execution history, task status, notification
queue — Supabase (operational store).

## Contract

**Input:** Decision Object (from Layer 4). **Output:** Execution Object (to Layer 5.2).

## Frozen decisions

- Executive Engine operationalizes; it never re-decides. Only Reasoning decides.
- Action-planning/delegation of *who/when/where* is Delivery's job, not this layer's.
- Reminders are business-relevance-driven, not time-driven.
- The Execution Validation Unit runs before delivery to kill stale/superseded actions.
