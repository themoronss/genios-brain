# 06 · Decisions — only you can make these

**Written for:** Rohit. Each decision has a recommendation and a default. If you say nothing, the
default holds, and the step that depends on it says so in its own file.

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| **D1** | Does the expert's judgment decide **what matters**? | **Yes** — an amendment to the Atlas's RULE 02 | `STEP-12`, `STEP-13` |
| **D2** | Are your founder workstreams in scope now, beyond "Admin only"? | **Yes** — one "Founder Office" domain. ⛔ Restated 2026-10-07 with STEP-09's check (§8.5): STEP-09's files (M27) are domain-free and build under any answer; D2 decides only whether files in a dark domain reach a card (M28). ⛔ Restated 2026-10-09 with STEP-11's check (§8.2, §8.6): a new corpus domain gets its card lane with **no engine code** (`packs/wiring._corpus_packs`); A means a `founder_office` corpus, the L2 `fundraising` domain mapped to it, live for your org only, Sales off | `STEP-09` (M28), `STEP-11` |
| **D3** | Before you review a playbook, may the expert still advise? | **Yes, labelled** — your org only. ⛔ 2026-10-09 (STEP-11 §8.2): playbooks and heuristics are not gated by review today, so the label needs new code (`STEP-11` M30.C3) | `STEP-11`, `STEP-12` |
| **D4** | How long is low-attention mail kept? | ✅ **180 days, encrypted** — on Rohit's go on STEP-03 (6 Oct), whose plan said 180 | `STEP-03` (✅ built) |
| **D5** | How far back does the re-sync go? | **365 days** — ⛔ restated 2026-10-07 by `09` D16: 180 loses the 3one4 deferral (2 Apr), and the 60-day default no longer reaches the oldest deleted mail (`STEP-08` §8.5). The run waits for your number; the script refuses `--apply` without one | `STEP-08` (✅ built 2026-10-07 — the run is Harsh's) |
| **D6** | Who is "us" | ✅ **Answered 2026-10-05:** `mrrohitswerashi@gmail.com` — the connected Gmail and Calendar | `STEP-04` |
| **D7** | Which model thinks, and the daily cap | **Sonnet-class; Opus-class for high stakes; $5/day** | `STEP-12` |
| **D8** | Screen reminders out of hiding? | **Yes — in the morning brief first** | `STEP-14` |
| **D9** | Where and when the morning brief arrives | **Dashboard, 08:00 IST** | `STEP-15` |
| **D10** | One branch before building | ✅ **Merged 2026-10-05, on your instruction.** You push the whole batch at once, later; Harsh deploys after | `STEP-00` |
| **D11** | The current per-sweep LLM Decision Maker until the expert replaces it | **Keep it, behind the change gate** | `STEP-02` |
| **D12** | Ten minutes of labels for the golden set | **Yes** — ⏳ until you answer, the defaults hold: applied 2026-10-06 | `STEP-01` (built on the defaults; not blocked) |
| **D13** | Once calibration runs again, may it mute a rule or move a threshold on your account without your approval? | **No** — shadow: it logs what it would do; you arm it per tenant, after `STEP-18` B22–B24 | `yc2_w27/M18` (shadow — ✅ built 2026-10-06, not deployed) · arming ⏳ |
| **D14** | When STEP-04's repair retires the cards whose subject is you, do you read its list first? | **Yes** — Harsh runs the dry run, you read the list, then `--apply`; every retirement is a `card_event` | `STEP-04` |
| **D20** | A kept mail with no signal — does it enter memory with its L1 extraction (its words), or as names and dates only? | **With its extraction** — it was already read, so no model call; the asks the expert needs are in it. Default applied 2026-10-06 (*"step 5 start karo"*) | `STEP-05` |
| **D21** | Is a memory write with no model read (an archived mail's metadata) billed as a message read? | **No** — only what a model read is billed. Default applied 2026-10-06 | `STEP-05` |
| **D22** | STEP-05's draft 3.7 — a screen item creates a person the graph does not have? | **No, dropped** — nodes are listed org-wide and a private WhatsApp contact must not appear to the rest of the org (`reason/moments/screen_memory.py:10-15`); revisit with seat-private nodes in `STEP-09`. Default applied 2026-10-06 | `STEP-05` |
| **D23** | Promote Boardy's archived introductions (rule N-02, sender `boardy.ai` — ⛔ corrected 2026-10-07 from `boardy.com`, which matches nothing) back to kept, so their words are read? | **Yes, after you read the list** — Harsh runs `scripts/promote_archived.py` dry, you read the event ids and dates it lists (never a mail's words), then `--apply`; the next chain pass reads them | `STEP-05` (✅ built 2026-10-07) — needed only after the deploy |
| **D24** | Cards that expired before STEP-06 carry no reason. Write one now ("expired before reasons were recorded")? | **No** — History keeps them as they are; the receipt counts only cards created since `0194`. Default applied 2026-10-07 (*"step 6 start karo … go"*) | `STEP-06` (✅ built 2026-10-07) |
| **D25** | A situation type that produced no card for 7 days: a red receipt, or a health-check line with its histogram? | **The line** — silence can be right; the histogram says which kind. Default applied 2026-10-07 | `STEP-06` (✅ built 2026-10-07) |
| **D26** | Run STEP-08 (the re-sync) before you have accepted the company brief? | **No** — re-read through a gate that does not know your connectors and portals would archive the same mail again (STEP-08 §8.5) | `STEP-08` |
| **D27** | Who may accept a line of the company brief: the account owner only, or admins too? | **The owner** — the brief steers every judgment. Default applied 2026-10-07: every write route is `require_account_owner` | `STEP-07` (✅ built 2026-10-07) |
| **D28** | The brief's drafter: which model, how often? | **Sonnet-class, one call to draft, one a week for what is missing** — about $0.05 each. Default applied 2026-10-07 (`Settings.company_brief_model = claude-sonnet-5`) | `STEP-07` (✅ built) |
| **D29** | Now that the brief exists, should the AI filter's archive stand (end `03` F55's re-admission)? | **No** — not until a live run measures the filter with the brief (D12c). Holds | `STEP-07` |
| **D30** | May a connector's introduction create the people it introduces? | **Yes, the brief's connectors only** — the contact is addressed in a mail to you, as any To/Cc recipient is; today an unsubscribe header drops every recipient, so the three contacts who never replied are not in memory at all (`STEP-09` §8.1). ✅ Applied on Rohit's go (7 Oct): built as recommended (`STEP-09` §9, `2c1cfbeb`) | `STEP-09` (✅ built) |
| **D31** | Does each in-motion line of the brief name its counterparty (a domain or an address) and its kind? | **Yes** — the drafter proposes it, you accept it; "every investor in the brief has a file" becomes measurable. Default: kinds only for connectors and the watchlist ⛔ Restated 2026-10-09 (STEP-11 §8.3 N1): now needed — without it no file can pick a playbook | `STEP-09` (M27.C4), `STEP-11` |
| **D32** | A new extraction field (`workstream_kind`, `stage_change`) now? | **Not now** — the brief gives the kind; if ever, before STEP-08 runs in production, or the mailbox is read twice (69 cassette answers re-recorded, two schema versions bumped) | `STEP-09` |
| **D33** | How long may a file stay quiet before it is dormant? | **Per kind, as data, labelled proposed** — 90 days investor, program, compliance; 45 intro, partner — until STEP-11 authors them. Default: 45 days for every file, as today ⛔ 2026-10-09: each playbook's stop rule, authored as a labelled prior (`STEP-11` §8.4) | `STEP-09`, `STEP-11` |
| **D34** | The legacy `unanswered_email` cards, once files exist? | **Keep them until STEP-14** — they make 15 of the 23 cards on the golden set's 32 workstream cases, every passing intro among them; measure the duplicates first | `STEP-14` |
| **D35** | May your company's own domain be declared as yours when you confirm the brief? | **Yes, once, by you** — the brief's *Us* line already shows your address; since STEP-04 a company domain is ours only by declaration (`03` F62), so a portal's notice that names your company files it under you as a counterparty (`03` F96 — golden F02, *"Nimbus Labs Private Limited is recognised"*). Declared, it is ours everywhere at once (`scripts/declare_self_identity.py`). Default: no — the stray file stays listed, carded never while its reading is in `fundraising` | `STEP-09` (F96), `STEP-04` |
| **D36** | Fix the double count before anything reads the reply time? It changes live *"they usually reply in X days"* lines | **Yes, first** — today a "normal" can rest on one reply counted twice (the person node and the thread node; golden F17, F25 — `STEP-10` §8.1) ✅ Applied on Rohit's go (7 Oct, *recommended defaults*): building as recommended | `STEP-10` (M29.C1) |
| **D37** | When is a measured number *normal*? | **n ≥ 5 at the level used**, with n and basis always shown; below it the number is shown as what it is (*"once, 1.9 days"*), never as a habit ✅ Applied on Rohit's go (7 Oct, *recommended defaults*): building as recommended | `STEP-10` (M29.C1) |
| **D38** | Bounces: keep them at the gate and put them on the file they belong to? | **Yes** — the report is parsed already, then archived by N-03 before the parser runs; a bounce becomes a fact on the investor's file and the wave, and closes `STEP-18` B6. Cards for it wait for STEP-14 ✅ Applied on Rohit's go (7 Oct, *recommended defaults*): building as recommended | `STEP-10` (M29.C3) |
| **D39** | Stage dwell (3.7) and what-if (3.11) now? | **No** — no stages exist (STEP-11 authors them); what-if cannot shift time and answers in the formula's utilities, so STEP-12 decides whether the expert gets it ✅ Applied on Rohit's go (7 Oct, *recommended defaults*): building as recommended | `STEP-10` |
| **D40** | New golden cases before the numbers? | **Yes** — the founder replying at several speeds, the production delivery-report shape, two mailboxes: the set holds one founder reply today (n = 1), no real bounce, no second mailbox. The board is re-scored and recorded ✅ Applied on Rohit's go (7 Oct, *recommended defaults*): building as recommended | `STEP-10` (M29.C6) |
| **D41** | One meaning for *reply cadence*? | **Their reply time.** The corpus's `reply_cadence` baseline is how often a person writes (the gap between their own messages); renamed for that, with every rule that reads it moved in the same unit ✅ Applied on Rohit's go (7 Oct, *recommended defaults*): building as recommended | `STEP-10` (M29.C1) |
| **D42** | Your reply time exists now. May the *reply owed* threshold come from it instead of a fixed two days? | **Yes, per counterparty where your normal with them holds, overall where only the tenant's does, and two days below both** — today a reply is "owed" after two days whatever your habit is (`outreach_situations.py:758`, `03` F107). It moves how many reply-owed situations are raised, so measure it on the golden set and read the list before it is armed. Default: two days, as today | `STEP-12` or a `STEP-10` follow-up |
| **D43** | A connector that only introduces has no file, so its rate (introduced, replied, met) shows nowhere. Show it on the brief's named entry for the connector? | **Yes** — the founder asks *"is Boardy worth it?"* of the connector, not of a file; the same three numbers, on `GET /v1/workstreams`' named list (`03` F114). Default: shown only when the connector has an ask of its own | `STEP-10` follow-up |
| **D44** | The corpus's prose still says *reply cadence*, and some of its rules were written to mean THEIR reply time (`champion.yaml:110,114`, `churn-risk.yaml:1232`, `named-contact.yaml:184-186`). Re-point them? | **Yours to decide, rule by rule** — the rename kept every number each rule actually reads (D41); re-pointing a rule to `party.reply_cadence_days` changes what it fires on. Two executable rules compare unlike units today (`03` F105) | the corpus authors |
| **D45** | Who reviews the founder playbooks? | **You**, line by line — accept, edit or reject each line, as with the company brief; a playbook is admitted (stable, approved, you named, its content hash stamped) only after it. Default: you | `STEP-11` |
| **D46** | Fix `03` F121 inside STEP-11 — the decider's prompt renders the corpus's claims, whole? | **Yes** — today every heuristic citation reaches the decider as `{"rule": null, "quote": null}` and playbook steps are cut at 300 characters, so nothing STEP-11 writes would reach the model before STEP-12; the cassettes whose prompts move are re-recorded. Default: yes | `STEP-11` |
| **D47** | Compliance written only from official sources, fetched and cited (startupindia.gov.in, dpiit.gov.in, udyamregistration.gov.in, digilocker.gov.in)? | **Yes** — every compliance line names its URL; nothing from memory. Default: yes | `STEP-11` (M31) |

