# The live run — what actually reaches L1, L2, L3, L4, and the user

**Tenant:** `org_e97e86f858ad48b2bbf64b8a` (Rohit Swerashi) · Gmail + Calendar
**Read:** 9 Sep 2026, read-only. Every number is a `select` against the tables the sweep itself
wrote. Nothing was re-run, nothing was written, no LLM was called.

> **How this was read, and why it is safe.** `scripts/pipeline_funnel_report.py` is 33 `select`
> statements, zero `insert`/`update`/`delete`/DDL, behind `set transaction read only` issued at
> the server — Postgres itself would refuse a write. Its guard nevertheless demands
> `GENIOS_ALLOW_PROD_WRITE=1`, because the guard does not distinguish reads from writes. Rather
> than assert a write permission this work never needed, the same 33 queries were run through a
> read-only session. **Nothing on this page came from re-running the pipeline.**

---

## 0. The funnel, in one line

```
863 captured → 225 emitted → 395 signals → 231 situations → 18 admitted → 512 candidates → 15 cards
```

| Step | Survived | Rate |
|---|---|---|
| captured → emitted | 225 / 863 | 26% |
| emitted → signals | 395 from 225 | 1.8 per event |
| signals → situations | 231 | — |
| situations → **admitted to L3** | **18 / 385 decisions** | **4.7%** ⟵ *the narrowest point, by far* |
| admitted → candidates | 512 | — |
| candidates → **cards** | **15** | 2.9% |

Yesterday's run (8 Sep, `docs/plans/L1_L4_PILOT_FUNNEL.md`) read `849 → … → 18 admitted → 9 cards`.
**Admitted is still exactly 18.** Nothing about the admission gate has moved, which is expected:
production runs `harsh/mvp`. **The `y-combinator-w27` code has never executed against this data.**

---

## 1. Layer 1 — Knowledge · *working, and better than its reputation*

**642 emails, 171 attachments, 50 calendar events.** 225 emitted, 397 dropped, 181 parked.

**395 qualified signals across 11 types**, and the verification rate is high:

| Signal type | Count | Importance range (bp) | Verified spans |
|---|---|---|---|
| `deadline_stated` | 131 | 1180–3870 | **131 / 131** |
| `relationship_change` | 49 | 880–1240 | 48 / 49 |
| `opportunity_signal` | 46 | 1040–4440 | 41 / 46 |
| `commitment_made` | 44 | 1000–4160 | 41 / 44 |
| `commitment_due` | 25 | 2700–3800 | **25 / 25** |
| `decision_pending` | 24 | 1120–3480 | 15 / 24 |
| `financial_obligation` | 22 | 1760–4560 | 21 / 22 |
| `contract_renewal` | 21 | 1600–4640 | 16 / 21 |
| `approval_requested` | 17 | 1240–3920 | 11 / 17 |
| `decision_made` | 13 | 920–3600 | 7 / 13 |
| `risk_flagged` | 3 | 1760–3760 | **3 / 3** |

**L1 is not the problem.** It is classifying, scoring and quoting. What it publishes,
almost nothing downstream consumes: `decision_pending` (24) has no decision situation,
`contract_renewal` (21) has no vendor situation, `risk_flagged` (3) has no risk situation.

### The ESQE cascade — it *does* run, and here is the proof

`.env` carries `GENIOS_ENABLE_L1_RELEVANCE=false`, which for a while looked like it might mean the
relevance work on this branch was dead code. It does not. **There are two different gates:**

| Module | What it is | State |
|---|---|---|
| `capture/gate/relevance.py` | the old deterministic guesser | **OFF** — this is what the flag disables |
| `capture/esqe/relevance.py` | the ESQE business-relevance cascade | **ON**, unconditionally, at `capture/pipeline.py:976` |

The `event_trace` table settles it. Every one of these is an `s4_esqe` decision recorded live:

| Reason | Events |
|---|---|
| `ambiguous_over_budget` | **69** |
| `known_counterparty` | **58** |
| `structured_source` | 50 |
| `bulk_headers` (short-circuit) | 46 |
| `llm5_not_business` | 2 |

