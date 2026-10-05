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