---

## D1 · Does the expert's judgment decide what matters?

**The question.** The Design Atlas's RULE 02 says *"the model describes and proposes — never
decides; it never scores, routes, permits or chooses a recipient."* You have asked for the
opposite in spirit: GeniOS should reason like a 30-year expert. These meet in one place — **who
decides what matters today**.

| Option | What it means | Verdict |
|---|---|---|
| **A · Amend RULE 02** | The expert's appraisal — stakes, urgency, reversibility, the mode of intervention, each **with its reasons** — becomes an input to the lane. Numbers, permissions, recipients and send/no-send still never come from the model | ✅ **Recommended** |
| B · Keep RULE 02 as written | The lane is computed only from deterministic features; the expert's words are advice on the card | Safe, but it is the formula you rejected |
| C · Full model authority | The model picks the lane and the priority directly | ❌ No receipt you can audit, and nothing stops it flip-flopping |

**Why A.** "What matters" *is* the judgment you are asking for. A cannot drift into what the
current decider does, because every appraisal must cite its evidence, is checked against hard
facts (a meeting date, a role, a deadline), and is stored and reused until the file changes.

**Default if unanswered:** B — and `STEP-12` ships with the expert writing advice only.

## D2 · Are your founder workstreams in scope now?

**The question.** Your standing rule since 25 Sep is *Admin only; Sales and Support on hold*.
Fundraising, applications and programs, intros, compliance, hiring — the work your mailbox is
actually made of — is mostly not Admin, and investor relations sits inside Sales.

