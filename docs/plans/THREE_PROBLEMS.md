# The three problems — what happened, what should happen, how to fix it

> **Created:** 2026-09-10 · **Status:** Active — spec written, build not started
>
> **Purpose:** the working spec for the three defects that keep the product's intelligence
> shallow. Written to be handed to another engineer or agent: every claim carries the
> measurement behind it, every fix carries an acceptance test that does not depend on the live
> database.

All numbers measured read-only against the live pilot tenant (`org_e97e…`) on 2026-09-10.

---

## THE HEADLINE

The product has produced **18 cards in its life**, of exactly two kinds. Cards produced by the
compiled/expertise lane — the one carrying the authored domain corpora, 152 capabilities, three
domains: **zero, ever.**

Three things cause that, and they are independent. Fixing one does not fix another.

| # | Problem | Symptom |
|---|---|---|
| **1** | Derived things carry no evidence | **No compiled cards at all** |
| **2** | The graph has no business nouns | Cards would be correct but shallow |
| **3** | Layer 4's writing half is switched off | Cards would have no recommendation |
| 4 | The renderer caps a situation at 140 chars | Whatever ships, ships cut in half |

---

# PROBLEM 1 — Derived things carry no evidence

## What happened

In this system, evidence is attached to **whoever spoke**. A person sends a message; the
pipeline writes a `graph_observation` against that person's node, with `graph_source_refs`
pointing back to the event.

But the product's entire job is to reason about things **it derived**, which nobody said:

- a **campaign** — nobody sent "a campaign"
- a **firm going quiet** — nobody sent "Peak XV is quiet"
- **silence itself** — the whole point is that nothing was said
- a **thread**, a **company**, a **commitment**, a **condition** — all inferred

So everything the product invents is unevidenced by construction, and the confidence gate
refuses anything unevidenced.

### The measurement

`graph_observations`: **1001 rows, on 30 person nodes.** Zero on any other node type.

| Node type | Count | Observations |
|---|---|---|
| thread | 66 | **0** |
| company | 43 | **0** |
| outreach | 41 | **0** |
| commitment | 15 | **0** |
| condition | 17 | **0** |
| campaign | 2 | **0** |
| organization | 2 | **0** |

`graph_facts` **do** exist on all of them — but with no provenance:

| Node type | Facts | With a `graph_source_refs` row |
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

`context/support_situations._write_fact` inserts into `graph_facts` alone.

### The exact line where it kills a card

`genios_engine/context/outreach_situations.py:915`

```python
stats = counts.get(finding.concerns_node)      # → None for every synthetic anchor
...
last_at = getattr(stats, "last_at", None)      # → None
fresh, fresh_known = freshness_score(last_seen_at=last_at, now=now)   # → (0, False)
...
evidence=evidence_score(
    event_count=int(getattr(stats, "events", 0) or 0),     # → 0
    source_count=int(getattr(stats, "sources", 0) or 0)),  # → 0
freshness=fresh if fresh_known else None,
```

`counts` comes from `_EVENT_COUNTS` (same file, line 232) which groups `graph_observations` by
`subject_node_id`. One `None` zeroes both the evidence axis and the freshness axis.

### The trace that proves it

The 13-investor campaign, followed end to end with real ids:

| Step | Result |
|---|---|
| Situation exists | ✅ `sit_65ae4399c61244bf9f9d3af3` |
| Facts on its node | ✅ **all of them** (below) |
| Admitted by the publisher | ✅ **admit** — twice, not held |
| Compiled | ✅ |
| Reasoned | ✅ `expertise.campaign_awaiting_reply` ran |
| **Confidence** | ❌ **0** |
| Decision | ❌ `defer` |
| Card | ❌ none |

What that node holds **right now**:

```
campaign.contacted          7
campaign.awaiting           7
campaign.longest_wait_days  30
campaign.sent_on            "2026-08-11"
campaign.people             "harshita@peakxv.com, adityad@iima.ac.in, Manik Pa…"
campaign.quote              "I am sharing a few details here as well for your…"
```

**Every clause of the card is already a stored fact.** The reasoner refuses to speak about a
situation it can describe completely, because the axes that ask "how much do we know" read zero
on a node that knows everything.

