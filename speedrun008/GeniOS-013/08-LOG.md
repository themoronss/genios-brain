# 08 · Log

Append-only. Each line records the date, what was done or measured, the number it moved, and who did it. Corrections are new lines; existing lines are never edited.

| Date | What | Numbers | By |
|---|---|---|---|
| 2026-10-28 | Folder written: the plan and the measured baseline, on a local copy of the design partner's org (production cut 12:45 UTC, code `harsh/mvp` `7d2c3615`) | cards 8/20 found, fields 28/220 (`ideal_card_gap.py`); stricter trace: 0 the same, 9 partial or wrong, 11 missing | Claude |
| 2026-10-28 | Correction recorded: the 547 parked rows are attachment stubs whose mails were emitted, not parked mails | emitted 1,193 / archived 636 of 1,829 mails | Claude |
| 2026-10-28 | Folder reordered on Rohit's ask into four questions: 01 what is happening, 02 what should happen, 03 how it gets fixed, 04 how it runs smoothly; spec, measurements, decisions and log became 05–08. Added the problem → step map (03), the target flow (02) and operations (04, units U13-39 to U13-42) | — | Claude |
| 2026-10-29 | Plan reorganised on Rohit's ask into five parts: P1 Orchestrator, P2 Notebook, P3 Plane D, P4 Plane R, P5 Cards. Each part has 01 what's exactly there, 02 what's failing and why, 03 expected vs happening, 04 what needs to be done now, 05 how at production level. Added 09 (what, why and how, from the launch film) and 10 (the acceptance set). Measured on the notebook build `b2` (as of 23 Oct 01:40 UTC) and on the product code at `speedrun008` `71c50f56`. Nothing built | `b2`: in-copy ideal cards same 4, close 2, partly 4, opposite 2, missed 5 (3 outside the copy); goals 6 of 10 matched (+1 in other words); 63 open cards; $8.41. Corpus: 160 capabilities, 69 situations, 22 draft; Founder Office 6 capabilities, all unreadable to the compiler; 71% of the notebook's situations had no expertise behind them | Claude |