| Option | |
|---|---|
| **A · One "Founder Office" domain** — Fundraising, Applications & Programs, Networking & Intros, Compliance, Hiring, plus Admin's own meetings and commitments. Sales' `10-investor-relations` moves here | ✅ **Recommended** |
| B · Fold them into Admin | fewer folders, but Admin's 17 areas were never designed for a raise |
| C · Stay Admin only | then the cases you named in this conversation stay out of reach by design |

**Default if unanswered:** C — and `STEP-09` / `STEP-11` build only the Admin-shaped files
(meetings, commitments, payments).

## D3 · Before you review a playbook, may the expert still advise?

**The question.** The Atlas's golden replay 07 says that without *accepted* expertise the answer
is **Observation only — no action button**. Writing and reviewing six playbooks takes time.

| Option | |
|---|---|
| **A · Advise, labelled** — cards carry *"playbook not yet reviewed"* and the draft is still offered. Your org only. Every customer org keeps the Atlas rule | ✅ **Recommended** — you are the reviewer *and* the only user |
| B · Observation only until accepted | the safest; useful cards wait for `STEP-11` |

**Default if unanswered:** B.

## D4 · How long is low-attention mail kept?

Today a mail the first gate drops is deleted outright. After `STEP-03` nothing is deleted at the
gate; mail judged low-attention is kept **encrypted and unread**, so it can be read later if it
turns out to matter — the way the intro from Pankaj mattered.

