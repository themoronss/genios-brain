# GeniOS-012 · From the ideal cards to the live product: every failure, layer by layer, unit by unit, and the build that fixes it

**Written for:** Harsh (CTO) and the coding agents he assigns. Rohit reads §1, §3 and §5.

**The question (Rohit, 23 Oct):** a Claude session read his Gmail and Calendar and produced 10 goals and 20 cards, now on `brain.thegenios.com/preview` (owner-only). The live product does not produce them. *Where does it fail, why, in which layer, part and unit, how is each failure fixed, and how does the product get ready for every customer and every kind of situation?*

**Measured at:** `origin/speedrun008` `71e4c4a8` (brain) and `origin/main` `ff13896` (dashboard), on 23 Oct 2026, by four read-only crosschecks of the code, one per layer group. Production was **not** read (that needs Rohit's yes). Every line number in this folder is from that head; re-check before editing if the head has moved.

**How this folder relates to GeniOS-011:** GeniOS-011 is the audit (255 items) and the master plan (43 steps, `S01`–`S43`). This folder takes the one target Rohit cares about, the `/preview` cards and goals, and goes one level deeper: the path a mail takes through the code, each place it is lost (D1–D32), and each unit that fixes it, with briefs an agent can build from. It reuses GeniOS-011's unit ids (`S09.U1` …) and adds 21 new units (`U12-01` … `U12-21`) found by this crosscheck. It also corrects GeniOS-011 in 13 places (§4).

---

## §1 · The answer in one page

**Why the local session got it right:** nothing stopped it; it read 11 months, including the mail that looks like newsletters, the founder's own sent mail, and the calendar; it filed by piece of work; it judged like a founder's chief of staff, with investor and programme know-how; it saw across threads; it had goals first; it wrote each card for a human. ([01](01-WHAT-THE-LOCAL-SESSION-DID.md))

**Why the live product doesn't, layer by layer** ([02](02-THE-PATH-OF-ONE-MAIL.md) traces one mail through 32 loss points):

| Layer (product vocabulary) | What fails | Loss points |
|---|---|---|
| **Before L1** (run gate, switches) | the scheduled sweep skips an expired org (Rohit's since 21 Sep), so only Sync now makes cards; the expert review, the L2 judgment and Founder Office are off by default; the script meant to switch them on silently drops them | D1–D3, D28 |
| **L1 Signals** | 60-day window; intro platforms and portals archived as newsletters; the junk judge never sees the sender; no word for intro, meeting, investor interest or application; calendar meetings never become usable events (0 of 22); the founder's own numbers in sent mail are never written | D4–D13 |
| **L3 Context Graph** | archived and private mail is never filed and nobody counts it; one counterparty holds several live situations (keyword domain × 45-day generation); admission sees only part of the file and its HOLD keeps the old lane in charge; a wave to many people is never one subject; any reply closes every ask; a bounce erases the waiting card; equal-rank conflicting numbers overwrite each other; a rebuild deletes human decisions and re-mints ids | D14–D23 |
| **L2 Qualification** (Plane D + Plane R) | a quiet file is never looked at again; the judgment reads one file only; most real-model answers are held and print an engineer sentence (the fix sits on an unmerged branch); a judged file needs a pre-existing "home" situation in an activated domain; template cards spend the daily cap first; Founder Office playbooks are unreviewed and refused, five of six have no trigger | D24–D31 |
| **Goals** | no goal object; goals are free-text brief lines; no card carries a goal | — |
| **L5 Delivery + dashboard** | the subject is the move cut to 60 characters with a "Needs a decision —" prefix; steps, result and draft are dropped or never rendered; the "why" repeats across cards; no goal, no category; the Goals page shows lines, Home shows none | D32 |

**How it gets fixed:** eight steps, each ending in a gate measured on Rohit's org in production ([09](09-STEPS.md)):

| Step | What | Cards expected after it (cumulative) |
|---|---|---|
| 0 | know what is deployed (readings, no code) | — |
| 1 | the chain runs; the expert is on | `f4` |
| 2 | 365 days; founder senders kept; fetchers armed | + `i6`, `b1`, `b3`, `l1` |
| 3 | founder words; meetings; own claims captured | + `f1`, `f2`, `i3`, `b2` |
| 4 | one file, one live situation; waves; bounces; conflicts; stable ids | + `i5` (and `i4`, `s2`, `p1`, `i2` as situations) |
| 5 | judge like the expert; Founder Office; quiet files; cross-thread facts; held cards fixed; L2 cards on, type by type | + `i1`, `i2`, `i4`, `s1`, `s2`, `f3`, `c1`, `c2`, `h1` |
| 6 | goals as objects; L2 proposes, one click approves; categories | + the 10 goals, the 2 proposals, `i1`'s goal line |
| 7 | the card writer; the dashboard reads it all | + `p1`; all 20 readable as on `/preview` |
| 8 | the same for every customer, with no hand action | — |

**Finish line (Gate 7):** `preview_parity.py` shows ≥ 18 of 20 `/preview` cards and 10 of 10 goals live on Rohit's org, or each missing one has a named reason Rohit accepts; `ideal_card_gap.py` shows the subject, steps, draft, goal and category on every matched card.

**Shortcut?** A brain route that runs the LLM directly over the mailbox could fill the pages faster, but it skips admission, the claim check, identity, budgets and learning. It is a bridge, not the product, and is not built ([01 §6](01-WHAT-THE-LOCAL-SESSION-DID.md)).

---

## §2 · Read in this order

| # | File | What it holds | For |
|---|---|---|---|
| 00 | this file | the answer, the order, the decisions, the corrections | everyone |
| 01 | [01-WHAT-THE-LOCAL-SESSION-DID](01-WHAT-THE-LOCAL-SESSION-DID.md) | the target: the method, the numbers, the 15-field card contract, why it worked, what not to copy | everyone |
| 02 | [02-THE-PATH-OF-ONE-MAIL](02-THE-PATH-OF-ONE-MAIL.md) | one mail through the code; the 32 loss points with file and line | Harsh, agents |
| 03 | [03-RUN-GATE-AND-SWITCHES](03-RUN-GATE-AND-SWITCHES.md) | before L1: the plan gate, the switches, the compile gate, deploy visibility | Harsh, agents |
| 04 | [04-L1-SIGNALS](04-L1-SIGNALS.md) | window, gate, words, calendar, own claims, connector hardening, the resync runbook | agents, Harsh |
| 05 | [05-L3-CONTEXT-GRAPH](05-L3-CONTEXT-GRAPH.md) | filing, one live situation, admission, waves, replies, conflicts, bounces, rebuilds, memory | agents |
| 06 | [06-L2-PLANE-D-AND-R](06-L2-PLANE-D-AND-R.md) | Founder Office, triggers, judgment to card, the dossier, reply-vs-ask, held cards, budgets, switching L2 on | agents, Rohit |
| 07 | [07-GOALS](07-GOALS.md) | the goal object, proposals, links, progress, categories | agents, Rohit |
| 08 | [08-L5-CARDS-AND-DASHBOARD](08-L5-CARDS-AND-DASHBOARD.md) | the card writer, the card's fields, the Cards / Goals / Home pages, measuring against the ideal | agents |
| 09 | [09-STEPS](09-STEPS.md) | the order: steps 0–8, owners, dependencies, gates, files shared between units | Harsh |
| 10 | [10-UNIT-BRIEFS](10-UNIT-BRIEFS.md) | paste-ready briefs for every new unit, with the common preamble | agents |
| 11 | [11-SCENARIOS](11-SCENARIOS.md) | every scenario (founder's work, any customer, the pitch scenes): what it needs, its status, its test | Harsh, Rohit |
| 12 | [12-PRODUCTION-READY](12-PRODUCTION-READY.md) | hand actions → onboarding; the release gate; quality and cost per customer; privacy; ops; the checklist | Harsh, Rohit |
| 13 | [13-LOG](13-LOG.md) | append-only record of what was done and measured | everyone |

Status key used everywhere: ✅ built and merged on `origin/speedrun008` · ⏸ built and held · 🔨 being built · ⬜ open · 🔒 waiting on a named person.

---

## §3 · What only Rohit decides (a skipped decision takes its default)

| # | Decision | Default (recommended) | Blocks | File |
|---|---|---|---|---|
| 1 | S02.U3: switch on `expert_review`, `l2_reasoning`, Founder Office for your org | yes | Step 1 | [03](03-RUN-GATE-AND-SWITCHES.md) |
| 2 | S02.U4: accept the brief lines naming your senders and work in motion | yes, from the list on `/preview` → Company | Step 2 | [03](03-RUN-GATE-AND-SWITCHES.md) |
| 3 | S09.U3: the history window | 365 days | Step 2 | [04](04-L1-SIGNALS.md) |
| 4 | **Spend:** the 365-day resync (estimate first), the L1 live pass (S07.U3), the R-7/R-9 live pass (S07.U2, ~$5), the catch-up budget (U12-17), the card-writer probe (S34.U3) | yes, each with its probe and cap | Steps 2, 5, 7 | 04, 06, 08 |
| 5 | S12.U1: the L1 words, and S13.U2 the bundle road | introduction, meeting, investor_interest, application_status; road A | Step 3 | [04](04-L1-SIGNALS.md) |
| 6 | S20.U1: STEP-13b | go | Step 5 | [06](06-L2-PLANE-D-AND-R.md) |
| 7 | S23.U1: unreviewed playbooks | label and use | Step 5 | [06](06-L2-PLANE-D-AND-R.md) |
| 8 | D57: a quiet file with an open ask comes back | yes, at most once per the kind's prior gap | Step 5 | [06](06-L2-PLANE-D-AND-R.md) |
| 9 | U12-13: the work kind for customers/prospects | `customer` | Step 5 | [06](06-L2-PLANE-D-AND-R.md) |
| 10 | S26.U1: goals | L2 proposes one per piece of work, one-click approve | Step 6 | [07](07-GOALS.md) |
| 11 | N2: `category` (and the progress basis) added to the architecture's goal object | yes, your eight as Admin's default list | Step 6 | [07](07-GOALS.md) |
| 12 | D-12-1: does a lapsed customer still get read-only cards? | no cards, but the alert (U12-01) | Step 8 | [03](03-RUN-GATE-AND-SWITCHES.md) |
| 13 | D-12-2: may the owner's own judgment read their private events? | yes, owner seat only, never on shared cards | Step 4 | [05](05-L3-CONTEXT-GRAPH.md) |
| 14 | The public brain repository (real names in older docs) | make it private | — | [12 §E](12-PRODUCTION-READY.md) |
| 15 | Every UI change: approve the local render against `/preview` first | — | Steps 6–8 | [08](08-L5-CARDS-AND-DASHBOARD.md) |

---

## §4 · What this crosscheck corrects in GeniOS-011

GeniOS-011's files belong to the session building it; they are not edited here. These corrections apply wherever GeniOS-011 says otherwise:

1. **`scripts/activate_tenant.py` cannot switch on `expert_review`, `l2_reasoning` or `l2_cards`.** `_plan_for` (`:155-179`) drops any L4 feature not in `PLAN`. 07 Phase A step 5 relies on it. Use the admin routes ([03 Part B](03-RUN-GATE-AND-SWITCHES.md)) until U12-02 ships.
2. **The resync runbook:** the backfill is `POST /connections/{gmail}/backfill` (full fetch), **never** `/integrations/gmail/sync` (which keeps rule-junk as a list snippet). `resync_deleted_mail.py` only frees keys; it is run as dry run → `--apply --days N` → backfill → `--finish` ([04 Part A](04-L1-SIGNALS.md)).
3. **Admission is not shadow-only.** Its HOLD stops the L2 judgment becoming the file's review (`reason/l2/sweep.py:379-383`), so the old lane stays in charge.
4. **`api/routes.py:797-823` is not the situation writers' order.** It is the start of `_run_l2_chain`; the nine writers run inside `context/runner.process_pending` (from `:703`).
5. **Migration 0176 and `context/lane_health.py` are not the open lane.** 0176 widens the CHECK for `delivery_failure`; `lane_health` lists dormant readings. The open lane is `unclassified_observations` (migration 0079, `capture/semantic/open_lane.py`).
6. **The signal vocabulary has 16 members**, not 15 (the `contracts/signal.py` docstring is stale).
7. **Situation ids are uuid4** (`situations.py:1220`); the `backfill.py:126-129` docstring ("a content hash") is false.
8. **The automatic history replay rebuilds destructively** whenever it creates a deal node (`backfill_layer2` `:428-447`), deleting human resolutions.
9. **The compile gate** (`runner.py:2029`): with no activated L3 domain and no L1 semantic row, a judged file is never decided. New (U12-03).
10. **Evidence fetchers use a 60-day window** even after the connection is widened (`_need_fetchers` builds `config={}`). New (U12-04).
11. **STEP-13b's migration `0250_expert_review_attempts.sql` collides** with `0250_screen_followup_read_path.sql` on the head; the port must renumber it.
12. **S34.U3 (the card writer) is on no branch:** it is uncommitted files in `.claude/worktrees/g011-S34U3`, and it claims migration 0252. Goals (S28.U1) must take a later number.
13. **The goal migration reservation (≥ 0251) is stale:** 0251 is `daily_health`.

---

## §5 · What Harsh does first (production, no new code)

1. Step 0 of [09](09-STEPS.md): the deployed SHA, the readings (with Rohit's yes), the two activation rows.
2. S02.U1: Rohit's org on a non-expiring internal plan (SQL in [03 Part A](03-RUN-GATE-AND-SWITCHES.md)).
3. Deploy `origin/speedrun008` (a fast-forward of `harsh/mvp`; migration 0251 at boot; set `GENIOS_BUILD_SHA`).
4. With Rohit's yes: the admin-route calls of [03 Part B](03-RUN-GATE-AND-SWITCHES.md), and log each flip in [13-LOG](13-LOG.md).
5. Then the 365-day resync by the runbook in [04 Part A](04-L1-SIGNALS.md), after Rohit's spend yes.

Everything else is code units: hand them to agents with the briefs in [10](10-UNIT-BRIEFS.md), in the order of [09](09-STEPS.md), one writer per file.