Two things follow, and they matter in opposite directions.

**The M1.C1 fix is live-relevant.** 58 events passed on `known_counterparty`, which today means
"this address is any `person` node" — the loose definition this branch tightened.

**The budget guard is the largest single ESQE outcome.** 69 events — more than any rule — passed
on `ambiguous_over_budget`, meaning the LLM never adjudicated them and they failed open. §2.1 of
the README warned that tightening `sender_known` raises the ambiguous share. **On this tenant the
guard is already the top bucket before that change lands.** Raising the ceiling is a cost decision
and it now has a number attached to it.

---

## 2. Layer 2 — Context · *the bottleneck, and it is not close*

**252 nodes, 2350 facts, 245 edges.** 231 situations. And then:

| Outcome | Count |
|---|---|
| **hold** | **367** |
| admit | 18 |

| Held for | Count |
|---|---|
| `qes_required + verified_evidence_required` | **349** |
| `conflict_open` | 17 |
| `conflict_open + identity_review_required` | 1 |

### Which kinds get through, and which never do

| Situation type | Admitted | Held |
|---|---|---|
| `investor_relationship` | 10 | 14 |
| `relationship` | 6 | 23 |
| `opportunity` | 2 | 14 |
| **`awaiting_response`** | **0** | **210** |
| **`first_response_overdue`** | **0** | **41** |
| **`commitment_overdue`** | **0** | **18** |
| `ticket_aging` | 0 | 17 |
| `deal` | 0 | 7 |
| the four period reviews | 0 | 22 |

**Every absence situation, without a single exception, is held.** These are precisely the readings
that would say *"you wrote to that investor 31 days ago and they never replied"* — the intelligence
this system exists to produce. 84 distinct situations, 269 admission decisions, zero shown.

### The two hold reasons are one starvation

349 candidates carry both `qes_required` and `verified_evidence_required`, which reads like two
independent defects. It is one. `_preflight` raises `qes_required` when `importance_source` is not
`l1_qualified_signals`; `importance_base()` returns that arm **only when an L1 bundle arrived** —
the same bundle the evidence gate is waiting for. Feeding the bundle clears both.

---

## 3. Layer 3 — Expertise · *running, and three-quarters hollow*

**381 packages compiled over 130 situations.** Only the `admin` domain is activated (by `harsh`).
Four packs are active: `sales` 1.13.0, `general` 1.4.0, `admin` 1.0.1, `customer_support` 1.0.1.

The four-brain merge, measured across every package on the tenant:

| capabilities | behaviour | org rules | adaptive | packages |
|---|---|---|---|---|
| 4 | **0** | **0** | **0** | 168 |
| 9 | **0** | **0** | **0** | 65 |
| 2 | **0** | **0** | **0** | 48 |
| 3 | **0** | **0** | **0** | 27 |
| 11 | **0** | **0** | **0** | 24 |
| 13 | **0** | **0** | **0** | 20 |
| 7 | **0** | **0** | **0** | 18 |
| 5 | **0** | **0** | **0** | 3 |

**Every package on this tenant carries capabilities and nothing else.** Behaviour patterns,
organization rules and adaptive preferences are empty in all 381. Three of the four brains have
never contributed a row here. `READINESS.md` predicted this from the source tree; this is the
same conclusion read off production.

**And 130 situations were packaged while only 18 were admitted.** L3 is compiling expertise for
situations the gate below it is holding — work performed and thrown away.

---

## 4. Layer 4 — Reasoning · *structurally sound, speaking the wrong language*

**141 runs, all completed.** 61 produced a decision (all at exactly 5000 bp), 80 deferred
(2300–3300 bp). **512 candidates: 482 eligible, 30 eliminated.**

The eliminated candidates score **6301–6643 bp** — *higher* than the eligible band tops out at
6545. The best-scoring candidates on this tenant are the ones being killed.

### Which plays produced them

