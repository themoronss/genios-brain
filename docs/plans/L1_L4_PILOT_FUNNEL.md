# The first live L1→L4 run — every layer, every group, and what to fix

> **Created:** 2026-09-08 · **Status:** Active

**Purpose:** the measured result of the first end-to-end pilot on a real tenant — 849 captured
objects walked through Layers 1–4 and out to 9 cards — broken down by every group each layer
decides in, with the losses named and ranked. Every number is read from the tables the sweep
itself wrote (`scripts/pipeline_funnel_report.py --org <org>`), not re-run and not estimated.

**Tenant:** `org_e97e86f858ad48b2bbf64b8a` (Rohit Swerashi) · Gmail + Calendar · 12 Aug – 8 Sep
**Activation:** L1 semantic · L2 analytic + patterns · L3 `admin` · L4 `roster_v2` + `ranking_v2`

---

## 0. The funnel in one line

```
849 captured → 225 emitted → 395 signals → 231 situations → 18 admitted → 112 candidates → 9 cards
```

Read as survival rates, each against the stage above it:

| Step | Survived | Rate |
|---|---|---|
| captured → emitted | 225 / 849 | **27%** |
| emitted → signals published | 395 signals from 225 events | 1.8 per event |
| signals → situations | 231 | — |
| situations → **admitted to L3** | **18 / 231** | **8%** ⟵ *the narrowest point* |
| admitted → candidates | 112 | 6 per situation |
| candidates → cards | 9 / 112 | **8%** |

---

## 1. LAYER 1 · Capture

### 1a · What was pulled

| Source | Object | Count |
|---|---|---|
| gmail | email_message | 640 |
| gmail | email_attachment | 159 |
| gcal | calendar_event | 50 |

### 1b · Every gate decision, with its reason code

| Stage | Action | Reason | Events | % of landed |
|---|---|---|---|---|
| landing | pass | — | 849 | 100% |
| S0 | pass | — | 849 | 100% |
| preprocess | pass | — | 799 | 94% |
| **S1** | **pass** | — | **245** | **28%** |
| S1 | drop | `N-02` bulk / unsubscribe | 198 | 23% |
| S1 | park | `DOC-02` unsupported file | 119 | 14% |
| S1 | drop | `N-06` Gmail Promotions | 87 | 10% |
| S1 | drop | `N-03` no-reply sender | 82 | 9% |
| S1 | park | `DOC-06` OCR unavailable | 25 | 2% |
| S1 | drop | `N-01` machine ack | 20 | 2% |
| S1 | park | `DOC-05` fetch failed | 15 | 1% |
| S1 | drop | `N-04` bulk precedence | 8 | 0% |
| S1.5 | short_circuit | structured (calendar) | 50 | 5% |
| S2 | pass | — | 175 | 20% |
| S2 | drop | `llm_junk` | 63 | 7% |
| S2 | park | `llm_junk_unconfident` | 7 | 0% |
| **s2_semantic_extraction** | **pass** | — | **172** | **20%** |
| s2_semantic_extraction | park | `extraction_parse_failed` | 3 | 0% |
| s4_esqe | pass | `ambiguous_over_budget` | 69 | 8% |
| s4_esqe | pass | `known_counterparty` | 58 | 6% |
| s4_esqe | pass | `structured_source` | 50 | 5% |
| s4_esqe | short_circuit | `bulk_headers` | 46 | 5% |
| s4_esqe | short_circuit | `llm5_not_business` | 2 | 0% |
| triage → emit | emit | — | 225 | 26% |

### 1c · The same decisions, per source — which tool loses what

| Source | Action | Reason | Events |
|---|---|---|---|
| **gcal** | emit | — | **50 (100%)** |
| gmail | drop | `N-02` | 198 |
| **gmail** | **emit** | — | **175 (27%)** |
| gmail | park | `DOC-02` | 119 |
| gmail | drop | `N-06` | 87 |
| gmail | drop | `N-03` | 82 |
| gmail | drop | `llm_junk` | 63 |
| gmail | park | `DOC-06` | 25 |
| gmail | drop | `N-01` | 20 |
| gmail | park | `DOC-05` | 15 |
| gmail | drop | `N-04` | 8 |
| gmail | park | `llm_junk_unconfident` | 7 |
| gmail | park | `extraction_parse_failed` | 3 |

**Calendar passes at 100%; Gmail at 27%.**

### 1d · Parked — held, not lost (all `pending`)

| Code | Meaning | Count |
|---|---|---|
| `DOC-02` | unsupported file type | 119 |
| `DOC-06` | has pages, no OCR engine | 25 |
| `DOC-05` | attachment download failed | 15 |
| `llm_junk_unconfident` | model called it junk, not confidently | 7 |
| `extraction_parse_failed` | model returned unparseable JSON | 3 |

**159 of 159 attachments produced no text.**

### 1e · Signals published — 395, by type

