# Intelligence Parity — making the product produce what a human analyst produced by hand

> **Created:** 2026-09-10 · **Status:** Active — diagnosis complete and measured, build in progress
>
> **Purpose:** the ordered, measured route from "the compiled lane has never produced a card" to a live `campaign_awaiting_reply` card, naming for each step the number that must move.

**Written 10 September 2026. Every number below was measured read-only against the live pilot
tenant (`org_e97e…`) on that date. Nothing here is estimated.**

---

## 0. The thing we are trying to reproduce

On 9 September an analyst (Claude) read this tenant's live database directly and wrote findings
like:

> On 11 August, between 07:56 and 07:57, you sent one line to seven people and another to six —
> Peak XV, Afore, Titan, Together, 3one4, Z Fellows, IIM-B. Six of the thirteen have not
> answered. The longest has been waiting 30 days. They were all sent: *"<verbatim line>"*.
> Sending the same line again is not the move — they have all already received exactly that.

That is the quality bar. Five properties make it good:

| # | Property | Why it matters |
|---|---|---|
| P1 | **Grouped** — 13 people are ONE card, not 13 | 13 separate "chase this person" cards is noise; one campaign card is a decision |
| P2 | **Verbatim** — the actual sentence is quoted | The founder wrote it and does not remember which version went to whom |
| P3 | **Counted** — 6 of 13, longest 30 days | A number is actionable; "some people haven't replied" is not |
| P4 | **Honest about its limits** — "we do not know what the outreach was FOR" | An objective is a model's guess; a sent sentence is a receipt |
| P5 | **A real next action** — "the same line again is not it" | The card that repeats what already failed is worse than no card |

---

## 1. THE CRITICAL FINDING: this intelligence is already written

**We do not need to author new intelligence. All five properties above are already implemented
in this repository, and the data they need is already in the database.**

| What | Where | State |
|---|---|---|
| The campaign reading (P1, P3) | `context/correlation_conversation.find_campaigns` | Built. Produces 2 live campaigns on this tenant |
| The firm reading (P1) | `context/correlation_organization.find_organizations` | Built. Produces 2 live `organization_gone_quiet` |
| The card copy (P2, P4, P5) | `Domain Expertise/Admin Expertise/.../campaign-awaiting-reply.yaml` | Authored, schema-valid. Its `render_hint` says *"QUOTE IT… Never call the reply rate good or bad"* |
| The firm card copy | `.../organization-gone-quiet.yaml` | Authored, schema-valid |
| The situations themselves | `context_situations` | **Live: `campaign_awaiting_reply` ×2, `organization_gone_quiet` ×2, `awaiting_response` ×17** |

**So the gap is plumbing, not authorship.** Every one of those situations is sitting in the
database right now, and has never once become a card.

Proof: `cards` for this org, all time —

```
reason_code         | n  | first ever
commitment_overdue  | 11 | 2026-09-08
unanswered_email    |  7 | 2026-09-08
```

Cards ever built from the compiled/expertise lane: **0**.

---

## 2. Why nothing gets through — the chain, measured

```
L1 capture        884 events, 398 qualified signals        ✅ works
L2 context        185 active situations built              ✅ works
L2 evidence       evidence axis reads an EMPTY node        ❌ BREAKS HERE
L2 publish        absence situations held forever          ❌ (fixed 10 Sep, deployed)
L3 compile        381 expertise packages written           ✅ works
L3 activation     only 'admin' on, and only by hand        ❌ (fixed 10 Sep, pushed)
L4 reason         53 runs, all complete                    ✅ works
L4 confidence     ceiling 2300 vs floor 4500 → DEFER       ❌ consequence of L2
L4 emit           no selected candidate → nothing_to_emit  ❌ consequence
L5/L6 card        never reached                            —
```

The single sentence: **Layer 2 computes each situation's evidence by counting `graph_observations`
on the situation's own anchor node, and observations are only ever written onto the person who
SENT an email. Every synthetic anchor — campaign, organization, outreach, thread, company — has
zero.**

---

## 3. Layer-by-layer changes

