# Prompt for the external agent

> **Created:** 2026-09-10 · **Status:** Active — hand this to the agent, paste its output back
>
> **Purpose:** a self-contained brief. The agent has no access to the live database and did not
> take the measurements, so every number it needs is written out here.

Copy everything below the line into the agent. Give it the repository.

---

# BRIEF

You are working in `genios-brain`, a Python intelligence engine (FastAPI + SQLAlchemy +
Postgres). It ingests a tenant's email and calendar, builds a graph, correlates it into
"situations", reasons over them with 17 deterministic units, and emits "cards" — short pieces of
advice with a receipt behind every claim.

**The problem: the compiled/expertise lane has produced ZERO cards in the product's entire
life.** 18 cards have ever been built, all from an older legacy lane, of exactly two kinds.

I have already diagnosed why, against the live production database. **You do not need to
re-diagnose. Every measurement you need is in this brief.** Your job is to build the fixes.

## RULES — these are the repository's own, and they are not negotiable

1. **Never weaken a test to make it pass.** Fix the code, or redraw the unit.
2. **A skip is not a pass.** An incomplete test run is not green.
3. **Do not lower any threshold to make output appear.** Specifically: `DEFAULT_CONFIDENCE_FLOOR_BP = 4500`
   in `genios_engine/reason/decision_maker.py:108` **stays at 4500**. Every change below raises
   the INPUT to a score, never moves the bar. If you find yourself editing a constant so that
   more things pass, stop and say so instead.
4. **Every test must be hermetic** — no network, no real Postgres, no clock, no LLM. Use SQLite
   for SQL paths. Note: `substr(x, 8)` not `substring(x from 8)`; `cast(int as text)` not
   `cast(text as int)`.
5. **Comments explain WHY, with the measurement.** This codebase's comments carry the number
   that motivated the code. Match that. A comment that only restates the line is noise.
6. **Test names are sentences** describing the defect, e.g.
   `test_a_derived_fact_carries_the_provenance_of_the_events_it_came_from`.
7. **Fail open, never closed, on anything that is a refinement.** If a new read cannot run, the
   caller must behave exactly as it did before — never worse.

## HOW TO RUN THE TESTS

```
export PATH="<toolchain>/bin:$PATH"
uv run --no-sync pytest <path> -q -p no:randomly
```

Baseline: **9899 passed, 24 failed.** Those 24 are pre-existing and unrelated — they live in
`tests/capture/esqe/test_qualification_routes.py` (12), `tests/capture/connectors/test_new_route_wiring.py` (6),
`tests/capture/esqe/test_rejection_ledger.py` (4), `tests/capture/test_g9_gate_probes.py` (1),
`tests/contracts/test_h0_gate.py` (1). **They may still fail. Nothing else may.**

---

# TASK 1 — Derived things must carry evidence  ← START HERE, HIGHEST VALUE

## The defect

Evidence in this system is attached to **whoever spoke**. A person sends a message; the pipeline
writes a `graph_observation` against that person's node with `graph_source_refs` pointing at the
event.

But the product reasons about things it **derived**, which nobody said — a campaign, a firm
going quiet, silence itself, a thread, a company, a commitment. **So everything the product
invents is unevidenced by construction, and the confidence gate refuses it.**

### Measured on production

`graph_observations`: 1001 rows, **all on 30 person nodes**. Zero on:

| Node type | Count | Observations |
|---|---|---|
| thread | 66 | 0 |
| company | 43 | 0 |
| outreach | 41 | 0 |
| commitment | 15 | 0 |
| condition | 17 | 0 |
| campaign | 2 | 0 |
| organization | 2 | 0 |

`graph_facts` exist on all of them, but with no provenance:

| Node type | Facts | Rows in `graph_source_refs` |
|---|---|---|
| company | 509 | **0** |
| outreach | 175 | **0** |
| condition | 134 | **0** |
| backlog_item | 140 | **0** |
| campaign | 12 | **0** |
| organization | 10 | **0** |
| person | 652 | 162 |
| thread | 459 | 137 |
| meeting | 29 | 29 |

