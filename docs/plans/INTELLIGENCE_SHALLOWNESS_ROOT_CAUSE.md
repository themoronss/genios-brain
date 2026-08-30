> **Created:** 2026-08-22 · **Status:** 🔵 Reference — historical audit, **substantially remediated**. Read it for the reasoning, not as a to-do list. Its open items were folded into `IMPLEMENTATION_PROGRAM.md` (2026-08-23) the next day. Re-verified 2026-08-30.
> **Purpose:** Code+data-grounded root-cause of why the app's suggestions read as "no intelligence" — why junk (`invite@thegenios.com`) surfaces, why dead rejections surface, and why the single most important live thread (Antler/Theresa) produces zero cards.
> **Method:** 10 parallel investigators over live Postgres (`org_e97e86f858ad48b2bbf64b8a`) + engine source → 78 findings → 18 adversarial refutation agents → 13 confirmed, 5 refuted/narrowed.
> **Scope:** ANALYSIS ONLY. No code was changed. Sibling of `INTELLIGENCE_QA_ROHIT_AUDIT.md` (2026-08-12) — several RCs there are re-confirmed here with exact failing clauses.

---

## 0. What the user actually sees (measured, not described)

Org `org_e97e86f858ad48b2bbf64b8a` (Rohit Swerashi), eval `2026-08-22 02:05`.

| Metric | Value |
|---|---|
| Signals / cards | 41 / 41 — but only **20 distinct subjects** (21 are dupes) |
| Distinct rules firing | **7 of 25** (`unanswered_email` 22, `commitment_overdue` 9, `closed_lost_risk` 4, `meeting_no_followup` 3, `objection_open` 1, `demo_requested` 1, `timeline_slip` 1) |
| Cards with an actual drafted body | **4 of 41** — 37 are `render_mode='raw_slot'`, `artifact->>'body' = ''` |
| Cards with zero evidence (`why=[]`) | 4 (the 4 top-ranked ones) |
| Impact term `I` | **55 on 38/41** cards (constant) |
| Urgency band | **`standard` on 41/41** |
| Score range | 42 – 60 |
| Observations read by any rule | **14.5%** (175 of 1208) |
| Inbound emails that reached the graph | **28%** (255 of 907) |
| Attachments parsed | **0** (286 parked, 106 "emitted" with ≤39 chars = filename only) |
| Honest hit rate | **12 of 41** signals land on a subject worth keeping; **0 of 41** cover 7 of the top-10 real priorities |

Verbatim cards being served:

```
Save the hello@forumvc.com deal now       | Loss signal — one last specific save      | why=[] | body=""
Book invite@thegenios.com's demo now      | They asked to see it — move fast          | body=""
Reply to boardy@boardy.ai now             | 3d since they wrote (expired) AND 7d (queued)
Deliver I'll be in PST starting this week | 12d overdue — you promised this
Handle lalithaar…'s objection now         | Raised severald ago — still unanswered
```

---

## 1. THE DEEPEST CAUSE

> **The engine never knows who the counterparty is, or which way the email went.**

Everything else is downstream of this.

- **No role model.** Enumerating every `"path"` in both packs yields **8 fact paths**, all channel mechanics (`thread.last_inbound`, `thread.ball_in_court`, `meeting.start_at`, `commitment.due_at`, `deal.status/value`). **Not one rule cites `role`, company, or counterparty type** — `grep -n 'role' sales_v1.py general_v1.py` returns nothing. Yet the graph holds 26 active `role` facts including *"Vice President, Investments"*, *"Seed Investments & Acceleration"*, *"Partner & Co-founder"*. The extractor captured who these people are; the rule layer never looks.
- **No direction.** `context/extract/prompt.py:10-13` hands the LLM `<<<MESSAGE>>>{content}<<<END MESSAGE>>>` — **no From, no To, no inbound/outbound marker**. And the observation schema has no actor (`prompt.py:36`), while `commitments` right above it *does* (`prompt.py:30`) — the designers knew, and omitted it exactly where the rules read.
- **Attribution defaults to the sender.** `context/pipeline.py:494` — `content_subject = canon_node or sender_node`.