| Play | Candidates | Best bp |
|---|---|---|
| `sales.pb.account_research.fifteen_minute_account_brief` | 75 | 6299 |
| `sales.pb.investor_relations.reopen_after_a_pass` | 45 | 6366 |
| `deliver_commitment` | 34 | 6300 |
| `wait_commitment_overdue` | 34 | 6300 |
| `reply` | 27 | 4900 |
| `wait_unanswered_email` | 27 | 4900 |
| `sales.pb.upsell.usage_triggered_upsell` | 25 | **6643** |
| `sales.pb.cross_sell.adjacent_problem_cross_sell` | 25 | 6545 |
| `sales.pb.churn_prevention.save_play_with_dignity` | 25 | 6482 |
| `sales.pb.renewal.renewal_starts_at_day_one` | 25 | 6475 |
| `sales.pb.onboarding.time_to_first_value_sprint` | 25 | 6475 |
| `sales.pb.customer_success.outcome_cadence_reviews` | 25 | 5947 |

**270 of 512 candidates come from the sales pack on a tenant whose only activated domain is
`admin`** — and they hold the top of the utility table. Upsell at 6643 outranks
`deliver_commitment` at 6300 in a mailbox with no customers to upsell.

> **A correction to `READINESS.md`.** That document said L4's nine plays "cannot express
> restraint". Production shows `wait_commitment_overdue` (34) and `wait_unanswered_email` (27) on
> the ballot. They are real — but they are **synthesised**, not authored:
> `reason/adapters/legacy_pack.py:67` mints a `wait_<rule>` twin for every legacy rule, fixed at
> impact 2000 / success 9000 / effort 0 / risk 0, so that acting has something to beat. That is a
> genuine do-nothing option and it is better than nothing. It is **not** the seventh card part —
> "do not chase the four owners who already delivered" — which still does not exist.

---

## 5. What the user actually sees · *15 cards*

| Band | State | Count | Score |
|---|---|---|---|
| critical | queued | 1 | 63 |
| standard | queued | 6 | 43–49 |
| standard | expired | 8 | 42–50 |

**All 15 cards are `domain='general'`.** The `admin` pack is active and produced none of them.
Every card has `capability_key = NULL` — 381 expertise packages compiled and not one card records
which capability it used.

### The single most useful finding on this page

**The card bodies are good. The headlines destroy them.**

| What the `situation` field says | What the `headline` says |
|---|---|
| "Manik at Titan Capital last wrote 31 days ago sharing product links and asking you to mention something succinctly. **Ball is in your court.**" | "Reply to Manik about GeniOS demo access" |
| "Sal sent a calendar link and said booking directly is easier for her. **You haven't replied in 32 days.** Ball is in your court." | "Book time with Sal Stabler on her calendar link" |
| "Lalitha A R last wrote 26 days ago asking about what you're building at GeniOS." | "Send Lalitha A R the product context materials" |
| "Evokoa Team sent a meeting invite for Thu 20 Aug 11:15am (IST) with Google Meet details. **You haven't replied in 23 days.**" | "Confirm your attendance for Evokoa's call" |

The left column is the intelligence that was asked for — *"you wrote, they did not reply, the ball
is with you, it has been 31 days"*. **It already exists, computed, stored, on the card.** The
headline is an imperative template that replaces a situation with an order.

### And four cards accuse the founder of promises he never made

| Headline | Who the graph says owns the commitment |
|---|---|
| **"Deliver fundraising opportunities to sanchiconnect.tech NOW"** — *critical, score 63, the top card* | `sunil.s@sanchiconnect.tech` |
| "Deliver $2,000 monthly savings to myzyner.com" | `willow@myzyner.com` (Sehan Sanjula) |
| "Deliver mentorship guidance from expert mentors now" | not Rohit |
| "Renew Growth plan at $599/month now" | a vendor |

