> **Created:** 2026-08-07 · **Status:** Reference — frozen target vision
> **Source:** `GeniOS Theory II.pdf` — "Layer 6: Learning & Evolution Engine"

# Layer 6 — Learning & Evolution Engine

**One responsibility:** make GeniOS **more valuable every day** — learn, adapt,
optimize, personalize, forget, update, validate. It **never executes** and **never
reasons.** Without it GeniOS is intelligent; with it GeniOS becomes an *evolving executive.*

**Current code:** `genios_engine/feedback/` — calibrate. *(Currently thin; the target
below is the full set of units.)*

## Learn from outcomes, not clicks

Learning is based on **outcomes** (did the recommendation actually work?), not on
whether a card was clicked.

## Units

```text
Learning & Evolution Engine
├── Feedback Unit                     what happened? (accepted/ignored/rejected/modified/executed/failed)
├── Outcome Analysis Unit             did the decision work? (success vs failure, impact, ROI)
├── Pattern Learning Unit ⭐          recurring behavior → Pattern Objects (not memories)
├── Preference Learning Unit ⭐       what the user prefers (choice, distinct from behavior)
├── Temporary Memory Unit             short-lived, TTL/expiry (executive-assistant reminders)
├── Long-term Learning Unit           promote temporary → permanent after enough observations
├── Recommendation Learning Unit      which recommendations worked → confidence → Adaptive Brain
├── Performance Optimization Unit     system self-improvement (false pos/neg, accuracy, latency)
├── Knowledge Evolution Unit          SUGGEST Expert-Brain version changes (never auto-edit)
├── Learning Validator Unit           is this learning trustworthy yet? (enough evidence/confidence)
└── Evolution Publisher Unit          publish validated updates downstream
```

Every unit follows the standard framework: `Input → Validator → Retriever → Analyzer →
Calculator → Builder → Publisher`.

### Pattern vs. Preference (distinct)
**Pattern** = observed behavior ("investor replies faster Tuesday mornings", "customer
closes after 2nd demo"). **Preference** = a choice ("short emails", "no weekend
notifications"). Both carry confidence, evidence, frequency, last-seen.

### Temporary Memory vs. Long-term
Temporary = runtime table with TTL ("remind me tomorrow 2pm to call Harsh" → gone
after). Long-term = a temporary pattern observed enough times (e.g. 26 weeks) is
**promoted** into the Behavioral Brain.

### Knowledge Evolution + Learning Validator (governance)
The Learning Engine **does not edit the Expert Brain.** It *suggests* version changes;
a human reviews. Nothing is published until the Learning Validator confirms enough
evidence/confidence (one action is not enough; ~20 examples → 95% confidence → publish).

## What it updates (writes DOWN as data, never imports upward)

```text
Execution Result → Feedback → … → Evolution Publisher
   → Behavior Brain · Adaptive Brain · Organization Brain (where applicable) · Context Graph · Runtime Preferences
```

Expert (Universal) Brain in **Git never changes automatically** — only version
suggestions after human review. Everything else (dynamic) lives in Supabase.

## Reminders belong to Layer 5, not here

The Executive Engine executes **today's** commitments (reminders are actions). The
Learning Engine only decides whether something should **become** recurring / earlier /
later based on observed patterns — it improves **tomorrow's** behavior.

## Governance (mandatory)

Approval · Rollback · Versioning · Validation · Human Review. Never silently change a
deterministic rule; every rule change must be explainable.

## LLM usage in Layer 6

Only: summarize feedback, extract learning from free text, infer preferences when
deterministic signals are weak. **Never** to decide patterns, update confidence,
promote long-term memory, or trigger reminders.

## Deployment

Asynchronous background worker — **never synchronous.** Learning must never add latency
to the critical path.

## Frozen decisions

- Learn from outcomes; validate before promotion; governed and explainable.
- Never edits authored knowledge — suggests versioned changes for human review.
- Writes learned state downward as data; never imports upward (matches `feedback/` rule).
- Reminders are Executive (actions); Learning only decides recurrence.