**Options:** 30 · 90 · **180 days (recommended)** · 365. **Default:** 90.

✅ **Taken as 180 days, 2026-10-06.** Rohit's go on STEP-03 (*"Thik hai step 3 start karo fully"*)
came on the plan that said *"content 180 din rakha jaayega"*. Built that way: an archived mail keeps
its encrypted payload 180 days (`capture/pipeline.ARCHIVED_PAYLOAD_TTL_DAYS`), and an emitted
mail's body the same 180. If you meant another number, it is that one constant.

## D5 · How far back does the re-sync go?

After the gate stops deleting (`STEP-03`), the mailbox is re-read so the deleted mail comes back.
Fundraising and program cycles run three to six months; 60 days loses the start of most of them.

**Options:** 60 · **180 (recommended)** · 365. More history means a slower re-sync but costs
little, because only high-attention mail is read by the model. **Default:** 60.

## D6 · Who is "us"? — ✅ answered

**Rohit, 2026-10-05:** `mrrohitswerashi@gmail.com` is your address, and it is the one the Gmail and
Calendar data comes from — the org's only two connections.

`STEP-04` builds the identity service on that. It also treats the company's own domain,
`thegenios.com`, and `ceo@thegenios.com` as *us*, never as an outside company or a service — the
data shows `ceo@thegenios.com` only as a recipient of your own mail. Nothing more is needed from
you here.