| Signal type | Count | min bp | max bp | With verified span |
|---|---|---|---|---|
| deadline_stated | 131 | 1180 | 3870 | 131 |
| relationship_change | 49 | 880 | 1240 | 48 |
| opportunity_signal | 46 | 1040 | 4440 | 41 |
| commitment_made | 44 | 1000 | 4160 | 41 |
| commitment_due | 25 | 2700 | 3800 | 25 |
| decision_pending | 24 | 1120 | 3480 | 15 |
| financial_obligation | 22 | 1760 | 4560 | 21 |
| contract_renewal | 21 | 1600 | 4640 | 16 |
| approval_requested | 17 | 1240 | 3920 | 11 |
| decision_made | 13 | 920 | 3600 | 7 |
| risk_flagged | 3 | 1760 | 3760 | 3 |

**359 of 395 (91%) carry a verified evidence span.** 11 of the 14 signal types fired.

### 1f · Refused by the tenant's floor (2500 bp)

| Signal type | Dropped | Floor |
|---|---|---|
| relationship_change | 48 | 2500 |
| commitment_made | 20 | 2500 |

Note: **every score is under 4700 bp** and the top of the range is `contract_renewal` at 4640.
Nothing in this tenant scored above the middle of the scale.

---

## 2. LAYER 2 · Context

### 2a · The graph

| | Count |
|---|---|
| nodes | 252 |
| facts | 2,350 |
| edges | 245 |

### 2b · Situations by type — 231 total

| Type | active | dormant | resolved |
|---|---|---|---|
| awaiting_response | 41 | | |
| first_response_overdue | 40 | | |
| relationship | 29 | 26 | |
| investor_relationship | 24 | 3 | |
| ticket_aging | 17 | | 2 |
| opportunity | 16 | 9 | |
| deal | 7 | 3 | |
| commitment_overdue | 3 | | |
| partnership_company | | 2 | |
| queue_overloaded | 1 | | |

### 2c · The admission gate — **18 admit · 202 hold**

| Held for | Count |
|---|---|
| `qes_required` + `verified_evidence_required` | **184** |
| `conflict_open` | 17 |
| `conflict_open` + `identity_review_required` | 1 |

### 2d · Admission by situation type — **only three types get through**

| Situation type | Admitted | Held |
|---|---|---|
| investor_relationship | **10** | 14 |
| relationship | **6** | 23 |
| opportunity | **2** | 14 |
| **awaiting_response** | **0** | **74** |
| **first_response_overdue** | **0** | **40** |
| ticket_aging | 0 | 17 |
| deal | 0 | 7 |
| commitment_overdue | 0 | 6 |
| admin_period_review | 0 | 3 |
| support_period_review · queue_overloaded · investor_contact · pipeline_period_review | 0 | 1 each |

**114 situations of the two commonest types produced nothing.**

---

## 3. LAYER 3 · Expertise

| Domain | Switched on by | State |
|---|---|---|
| admin | harsh | **live** |
| sales · customer_support | — | off (compiled, not activated) |

**349 packages** over **130 situations**, 30 Aug – 8 Sep.

### 3c · What is inside the packages — the four brains

| capabilities | behaviour | org rules | adaptive | packages |
|---|---|---|---|---|
| 4 | **0** | **0** | **0** | 166 |
| 9 | **0** | **0** | **0** | 55 |
| 2 | 0 | 0 | 0 | 30 |
| 3 | 0 | 0 | 0 | 27 |
| 11 | 0 | 0 | 0 | 24 |
| 13 | 0 | 0 | 0 | 20 |
| 7 | 0 | 0 | 0 | 18 |
| 12 | 0 | 0 | 0 | 3 |

**Every package carries capabilities and nothing else.** Behaviour, organization rules and adaptive
preferences are empty on all 349 — the Expert brain speaks, the other three do not. This is the
open J5 defect recorded in `L3_V2_BUILD_RECORD.md` §5.1.

### 3d · Packs this tenant runs

| Pack | State | Version |
|---|---|---|
| sales | active | 1.13.0 |
| general | active | 1.4.0 |
| admin | active | 1.0.1 |
| customer_support | active | 1.0.1 |

---

## 4. LAYER 4 · Reasoning

### 4a · Runs — 33, all `completed`

### 4b · Outcome per run

| Outcome | Runs | confidence bp |
|---|---|---|
| **decision** | 17 | 5000 |
| **defer** | 16 | 2300 – 3300 |

**Just under half the runs defer** — below the 4500 confidence floor.

### 4c · Candidates by disposition

| Disposition | Count | min bp | max bp | Distinct values |
|---|---|---|---|---|
| eligible | 106 | 4200 | 6545 | 41 |
| eliminated | 6 | 6301 | 6643 | 6 |

The formula moves: **41 distinct utilities across 106 candidates**, not a constant.

### 4d · Which play produced them

