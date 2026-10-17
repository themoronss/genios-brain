# L1 Enterprise Signals (`capture/`) — start here

**Status 2026-10-17 evening:** A1 A2 pushed (`e0996e6c`) · A3 C3 built, hermetic green, golden board unread · B waits for R1 · C4 D1 D2 moved to L3.

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
| A · never say what you do not know | A1 refusal ≠ empty · A2 truncated poll · A3 inferred time · A4 Gmail `historyId` | A1 ✅ A2 ✅ pushed · A3 ✅ built (golden unread) · A4 needs one live Composio history response (Harsh) |
| B · the junk filter | B1 live measurement · B2 prompt · ~~B3~~ already built | ⛔ B1, B2 wait for R1 |
| C · what L1 knows reaches L2 | C1 evidence fetcher · ~~C2~~ not a defect · C3 unchecked quotes · C4 L2 reads L1's columns · C5 bundles | C1 deferred · C3 ✅ built (golden unread) · C4 → L3 · C5 ⛔ R2 |
| D · new objects | D1 thread end state · D2 condition | both → L3 (they need a reader there) |

## What Rohit decides (from `02-PLAN.md`)

R1 spend ≈ $1 on the live pass · R2 bundles: read or retire · R3 a second mailbox · R4 history 60 → 365 days.

## Read order

`01-AS-IS.md` → `02-PLAN.md` → `03-LOG.md`.
