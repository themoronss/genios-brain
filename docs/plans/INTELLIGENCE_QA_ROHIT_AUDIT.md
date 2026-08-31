> **Created:** 2026-08-12 · **Status:** 🔵 Reference — historical audit, **largely remediated**. Read it for the root-cause reasoning, not as a fix list. Re-verified 2026-08-30.
> **Purpose:** Consolidated, code+data-grounded QA audit of the reasoning engine run against the design-partner's real org (Rohit Swerashi, `org_325a6e36e6bb4651a2a1e403`), covering the 8 analysis dimensions + 5 key checks. Root-cause grouped, severity-ranked, with a trial fix-priority. Every finding is traced to real rows and `file:line`.

# Intelligence QA — Rohit Org Audit (4-agent, grounded)

**Org:** `org_325a6e36e6bb4651a2a1e403` · **Connected:** Gmail + Calendar only · **Data:** 483 nodes (person 306 / meeting 140 / company 26 / commitment 11), 699 edges, 29 open signals, 30 cards, packs sales `1.9.0` + general `1.1.2`. Read-only audit; nothing modified.

## Headline verdict
The **engine plumbing is production-clean.** Every layer boundary contract holds on real rows, **29/29 open signals pass the full delivery-authority predicate**, cards are all linked, and there are **no silent drops** (12,665 runs → 1,802 candidates → 202 decisions → 30 signals, every non-emit reason-coded). This is **not a code/compatibility problem.**

The problem is **feasibility + quality on thin data.** Of 29 open signals, **~4 are cleanly actionable** (real external people, ball genuinely on us, fresh); ~7–8 map to a real live loop if rendering is fixed; the remaining ~21 are self/bot noise, duplicate second-cards, or stale "reply now" on 3-week-dead threads. We sell **sales intelligence**; on Gmail+Calendar-only data the engine can currently only tell the founder to answer emails and send meeting recaps.

---

## Root-cause map (all findings grouped)

### RC1 — L1/L2 extraction is thin → deep intelligence cannot fire  🔴 CRITICAL
The single biggest hole. Rules are correct; the facts they AND against don't exist.
- **No `deal` node type / `deal.status` = 0 rows.** 7 sales rules (`stalled_deal`, `single_threaded_deal`, `competitor_in_live_deal`, `cooling_deal`, `deal_sentiment_negative`, `deal_health` composite) compare `deal.status='open'` — structurally dead. `runner.py:634,645` (`if nd.node_type=='deal'` never true). L2 instead puts `deal.stage` as free-text prose ("nearing $2k MRR", "rejected") on 6–10 **person** nodes, which no rule reads. `packs/sales_v1.py:86,132,141`.
- **Deep-sales obs vocabulary never extracted (0 rows each):** budget_approved, objection_price, verbal_yes, pricing_discussed, security_review_started, champion_change, budget_freeze, discount_pressure, legal_review, competitor. → 9 more rules can never match. `_OBS_CANON` (`context/pipeline.py:113`) maps synonyms but nothing upstream emits them. Near-miss: `next_step_agreed` ×15 exists but `verbal_yes_not_closed` wants `verbal_yes`.
- **`ball_in_court='us'` only 4.6% of persons (14/306); any `ball_in_court` 12% (37/306); `thread.last_inbound` 6.5% (20/306).** Every high-intent obs that DOES exist (demo_requested 2, contract_requested 1, objection 2, proposal_sent 2) sits on a node with **0** `ball=us` → gated out. Confirms the memory ~9% coverage gap.
- **Net:** ~15/21 sales rules structurally un-fireable → output = **26 hygiene / 4 sales**, and the 2 sales reason_codes that fired (`timeline_slip`, `closed_lost_risk`) are the only two with **no** `ball` gate.

**Fix:** (i) L2 must mint `deal` nodes + `thread.ball_in_court`/`last_inbound`/`last_outbound` + fine-grained obs from email threads far more often (this is the body-truncation/thread-state extraction gap already in memory); (ii) relax the hard `ball_in_court='us'` conjunct on high-intent obs rules — a `demo_requested`/`contract_requested` is worth surfacing even when the ball is ambiguous.

