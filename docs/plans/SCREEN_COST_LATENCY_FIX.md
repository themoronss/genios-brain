# Screen intelligence — cost, latency and the interrupt gate

> **Created:** 2026-09-17 · **Status:** Active — waves 1 and 2 built, nothing pushed

**Purpose:** cut what one screen-reading seat costs per month and what one instant note costs in
seconds, without removing a single card — by fixing four things the code itself shows are wrong:
a thread key that collapses every Gmail thread into one, a paid model call spent on screens a rule
could have refused, a prompt that cannot be cached, and an interrupt the model still authors.

---

## 0 · Where the truth is

The instant lane, the follow-ups, the memory batch and the seat profile live on brain
`p15/quality` (NOT on `harsh/mvp`). The desktop half lives on dashboard `p14/capture-save` (NOT on
`main`). `docs/screen-intelligence/index.html` is the current spec; the 16 Sep `genios-screen.md`
reference architecture is written off the 14 Sep prototype and is a generation behind the code —
retention, per-thread verdicts, mute, topic caps, rate guards and the grounding validator all
exist now. Three of its findings are still true and are items 3, 4 and the wave-2 reader work
below.

## 1 · What is actually wrong (code-verified)

**D1 · Gmail is one thread.** `capture/session.rs:74 doc_thread_key` builds `doc:<bundle>:<host><path>`
from `capture/gate.rs:141 host_path`, which returns `parsed.path()` — the URL **fragment is
dropped**. Gmail routes the thread in the fragment (`…/mail/u/0#inbox/FMfcgz…`), so every mail
thread a manager opens shares the key `doc:com.google.Chrome:mail.google.com/mail/u/0`.
`followups.py:270 CHAT_HOSTS` deliberately lists `mail.google.com` so mail is judged *per thread*
— the intent is right, the key cannot carry it. Consequences, all measurable: one personal mail
turns the whole mailbox personal for 24 h (`thread_verdict`), "Mute chat" mutes the mailbox,
`topic_key` folds unrelated asks into one topic, and `mark_answered` closes an ask because a
different mail has a later `You:` line. Same class of bug on `teams.microsoft.com`.

**D2 · Triage is a paid call.** `capture/screen/relevance.py` already holds the deterministic
work/personal rules (`alias_hit`, `record_shaped`, `WORK_HOSTS`, `WORK_BUNDLES`, `WORK_EXES`,
`personal_chat_verdict`) — but only the promoter lane consults them. `api/moment_routes.py
_screen_insight` sends **every** unjudged screen with ≥ 30 chars to Haiku, including the ones a
rule would have refused for free. The 24 h verdict only helps *after* the first call. Measured
14 Sep: one seat, 3.7 h, 224 calls, ₹30.

**D3 · The prompt cannot be cached.** `screen_insight.llm_insight` constructs `Anthropic()`
directly and bypasses `context/llm/client.py`, which already implements `cache_prefix_chars` and
cost-equivalent token accounting. Even if it did not: the static half of `_PROMPT` is ≈ 1,200
tokens [estimate] against Haiku 4.5's **4,096-token minimum cacheable prefix**, and the template
interleaves `{profile}`/`{now_local}` near the top with the JSON schema (static) at the bottom, so
the longest stable prefix is ~80 characters. The same repo measured the *other* lane at
**input −88 %/call** once its prefix passed 4,096 tokens (email at 3,998 did not cache).

**D4 · The model still authors the interrupt.** `screen_insight.judge` keeps `adds` whenever the
response has ≥ 1 grounded item; nothing verifies the claim. `repeat_ask` is never matched against
item history, `conflict` is never recomputed against the meetings the prompt already carried,
`same_ask_elsewhere` is never matched across sources. There is no `confidence` field at all, so
the "below the floor, counted" behaviour the spec asks for has nothing to read. Everything
*around* the decision is already deterministic and good (topic/day cap, ≤ 3/h, mute 7 d/forever,
shadow/DND/quiet/rate guards, duplicate TTL) — only the decision itself is the model's.

## 2 · Wave 1 — what this plan builds