### LAYER 1 — capture

L1 is healthy. Two real defects.

#### L1-1 · Gmail and Calendar never resolve to the same person
**Measured:** people appearing in both gmail and gcal `source_events`: **0**.

`evidence_score` awards 60 of its 100 points for *corroboration across sources* and 40 for
volume. With zero cross-source overlap, corroboration is permanently capped at 25 (one source).

**Change:** normalise the `actor` field per source before identity resolution. gcal writes an
organiser/calendar id; gmail writes an email address. They must reduce to the same key.
**File:** `capture/connectors/composio.py` (actor extraction) + `context/pipeline.py` identity
resolution.
**Number that must move:** people in both sources `0 → >0`; max `source_count` per node `1 → 2`.

#### L1-2 · Four signals rejected for having no evidence refs
**Measured:** `publication_rejections` = 4, all rule `V-4` ("evidence_refs is empty").
Low volume; same root cause as L2-3. Fixing L2-3 fixes this.

---

### LAYER 2 — context. **This is where it breaks.**

#### L2-1 · Observations are written only onto the sender
**Measured:** 1001 observations, on **30 person nodes**. Zero on any thread (66), company (43),
outreach (41), campaign (2), organization (2), commitment (15), condition (17).

**Change:** when an event is processed, write the observation onto every node the event
establishes — the thread, the counterparty, the company — not only the sender.
**File:** `context/pipeline.py` (the four `write_observation` call sites, all currently
`subject_node_id=sender_node` or `content_subject`).

#### L2-2 · Half the people have no evidence at all
**Measured:** 60 person nodes; **30 have zero observations**. These are exactly the people we
emailed who never replied — i.e. the subjects of every "they have gone quiet" card.

398 of the 1001 observations sit on the founder's own node.

**Change:** an outbound message is evidence about its RECIPIENT, not only about its sender.
Write the observation onto the recipient too.
**Same file as L2-1.**

#### L2-3 · Derived facts carry no provenance — **the biggest single lever**
**Measured:**

| Node type | Facts | With a source ref |
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

`_write_fact` inserts into `graph_facts` alone and never into `graph_source_refs`. The fact
exists; where it came from is lost.

**Change:** every writer of a derived fact must also write its source refs, carrying forward the
refs of the events it was derived from.
**Files:** `context/support_situations._write_fact`, `context/outreach_situations`,
`context/document_register`.

**Measured effect** — if evidence were computed from facts *with* their refs restored:

| Node type | Evidence now | After |
|---|---|---|
| campaign | 0 | **65** |
| organization | 0 | **65** |
| outreach | 0 | **65** |
| thread | 0 | **65** |

65 → 6500 bp, against a floor of 4500. **This is the change that crosses the bar.**

#### L2-4 · The evidence count reads the anchor's own node
Even with L2-1..3 fixed, the count must look in the right place. A situation anchored on a
synthetic node must count the evidence of the person/company it concerns.

**Change:** walk one hop from the anchor, **in both directions**, to `person` and `company`
nodes, and count over those. Direction matters: the live edge is `person → thread`, so a
thread-anchored situation walking outward finds nothing.

**Measured effect:** `first_response_overdue` (25 situations) `33 → 65`.
Situations clearing the bar: **6 → 17**.

For group situations (`campaign`, `organization`) one hop is not enough — the graph links the
anchor to only 2 representative people, while the real membership (40, 25, 18, 14 members per
group) lives in `context_correlation_members`. Count over the members.

#### L2-5 · 80 open merge proposals are suppressing identity across the tenant
**Measured:** `merge_proposals` status `open` = **80**, oldest 8 September.

`identity_score` returns 100 for zero open proposals, 40 for one, 20 for more. 104 of 185
situations sit at exactly 40.

This is **not a code fix** — it is a review queue nobody has worked. It is the cheapest lever
available.

**Measured effect:** situations clearing the bar **17 → 26**.

**Change:** build the resolve-duplicates flow (or auto-merge above a confidence threshold), and
surface the queue in the dashboard.

