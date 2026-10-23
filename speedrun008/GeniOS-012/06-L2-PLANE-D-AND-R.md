# 06 · L2 Qualification: Plane D (what an expert knows) + Plane R (how it reasons) (D24–D31)

**Written for:** coding agents (units), Rohit (three decisions) and Harsh (budgets and switches).
**Fixes:** D24–D31 of [02](02-THE-PATH-OF-ONE-MAIL.md).
**Atlas v2 target for L2** ([GeniOS-008 00-ARCHITECTURE](../GeniOS-008/00-ARCHITECTURE.md)): L2 reads a bounded, versioned L3 snapshot plus the relevant **Plane D** slice (an `ExpertisePackage`), runs **Plane R** reasoning units with 0–3 bounded model calls, asks for missing evidence (`EvidenceNeed`) instead of guessing, and returns a `ReasoningResult` with proposed changes for L3 to admit. Recommendation ≠ authorization: L4 authorizes.

**Cards this file unlocks:** almost all of them. L2 is where `i1` becomes "write to them now, because of today's new fact", where `i2` becomes "your reply didn't answer the ask", and where every investor, programme and intro card gets its playbook.

---

## How L2 runs today (read before any unit)

```
reason/runner.run_all (:1923-2126)
 1. expert_pass  reason/expert/sweep.py:156-375   (:2002-2007)
      triggers_for (triggers.py:175-196) picks moved files
      if l2_cards AND l2_reasoning AND an R-9 client  → hand the files to L2, no R-7 call
      else R-7 reviews them: ≤10 files per pass, nearest deadline first
 2. l2_pass      reason/l2/sweep.py:169-445       (:2013-2019)   files_due = expert["to_l2_files"]
      dossier + snapshot → R-9 → l2_admission.decide → ADMIT/HOLD/REJECT
 3. shadow_compile reason/domain_shadow.py:1328+  (:2029-2039)   (only if a compile flag holds, see 03 Part C)
      _decide_covered_files (:780-972) FIRST (S18.U1 ✅), then the compiled situation loop (:1756+)
 4. the legacy per-pack run() loop                (:2062-2081)
 5. why_no_card counts                            (:2096-2101)   (S18.U3 ✅)
```

Models: R-7 (`SITE_EXPERT`) and R-9 (`SITE_REASON`) both run on tier T2 = `claude-sonnet-5` (hard-coded in `llm_sites.tier_model` `:290-299`), thinking **off**, `max_tokens` 6000 / 8000, timeout 120 s / 160 s, budget **$2.00/day** each and $0.10 / $0.15 per call (`reason/bundle/budget.py` `OWN_BUDGETS` `:63-71`). A client exists only if `use_real_llm` and an API key are set.

---

## Part A · Plane D: the founder's expertise exists, but is refused (D31)

### What happened, and how