### The exact line

`genios_engine/context/outreach_situations.py:915`

```python
stats = counts.get(finding.concerns_node)      # None for every synthetic anchor
last_at = getattr(stats, "last_at", None)      # None
fresh, fresh_known = freshness_score(last_seen_at=last_at, now=now)   # (0, False)
evidence=evidence_score(
    event_count=int(getattr(stats, "events", 0) or 0),     # 0
    source_count=int(getattr(stats, "sources", 0) or 0)),  # 0
```

`counts` comes from `_EVENT_COUNTS` at line 232 of the same file, which groups
`graph_observations` by `subject_node_id`. **One `None` zeroes both the evidence axis and the
freshness axis.**

### The scoring formula (do not change it)

`genios_engine/context/situations.py:117`

```python
def evidence_score(*, event_count, source_count):
    volume = min(40, max(0, int(event_count)) * 8)
    corroboration = min(60, max(0, int(source_count)) * 25)
    return max(0, min(100, volume + corroboration))
```

Layer 4 takes Layer 2's six axes and applies the **minimum** of them as a ceiling on confidence
(`genios_engine/reason/reasoners/confidence.py`, class `SituationTrustPlugin`). A 0 on any axis
means confidence 0 means the reasoner defers means no signal means no card.

### The trace that proves it

The live "13 investors" campaign, followed end to end:

- Situation exists ✅ `sit_65ae4399c61244bf9f9d3af3`
- Its node holds **every fact the card needs**:
  `campaign.contacted 7`, `campaign.awaiting 7`, `campaign.longest_wait_days 30`,
  `campaign.sent_on "2026-08-11"`, `campaign.people "harshita@peakxv.com, …"`,
  `campaign.quote "I am sharing a few details here as well for your…"`
- **Admitted** by the publisher ✅ (twice — it is not blocked there)
- Compiled ✅ · Reasoned ✅ (`expertise.campaign_awaiting_reply` ran)
- **confidence_bp = 0** ❌ → `defer` → no signal → no card

## What to build

### 1A · Derived facts write their provenance
Every writer of a derived fact must also insert `graph_source_refs` rows — one per contributing
event, carrying `event_id`, `source`, and the same `independence_group` discipline the
observation path already uses.

**Files:** `genios_engine/context/support_situations.py` (`_write_fact`),
`genios_engine/context/outreach_situations.py`, `genios_engine/context/document_register.py`.

**Test:** write a derived fact from two events; assert two `graph_source_refs` rows exist with
`fact_version_id` set and the right `source` on each.

### 1B · Evidence is counted where the situation actually lives
`_EVENT_COUNTS` must reach the evidence of the nodes a situation is ABOUT, not only its anchor.
Two parts, both required:

- **One hop, BOTH directions.** Walk the anchor through `graph_edges` to `person` and `company`
  neighbours and count over those. **Direction is load-bearing** — the live edge is
  `person → thread`, so a thread-anchored situation walking only outward finds nothing. The
  edges that exist on production are: `person corresponded_with person` 70,
  `person corresponded_with thread` 64, `person works_at company` 47, `outreach concerns thread`
  21, `outreach concerns person` 18, `person owns commitment` 10, `campaign concerns person` 2,
  `organization concerns person` 2.
- **Group situations count their members.** The graph links a campaign to only 2 representative
  people; the real membership lives in `context_correlation_members` (live groups of 40, 25, 18,
  14, 10, 7). Its columns are `org_id, correlation_id, event_id, joined_via, joined_at` — note
  it keys on **event_id**, not a node id.

**Test:** a synthetic anchor with two neighbour people carrying three observations each from one
source must score `min(40, 6×8) + min(60, 1×25)` = **65**, not 0. And a situation whose
neighbours genuinely have nothing must still score 0 — the fix must not become "everything has
evidence".

