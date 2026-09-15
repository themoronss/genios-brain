-- 0161 · FOLLOW-UP QUOTE (SCREEN_INTEL_SYSTEM_DESIGN.html, phase 1 "one judge").
--
-- `quote`  the ≤ 12 words the screen-insight model copied from the screen as proof of the item
--          (already grounded: it must appear in what was on screen). Under the design's product
--          rule most items are saved WITHOUT a popup, so the "answered" check can no longer read
--          the quote from the popup's moment row — it reads it here. NULL for rows made before
--          this migration (those still fall back to the moment's body).
alter table screen_followups add column if not exists quote text;
