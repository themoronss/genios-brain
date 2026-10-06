# 06 · Decisions — only you can make these

**Written for:** Rohit. Each decision has a recommendation and a default. If you say nothing, the
default holds, and the step that depends on it says so in its own file.

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| **D1** | Does the expert's judgment decide **what matters**? | **Yes** — an amendment to the Atlas's RULE 02 | `STEP-12`, `STEP-13` |
| **D2** | Are your founder workstreams in scope now, beyond "Admin only"? | **Yes** — one "Founder Office" domain | `STEP-09`, `STEP-11` |
| **D3** | Before you review a playbook, may the expert still advise? | **Yes, labelled** — your org only | `STEP-12` |
| **D4** | How long is low-attention mail kept? | ✅ **180 days, encrypted** — on Rohit's go on STEP-03 (6 Oct), whose plan said 180 | `STEP-03` (✅ built) |
| **D5** | How far back does the re-sync go? | **180 days** | `STEP-08` |
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
| D21 | A · not billed · B · billed as a message read | **A** — no model read it |
| D22 | A · drop 3.7 · B · a screen item creates a weak person node, visible org-wide | **A** — B breaks a written privacy rule; graph nodes have no visibility of their own |

