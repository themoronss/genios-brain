# Build to the target card — the complete construction plan

> **Created:** 2026-09-10 · **Status:** Active — plan complete, build not started
>
> **Purpose:** everything that has to be built, switched on, widened or removed for the product
> to emit the target card. Decomposed clause by clause from the target sentence, so nothing in
> the plan exists without a clause that needs it, and no clause is left without a change.

Companion to `WHY_THE_INTELLIGENCE_IS_SHALLOW.md` (the diagnosis). Every number measured
read-only against the live pilot tenant on 2026-09-10.

---

## THE TARGET

> **Theresa Hoffmann, Partner at Antler** — 30 days silent since you sent the deck on 11 August,
> in a raise where **6 of the 13** you contacted have not answered. They all received the same
> line: *"…"*. Sending it again is not the move.

---

## 0. THE TARGET, DECOMPOSED

Every clause, what data it needs, and whether that data exists today.

| # | Clause | Needs | Today | Work |
|---|---|---|---|---|
| 1 | "Theresa Hoffmann" | person display name | ✅ exists | — |
| 2 | **"Partner at"** | `party.role` / `person.title` | **1 fact in the whole graph** | **B1** |
| 3 | "Antler" | `works_at` edge → company | ✅ 47 edges exist | — |
| 4 | "30 days silent" | `outreach.days_waiting` | ✅ 41 facts | — |
| 5 | "since you sent the deck" | `thread.last_outbound` + attachment awareness | partial | **B5** |
| 6 | "on 11 August" | `campaign.sent_on` | ✅ | — |
| 7 | **"in a raise"** | `thread.objective` / `campaign.objective` | **0 facts** | **B2** |
| 8 | "6 of the 13" | `campaign.awaiting` / `campaign.contacted` | ✅ situation exists | **A** (to make it publish) |
| 9 | "the same line: …" | `campaign.quote` | ✅ | **A** |
| 10 | **"Sending it again is not the move"** | R-1 interpret / R-3 alternatives | **switched off** | **C1** |
| — | the card existing at all | evidence ≥ 45, confidence ≥ 4500 | evidence **0** | **A1, A2** |
| — | the sentence surviving the renderer | situation ≤ 140 chars | target is **224** | **E1** |

**Five tracks fall out: A (plumbing), B (nouns), C (the writing half), D (learning), E (the
surface).** Nothing else is needed, and none of these can be skipped.

---

## TRACK A — PLUMBING · make a card exist at all

*Nothing below this line matters until a compiled card can be built. Today: zero, ever.*

### A1 · Derived facts carry their provenance
**Fault:** `_write_fact` inserts into `graph_facts` and never into `graph_source_refs`.

| Node type | Facts | With source ref |
|---|---|---|
| company | 509 | **0** |
| outreach | 175 | **0** |
| condition | 134 | **0** |
| campaign | 12 | **0** |
| organization | 10 | **0** |

**Change:** every derived-fact writer carries forward the `graph_source_refs` of the events it
derived from — one row per contributing event, with the same `independence_group` discipline the
observation path already uses.
**Files:** `context/support_situations._write_fact`, `context/outreach_situations`,
`context/document_register`.
**Proves it:** campaign/organization/outreach evidence **0 → 65**.

### A2 · Evidence is counted where the situation actually lives
**Fault:** `_EVENT_COUNTS` groups `graph_observations` by `subject_node_id`, and the situation
reads its own anchor — which is a synthetic node with none.

**Change, two parts:**
- **One hop, both directions.** Walk the anchor to `person` and `company` neighbours and count
  over those. Direction is load-bearing: the live edge is `person → thread`, so a thread-anchored
  situation walking outward alone finds nothing.
- **Group situations count members, not edges.** The graph links a campaign to 2 representative
  people; the real membership (40, 25, 18, 14 per group) lives in `context_correlation_members`.

**Proves it:** situations clearing the bar **6 → 17**; `first_response_overdue` **33 → 65**.

### A3 · The calendar lane writes observations
**Fault:** 50 calendar events → 29 facts, 5 meeting nodes, 2 person nodes, **0 observations**.
The structured lane writes facts only; the evidence axis counts observations.

**Change:** the structured lane writes an observation per established node, like the text lane.
**Proves it:** `graph_observations` from gcal **0 → >0**; max `source_count` per node **1 → 2**.

### A4 · Observations land on everyone an event establishes
**Fault:** written only onto the sender. 1001 observations on 30 person nodes; **30 of 60 people
are empty**, and they are exactly the people who never replied. 398 sit on the founder alone.

**Change:** write onto the thread, the counterparty, the company — and onto **recipients**. An
outbound message is evidence about who received it.
**File:** `context/pipeline.py`, the four `write_observation` sites.
**Proves it:** empty person nodes **30 → 0**.