## What should happen

A derived thing inherits the evidence of the things it was derived FROM. A campaign built out of
seven emails has seven emails' worth of evidence, from one source, and its freshness is the date
of the send.

## How to fix it

Four changes, in this order.

### 1A · Derived facts write their provenance
`_write_fact` (and the equivalent writers in `outreach_situations`, `document_register`) must
insert `graph_source_refs` rows alongside the fact — one per contributing event, carrying
`event_id`, `source`, and the same `independence_group` discipline the observation path uses.

**Acceptance:** a hermetic test that writes a derived fact from two events and asserts two
`graph_source_refs` rows exist with `fact_version_id` set.

### 1B · Evidence is counted where the situation actually lives
`_EVENT_COUNTS` must reach the evidence of the nodes a situation is ABOUT, not only its anchor.
Two parts:

- **One hop, both directions.** Walk the anchor to `person` and `company` neighbours through
  `graph_edges` and count over those. **Direction is load-bearing** — the live edge is
  `person → thread`, so a thread-anchored situation walking only outward finds nothing.
- **Group situations count their members.** The graph links a campaign to 2 representative
  people; the real membership lives in `context_correlation_members` (groups of 40, 25, 18, 14).

**Acceptance:** a hermetic test with a synthetic anchor, two neighbour people carrying three
observations each from one source, asserting `evidence_score` returns 40 + 25 = 65 rather than 0.

### 1C · The structured (calendar) lane writes observations
50 calendar events currently produce 29 facts, 5 meeting nodes, 2 person nodes and **0
observations**. The structured lane writes facts only; the evidence axis counts observations.

**Acceptance:** a test that runs one calendar event through the structured lane and asserts an
observation exists for each node it established.

### 1D · Observations land on everyone an event establishes
Currently written only onto the sender — `context/pipeline.py`, four `write_observation` sites,
all `subject_node_id=sender_node` or `content_subject`.

Consequence: **30 of 60 people have zero observations**, and they are exactly the people who
never replied — the subject of every "they have gone quiet" card. 398 of the 1001 sit on the
founder's own node.

An outbound message is evidence about its **recipient**.

**Acceptance:** a test asserting an outbound message writes an observation against each
recipient node, not only the sender.

### The arithmetic that proves 1A + 1B is enough for the first card

After 1A + 1B, the campaign situation scores:

| Axis | Value | Working |
|---|---|---|
| evidence | **65** | `min(40, 7 facts × 8)` + `min(60, 1 source × 25)` |
| freshness | **50** | `sent_on` 11 Aug = 30 days → the `≤30` rung |
| consistency | 100 | unchanged |
| identity | 100 | synthetic anchor, no merge proposals |
| analytic | skipped | unassessed sentinel |

Ceiling = `min(65, 50, 100, 100)` = **50 → 5000 bp**. Floor is **4500**.

**5000 > 4500. The card ships.** Same formula the code runs, on values already in the database.

## What must NOT be done

- **Do not lower `DEFAULT_CONFIDENCE_FLOOR_BP` (4500).** Admitting 2300 would admit ~120 of 185
  situations whose whole evidence is one unconfirmed email. Every change above raises the INPUT.
- **Do not touch `freshness_score`.** 68 situations really are 90+ days old.
- **Do not widen `cards_one_per_signal`.** Three writers upsert on it and four reads join it.

## Two one-line fixes that belong with Problem 1

**1E · `reason/reasoners/confidence.py:81`**
`_UNREAD_SITUATION_AXES = ("coverage",)` → `("coverage", "analytic")`

The `analytic` axis maps cohort size to a score with floor 10 and full population 200. Every
legal cohort in **[5, 77] peers maps to [1200, 4400] bp against a 4500 floor** — 78 peers are
required to clear it. For any small tenant it is a deterministic veto no operator action can
lift: a constant `False` wearing a threshold's clothes. The axis keeps publishing as a receipt;
it stops being a ceiling. **Do not rescale the ramp** — no measurement licenses a new constant.

