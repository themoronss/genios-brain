# GeniOS-008 — every question, asked once (18 Oct 2026)

**Written for:** Rohit. Answer by number. **A question you skip takes its recommended default**, and the
work goes ahead on it. Nothing here is asked again later (`01-RULES` Rule 4.6).

## A · The architecture and the migration

| # | Question | Recommended default |
|---|---|---|
| A1 | Is [`00-ARCHITECTURE.md`](00-ARCHITECTURE.md) the final target? | **Yes** |
| A2 | Migration: new path built beside the old one in shadow; the golden set compares; switch one situation type at a time; old path deleted at the end (`02-MIGRATION-PLAN` §4)? | **Yes** |
| A3 | First situation type to switch? | **Awaiting reply / outreach.** Your investor, intro and incubator cases live here |
| A4 | Domains live for your org: Admin + Founder Office live; Sales and Support stay off (shadow only)? | **Yes** |
| A5 | Retire the LLM decider (`llm_decision_maker`, R-1)? Today the model chooses DECISION vs DEFER, which the architecture forbids | **Yes, retire**; the one bounded judgment pass replaces it |
| A6 | The judgment pass model and budget | **Sonnet-class (`claude-sonnet-5`), $2 a day for your org**, as the expert pass runs today |

## B · L4 Executive — who decides

| # | Question | Recommended default |
|---|---|---|
| B1 | Must a human approve a decision before any work is planned? | **Yes, for the decision lane.** Monitor and investigation need no approval (they only watch or ask) |
| B2 | Who are the seats and approvers today? | **You are the only approver.** Harsh is a seat with no approval rights. Others are added through the company brief |
| B3 | How should a card or reminder reach you, beyond the in-app view? | **Email to `mrrohitswerashi@gmail.com`** first; Slack later |

## C · Layer 1 items still waiting on you

| # | Question | Recommended default |
|---|---|---|
| C1 | Spend about $1 on the live test of Layer 1's model calls (junk filter, relevance, extraction on Haiku)? Needs a key in `GENIOS_GOLDEN_LIVE_KEY` | **Yes** (then the junk-filter prompt fix, B2) |
| C2 | Connect `ceo@thegenios.com` as a second mailbox (a seat connection)? | **Yes** |
| C3 | History window 60 → 365 days, then the resync? | **365** |
| C4 | Metric definitions ("sales" = booked/collected/signed): who owns them? | **Plane D corpus** (reviewed YAML), not L1 code |

## D · Expertise and learning

| # | Question | Recommended default |
|---|---|---|
| D1 | The two founder playbooks (`review/investor.review.yaml`, `review/program.review.yaml`) wait for your line-by-line review (`06` D45). Fundraising is refused as "unreviewed" until then. Review them, or let them run labelled "not yet reviewed"? | **Run labelled until you review** (`06` D3 already allows it for your org) |
| D2 | May calibration mute or nudge on your account (`06` D13)? | **No, stay in shadow** until L6 attribution (L6-1) is built |

## E · How we work

| # | Question | Recommended default |
|---|---|---|
| E1 | Push each finished group straight to `speedrun008` (fast-forward), CI runs the suites? | **Yes** |
| E2 | Budget for live model evaluations during the migration (comparing old vs new on the golden set with a real model)? | **Up to $20**, reported per pass |
| E3 | The old plan folders (`YCW27/`, `YC-II W27/`): freeze them as history, no more edits? | **Yes.** All new work and notes go to GeniOS-008 |
| E4 | Harsh's deploy cadence | **Deploy `speedrun008` now** (L1 H1), then after every layer's group is pushed |