### A5 · Remove `analytic` from the confidence ceiling · **one line**
**Fault:** its ramp maps every legal cohort in [5, 77] peers to [1200, 4400] bp against a 4500
floor. 78 peers required. A veto no operator action can clear — a constant `False` wearing a
threshold's clothes.

**Change:** `reason/reasoners/confidence.py:81` — `_UNREAD_SITUATION_AXES = ("coverage",)` →
`("coverage", "analytic")`. The axis keeps publishing as a receipt; it stops being a ceiling.
Cohort thinness belongs in the ranking that consumes importance, not in a confidence gate.
**Do not rescale the ramp** — no measurement in the repo licenses a new constant.

### A6 · `calendar.py:115` stops calling every organiser internal · **one line**
**Fault:** `actor_type="internal_user"` hardcoded. All 50 calendar events label the organiser as
the tenant's own staff — `theresa.hoffmann@antler.co` included.
**Change:** derive it from the "us" set (`context/runner._internal_emails`), the same source the
rest of L2 uses.

### A7 · Work the 80 open merge proposals
**Fault:** `identity_score` returns 100 for zero open proposals and 40 for one. There are **80
open**, oldest 8 September; 104 of 185 situations sit at exactly 40.
**Not a code fix in itself** — a review queue nobody has worked, plus the UI to work it, plus
auto-merge above a confidence threshold.
**Proves it:** clearing the bar **17 → 26**; identity **40 → 100**.

### A8 · Absence receipts on the publish path — **DONE, deployed 10 Sep**
`awaiting_response`: 401 held / **0 admitted**, ever, because `backfill_absence_l1` ran only in
the importance sweep.

> **Track A total: situations clearing the bar 6 → 26. Cards begin to exist.**
> **Ceiling of Track A alone:** *"Peak XV — 2 of 2 gone quiet, longest 24 days."* Real, useful,
> and still not the target.

---

## TRACK B — NOUNS · make the cards worth reading

*This is the track that closes the gap to a human analyst. Everything else is delivery.*

The graph is behavioural. It knows who mailed whom and when. It does not know who anybody **is**.

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

The corpus already declares every one of these. **None has a writer.**

### B1 · Who is this person to this business
Extract `party.role`, `person.title`, `company.industry`.
Signal sources already in hand: the signature block, the sender domain, the thread's own
introductions ("I lead investments at…"), the calendar invite's organiser role.
**Proves it:** `party.role` **1 → most counterparties**.

### B2 · What is this exchange for
Extract `thread.objective`, `campaign.objective`, `relationship.nature`,
`organization.relationship`.

**This is the hardest and the most valuable.** `campaign-awaiting-reply.yaml` states the rule it
must obey: *"A send is evidence of what was written, not of what it was meant to achieve"* — so
an objective is a JUDGEMENT and must be written with a receipt and an authority rank below an
observed fact, never as if it were observed. `unknown` is never written; an unplaced thread keeps
the field in `missing`.

### B3 · What state is any deal in
`deal.stage`, `deal.value`. Same discipline.

### B4 · Every one stored as a typed fact with a verbatim quote as its receipt
Not a model opinion at read time — a stored fact with provenance, so reasoning stays
deterministic and reproducible, and a card can show why it believes Theresa is a partner.

**This is the whole architectural difference between this product and connecting Gmail to a
chatbot:** the chatbot re-derives the meaning every time and cannot show its work; this derives
it once, stores it with a receipt, and every card afterwards is auditable.

### B5 · Attachment awareness — "the deck"
776 attachment events, 767 parked. OCR now ships in the image (Harsh, 10 Sep). Drain the parked
queue so "you sent the deck" is a fact rather than a guess.

> **Track B is where the LLM should do MORE work, at Layer 1, once per message.** It already
> reads every email (1,413 `extract` calls) and is asked only for timing and process fields.

---

## TRACK C — THE WRITING HALF · switch on Layer 4's prose

`reason/llm_sites.py` defines three sites, all gated on `FEATURE_BUNDLE`:

| Site | Question it answers |
|---|---|
| **R-1 `interpret`** | What does this situation mean |
| **R-3 `alternatives`** | What else could be done |
| **R-4 `effect`** | What happens if nothing is done |

Plus `interpretation.py`, `narration.py`, `critique.py`, `bundle/sweep.py`, `bundle/narrator.py`.

| Table | Rows |
|---|---|
| `l4_reasoning_bundles` | **0** |
| `l4_r_site_calls` | **0** |
| `l4_r_site_generations` | **0** |
| `l4_brief_rankings` | **0** |

**Never executed once, for any tenant.** `bundle`, `critique` and `brief` have never been on.

### C1 · Enable `FEATURE_BUNDLE`
Gives clause 10 — *"Sending it again is not the move"*. That sentence is an R-3 answer.
**Precondition: Track A.** `bundle` narrates PUBLISHED decisions, and there are currently none —
switch it on today and it runs against nothing.

