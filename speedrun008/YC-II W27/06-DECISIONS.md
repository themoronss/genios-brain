# 06 · Decisions — only you can make these

**Written for:** Rohit. Each decision has a recommendation and a default. If you say nothing, the
default holds, and the step that depends on it says so in its own file.

| # | Decision | Recommendation | Blocks |
|---|---|---|---|
| **D1** | Does the expert's judgment decide **what matters**? | **Yes** — an amendment to the Atlas's RULE 02 | `STEP-12`, `STEP-13` |
| **D2** | Are your founder workstreams in scope now, beyond "Admin only"? | **Yes** — one "Founder Office" domain | `STEP-09`, `STEP-11` |
| **D3** | Before you review a playbook, may the expert still advise? | **Yes, labelled** — your org only | `STEP-12` |
| **D4** | How long is low-attention mail kept? | **180 days, encrypted** | `STEP-03` |
| **D5** | How far back does the re-sync go? | **180 days** | `STEP-08` |
| **D6** | Who is "us" | ✅ **Answered 2026-10-05:** `mrrohitswerashi@gmail.com` — the connected Gmail and Calendar | `STEP-04` |
| **D7** | Which model thinks, and the daily cap | **Sonnet-class; Opus-class for high stakes; $5/day** | `STEP-12` |
| **D8** | Screen reminders out of hiding? | **Yes — in the morning brief first** | `STEP-14` |
| **D9** | Where and when the morning brief arrives | **Dashboard, 08:00 IST** | `STEP-15` |
| **D10** | One branch before building | ✅ **Merged 2026-10-05, on your instruction.** You push the whole batch at once, later; Harsh deploys after | `STEP-00` |
| **D11** | The current per-sweep LLM Decision Maker until the expert replaces it | **Keep it, behind the change gate** | `STEP-02` |
| **D12** | Ten minutes of labels for the golden set | **Yes** | `STEP-01` |

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