**1F · `capture/connectors/calendar.py:115`**
`actor_type="internal_user"` is hardcoded. All 50 calendar events label their organiser as the
tenant's own staff — including `theresa.hoffmann@antler.co`, an external investor. Derive it
from the "us" set (`context/runner._internal_emails`), the same source the rest of L2 uses.

---

# PROBLEM 2 — The graph has no business nouns

## What happened

The graph knows Theresa has not replied in 30 days. It does not know Theresa is an investor.

Every fact in the graph, by kind:

| Kind | Facts | Distinct fields |
|---|---|---|
| `derived.*` — trends, anomalies, engagement counts | 991 | 30 |
| `thread.*` — whose turn, last inbound | 500 | 7 |
| Everything else | 895 | 86 |

But "everything else" is mostly behaviour wearing a business name —
`response.overdue_hours`, `outreach.days_waiting`, `backlog.age_days`, `condition.age_days`.

The fields that carry actual business meaning:

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

**The corpus already declares every one of these. None has a writer.**

Structural consequence: 60 people, **9 have a commitment**, **6 have a role**.

## What should happen

The LLM already reads every message once — 1,413 `extract` calls on this tenant. It is asked for
timing and process fields. It should also be asked:

- **who is this person to this business** → `party.role`, `person.title`, `company.industry`
- **what is this exchange for** → `thread.objective`, `relationship.nature`,
  `organization.relationship`
- **what state is any deal in** → `deal.stage`, `deal.value`

Each stored as a **typed fact with a verbatim quote as its receipt** — not a model opinion
re-derived at read time. That is the architectural difference between this product and
connecting a mailbox to a chatbot: the chatbot re-derives meaning every time and cannot show its
work; this derives it once, stores it with provenance, and every card afterwards is auditable
and reproducible.

## How to fix it

### 2A · Extend the extraction contract
Add the nine fields above to what `capture/esqe` extraction asks for and validates. Signal
sources already in the payload: the signature block, the sender domain, self-introductions in
the thread body, calendar organiser role, thread subject.

### 2B · Judgement fields carry a lower authority rank than observed fields
`campaign-awaiting-reply.yaml` states the rule: *"A send is evidence of what was written, not of
what it was meant to achieve."* An objective is a JUDGEMENT. It must be written with a receipt
and an authority rank below an observed fact, so a stated purpose always beats an inferred one.

### 2C · `unknown` is never written
An unplaced thread keeps the field in `missing` rather than satisfying it with a meaningless
label. This rule already exists for `thread.objective` (Pass D) and must hold for all nine.

### 2D · Drain the parked attachments
776 attachment events, 767 parked. OCR now ships in the image (10 Sep). Draining them is what
turns *"you sent the deck"* from a guess into a fact.

**Acceptance:** on a fixture mailbox containing one signature block naming a title and one
thread whose subject states a purpose, assert `party.role` and `thread.objective` are written,
each with a non-empty verbatim span, and that a thread with neither writes neither and reports
both as missing.

---

# PROBLEM 3 — Layer 4's writing half is switched off

## What happened

`reason/llm_sites.py` defines three LLM sites, all gated on `FEATURE_BUNDLE`:

| Site | Question it answers |
|---|---|
| **R-1 `interpret`** | What does this situation mean |
| **R-3 `alternatives`** | What else could be done |
| **R-4 `effect`** | What happens if nothing is done |

Plus `reason/interpretation.py`, `reason/narration.py`, `reason/critique.py`,
`reason/bundle/sweep.py`, `reason/bundle/narrator.py`.

Layer 4 has five activation features. This is the complete contents of `l4_activation` for every
tenant that has ever existed:

| Feature | State |
|---|---|
| `roster_v2` | ON — `harsh`, "pilot run 2", 8 Sep |
| `ranking_v2` | ON — same hand, same minute |
| **`bundle`** | **never on, for anyone** |
| **`critique`** | **never on, for anyone** |
| **`brief`** | **never on, for anyone** |

| Table | Rows |
|---|---|
| `l4_reasoning_bundles` | **0** |
| `l4_r_site_calls` | **0** |
| `l4_r_site_generations` | **0** |
| `l4_brief_rankings` | **0** |

**The half of the product that writes prose has never executed once.**

## What should happen

