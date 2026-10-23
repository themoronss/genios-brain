# 13 · Log (append-only)

**Rule:** one line per event, newest last. A correction is a new line, never an edit. Every "it works" names the command or the reading that showed it. Every failure is recorded with its reason. After each step of [09](09-STEPS.md), one line: which `/preview` cards appeared, which are missing, and each missing card's `why_no_card`.

| Date | What | Evidence |
|---|---|---|
| 23 Oct | Folder written on Rohit's ask: *"layer by layer, parts by parts, unit level … taki Harsh … coding agent se changes and updates kara sake"*. Built from four read-only code crosschecks at `origin/speedrun008` `71e4c4a8` (L0+L1, L3, L2, L5+goals API+dashboard `origin/main` `ff13896`), GeniOS-011 (02-PLAN, 04, 07, 08) and the ideal dashboard's traces on Rohit's machine. No code changed. | files 00–12 |
| 23 Oct | New in this crosscheck (not in GeniOS-011): `activate_tenant._plan_for` drops `expert_review`/`l2_reasoning`/`l2_cards` (U12-02); the compile gate at `runner.py:2029` (U12-03); `_need_fetchers` uses `config={}` (U12-04); admission's HOLD is not shadow-only; situation ids are uuid4 and the backfill docstring is false; the automatic history replay rebuilds destructively (U12-11); the gate judge never sees the sender; calendar events have no meeting type; sent-mail amounts are never written; equal-rank conflicting facts are overwritten; a reply closes every ask; time is never a trigger and `FOUNDER_ASKED` is dead; STEP-13b's migration 0250 collides; S34.U3 is uncommitted in its worktree and claims 0252; the dashboard never renders the draft and hard-codes the goal row. | [00 §4](00-START-HERE.md) |
| 23 Oct | Rohit: `/preview` stays. 07's N6 (retire `/preview`) is not to be done. | Rohit's message |
