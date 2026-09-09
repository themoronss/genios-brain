# Expected vs Reality — the Globe's architecture against the first live run

> **Created:** 2026-09-08 · **Status:** Active

**Purpose:** put the design document (`GeniOS-Design-Globe`, the *expected*) side by side with the
code at HEAD `acb18c8` and the measured pilot (`L1_L4_PILOT_FUNNEL.md`, the *reality*), layer by
layer and group by group, and name — with file and line — the exact units that produce the wrong
output. Nothing here is estimated: every number is either read from the funnel sweep or counted
out of the repository.

**Tenant:** `org_e97e86f858ad48b2bbf64b8a` · Gmail + Calendar · 12 Aug – 8 Sep 2026
**Sources of truth:** Globe HTML (vision) · `genios_engine/` at `acb18c8` (code) ·
`scripts/pipeline_funnel_report.py` output (data) · `Domain Expertise/` corpus (knowledge)

---

## 0. The one-paragraph answer

The engine did not hallucinate and the model was not wrong. **Four independent, individually
defensible decisions compose into a wrong product.** L1 has no feature that distinguishes a
message addressed to you from a message blasted to a list, so cold marketing enters as ordinary
business mail. L2 builds `commitment_overdue` without reading the `owns` edge it just wrote, so
somebody else's promise is rendered in the founder's voice. L2's admission gate requires a quoted
span, which an *absence* can never have, so the 114 situations that describe the real inbox work
are held forever. L3's Admin corpus is written against facts nothing emits, so the one activated
domain cannot fire and the general/sales fallbacks render the cards instead. Result: **9 cards, of
which 3 are the same marketing email in the imperative voice, and the top one is `critical`.**

---

## 1. The dataset — what the tenant actually handed the system

| Source | Object | Count | What it is |
|---|---|---|---|
| gmail | `email_message` | 640 | one founder's fundraising/BD inbox |
| gmail | `email_attachment` | 159 | decks, agreements, brochures |
| gcal | `calendar_event` | 50 | meetings, most with external attendees |

### 1a · The Globe's own worked example is unreachable on this data

The Globe traces one example end to end: the AWS renewal — *contract PDF + finance rows + Slack
aside + calendar absence*. Of those four evidence classes this tenant has **one and a half**:

| Evidence class the example needs | On this tenant |
|---|---|
| Contract PDF (readable) | arrives (159 files) — **0 readable**, no OCR engine |
| Finance rows (spend trend) | **no connector** — `stripe`/`razorpay` not buildable |
| Slack aside (strategic signal) | **no connector** — `slack` registered, not buildable |
| Calendar absence | present (50 events) |

So the flagship demonstration in the design document cannot be produced by the shipped system on
the shipped connectors. That is not a bug report — it is the scope statement the roadmap has to
start from.

---

### 1b · The funnel, measured

```
849 captured → 225 emitted → 395 signals → 231 situations → 18 admitted → 112 candidates → 9 cards
```

| Step | Survived | Rate against the step above |
|---|---|---|
| captured → emitted | 225 / 849 | 27% |
| emitted → signals | 395 from 225 events | 1.8 per event |
| signals → situations | 231 | — |
| situations → **admitted to L3** | **18 / 231** | **8%** ⟵ narrowest point |
| admitted → candidates | 112 | 6 per situation |
| candidates → cards | 9 / 112 | **8%** |

The narrowest point is Layer 2 admission; the second is delivery. Between them sits a Layer 3 that
compiled 349 packages carrying one brain slice of four.

---

## 2. LAYER 1 · Knowledge — what went in, and why

### 2.1 · L1.1 Sources — expected 16 categories, reality 33 declared / 8 buildable / 2 connected

