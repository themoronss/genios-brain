# Why the intelligence is shallow — the complete analysis

> **Created:** 2026-09-10 · **Status:** Active — analysis complete, build not started
>
> **Purpose:** one consolidated answer to "why can a human reading this database write better
> intelligence than the product can", replacing the partial answers given during the session that
> produced it. Every number is measured read-only against the live pilot tenant on 2026-09-10.

---

## THE ONE-PARAGRAPH ANSWER

The product is roughly three times larger than the part of it that is switched on. Of 153 tables
in the live database, **51 have never had a single row written**. Everything that IS running
produces **behaviour** — who mailed whom, when, how long ago, whose turn it is. Everything that
is switched off or unwired produces **meaning** — who a person is, what a relationship is for,
what a situation implies, what happens if you ignore it. That is precisely the difference
between the card you get ("Reply to Sunil now") and the analysis a human writes ("Theresa
Hoffmann, Partner at Antler, silent 30 days into a raise where 6 of 13 have gone quiet"). It is
not one bug. It is one **pattern**, repeated at every layer: the measuring half shipped and the
interpreting half did not.

---

## 1. WHAT IS ACTUALLY SWITCHED ON

There are four activation tables, one per layer. This is the entire contents of all four, for
every tenant that has ever existed:

| Layer | Switch | State |
|---|---|---|
| L1 | `l1_semantic_activation` | **ON** — 1 org (`harsh`, "pilot run 2", 8 Sep) |
| L2 | `l2_v2_activation.analytic` | **ON** — same org, same hand, same minute |
| L2 | `l2_v2_activation.patterns` | **ON** — same |
| L3 | `l3_activation` | **`admin` only** — 1 domain of 3. `sales` and `customer_support` never on, for anyone |
| L4 | `roster_v2` | **ON** |
| L4 | `ranking_v2` | **ON** |
| L4 | **`bundle`** | **OFF — never on, for anyone** |
| L4 | **`critique`** | **OFF — never on, for anyone** |
| L4 | **`brief`** | **OFF — never on, for anyone** |

Every row in all four tables was written by one person by hand on 8 September within a 3-second
window. **Nothing in the product has ever switched anything on by itself** — that gap is now
fixed for L3 (`provision_intelligence`, pushed 10 Sep) and remains open for L1, L2 and L4.

---

## 2. WHAT IS BUILT AND HAS NEVER RUN

51 of 153 tables are empty. Grouped by capability, discounting the ones that are legitimately
empty (nobody has paid, nobody has been invited, nobody has deleted an account):

### 2.1 · The Layer 4 narrative lane — the one that would write like a human
| Table | Rows |
|---|---|
| `l4_reasoning_bundles` | **0** |
| `l4_r_site_calls` | **0** |
| `l4_r_site_generations` | **0** |
| `l4_brief_rankings` | **0** |

`reason/llm_sites.py` defines three LLM sites — **R-1 `interpret`** (what does this situation
mean), **R-3 `alternatives`** (what else could be done), **R-4 `effect`** (what happens if
nothing is done) — plus `reason/interpretation.py`, `reason/narration.py`, `reason/critique.py`,
`reason/bundle/sweep.py` and `reason/bundle/narrator.py`.

All of it is gated on `FEATURE_BUNDLE`, which has never been enabled. **This is the half of the
product that produces prose, and it has never executed once.**

### 2.2 · The learning lane
| Table | Rows |
|---|---|
| `card_feedback_verdicts` | **0** |
| `card_feedback_revisions` | **0** |
| `learning_event_inbox` | **0** |
| `learned_brain_entries` | **0** |
| `calibration_nudges` | **0** |
| `user_models` / `user_model_proposals` | **0** |
| `discrepancies` | **0** |

Nothing the user does with a card is ever read back. The system cannot get better at this
tenant, ever.

### 2.3 · Pattern recognition (L2.6)
| Table | Rows |
|---|---|
| `pattern_activation` | **0** |
| `pattern_fires` | **0** |

The switch (`l2_v2_activation.patterns`) is ON and the tables are empty — so this is **wired,
switched on, and still producing nothing**. Different failure from 2.1: not off, but silent.

### 2.4 · Authority and policy
| Table | Rows |
|---|---|
| `authority_rules` | **0** |
| `policy_rules` | **0** |
| `approvals_queue` | **0** |
| `org_qualification_floors` | **0** |
| `org_mission_critical_entities` | **0** |
| `rule_mutes` | **0** |

The tenant has declared nothing about who approves what, what matters most, or what to ignore.
Some of this is a UI gap (there is nowhere to declare it); some is that nothing infers it.

### 2.5 · Delivery beyond the in-app queue
| Table | Rows |
|---|---|
| `delivery_attempts` | **0** |
| `delivery_preferences` | **0** |
| `delivery_rate_windows` | **0** |
| `delivery_outbox` | 1 (a single `failed_terminal`) |

Cards exist only inside the app. Nothing has ever been pushed anywhere.

### 2.6 · People and org structure
| Table | Rows |
|---|---|
| `org_members` | **0** |
| `seat_responsibilities` | **0** |
| `integration_preferences` | **0** |
| `workspace_accounts` | **0** |

---

## 3. THE GRAPH — measured against the model it should have

The right mental model is: **me → my company → counterparty companies → their people → each
person's role, commitments and relationships.** Here is how much of that exists:

| Should have | Has |
|---|---|
| Companies with people attached | 43 of 43 ✅ |
| People linked to their company | 49 of 60 ✅ |
| People with a commitment | **9 of 60** |
| **People with a role or designation** | **6 of 60** |

Now every fact in the graph, sorted by what kind of thing it is:

| Kind | Facts | Distinct fields |
|---|---|---|
| `derived.*` — trends, anomalies, engagement counts | 991 | 30 |
| `thread.*` — whose turn, last inbound | 500 | 7 |
| Everything else | 895 | 86 |

But "everything else" is mostly still behaviour wearing a business name —
`response.overdue_hours`, `outreach.days_waiting`, `outreach.follow_up_count`,
`backlog.age_days`, `condition.age_days`.

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

**The graph is a behavioural graph, not a business graph.** It knows Theresa has not replied in
30 days. It does not know Theresa is an investor.

This is why the ceiling on card quality is what it is, independently of every plumbing bug
below. Even with perfect evidence, the best sentence available is *"Theresa hasn't replied in
30 days"*, because that is the entirety of what the graph holds about her.

---

## 4. THE PLUMBING FAULTS — why even the behavioural cards do not appear

Cards ever built for this tenant: **18**, in two kinds (`unanswered_email` 7,
`commitment_overdue` 11). Cards ever built from the compiled/expertise lane: **0**.

### 4.1 · Evidence is counted on a node that is always empty
`graph_observations` are written only onto the person who **sent** an email — 1001 of them, on
30 person nodes. Zero on any thread (66), company (43), outreach (41), campaign (2),
organization (2), commitment (15).

Every situation that is not about one person therefore scores evidence **0**.

### 4.2 · Derived facts carry no provenance
`_write_fact` inserts into `graph_facts` and never into `graph_source_refs`:

| Node type | Facts | With a source ref |
|---|---|---|
| company | 509 | **0** |
| outreach | 175 | **0** |
| condition | 134 | **0** |
| campaign | 12 | **0** |
| organization | 10 | **0** |
| meeting | 29 | 29 ✅ |

### 4.3 · The calendar lane writes facts but never observations
50 calendar events, all passing L1 cleanly (`s2_structured_lane pass`, 50/50 emitted). Result:
29 facts, 5 meeting nodes, 2 person nodes, **0 observations**. Since evidence counts
observations, calendar contributes nothing to any confidence score.

Also: `calendar.py:115` hardcodes `actor_type="internal_user"` for the organiser. All 50
calendar events label their organiser as the tenant's own staff — including
`theresa.hoffmann@antler.co`.

*(Correction to an earlier claim made in this session: Gmail and Calendar **do** resolve to the
same people — 16 addresses appear in both. The earlier "0 overlap" compared whole JSON blobs
rather than the email inside them.)*

### 4.4 · Half of all people have no evidence at all
30 of 60 person nodes carry zero observations. They are the people who never replied — i.e. the
subject of every "they have gone quiet" card. 398 of the 1001 observations sit on the founder's
own node.

### 4.5 · 80 open merge proposals suppress identity tenant-wide
`identity_score` returns 100 for zero open proposals, 40 for one. There are **80 open**, oldest
8 September, and 104 of 185 situations sit at exactly 40 as a result. **Not a code fix** — a
review queue nobody has worked.

### 4.6 · The `analytic` axis is a wall, not a measurement
Its ramp maps cohort size to a score with a floor of 10 and a full population of 200:

| Peers | Axis | bp | vs floor 4500 |
|---|---|---|---|
| 5 (legal minimum) | 12 | 1200 | defer |
| 30 (this tenant) | 23 | **2300** | defer |
| 77 | 44 | 4400 | defer |
| 78 | 45 | 4500 | first pass |

**Every legal cohort size below 78 peers is below the floor.** For a small tenant this axis is a
deterministic veto no operator action can clear.

### 4.7 · Absence situations could never publish — FIXED, deployed 10 Sep
`awaiting_response`: 401 held, **0 admitted**, ever. `backfill_absence_l1` ran only in the
importance sweep and never on the path that decides publication.

### 4.8 · Seven of seventeen reasoning units never run
`no_declared_input_available`: `core.relationship` 150, `core.policy` 150, `core.resource` 134,
`core.scheduling` 134, `core.timeline` 94, `core.temporal` 94, `core.opportunity` 94.

### 4.9 · A DEFER produces nothing at all
53 of 53 expertise runs deferred today. No card, no suppression row, no user-visible trace. The
legacy lane writes a suppression row; the compiled lane writes nothing.

---

## 5. WHERE THE LLM ACTUALLY IS

| Purpose | Calls, all time | Layer |
|---|---|---|
| `extract` | 1,413 | L1 |
| `relevance_gate` | 1,340 | L1 |
| `l5_render` | 1,124 | L5/L6 |
| `l2:resolution` | 273 | L2 |
| R-1 / R-3 / R-4 | **0** | **L4 — built, gated on `bundle`, never on** |
| `org_rule_extract` | **0** | L3 brains |
| `behavior_distill` | **0** | L3 brains |

The LLM reads every email once, and is asked for timing and process fields. It is **not** asked
who this person is to this business or what this exchange is for — even though it has the text
in front of it and the corpus already defines the fields to store the answer in.

---

## 6. THE PLAN

Four tracks. Tracks A and B together are the minimum for the target quality; C and D are what
make it compound.

### TRACK A — make the behavioural cards appear at all
*Effect: situations clearing the confidence bar 6 → 26. Cards start existing.*

| # | Change | Where |
|---|---|---|
| A1 | Derived facts write their source refs, carried from the events they came from | `context/support_situations._write_fact`, `outreach_situations`, `document_register` |
| A2 | Evidence walks one hop from the anchor to `person`/`company`, **both directions**; group situations count their members from `context_correlation_members` | `context/situations`, `outreach_situations._EVENT_COUNTS` |
| A3 | The structured (calendar) lane writes observations, not only facts | `context/pipeline.py` |
| A4 | Observations written onto every node an event establishes — thread, counterparty, company — and onto **recipients**, not only senders | `context/pipeline.py`, 4 `write_observation` sites |
| A5 | Remove `analytic` from the confidence ceiling | `reason/reasoners/confidence.py:81`, one line |
| A6 | Work the 80 open merge proposals; build the resolve flow | `context/merge`, + UI |
| A7 | `calendar.py:115` stops labelling every organiser `internal_user` | one line |

### TRACK B — give the graph nouns
*Effect: cards stop saying "hasn't replied" and start saying "Partner at Antler, in a raise".*
**This is the track that closes the gap to a human analyst.**

| # | Change | Where |
|---|---|---|
| B1 | The extraction prompt asks who this person is to this business — write `party.role`, `person.title`, `company.industry` | `capture/esqe` extraction contract |
| B2 | And what this exchange is for — write `thread.objective`, `campaign.objective`, `relationship.nature` | same |
| B3 | And what state any deal is in — `deal.stage`, `deal.value` | same |
| B4 | Every one stored as a typed fact with a verbatim quote as its receipt, so reasoning stays deterministic and auditable | existing fact contract |

The corpus already declares all of these fields. They have writers for none of them.

### TRACK C — switch on the half of Layer 4 that writes
*Effect: the prose. Requires Track A first — `bundle` narrates published decisions, and there
are currently none.*

| # | Change |
|---|---|
| C1 | Enable `FEATURE_BUNDLE` → R-1 `interpret`, R-3 `alternatives`, R-4 `effect` begin running |
| C2 | Enable `FEATURE_BRIEF` → the daily re-rank |
| C3 | Enable `FEATURE_CRITIQUE` |
| C4 | Make L1/L2/L4 activation automatic for new tenants, as L3 now is |

### TRACK D — close the loop
| # | Change |
|---|---|
| D1 | Card feedback is read back — `card_feedback_verdicts` stops being empty |
| D2 | `pattern_fires` — switched on and silent; find out why |
| D3 | Delivery beyond the in-app queue |

---

## 7. THE ORDER, AND WHAT PROVES EACH STEP

| Step | Track | Number that must move |
|---|---|---|
| 1 | A1 + A2 | campaign/organization/outreach evidence **0 → 65**; situations clearing the bar **6 → 17** |
| 2 | A5 + A7 | two one-line fixes; no tenant vetoed by cohort size |
| 3 | A6 | clearing the bar **17 → 26**; identity **40 → 100** |
| 4 | A3 + A4 | empty person nodes **30 → 0**; source count per node **1 → 2**; evidence **65 → 90** |
| 5 | **B1–B4** | `party.role` **1 → most people**; `thread.objective` **0 → most threads** |
| 6 | C1 | `l4_r_site_calls` **0 → >0**; the first narrative card exists |
| 7 | C2, C3, C4, D | compounding |

**Steps 1–4 are plumbing: they make cards appear. Step 5 is what makes them worth reading. Step
6 is what makes them read like a person wrote them.**

### Definition of done

Run the live pipeline and get one card that says, in substance:

> Theresa Hoffmann, Partner at Antler — 30 days silent since you sent the deck on 11 August, in
> a raise where 6 of the 13 you contacted have not answered. They all received the same line:
> *"…"*. Sending it again is not the move.

Every clause in that sentence maps to something above: the name and role to **B1**, "Antler" to
the graph edge that already exists, "in a raise" to **B2**, "6 of 13" to **A2**, the quote to
**A1**, and "sending it again is not the move" to **C1**.
