# Layer 1 — Sources

**Last updated:** 6 August 2026
**Branch:** `harsh/mvp`
**Tests:** 467 passing

Layer 1 is where reality enters GeniOS. Emails, calendar events, documents, uploaded
files, things people type in — everything comes in through here, gets cleaned, gets
checked, and gets handed to Layer 2.

This file tracks what it was, what changed, and what is still broken.

---

## Part 1 — Source Registry

### What it was before

A source like `gmail` or `stripe` was described in **four separate lists** in four
different files:

| List | File | What it said |
|---|---|---|
| Family | `source_families.py` | what kind of source this is |
| Buildable | `platform/wiring.py` | can we actually connect to it |
| Capability | `coverage/model.py` | what it gives us (email? calendar?) |
| Mappings | `structured/registry.py` | how to read its data |

Nothing compared these four lists against each other. So they drifted apart quietly.

### What was actually broken because of it

**1. Six sources were invisible**

`stripe`, `razorpay`, `zendesk`, `intercom`, `mscal`, `mixpanel` were listed as
providing something useful — but had no family entry. So any data from them would have
landed as **"unclassified"**. Stripe even had a working data-reader built for it,
pointing at a source the system didn't officially know about.

It hadn't caused damage yet only because none of those are connected. It was loaded and
waiting.

**2. Calendar coverage was under-reported**

If a connection was saved as `google_calendar` instead of `gcal`, the system **did not
count it** as calendar coverage. Same for `drive` vs `gdrive`. So you could have your
calendar connected and GeniOS would still say "no calendar data".

**3. The Sales domain could never be ready — and nothing said so**

The Sales pack requires a CRM. No CRM can be connected today. So Sales can never reach
"ready" status, and there was no way to find that out.

### What we changed

One file now describes each source completely: [`capture/source_registry.py`](../genios_engine/capture/source_registry.py)

```python
SourceDescriptor("gcal", "communication", capability="calendar", buildable=True,
                 aliases=("calendar", "google_calendar"),
                 object_types=("calendar_event",))
```

The four old lists are now **generated from this one**, so they cannot disagree again.
Adding a new source = adding one line here.

12 tests were added that fail if the lists ever drift apart again. The Sales/CRM gap is
now written down as known debt — the test fails both if a new gap appears **and** if
someone fixes one without deleting the note.

### Result

- Behaviour unchanged for everything that already worked
- 6 sources correctly classified
- Calendar and Drive coverage now counted correctly
- 3 known gaps (CRM, support desk, finance) now visible instead of hidden

---

## Part 2 — Company Knowledge

### What it was before

Every piece of text that came in — an email, a chat, an uploaded document — was given
**the same level of trust.**

This meant:

> You upload your official pricing document.
> A stranger sends you an email mentioning a price.
> **GeniOS treated both as equally reliable.**

And worse: data pulled from connected tools like Stripe was ranked **higher** than your
own written policy. So Stripe could overwrite what your company officially stated.

Two places in the code already assumed this was fixed:

- `contracts/events.py` says a human correction is "the strongest correction signal" —
  it wasn't
- The trust scale already had a top level defined that **nothing ever used**

Both were wishful thinking, not real behaviour.

### What we changed

**A. Trust levels now mean something**

| Level | What it is | Example |
|---|---|---|
| 4 | **Company canon** — you said it about yourself | your written refund policy |
| 3 | System of record | a Stripe subscription row |
| 2 | Observed | something inferred from an email |

Company canon now sits at the top. When two things disagree, your own statement wins —
and the disagreement is still recorded, not silently thrown away.

Important: **canon is authoritative, not permanent.** Freshness is checked before trust
level, so a policy from last year does not block this morning's data.

**B. A vocabulary of 12 things you can record**

```
policy · sop · product · pricing · goal · kpi
org_structure · employee_profile · project · task · asset · wiki
```

