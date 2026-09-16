# Screen intelligence — cost, latency and the interrupt gate

> **Created:** 2026-09-17 · **Status:** Active — wave 1 building

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
| 3 | Cached rulebook (system block ≥ 4,096 tok) + Hinglish few-shots | brain `screen_insight.py` | −30–40 % ₹/call [estimate]; accuracy lever is free |
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

`build_prompt` splits into `rulebook()` (frozen, cached, `cache_control: ephemeral`) and a
dynamic user block. The rulebook is not padding: it is the taxonomy, the safety rules, the five
popup reasons with worked examples and 15–20 Hinglish/English few-shots — the cheapest accuracy
lever available, and it is what takes the prefix past 4,096 tokens. The call goes through
`context/llm/client.py` so cost-equivalent tokens (uncached + 1.25 × writes + 0.1 × reads) land in
`llm_costs` and the budget prices a cached call correctly.

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

## 3 · Wave 2 (not in this plan)

Dedicated readers for Gmail, Google Calendar and Slack (`ReaderRegistry.dedicated` holds
**only** `WhatsAppReader` today; the generic reader sends no participants and always a `nil`
timestamp, which is *why* the prompt has to carry a 14-day date list and why `who` is a model
guess); the four zero-LLM cards (ask priority, who-owns-X, post-meeting follow-ups, attention);
collapsing the ~25 DB round trips of one instant check to ~8; and the reader canary. Readers are
blocked on real AX trees (`scripts/measure.sh`) and therefore on the Accessibility grant.

## 4 · Definition of done (wave 1)

* a Gmail thread and a second Gmail thread produce different `thread_key`s (Rust test);
* a screen with no rule-visible work signal spends no model call and is counted (brain test);
* the rulebook prefix measures ≥ 4,096 tokens and the dynamic half carries the screen (test on
  the built prompt, no API key needed);
* an `adds_candidate` with no verifiable evidence never renders a popup and its items still save;
* every existing screen test stays green.