R-1/R-3/R-4 run on published decisions and produce the interpretation, the alternatives and the
consequence — the clauses a template cannot write.

## How to fix it

### 3A · Enable `FEATURE_BUNDLE`
**Precondition: Problem 1 must be fixed first.** `bundle` narrates PUBLISHED decisions and there
are currently none — switched on today it runs against nothing and produces zero narratives.

### 3B · Enable `FEATURE_BRIEF`, then `FEATURE_CRITIQUE`
`PRECONDITIONS` in `platform/l4_activation.py` puts both after `ranking_v2`, which is on.

### 3C · Activation becomes automatic for a new tenant
Every switch in the stack was set by one person by hand in a 3-second window on 8 September. A
new customer gets none of them. L3 was fixed on 10 Sep (`platform/intelligence_onboarding`);
L1, L2 and L4 still need it, following the same pattern.

---

# PROBLEM 4 — The renderer cuts the card in half

## What happened

`genios_engine/deliver/render.py:16` — `HEADLINE_CAP = 60`, situation cap **140**.

Live evidence of the guards firing on real cards:

| Reject | Meaning |
|---|---|
| `V-01:len=61`, `len=64` | headline one to four characters over |
| `V-01-trimmed:201->111` | **the situation cut from 201 characters to 111** |
| `V-02:name:Insert` | invention guard caught a template placeholder leaking |
| `V-02:name:SwerashiGeniOS` | invention guard caught a concatenation artefact |

The corpus's own authored fallback for the campaign card:

```
{contacted} people received the same message on {sent_on} and {awaiting} have not answered.
The longest has been waiting {longest_wait_days} days. They were sent: "{quote}"
```

≈ **190 characters** with real values. **The card copy we authored is longer than the renderer
permits**, and the quote — the single most valuable thing on the card — sits at the end, so it
is the first thing the trim removes.

## How to fix it

- **4A** · The cap becomes a property of the card, not a global constant. A one-line nudge and a
  group briefing are different objects. Let the situation declare its own cap, with 140 as the
  default.
- **4B** · A verbatim quote is not prose and is not counted against the cap.
- **4C** · `V-02:name:Insert` is a template placeholder leaking into copy — a real bug upstream,
  not a hallucination. Fix at source.
- **4D** · A rejected LLM render re-templates against the corpus's authored fallback instead of
  dropping to raw slot-filling. 3 of 18 live cards took that path and read like *"2d since they
  wrote — still waiting on you"*.

---

# ORDER, AND WHAT PROVES EACH STEP

| Phase | Do | Proves it |
|---|---|---|
| 1 | 1E, 1F | two one-line fixes, no risk |
| **2** | **1A, 1B** | **campaign evidence 0 → 65; the first compiled card exists** |
| 3 | 4A, 4B, 4D | situation trims → 0; the quote survives |
| 4 | 1C, 1D | empty person nodes 30 → 0; source count per node 1 → 2 |
| **5** | **2A–2D** | **`party.role` 1 → many; `thread.objective` 0 → many** |
| **6** | **3A** | **`l4_r_site_calls` 0 → >0; the first narrative** |
| 7 | 3B, 3C, 4C | compounding |

**Phase 2 makes cards exist. Phase 5 makes them worth reading. Phase 6 makes them read like a
person wrote them.** Phase 3 is small and must not be skipped or 5 and 6 ship truncated.

# DEFINITION OF DONE

Run the live pipeline and get one card that says, in substance:

> **Theresa Hoffmann, Partner at Antler** — 30 days silent since you sent the deck on 11 August,
> in a raise where **6 of the 13** you contacted have not answered. They all received the same
> line: *"…"*. Sending it again is not the move.

| Clause | Comes from |
|---|---|
| "Theresa Hoffmann" | already in the graph |
| "Partner at" | **2A** |
| "Antler" | already in the graph (`works_at`) |
| "30 days silent" | already a fact |
| "you sent the deck" | **2D** |
| "on 11 August" | already a fact |
| "in a raise" | **2A** |
| "6 of the 13" | **1B** |
| "the same line: …" | **1A** + **4B** |
| "Sending it again is not the move" | **3A** |
