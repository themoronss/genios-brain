# Step 16 · Source field coverage — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** 16-U1…U5 **DONE** · no migration · **one re-extraction, priced and bounded** (§5)

---

## 1. ⛔ Premise check — the step's own list of gaps was wrong in two of three places

| §1 said | Verdict |
|---|---|
| gap 3 · calendar `responseStatus` discarded | ❌ **already closed** — step 13's `read_attendees` did it |
| gap 1 · Gmail `bcc` never captured | ❌ **impossible** — the provider does not supply it |
| gap 2 · `In-Reply-To` / `References` never captured | ✅ confirmed, and closed here |
| *"`assemble_chain` always falls back to chronology"* | ❌ **it never gets that far** — §3 |
| — | ⛔ **a fourth defect the step does not mention, and it is the biggest** |

**Two of three named gaps moved.** That is not a criticism of the plan — it is the argument for
16-U1. A written list of gaps goes stale the moment a step closes one, and re-deriving it costs a
full premise check every time. **The table is the fix; the list was the problem.**

---

## 2. ⛔ THE FINDING · every prompt in production says "message 1 of 1"

```python
# capture/pipeline.py — reads two keys
depth = max(1, _int(raw.get("thread_depth")))
position = _int(raw.get("thread_position")) or 1

# capture/semantic/extractor.py:717 — renders them into EVERY prompt
lines.append(f"thread position: message {envelope.thread_position} of {envelope.thread_depth}")
```

**No connector has ever written either key.** Verified by grep and by execution:
`_thread_place({"subject": "Re: Re: Re: renewal"})` → `(1, 1)`.

So the twelfth turn of a renewal negotiation is described to the model as **the first and only
message in its thread**, and `ThreadContext.turn_index` has been `0` for the entire corpus.

**This is not a missing field. It is a wrong one, stated confidently, on every extraction this
product has ever run.** A missing field fails loudly at its first reader. A wrongly-stated one never
fails at all — which is exactly why it survived sixteen steps and 12,700 tests.

It is the same shape as the defect steps 5, 6, 7 and 14 each caught **one step after shipping it** —
a field nothing fills — with the polarity reversed: here the reader existed and the writer never did.

### 2.1 · The fix costs no extra API call

RFC 5322 §3.6.4: `References` holds the parent's `References` plus the parent's `Message-ID`,
oldest first. **N references means N ancestors**, so the message is the (N+1)th. The header captured
for gap 2 answers the position question for free.

`threads.get` would give an exact thread size at **one request per thread on every sync**, against a
shared rate limit. §9 says the goal is *"know what we fetch, and why we do not fetch the rest"* — so
the trade is a row in the manifest, not a bill.

### 2.2 · Why `depth` equals `position`

One message cannot state its thread's total size, and inventing one would be **precisely the failure
step 15 was built to end** — reporting the size of what we hold as the size of what exists.

`_thread_context`'s own docstring already settles the honest reading: *"at capture time this event
genuinely IS the newest message of its thread."* So `(4, 4)` says **"message 4, and the newest so
far"** — the same claim the existing `(1, 1)` default makes for a lone message. This **generalises**
that default rather than replacing it.

---

## 3. ⛔ The correction to §1 · capturing the headers is necessary and NOT sufficient

§1 says `assemble_chain` *"always falls back to chronology"*. **It does not get that far.**

```python
# pipeline.py — reconstruct_thread receives a list of ONE message
ball = reconstruct_thread([ThreadMessage(message_id=event.event_id, ...)], ...)
```

There is no chain to build, branched or straight. `assemble_chain` implements full RFC 5322 parent
resolution, it is **correct**, and T2 proves it — by passing on the first run. **The unit works. It
has simply never been given data.**

Closing that needs the sibling messages, which is an API call or a store read and a different unit.
What this step does instead:

* the headers are carried onto the `ThreadMessage` the pipeline builds, so the seam is **already
  correct the day a caller supplies a thread** rather than being a second change nobody remembers;
* the limit is written down as a passing test (`test_capturing_the_headers_is_necessary_and_not_sufficient`)
  rather than left as an assumption that the step is finished.

---

## 4. The re-sync boundary — which events predate which field

**Recorded here because a silently mixed corpus is worse than a thin one.**

| Field | Lands from | Events before it |
|---|---|---|
| `In-Reply-To` / `References` in `raw["headers"]` | this deploy | carry neither |
| `thread_position` / `thread_depth` | this deploy | read `(1, 1)` — the honest default |
| `to_recipients` / `cc_recipients` (step 13) | step 13's deploy | fall back to `recipients` |
| `attendee_people`, `meeting_kind` (step 13) | step 13's deploy | parse from raw `attendees` |