| Play | Candidates | Best bp |
|---|---|---|
| `sales.pb.account_research.fifteen_minute_account_brief` | 15 | 6299 |
| `reply` | 11 | 4900 |
| `wait_unanswered_email` | 11 | 4900 |
| `sales.pb.investor_relations.reopen_after_a_pass` | 9 | 6366 |
| `wait_commitment_overdue` | 6 | 6300 |
| `deliver_commitment` | 6 | 6300 |
| `sales.pb.renewal.renewal_starts_at_day_one` | 5 | 6475 |
| `sales.pb.cross_sell.adjacent_problem_cross_sell` | 5 | 6545 |
| `sales.pb.upsell.usage_triggered_upsell` | 5 | 6643 |
| `sales.pb.churn_prevention.save_play_with_dignity` | 5 | 6482 |
| `sales.pb.onboarding.time_to_first_value_sprint` | 5 | 6475 |
| `sales.pb.customer_success.outcome_cadence_reviews` | 5 | 5947 |

Note the mismatch: the **sales** plays produce the highest utilities on a tenant where only the
**admin** corpus is switched on.

### 4e · Signals emitted — 6 open · 3 resolved

---

## 5. DELIVERY · 9 cards

| Urgency | State | Count | min score | max score |
|---|---|---|---|---|
| critical | queued | 1 | 63 | 63 |
| standard | queued | 5 | 42 | 49 |
| standard | expired | 3 | 42 | 50 |

| Score | Urgency | Headline |
|---|---|---|
| 63 | critical | Deliver fundraising opportunities to sanchiconnect.tech NOW |
| 50 | standard | Deliver mentorship guidance from expert mentors now |
| 50 | standard | Deliver fundraising opportunities to healthcare leaders |
| 49 | standard | Reply to Sehan Sanjula now |
| 48 | standard | Reply to Sunil about HealthX Elevate visibility |
| 44 | standard | Confirm your attendance for Evokoa's call |
| 43 | standard | Send Lalitha A R the product context materials |
| 42 | standard | Book time with Sal Stabler on her calendar link |
| 42 | standard | Reply to Manik about GeniOS demo access |

Each card is grounded: the top one carries `commitment.due_at = 2026-08-30` and
`commitment.action = "provide fundraising opportunities through direct engagement with healthcare
leaders, investors, and potential collaborators at the finale event"`, both sourced to Gmail.

---

## 6. Where the losses are, ranked

| # | Loss | Size | Layer | Why |
|---|---|---|---|---|
| **1** | `awaiting_response` + `first_response_overdue` produce **zero** admitted situations | **114 situations** | L2 | Both are built from a thread's SILENCE. A situation whose evidence is "nobody replied" has no quoted span to carry, so `verified_evidence_required` holds it every time. The rule is right in general and wrong for this class. |
| **2** | Every attachment unread | **159 files** | L1 | OCR is off and the image has no engine. `DOC-02` 119 + `DOC-06` 25 + `DOC-05` 15. |
| **3** | The four brains are empty on all 349 packages | **349 packages** | L3 | `brain_subject_keys` has no writer; the Behaviour subject vocabulary and the situation's entity ids never intersect; the Adaptive store is never read. (`L3_V2_BUILD_RECORD.md` §5.1) |
| **4** | Half the runs defer | **16 of 33** | L4 | Confidence 2300–3300 against a 4500 floor. On a tenant with 1–2 sources per subject, the L2 ceiling binds. |
| **5** | 367 emails dropped at S1 | **367** | L1 | `N-02` 198 · `N-06` 87 · `N-03` 82. Correct for newsletters; `N-06` is Gmail's own classifier and drops a first-time vendor's mail with it. |
| **6** | 69 events kept at unknown authority | 69 | L1 | `ambiguous_over_budget` — the LLM-5 relevance call was refused because the ambiguous share was over 10%. That is a graph-coverage symptom, not a relevance one. |
| **7** | No score above 4700 bp | all 395 | L1 | Every signal sits in the lower half of the importance scale, so the floor at 2500 does most of the sorting. |

---

## 7. What to do, in order

**P0 · Unblock the 114 held situations (loss #1).**
`awaiting_response` and `first_response_overdue` are absence-shaped: their evidence is that nothing
came back. Either the admission gate learns that an absence-typed situation cites its ANCHOR's last
inbound span rather than its own, or those types carry a typed-absence receipt. Until one of the
two lands, the two commonest situation types in any inbox cannot reach Layer 3.

**P1 · Turn OCR on (loss #2).** The image is built (`Dockerfile`); deploy, then
`GENIOS_ENABLE_OCR=true` + `GENIOS_OCR_ENABLED_ORGS`. The 159 parked files drain themselves.

**P2 · Give the packages their brains (loss #3).** The three faults are named in
`L3_V2_BUILD_RECORD.md` §5.1 with the fix sequence; the cheapest is teaching
`PostgresRuntimeBrains.snapshot` to union `temporary_memories`.

**P3 · Switch `sales` on for this tenant.** The sales plays already produce the highest utilities
here (4d) and this is a founder's fundraising inbox; the `admin` corpus is the wrong fit.
`python scripts/activate_tenant.py --org <org> --domains admin,sales --apply`

**P4 · Read the deferrals (loss #4)** before touching the floor. A floor that nothing trips and a
floor everything trips are both wrong; 16 of 33 is neither, so the question is whether those 16
SHOULD have decided.

**P5 · Re-measure.** `python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"`
after each of the above. Every number in this file came from that command.