## D7 · Which model thinks, and the daily cap

| Option | |
|---|---|
| **A · Sonnet-class for every expert pass; Opus-class for high-stakes files** (investors, a compliance step with a deadline, anything irreversible); a cap of **$5 a day** for this org, with the overflow becoming a "think later" queue rather than a dropped file | ✅ **Recommended** |
| B · Haiku for everything | cheapest; the judgment is the point, so it is the wrong place to save |

**Default:** A without Opus.

## D8 · Screen reminders out of hiding?

65 screen reminders and pieces of advice have been built and hidden. **Recommended:** show them
inside the morning brief first; in-the-moment popups only after a week of brief feedback.
**Default:** stay hidden.

## D9 · Where and when the morning brief arrives

**Recommended:** the dashboard's Today view at 08:00 IST. Email or WhatsApp later, if you want
it. **Default:** dashboard only.

## D10 · One branch before building — ✅ merged; the push is batched

**Rohit, 2026-10-05:** *"Harsh MVP se pull le lo — Step 00 karo."* Done locally: `origin/harsh/mvp`
(13 commits, 2–4 Oct) merged into `speedrun008` with no conflicts. The two branches overlapped
only in `api/routes.py` and `deliver/card_builder.py`, in disjoint hunks. Results are in `STEP-00`.

**Rohit, the same day:** *"ek saath mein saari cheezein push kar dunga."* The push is **batched**.
Each step is fixed and committed locally, and you push everything at once when the steps are done.
Then:

- **you** push — `git push origin speedrun008`. Claude does not push; the auto-mode classifier
  refuses `git push` for Claude anyway;
- **Harsh** deploys it. No migration is needed today: production and this branch are both at
  `0190`. A step that adds a migration says so in its own file.

Until that push and deploy, nothing built here reaches production. So a number a step moves
locally is measured on production only afterwards, and each step's file says which of its numbers
waits for that.

## D11 · The current per-sweep LLM Decision Maker, until the expert replaces it

| Option | |
|---|---|
| **A · Keep it, behind the material-change gate** (`STEP-02`). It stops re-deciding unchanged situations at once — churn ends and ~60% of the spend disappears — without handing anything to a formula | ✅ **Recommended** |
| B · Switch it off now | formula decides in the meantime — you rejected this |
| C · Leave it as it is | churn and cost continue until `STEP-12` |

**Default:** A.

## D12 · Ten minutes of labels for the golden set

`STEP-01` lists about 40 real items from your mailbox by sender and date only — no content — and
asks one question of each: *should this have reached you?* Your answers become the exam every
later step must pass. **Recommended: yes.** **Default:** I label them from this analysis, marked
as mine, and you correct them later.

**Five smaller questions came out of the 2026-10-05 check of `STEP-01`** (its §9). Each has a
default, so none blocks the build:

| | Question | Default if you say nothing |
|---|---|---|
| a | Label the ~40 items yourself, or accept mine, marked as mine? | mine, marked; you correct later |
| b | Sender and date only — or may the sheet show subjects and card headlines too? `STEP-01` §4 already goes slightly beyond sender and date | sender and date only |
| c | May the live recording spend model money on the synthetic set, and on which model? | no spend: the cassettes are my own writing, marked as such |
| d | Score *"in the morning brief only"* as not expressible until `STEP-15` builds the brief? | yes |
| e | May a case file carry a production `event_id` (an opaque id, no content)? | no — synthetic ids only |

✅ **The defaults were applied on 2026-10-06, when `STEP-01` was built** — every one can still be
changed, and nothing waits on it:

- **a** — all 40 rows of `golden-labels.md` carry my answer and say `claude` (22 *yes*, 8 *brief
  only*, 10 *no*). Change a row and its case must follow: `tests/replays/test_founder_cases.py`
  fails until it does.
- **b** — each row is a sender and a date; no subject, no text.
- **c** — no spend. All 40 cassettes say `ideal_reader`: a faithful reading of each prompt, written
  by me. One live pass would cost **≈ $0.63** on Haiku 4.5 at list price (288 calls,
  `scripts/golden_eval.py --dry-run`); it runs only with a key and `--spend-ok`.
- **d** — the 8 *brief only* rows are counted *not expressible* until `STEP-15`.
- **e** — synthetic ids only.