### 1C · The structured (calendar) lane writes observations
50 calendar events currently produce 29 facts, 5 meeting nodes, 2 person nodes and **0
observations**. The structured lane writes facts only; the evidence axis counts observations.

**Test:** one calendar event through the structured lane writes an observation for each node it
established.

### 1D · Observations land on everyone an event establishes
Currently written only onto the sender — `genios_engine/context/pipeline.py`, four
`write_observation` call sites, all `subject_node_id=sender_node` or `content_subject`.

Consequence: **30 of 60 person nodes have zero observations**, and they are exactly the people
who never replied — the subject of every "they have gone quiet" card. 398 of the 1001
observations sit on the tenant owner's own node.

An outbound message is evidence about its **recipient**.

**Test:** an outbound message writes an observation against each recipient node, not only the
sender.

### 1E · One line
`genios_engine/reason/reasoners/confidence.py:81`
`_UNREAD_SITUATION_AXES = ("coverage",)` → `("coverage", "analytic")`

**Why:** the `analytic` axis maps cohort size to a score with floor 10 and full population 200
(`genios_engine/context/situations.py`, `_analytic_sub_score`). Every legal cohort in **[5, 77]
peers maps to [1200, 4400] bp against a 4500 floor**; 78 peers are required to clear it. For any
small tenant it is a deterministic veto no operator action can lift — a constant `False` wearing
a threshold's clothes. The axis keeps publishing as a receipt; it stops being a ceiling.
**Do not rescale the ramp.** Update the two comment blocks that currently argue the axis should
bind (around `confidence.py:70-81` and `:326-334`) with the measurement above.

### 1F · One line
`genios_engine/capture/connectors/calendar.py:115` hardcodes `actor_type="internal_user"`. All
50 live calendar events therefore label their organiser as the tenant's own staff — including
`theresa.hoffmann@antler.co`, an external investor. Derive it from the "us" set
(`genios_engine/context/runner.py`, `_internal_emails`), which is the source the rest of Layer 2
uses.

## The arithmetic you are aiming at

After 1A + 1B the campaign situation should score:

| Axis | Value | Working |
|---|---|---|
| evidence | **65** | `min(40, 7×8)` + `min(60, 1×25)` |
| freshness | **50** | `sent_on` 11 Aug = 30 days → the `≤30` rung of `freshness_score` |
| consistency | 100 | unchanged |
| identity | 100 | synthetic anchor, no merge proposals |
| analytic | skipped | unassessed sentinel `-1` |

`min(65, 50, 100, 100)` = **50 → 5000 bp** against a **4500** floor. It clears.

**If your change produces a number materially different from 65 and 50, say so and explain why
rather than adjusting anything to hit them.**

---

# TASK 2 — Give the graph business nouns

## The defect

The graph knows a person has not replied in 30 days. It does not know that person is an
investor.

Every fact in the graph by kind: `derived.*` 991 facts / 30 fields · `thread.*` 500 / 7 ·
everything else 895 / 86. But "everything else" is mostly behaviour wearing a business name —
`response.overdue_hours`, `outreach.days_waiting`, `backlog.age_days`.

The fields that carry real business meaning:

| Field | Facts in the entire graph |
|---|---|
| `party.role` | **1** |
| `relationship.nature` | **1** |
| `deal.stage` | **0** |
| `deal.value` | **0** |
| `person.title` | **0** |
| `company.industry` | **0** |
| `thread.objective` | **0** |
| `campaign.objective` | **0** |
| `organization.relationship` | **0** |

**The corpus under `Domain Expertise/` already declares every one of these. None has a writer.**
Structurally: 60 people, 9 have a commitment, **6 have a role**.

## What to build

### 2A · Extend the extraction contract
The LLM already reads every message once (1,413 `extract` calls on this tenant) and is asked
only for timing and process fields. Add the nine fields above. Signal sources already present in
the payload: the signature block, the sender domain, self-introductions in the body, the
calendar organiser, the thread subject.