### RC2 — Scoring is blind → ranking is meaningless  🔴 CRITICAL
`S = C·(0.45U + 0.35I + 0.20R)`. On this data:
- **Impact I is a constant:** `i_floor=55, scope=deal_linked` (`general_v1.py:29`, `sales_v1.py:36`). No CRM → no `deal.value` → `impact()` returns **55 for every deal-linked signal, 0 for meeting_no_followup**. Verified: `score_inputs.I` is literally 55 or 0 across all 29.
- **Urgency U is saturated:** U=**100 for 20 of 29** (any loop >3d old saturates the elapsed curve).
- So **80% of the weight (U+I) is constant**; only R (recency, 72h half-life) and C move. **Result: score ranks "how recent," not "how important."** A 2-day unanswered email from an unknown (56) outranks an 8-day-stalled real deal (44).
- **Consequence:** all 29 sit at **42–56 = 100% "standard" band.** Nothing reaches push (70) or interrupt (85) → with `push_band=high`/`interrupt_band=critical` (`sales_v1.py:56-57`), **the entire L5 proactive/delivery tier is dormant by score ceiling** — no config error.

**Fix:** derive a **proxy Impact** from counterparty signals (VC domain, title=CEO/founder, thread depth, company size) instead of a flat floor; recalibrate the U curve so it doesn't saturate at 3 days; add hysteresis around the gate boundary (signals sit exactly at s_min=42).

