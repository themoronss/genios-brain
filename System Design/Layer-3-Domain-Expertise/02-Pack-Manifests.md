← [The Four Brains](01-The-Four-Brains.md) · [Folder map](README.md) · → [The Merge Engine and Content Addressing](03-The-Merge-Engine.md)

---

# Pack Manifests — the Universal Brain

---

## A pack manifest — the Universal brain

A pack is a **plain Python dict**. That is not laziness; it is the point. It is data that
happens to be checked into the repo, and it can equally arrive from a database row or a
YAML file — the registry stores it as `jsonb`.

#### The seven sections of a manifest

| Section | Holds | Consumed by |
|---|---|---|
| `id` / `version` / `requires` | identity + engine compatibility | registry |
| `scoring_defaults` | all of Layer 4's arithmetic constants | Layer 4 |
| `rules` | the detection corpus | Layer 4 |
| `plays` | what to *do* — artifact, success signal, window | Layers 4 → 5 → 6 |
| `templates` | how a card reads | Layer 5.2 |
| `schema` | `fields` + `signal_vocab` — the declared vocabulary | Layer 2 hints, Layer 5.2 |
| `capture` | classifier hints | Layer 1 |

#### `scoring_defaults` — the engine's constants, moved out of the engine

```python
"weights":       {"u": 45, "i": 35, "r": 20},        # S = C·(0.45U + 0.35I + 0.20R)
"c_weights":     {"conf": 50, "fresh": 30, "corr": 20},
"corroboration": {"one": 60, "two": 85, "three_plus": 100, "rank3_full": True},
"gate":          {"s_min": 55, "c_min": 60},
"budget_per_user_day": 7,
"impact":        {"i_floor": 55, "i_floor_scope": "deal_linked", "p90_default": 50000},
"r_half_life":   {"countdown_h": 24, "elapsed_h": 72},
"bands":         {"high": 70, "critical": 85},
```

Two of these constants carry arguments worth reading in full, because both were *bugs of
calibration* — the code was correct and the number silently killed the product.

**`i_floor = 55`** — what a deal-linked rule scores when the deal's value is unknown.

> 40 read the missing value as "assume a median deal". But combined with the gate it meant
> **unknown-value deals could never clear `s_min`** — i.e. the entire no-CRM tenant saw
> nothing. Unknown is not small: the cost of missing a real stalled deal dwarfs the cost of
> one extra card in a 7/day budget that is ranked anyway. 55 = *"assume it matters until we
> learn otherwise"*; a known value always overrides it.

**`bands.critical = 85`** — small-deal tenants cannot reach critical, because with impact
floored at 50 the maximum achievable score is 83.

> Kept at 85, **documented**, and tunable without a deploy. The alternative — quietly
> lowering it — would mean nobody ever learns that a whole tenant class is capped.

**The shared budget.** `general_v1` deliberately repeats sales' `budget_per_user_day: 7`
and its `i_floor: 55`, because Layer 4's budget counter is org-wide across packs. Matching
numbers keep the cap at **7/day combined, not 7+7** — and a different impact floor would
silently make one pack's cards win or lose every tie on scale alone.

#### The `execution` block — Layer 5's dials, as pack data

Added in sales v1.8.0. How a recommendation becomes a tracked commitment is *domain
knowledge*, so it merges, pins and guardrails like everything else:

```python
"planning":      {"first_action_hours": {"critical": 4, "high": 24, "standard": 72},
                  "max_actions": 12},
"communication": {"interrupt_band": "critical", "push_band": "high",
                  "interrupt_min_confidence_bp": 6_000},
"escalation":    {"ladder": [day 1 notify owner · day 3 remind owner (interrupt) ·
                             day 7 escalate manager · day 14 critical executive],
                  "band_multiplier_bp": {"critical": 5_000, "high": 7_500, "standard": 10_000}},
"reminder":      {"min_interval_hours": 20, "max_reminders": 4,
                  "untouched_hours": 24, "deadline_warning_bp": 7_500},
"monitor":       {"stall_bp": 3_000, "stall_floor_hours": 12},
```

The reasoning behind each is stated inline in the pack:

- **`first_action_hours` is separate from the play's `window_days`.** Urgency shapes when
  work *starts*; the window shapes when it must *finish*. Conflating them is how a
  fortnight-long commitment ends up demanded by this afternoon.