#### L2-6 · Absence situations could never publish — **FIXED, DEPLOYED 10 Sep**
`backfill_absence_l1` was called only from the importance sweep, never from the path that
decides publication, so `l1` was `None` for every situation claiming a silence and both hold
reasons fired. **Measured:** `awaiting_response` 401 held / **0 admitted**, ever.

---

### LAYER 3 — domain expertise

L3 compiles correctly: 381 expertise packages written.

#### L3-1 · Activation was manual and per-tenant — **FIXED, PUSHED 10 Sep**
`l3_activation` held **one row in the entire database** — `(pilot org, admin)`,
`enabled_by: 'harsh'`. Every other tenant, and every new signup, had zero, so the compiler
skipped all three authored corpora for them.

Now: each corpus declares `activation: {default_on, why}` in its own `domain.yaml`
(schema-enforced), and `provision_intelligence` switches on every declared-ready domain for any
tenant that has not already been decided about — running from `_run_l2`, so it backfills the
existing installed base as well as new signups.

#### L3-2 · Sales and Customer Support were never activated for anyone
Consequence of L3-1; now resolved by the same change. `sales` and `customer_support` carry
`default_on: true`.

---

### LAYER 4 — reasoning

#### L4-1 · The `analytic` axis is a wall, not a measurement
**Measured ramp** (`_analytic_sub_score`, floor 10, full population 200):

| Cohort peers | Axis | bp | vs floor 4500 |
|---|---|---|---|
| 5 (the legal minimum) | 12 | 1200 | defer |
| 30 (this tenant) | 23 | **2300** | defer |
| 77 | 44 | 4400 | defer |
| **78** | 45 | 4500 | **first pass** |

Every legal cohort size in [5, 77] lands below the floor. For a tenant with fewer than 78 peers
in a cohort, this axis is a deterministic veto that no operator action can clear — a constant
`False` wearing a threshold's clothes. The repo's own standard: *"A floor nothing trips and a
floor everything trips are both wrong."*

**Change (one line):** `reason/reasoners/confidence.py:81`
`_UNREAD_SITUATION_AXES = ("coverage",)` → `("coverage", "analytic")`.

The axis keeps being published as a receipt; it stops being a ceiling. Cohort thinness belongs
in the ranking that consumes importance, not in a confidence gate.

**Measured effect on this tenant today: 0 additional situations** (evidence is already lower).
Ship it anyway — it silently blocks every small tenant forever.

#### L4-2 · Seven of seventeen units never run
**Measured skips**, reason `no_declared_input_available`: `core.relationship` 150,
`core.policy` 150, `core.resource` 134, `core.scheduling` 134, `core.timeline` 94,
`core.temporal` 94, `core.opportunity` 94.

The capability declares inputs the situation does not carry. Each skipped unit is a dimension of
the answer that is simply absent, and `missing_data` on deferred runs names them
(`below_floor_absent_unit:core.policy`).

**Change:** for each of the seven, either (a) the corpus stops declaring an input nothing emits,
or (b) L2 starts emitting it. Decide per unit against the live data, not in bulk.

#### L4-3 · A DEFER is total silence
**Measured:** 53 of 53 expertise runs today deferred. No card, no suppression-log row, no user
visible trace. The legacy lane writes a suppression row (`runner.py`); the compiled lane writes
nothing.

**Change:** a below-floor compiled decision should still be recorded, and should be able to
reach the user as an `observation`-level card carrying its confidence and its cause — the floor
keeps stopping it INSTRUCTING; it stops making it invisible. `contracts/abstention` already has
the three levels and the legacy lane already ships `review` and `observation` cards.

**This is a separate unit and must land after the confidence number is correct** — shipping
"23% confident" to a user while 23 actually means "your cohort has 30 members" would be
productising a wrong number.

---

### LAYER 5 / 6 — the cards that do ship

18 cards ever, two kinds only. Their quality is the pre-existing problem recorded in
`INTELLIGENCE_SHALLOWNESS_ROOT_CAUSE.md`:

- *"Deliver $2,000 monthly savings to myzyner.com"* — a promotional email read as our own
  commitment.