`capture/source_registry.SOURCES` declares **33 descriptors**. `buildable=True` on **8**:
`gmail`, `gcal`, `notion`, `gdrive`, `hubspot`, `postgres`, `database`, `mysql`. Connected here:
**2**. The registry is deliberately honest about the rest (`gsheets`, `gdocs`, `salesforce`,
`slack`, …) — they render as *coming soon*, not as clickable lies.

**Consequence, stated once and inherited by every later layer:** this is a *correspondence-only*
tenant. Every Admin surface whose evidence lives in a system of record — invoices, approvals,
filings, assets, access — has no substrate, at any layer, for reasons that have nothing to do
with reasoning quality.

### 2.2 · L1.3a Content pipeline — the total loss

Expected (Globe): OCR → normalize → chunk → entity/relationship extraction → embeddings → dedup.
Measured: **159 of 159 attachments produced no text.**

| Park code | Meaning | Files |
|---|---|---|
| `DOC-02` | unsupported file type | 119 |
| `DOC-06` | has pages, no OCR engine wired | 25 |
| `DOC-05` | attachment download failed | 15 |

`capture/gate/rules.content_integrity_rule` is doing exactly the right thing — it parks rather
than emitting an empty body, and it is *not bypassable by a whitelist* (a known investor's deck
must not sail through empty). The gap is upstream of it: no engine.

**What dies with it:** contract terms, renewal dates, notice periods, invoice amounts, PO
matching — i.e. the entire *document* half of Admin Intelligence, plus the Globe's Vendor/Contract
surface.

### 2.3 · L1.4 ESQE — the gate, rule by rule

**S1, deterministic (`capture/gate/rules.py`).** Whitelist first (`W-01` known sender 58 · `W-02`
starred 39 · `W-04` readable attachment 10), then the N-codes. 367 emails dropped: `N-02`
unsubscribe headers 198 · `N-06` Gmail Promotions 87 · `N-03` automated local-part 82 · `N-01`
machine ack 20 · `N-04` precedence 8.

**S2, the model gate (`capture/gate/relevance.py`).** One question per message, `drop` below
0.25, `park` at 0.25+. 63 dropped, 7 parked. It asks *"is this business mail?"* — and a
well-written funding-programme pitch **is** business mail.

**S4, ESQE relevance (`capture/esqe/relevance.py`).** Five deterministic rules in order, then
LLM-5. Measured: `known_counterparty` 58 · `structured_source` 50 · `bulk_headers` 46
(short-circuit) · `llm5_not_business` 2 · **`ambiguous_over_budget` 69**.

Those 69 were never judged. `AMBIGUOUS_BUDGET_BP = 1000` with `MIN_BUDGET_SAMPLE = 50`: above a
10% ambiguous share the unit alerts instead of spending, and the events **fail open at `unknown`
authority**. The doctrine is right — a high ambiguous share is a graph-coverage problem — but on
a three-week-old graph almost every sender is unknown, so the guard trips permanently and the one
component that could have asked *"is this a mass programme announcement?"* never ran.

### 2.4 · The structural hole — nobody asks who else got this mail

This is the root of "spam kaise ghus gaya", and it is not a tuning question.

* `capture/connectors/composio.py:302,519` captures **To and Cc** in full.
* `capture/landing/pg_repository.py:83` persists them as `source_events.recipients`.
* Consumers of that column: `semantic/extractor.py` (prompt envelope),
  `esqe/publisher.py` (record), `context/document_register.py`, `context/support_situations.py`.

**No gate, no scorer, no situation rule reads the fan-out.** `grep -rn "\.recipients"` returns
those four and nothing else. There is no `audience_size`, no `addressed_to_me`, no
`one_to_many` anywhere in `capture/`. A message sent to one person and a message sent to four
hundred are, to every decision in this pipeline, the same message.

And the ladders do not compensate:

| Ladder | Value for a cold external stranger |
|---|---|
| `RUNG_AUTHORITY_BP[EXTERNAL]` | 5000 / 10000 |
| `RUNG_AUTHORITY_BP[UNKNOWN]` | 3000 / 10000 |
| `ENTITY_CRITICALITY_BP[FIRST_SEEN]` | 2000 / 10000 |

