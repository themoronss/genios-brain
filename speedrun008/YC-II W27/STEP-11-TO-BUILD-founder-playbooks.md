# STEP-11 · TO BUILD · founder playbooks — what a professional knows about your work

**Owner:** Claude drafts · **Rohit reviews and accepts** (or names a reviewer). **Depends on:**
nothing to start — drafting runs in parallel from `STEP-03` on; *routing* the playbooks needs
`STEP-09`. **Decisions:** `06` D2 (the domain), D3 (advice before acceptance). **Moves:** six
playbooks accepted, each with cases that pass.

---

## 1 · What is true now `[CODE]`

| Your work | What the corpus has today |
|---|---|
| **Fundraising** | Sales `capabilities/10-investor-relations/` — the capability is stable and admitted; its knowledge (`reopen_after_a_pass`, `a_pass_is_a_date_not_a_verdict`, `investors_do_not_chase`) and its object are **draft**; situations `live-investor-relationship` / `live-investor-contact`. Admin's `campaign-awaiting-reply`, `campaign-going-quiet`, `organization-gone-quiet`, `outbound-awaiting-reply`, `condition-awaiting-review` (which names Theresa / Antler) cover parts of it. **And it cannot go live:** `fundraising` maps to no live lane (`reason/domain_shadow.py:512-526`) and is aliased to Sales (`packs/compiler/capability_resolver.py:35-47`), which is shadow on `harsh/mvp` |
| **Programs, accelerators, applications** | no L2 objective or observation kind; appears only in prose (`dependency-stated`, `live-account-admin`, `condition-awaiting-review` mention an application or HF0) |
| **Intros** | no situation. A playbook step (*"close introductions on both sides"*, `playbooks/follow_up_coordination/the-follow-through-relay.yaml`), a rule (`an-introduction-is-not-discharged-by-sending.yaml`), relay detection and the `introducer` / `introduced` roles |
| **Compliance — Startup India / DPIIT** | **nothing anywhere in the repository**; Admin's `statutory-filing` situation is draft, deferred, and cites UK Companies Act examples |
| **Hiring** | `employee-lifecycle-event` is pending an L2 type and routes nothing |
| **Meetings** | Admin `02-meeting-operations` — meeting ahead, left open, without follow-through, cancelled-not-rebooked — **usable as is** |
| Runtime fields the expert needs | `do_nothing_consequence`, `success_signal`, `outcome_window_days` are **not** corpus fields; they come from a template sentence, a 7-day default and NULL. `typical_duration_days`, `signals_of_progress`, `signals_of_decay` exist in the schema and are read by nothing |

## 2 · Why