## D13 · Once calibration runs again, may it mute or move a threshold without you?

**What it is.** The weekly calibration (`feedback/calibrate.py`) scores each rule from your "wrong"
presses. Below a precision floor it **mutes** the rule, and it nudges score thresholds ±5 a week.
It has failed on every run since 10 Sep, so it has never done either. The fix is one line
(`STEP-18` B1). That line alone switches all of this on, unattended.

**What the 2026-10-05 test on a scratch database found** once it applies anything (`STEP-18`
B22–B24):

- a muted rule's cards vanish and nothing explains why;
- a mute never lifts;
- any applied mute or nudge hides **every** open card of that pack — even a nudge meant to show
  more. In the test the queue went from 5 to 0.

| Option | |
|---|---|
| **A · Shadow** — it runs, and records what it would mute or nudge; nothing changes until you switch it on for a tenant | ✅ **Recommended.** Built in `yc2_w27/M18`, whatever you decide |
| B · Let it apply | not before B22–B24 are fixed |

**Default:** A.

✅ **A is built** (`yc2_w27/M18`, `184269a0`, 2026-10-06; not yet deployed): calibration completes on
Postgres and records what it would mute or nudge; it applies nothing unless `calibration_apply` is
switched on for a tenant, and that switch is on for no one by default. ⏳ **Your decision** is
only the arming — per tenant, and not before `STEP-18` B22–B24.

## D14 · STEP-04's repair — do you read the list before it retires your cards?

STEP-04 stops the engine making you the subject of a card, a thread or a "waiting" line. The ones
already in production stay until something retires them: `scripts/repair_self_identity.py`. By
default it only **lists** what it would change — the nodes of yours typed as a service or an outside
company, the threads named after you, the open cards and signals whose subject is you.

| Option | |
|---|---|
| **A · You read the dry run, then Harsh applies it** — each retired card gets a `card_event` saying why, so it can be audited and rebuilt | ✅ **Recommended** |
| B · Harsh applies it straight after the deploy | faster; a card you still wanted is retired without you seeing the list |

**Default:** A. Nothing blocks the build — the decision is needed only at the repair, after the deploy.

## D20–D22 · STEP-05 — what enters memory, what is billed, who the screen may create

Asked 2026-10-06 with STEP-05's check (`STEP-05` §8); Rohit's reply was *"step 5 start karo"*, so the
defaults hold until he says otherwise.

| | Options | Default |
|---|---|---|
| D20 | A · with its L1 extraction, at the confidence it scored, marked below the floor · B · names, dates and thread only (the draft's skeleton) | **A** — Neel Jain's question and Manik's traction ask are in the extraction; B would put the names in memory and leave the asks out |
| | ⛔ **Built 2026-10-07, one change named:** "at the confidence it scored" has nothing to read — a floor refusal's confidence is never composed (`03` F69). A mail below the floor enters at one relevance under the ranking floor, and that relevance on every claim is the whole mark | |
| D21 | A · not billed · B · billed as a message read | **A** — no model read it |
| D22 | A · drop 3.7 · B · a screen item creates a weak person node, visible org-wide | **A** — B breaks a written privacy rule; graph nodes have no visibility of their own |

## D23 · STEP-05 — promote Boardy's archived introductions?

Built 2026-10-07 (`STEP-05` §9). The gate archives Boardy's introductions on their unsubscribe header
(N-02, `03` B5: the header is the sending service's, not a mailing list's). Since STEP-05 an archive
enters memory as names and dates only — who introduced whom, in which thread — and its words stay
unread. Promotion is how they get read: the mail goes back to the ledger as kept, and the next chain
pass reads it as a re-read the gate does not archive again.

| | Option | Verdict |
|---|---|---|
| **A** | Harsh runs the dry run (`scripts/promote_archived.py --org … --rule N-02 --sender-domain boardy.ai`), you read what it lists — event ids, dates, sender domains, never a body — then `--apply` | ✅ **Recommended** |
| B | Promote every N-02 archive, not only Boardy's | reads every newsletter with an unsubscribe header too — one model call each, and most are what N-02 was written for |
| C | Leave them archived | the people Boardy introduced stay names without the reason they were introduced |

**Default:** A — nothing is promoted until you have read the list.