| # | Fix | Where | Expected effect |
|---|---|---|---|
| 1 | Thread key carries the SPA route | desktop `capture/session.rs` | correctness; fewer wasted calls (verdicts stop being wrong) |
| 2 | Deterministic triage before the paid call | brain `_screen_insight` + `screen_triage.py` | −30–40 % calls [estimate] |
| 3 | Cached rulebook (≥ 4,096 tok) + 50 Hinglish/English few-shots | brain `screen_insight.py` | −11 % to −22 % input [derived]; the few-shots come almost free |
| 4 | Deterministic interrupt gate + per-item confidence | brain `screen_insight.py`, `moment_routes.py` | popups only when code can verify them |

**Invariants this plan does not touch:** device timers (dwell 5 s / 2 s, gaps 20 s / 10 s, focus
debounce 700 ms), the never-read privacy gate, store-don't-delete (a refused screen is *skipped
and counted*, never deleted), billing (`platform/billing.py` untouched — screen ingestion stays
uncharged), and no new periodic task (Upstash quota — both lanes stay in-process threads).

### 1 · Thread key

`doc_thread_key` gains the URL fragment for an explicit allowlist of hosts that route in the
fragment (`mail.google.com`, `teams.microsoft.com`, `teams.live.com`, `mail.zoho.com`,
`mail.zoho.in`). Allowlist, not "always": a fragment on `docs.google.com` or `notion.so` is a
section anchor, and folding it into the key would *split* one page into many and cost more calls.
The key stays `doc:<bundle>:<host><path>` shaped so the brain's `_WEB_DOC` regex, `verdict_key`,
`is_assistant_page` and the site/thread split keep working with no brain change, and an older
device that sends no fragment behaves exactly as today.

Not fixable here: WhatsApp Web (no route in the URL *and* the tab title is `(3) WhatsApp`) — it
needs a dedicated reader that reads the chat header. Wave 2.

### 2 · Triage

A new `genios_engine/reason/moments/screen_triage.py` answers one question before any spend:
*does this screen carry a work signal a rule can see?* It reuses the promoter lane's own rules so
there is one spelling of "work" in the product:

* the device matcher already resolved slice entities → `body.features.entities` non-empty ⇒ judge;
* a participant that resolves in the graph ⇒ judge;
* `WORK_HOSTS` / `WORK_BUNDLES` / `WORK_EXES` hit ⇒ judge;
* a record-shaped page (kv + table blocks) ⇒ judge;
* otherwise **skip**, 204, no model call — counted with its reason.

Governed by `screen_insight_triage_enabled` (default on) so it can be switched off in one env var
if it ever hides something. Every skip increments a counter the weekly report reads, because the
14 Sep lesson was that a limit which hides data silently is worse than the cost it saves.

### 3 · Cached rulebook

`build_prompt` splits into `_RULEBOOK` (frozen, marked `cache_control: ephemeral` at
`RULEBOOK_CHARS`) and `_TASK` (everything per-screen). The call goes through
`context/llm/client.py` so cost-equivalent tokens (uncached + 1.25 × writes + 0.1 × reads) land in
`llm_costs` and the budget prices a cached call correctly.

**Do not repeat the reference architecture's −37 %, and do not read the repo's own −88 % across.**
That −88 % was measured on the extraction lane, where the static prefix was 4,203 of ~4,700
tokens. Here the fixed half is ~1,200 of ~2,400, so caching it is worth much less. The arithmetic,
with `R` the rulebook, `D` the dynamic half and `h` the hit rate — effective input =
`(0.1h + 1.25(1−h))·R + D`:

| | per check | vs today |
|---|---:|---:|
| today (1,200 fixed + 1,200 dynamic, uncached) | 2,400 | — |
| rulebook 4,300 tok, 90 % hit | 2,124 | **−11 %** |
| rulebook 4,300 tok, 95 % hit | 1,877 | **−22 %** |

So the honest case for this change is **accuracy**: 50 worked examples — Hinglish asks and
promises, the manager's own job search and pay as personal, buttons and missing-info lines that
are not items, an ask addressed to someone else, and one worked example per popup reason — for
about a tenth of their size on every call after the first. The cost win is real but modest, and a
seat that checks once in a long while pays MORE for a big rulebook than a small one: the hit rate
is the whole argument, which is why `llm_insight` logs `cache read=… write=…` on every call.

