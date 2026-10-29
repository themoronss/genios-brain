# P1 · Orchestrator · 06 · Onboarding a new customer

**What this file answers:** what a new customer goes through today; what is missing; what onboarding should be; what it costs by company size; and when GeniOS is ready to onboard customers without a person in the loop.

**Measured on:** the design partner's org, whose production data was started from empty on 21 Oct and whose mailbox was captured again on 22 Oct. That is a real first week of a new tenant. The numbers are in [01](01-WHATS-EXACTLY-THERE.md).

---

## 1 · What a new customer goes through today

| # | Step | What happens | Measured on 22 Oct |
|---|---|---|---|
| 1 | Sign up | The org row and the owner's seat are created. The time zone is empty until the 6-hour tick infers it from the times mail is sent | — |
| 2 | Connect Gmail and Calendar | Composio OAuth. The status poll mirrors the connection into `connections` and queues one durable sync job for the sources never read | Job queued 15:31 UTC |
| 3 | The first pull | Gmail, then Calendar, newest first. The window is the founder's pick: 60 days by default, 180 here. It stops at about 5,000 messages per source and checkpoints every page. L2 reads what has landed every 6 rounds | 2,240 mails backfilled in 2 h 18 min (about 16 a minute), and 136 calendar events. The screen counted about 2,600 by the end, with the mail that arrived meanwhile. The first attempt failed; the job resumed from its checkpoint |
| 4 | Switch-on | `provision_intelligence` and `make_tenant_live` switch on the defaults ([01](01-WHATS-EXACTLY-THERE.md) §4) | The old sales, general, admin and support packs active; the brain off |
| 5 | The first reasoning | L2 drains everything in chunks of 500, `run_all` runs once, cards are built, and the screen says **"Ready"** | "Ready" at 19:10 UTC, **3 h 39 min after connect**. 14 cards from the old lanes; 3 files reviewed by the brain; no goal |
| 6 | The first brief | Composed at the tail of a sweep, by template | 16:20 UTC, before "Ready" |
| 7 | Days 2–7 | The 15-minute tick and the 97-minute chain, back to back | About 11 files judged a day (the judge's $2 cap). The first brief review and the first goal proposals on days 5–6. The 24 Oct brief missing |
| | **Cost** | | **$25.44 on day one** (of which $14.92 is L1 reading the backfilled mail), then about **$5.70 a day** |

**This org's brain works only because a person switched it on**: expert review, L2 reasoning, L2 cards and Founder Office (21 Oct), with the sales and support packs disabled (3 Oct).

## 2 · What is missing for a new customer

| # | Gap | Why it matters | Fixed by |
|---|---|---|---|
| G1 | The brain is off by default | A new founder gets old rule cards, not judgment | D-P1-9; [05](05-HOW-AT-PRODUCTION-LEVEL.md) §4 |
| G2 | The wrong packs for a founder | Sales and support rules run on a founder's mailbox; Founder Office is off | P3 §3; the runbook (R6) |
| G3 | No first pass that understands the company: who we are, the work in motion, the goals | "Ready" means the old chain ran once (F15) | P1-3 (the Onboard loop); GeniOS-013 Step 5 |
| G4 | A first look at every file takes over three weeks | The judge's $2 a day allows about 11 files (F11) | The one-time onboarding budget (D-P1-3, `07` D2) |
| G5 | Nothing useful appears until the whole window is captured | 180 days took 2 h 18 min; 365 days would take hours more | Waves (D-P1-10) |
| G6 | The progress screen isn't honest | It says "Ready" with 3 files reviewed | §3 below: phases named after what GeniOS understands |
| G7 | The time zone is guessed later | Times are read in UTC until the 6-hour tick infers the zone (F6) | Ask at signup or take it from the browser, and confirm it on the company page |
| G8 | Goals come on day 5–6, and need a confirmation step the onboarding doesn't have | Intelligence can't be organised by goal in the first week | P1-3 phase 5; P2, P4 and P5 for the goal object, reasoning and cards |
| G9 | Each extra tenant slows everyone | One tenant's chain fills the day (F9, F14) | R2 now; the worker process and the queue ([05](05-HOW-AT-PRODUCTION-LEVEL.md) §2) |
| G10 | Everything that made this org work was done by hand | It can't be repeated for ten customers | The runbook now (R6), defaults later |

## 3 · The target: the Onboard loop, in waves

Each phase is a checkpoint with a ledger row. A crash resumes in the phase it stopped in, and nothing judged is paid for twice.

| Phase | What GeniOS does | What the founder sees | Target, from connect |
|---|---|---|---|
| 0 · Connect | OAuth, the job queued, the tenant's policy rows set (caps, model, hours) | "Connected. Reading your last 30 days first" | 2 min |
| 1 · The last 30 days | Capture, newest first | Mails read, as a count | 30 min |
| 2 · Who you are | The company page: name, our addresses, our time zone, what the company does, who the founders are. Built from sent mail and the signup | "This is how we understand your company": confirm or correct | 35 min |
| 3 · Who is who | The parties | — | 40 min |
| 4 · Your work | The situations in those 30 days. Each live one is judged: ours first, then the nearest dates | "N things in motion", by kind | 90 min |
| 5 · Your goals | Goals proposed from the situations, each with its target, its evidence and the situations that serve it | "We think you are driving toward these": confirm, edit or drop | 100 min |
| 6 · First intelligence | Cards from the pages and from the goals' missing steps, only the ones that need the founder now, ranked | The first cards | **2 h** |
| 7 · History | The rest of the window (365 days) captured in the background. Older threads are placed into the situations already found, or into new ones. Only situations that history changes are judged again, and the goals are refined | "Reading your older history; it adds context and may sharpen your intelligence" | **24 h** |
| 8 · Daily life | Evolve on each wake-up; Maintain at night; the morning view at 08:00 company time | — | from day 2 |

**Three rules hold throughout:**
- **Nothing is "confirmed" until the founder confirms it.** A proposed goal can organise cards, labelled "proposed" (`07` D1).
- **The founder never waits for history.** Wave 2 can change a card; it never holds one back.
- **Budget is split by wave:** at most half for wave 1, the rest for wave 2. If the cap is hit, the skipped situations are listed, and the daily Evolve picks them up in priority order.

## 4 · What onboarding costs and takes, by company size

**The basis:**
- The notebook measured, on this org's six months: 378 situations judged for $6.37, and $8.41 for the whole build. That is about $0.017 per situation plus about $2 fixed, with about one situation per five mails.
- A worker judges one situation in about 30 seconds.
- Capture was measured at about 16 mails a minute.

Rows marked "est." are scaled from those figures, not measured.

| Company | Mail in the window | Situations | Reasoning cost, once | Judging, 8 workers | Capture at today's rate |
|---|---|---|---|---|---|
| A small founder, 6 months | ~1,000 (est.) | ~200 (est.) | ~$5.50 (est.) | ~13 min | ~1 h |
| **This org, 6 months** | **~1,800 (measured)** | **378 (measured)** | **$8.41 (measured)** | **~25 min (measured)** | **2 h 18 min (measured)** |
| A founder, 365 days | ~3,600 (est.) | ~700 (est.) | $10–15 (est.; old dormant work is placed, not fully judged) | ~45 min | ~4 h |
| A small team, 3 mailboxes, 365 days | ~10,000 (est.) | ~1,500 (est.) | ~$25–30 (est.) | ~1.5 h | ~10 h |

**What this means:**
- **These are one-time costs, paid when a customer connects.** After that, reasoning costs under about $20 a month for a founder ([05](05-HOW-AT-PRODUCTION-LEVEL.md) §6), plus reading the new data (today about $57 a month).
- Capture, not reasoning, is the long pole. That is why waves exist: wave 1 needs only about 30 days.
- The reasoning cap (D-P1-3) is $10 for six months and $15 for 365 days for a founder. A team gets its own number before it is onboarded.
- **L1 reading the mail at capture** ($14.92 for this org's 180 days) is the biggest single onboarding cost today. Whether the notebook path still needs L1's per-mail extraction, or reads the clean text directly as the notebook does, is a P2 question. The answer could halve onboarding's cost.

## 5 · Readiness: when GeniOS can onboard customers without a person in the loop

All eight must hold. Each is checked by a test or a drill, not by reading code.

1. **The new path passes the acceptance set** on the golden tenant ([10](../10-ACCEPTANCE.md) §5).
2. **The onboarding drill passes** (P1-10):
   - first intelligence within 2 hours;
   - everything judged within 24 hours;
   - cost within D-P1-3;
   - every crash and restart resumed, without paying twice.
3. **Two tenants at once** (P1-9), then the load drill ([05](05-HOW-AT-PRODUCTION-LEVEL.md) §8) at 2, 5 and 10 tenants. The freshness promise holds at each size.
4. **New tenants get the new path with no switch flipped by hand** ([05](05-HOW-AT-PRODUCTION-LEVEL.md) §4). The runbook (R6) is retired.
5. **Health, alerts and the switch registry are live**, and each alert has fired once in a drill.
6. **Erasure removes a test tenant completely**, including the new tables ([05](05-HOW-AT-PRODUCTION-LEVEL.md) §10, P2).
7. **The founder can confirm the company page and the goals, and act on cards**, on the screens (P5).
8. **A support view per tenant** shows:
   - each loop's state;
   - its last runs;
   - what was skipped;
   - and lets support pause, resume or re-run a phase.

## 6 · Until then: design partners, by runbook (D-P1-9, R6)

1. **Create the tenant** and set its time zone (ask; don't wait for the inference).
2. **Before connect**, set:
   - the window to 365 days;
   - the packs that fit: Founder Office on; sales and support off unless the company sells or supports;
   - the brain on: expert review, L2 reasoning, L2 cards;
   - the onboarding budget, and the judge's daily budget raised for the first week (`07` D2).
3. **Connect**, watch the job, and read the first day's health row.
4. **Day 2:** check how much has had its first look, and the cost.
5. **Day 7:** review with the founder: are the goals confirmed, and are the cards useful?

This is temporary. Every step of it becomes a default once §5 holds.

## 7 · Later: a team member, or a new tool

- **A team member connects their mailbox.** This is an Onboard run for that seat, not a new tenant:
  - their window is captured;
  - their threads are placed into the company's existing situations (or new ones), with the seat's visibility;
  - only the situations touched are judged.
- **A new tool connects** (Slack, Notion, HubSpot …). The same: one onboarding wave for that source, placed into the situations already known.