1. The investor and programme playbooks were authored in YC-II W27 and moved into a **Founder Office** domain on 9 Oct (D2), with six capabilities: `investor_relations`, `program_applications`, `introductions`, `registrations_and_recognition`, `offers_and_joining`, `external_meetings`. On the same day the Sales domain's investor copy was retired (Sales `domain.yaml:148-151`; `CANDIDATE_ROUTES` emptied, `domain_shadow.py:1004-1021`).
2. All six are `status: draft`, `review_status: unreviewed`. Their review sheets, `speedrun008/YC-II W27/review/investor.review.yaml` (146 lines) and `program.review.yaml` (121 lines), have every `decision: ''`, and both say "Nothing is admitted until every line is accepted (06 D45)". Nobody did the review.
3. The registry routes only `investor_relationship` and `investor_contact` (to `investor_relations`). The other five are `deferred_capabilities` with reason `no_runtime_trigger`: there is no signal or situation that starts them (the L1 words of [04 Part C](04-L1-SIGNALS.md) are what is missing).
4. The live compiler runs with `require_admission=True` (`domain_shadow.py:1668-1676`). `_admission_reason` (`packs/compiler/capability_resolver.py:274-298`) requires `status == stable`, `approved`, `reviewed_by` and a hash match, and raises `UnsupportedCoverage("unreviewed")` (`:820-823`). A programme or compliance file is refused as `misfiled_kind` (`domain_shadow.py:1146-1153`, `:1913-1917`).
5. The expert *file* path does not check admission: it needs only the domain's activation row and the synthesised corpus pack (`packs/wiring._corpus_packs`, `ensure_defaults` `:164-176`). The dossier then labels the playbook "playbook not yet reviewed" (`playbook_reader.REVIEW_LABEL`). So with Founder Office **activated** ([03 Part B](03-RUN-GATE-AND-SWITCHES.md)), the expert reviews investor files with the draft playbook, labelled; the compiled lane still refuses them.
6. `WORK_KINDS` (`contracts/company_brief.py:48`) = investor, program, compliance, hiring, intro, partner, vendor. There is no sales or customer kind, so `KIND_CAPABILITY` (`playbook_reader.py:48-56`) gives a prospect file no playbook (`s1`, `s2`).

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S23.U1** | Rohit | The playbook decision | Recommended default: **"label and use"**: draft Founder Office capabilities may make cards, every such card is labelled "playbook not yet reviewed", and lines are reviewed over time from real cards. GeniOS-011 [06](../GeniOS-011/06-DECISIONS.md). | logged | 🔒 Rohit |
| **S23.U2** | Claude | The compiled lane admits draft Founder Office capabilities, labelled | In `_admission_reason`, accept `status: draft` for domains on an explicit allow-list (Founder Office first) when the tenant decision (S23.U1) says "label and use"; carry `review_status` onto the card (`label: unreviewed`). The hash check stays. | an investor file in `fundraising` compiles live with the label; a draft Sales capability is still refused | ⬜ |
| **U12-12** | Claude | The five deferred capabilities get triggers | In the Founder Office registry map, route: `application_status` → `program_applications`; `introduction` → `introductions`; registration and recognition portal mail (kind `compliance`) → `registrations_and_recognition`; offer and joining mail (kind `hiring`) → `offers_and_joining`; `meeting` with an external attendee → `external_meetings`. Each route needs its L1 word (S12.U2) or a brief kind. Files: `Domain Expertise/Founder Office Expertise/registry/*`, `packs/compiler/capability_resolver.py`, tests with synthetic cases. | each synthetic case routes to its capability; `deferred_capabilities` is empty | ⬜ after S12.U2 |
| **U12-13** | Claude + Rohit | A customer (prospect) kind | Add `customer` (or `prospect`) to `WORK_KINDS` and map it to Admin's outreach playbook, so design-partner outreach files get a playbook while Sales stays off | a prospect file's dossier carries a playbook | ⬜ (Rohit names the kind) |
| **S23.U3** | Claude | Vendor renewal reaches a renewal card | the renewal play (Admin) on `contract_renewal` signals; Stripe-type notices not junked | `c2` appears | ⬜ |
| **S23.U4** | Claude | The cadence line says whose normal it is | "their usual reply is 4 days (measured on 6 replies)" vs "a typical investor replies in a week (playbook)" | — | ⬜ |
| **Review** | Rohit or a reviewer he names | Review the two sheets line by line over time | `investor.review.yaml`, `program.review.yaml`: accept, edit or reject each line; an accepted capability moves to `status: stable` with `reviewed_by` and a new hash | the first capability is `stable` | 🔒 |

---

## Part B · Plane R: a quiet file is looked at again (D24)

### What happened, and how