### C2 · Enable `FEATURE_BRIEF` — the daily re-rank with `rank_components` per entry.
### C3 · Enable `FEATURE_CRITIQUE`.
### C4 · Make L1, L2 and L4 activation automatic for a new tenant, as L3 now is.
Today every switch in the stack was set by one person by hand in a 3-second window on 8
September. A new customer gets none of them.

---

## TRACK D — LEARNING · make it compound

| Table | Rows |
|---|---|
| `card_feedback_verdicts` | **0** |
| `card_feedback_revisions` | **0** |
| `learning_event_inbox` | **0** |
| `learned_brain_entries` | **0** |
| `calibration_nudges` | **0** |
| `user_models` | **0** |
| `pattern_fires` | **0** — *switch is ON and it is still silent* |

### D1 · Card feedback is read back.
Nothing a user does with a card ever returns to the system. It cannot get better at this tenant.

### D2 · `pattern_fires` — switched on, producing nothing. Different failure from the rest: not
off, silent. Find out why.

### D3 · Delivery beyond the in-app queue. `delivery_attempts` 0, `delivery_preferences` 0.

---

## TRACK E — THE SURFACE · let the good sentence through

**Newly found, and it blocks the target card outright.**

`deliver/render.py:16` — `HEADLINE_CAP = 60`, situation cap **140**.

Live evidence of the guards firing:

| Reject | Meaning |
|---|---|
| `V-01:len=61`, `len=64` | headline one to four characters over |
| `V-01-trimmed:201->111` | **the situation cut from 201 characters to 111** |
| `V-02:name:Insert` | invention guard caught a template placeholder leaking |
| `V-02:name:SwerashiGeniOS` | invention guard caught a concatenation artefact |

The target situation is **224 characters**. The corpus's own authored fallback for that card —

```
{contacted} people received the same message on {sent_on} and {awaiting} have not answered.
The longest has been waiting {longest_wait_days} days. They were sent: "{quote}"
```

— is about **190 characters** with real values.

**The card copy we authored is longer than the renderer permits.** Both would ship cut in half.

### E1 · The cap becomes a property of the card, not a global constant
A one-line nudge and a group briefing are different objects. A `brief` artifact kind needs room
for a count, a duration and a quote; a nudge does not. Let the situation declare its own cap, with
the current 140 as the default.

### E2 · A quote is not prose and must not be counted against the cap
The verbatim line is the single most valuable thing on the card (P2 of the quality bar) and it is
the part the trim removes first, because it sits at the end.

### E3 · The invention guard must not fire on the tenant's own material
`V-02:name:Insert` is a template placeholder that leaked into the copy — a real bug upstream, not
a hallucination. `SwerashiGeniOS` is a concatenation artefact. Both should be fixed at source and
neither should look like a hallucination to the guard.

### E4 · The fallback stops being mad-libs
Today a rejected render falls to raw slot-filling. 3 of 18 live cards took that path and read
like *"2d since they wrote — still waiting on you"*. A rejected LLM render should re-template
against the corpus's authored fallback — which is written, and good — rather than dropping to
tokens.

---

## THE ORDER

| Phase | Steps | What you get | Proof |
|---|---|---|---|
| **1** | A5, A6 | two one-line fixes, no risk | no tenant vetoed by cohort size |
| **2** | A1, A2 | **compiled cards start existing** | evidence 0 → 65; bar 6 → 17 |
| **3** | E1, E2, E4 | the sentence survives the surface | situation trims **0** |
| **4** | A7 | identity unblocked | bar 17 → 26 |
| **5** | A3, A4 | cross-source corroboration | source count 1 → 2; evidence 65 → 90 |
| **6** | **B1, B2, B3, B4** | **the cards gain nouns** | `party.role` 1 → many; `thread.objective` 0 → many |
| **7** | C1 | **the prose** | `l4_r_site_calls` 0 → >0 |
| **8** | B5, C2, C3, C4, D | compounding | |

**Phase 2 makes cards exist. Phase 6 makes them worth reading. Phase 7 makes them read like a
person wrote them.** Phase 3 is small and must not be skipped, or 6 and 7 ship truncated.

---

## WHAT IS DELIBERATELY NOT ON THIS PLAN

| Not doing | Why |
|---|---|
| Lowering `DEFAULT_CONFIDENCE_FLOOR_BP` from 4500 | Admitting 2300 admits ~120 of 185 situations whose entire evidence is one unconfirmed email. Every change above raises the INPUT instead |
| Touching `freshness_score` | 68 situations really are 90+ days old. Their confidence should be low |
| Rescaling the `analytic` ramp | No measurement licenses a new constant. Removal from the ceiling requires none |
| Putting an LLM in the reasoning units | Reasoning must stay deterministic and replayable. The LLM belongs at extraction (Track B) and at narration (Track C), both with stored receipts |
| Widening `cards_one_per_signal` | Three writers upsert on it and four reads join it; widening double-counts a situation in the brief and the budget |