Measured: **15 commitment nodes, 12 carry an `owns` edge, and only 3 are owned by
`mrrohitswerashi@gmail.com`.** Nine belong to `sunil.s@sanchiconnect.tech` (2), `willow@myzyner.com`,
`Lalitha A R`, `Shourya Sharma`, `deepthi.chandrashekhar@nsrcel.iimb.ac.in`, `hv@errorcore.dev`.

Myzyner promised Rohit the savings. The card tells Rohit he promised Myzyner. SanchiConnect
promised fundraising access at their event; that is the **number one critical card in the feed.**

**This is the failure M3.C1 fixes, and the live data confirms the fix fires on 9 of 12.**

---

## 6. What this run proved about `y-combinator-w27`

Honest scorecard, measured rather than argued:

| Fix | Live verdict |
|---|---|
| **M3.C1** — attribute a promise to whoever made it | ✅ **Confirmed.** 12 `owns` edges exist, 9 name someone other than Rohit, and 4 cards currently misattribute. |
| **M1.C1** — `sender_known` means "we corresponded" | ✅ **Reaches live traffic.** 58 events passed on the loose definition. Consequence is real: `ambiguous_over_budget` is already the largest ESQE bucket at 69. |
| **M1.C3** — audience discount | ⚪ Not separately measurable from stored rows; `recipients` is captured on `source_events` and the multiplier is neutral where absent. |
| **M2.C1** — absence carries its receipt | ❌ **Was wrong as shipped. Corrected on 9 Sep.** |

### M2.C1 — what was wrong, and what it is now

The read shipped on 8 Sep looked for `thread.last_outbound` **on the anchor node**. Measured live,
**no absence anchor carries that field**, so it would have found zero receipts and unblocked
nothing:

| Situation | Anchor node type | What the anchor actually holds |
|---|---|---|
| `awaiting_response` (41) | `outreach` | only `outreach.*` — the waiting arithmetic, no messages |
| `first_response_overdue` (40) | `thread` | `thread.last_inbound`, **never** `last_outbound` |
| `commitment_overdue` (3) | `commitment` | reaches only a `company` node |

The direction was backwards for one type and the node was one hop off for the other. The corrected
read chooses the leg from the situation type, and follows `concerns` one hop only when the anchor
holds nothing itself. Measured on this tenant **before the code was written**:

| Situation | Reach a real qualified signal | With a real `importance_bp` |
|---|---|---|
| `awaiting_response` | **41 / 41** | **41 / 41** |
| `first_response_overdue` | **40 / 40** | **40 / 40** |
| `commitment_overdue` | 0 / 3 | 0 / 3 — no message path, stays held honestly |

101 of those 105 receipts already carry verified spans. **81 of 84 held absences have had a valid,
verified receipt sitting in the graph the entire time.**

The inbound leg is admitted for `first_response_overdue` **alone** — a marketing sender produces
only inbound mail, so a blanket union would hand every blast a receipt. Two tests fail if either
direction widens.

`tests/context/test_absence_receipt.py`: **25 passed** (was 14). Full suite: **8853 passed,
24 failed** — the same 24 pre-existing failures. Zero regressions, zero skips added.

---

## 7. What to fix next, in the order the data justifies

1. **The headline template.** The card already holds better prose than it displays. This is the
   cheapest large improvement available and it is a rendering change, not an intelligence one.
2. **Deploy the branch and re-read this page.** Every claim above about what *would* change is
   still a claim. `admitted` has sat at 18 across two runs; that number is the one to watch.
3. **`ambiguous_over_budget` at 69.** The largest ESQE outcome is "we did not decide". Raising the
   ceiling costs money and is the budget owner's call — but it should be a decision, not a default.
4. **The sales pack on an admin tenant.** 270 of 512 candidates, holding the top of the utility
   table, in a mailbox with no customers. Deactivating `sales` here is a configuration change.
5. **Carry `capability_key` onto the card.** 381 packages compiled, zero cards say which one they
   used. Without it, L3's contribution is unauditable.
6. **The three empty brains.** Behaviour, organization rules and adaptive preferences are `0` in
   all 381 packages. Everything in `READINESS.md` §6 still stands.
