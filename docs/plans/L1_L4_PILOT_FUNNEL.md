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

---

## 8. WHY — the rule behind every group, and the case that proves it

Counts say *what* happened. This section says *why*, rule by rule, and traces one real email all
the way through so the reasoning is checkable rather than asserted.

### 8.0 The case: one email, seven stages

From `sunil.s@sanchiconnect.tech`, subject *"something that's been on my mind about healthcare
startups"* — cold marketing outreach for the **HealthX Elevate** programme. It produced the
tenant's **top three cards**, including the only `critical` one. Its full trace:

| Stage | Verdict | Why, in the code |
|---|---|---|
| landing | pass | new `dedup_key`, visibility derivable from participants |
| preprocess | pass | prose, 1 protected span, language `en` |
| S0 | pass | in scope |
| **S1** | **pass, no whitelist** | **no N-code matched — see 8.1** |
| **S2 gate** | **pass, relevance 0.75** | model's own words: *"Named person sharing substantive business insight"* |
| s2_semantic_extraction | pass, T1, 19 claims, 13 spans | profile `email`, 1 model call |
| s4_esqe | pass, `ambiguous_over_budget` | LLM-5 was NOT called — budget guard; kept at unknown authority |
| emit | emit | lane P2, route `needs_extraction` |

### 8.1 L1 · S1 — why the noise rules did NOT fire on it

The gate is a table of predicates over `raw`. For this email each one was asked and each said no:

| Rule | Predicate (`capture/gate/rules.py`) | On this email |
|---|---|---|
| `N-09` | label `SPAM` / `TRASH` | labels were `IMPORTANT`, `CATEGORY_PERSONAL`, `INBOX` → **no** |
| `N-06` | label `CATEGORY_PROMOTIONS` | **Gmail itself filed it as PERSONAL** → no |
| `N-07` | label `CATEGORY_SOCIAL` | no |
| `N-01` | header `Auto-Submitted != no` | headers empty → no |
| `N-02` | `List-Unsubscribe` / `List-Id` / `Feedback-ID` | **no bulk headers at all** → no |
| `N-04` | `Precedence: bulk\|list\|junk` | no |
| `N-03` | `mailer-daemon\|bounces@\|postmaster@`, or an automated local-part (`no-reply`, `notify`, `newsletter`, `digest`, `mailer`, `marketing`, `alerts`) | sender is `sunil.s@` — **a named human** → no |
| `N-05` | out-of-office in the SUBJECT | no |
| `N-10` | empty body and no attachment | no |

**This is the answer to "why do some promotional emails pass".** The gate is deterministic and
looks only at labels, headers and the sender's local part. Cold outreach written by a person, from
a personal address, with no mailing-list headers, is **indistinguishable from real mail at S1** —
because at S1 there is nothing to distinguish it by. Gmail's own classifier, which is the one
signal that could have caught it, put it in `CATEGORY_PERSONAL`.

The 367 that WERE dropped had the markers this one lacked: 198 carried unsubscribe headers, 87
were labelled Promotions by Gmail, 82 came from `no-reply@`-shaped addresses.

**Why the whitelist matters too.** 107 of the 245 that passed S1 did so on a whitelist, which
skips every N-code:

| Code | Rule | Count |
|---|---|---|
| `W-01` | sender is already a person in the graph | 58 |
| `W-02` | Gmail `STARRED` | 39 |
| `W-04` | a READABLE document is attached (pdf/docx/xlsx/pptx) | 10 |
| — | no whitelist, simply matched no N-code | 138 |

### 8.2 L1 · S2 — the model gate, and what it is allowed to do

`capture/gate/relevance.py`. One question per message, scored 0–1. The rule:

```
verdict = "drop"  AND  relevance < 0.25   →  DROP   (63 events)
verdict = "drop"  AND  relevance >= 0.25  →  PARK   (7 events, recoverable)
anything else                             →  KEEP
```

Real verdicts from this run, in the model's own words:

| Model's reason | Score | Outcome |
|---|---|---|
| Named person sharing substantive business insight | 0.75 | keep ← *the HealthX email* |
| Live session invite with Zoom link, attendance expected | 0.75 – 0.80 | keep |
| Human confirming availability for scheduled meeting | 0.85 | keep |
| Canceled meeting notification, no action needed | 0.20 | drop |
| Automated event invitation, one-to-many broadcast | 0.20 | drop |
| Enrollment confirmation, automated receipt | 0.00 | drop |
| known sender | 0.90 | keep, **no model call spent** |

