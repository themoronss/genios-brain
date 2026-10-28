# 04 · How it runs smoothly: rollout, measurement, cost, storage, new customers, more tools

**Written for:** Rohit and Harsh.
**What "smooth" means here:**
1. Every change is measured before and after.
2. Every new piece is switched on for one tenant at a time and can be switched off at once.
3. Costs are known in advance.
4. A failure is visible within a day.
5. The founder is never flooded and never left in the dark.
6. A new customer needs no hand work.
7. New tools and agents plug in without a redesign.

---

## §1 · The release routine, the same for every step

1. **Build** the step beside what runs today. Unit tests and a mutation proof for every unit. Repo-wide guards once per group of 2–3 units. Full suites in CI.
2. **Gate it on the local copy** of the design partner's org, with production's models and nothing sent. Run `scripts/parity.sh` (Step 0) and write the three numbers in [08-LOG](08-LOG.md).
3. **Deploy** with the step's activation row on for **one** tenant.
4. **Next day**, run `scripts/parity.sh` read-only against production. Compare with the local numbers.
5. **Widen** to the next tenant only when the numbers held for three days.
6. **Rollback:** switch the row off. Nothing else is undone, and no migration in this plan deletes data.

**Two things to fix first, so releases are visible:**
- **CI is red** on `speedrun008` (since 23 Oct) and on `harsh/mvp` `7d2c3615`: the `golden-pg` and `database` jobs. Green CI is the floor for every step.
- **The running code is unnamed.** Production's `/health` reports `build_sha: "dev"`, so nobody can tell which code is running. Set the build SHA at deploy (U13-42).

---

## §2 · Measurement that never stops

**For the design partner (privately, because the ideal cards are real mail):**
- `scripts/parity.sh` after every deploy. It gives the card score, the work score, and the stage where each ideal item was lost.
- The result goes in 08-LOG, so the trend is visible.

**For every tenant (in the product):**
- The `daily_health` row already exists: one per org per day, with alerts for a card drop, a dark lane, a full database or an expired plan. Add the numbers that show whether the work model is healthy (U13-39):

| Number | Healthy | Says something is wrong when |
|---|---|---|
| pieces of work past their expected-by date and not judged | 0 at day end | it grows: the budget is too small, or priority is wrong |
| changes held by admission, against admitted | low and stable | it jumps: a prompt or check change broke something |
| re-judgments without new input | 0 | above 0: the fingerprint is reading noise |
| cards per piece of work | 1 | above 1: a duplicate path is still delivering |
| judgments skipped for budget | low | it stays high: raise the budget, or reading is too large |
| median dossier size | ≤ 12k characters | it grows: pieces of work need splitting |
| founder corrections a week | falling | rising: GeniOS is getting the same thing wrong |

**For releases:**
- The golden set mostly runs with a stand-in reader. That proves the plumbing, not the intelligence.
- Before each production push that changes a prompt or a check, run one **real-model pass** on the golden set, as Harsh did on 23 Oct.

---

## §3 · Cost: known in advance

| Spend | Today | After the plan |
|---|---|---|
| The brain (R-9) | $2/day cap, hit every day, ~12 judgments | Same cap at first. Each judgment reads ~3–5k tokens instead of ~17k, so the same money buys several times more judgments. The cap is then re-set from the measured cost (D2) |
| Finding silence | not possible | code only: $0 |
| Re-judging unchanged files | 16 of 20 re-judgments | 0 |
| Old flow's model calls | 5,656 calls, 10.75M input tokens since 21 Oct | 0 for a tenant once Step 6 is switched on for it |
| Onboarding | — | one-time, about $20 per tenant at today's size (D2) |

Every site keeps its own daily cap (`OWN_BUDGETS`), and a judgment that would cross it is carried to the next day, never lost. If carried work stays carried for more than a day, the health row says so.

---

## §4 · Storage: the database is already over its ceiling

On 26 and 27 Oct, `daily_health` raised `database_over_ceiling`: about 544 MB and 570 MB, against a 472 MB ceiling.

The largest tables in this org (data plus indexes):

| Table | Size | What it is |
|---|---|---|
| `graph_source_refs` | 54 MB | where each fact came from |
| `screen_session_deltas` | 47 MB | Mac-app screen captures |
| `raw_payloads` | 32 MB | encrypted raw mail |
| `graph_facts` | 25 MB | the facts |
| `expertise_packages` | 15 MB | compiled expertise packages |
| `situation_admission_decisions` | 14 MB | the old admission log |
| `event_trace` | 13 MB | per-event trace |
| `reasoning_results` | 8 MB | mostly stored dossiers |

**What the plan does to this:**
- The pages, their versions, members, links and claims are about 1 MB for 264 pieces of work.
- Step 3 shrinks every stored dossier by about five times.