**The token count is not measured yet.** Haiku 4.5 caches nothing under 4,096 tokens and a short
prefix fails silently. The rulebook is 20,499 characters, which is ≥ 4,096 tokens even at a
pessimistic 4.5 chars/token, and a test guards that floor — but characters are not tokens.
`scripts/measure_insight_cache.py` settles it with `count_tokens`; it could not be run here
because the workspace's Anthropic key is **over its usage limit until 2026-10-01**.

### 4 · The gate

The model's `adds` becomes `adds_candidate` and each item gains `confidence`. A note survives only
when code can verify the claim from data the request already loaded:

| Candidate | Verified by |
|---|---|
| `repeat_ask` | an open `ask` in `open_context` from the same `who` |
| `promise_to_them` | an open `my_promise` for that `who` |
| `same_ask_elsewhere` | an open item, same `who`, **different** `thread_key` |
| `conflict` | the item's due overlapping a meeting in `_meetings_soon` |
| `urgent_risk` | a due within 24 h (language alone is not enough) |

Unverified ⇒ the items are still saved, the popup is not shown, and the suppression reason is
counted. `confidence` is stored and counted but the floor ships at 0 (off) — no floor is set
before it is measured on a real labelled set.

## 3 · Wave 2 — built

| Fix | Where | What it changes |
|---|---|---|
| Addresses on a page become participants | desktop `moments/focus.rs` | `who` becomes a lookup instead of a guess on Gmail / Outlook / CRM |
| A parsed date keeps its hour on the wire | desktop `moments/client.rs` | "kal 5 baje" stops arriving as "kal" |
| The matcher reads what actually travels | desktop `moments/service.rs` | names and dates five lines up are found, not guessed |
| `snap_due` — the device's clock beats the model's arithmetic | brain `screen_insight.py` | a quoted phrase the device resolved is never recomputed |
| Two duplicated read pairs merged | brain `followups.py` | `any_muted`, `taught_notes`; covered against real Postgres |
| A reader that goes blind says so | desktop `capture/health.rs` + panel | NFR-04: silence stops being a valid outcome |
| P-21 attention | desktop `moments/attention.rs` | the first card about where the manager is NOT looking; zero tokens |

**Dedicated Gmail / Calendar / Slack readers are deliberately NOT built.** A dedicated reader is
accessibility paths, and `ReaderEngine`'s own comment says they are written from real trees
recorded by `scripts/measure.sh`. Guessing selectors would ship a reader that silently shadows the
generic one and returns nothing — the exact failure `capture/health.rs` now exists to catch. What
those readers were *for* — participants and timestamps — was obtained deterministically instead,
from text the generic reader already sends. The readers themselves wait for the Accessibility
grant.

**The remaining round trips are left alone, on purpose.** At a 10 ms round trip one instant check
spends roughly 250 ms in the database against a 1.5–3 s model call — about a tenth of it. Merging
the other eight reads into one CTE would touch the visibility, verdict and mute rules to save
that tenth. The two pairs that WERE merged were duplicates of each other, which is a different
thing. Revisit if the pooler RTT is ever measured above ~25 ms.

**Still open:** the other three zero-LLM cards (ask priority, who-owns-X, post-meeting
follow-ups); who-owns-X needs task ownership in the slice, which needs Linear or Jira. WhatsApp
Web's thread key (its URL carries no route and its tab title is `(3) WhatsApp` — it needs the
dedicated reader). Quiet-hours *windows* are enforced server-side but not on device-made advice;
the device sees DND and pause, not the configured window, and the capture policy does not carry
it yet.

## 4 · Definition of done (wave 1)

* a Gmail thread and a second Gmail thread produce different `thread_key`s (Rust test);
* a screen with no rule-visible work signal spends no model call and is counted (brain test);
* the rulebook prefix measures ≥ 4,096 tokens and the dynamic half carries the screen (test on
  the built prompt, no API key needed);
* an `adds_candidate` with no verifiable evidence never renders a popup and its items still save;
* every existing screen test stays green.
