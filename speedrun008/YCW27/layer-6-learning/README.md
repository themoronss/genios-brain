# L6 · Learning — `feedback/`

**12 files · 2,737 lines.** Milestone **M14**, 3 units.

> What did reality teach — and which layer, exactly, should change?

---

## How the loop closes without breaking the import rule

This is the pattern for **every** cross-layer need in the system. A lower layer never imports a
higher one, so Learning cannot be imported by Reasoning — and it isn't: nothing in `context/`,
`reason/` or `packs/` imports `feedback`.

```
feedback/calibrate.py   writes  →  rule_mutes
                                   tenant_packs.lvl3_config
                                       ↓  read by
                         reason/runner.py  ·  packs/registry.py
```

**Live today.** A table written above and read below satisfies the need without an upward import.
The two roads are **injection** (the composition root passes values down) or **data**. Never a
third.

---

## What it is conservative about, and why

> *Learning is deliberately conservative: passive impressions are observability, not labels. Only
> canonical human judgments enter confidence and eligibility calculations.*

| Counts as positive | Counts as negative | Counts as **neither** |
|---|---|---|
| `run_play` · `do_it_myself` | `wrong:not_relevant` · `wrong:wrong_facts` | `bad_timing` · `snooze` · `requeue` |

The third column says **when**, not **whether**. Windows: 28 days, minimum 8 judgments; mute below
0.25 precision with at least 12.

**Why-not receipts.** `explain.why_not` answers *"Why did GeniOS not tell me about X?"* from
`signal_suppression_log`, with six codes: `below_gate` · `budget` · `cooldown` · `muted` ·
`shadow` · `situation`. **Silence without receipts is indistinguishable from a bug.**

---

## The missing half

A negative judgment today lowers the precision of the rule that produced the card. But the card may
have been wrong because L1 read the wrong sender, or the frame was wrong, or the timing was bad.
**Punishing the rule for an extraction bug teaches the system the wrong lesson.**

## What changes — M14

### `M14.C1` Attribution by layer

| Unit | What |
|---|---|
| `U01` | the attribution vocabulary — eleven reasons, each mapped to exactly one layer, **closed in both directions** |
| `U02` | "Wrong because…" on the card, returning one of the eleven |
| `U03` | the router — reason → layer → the thing that changes |

| The user says | Attribution | What changes |
|---|---|---|
| "That's not what the email said" | `wrong_evidence` | L1 extraction |
| "That's a different person" | `wrong_entity_resolution` | L1 identity, L3 merge |
| "These are unrelated" | `wrong_correlation` | L1 bundling, L2 relationship units |
| "That's not the real problem" | `wrong_situation_frame` | L2 framing |
| "You didn't know about X" | `missing_context` | L1 coverage, L3 query scope |
| "That's not how this works" | `wrong_expertise` | Plane D proposal → **human review** |
| "Your logic doesn't follow" | `wrong_reasoning` | Plane R unit + its evaluations |
| "Not my job" | `wrong_owner` | L4 assignment, organisation brain |
| **"Not now"** | `bad_timing` | **L5 timing — never the rule's precision** |
| "Confusing" | `bad_wording` | L5 composer |
| "Already handled" | `outcome_changed` | L1 coverage + L3 lifecycle: we were late or blind |

---

## Two rules that must not be traded away

**Mute in stages, never at once:** `live → downrank → shadow → review → muted`. Twelve judgments is
a thin sample for a small tenant.

⛔ **Safety rules are not learnable.** A user repeatedly dismissing a real risk must not teach the
system to stop seeing it.

## Three kinds of learning, three owners

| Kind | Goes to | Automatic? |
|---|---|---|
| **Case** — what happened here | context history | yes |
| **Organisational** — how long approvals really take | behaviour + adaptive brains | yes, and reversible |
| **Professional** — a reusable pattern or exception | a pull request to Plane D | ⛔ **merged only by a human** |

## Read these first

`feedback/calibrate.py` · `feedback/orchestrator.py` — where all four brain suppliers run ·
`explain.why_not`
