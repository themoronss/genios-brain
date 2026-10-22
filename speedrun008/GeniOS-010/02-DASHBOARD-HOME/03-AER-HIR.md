# 02.3 · AER and HIR: what they mean, what the screen needs

**Written for:** Harsh.

**Status:** the screen is built. **The brain measures neither metric yet.** Live mode shows readiness (what is in place); real values need the rollup in §4.

**Rohit's words, 22 Oct:**
- **AER is the *Automation* execution rate**, not "agentic": the work agents did correctly, with no human beyond an approval.
- **HIR is the Human intervention rate**: how often a person still had to step in or think, and how that gets better.
- The customer should see both improving week on week. That is the *"can't live without it"* proof.

---

## 1 · Definitions the screen uses

**AER** for a week = steps finished by an agent, **proven done, with no human fix afterwards** ÷ all steps finished that week. Higher is better.

| Counts as an agent step | Does not |
|---|---|
| A delegation approved once by a person, then dispatched → succeeded, with proof found (an `execution_outcomes` row labelled `succeeded`) | `completed_unproven`, `expired_untouched`, failed; a step a person did; an agent step a person then fixed (shown separately, "agent, then fixed by you") |

**HIR** for a week = resolved situations where a person **had to step in avoidably** ÷ all resolved situations that week. Lower is better.

| Counts as stepping in | Not counted |
|---|---|
| GeniOS was missing information and had to ask (a question card answered) | **A one-tap approval.** That is the design working, not an intervention |
| No agent for the task, so the person did it (`do_it_myself`) | **Decisions that are rightly the person's:** money, legal, people. These are shown *beside* HIR ("Not counted: N decisions that are rightly yours"), never in it, so GeniOS cannot look better by taking them away |
| The card was wrong or unclear (`wrong:*` verdicts, "Wrong because…") | |
| An agent's work needed fixing | |
| The person had to chase someone (reminders / escalations fired: `execution_outcomes.reminders_sent`, `escalations_fired`) | |

**The reasons breakdown** under HIR (shown when the card is opened) is the "how it gets better" part. Each reason has a lever:
- more sources → fewer questions;
- owners and approvers on file;
- corrections;
- agents for routine steps;
- sources that stay connected.

## 2 · What the screen shows before there is a measurement

`sections/genios-at-work.tsx · aerSteps / hirSteps / readiness`

| Metric | Step | Live source | Done when |
|---|---|---|---|
| AER | An agent that can act for you | `GET /v1/agents` | an `active` agent with ≥1 connector |
| AER | A step you approved | `GET /v1/delegations` | any delegation in approved / dispatched / succeeded / failed |
| AER | A step proven done | `GET /v1/delegations` | any `succeeded` |
| HIR | Sources being read | `/integrations/status` | any `connected` |
| HIR | Situations forming | `home-summary.cards[situations].value` | > 0 this week |
| HIR | A situation closed and checked | `home-summary.cards[verified].value` | > 0 this week |

- **Readiness** = steps done ÷ steps, shown as a **percentage** in the gauge ("67% ready to measure") and in the folded row. Rohit found "2/3" unclear.
- A step whose route failed shows "—" and counts as not done.
- **AER is locked** in live mode: the card is blurred under "Automation is locked … Connect an agent".

**When to remove the lock:** once §4 exists, render AER unlocked whenever `aer.total_steps > 0` for any of the 8 weeks. Keep the lock while there is nothing to show.

## 3 · Two names that already mean something else in the brain — rename before HIR ships

1. **`intervention_rate` in `api/intelligence_routes.py`** (~line 816): `acted / fired`, i.e. cards acted on ÷ cards fired. That is engagement, not HIR. Rename it, e.g. `card_action_rate`, so two different numbers do not share one name.
2. **`/v1/metrics/intervention_rate/summary`** (`api/routes.py` ~line 4673) is an empty stub. Either make it serve §4's HIR, or delete it.

`home-summary.cards[key=intervention]` (the notify/flag share of `decisions`) is a third meaning. The dashboard no longer shows it.

## 4 · What the brain should serve (proposal)

One route, so the two cards and their breakdowns come from one consistent week:

```
GET /v1/metrics/automation/weekly?weeks=8
→ {
  "targets": { "aer": 50, "hir": 15 },            // per workspace, settable later; omit → no target line
  "weeks": [                                        // oldest → newest, Monday-aligned in the org's timezone
    {
      "week_start": "2026-10-19",
      "aer": {
        "agent_clean": 24,       // agent step, succeeded, proof found, no human fix within N days
        "agent_fixed": 4,        // agent step a person then fixed
        "by_person": 36,         // steps a person did (do_it_myself, completed_by = person)
        "total": 64,
        "rate": 38               // round(100 * agent_clean / total), null when total = 0
      },
      "hir": {
        "resolved": 29,          // situations closed with an outcome that week
        "stepped_in": 7,         // avoidable interventions, ≤ resolved
        "rightly_yours": 6,      // money / legal / people decisions — shown beside, never inside
        "reasons": {             // sums to stepped_in
          "missing_information": 3, "no_agent": 2, "card_wrong": 1, "agent_fixed": 1, "chased": 0
        },
        "rate": 24               // round(100 * stepped_in / resolved), null when resolved = 0
      }
    }
  ]
}
```

**What the screen does with it:**

| Field | Shown as |
|---|---|
| last week's `rate` | the gauge value |
| the last two rates | "±N pts from last week" |
| the 8 rates | the trend chart |
| `targets` | the green tick and the target line |
| `aer.agent_clean / agent_fixed / by_person` | the "Who finished this week's N steps" bar |
| `hir.resolved / stepped_in` | the "with / without you" bar |
| `reasons` | the "Why you stepped in" bars |
| `rightly_yours` | the "Not counted" line |

**Rules the brain side must keep:**
- **`rate: null` when the denominator is 0.** Never 0%. The screen then shows "Not measured yet".
- **Every `completed_by` needs a fixed actor kind:** `agent` / `person` / `system`. `executive/execution_store.complete_action(actor=…)` today takes free text. Without fixed kinds, AER cannot tell an agent step from a person's.
- **"Proven" means an `execution_outcomes.label = succeeded`** (GeniOS-009 G7, verified outcomes). `completed_unproven` does not count.
- **AER needs delegation dispatch** (GeniOS-009 G8). Until an agent can act, AER is honestly 0 / null, and the lock stays.

**Where it plugs in:** in `GeniosAtWork`, replace `metric={sample ? SAMPLE_AER : null}` / `SAMPLE_HIR` with values from this route. The `Metric` type is `{ value, series[8], target, basis }`. Feed the breakdown children from the same response in place of `SAMPLE_AER_SPLIT`, `SAMPLE_HIR_SPLIT` and `SAMPLE_REASONS`.
