# L1 Enterprise Signals — log (append-only; a correction is a new line)

| Date | Item | What happened | Commit | Proof |
|---|---|---|---|---|
| 2026-10-17 | — | As-is checked against `origin/speedrun008` `6e8f5b12` by three read-only audits, every headline claim re-read by hand. Written to `01-AS-IS.md` | — | file:line in `01-AS-IS.md` |
| 2026-10-17 | A1, A2 | Built on branch `yc2w27-l1`. A Composio refusal raises `ProviderRefused`; a truncated poll says we stopped | (pending) | 6 tests pass; three mutations (base never raises · Gmail list unguarded · budget branch removed) → 4, 2 and 1 failures. Repo-wide guards: first run hit my own 10-minute limit at 81% with 0 failures — void; re-running |
| 2026-10-17 | A1, A2 | Guards green: hermetic capture + platform + root 9,931 passed, 0 failed; on a fresh Postgres (pg3 `l1a_1017`) capture + platform 7,104 passed, 0 failed, 2 skipped. Fast-forwarded to `origin/speedrun008` | `e0996e6c` | the two runs |
| 2026-10-17 | B3, C2 | Retracted after reading the code: snippet drops from known senders are already fetched whole (`keeps_whole`); a contested alias with no hint is the canonicalizer's contract, identity is L3's | — | `02-PLAN` B3, C2 |
| 2026-10-17 | C1 | Deferred: the only need filed today is one no fetch answers, and a closure is permanent | — | `02-PLAN` C1 |
| 2026-10-17 | C4, D1, D2 | Moved to the L3 folder: each is worth something only with a reader in `context/` | — | `02-PLAN` |
| 2026-10-17 | A3, C3 | Built on branch `yc2w27-l1-next`. A3: 9 tests, three mutations caught. C3: 4 tests, mutation caught. Hermetic capture + platform + root 9,944 passed, 0 failed. Golden board run on a fresh DB (pg3 `l1b_gold_1017`) finished; **its result is unread** — auto mode refused the read of the local log. Not pushed until it is read | (local) | — |