The gate is asking *"is this business mail?"* — and a well-written funding-programme pitch **is**
business mail. It is not asking *"is this addressed to me personally or blasted to a list?"*, and
nothing in the pipeline asks that question of prose.

### 8.3 L1 · S4 ESQE — five rules, and the budget guard that skipped 69

`capture/esqe/relevance.py`, in order; the first that matches wins:

| Rule | Verdict | Relevance bp |
|---|---|---|
| sender known in the graph | relevant | 9000 |
| `internal_kind` set (company canon) | relevant | 9500 |
| structured source (calendar, CRM) | relevant | 8000 |
| bulk headers present | **not** relevant | 500 |
| service account **and** zero typed claims | **not** relevant | 800 |
| *(no rule matched)* | → the model, LLM-5 | 6000 / 1000 |

Measured here: `known_counterparty` 58 · `structured_source` 50 · `bulk_headers` 46 (short-circuit)
· `llm5_not_business` 2 · **`ambiguous_over_budget` 69**.

Those 69 — including the HealthX email — were never judged by LLM-5 at all. The guard:

> above **10%** ambiguous share (`AMBIGUOUS_BUDGET_BP = 1000`, min sample 50) the unit **alerts
> instead of spending**, and the events fail OPEN at `unknown` authority.

The doctrine is that a high ambiguous share is a graph-coverage problem, not a relevance one. On a
tenant this new almost every sender is unknown, so the guard trips and the one component that
could have said *"this is a mass programme announcement"* never ran.

### 8.4 L1 · extraction — the model got it RIGHT

This is the part worth being precise about, because the failure is **not** the model's:

```
actor       : "HealthX Elevate program"
action      : "provide fundraising opportunities through direct engagement with
               healthcare leaders, investors, and potential collaborators…"
beneficiary : "selected applicants"
due         : "30th August 2026"
```

The extractor correctly identified the **programme** as the promiser and **applicants** as the
beneficiary. All four commitments in that email are attributed away from the tenant.

### 8.5 L1 · the floor — why nothing scored high

`DEFAULT_FLOOR_BP = 2500`, and this tenant has no `org_qualification_floors` row, so it runs on
the default. 68 signals fell under it (`relationship_change` 48, `commitment_made` 20).

The whole tenant tops out at **4,640 bp of 10,000**, because ALG-17's money term is the largest
weight (3,000) and this inbox carries almost no amounts — so every score is decided by deadline
proximity, actor authority and entity criticality alone, and `entity_criticality` is `first_seen`
(2,000 bp) for nearly every counterparty on a three-week-old graph.

### 8.6 L2 · admission — the two unconditional halves

`context/situation_publisher.decide_publication`. Two halves, and only one is conditional:

**Conditional (skipped when the tenant's L1 is not scoring):** `qes_required`.

**Unconditional, on every tenant:** no **verified evidence span** · an **open conflict** · an
**unresolved identity** · insufficient coverage · a receipt-less activated pattern.

Measured: 184 held for `qes_required + verified_evidence_required`, 17 for `conflict_open`, 1 for
`conflict_open + identity_review_required`.

**Why `awaiting_response` (74) and `first_response_overdue` (40) can NEVER pass.** Both situations
are built from a thread's SILENCE — the finding *is* that nobody wrote back. There is no sentence
to quote, so no verified span can exist, so the unconditional half holds every one of them, on
every tenant, for ever. The rule is right for a claim and wrong for an absence, and these are the
two commonest situation types in any inbox.

The three types that DO pass — `investor_relationship` (10), `relationship` (6), `opportunity` (2)
— are all built from something somebody actually wrote, so a span exists to carry.

### 8.7 L2 · the situation rule that mis-attributed the promise — **the quality bug**

The graph stored the ownership **correctly**:

```
graph_edges:  sunil.s@sanchiconnect.tech  --owns-->  commitment "provide fundraising opportunities…"
```

`context/pipeline.py:1238` resolves the promiser with:

```python
subj = _resolve_subject(cm.get("actor"), name_to_node, sender_node)

def _resolve_subject(name, name_to_node, fallback):
    if name and _norm(str(name)) in name_to_node:
        return name_to_node[_norm(str(name))]
    return fallback                      # ← the SENDER
```

`"HealthX Elevate program"` is not a resolvable identity in that email's entity map, so it falls
back to the sender — which happens to be right here, and is right only by luck: the fallback
assumes the sender is the promiser whenever the named actor cannot be resolved.

Then `context/outreach_situations.py:240-261` builds `commitment_overdue` for **every** commitment
node whose `commitment.due_at` has passed — it never asks who owns it:

```python
display_name = f"{name} — promise past due"
facts        = [... ("commitment.owed_to", name, "string") ...]
```

And `packs/general_v1.py:146` renders it:

```python
"fallback": {"headline": "Deliver {action} to {entity} today",
             "situation": "{days}d overdue — you promised this"}
```

**So a promise the incubator made TO the founder is rendered as a promise the founder owes THEM,
in the imperative voice, at `critical` urgency.** Three of the nine cards are this same email.
Every layer did what it was told; the ownership fact stops being read one hop before the sentence
that needs it.

### 8.8 L3 · what compiled, and why the brains are empty

`admin` is the only activated domain, and `shadow_compile` compiles a package **per admitted
situation** — 349 packages over 130 situations. Each carries 2–13 capabilities and **zero**
behaviour entries, org rules and adaptive preferences, because:

1. `brain_subject_keys` — the selector that binds a situation to its brain entries — **has no
   writer** anywhere in the engine;
2. a Behaviour subject is `behavior:<metric>:<node_id>` while a situation's entity ids are **email
   addresses**; the two vocabularies never intersect;
3. the Adaptive brain writes to `temporary_memories` and the reader selects only from
   `learned_brain_entries`.

So the Expert corpus speaks and the other three cannot. (`L3_V2_BUILD_RECORD.md` §5.1.)

### 8.9 L4 · why 16 of 33 runs deferred

Two gates in series.

**The confidence floor** — `DEFAULT_CONFIDENCE_FLOOR_BP = 4500`. Measured confidences were
2,300–3,300 on the deferrals and 5,000 on the decisions. The binding input is Layer 2's own
per-axis situation confidence, taken as a **ceiling** (`min`, never a raise): on a subject known
from one email and one source, `evidence_score(event_count=1, source_count=1) = 33`, so the
ceiling lands at 3,300 and the floor refuses. That is the guard working — an engine that speaks
confidently about a single unconfirmed email is what the floor exists to stop.

**The ranking formula** — six components, weights `importance 2500 · impact 2000 · urgency 2000 ·
success 1500 · effort 1000 · risk 1000`. It resolved **41 distinct utilities** across 106
candidates here, so the formula is moving. Three of its six components (`impact`, `risk`,
`opportunity`) are known constants — that is 4,000 of 10,000 basis points not discriminating.

### 8.10 The chain of custody for the top card, end to end

| Layer | What it did | Was it right? |
|---|---|---|
| L1 gate | passed — no N-code matched, Gmail said PERSONAL | **right by its own rules**, blind to mass outreach |
| L1 model gate | kept at 0.75, *"substantive business insight"* | right — it IS business mail |
| L1 extraction | `actor = HealthX Elevate program` | **right** |
| L1 ESQE | kept at unknown authority, LLM-5 skipped (budget) | the one check that could have caught it, skipped |
| L2 graph | `sanchiconnect --owns--> commitment` | **right** |
| L2 situation | `commitment_overdue` built without reading the owner | **wrong** |
| L3 | compiled the admin corpus for it | as configured |
| L4 | ranked it top, `critical` | correct given the situation it was handed |
| Card | *"Deliver … NOW"*, *"you promised this"* | **wrong — the voice assumes the tenant owes it** |

**Two lines of code would have prevented the wrong card**, and neither is in the model: the
situation rule reading the `owns` edge, and the card copy branching on who owns the promise.

---

## 9. The fix list, revised by this analysis

| # | Fix | Where | Why it is the fix |
|---|---|---|---|
| **1** | `commitment_overdue` must read the `owns` edge, and the copy must branch on it | `context/outreach_situations.py` + `packs/general_v1.py` | 3 of 9 cards are one marketing email rendered as the founder's own overdue promise |
| **2** | Absence-shaped situations need an absence receipt | `context/situation_publisher.py` | 114 situations can never be admitted while a quoted span is required for a silence |
| **3** | Raise the LLM-5 ambiguous budget, or seed the graph | `capture/esqe/relevance.py` | 69 events skipped the only check that asks "is this addressed to me or blasted to a list?" |
| **4** | Turn OCR on | deploy + env | 159 of 159 attachments unread |
| **5** | Teach `commitment.actor` to resolve to an identity, and stop defaulting to the sender | `context/pipeline._resolve_subject` | the fallback is right by luck here and wrong the moment a third party is named |
| **6** | Give the packages their brains | `packs/compiler/runtime_brains.py` | 349 packages, three empty slices |
| **7** | Switch `sales` on for this tenant | `activate_tenant.py --domains admin,sales` | the sales plays already produce the highest utilities here |