- **Interruption is a budget, not a feature.** `interrupt_band` is *the* one dial to reach
  for when a tenant says "too noisy".
- **`interrupt_min_confidence_bp: 6000`** — a 92-score conclusion the reasoner is 40% sure
  of should arrive calmly.
- **Escalation days count from creation, not from the deadline**, because the useful
  intervention is early. Critical work runs the same ladder at half the delay.
- **`max_reminders: 4`, then escalation owns it** — a fifth nudge gets muted.

The engine ships identical defaults, so an untuned pack behaves exactly as if the block
were absent.

#### The rule grammar

Every rule is a dict with the same shape:

```python
{"id": "cooling_deal",
 "level": "predictive",              # prescriptive | predictive
 "scope": "person",                  # person | deal | meeting
 "when": [ ...predicates... ],       # ALL must hold
 "urgency": {"type": "elapsed", "path": "thread.last_inbound", "h": 6},
 "reason_code": "cooling_deal",
 "play": "re_engage",
 "cooldown_hours": 96,
 "linked_deal": True,
 "evidence_fields": ["derived.engagement", "thread.last_inbound"]}
```

The predicate vocabulary — a small, **whitelisted** language, which is why a pack is data
rather than code that could do anything:

| Predicate form | Reads |
|---|---|
| `{"path": ..., "op": ..., "value": ...}` | a typed L2 fact |
| `{"fn": "days_since" \| "hours_since", "path": ..., ...}` | time arithmetic over a fact |
| `{"fn": "edge_count", "op": "<=", "value": 1}` | graph degree |
| `{"has_obs": ...}` / `{"no_obs": ...}` | an L2 observation kind |
| `{"neighbor_fact": ..., "op": ..., "value": ...}` | a fact on an adjacent node |
| `{"neighbor_has_obs": ...}` | an observation on an adjacent node |
| `{"value": {"baseline": "reply_cadence", "mult": 2.5, "floor": 10}}` | a **learned per-entity baseline**, not a constant |

That last form is what makes `champion_quiet` adaptive: *"quiet for 2.5× **this contact's
own** normal reply cadence, but never less than 10 days"* — rather than a single global
threshold that is wrong for everybody.

#### The two shipped packs

**`sales` v1.8.0 — 20 rules.** Their lineage is written into the version comment, which
doubles as a changelog:

| Version | Added |
|---|---|
| 1.3.0 | derived-metric + cross-entity rules (`cooling_deal`, `single_threaded_deal`, `competitor_in_live_deal`, `going_dark_after_proposal`, `deal_sentiment_negative`) |
| 1.3.1 | composite deal-health |
| **1.4.0** | **moved 4 non-deal-specific rules OUT to `general_v1`** |
| 1.5.0 | deep lifecycle corpus — `pricing_objection`, `verbal_yes_not_closed`, `contract_requested`, `security_review_pending`, `champion_left`, `budget_freeze` — plus the obs-kind normalizer |
| 1.6.0 | `discount_pressure`, `legal_in_review`, `timeline_slip`, `demo_requested` (18 rules) + enriched extraction vocab |
| 1.8.0 | the L5 `execution` block |

**`general` v1.1.0 — 5 rules.** The 1.4.0 split is the interesting event:

> `commitment_overdue`, `unanswered_email`, `champion_quiet` and `meeting_no_followup`
> used to live inside `sales_v1` — and **every card they produced got mislabelled "sales"
> regardless of who the contact actually was.** Moved here so the engine (and the browser
> extension) can tell a genuine deal-risk signal apart from plain relationship upkeep.
> Same rule engine, same scoring math, **zero engine change**.

That split is the proof the architecture works: a real product change delivered entirely by
moving data between two manifests.

#### `templates` — manager mode

Cards get their voice from the pack, not from the renderer:

```python
"render_hint": ("Headline: a direct order to reply to this person now — imperative "
                "voice ('Reply to X now'), not a status line. ...")
"fallback":    {"headline": "Reply to {entity} now",
                "situation": "{days}d since they wrote — still waiting on you"}
```

Every template ships a **deterministic fallback** alongside the LLM render hint, so a card
still reads correctly when the model is unavailable. `"_version": "cards.v2"` lets the
renderer evolve without breaking older packs.

---