**FORWARD-ONLY, and not by choice.** The raw Gmail payload is **encrypted and expires** — the
connector says so in as many words. A backfill cannot retrofit a header onto a landed event because
the bytes that carried it are gone. The only way to fill these for old events is a **re-sync from
the provider**, which re-fetches the message.

**Old events stay correct, not wrong.** `(1, 1)` on an event whose thread we cannot see is the true
answer, which is why the default was written that way. The corpus is mixed in *precision*, not in
*truth* — and `missing_captures` is now the tool that says which side of the line a source is on.

---

## 5. ⛔ Cost check — the one re-extraction, priced and bounded

`envelope_hash` is a `KEY_COMPONENTS` member and it hashes the **rendered prompt block**. Changing
what that block says is a cache miss.

| | Renders | Cache |
|---|---|---|
| opening message | `message 1 of 1` — **byte-identical to before** | ✅ **HIT** |
| a reply | `message 4 of 4` | ❌ **miss** |

**The bound is the argument.** Only replies re-extract, and **a cached extraction of a reply was
produced from a prompt that stated a falsehood.** Re-extracting it is not the cost of this fix; it
**is** the fix. A cache entry we would want to keep is one we did not mislead.

`vocabulary_fingerprint()` = **`a3d5496aa0d3`**, unchanged since step 4 — so the whole-corpus trigger
(`_SETS`, `UNTYPED_LANE_KEYS`) does **not** fire. This is a per-message miss on threaded mail, not a
re-extraction of the corpus.

Asserted, not asserted-to: `test_the_cache_price_is_paid_only_by_replies`.

---

## 6. What was built

| Unit | What |
|---|---|
| **16-U1** | `connectors/manifest.py` — 6 sources, every uncaptured field carrying a **reason** |
| **16-U2** | `connectors/thread_position.py` + `_THREAD_HEADERS`, wired at the connector and the pipeline |
| **16-U3** | `undeclared_captures` / `missing_captures` — **both directions**, driven by real output |
| **16-U4** | the re-sync boundary — §4 |
| **16-U5** | the remaining sources, in the same table — §7 |

### 6.1 · `reason` is required, and `bcc` is why

A silent omission and a considered one look identical without it. `bcc` reads as an oversight in
every connector review until someone spends a premise check discovering the provider does not supply
it — **which this step just did, for the second time.** The row ends that.

### 6.2 · E1 — captured-but-unread is a recorded position, not a bug

> *"The goal is not 'fetch everything'. It is 'know what we fetch, and why we do not fetch the rest.'"*

`gcal.hangoutLink` is captured and read by **nothing** — one write, zero readers. It stays, with the
reason: over-fetching costs payload bytes, deleting is free now, and re-adding means a re-sync. The
two directions are **not symmetric** and the table does not pretend they are.

### 6.3 · Its own tuple, not `_ROUTING_HEADERS`

`_ROUTING_HEADERS` is `("Reply-To", "Sender")` and the file states why it is separate from
`_NOISE_HEADERS` — *"captured for the opposite purpose"*. Those mark **attribution**; these mark
**threading**. One tuple per purpose is this file's existing convention, and a third tuple follows it
rather than overloading the second.

---

## 7. 16-U5 · the remaining sources, and the count correction

§5 names *"hubspot, notion, gdrive, linear, postgres, database"* for nine total. The registry
(`dispatch._PARSER_IMPORTS`) holds **six**: `gmail`, `gcal`, `gdrive`, `notion`, `linear`, `hubspot`.

* `postgres` and `database` are **one module**, and it emits no `RawObject`;
* `screen_session` is L1's own promoter, not a provider.

**Three manifests invented to reach nine would have been exactly the drift this step exists to
end** — a table that disagrees with the code. Six sources, all real.

---

## 8. Test result

```
FULL SUITE      12748 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 16: 12719 passed · 14 failed
```

**Zero regressions, +29 tests.** No migration · no model call · no vocabulary change ·
one bounded re-extraction (§5).

---

## 9. What this step does NOT do

* **It does not make `assemble_chain` run on real threads.** It captures what that needs and carries
  it to the seam. Feeding it the sibling messages is a separate unit — §3.
* **It does not capture `bcc`.** It records that nobody can — §1.
* **It does not backfill.** The raw payload is encrypted and expires; old events keep `(1, 1)`,
  which is true for a thread we cannot see — §4.
* **It does not measure the corpus.** How many landed events are replies, and therefore how large
  the re-extraction actually is, needs the corpus. **Harsh's.**