**Files:** `genios_engine/capture/esqe/` (the extraction contract and its validator).

### 2B · A judgement ranks below an observation
`Domain Expertise/Admin Expertise/.../situations/campaign-awaiting-reply.yaml` states the rule:
*"A send is evidence of what was written, not of what it was meant to achieve."* An objective is
a JUDGEMENT. Write it with a verbatim receipt and an `authority_rank` **below** an observed
fact, so a stated purpose always beats an inferred one.

### 2C · `unknown` is never written
An unplaced thread keeps the field in `missing` rather than satisfying it with a meaningless
label. This rule already exists for `thread.objective` and must hold for all nine.

### 2D · Drain the parked attachments
776 attachment events, **767 parked**. OCR now ships in the deploy image. Draining them is what
turns "you sent the deck" from a guess into a fact.

**Test:** a fixture mailbox with one signature block naming a title and one thread whose subject
states a purpose writes `party.role` and `thread.objective`, each with a non-empty verbatim
span. A thread with neither writes neither and reports both as missing — **not** as `unknown`.

---

# TASK 3 — Let the good sentence through the renderer

## The defect

`genios_engine/deliver/render.py:16` — `HEADLINE_CAP = 60`, situation cap **140**.

Live guard rejections on real cards:

| Reject | Meaning |
|---|---|
| `V-01:len=61`, `len=64` | headline one to four characters over |
| `V-01-trimmed:201->111` | **the situation cut from 201 characters to 111** |
| `V-02:name:Insert` | invention guard caught a template placeholder leaking into copy |
| `V-02:name:SwerashiGeniOS` | invention guard caught a concatenation artefact |

The corpus's own authored fallback for the campaign card is ≈**190 characters** with real
values:

```
{contacted} people received the same message on {sent_on} and {awaiting} have not answered.
The longest has been waiting {longest_wait_days} days. They were sent: "{quote}"
```

**The card copy we authored is longer than the renderer permits**, and the quote — the most
valuable thing on the card — sits at the end, so the trim removes it first.

## What to build

- **3A** · The cap becomes a property of the card, not a global constant. A one-line nudge and a
  group briefing are different objects. Let the situation declare its own cap in its YAML, with
  **140 as the default** so nothing already shipping changes.
- **3B** · A verbatim quote is not prose and is not counted against the cap.
- **3C** · A rejected LLM render re-templates against the corpus's authored fallback instead of
  dropping to raw slot-filling. 3 of 18 live cards took that path and read like *"2d since they
  wrote — still waiting on you"*.
- **3D** · `V-02:name:Insert` is a template placeholder leaking into copy — a real bug upstream,
  not a hallucination. Find and fix the source.

---

# WHAT NOT TO TOUCH

| Do not | Why |
|---|---|
| Lower `DEFAULT_CONFIDENCE_FLOOR_BP` from 4500 | Admitting 2300 admits ~120 of 185 situations whose whole evidence is one unconfirmed email |
| Change `freshness_score` | 68 situations really are 90+ days old; low confidence is correct |
| Rescale the `analytic` ramp | No measurement licenses a new constant. Removing it from the ceiling requires none |
| Change `evidence_score`'s formula | The formula is right; its inputs are wrong |
| Put an LLM inside a Layer 4 reasoning unit | Reasoning must stay deterministic and replayable. The LLM belongs at extraction (Task 2) |
| Widen the `cards_one_per_signal` unique index | Three writers upsert on it and four reads join it; widening double-counts a situation in the brief and the budget |
| Enable `FEATURE_BUNDLE` | It narrates published decisions and there are none until Task 1 lands. I will switch it on |

---

# DELIVERABLE

For each task: the code, its tests, and a short note saying **what number moved**. Report the
full suite result. If you could not do something, say which and why — do not work around it and
do not soften a check to get green.

Order: **Task 1 first** (1E and 1F are one-liners, do them first; then 1A + 1B, which is where
the value is), then Task 3, then Task 2.
