# STEP-15 · TO BUILD · the morning brief — what a chief of staff tells you at 8

**Owner:** Claude. **Depends on:** `STEP-12`, `STEP-13`, `STEP-14`. **Decisions:** `06` D1 (who orders
the day), D9 (where and when). **Moves:** one brief a day, read in under three minutes, with a
feedback mark on every line.

---

## 1 · What is true now `[CODE]`

| What exists | Where | What it does today |
|---|---|---|
| The executive summary ladder — one line, one minute, five minutes | `executive/summary.py` | deterministic composition; *"an empty morning says 'nothing needs you'"*; sent as the daily digest from the outbox on the heavy tick (`deliver/outbox.py:308-324`; `api/routes.py:1268`) |
| The book-level daily re-rank | `reason/brief_ranking.py:412` `daily_brief_ranking` | compares the day's decisions against each other — concentration, staleness, coverage — as **penalties** on `final_utility_bp`; on-demand API only (`api/l4_seam_routes.py:184-195`) |
| The decision brief, per signal | `executive/brief.py` `compose_brief` | situation, why, recommendation, evidence, risks, alternatives, confidence, do-nothing; no model |
| Meeting prep, per attendee | `reason/meetings/prep.py` | last touch, open commitments both ways, the previous meeting's open items, screen items — precomputed by the post-pass, served by an API |
| Attention | `context/attention.py` → `context_attention` | a deterministic *"look here first"* per node, read by the digest |

The pieces exist; none of them sees a workstream, the expert's judgment, your calendar for the day
and your promises together.

## 2 · Why

A chief of staff's most valuable minute is the first one of your day: *what changed, what is stuck,
what is due, what I would do — and the drafts are ready.*

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the day's inputs | new `executive/morning.py` | every live workstream's latest **validated** expert result; today's and tomorrow's meetings with their prep (`reason/meetings/prep.py`); your promises due (screen `my_promise`, commitments); what changed since yesterday's brief |
| 3.2 | the ordering | one Sonnet-class pass over the day — or `daily_brief_ranking` if D1 = B | the top items with **one reason each**, drawn from the files' appraisals. Guard rails the pass cannot override: a hard deadline within 48 hours and any meeting today are always in; nothing appears without a validated result; every number comes from the calculators |
| 3.3 | the shape | the existing summary ladder | **one line** (*"3 things need you; Insight call Wednesday"*) · **one minute** (the top five with the move and the draft) · **five minutes** (changed · stuck · your promises · meetings with prep · what I am watching and why) |
| 3.4 | delivery | D9 | the dashboard's Today view (Atlas A.10 has the wireframe) at 08:00 IST; e-mail or WhatsApp later, through the existing outbox |
| 3.5 | feedback | `STEP-16` | *useful · not useful because ___* on every line |

## 4 · What will happen — a Monday `[MODELLED]`

```
GeniOS · Monday 6 Oct · 3 things need you

1  Insight Partners, Wed 8 Oct — send Neel the pre-read by Tuesday            draft ready
2  Pankaj (saka.vc), introduced by Boardy 3 Sep — 33 days, nobody has written   draft ready
   (I asked you on Friday whether saka.vc is a fund — still open)
3  Startup India — your DPIIT application moved to ___; ___ is due by ___       steps listed

Changed since Friday   Hub71 wrote · Khushi (247VC) is now 18 days unanswered
Stuck                  the 11 Aug investor wave — 0 of 11, follow-up plan ready
Your promises due      2 from WhatsApp (to ___, to ___)
Meetings               Wed Insight · Wed Noveum (Aditi) · Thu Tryclean (Tejas) — prep in each card
Watching               Theresa (Antler) — waiting for a real milestone before the next update
```

## 5 · Expected

- one brief a day at the set time, empty mornings saying so;
- every line traceable to a validated file;
- your feedback recorded on at least some lines in the first week — the input `STEP-16` needs.

## 6 · Verify

```
.venv/bin/python -m pytest tests/executive/test_morning_brief.py -q
#   a deadline within 48 h is always present; a file with no validated result is never present;
#   numbers equal the calculators; an empty day renders "nothing needs you"
```