**What still needs a decision (U13-41, retention, Harsh's call):**
- Keep full dossier text and per-event traces for N days only. They can be rebuilt.
- Expire screen deltas once they have been promoted.
- Keep the old admission log only while the old lanes run.

---

## §5 · A new customer with no hand work

1. **Connect** the mail and calendar (later: Slack, Drive, CRM).
2. **Identity is proposed** from the account, the sent mail and the signatures. The founder confirms it with one click (Step 5).
3. **Capture** 365 days (D4). L1 reads it.
4. **The onboarding pass** turns the history into pieces of work, within the one-time budget (Step 5).
5. **First judgments** run in priority order: overdue and goal-linked work first.
6. **Day-one screen:** confirm identity, look over the pieces of work, approve or edit the proposed goals.
7. **From then on:** the 15-minute light tick reads new mail, the 6-hour heavy tick runs the rest, and the clock runs every pass.

There is no script to run by hand and no row to insert by hand. Activation rows are written by onboarding, and the health row shows if a tenant stalls. That includes an expired plan, which already raises `plan_expired`.

---

## §6 · More tools, without redesign

A new tool needs only a connector that produces events. Its items join pieces of work as **members**. They follow a thread when one exists, otherwise L2 places them.

| Tool | Becomes |
|---|---|
| Calendar | a meeting member; its date can set "expected by" |
| Drive or Docs | a document member; its edits are new evidence |
| Slack or WhatsApp (through the Mac app) | message members on the same piece of work as the mail |
| CRM | deal members; stage changes are evidence |
| Billing | the source of truth for "one number everywhere" (`p1`) |

Nothing in L2 or L3 changes per tool. Pieces of work, playbooks and goals stay the same.

---

## §7 · Agents

- When the founder approves a move, L4 turns it into an owned task for a person or an AI agent, **attached to the piece of work**.
- The agent's result (a sent mail, a booked meeting, a filled form) comes back as new evidence on the same page. It can settle the page's loops (for example, "promise kept").
- L6 learns from whether it worked.

So an agent never works from a card's text alone. It works from the page, and its result updates the page.

---

## §8 · The founder's controls

| The founder does | What happens |
|---|---|
| Confirms or corrects a fact ("not an investor", "done") | a version written by the founder; that field is locked against the model |
| Snoozes ("Monday") | the expected-by date is set by the founder and locked |
| Marks "not relevant" | the piece of work is closed, or its card is muted; L6 records why |
| Answers a question card | the answer is saved on the page; the loop is settled |
| Approves a goal | the goal becomes live; linked pieces of work rise in priority |

---

## §9 · When something goes wrong

| What happens | What the system does | Who is told |
|---|---|---|
| The model provider is down or refuses | judgments wait at their watermark, and are retried the next pass | health row (`lane_no_data` if it lasts a day) |
| The budget runs out | work is carried to the next day; overdue work goes first | health row (judgments skipped for budget) |
| Admission suddenly holds many changes | nothing wrong is saved; the old state stands | health row (held against admitted) |
| A wrong page is reported by the founder | a correction version is written and locked; the case is logged for L6 | the founder sees it fixed at once |
| A tenant's plan expires | the sweep skips it | `plan_expired` alert |
| A tenant is deleted | all of its pages, versions, members, links and claims are erased with the org (as migration 0256 does for goals) | — |

---

## §10 · How the team works

- **Rohit** opens each step and makes the decisions in [07](07-DECISIONS.md).
- **Harsh** assigns units to agents. One writer per file. Every unit has tests and a mutation proof, and guards run per group.
- **Claude** prepares the private expected-works sheet, runs `parity.sh` on the local copy after each step, and writes the numbers in 08-LOG.
- **Docs** live in this folder, with no names, because the repo is public. Private data stays in the private local copy.
- **Each step's PR** says which step and which units it covers, and the parity numbers before and after.

---

## §11 · The weekly check: is it smooth?

1. CI green on the branch production runs.
2. `/health` names the build that is running.
3. Parity score for the design partner, compared with last week.
4. Pieces of work past their date and not judged: 0 at day end.
5. Duplicate cards: 0.
6. Founder corrections: fewer than last week.
7. Model spend per tenant: within its caps.
8. Database size: under the ceiling.

## §12 · New units this file adds

| Unit | Where | What |
|---|---|---|
| U13-39 | `platform/daily_health.py` | The numbers in §2 for pieces of work, with their alerts |
| U13-40 | `scripts/` + the release checklist | A real-model golden pass before any push that changes a prompt or a check |
| U13-41 | `platform/retention` (or the heavy tick) | Retention for dossier text, event traces, screen deltas and the old admission log |
| U13-42 | deploy config + `/health` | Set the build SHA at deploy, so `/health` names the running code |