**Consequence:** every `person` node is interchangeable to the rule engine, so *"someone wrote and you didn't reply"* is literally the deepest statement it can make. That is why 22 of 41 signals are `unanswered_email`.

---

## 2. Your three examples, mechanically

### 2a. `invite@thegenios.com` → "Book their demo now"

Four independent failures compose:

1. **Self-filter is dead.** `context/runner.py:55` sources internal identity from `org_seats` — **0 rows** for this org (also `org_members` 0, `workspace_accounts` 0). So `internal_set = frozenset()`, and every guard written against it is a no-op. L4's only self-exclusion is one string: `select lower(email) from orgs where id=:o` → `mrrohitswerashi@gmail.com` (`reason/runner.py:620`).
2. **No vendor-domain concept.** `grep -rn "thegenios" --include="*.py" genios_engine/` → **nothing**. GeniOS's own outbound is indistinguishable from a prospect.
3. **Direction-blind extraction.** The mail's body was *"as requested, here is the demo: https://demo.thegenios.com"* — i.e. **we are sending you a demo**. With no direction, the model tagged it `demo_requested` and the pipeline filed it on the sender.
4. **The empty self-set then wrote `thread.ball_in_court='us'`** on that node (`pipeline.py:552`), which is exactly `demo_requested`'s second condition (`sales_v1.py:253-258`).

The other `invite@thegenios.com` email's entire body is: *"Dear Rohit, The life is going to be changed for forever now."* → produced 2 more `unanswered_email` cards.

Bonus: because extraction is direction-blind, **Rohit's own signature block** (`role="Founder"`, `company="TheGENIOS"`) got written onto the vendor bot node.

### 2b. The 4 "Save the deal now" cards on dead rejections

`hello@forumvc.com`, `apply@surgeahead.com`, `aviral@ajuniorvc.com`, `hello@bharatkesuperfounders.com` — all **one-way rejection auto-mailers**. Their `closed_lost_mention` evidence is verbatim:

```
apply@surgeahead.com  → "we are unable to take your application forward for Surge"
aviral@ajuniorvc.com  → "it could not proceed to the next stage"
hello@forumvc.com     → "we won't be moving forward at this time"
```

The direction is **inverted**: Rohit is the applicant being rejected, not a vendor losing a customer. The pack has one word for it — `closed_lost_mention` — whose play is `defend_position` → artifact `draft_competitive`. The literal button on a VC's inbox reads **"Draft competitive"**.

Then three scoring bugs push them to the **top of the feed**:

- **`has_obs` ignores confidence.** `reason/engine.py:94-95` is bare kind-equality; `_bulk_load_obs` (`runner.py:181`) never even loads the `confidence` column. So `closed_lost_mention @ 0.040` == `@ 0.750`.
- **`missing_ok:True` rewards ignorance.** All four have **zero `thread.*` facts** (their mail was classed noise so the thread writer was skipped) → the guard `ball_in_court != them, missing_ok:True` waves them through.
- **Missing data scores HIGHER than present data.** When the urgency fact is absent: `ext_conf` falls back to `0.9` (`engine.py:194`) — *higher than the 0.85 a real email fact carries*; `_freshness(None)` returns `1.0`; `hrs = ... or 0.0` → `R = 100`. Result: `C=87, I=55, R=100, U=65 → S=60`, byte-identical on all four, **the highest score in the org**, produced entirely by absence of data.

### 2c. Antler / Theresa — why the real deal is invisible

The graph has it **correctly**: `status="rejected"`, `traction="has traction and good pipeline"`, `date="14 August"`, `thread.last_inbound=2026-08-07`, `thread.last_outbound=2026-08-13`, `ball_in_court="them"`, `closed_lost_mention @ 0.750`, `next_step_agreed @ 0.750`. Theresa's actual words: *"always happy to take a look and reconsider."*

Zero signals. **Zero suppression-log rows** — it never even produced a candidate. Five stacked reasons:

1. **The v1.10.0 staleness guard is the single silencing clause.** `sales_v1.py:272-277` — `{"path":"thread.ball_in_court","op":"!=","value":"them","missing_ok":True}`. Theresa's is `"them"` (because Rohit *replied*). Hand-evaluated all 21 person-scoped rules against her live facts: `closed_lost_risk` is the **only** one that passes its `has_obs` clause, and it dies here. **Having thread evidence is what disqualifies you.**
2. **The one rule that DOES match is dead engine-wide — a real bug.** `champion_quiet` (`ball='them'` AND `days_since ≥ max(10, 2.5×reply_cadence)`) matches Theresa (15.03d elapsed, threshold 10). But the L4 capability manifest deep-freezes rule config into `MappingProxyType` (`contracts/reasoning.py:60-64`), and `reason/engine.py:30` tests `isinstance(value, dict)` — **False for a mappingproxy**. So the baseline threshold is returned as a Mapping object, `_cmp(15.03, ">=", mappingproxy)` → `None` → `False`. **The rule can never fire, in any org.** Verified by in-process repro: raw ctx → `[True, True]`; through the adapter → `matched: False`. And because the outcome is `NO_ACTION` not `BLOCKED`, `runner.py:811` does `continue` with **no suppression row** — completely invisible in the audit trail. (Tests exercise `evaluate()` directly, not the adapter path — that's why CI is green.)
3. **Her half of the conversation was thrown away.** Every observation from Rohit's **outbound** re-pitch (6 obs incl. `closed_lost_mention @ 0.850`, `question`, `followup_sent`) landed on **his own node** — 237 obs / 112 facts — which `runner.py:631` then **self-excludes**. Org-wide: 44 outbound events → 234 observations, all discarded.
4. **A direct email from Theresa was hard-dropped at L1.** `evt_b5123f4ff85b44f688802be2` → `S1:drop/N-02` (`gate/rules.py:139` drops on a `List-Unsubscribe` header alone). Also `singapore-scouting@antler.co` (N-02) and `no-reply@antler.co` (N-01).
5. **The rejection landed on a dead-end node at 0.100 confidence.** `no-reply@antler.co` → typed `service` (a node type **no rule has scope for**), and because L2 judged the mail `noise_type='automated'`, its `closed_lost_mention` was written at **confidence 0.100** and the event **joined no correlation at all** (`pipeline.py:641`). The Antler arc also spans two Gmail threads that nothing joins.

Plus: her thread correlated as **`domain='support'`** — because the word `error` appears 4× **inside the legal disclaimer footer**, firing `capture/domain/hints.py:56`'s support regex. The LLM's own correct label — `["venture_capital","startup_funding"]` — was computed and discarded.

---

## 3. Why the copy has no intelligence

### 3a. The renderer is never shown the email

`deliver/card_builder.py:30-52` issues exactly **two** queries: `graph_nodes` + `graph_facts`. It never touches `graph_observations`, `graph_source_refs.evidence`, `source_events`, or `graph_edges`. The LLM is asked to write a thread-specific reply from ~5 typed key/value pairs.

Reproduced prompt for the live "Reply to maria@alystventures.com now" card — the entire tenant-specific payload:
```json
{"company":"Unstuck","focus":"traction and repeatable-revenue framework","role":"Partner & Co-founder",
 "thread.ball_in_court":"us","thread.last_inbound":"2026-08-11T17:17:53+00:00"}
```
What the DB holds one join away and never sends:
```
mention:person  | "Maria Exconde * Partner & Co-founder of Unstuck"
introduction    | "Re: Boardy Intro: Maria + Rohit"
positive_reply  | "Happy to hop on an intro call with you. Would love to know what you're building."
```

### 3b. The invention guard rejects any fluent sentence — 25 of 41 cards died here

`deliver/render.py:71-73` flags **any capitalised token** not in the corpus as a hallucinated name — and the corpus (`_corpus(facts, slots)`) is *the same 5 facts the model was given*. Direct repro with the repo's own functions and Maria's real facts:

```python
invention_ok('Hi Maria, Thanks for reaching out…')  → (False, 'name:Thanks')
invention_ok('Best regards, Rohit')                 → (False, 'name:Rohit')
invention_ok('I will send the deck Monday')         → (False, 'name:Monday')
```

Live count from `card_events.detail`: **`raw_slot|V-02` 25 · `raw_slot|V-01` 12 · `llm` 4**. And validation is all-or-nothing across headline+situation+artifact with **no retry and no regeneration ever** — `render_copy` has exactly one call site (`pipeline.py:100`), and pressing "Run Play" does not generate the missing draft. 41 `l5_render` LLM calls were paid for; 37 were discarded.

### 3c. The fallback is mad-libs

Of the 21 sales templates, **14 situation lines are 100% constant strings** keyed only to the rule id. The whole slot vocabulary is 7 values (`slots.py:63-71`), 4 of which collapse to generic words when missing (`"open"`, `"no value set"`, `"the commitment"`, `"several open items"`). The template literally never sees anything but the rule id and a name — which is why *"They asked to see it — move fast"* can be printed under GeniOS's own product address.

Two visible artifacts of this:
- **`"Raised severald ago"`** — `_CLOCK` (`slots.py:45-52`) has no entry for `objection_open`, so `days` is `None` and the sentinel `"several"` gets substituted into a `{days}d` slot.
- **`"Deliver I'll be in PST starting this weekend, let's find som"`** — the extractor emits a normalised `action` field; `pipeline.py:593` reads `evidence_text` instead and **`cm["action"]` is never read anywhere in the codebase**. So the commitment title is the counterparty's raw sentence, in *their* voice, framed as *your* overdue promise, then hard-sliced at 60 chars (`render.py:79` — contradicting its own docstring "never truncate, Law 3"). 11 of 41 headlines sit exactly on the cap.

### 3d. `why=[]` is structural

`reason/adapters/legacy_context.py:119-123` builds evidence **only** by looking up `rule.evidence_fields` in `context.facts` — `context.obs` is used for matching and never converted into an `EvidenceRef`. `closed_lost_risk` fires on `has_obs` but declares `evidence_fields: ["thread.last_inbound"]`, which those nodes don't have → `continue` → `why = []`. **Observations are structurally uncitable.** The maximum any card reaches is 2 items: a timestamp and the word `"us"`.

---

## 4. Why ranking is meaningless

- **`I` is a hardcoded constant.** `deal.value` has **0 rows in the entire database**. `scoring.py:80` → `base = 0.0` → `:83` `if linked_deal: i = max(floor_pct, i)` → the pack's `i_floor: 55`. And `linked_deal` is a **static per-rule boolean**, not a check that a deal exists. **35% of the score's weight is a fixed +1925bp offset** added identically to a newsletter and a term sheet.
- **`U` and `R` are the same clock read with opposite signs.** `engine.py:169` computes one `hrs`; `U` rises off it, `R` decays off it, weighted 45 and 20. For `unanswered_email`: `45U + 20R = 4500 − 604·e^(-d/3)` — moves between **4190 and 4500 across all time**. 65% of the weight self-cancels.
- **Corroboration counts connector names, not evidence.** `runner.py:93-95` → `count(distinct sr.source)`. The tenant has two sources ever (`gmail`, `gcal`), so **`src_count = 1` for all 998 active facts**. The `two:85` / `three_plus:100` rungs are unreachable by construction; `corr` is pinned at 0.60, capping `C ≤ 85` for every email rule.
- **The `high` band (70) is arithmetically unreachable.** Closed-form sweep over all 25 rules with this tenant's real fact properties: global max `S = 62`; every firing rule caps at ≤58. So `urgency_band='standard'` is a **compile-time constant**, and everything band-gated is pinned to its quietest setting forever — `deliver/pipeline.py:135` pushes only on `high/critical`; `executive/communication.py` defaults `push_band="high"`. **`delivery_outbox`, `delivery_events`, `executions` = 0 rows across all orgs.** The entire Layer 5.2 delivery control plane has never executed.
- **Ranking is reverse-chronological, wearing a priority costume.** All 17 `unanswered_email` score_blocks reconstruct exactly from one scalar `d` (days since last inbound): d = 3.73, 4.24, 5.77 … 30.10. 41 signals occupy 15 distinct scores; 14 cards' feed position is decided by `created_at` sweep order (`deliver/store.py:283`). And since `S` **decreases** with `d`, **ignoring something makes it rank lower**.
- Two rules are dead by arithmetic: `budget_freeze` (S_max 40) and `intro_followup` (S_max 38) are below `gate.s_min = 42` — `intro_followup` matched **20 times** in the last sweep and emitted **0**.

---

## 5. Why the same person appears twice with contradictory copy

- **A re-fire mints a new identity.** `runner.py:450-484` retires the old signal + card and `insert`s with `sid = new_id("sig")`. `cards_one_per_signal` is UNIQUE on `signal_id`, so a new signal always means a new `card_id`. **No code path ever updates `headline` or `situation`** — 17 grep hits on `update cards set`, all touching `state`/`snooze_until`/`resolved_at`.
- **`cooldown_hours` is overloaded as the decision TTL.** `adapters/legacy_pack.py:136` feeds it into `expiry_hours`; `decision_maker.py:409` makes it the authority window; `card_builder.py:147` clamps the card to it. So **card lifetime == suppression window exactly** — the moment one lapses the other unlocks. (`publication.py:48-52` explicitly documents these as different concepts; the adapter collapses them.) Side-effect: the org's queue was **empty for ~25 hours** before the Aug-21 run.
- **Elapsed-time strings are frozen at build time.** Same node, same unchanged fact: card built Aug-17 says *"3d since they wrote"*, card built Aug-21 says *"7d"*, truth today is 8d. Meanwhile the detail endpoint (`routes.py:2268`) recomputes freshness **live**, so one card can print "Latest info here is just now" above a frozen "7d since they wrote".
- **`/activity` has no gate.** `api/routes.py:1630` is literally `select headline, situation, urgency_band, created_at from cards where org_id=:o order by created_at desc limit :l` — no state, no expiry, no signal join. Every other card surface (`deliver/store.py:272`, `intelligence_routes.py:485`) applies the full authority predicate. The dashboard's `brain-activity-panel.tsx:95` requests limit 30, which spans back into the expired Aug-17 batch → **live card and dead predecessor in one scrollable list**.
- **Acting on a card gives zero suppression.** `_recent_signal` (`runner.py:320`) requires `status='open'`; pressing "wrong"/"done" sets `status='acted'` → the cooldown memory is erased *by the act of handling it*. The `and s.config_snapshot_id=:cfg` clause is a second erasure path: any pack/config change re-fires the entire book at once.

---

## 6. Input starvation

| Stage | Loss |
|---|---|
| `S1 drop N-02` (List-Unsubscribe header alone) | **370** — of which **209 are from people already in Rohit's graph** |
| `S1 drop N-06 / N-01 / N-04 / N-03` | 123 / 21 / 16 / 13 |
| `S2 drop llm_junk` | 109 |
| `S1 park DOC-02 / DOC-05` | 262 / 24 — **all `status='pending'`, no drain path exists** |
| Net | **652 of 907 emails dropped (72%)**, and dropped events retain **no payload at all** |

- Per-domain emitted/dropped: `accubate.app 1/47` · `fitt-iitd.in 0/42` · `sineiitb.org 0/29` · `ycombinator.com 0/10` · `antler.co 4/3`. **N-02 is not a newsletter filter here — it is a fundraising-pipeline filter**, because accelerator and application-platform mail is exactly what travels via ESPs.
- The W-01 whitelist meant to protect real correspondents is **bootstrap-circular**: `sender_known` = "already a person node" (`api/routes.py:121`). On a first backfill the graph is empty → nobody is known → the N-codes run destructively → the dropped people never become nodes. **The whitelist can only protect people it has already failed to protect.** And once admitted, a sender is trusted *forever* and skips the LLM junk gate entirely (`relevance.py:212`) — top W-01 beneficiaries are `boardy@boardy.ai` (36) and `hello@cal.com` (6); Theresa gets 4.
- **Zero document text has ever reached L2.** `enable_ocr: bool = False` (`config/py:84`) → every image-only PDF parks permanently, and the parked payload is a **stub with `body: ""`** — the bytes were never downloaded, so even `recover_parked` is theatre. Parked files include `GeniOS_Founder_Report.pdf`, `StartUp Launchpad Proposal.pdf`, and the NSRCEL mid-review rubric.
- **No quoted-reply / signature / disclaimer stripping** before extraction (`preprocess.py` does only language detection + PII masking). The Antler reconsideration message is 6054 chars of which ~700 is signal; the rest is calendar chrome and two verbatim copies of the confidentiality disclaimer — which is what fired the wrong domain hint.

---

## 7. Vocabulary is backwards in both directions

- **Observation kinds: CLOSED and wrong-domain.** ~30 fixed B2B-SaaS strings. There is no kind for *application submitted*, *application rejected*, **reconsideration offered**, *intro requested*, *term sheet*, *diligence*, *partner meeting*, *cohort decision*. So Antler's *"always happy to reconsider"* collapsed into generic `next_step_agreed`. Six rules require kinds the LLM emitted **zero** times (`verbal_yes`, `budget_approved`, `objection_price`, `security_review_started`, `champion_change`, `legal_review`). Meanwhile **`meeting_request` (183), `question` (83), `next_step_agreed` (27), `positive_reply` (34) are read by no rule at all** — the VP of Investments' direct question and a candidate's "send me the deck" both reduce to the same generic "Reply to X now" as a newsletter.
- **Fact fields: OPEN and unbounded.** `prompt.py:26` says `"field": "role|company|budget|deal.stage|..."` — three examples and an ellipsis. The LLM invented **268 distinct field names** in this org, **192 of them singletons**. Antler's rejection is stored under bare `status`, not `deal.status`. The pack's own `schema.fields` block is commented *"L2 extraction whitelist"* (`sales_v1.py:475`) and `registry.effective()` **drops it on the floor** — the only repo-wide consumers are tests and a display route.
- **Field drift is total.** Rules read `deal.status` / `deal.value` / `deal.last_inbound` — **0 rows anywhere in the database**. The bridge `deal_facts()` exists but `runner.py:645` gates it behind `if nd.node_type == "deal"`, and **no `deal` node type exists in the entire DB**. So 3 deal-scoped rules are filtered out before evaluation, 2 person-scoped ones fail their `neighbor_fact` check, and the `deal_health` composite starts from an empty select.

---

## 8. Domain misfit

- **There is no domain routing at all.** `packs/wiring.py:17-23` — `BUILTIN_PACKS = [SALES_V1, GENERAL_V1]`, `DEFAULT_PACK_ID = "sales"`. `runner.py:537` calls `ensure_default(registry, org_id)` on every sweep with the literal comment `# design-partner default: sales.v1`. **Nothing anywhere inspects the org to decide which domain applies.** The L3 domain compiler that could synthesize one is off (`config.py:89 use_domain_compiler: bool = False`; `expertise_packages` = 0 rows). The corpus covers Sales / Support / Admin — no fundraising.
- **`domain_hints` never reach pack selection.** Grep shows zero consumers under `reason/`. And the hint lexicon can't express fundraising anyway: `sales` = `deal|pricing|proposal|contract|quote|demo|budget|renewal`. 1300 of 1356 events carry no hint.
- **The system holds ZERO representation of what business this org is in.** `user_models` 0 · `learned_brain_entries` 0 · `temporary_memories` 0 · `knowledge_suggestions` 0 · `user_model_proposals` 0 · `domain_requests` 0 · `org_seats` 0 · `org_members` 0. `orgs` has no industry column; registration collects 4 fields; `orgs.role` is empty. The sales default isn't a bad default — **it's the only reachable state**.

---

## 9. The counterfactual — what should have surfaced

Reconstructed by decrypting `raw_payloads` (Fernet) over the last 30 days. Ranked by real consequence for a founder mid-raise, as of 2026-08-22:

| # | What | Engine | Gap type |
|---|---|---|---|
| T1 | **NSRCEL Launchpad mid-review, Mon 24-Aug 15:00 IST (2 days out)** — mandatory assignment deadline was **21-Aug 16:00, passed yesterday** | no signal | REASONING (gcal node + `deadline` fact both present) |
| T2 | **Antler reconsideration is past its own 14-Aug cutoff and silent** | no signal, no suppression row | REASONING |
| T3 | **Titan Capital VP asked one question 14 days ago, still unanswered** — *"your deck doesn't mention current traction, could you mention it succinctly?"*; Rohit's reply was one of 18 copy-paste blasts | no signal | REASONING (`question` obs @ 0.75 on his node) |
| T4 | Lalitha (founding-engineer candidate) cancelled pending a deck — 9 days silent | partial, mis-framed as a sales objection, empty draft | REASONING |
| T5 | **The 11-Aug blast has a 0/18 reply rate** | no signal on any of the 18 | REASONING (org-level) |
| T6 | **Zerodha pitch invisible — and it contradicts the Antler pitch** (`$5k MRR` to Nithin 19-Aug vs `~$2-3k MRR` to Antler 13-Aug) | no node, no signal | CAPTURE + REASONING |
| T7 | Three warm intros rotting on a one-click booking link (Sal, Nitesh, Maria) | generic "Reply to X now", empty body; never says "click their link" | REASONING |
| T8 | Unanswered complaint to a paid program, 5 days | fires on the **wrong address** with the wrong frame | REASONING |
| T9 | **Mentor feedback arrived 21-Aug and IS the mid-review rubric** — *"ventures already running pilots should focus on converting these into paying customers"* | no signal | REASONING (`stage='running pilots'` fact written from this very email) |
| T10 | **The raise has no coherent state** — 4 rejections in 24 days, 0/18 replies, exactly 2 live threads | no concept — every rule is scoped person/deal/meeting, **there is no org-level rule** | REASONING |

**No rule can read a future date.** Every temporal predicate in all 26 rules is backward-looking (`days_since` / `hours_since`); `grep 'hours_until\|days_until'` → nothing exists. The 24-Aug review (confirmed calendar event, Rohit an attendee) and the 21-Aug deadline (stored verbatim as a fact) are **invisible by construction**. Meanwhile the 3 `meeting_no_followup` cards that *did* fire are 20+ attendee cohort webinars where "send a recap" is nonsense — and that rule's only guard is vacuous: observations are **never attached to meeting nodes** (0 in this org), so `no_obs: followup_sent` is always true.

**Honest hit rate:** 13 hard-wrong · 16 dead-cold (≥21 days, all framed "now") · 12 plausibly-useful. The single highest-scoring card in the system (`Reply to boardy@boardy.ai now`, 56) sits on an inbound whose decrypted subject is *"HF0 opened five more spots for its fall cohort"* — a newsletter.

---

## 10. Ranked causes

| # | Cause | Explains |
|---|---|---|
| **1** | **No counterparty role + no direction in extraction** — every person is interchangeable, every email is directionless | invite@, "Save the deal", 22× "Reply to X", the whole shallow feel |
| **2** | **Outbound content written to the self node, then self-excluded** — 234 obs discarded | half of every conversation, incl. the Antler re-pitch |
| **3** | **Single-message extraction, no thread state** — "rejected → re-pitched → reconsideration open" is not a property of any one message | Antler invisible |
| **4** | **`missing_ok:True` + confidence-blind `has_obs` + missing-data-scores-higher** — absence of evidence beats presence of evidence | 4 junk cards at the top, Antler blocked |
| **5** | **`champion_quiet` mappingproxy bug** — the one rule that matches Antler is dead engine-wide, silently, with no audit row | Antler produces literally nothing |
| **6** | **Renderer never sees the email** + invention guard rejects fluent English | 37/41 empty cards |
| **7** | **Score is one clock** — `I` constant, `U`/`R` self-cancel, `corr` pinned, `high` band unreachable | flat ranking, nothing ever pushed, L5.2 never ran |
| **8** | **Vocabulary backwards** — obs closed & wrong-domain, fields open & unread | 85.5% of observations dead, 268 field names |
| **9** | **72% input loss + 0 documents parsed**, no drain, no payload retention | Theresa's own email dropped, decks never read |
| **10** | **No domain routing, no org business model** — sales is the only reachable state | everything reframed as a B2B deal |
| **11** | **Retire-and-reinsert lifecycle + ungated `/activity`** | duplicate contradictory cards |

**If only one thing is fixed:** #1. Role + direction are the inputs every other fix depends on — a fundraising pack alone would still be blind to *who*, and a role model alone would still have only sales plays to offer.

---

## 11. Refuted / narrowed by adversarial verification

Recorded so they don't get re-litigated:

- **"Node scope coverage (company/commitment/service have no rules) is a root cause"** → REFUTED as a *cause*. Real but secondary; the narrow true part is that 3 `deal`-scoped rules are dead and commitments are reasoned only through a latest-wins person mirror (2 promises silently overwritten).
- **"Observation-vocabulary mismatch is why reasoning is shallow"** → NARROWED. The 14.5%/85.5% split is real, but it doesn't explain Antler (whose kinds *are* in the read set). Binding gaps are `meeting_request` + `question` (266 obs, 22%) having no rule at all.
- **"Missing fundraising pack is the root cause"** → NARROWED. True that no rule reads `funding.*` / `application_status` etc., but a fundraising pack alone fixes neither the direction blindness nor the empty drafts.
- **"Dead `schema.fields` is the root cause"** → NARROWED to a real defect (268 invented field names, 192 singletons, a write-only lane) but not the binding constraint.
- **"Commitment/date shape loss is why Antler is invisible"** → REFUTED as primary. The refutation itself surfaced finding #5 above (`champion_quiet` matches and is then lost).

---

## 12. Plan alignment

- Respects **"never expose v1/v2 naming to users"** — no user-facing change proposed here.
- Re-confirms `INTELLIGENCE_QA_ROHIT_AUDIT.md` RC1 (thin extraction), RC2 (constant Impact), RC3 (dead self-filter / `org_seats` empty, investors-as-deals), RC4 (hollow commitments, dupes, staleness) — now with exact failing clauses and a live-repro for each.
- Extends `INTELLIGENCE_DEEP_SALES.md`'s field-drift finding: it is not just `deal.status` vs `deal.stage`, it is that **no `deal` node type exists at all**, so the bridge never runs.
- Nothing in this document was implemented. Read-only throughout.

## Re-verification — 2026-08-30

An audit is a photograph, and this one was taken eight days and roughly two hundred commits ago. It is being marked Reference rather than Active because most of what it found has been fixed and leaving it Active implies a backlog that no longer exists. Its headline findings, checked against code:

**Closed:**

- **"The engine has no idea who the counterparty is or which direction the email went" — the central finding — is FIXED.** `context/extract/envelope.py` now assembles From / To / direction and hands it to the model; `context/extract/prompt.py:14` passes `direction` (inbound/outbound), `:17` passes `we_are` (the account owner's own addresses, "never a counterparty"), and `:34-42` asks for a `roles` array resolved from the envelope (`counterparty | introducer | introduced | …`). `envelope.py:35-39` is careful in the right way: with no self-identity set the direction is `unknown` rather than guessed.
- **"`I` = 55 constant, so the `high` band at 70 is arithmetically unreachable" — FIXED.** `reason/scoring.py:72` — `impact()` is a real function of `(value, p90, linked_deal)`, and the constant is gone from the file.
- **"Copy is empty — the invention guard kills 25 of 41 cards"** — worked and partly closed. `679982d` ("a card was falling back to template copy for reasons that were bugs") plus `deliver/slots.py:63`, which records that the model was not hallucinating but had been handed the wrong premise. The *rate* on a live queue is **UNVERIFIED**.
- **"Junk scores highest because missing data has a higher score"** and **the ranking/tier findings** — addressed by the same scoring rework; live distribution **UNVERIFIED**.

**Not confirmed either way:**

- **The `champion_quiet` / `MappingProxyType`-vs-`isinstance(dict)` finding is UNVERIFIED.** `champion_quiet` still exists as a rule (`packs/general_v1.py:84,155,212`) and `reason/engine.py:44` still tests `isinstance(value, dict)`. Whether a `MappingProxyType` still reaches that line was not established by this pass. If the rule matters, prove it with a test rather than a grep.
- **"72% of email dropped (N-02)"** — this is a live-data measurement and needs a DB. Related and important: `IMPLEMENTATION_PROGRAM.md` gap **L1-02** measured "109 emails irrecoverably deleted", and the drop path itself is still open — see `docs/plans/GRAPH_QUALITY_FIX.md` in the workspace, where the LLM gate's ability to delete violates that plan's own stated law.
- **"0 documents parsed"** — the document lane has since been built (`context/document_register.py`, `context/documents.py`, the Drive projection). Live counts **UNVERIFIED**.