So an unknown marketing sender scores mid-band on authority and low-but-nonzero on criticality —
never near zero. The fix is one derived column and one term, not a model.

### 2.5 · What L1 published, and why nothing scored high

395 signals across 11 of 14 types (`deadline_stated` 131 · `relationship_change` 49 ·
`opportunity_signal` 46 · `commitment_made` 44 · …), **359 (91%) carrying a verified evidence
span**. 68 refused by the tenant's floor (`DEFAULT_FLOOR_BP = 2500`).

Ceiling: **4,640 bp of 10,000.** `IMPORTANCE_WEIGHTS_V1` gives money the largest weight (3000) and
this inbox carries almost no amounts, so every score is decided by deadline proximity, authority
and criticality alone — and criticality is `FIRST_SEEN` (2000) for nearly every counterparty on a
three-week-old graph. **A whole tenant living in the lower half of the scale is a distribution
problem, not a scoring bug**, but it means the 2500 floor does most of the sorting.

### 2.6 · Verdict on Layer 1 — did it make bad structured data?

**No. The extractor was right.** On the email that became the top card it produced:

```
actor       : "HealthX Elevate program"
action      : "provide fundraising opportunities through direct engagement with
               healthcare leaders, investors, and potential collaborators…"
beneficiary : "selected applicants"
due         : "30th August 2026"
```

It correctly attributed the promise **away from the tenant**. L1's three real failures are
different in kind: **absence** (no documents readable), **blindness** (no fan-out feature) and
**compression** (every score in the lower half of the scale).

---

## 3. LAYER 2 · Context — what it made of it

### 3.1 · Groups: expected vs present

| Globe group | Expected | In code | Note |
|---|---|---|---|
| L2.1 Context Graph | 8 views | present as `graph_nodes` / `graph_facts` / `graph_edges` + `projections.py` | views are queries, not 8 modules — fine |
| L2.2 Graph Engines | 8 components | `graph_store`, `identity`, `merge`, `canon`, `lifecycle/*`, `derived` | present |
| L2.3 Cross-Correlation | 8 correlators | **4 named**: `correlation.py` (tool/entity), `correlation_timeline.py`, `correlation_dependency.py`, `correlation_resource.py` | cross-user / cross-conversation / cross-domain / cross-organization exist only as behaviour inside the anchor logic, not as named units |
| L2.4 Context Quality | 8 components | **4 modules**: `quality/{missing,lens,epoch,inference}.py` + `validate/confidence.py`, `validate/conflict.py` | conflict + confidence live in `capture/validate`, one layer down |
| L2.5/2.6 Situation engine | 9 components | `situations.py`, `situation_bso.py`, `situation_publisher.py`, `outreach_situations.py`, `support_situations.py`, `periodic.py` | present |

### 3.2 · What 395 signals became

Graph: **252 nodes · 2,350 facts · 245 edges.** Situations: **231**, dominated by two types —
`awaiting_response` 41 and `first_response_overdue` 40 (74 + 40 = **114** counting held rows).

### 3.3 · The admission gate — 18 admit, 202 hold

`context/situation_publisher._preflight` (line 217) holds on six reasons. One is conditional
(`qes_required`); five are unconditional: no verified span, open conflict, unresolved identity,
insufficient coverage, receipt-less pattern.

| Held for | Count |
|---|---|
| `qes_required` + `verified_evidence_required` | **184** |
| `conflict_open` | 17 |
| `conflict_open` + `identity_review_required` | 1 |

### 3.4 · FAILING UNIT #1 — `commitment_overdue` never reads the owner

The graph stored ownership **correctly**:

```
graph_edges:  sunil.s@sanchiconnect.tech  --owns-->  commitment "provide fundraising opportunities…"
```