### RC3 — No identity / relationship discrimination  🔴 CRITICAL
- **Self/internal filtering is DEAD — `org_seats` is EMPTY.** `context/runner.py:51` derives the internal-exclusion set purely from `org_seats`; 0 rows → `internal_emails=frozenset()` → guards at `pipeline.py:539,609` exclude nobody. So `invite@thegenios.com` (GeniOS's **own** invite bot, relevance 0.10) fired the org's **3rd-highest** signal ("Reply now"); `ceo@thegenios.com` etc. live as external counterparties; Rohit's own alt identity `rohitswerashi@moronss.com` is a separate signal-eligible node (self-fragmentation). **NOTE (verified 2026-08-12):** do NOT name-match "rohit" — of the same-first-name nodes, `rohit@crescerelabs.com` (CEO, Crescere Labs) and `rohit2115maurya@gmail.com` (Rohit *Maurya*) are **different real people**, `rohit@cyberstanc.com` unknown; only the connected account + verified-same-identity aliases are self. Blanket name-match would silence real prospects. None of these carry an open signal today → latent. **Zero-day trap:** a trial org connecting a personal Gmail (as Rohit did) gets **no** internal filtering → self/colleague noise floods the queue.
- **Investors treated as sales deals.** 100% of `closed_lost_risk` (Zeropearl VC, Antler) are **investors who passed on funding**, not lost customers → wrong `defend_position` "draft competitive" play. Aditya (IIMA Ventures) same family via `timeline_slip`. No relationship-type discriminator separates investor/collaborator from prospect/customer → sales rules leak onto non-sales contacts (~10% of signals). Vini (a GeniOS co-builder) queued as a lead.
- **Human identity fragmented:** exact-email only; same human across addresses never merged (`vatsashah45@gmail.com` vs `@calendly.com`; Rohit ×5). Latent double-fire.

**Fix:** seed `org_seats`/internal set on day-1 from the connected account's own address + observed same-domain senders + own-domain (`@thegenios.com`); add a **relationship-type** attribute (prospect / customer / investor / collaborator / internal) driven by thread content + domain, and gate sales plays on it; add entity-resolution beyond exact email.

### RC4 — Signal hygiene: hollow content, duplicates, staleness, meeting↔person split  🟠 HIGH
- **`commitment_overdue` fabricates promises.** `commitment.action` is **never written** (pipeline writes `commitment.text/status/due_at` only, `pipeline.py:585-595`) yet the rule's `evidence_fields` cite it → every card says "you promised this — deliver today" with **null promise content**. Worse, the extractor captures the **counterparty's** reschedule lines ("could we push the call to Monday?") as Rohit's commitments via latest-wins (`pipeline.py:596`) → "you promised this today" is frequently the other side's request. `general_v1.py:35`.
- **Duplicate loops as separate cards.** 6 people hold 2 cards each for one silence (adityad, zeropearl, errorcore, nelieo, nitesh, vini) → **12 of 29 cards = 6 real loops.** No cross-reason dedup per subject. Inflates the "29" headline ~20%.
- **Stale signals not reconciled.** Aditya & Antler already replied (`last_outbound=2026-08-11`, `ball=them`) yet "22d overdue" / "Save the deal now" still fire. **No fulfillment/close detection** — overdue counters climb forever; `commitment.action=null` on every commitment subject.
- **Meeting ↔ person/deal never unify.** All `meeting_no_followup` subjects are the **meeting node**; no edge links a meeting to its thread/deal (edge types: attended 603, corresponded_with 52, works_at 33, owns 11 — none topical). Reticle recap is addressed to **"Mr Rohit Swerashi"** (booking name = the owner himself) while the real prospects `hardik@`/`divyanshu@reticle.sh` carry **0 signals**. No external-attendee guard → internal cohort sessions ("GAM 1 - Group 2 | Launchpad 30") fire. Recipient resolves to meeting **title** → "Send GeniOS x Engramme (Meet) a recap."

**Fix:** cross-reason dedup per subject before card-build; write `commitment.action` + correct actor-ownership (whose promise); reconcile against latest thread state (ball flip / outbound → close the loop); external-attendee guard + meeting→thread→person linking so recaps address the counterparty.

### RC5 — Process/perf + latent traps  🟡 MED
- **823 suppression-log writes for 29 surfaced cards** (710 `legacy_score_gate_failed`, 86 cooldown, 27 budget). Per-candidate audit writes dominate → matches the known "24k audit writes / O(nodes) round-trips" bottleneck. Skip/batch non-firing + gate-failed audit writes.
- **Per-node reasoning over 483 nodes**, most never fire → pre-filter to nodes with an active `thread.*`/`commitment.*`/`meeting.*` fact before entering the reasoning loop.
- **Budget cap is per-run, not per-day.** `budget_per_user_day:15` (`sales_v1.py:28`) — two runs in <9h each emitted ~15 → 29 surfaced. Gate on a real per-day window; and the cap silently dropped a `closed_lost_risk rank 0/1` real deal.
- **`graph_facts.status` vocab is `active`/`superseded`/`historical`, never `current`.** Runner filters `status='active'` correctly, but any consumer/analytics/L6 assuming `status='current'` reads **0 rows.** Grep the codebase for `status='current'` on graph_facts.
- **Short TTL churn:** commitment cards expire in **2 days** (`min(+7d, decision_expires_at)`), then hit 48–72h cooldown → good loops flicker between runs. Confirm the re-emit sweep covers the shortest TTL.
- **`closed_lost_risk`/`timeline_slip` fire on a SINGLE evidence field** (`thread.last_inbound` only, `sales_v1.py:270,243`) despite card_builder's "≥2 evidence (Law 2)" claim; don't cite the obs (e.g. `deal.stage=rejected`) that actually triggered them.
- **Headline uses raw email / meeting-title as a name** ("Save the theresa.hoffmann@antler.co deal now") — person attrs `{}`, no display-name resolution. Reads like a bug to a paying user.
- **`intro_followup` under-yields:** 14 eligible nodes (introduction obs + last_inbound, no followup_sent), **0 emitted** — needs a runtime trace; a warm-intro follow-up is high value.

---

## Key-check answers (the 5 the partner asked for)
1. **5 founder case studies:** 1 GOOD (Nitesh/DevDash — 2d unanswered, ball on Rohit), 1 GOOD-but-misaddressed (Reticle recap → self), 3 WEAK/NOISE (Zeropearl VC-as-lost-deal, Aditya stale+investor, Vini collaborator-as-lead).
2. **5 cross-domain cases:** only 1 of 5 correlates (the trivial in-thread case, CD-4 Nitesh); email↔calendar and sales↔general both fragment.
3. **L1 & L4 feasibility:** L4 (reason) sound; L1/L2 capture is the constraint — deal facts 0%, ball_in_court 4.6%, last_inbound 6.5%; meeting facts 100%.
4. **Intelligence quality:** ~4/29 cleanly actionable; ~5 pure noise/self, ~6 duplicate second-cards, ~8 stale/dead.
5. **Cross-correlation:** meeting↔person never unify; investor≠customer not distinguished; self ×5 nodes; VC/collaborator queued as leads.

---

## Progress (2026-08-13)
- ✅ **RC4-partial — commitment.action populated** ([pipeline.py](../../genios_engine/context/pipeline.py) person-level dual-write). Card now renders the real promise instead of hollow "you promised this". Firing unchanged (trigger stays `commitment.due_at`). 48 relevant tests pass.
- ✅ **RC4-partial — staleness guard on obs-only sales rules.** New backward-compatible engine operator `missing_ok` ([engine.py](../../genios_engine/reason/engine.py) `_eval_condition`) → added `{ball_in_court != them, missing_ok}` to `timeline_slip` + `closed_lost_risk` (sales_v1 → **1.10.0**). Proven on Rohit's data: suppresses exactly the 2 genuinely-stale signals (Antler `theresa@antler.co`, Aditya `adityad@iima.ac.in` — both ball=them = we already replied), KEEPS the 2 active (ball=us) + all null-ball nodes (no coverage loss). Full suite 1341 pass, 0 new failures.
- Also fixed 4 pre-existing stale pack-test assertions (version/gate values from commit 489a188).
- **NOT deployed/committed.** commitment.action applies on next capture; the stale-guard needs sales_v1 **1.10.0 promoted** to Rohit (currently pinned to 1.9.0) + a re-reason to take visible effect.
- Pre-existing (not from this work, left as-is): test_migrate (needs live PG), test_executive_authority (SQL-join asserts), test_corpus_can_fire unfireable-list (revived by the 489a188 gate lowering).

## Fix priority for the trial (recommended order)
The three that read as "this is wrong" on first glance — fix before any demo:
1. **RC3a — seed `org_seats` / self-exclusion** (kills invite@thegenios, self-recap, own-alias noise). Smallest change, biggest credibility win.
2. **RC4 — dedup + commitment.action + staleness reconcile** (removes ~6 duplicate cards, stops "you promised this"/"save the deal" on already-answered threads).
3. **RC3b — relationship-type discriminator** (stops investors→lost-deal, collaborators→leads).
4. **RC2 — proxy Impact + U recalibration** (makes ranking mean something; wakes the dormant push/interrupt tier).
5. **RC1 — L2 deal-node + thread-state + obs extraction** (the deep-sales unlock; largest effort, unblocks ~15 dormant rules).
6. **RC5 — perf/audit-write batching + per-day budget + status/TTL traps** (scale + polish).

## Invariants respected
Read-only audit. No packs promoted, no rules changed, no user credits touched (only `/v1/intelligence/query` charges). All findings honor the engine's layer topology (capture→…→feedback) and the "L2 = scorer not filter" / "store-don't-delete" rules — several findings (RC3a, RC4) are about restoring guards that are silently no-op'ing, not adding drop-gates.

## Re-verification — 2026-08-30

The five root causes, against code today:

| RC | Then | Now |
|---|---|---|
| **RC1** L1/L2 extraction thin → ~15/21 sales rules structurally dead (`deal.status`=0, `ball_in_court=us` 4.6%) | The deal lane was unreachable | **LARGELY CLOSED.** The `deal` node is minted (`context/pipeline.py:863`) with both edges (`:871-873`); `deal.status` normalisation and a backfill exist (`context/backfill.py:162`, `:299`). Sales routing is 43 of 47. The extraction prompt now carries envelope, direction and roles (`context/extract/prompt.py:14,17,34`). |
| **RC2** Impact constant → 42-56 score compression → L5 proactive tier dormant | `I` was a constant | **CLOSED.** `reason/scoring.py:72 impact()` is a real function of `(value, p90, linked_deal)`. |
| **RC3** self-filter dead (`org_seats` empty) + investors-as-lost-deals + self ×5 nodes | `org_seats` had one manual writer | **ADDRESSED.** `platform/seats.py` writes seats and backfills orgs that have none; `platform/receipts.py:66` asserts the table is non-empty as a release check; `context/runner.py:65`, `context/extract/envelope.py:40` and `context/support_situations.py:515,1246` all stop trusting `org_seats` alone and fall back for self-serve tenants. `bd25b31` records that both live orgs now hold an active admin seat. |
| **RC4** hollow commitments / dupes / staleness / meeting↔person split | | **PARTIAL.** The meeting lane opened (`1881133`), commitment reachability was fixed (`bd25b31` — 203 of 203 commitments had been unremindable because nobody owned them), and the overloaded contact-signal name was split (`0eaf94e`). **Still open:** there is no commitment backfill — `commitment` does not appear in `context/backfill.py`, so the historical rows this audit counted are unrepaired. Tracked as L2-3 in `L2_L3_GAP_ANALYSIS.md`. |
| **RC5** perf — ~1000 per-node reads, 823 audit writes per 29 cards | | **PARTIAL.** P1 bulk reads, P2 no-op audit skip, P4 L2 parallel extraction and P5 L1 paging all shipped. **P2b (batch the audit writes) and P3 (skip nodes that cannot fire) are still open** — see `PERFORMANCE_HARDENING.md` in the workspace, which was re-verified the same day. |

Marked Reference rather than Active because the two things that genuinely survive from it — the commitment backfill and the reasoning-write batching — are each owned by a live plan of their own. Every number in the body is a 2026-08-12 measurement against `org_325a6e36e6bb4651a2a1e403` and has not been re-taken.
