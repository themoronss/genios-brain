# L1 Enterprise Signals (`capture/`) — start here

**Status 2026-10-17:** as-is written · plan written · Group A being built on branch `yc2w27-l1`.

**Layer 1's job:** say what happened, in which source, when, with what evidence — and say honestly
what it did NOT see. It does not decide what anything means for the company; that is L3 and L2.

## In one screen

- **Most of Layer 1 is built and works** — the gate keeps everything, coverage says "18 of about
  465", dedup, bounces, commitments, importance, expiry, publication checks. (`01-AS-IS.md` §2)
- **Production does not have it yet.** It runs `harsh/mvp`, 815 commits behind. Harsh's deploy is the
  single biggest improvement to what the founder sees.
- **15 things do not work** (`01-AS-IS.md` §3). The worst: an expired login read as an empty inbox
  (fixed today), and a junk filter told to drop introductions and price changes.
- **14 items are planned** in four groups, plus **4 decisions only Rohit can make**
  (`02-PLAN.md`).

## The plan's state

| Group | Items | State |
|---|---|---|
| A · never say what you do not know | A1 refusal ≠ empty · A2 truncated poll · A3 inferred time · A4 Gmail `historyId` | A1 ✅ A2 ✅ (guards running) · A3 next · A4 needs a live shape from Harsh |
| B · the junk filter | B1 live measurement · B2 prompt · B3 re-judge risky drops | ⛔ waits for R1 |
| C · what L1 knows reaches L2 | C1 evidence fetcher · C2 entity doubt · C3 four unchecked lanes · C4 L2 reads L1's columns · C5 bundles | C1–C4 Claude · C5 ⛔ R2 |
| D · new objects | D1 thread end state · D2 condition | Claude |

## What Rohit decides (from `02-PLAN.md`)

R1 spend ≈ $1 on the live pass · R2 bundles: read or retire · R3 a second mailbox · R4 history 60 → 365 days.

## Read order

`01-AS-IS.md` → `02-PLAN.md` → `03-LOG.md`.