Then three units in a row lose it:

1. `context/pipeline._resolve_subject` (line 452) — if the extracted `actor` string is not a
   resolvable identity in that email's entity map, it **falls back to the sender**. Here that is
   right by luck; it is wrong the moment a third party is named.
2. `context/outreach_situations.read_overdue_commitments` (line ~231) — builds a finding for
   **every** commitment node whose `commitment.due_at` has passed. It writes
   `("commitment.owed_to", name, "string")` and **never asks who owns it**.
3. `packs/general_v1.py:146` renders it:
   `"Deliver {action} to {entity} today"` / `"{days}d overdue — you promised this"`.

**So a promise the incubator made TO the founder is rendered as a promise the founder owes THEM,
in the imperative voice, at `critical` urgency.** Three of the nine cards are this one email.

### 3.5 · FAILING UNIT #2 — absence-shaped situations can never be admitted

`awaiting_response` and `first_response_overdue` are built from a thread's **silence**. The
finding *is* that nobody wrote back. There is no sentence to quote, so `verified_evidence_required`
holds every one of them, on every tenant, for ever. **114 situations — the two commonest types in
any inbox — cannot reach Layer 3 by construction.**

The rule is right for a *claim* and wrong for an *absence*. Globe Rule 04 ("evidence travels with
every claim") is being enforced faithfully; the class it was written for just does not include
silence.

### 3.6 · The 50 calendar events produced zero meeting situations

Two reasons, both deliberate, and together they close the Globe's Scheduling/Preparation surface:

* `context/correlation.ANCHOR_PRIORITY` = `deal → anchoring kinds → subscription →
  product_account → company → person`. **A meeting is not an anchor** — `context/structured.py`
  states it: *"a meeting is not a situation — it is evidence within"* the counterparty's
  situation. So calendar events become facts on relationship situations, never cards of their own.
* `domain_spec.py:456` declares `meeting_follow_through` needing `meeting.recap_sent`, and the
  comment says it plainly: **that fact has no writer.**

---

## 4. LAYER 3 · Domain Expertise

### 4.1 · The compiler is complete

All nine Globe components exist as modules under `packs/compiler/`: `capability_resolver`,
`object_resolver`, `brain_resolver`, `knowledge_retriever`, `context_adapter`,
`evidence_aggregator`, `expertise_builder`, `expertise_publisher`, `domain_compiler`.
**349 packages** were compiled over **130 situations**.

### 4.2 · One brain of four speaks

Every one of the 349 packages carries capabilities and **zero** behaviour entries, org rules and
adaptive preferences. Three named faults (`L3_V2_BUILD_RECORD.md` §5.1):

1. `brain_subject_keys` — the selector binding a situation to its brain entries — had no writer;
2. a Behaviour subject is `behavior:<metric>:<node_id>` while a situation's entity ids are email
   addresses, so the two vocabularies never intersect;
3. the Adaptive brain writes `temporary_memories`; the reader selects only `learned_brain_entries`.

**Status correction vs the funnel doc:** fault (1) is now fixed in code —
`context/situation_bso.gather_brain_subject_keys` (line 790) exists and is called from
`reason/domain_shadow.py:651`. The 349 measured packages predate that commit. Faults (2) and (3)
are open.

### 4.3 · The deeper one — the Admin corpus is written against facts nothing emits

`Domain Expertise/_schema/vocabulary.yaml` splits the world into `substrate` (what the engine
really writes) and `planned_substrate` (what the corpus wishes existed):

| | substrate (real) | planned (unfireable) |
|---|---|---|
| L2 situation types | 26 | **40** |
| fact paths | 136 | **70** |
| observation kinds | 51 | **65** |
| baselines | 2 | **7** |

Now cross that against each domain's authored capabilities:

| Domain | Capability files | Fact paths used that EXIST | Fact paths that are PLANNED-ONLY | Situation types planned-only |
|---|---|---|---|---|
| **Admin** | 201 | 38 | **20** | **20** |
| Sales | 156 | 21 | **0** | 2 |
| Customer Support | 167 | 27 | 24 | 12 |

**This is the single most important line in this document.** The Sales corpus is
substrate-aligned — it asks for facts the engine actually writes. The Admin corpus asks for
`approval.state`, `filing.due_at`, `invoice.amount`, `asset.custodian`, `document.review_due_at`,
`contract.end_at` and 14 more that **nothing in the engine emits**, plus 20 situation types
(`filing_due`, `auto_renewal_imminent`, `access_orphaned`, `invoice_mismatch`, …) that **nothing
mints**.

So on a tenant where `admin` is the only activated domain, the Admin lane is structurally silent,
and `general_v1`'s relationship hygiene renders the cards instead. That is not a mis-tuning — it
is a knowledge base pointed at a substrate that does not exist yet.

### 4.4 · `admin_v1` carries no rules, on purpose

`packs/admin_v1.py` is 128 lines against `sales_v1.py`'s 712, with `"rules": []` and
`"plays": {}`. Its own docstring gives the three reasons, and the third is the one above:
*"Everything that is genuinely ADMIN-native … rests on facts Layer 2 does not write."* The pack
grants authority and declares vocabulary. It does not pretend to reason.

---

## 5. LAYER 4 · Reasoning

### 5.1 · All 17 units exist

`reason/reasoners/` carries every one of the Globe's 17: context, timeline, dependency,
constraint, risk, opportunity, impact, priority, confidence, tradeoff, resource, scheduling, cost,
policy, alternative, validation, recommendation. Orchestrator, evidence layer and a single
`decision_maker` are present as specified. **Layer 4 is the most faithfully built layer in the
system.**

### 5.2 · Why 16 of 33 runs deferred

`DEFAULT_CONFIDENCE_FLOOR_BP = 4_500` (`reason/decision_maker.py:108`). Measured: decisions at
5000, deferrals at 2300–3300. The binding input is Layer 2's per-axis situation confidence, taken
as a **ceiling** (`min`, never a raise): on a subject known from one email and one source,
`evidence_score(event_count=1, source_count=1) = 33` → ceiling 3300 → the floor refuses.

**That is the guard working.** An engine that speaks confidently about a single unconfirmed email
is exactly what the floor exists to stop. The deferrals are a Layer 1/2 coverage symptom
surfacing at Layer 4.

### 5.3 · The formula moves, but a third of it is constant

`contracts/reasoning.RANKING_WEIGHTS_V2` = `importance 2500 · impact 2000 · urgency 2000 ·
success 1500 · effort 1000 · risk 1000`. It resolved **41 distinct utilities across 106
candidates** — so it is genuinely discriminating, unlike the v1 constant it replaced. But
`impact`, `risk` and `opportunity` are still known constants: **4,000 of 10,000 basis points not
discriminating.**

### 5.4 · The play mismatch is a Layer 3 symptom, not a Layer 4 bug

The highest utilities on this tenant come from **sales** plays
(`usage_triggered_upsell` 6643, `adjacent_problem_cross_sell` 6545, `renewal_starts_at_day_one`
6475) on a tenant where only **admin** is switched on. Read §4.3 again: the sales corpus is the
only substrate-aligned one, so it is the only one that can score. Ranking is reporting the
knowledge base's shape accurately.

---

## 6. LAYERS 5 / 5.2 / 6 — executive, delivery, learning

| Globe expectation | Reality |
|---|---|
| L5 Executive, 11 units, plan + watch loop | `executive/` carries 23 modules — the most complete non-reasoning layer |
| L5.2, 11 delivery units | `deliver/units.UNITS` registers all 11. `email` is `engine_ready=False`. `channels/` implements **Slack only** — every other push channel reports `no_adapter` |
| Globe's flagship surfaces: desktop card, inline Gmail card, mobile push | **no client exists** for any of the three. `in_app`/`dashboard` are pull surfaces the dashboard renders |
| L6, 11 learning units | all 11 present in `feedback/units.py` (10 `unit_*` + `validate_learning`) |
| L6 closes the loop into L3 | cannot, while three of four brain slices are empty (§4.2) |

Delivery outcome: **9 cards — 1 critical queued, 5 standard queued, 3 standard expired.**
A third of the tenant's output expired before anyone saw it.

---

## 7. Why the output looks weird — the four-mechanism chain

```
(1) L1 has no fan-out feature      →  mass outreach enters as ordinary business mail
(2) L1 budget guard trips at 10%   →  69 events skip the ONE check that could catch it
(3) L2 loses the owns edge         →  their promise is rendered in the founder's voice
(4) L2 blocks absence situations   →  114 real items never compete for the same slots
(5) L3 admin corpus unfireable     →  general_v1 hygiene copy renders what is left
                                    ─────────────────────────────────────────────────
                                    9 cards · 3 of them one marketing email · top = critical
```

The important part is **(4) multiplied by (1)**. Spam surviving would be tolerable if the real
work were also arriving — it would rank below it. What actually happened is that the genuine
inbox work was held at the gate while the marketing mail sailed through, so the noise is not
merely present, it is **over-represented by construction**.

### 7.1 · Chain of custody for the top card

| Layer | What it did | Right? |
|---|---|---|
| L1 S1 gate | passed — no N-code matched; Gmail itself said `CATEGORY_PERSONAL` | right by its own rules, blind to mass outreach |
| L1 S2 model gate | kept at 0.75, *"named person sharing substantive business insight"* | right — it IS business mail |
| L1 extraction | `actor = HealthX Elevate program` | **right** |
| L1 ESQE | kept at unknown authority, LLM-5 skipped on budget | the one check that could have caught it, skipped |
| L2 graph | `sanchiconnect --owns--> commitment` | **right** |
| L2 situation | `commitment_overdue` built without reading the owner | **wrong** |
| L3 | compiled the admin corpus for it | as configured |
| L4 | ranked it top, `critical` | correct given the situation it was handed |
| Card | *"Deliver … NOW"*, *"you promised this"* | **wrong — the voice assumes the tenant owes it** |

**Two lines of code would have prevented the wrong card**, and neither is in the model.

---

## 8. The failing-unit register

| # | `layer.group.unit` | Expected (Globe) | Actual | Size | Fix |
|---|---|---|---|---|---|
| 1 | `l2.outreach.read_overdue_commitments` + `packs.general_v1` template | a promise is attributed to its owner | owner never read; imperative copy | 3 of 9 cards | read the `owns` edge; branch the copy |
| 2 | `l2.situation_publisher._preflight` | evidence travels with every claim | an absence can never carry a span | 114 situations | typed-absence receipt, or cite the anchor's last inbound span |
| 3 | *(missing unit)* `l1.esqe.audience_fanout` | — (the Globe never specified it) | `recipients` captured, read by nobody | all mass mail | derive `audience_size`; add a term to ALG-17 and a rule to S1 |
| 4 | `l1.content.ocr` | documents become retrievable text | no engine in the image | 159 of 159 files | deploy the built image + `GENIOS_ENABLE_OCR` |
| 5 | `l3.corpus.admin` | domain knowledge fires on real facts | 20 planned-only facts, 20 planned-only situation types | the whole Admin lane | either write the L2 producers, or re-author the corpus onto substrate |
| 6 | `l1.esqe.relevance` budget guard | LLM-5 judges the ambiguous | trips permanently on a young graph | 69 events | raise the budget for cold tenants, or seed the graph first |
| 7 | `l3.compiler.runtime_brains` | four brains merge | one speaks | 349 packages | subject-vocabulary bridge + union `temporary_memories` |
| 8 | `l4.decision_maker` constants | six discriminating components | `impact`/`risk`/`opportunity` constant | 4000 bp | wire the three to real measurements |
| 9 | `l5_2.channels` | 11 delivery surfaces | 1 adapter (Slack); no desktop/Gmail/mobile client | 3 cards expired unseen | build one client, or lean on the dashboard pull surface |
| 10 | `l1.content.pipeline` sources | 16 categories | 8 buildable, 2 connected | every system-of-record surface | connector roadmap = product roadmap |

---

## 9. The 15 Admin surfaces — what the Globe claims vs what shipped

The Globe scores 6 surfaces as fully reachable on Gmail + Calendar. Measured on this tenant:

| # | Surface | Globe | Measured | Blocking unit |
|---|---|---|---|---|
| 01 | Commitment | full | **fires, wrong voice** | #1 above |
| 02 | Follow-up / Relationship | full | **blocked at admission** | #2 |
| 03 | Deadline | partial | 131 signals, no chains | #4 (documents) |
| 04 | Scheduling / Meeting prep | full | **0 situations** | meeting is not an anchor; `meeting.recap_sent` has no writer |
| 05 | Decision debt | partial | 24 signals, no situation type | no producer |
| 06 | Ownership | partial | none | no ownership facts |
| 07 | Founder bottleneck | full | none | `approval.*` is planned-only |
| 08–12 | Coordination · Process · Doc integrity · Vendor · Financial | no / partial | none | connectors + OCR |
| 13 | Goal / Progress | partial | none | no stated goal as data |
| 14 | Opportunity | full | 16 situations, **2 admitted** | #2 |
| 15 | Risk | no | none | as designed |

**Honest count: of 15 claimed and 6 promised, one and a half are actually shipping cards** — and
the one that ships, ships in the wrong voice. That is the sentence the Globe HTML should carry
instead of the "6 fully reachable" row.

---

## 10. What to do, in order

**P0 · Ownership (#1).** Read the `owns` edge in `read_overdue_commitments`; branch the copy in
`general_v1`. Smallest diff in this document, removes the worst card in the product.

**P1 · Fan-out (#3).** Derive `audience_size` from the `recipients` column already stored, add an
S1 rule for a large external fan-out with no prior relationship, and a term to ALG-17. This is the
missing unit the Globe never specified and the reason "promotional mail passes".

**P2 · Absence receipts (#2).** Unblocks 114 situations — the two commonest types in any inbox.
Until this lands, Follow-up Intelligence does not exist as a product.

**P3 · OCR (#4).** The image is built. Deploy, flip the env, and 159 parked files drain
themselves.

**P4 · Corpus vs substrate (#5).** Decide, explicitly: either write the L2 producers for
`approval.*`, `filing.*`, `invoice.*`, `asset.*`, or re-author the Admin corpus onto the 136 fact
paths that exist. Also switch `sales` on for this tenant now — it is a founder's fundraising
inbox and the sales corpus is the substrate-aligned one.

**P5 · Re-measure.** `python scripts/pipeline_funnel_report.py --org <org>` after each. Every
number in this file came from that command or from `grep` over the repository.

---

## 11. Corrections the Globe (expected side) should absorb

1. **"6 surfaces fully reachable on two connectors"** → one and a half, measured. §9.
2. **The audience-fan-out unit is missing from the architecture**, not just from the code. No
   layer in the Globe owns the question *"was this addressed to me or blasted to a list?"* §2.4.
3. **Rule 04 needs an absence clause.** As written it makes silence unpublishable, and silence is
   the most common finding in an inbox. §3.5.
4. **Domain knowledge needs a substrate contract.** A capability that reads a fact with no writer
   should fail authoring, not compile silently into a package that can never fire. §4.3.
5. **The worked example (AWS renewal) needs a connector precondition.** It requires finance and
   chat sources that are not buildable today. §1a.