- `reason/expert/triggers.py` `triggers_for` (`:175-196`) reviews a file only on: first look, a new event or answer, a date moving a rung closer (`HOURS_UNTIL`), a correction or a "wrong" verdict, or a one-time crossing (`_crossings` `:132-159`): `reply_overdue` (their move, past their usual reply time or the file's usual gap) and `past_normal` (past the longest gap ever, or our move past our usual time).
- With a single touch there is no measured reply time and no gaps, so `their_usual` and `longest_gap_days` are None and **no crossing ever fires**. Even when one fires, it fires once (the `not (... quiet_then > usual)` guard). **Time alone is never a trigger.** `FOUNDER_ASKED` exists, but no caller passes `asked=True`.
- Effect: after three unanswered updates to an accelerator, or one outreach to a prospect who replied once, the file is never reviewed again.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S21.U2** | Claude, after Rohit's D57 | A quiet file with an open ask comes back | 1. When a file has no measured gap, use a **prior** from Plane D: the kind's typical gap, written in the playbook (never in code) and reviewed like any other line. Proposed starting values for the reviewer, not measured: investor 14 days, programme 21, intro 7, prospect 10. Once the Behavior Brain has measured this company's own gaps, the measured value wins. 2. A file with an open ask, or an in-motion brief line, is re-looked at most **once per prior gap** while quiet (time becomes a trigger, bounded). 3. Wire `FOUNDER_ASKED`: "Ask GeniOS about X" and a founder's "watch this" mark pass `asked=True`. Files: `reason/expert/triggers.py`, `Domain Expertise/Founder Office Expertise/playbooks/*` (the prior), `api/` ask route. | a synthetic investor file with one outreach and 30 quiet days is re-looked once at day 14 and once at day 28; a file with no open ask and no in-motion line is not. Mutation: drop the prior → red | 🔒 D57, then ⬜ |

---

## Part C · From judgment to card (D28, D29, D30)

### What happens, and how

- **D29, the home:** a covered file makes a card only if it has a **home** (`_FILES_HOME` `domain_shadow.py:547-553`): a `context_situations` row anchored on it, or one its review explains, in an **activated** domain (`live_lane` `:1056-1083`), with an active tenant pack with `authority_revision > 0` (`_tenant_pack` `:130-162`). No home → `covered_without_situation` (`:817-823`). `general` maps to no L3 domain (`_L2_TO_L3_DOMAIN` `:1040-1053`), so it is decided in shadow only (`expert_shadow`, `:875-879`). `fundraising` maps to `founder_office`.
- **D30, the cap:** `_daily_allowance` (`domain_shadow.py:165-186`) = `budget_per_user_day` (7, `runner.py:1089`) × active seats (≥1, capped by tier: trial 2, startup 5, growth 15, scale 50) − `_budget_used` (`runner.py:551-555`), and `_budget_used` counts **every signal the org created today, from any lane**. S18.U1 decides judged files first within a sweep, but a morning sweep's template cards still spend the day before an afternoon judgment. (Sales and Support packs set 15, `packs/sales_v1.py:35`, `support_v1.py:50`, capped at 15 by `packs/merge.py:43`.) In L5 the cap stops only the push; the card is still written.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S18.U4** | Claude | Bind a covered file's decision to the file itself | When a covered file has no home, decide it on the file (`file_id` as the subject), in the domain its review names; `general` decides in **Admin** instead of shadow. The card's `file_id` column carries it. | a covered file with no situation, in `general`, gives an Admin card; `covered_without_situation` and `expert_shadow` for `general` reach 0 on the golden set | ⬜ |
| **U12-14** | Claude | Judged files keep their slots across the day | Reserve part of the day's allowance for covered files: `_daily_allowance` returns two numbers, `judged` (default: half, at least 3) and `formula` (the rest); legacy and compiled-formula lanes spend only `formula`; judged files spend `judged` first, then `formula`. `_budget_used` counts per lane (`signals.output_lane`). Files: `reason/domain_shadow.py`, `reason/runner.py`, tests. | with 7 formula signals made at 09:00, a file judged at 15:00 still gets a card. Mutation: one shared pool → red | ⬜ |

---

## Part D · The dossier sees across threads (D25)

### What happens, and how

The judgment reads **one file** (`reason/expert/dossier.py` `read_parts` `:759-813`, `SECTIONS` `:67`; `reason/l2/dossier.py` `build_l2_dossier`). A file is one counterparty, so several threads with them are included, but nothing from other counterparties. It holds: the accepted brief (including "Goals now"), the file's timeline, its own meetings, promises, numbers, coverage, the kind's playbook, situations, judged-before and what-if. L2 adds signals (block A), a 2-hop graph snapshot (`reason/l2/snapshot.py`, 40 nodes, 5 seeds), up to 5 comparable files, tools and coverage. Caps: 8 whole touches, 30 listed, 10 people, 5 waves, 10 promises, 10 moves, 20 claims, 5 asks closed, `DOSSIER_CHARS=60_000`.

What it does **not** hold: the calendar outside the file, other files, goal objects. So the ideal card's "one cross-thread fact" (field 13, [01 §3](01-WHAT-THE-LOCAL-SESSION-DID.md)) cannot exist.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **U12-15** | Claude | A "what else is true today" block | Add a bounded block to both dossiers: (1) the founder's calendar for the next 7 days and last 3 days, titles and attendees only, every event marked whether it involves this counterparty; (2) up to 5 other files linked to the same accepted goal (after S30) or the same in-motion brief line, one line each with their state; (3) open discrepancies on the tenant node (N1b). Hard cap 2,000 characters, so the dossier stays bounded. Files: `reason/expert/dossier.py`, `reason/l2/dossier.py`, tests. The judgment's output schema gains `cross_fact` (one sentence with its source id), checked by the claim check like every other sentence. | on a synthetic founder with an investor file and a programme review on the calendar today, the dossier carries the review; the judgment's `cross_fact` cites it | ⬜ |
| **S22.U2** | Claude | The routed capability's `ExpertisePackage` in block D | as in GeniOS-011 | — | ⬜ |
| **S16.U3** + **U12-09** | Claude | Typed unknowns and contradictions in the snapshot | held until the replay harness pins knowledge time ([05 Part H](05-L3-CONTEXT-GRAPH.md)) | — | ⏸ |
| **S29.U1–U2** | Claude | Goals in the judgment (block G, `GoalImpact`) | see [07](07-GOALS.md) | — | ⬜ |

---

## Part E · The answer that does not answer (D20, L2 half)

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **U12-16** | Claude | The judgment says whether a reply answered the ask | For every `replied_unanswered` ask in the dossier (U12-08), the judgment's output carries `asks: [{ask_id, answered: yes/no/partly, quote}]`. "no" or "partly" keeps the ask open and makes the move "answer what they asked: X". Verify checks the quote against the mail (claim check). L3 records the result: `answered` closes the ask, `no` keeps it `reply_owed`. | `i2` on a synthetic analogue: "what is your traction?" → a reply with no number → a `reply_owed` card "they asked for traction; your reply didn't give it" | ⬜ after U12-08 |

---

## Part F · Judgment quality: held cards and the real model (D27, D26)

### What happened, and how

1. The claim check (`contracts/claim_check.py`, `CHECK_VERSION = "check.v4"` `:38`, 17 `HELD_BECAUSE` reasons `:131-151`) holds any move whose facts it cannot trace to the mail.
2. The first real-model pass (12 Oct, Haiku) held **68 of 86** reviews: the model cited line text instead of ids, paraphrased numbers, named rules. A held card prints `reason/expert/verify.py:787-793` `_held_question`: *"What is the next step with {them}? We held the one we found: {why}."* That is the "weird card".
3. STEP-13b fixed it (check.v5, a repair ladder, `reason/expert/ladder.py`, `file_engine.py`, `file_units.py`): held share 79% → 18.5% on Haiku. It sits on `yc2w27-int13b` (`42d61e8f`) and `yc2w27-s13b` (`1eb37eb1`), 43–44 commits off the head, and its `migrations/0250_expert_review_attempts.sql` **collides** with `0250_screen_followup_read_path.sql` on the head.
4. The production models (Sonnet 5 for R-7 and R-9) have **never completed a live golden pass**. Every golden answer is pre-written by the ideal reader (67 of 67 cassettes `source=ideal_reader`). S07.U1 ✅ fixed the harness (it now asks R-9 on its production tier, with a 2-call probe).
5. Budget: $2/day per site and ≤10 files per R-7 pass is right for steady state. After a 365-day resync, every in-motion file is "first look" at once.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **S20.U1** | Rohit | Go for STEP-13b, and the claim-check product calls | default: go | logged | 🔒 |
| **S20.U2** | Claude | Port STEP-13b onto `speedrun008` | rebase or cherry-pick the 13b units; **renumber its migration** to the next free number at merge time (0252 is claimed by S34.U3's `cards_copy`, see [08](08-L5-CARDS-AND-DASHBOARD.md); take 0253 or later, and update every reference); re-run the 13b tests and one mutation per unit | the 13b tests pass on the head; migrations apply in order on a fresh DB | ⬜ |
| **S20.U3** | Claude | A held card is repaired once, then written in the founder's words | one repair call with the check's reasons; if still held, the card says what is known and what to check, in plain words, never the template | no card text contains "We held the one we found" | ⬜ |
| **S20.U4** | Claude | Uncertainty routes to a lane, never to a held question | an overdue move, an "unknown" confidence or an unnamed decider becomes an Investigation or Monitor card (Admin Atlas lanes), not a held question | — | ⬜ |
| **S07.U2** | Rohit | The live key and a spend cap for one real-model pass | ~$5 cap, probe first | logged | 🔒 |
| **S07.U4** | Claude | R-7/R-9 live pass on Sonnet 5, then the board | after S20.U2; the result (held share, cards per file, cost) in [13-LOG](13-LOG.md) | held share ≤ 25% | ⬜ |
| **U12-17** | Claude + Rohit's yes | A catch-up budget after a resync | after a backfill completes, raise R-7/R-9's daily budget for that org for N days (default 3 days × $10) and lift the 10-files-per-pass limit, nearest deadline and in-motion lines first; back to steady state after. Behind a per-org switch Harsh sets. | after a synthetic 365-day backfill of 40 in-motion files, all 40 are first-looked within 3 days; spend stays under the cap | ⬜ |

---

## Part G · Waves and seeds (L2 half)

| Unit | Owner | What | Status |
|---|---|---|---|
| **S21.U1** (L2 half) | Claude | A wave file is judged **once**: "an update to 12, 0 replies in 10 weeks; follow up individually with the 3 warmest, with drafts" | ⬜ after [05 Part C](05-L3-CONTEXT-GRAPH.md) |
| **S21.U3** | Claude | Seeds re-key to their file; a two-file bundle is judged per file (today it is judged under the first file only) | ⬜ |
| **S19.U1–U2** | Claude | What the judgment proposes is written; a failed judgment keeps the last good review; truncated answers retried | ⬜ |

---

## Part H · Switching L2 cards on (S25), one type at a time

The order is fixed by the plan: the real-model pass (S07) → the claim check fixed (S20) → admission decides (S24) → daily health (S05) → then:

| Unit | What | Status |
|---|---|---|
| **S25.U1** | a per-type gate for `l2_cards` (not one tenant-wide switch), and the producer on every card | ⬜ |
| **S25.U2** | card guard and the L2 board in CI | ⬜ |
| **S25.U3** (Rohit + Harsh) | first types on Rohit's org: investor outreach and awaiting reply; one week side by side with `l2_shadow_report` | 🔒 |
| **S25.U4** | retire the old lanes for each switched type | ⬜ |

---

## After this file: what should be true

1. Founder Office capabilities make cards, labelled until reviewed, and all six have triggers.
2. A quiet file with an open ask comes back on a bounded schedule.
3. A judged file always reaches a decision, in its own file, with a slot kept for it.
4. The judgment sees today's calendar, linked files and open conflicts, and can state one cross-thread fact.
5. A reply that doesn't answer the ask is caught.
6. Held cards are rare (≤ 25% on the production model) and never read as engineer sentences.

**Expected after Step 5:** `i1`, `i2`, `i4`, `s1`, `s2`, `f3`, `c1`, `c2`. Record what actually appears in [13-LOG](13-LOG.md).