*(Company Memory was deliberately left out — memory is something GeniOS works out from
what it has already seen. Feeding it back in as a "source" would turn yesterday's guess
into today's evidence. Memory belongs to Layer 2.)*

**C. A new door — write knowledge directly**

```
POST /api/org/{org}/knowledge
{ "kind": "policy", "title": "Refund Policy", "body": "Refunds within 30 days." }

GET  /api/org/{org}/knowledge/kinds     → the 12 kinds, for the UI dropdown
```

**D. Uploads can be tagged as official**

Tag a file `pricing` or `policy` or `sop`, and that file becomes company canon instead of
just another document. Old free-text tags still work — common spellings are understood
(`SOPs` → `sop`, `Price List` → `pricing`, `OKRs` → `goal`).

**E. Editing replaces, instead of piling up**

Rewrite your refund policy and submit again — it **replaces** the old one. Submit the
same text twice and nothing happens (reported as success, not an error). You never end up
with three competing versions of one policy.

### Also fixed along the way

The uploads list was returning `"authority": 1.0` on every single file — a hardcoded
number on a scale nothing else in the system uses, while the actual facts underneath were
all stored at level 2. It now reports the real number.

### Files changed

| File | What |
|---|---|
| `capture/internal_knowledge.py` | **new** — the 12 kinds, spelling variants, trust rules |
| `api/knowledge_routes.py` | **new** — the write-knowledge endpoint |
| `migrations/0035_l1_internal_knowledge.sql` | **new** — database column |
| `capture/intake.py` | new door, with replace-not-duplicate logic |
| `capture/landing/normalize.py` | tagged files become "internal" family |
| `context/pipeline.py` | facts now stored at their real trust level |
| `context/runner.py` | trust level carried across to Layer 2 |
| `api/upload_routes.py` | tag → official knowledge |

20 tests added.

---

## Part 3 — What is still broken

These are real, confirmed problems. Not theory.

### Uploads

**1. Big files are silently cut off** — *worst one*

The limit is 60 pieces × 2000 characters ≈ **50 pages**.

Upload a 200-page company handbook and GeniOS reads the first 50 pages, throws the rest
away, and reports **"indexed"**. You would believe it knows your whole handbook. It knows
a quarter of it.

The danger is not the limit. It's that **it reports success.**

**2. Text is cut at random points**

Files are sliced every 2000 characters — mid-sentence, mid-word, mid-table.

> *"...refunds are accepted within* **| CUT |** *30 days of purchase..."*

Neither half means anything on its own. The fact is lost. This quietly damages the
quality of everything extracted from every document.

**3. Scanned PDFs work by email but not by upload**

Someone **emails** you a scanned contract → GeniOS reads it (OCR runs).
You **upload** that same file → "no extractable text".

Same file. Two different answers. The upload path was simply never connected to the OCR
that already exists and already works.

**4. Uploading the same file twice creates two copies**

Every upload gets a brand new ID, so there is no "I have seen this document before"
check. Your event log fills with duplicates.

*Not as bad as it sounds:* there is a content cache, so the AI cost does not double.

### Manual writing

**5. You can write knowledge, but not see or delete it**

There is only an "add" endpoint. No list. No delete. If you write something wrong, there
is no way to remove it.

Uploads have both. This door doesn't yet.

### Connecting tools

**6. Only 4 tools can be connected**

Gmail · Google Calendar · Notion · Google Drive *(plus your own database)*

These work properly — connect, sync, no data missed. But everything else — HubSpot,
Slack, Stripe, Zendesk — needs code written for each one.

---

## Part 4 — Remaining planned work

| Step | What | Why it matters |
|---|---|---|
| **3** | Filters that understand each source type | The noise filter only understands email. For every other source it does nothing at all. |
| **4** | One generic handler for any Composio tool | **This is the big one.** Right now the live-event webhook is hardcoded for Gmail only. |
| **5** | Move data mappings into config files | Adding a mapping shouldn't mean editing Python. |
| **6** | Add 2–3 new tools to prove it works | If Step 4 is right, this needs **zero** pipeline code. |

**Step 4 is the one that matters most.** Until it's done, "add more sources later" means
"write a new connector every time". After it's done, adding a tool is a few lines of
configuration, because Composio already handles the login and the data pulling.

---

## Part 5 — Deliberately not done

**Company knowledge is not counted in the coverage dashboard.**

That dashboard works out readiness by looking at **connected apps**. Written knowledge is
not an app, so it has no connection record. If I added it now, it would show
**"not connected"** forever — even after you upload every document you own.

That would be a new wrong answer replacing an old one. The dashboard needs to accept
non-app evidence first. That's its own small piece of work.

---

## Summary

| | Status |
|---|---|
| Upload files | Works — but silently truncates and cuts text badly |
| Write knowledge manually | Works — but no way to view or delete |
| Connect tools | Works — but only 4 |
| Add new sources easily | **Not yet** — needs Step 4 |
| Everything lands the same way | Yes — one door, one path, fully traced |
| Trust levels are real | Yes — your word beats a connector's guess |