- *"Confirm attendance for Rohit Swerashi spotlight call"* — the founder's own name resolved as
  the counterparty.

These are legacy-lane cards. They are displaced, not repaired, by the compiled lane working.

---

## 4. Scoring changes

**The formulas are mostly right. The inputs are wrong.** Do not tune a threshold to make output
appear.

| Score | Formula | Verdict | Change |
|---|---|---|---|
| `evidence_score` | `min(40, events×8) + min(60, sources×25)` | **Formula correct, input wrong** | Fix L2-1..4. Do not touch the formula |
| `identity_score` | 0 proposals → 100, 1 → 40, 2+ → 20 | **Correct** | Work the 80-item queue (L2-5) |
| `freshness_score` | ≤3d → 100, ≤7d → 70, ≤30d → 50 … | **Correct and honest** | **Do not touch.** 68 situations are 90+ days old and should score low |
| `analytic` sub-score | `10 + peers × 90 / 200` | **Structurally broken as a gate** | Remove from the ceiling (L4-1). Do not rescale — no measurement licenses a new constant |
| `DEFAULT_CONFIDENCE_FLOOR_BP` | 4500 | **Uncalibrated but not the defect** | **Do not lower.** Lowering to admit 2300 would admit ~120 of 185 rows whose whole evidence is one unconfirmed email |
| Layer-2 ceiling | `min` over assessed axes | **Correct** | Keep. The minimum is right: perfect evidence about an entity we cannot identify is not 60% confidence, it is unusable |

**One deliberate non-change:** the confidence floor stays at 4500. Every fix above raises the
INPUT to the number, which is the only honest way to cross a bar.

---

## 5. Order of work, and the number that proves each step

Ranked by (measured effect ÷ effort).

| # | Change | Layer | Effort | Number that must move |
|---|---|---|---|---|
| 1 | Derived facts carry their source refs | L2-3 | S | campaign/organization/outreach evidence `0 → 65` |
| 2 | Evidence walks one hop to person/company, both directions; group situations count members | L2-4 | S | situations clearing the bar `6 → 17` |
| 3 | Remove `analytic` from the confidence ceiling | L4-1 | XS (1 line) | no tenant is vetoed by cohort size again |
| 4 | Resolve the 80 open merge proposals | L2-5 | M (queue + UI) | clearing the bar `17 → 26`; identity `40 → 100` |
| 5 | Observations written onto every node an event establishes, incl. recipients | L2-1, L2-2 | M | empty person nodes `30 → 0` |
| 6 | Gmail/Calendar actor normalisation | L1-1 | M | max `source_count` per node `1 → 2`; evidence `65 → 90` |
| 7 | The seven skipped units: fix the declaration or emit the input | L4-2 | L | skips `150 → 0` per unit |
| 8 | A DEFER produces an observation card, not silence | L4-3 | M | deferred runs producing a user-visible trace `0 → 53` |

**Steps 1 + 2 together are what turn on the compiled lane.** Steps 4 and 6 are what take it from
working to good.

### Definition of done

The acceptance test is not a unit test. It is: **run the live pipeline on this tenant and get a
`campaign_awaiting_reply` card whose situation text names the count, the longest wait and the
verbatim line, and whose artifact does not suggest re-sending the same message.**

That card's copy is already written, in
`Domain Expertise/Admin Expertise/capabilities/01-executive-support/inbox-and-correspondence/situations/campaign-awaiting-reply.yaml`.
Nothing new needs to be authored to pass it.

---

## 6. What is already done (10 September)

| | Change | Status |
|---|---|---|
| L2-6 | Absence receipts reach the publish path | Merged to `harsh/mvp`, deployed 14:54 UTC |
| L3-1 | Corpus declares `activation.default_on`; `provision_intelligence` runs from `_run_l2` | Pushed on `y-combinator-w27` |
| — | A completed OAuth mirrors the connection and enqueues the first pull | Pushed |
| — | `viewer` separated from `admin` so per-person features reach the founder | Pushed |
| — | One card reaches everyone who declared responsibility for it | Pushed |
