# 02.4 · Intelligence → Screen

**Written for:** Harsh.

**Commit:** `0ab7b03`.

**Files:**
- `src/app/dashboard/moments/page.tsx` (route kept as `/dashboard/moments`)
- `src/components/moments/screen-lanes.tsx` (new)

**Screenshot:** `screens/screen-page-signed-in.png`.

**Rohit's ask:**
- Whatever the desktop app records from the screen shows up here.
- **Instant** things (a follow-up, a reminder, an update) are saved at once and need nothing more.
- Things **with context** need reasoning, and after reasoning they become a card.
- He asked whether that second kind needs its own part: *"iska koi alag part banana padega ki nahi, wahi dekh lena"*.

**Answer: no separate page.**
- What reasoning produces *is a card*, and cards already live in Cards: one place to act.
- The Screen page shows both lanes and links the reasoning lane to Cards.

---

## What the page shows

1. **Header:** "Screen — What GeniOS caught on your screen, and what happened to it." It also shows the existing Loaded / Shown / Wrong counters and a Refresh button.
2. **Two lanes**, `ScreenLanes`:

| Lane | What it means in the brain | Live numbers |
|---|---|---|
| **Done instantly** | The instant judge (`reason/moments/screen_insight.py`, one quick read; a rule where `screen_rules.py` can answer for free) picks asks / promises / deadlines / risks out of the visible text. They are saved at once as `screen_followups`. A popup shows only when it adds something the screen does not already say | `/v1/seats/me/weekly-report`: promises_caught · asks_flagged · deadlines_flagged · risks_flagged · popups_shown |
| **Sent for reasoning** | A work thread is promoted to memory at most hourly (`platform/screen_promoter.py` → a seat-private source event). `screen_memory.py` writes the items as graph observations, and `screen_memory_batch.py` writes the hourly batch read. From there it is reasoned over with everything else; a situation becomes a card | **none yet**: shown as "—" with the explanation and a link to Cards |

3. Everything that was on the Moments page before, unchanged: This week, Open follow-ups, and the moments list with its Useful / Wrong feedback.

## Brain work to make the reasoning lane real

`05-BRAIN-WORK.md` §4. Two counts per seat per week:
- threads sent to memory;
- cards whose evidence came from a screen observation.

The first is countable from `screen_memory_batch` jobs, or from promoted source events with the screen source. The second needs a card → source join: a card's evidence has a `source`, and screen observations are kind `screen.<item kind>`.