The expert's reasoning is only as good as what it knows about how this kind of work goes:
the stages, how long each usually takes, what silence means at each stage, what a good next move
looks like, and when to stop. That is professional knowledge, and it belongs in reviewed files
(Atlas RULE 06), not in a prompt.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the domain | `Domain Expertise/Founder Office Expertise/` (D2) | `domain.yaml` with `default_on: false`, activated for your org; its own live lane in `domain_shadow.py:512-526` and its own alias in `capability_resolver.py:35-47`. Sales' `10-investor-relations` **moves** here |
| 3.2 | six capabilities | under it | **01 fundraising** (investor waiting on us · outreach wave gone silent · conditional deferral — *"send me updates"* · warm intro to an investor · before an investor call) · **02 programs and applications** (stages, deadlines, decision mail, documents after acceptance) · **03 networking and intros** (connector semantics, per contact, both sides closed) · **04 compliance** (Startup India / DPIIT recognition and what it unlocks; DigiLocker; MSME / Udyam; state programs such as StartinUP) · **05 hiring** (offer pending acceptance, documents, the ESOP dependency) · **06 meetings** (reuses Admin's four situations) |
| 3.3 | what each must contain | the existing schemas, plus three fields | stages and their typical durations (`typical_duration_days`, finally read); patterns and counter-patterns (heuristics); signals of progress and decay (finally read); wait and stop rules; what a good next move looks like (playbooks); **and** `do_nothing_consequence`, `success_signal`, `outcome_window_days` as authored fields — a schema change, reviewed |
| 3.4 | cases | `Domain Expertise/_eval/founder.cases.yaml` + `STEP-01`'s founder set | ≥ 10 cases per capability, must-detect **and** must-abstain, run by `tests/packs/test_the_corpus_answers_its_own_cases.py` |
| 3.5 | how it is written | offline drafting (the Secret War audit's own allocation: L3 drafting is a permitted model use) | the model drafts from public best practice and from your own measured patterns; every claim in a draft names its source; **you review**; admission needs `stable` + an approved review + a named reviewer (`capability_resolver.py:154-217`) |
| 3.6 | until accepted | D3 | the expert may advise, and the card says *"playbook not yet reviewed"*; with D3 = B, the file is observation only |

## 4 · What will happen

The expert stops guessing what a stage means. *"Hub71 wrote on 1 Oct"* becomes *"Hub71 moved your
application from under review to ___; the next step in this kind of program is ___, usually within
___ days."* *"Pankaj has not replied"* becomes *"an intro this old usually needs one short note from
you, or it dies."* Each of those sentences is a line in a file you accepted.

## 5 · Expected

- six capabilities authored, each with ≥ 10 cases, all passing;
- accepted by you (or a reviewer you name), with admission hashes;
- `fundraising` has a live lane; no founder situation routes through Sales;
- the runtime defaults (template consequence, 7 days, NULL success) disappear from founder cards.

## 6 · Verify

```
.venv/bin/python Domain\ Expertise/_tools/validate.py
.venv/bin/python -m pytest tests/packs/test_the_corpus_answers_its_own_cases.py tests/corpus -q
```

## 7 · Risks

| Risk | Guard |
|---|---|
| Volume before quality — the audit's own warning against authoring 152 files at once | six capabilities, depth first; each must pass its own cases before the next |
| India-specific compliance written from memory | every compliance line names its official source; you review it |

---

## 8 · The check of 2026-10-09 — what the 5 Oct plan got right, and wrong

Every claim above was re-read against `speedrun008` @ `353d06ea` (STEP-10 closed) by two read-only workers,
and the claims that decide the design again by hand (*hand*). The plan was **measured on the golden set**:
all 47 founder cases replayed from their cassettes through the real chain, each tenant's rows read before
it was removed — 0 cassette misses, every verdict as `03` §F.1 records it, no spend
(`baseline/yc2w27-s11-check/`: `measure_expertise.py`, `table.md`). Production was not read.

### 8.1 · Measured — the golden set (47 cases; only Admin is active: `l3_activation` `admin:on:system:onboarding`)

| | Result |
|---|---|
| where the work lands | 361 situations: admin 140 (75 of them period reviews), support 108, sales 90, **fundraising 23** — `investor_relationship` 22, `investor_contact` 1, in 18 cases. Every fundraising one is **dark**: `fundraising` maps to no corpus (`reason/domain_shadow.py:525`), so nothing the decider says about it can become a card |
| where the cards come from | 27 cards: **17 from the legacy `unanswered_email` rule**, 10 from Admin capabilities (`account_admin` 4, `meeting_follow_through` 4, `dependency_stated` 1, `admin_contact` 1). **None** carries founder expertise |
| programs read as investors | F17 (an accelerator's interview), F24 (an accelerator's review), F01 and F02 (a government portal), F20, F31, F35 each form `investor_relationship` in `fundraising`. F17's decider (cassette `ba2537db…`) weighs two Sales plays — `account_research…` 4389, `investor_relations.reopen_after_a_pass` 4686 — and defers: *"Defining the ideal customer profile does not answer what this person asked."* |
| the 12 must-detect cases lost in reasoning, by what blocks them | **STEP-11 itself:** F17 (and F24, the same mechanism) — a program's stages and plays, and a live lane. **The domain first (D2):** F01, F09 — and F15 (not among the 12: five fund situations dormant in `fundraising`). **STEP-12's dossier:** F02 (the decider sees none of the notices' words, F99), F11, F19. **STEP-14:** F07, F16, F47, F27, F29 (and the must-abstain F40) |
| what that means | STEP-11 on its own moves **two to four** must-detect cases, and only with a live founder lane. Its main value is what STEP-12's expert reads per file |

### 8.2 · The claims

| Claim (5 Oct) | Verdict (9 Oct) |
|---|---|
| Sales `10-investor-relations`: capability stable and admitted; knowledge and object draft; two live situations | ✅ — `capability.yaml:7` stable, approved by Harsh, content hash; the playbook (`reopen-after-a-pass`), both heuristics and the object `investor-conversation` are `draft`; `live-investor-relationship` and `live-investor-contact` stable, approved, routed by the Sales registry (`:195-228`). It also carries **program doctrine** — *"accelerator and programme conversations kept apart … cohort deadlines that do not move"* (`capability.yaml:39-50`) |
| Admin's `campaign-awaiting-reply`, `campaign-going-quiet`, `organization-gone-quiet`, `outbound-awaiting-reply`, `condition-awaiting-review` cover parts | ✅ all five stable, their capabilities admitted; Theresa / Antler is named only in a comment (`condition-awaiting-review.yaml:15-17`), whose `:60` still says "stays `draft`" against `stable` at `:68` |
| `fundraising` maps to no live lane; aliased to Sales; Sales shadow | ✅ (*hand*: `domain_shadow.py:525` `"fundraising": None`; `capability_resolver.py:35-52`). Sales' `default_on` is `false` on this branch (Admin `true`, Support `false`); whether production still holds a Sales row written while it was `true` (10 Sep – 2 Oct) needs one read |
| programs: no L2 objective or observation kind | ✅ — and worse: programs are **fundraising by construction** — the L1 hint (*hand*: `capture/domain/hints.py:23-29`, *accelerator, incubator, cohort, programme, program application, application status* → `fundraising`), the extraction prompt (*"a fund, an angel, an accelerator"*, `context/extract/prompt.py:118`) and `application_status`, expected on `investor_relationship` with no writer (`context/domain_spec.py:650`) |
| intros: a playbook step, a rule, relay detection, two roles; no situation | ✅ (`the-follow-through-relay.yaml:75-85`, `an-introduction-is-not-discharged-by-sending.yaml`, `pipeline.py:421-429`); the legacy lane already makes intro follow-up cards (`packs/general_v1.py:145`) |
| compliance: *"nothing anywhere"* | ⚠️ nothing in the engine or the corpus (0 hits); a few in tests and one docstring. Admin's `statutory-filing` is a **capability** (stable, admitted, deferred: `blocked_on_l2_type` `filing_due`, `filing_overdue`), whose one situation is draft and routes nothing; the UK examples sit in its objects, beside Indian forms (MGT-7, PF, ESI) |
| hiring: `employee-lifecycle-event` pending an L2 type | ✅ draft, routes nothing — and it is on/offboarding, not hiring: nothing covers a candidate, an offer or ESOP, though L2 has a `candidate` nature and a `hiring` objective |
| meetings: Admin `02-meeting-operations` usable as is | ⚠️ three situations there plus `meeting-ahead` in `01`; two bind `relationship`, a `general` type that maps to nothing, so they are live only through `admin_contact` |
| `do_nothing_consequence`, `success_signal`, `outcome_window_days` are not corpus fields — a template, 7 days, NULL | ✅ (*hand*: `reason/adapters/expertise.py:1530-1532` the sentence; `contracts/reasoning.py:572` `window_days = 7`, carried only on a DECISION; `success_signal` read from the tenant pack's `plays`, which is `{}` for every corpus pack) |
| `typical_duration_days`, `signals_of_progress`, `signals_of_decay` read by nothing | ✅ at runtime — all 69 situations carry them; only an offline display script reads them (`scripts/dx_review_queue.py:85-87`). A playbook STEP's duration is read, as effort (`play_priors.py:319`) |
| §3.1 a Founder Office domain needs its own lane | ⚠️ simpler than written: **a new corpus gets its card lane with no engine code** (*hand*: `packs/wiring._corpus_packs`, `platform/l3_activation.L3_DOMAINS` reads the corpus). The resolver's comment that it *"can never become a card"* is stale. It does need the L2 map (`_L2_TO_L3_DOMAIN`, `CANDIDATE_ROUTES`, `context/domain_silence.DARK_DOMAINS` and their two guards), the alias, and the activation |
| §3.5 admission needs stable + approved review + a named reviewer | ✅ for situations (flagged, the card becomes an observation) and capabilities (dropped without an accepted content hash). ⚠️ **playbooks, heuristics and objects are not gated at all** (`artifact_admission_reason` *"reports, it does not gate"*) — §3.6's *"playbook not yet reviewed"* needs new code |
| §6 verify | ⚠️ both commands are **green before any STEP-11 work** (`validate.py`: 1,443 files, 0 errors, 35 warnings; the tests: 104 passed) — a green run is no evidence; the cases test checks routing and admission only, never content, and wants half of all cases to abstain |

### 8.3 · New — not in the plan

| # | What | Evidence |
|---|---|---|
| N1 | **A file cannot pick a playbook.** Its kind is `connector`, `watched`, `person` or `intro` — roles, not work; an in-motion line of the brief carries no kind and no counterparty (D31 open) | `context/workstreams.py:70-71`, `:247-256`; `contracts/company_brief.py:71-79` |
| N2 | **No stage anywhere.** No file has one; the corpus's only stage model is the draft `investor-conversation` object (`stage`, states, `party_kind` *fund, accelerator, angel…*). The golden specs expect one on F01 (*under examination*), F02 (*recognised*), F17 (*interview*); STEP-09 and STEP-10 left stages to STEP-11 (D39) | `workstreams.py:93-117`; `investor-conversation.yaml:62-223` |
| N3 | **The decider never reads the corpus's claims** — live: the prompt renders each heuristic citation as `{"rule": null, "quote": null}` (it reads `rule_id`/`quote`, the contract carries `artifact_id`/`statement`); playbook steps are cut at 300 characters; labels fall back to ids; mental models are never read; R-1 reads no corpus field. Whatever STEP-11 writes would not reach the model → **`03` F121** | (*hand*) `reason/llm_decision_maker.py:313, 505-507`; `contracts/domain_expertise.py:249`; `reason/adapters/citations.py:316-321` |
| N4 | the existing route for fundraising is *"one line from live"* — but it lands in the **Sales** corpus, and its second switch is activating Sales, which lights every Sales situation (90 on the golden set) against your *Admin only* rule | `domain_shadow.py:482-494` |
| N5 | the corpus may bind only the L2 situation types that exist; there is none for a program, an intro, compliance or hiring (`filing_due`, `employee_lifecycle_event` are planned, with no producer). *"If no L2 type honestly applies, author no situation and say why"* | `Domain Expertise/_AUTHORING-BRIEF.md`; `_schema/vocabulary.yaml` |
| N6 | the corpus already has a reviewer's queue (`scripts/dx_review_queue.py` → `_review/QUEUE.md`: approve · change · defer) and an admission stamp (`_tools/admit.py --accept`) | — |

### 8.4 · What changes in the design

1. **STEP-11 writes what a professional knows, as reviewed data the expert reads — no new rules engine.**
   The LLM judges (STEP-12); code keeps memory, computes and checks. Nothing here detects a stage by rule.
2. **One founder domain (D2), with no new engine code:** a `Founder Office Expertise` corpus; the L2
   `fundraising` domain maps to it (the `CANDIDATE_ROUTES` row moves, `DARK_DOMAINS` and both guards with
   it); the alias `fundraising → founder_office`; `default_on: false` and an activation for your org only.
   Sales stays off. Sales' `10-investor-relations` moves in, re-reviewed (moving it changes its ids and
   its content hash).
3. **A file's kind of work comes from the brief (D31):** an in-motion line names its kind — `investor`,
   `program`, `compliance`, `hiring`, `intro`, `partner` — and its counterparty (an address or a domain);
   the drafter proposes, you accept. A file takes the kind of the line that names it; the roles
   (connector, watched, person, intro) stay. One kind, one playbook. A file no line names has no kind, and
   the expert may propose one, labelled (STEP-12).
4. **Stages are data; the current stage is a judgment.** Each playbook declares its stages — a closed list
   — with a typical duration per stage as a `playbook_prior` (never called *normal*; only a measurement at
   n ≥ 5 is, D37), what quiet means at each stage, and its wait and stop rules. STEP-12's expert names a
   file's stage from its timeline, constrained to the list and with evidence; code computes the dwell —
   D39's stage dwell lands there.
5. **What a playbook holds** (the contract, in the corpus's own schema, extended where needed): stages with
   priors · silence by stage · next moves (plays with *done when*) · wait and stop · `do_nothing_consequence`
   · `success_signal` · `outcome_window_days` · failure patterns · a source for every claim. The compiled
   adapter reads the three runtime fields and the situation lifecycle fields; today's template, 7 days and
   NULL remain only as labelled fallbacks.
6. **The expert can see it (F121):** the decider's prompt renders the contract's citation keys, whole
   playbook steps within a budget, and names; STEP-12's dossier reuses the same rendering. The cassettes
   whose prompts move are re-recorded.
7. **Review state is visible (D3):** the package carries which playbooks and heuristics are unreviewed; a
   card built on one says *"playbook not yet reviewed"* — your org only. Admission stays the corpus's own:
   stable, approved, a named reviewer (you), the content hash stamped.
8. **A resolver for STEP-12:** `playbook_for(file)` → the kind's playbook — stages, priors, signals, moves,
   do-nothing, success, review state — the read model STEP-12's dossier calls; `GET /v1/workstreams/{file}`
   names it.
9. **Content, depth first, by measured reach:** 01 fundraising (moved and deepened: the wave gone silent,
   the conditional deferral — *"send me updates"*, a warm intro to an investor, before an investor call, a
   pass is a date) and 02 programs & applications (stages, deadlines, decision mail, interview prep,
   documents after acceptance) first; then 03 intros, 04 compliance (official sources only, each line
   cited), 05 hiring (offer → acceptance → documents → joining; ESOP), 06 meetings (Admin's four reused,
   investor-call and interview prep added) — authored while STEP-12 is built.
10. **Not now:** new L2 situation types for programs, compliance or hiring (D32 holds — the brief gives
    the kind and the expert reads the file); stage rules; a Sales switch.

### 8.5 · What will be built — tree block `yc2_w27_s11` (milestones M30, M31), proposed

| Milestone · category | Units | What |
|---|---|---|
| M30.C1 · the domain (D2) | 4 | the corpus domain; the L2 map with its declarations and guards; the alias; the golden runner switches it on for the founder cases, as `scripts/activate_tenant.py --domains admin,founder_office` will for your org |
| M30.C2 · the playbook contract | 3 | the schema and validator (stages with priors, the three runtime fields); the compiled adapter reads them; stage priors as `playbook_prior` numbers |
| M30.C3 · the expert can see it | 2 | F121 — citations, whole steps and names in the decider's prompt; review state on the card (D3) |
| M30.C4 · the file's kind (D31) | 8 | migration `0196` and the contract (an in-motion line's kind and counterparty); the store, the route and the script carry them (three units added on 9 Oct, building: the contract alone reached none of the three); the drafter proposes them; files take them; the golden brief |
| M30.C5 · the resolver | 2 | `playbook_for(file)`; the route names it |
| M30.C6 · the first two playbooks | 3 | 01 fundraising (moved, deepened), 02 programs & applications; and Sales' copy of investor relations retired once the L2 map has moved (added on 9 Oct, building: retired any earlier, it breaks the candidate-route guard the map retires) |
| M30.C7 · the golden set and review | 4 | `_eval/founder.cases.yaml`; the review sheet for you and the admission stamps; the re-record and the board; the acceptance — every founder file resolves its playbook, F17's file reads the program one, the decider reads the playbook's claims, no founder card carries the template, 7 days or NULL |
| M31 · the other four playbooks | 4 | 03 intros · 04 compliance · 05 hiring · 06 meetings — each with its cases, reviewed by you, authored while STEP-12 is built |

30 units: 26 in M30, 4 in M31 (26 when proposed; C4's store, route and script, and C6's retirement of the Sales copy, added on 9 Oct). Critical path: the contract → the adapter → the fundraising playbook → the resolver → the re-record → the
acceptance.

### 8.6 · Decisions

| | Question | Recommended | Default |
|---|---|---|---|
| D2 | Founder work in scope, as one Founder Office domain? *(restated)* | **Yes** — a corpus of its own, live for your org only; Sales stays off. Its card lane needs no engine code | C — Admin only: the playbooks are written for STEP-12 and no fundraising situation becomes a card |
| D3 | Before you review a playbook, may the expert advise? | **Yes, labelled** *"playbook not yet reviewed"* — your org only | observation only |
| D31 | Does an in-motion line name its kind and counterparty? *(now needed)* | **Yes** — without it no file can pick a playbook | kinds only for connectors and the watchlist |
| D45 | Who reviews the playbooks? | **You**, line by line (accept · edit · reject), as with the brief; admission only after it | you |
| D46 | Fix F121 inside STEP-11 (the decider reads the corpus's claims; cassettes re-recorded)? | **Yes** — otherwise nothing STEP-11 writes reaches the model before STEP-12 | yes |
| D47 | Compliance written only from official sources, fetched and cited (startupindia.gov.in, dpiit.gov.in, udyamregistration.gov.in, digilocker.gov.in)? | **Yes** | yes |
| D33 | Dormancy per kind? *(now authored here)* | **Yes** — each playbook's stop rule, as a labelled prior | 45 days for every file |

### 8.7 · Risks

| Risk | Guard |
|---|---|
| volume before quality — six capabilities at once | depth first: two in M30, each passing its own cases and your review before the next |
| your review is the bottleneck (the Atlas: *"the dominant hidden cost is expert review"*) | one review sheet per playbook, line by line; D3 lets the expert advise, labelled, meanwhile |
| a prior read as a habit | `playbook_prior` is a source, never *normal*; the card says *"a typical program takes…"*, not *"you usually…"* |
| India compliance from memory | D47; a guard that every compliance line names an official URL |
| moving investor relations breaks what Sales routes | Sales is off; the move retires the Sales ids in one unit, its guards with it |
| fixing F121 changes every decider prompt that carries a citation | the cassettes re-recorded from the ideal reader, each diff read (as STEP-10 did fifteen) |

