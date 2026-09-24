# Step 13 · Cross-source identity keys — findings

**Run:** 2026-09-24 · premise checked and cost checked BEFORE any code
**Status:** 13-U1 · U2 · U3 · U5 **DONE** · 13-U4 **deferred with a reason** ·
the joinability figure is Harsh's

---

## 1. The premise was right, and the code was worse than it said

§2's table says `to`/`cc` are *"not separated"*. They are separated — **read from the headers,
destroyed one line later, preserved in the raw dict, and destroyed a second time by the only
consumer that reads them.**

```
composio.py:522-525   to_emails / cc_emails read SEPARATELY from the headers
composio.py:318       recipients = tuple(to_emails) + tuple(cc_emails)      ← flattened
composio.py:326       raw={... "to": to_emails, "cc": cc_emails}            ← still there!
context/runner.py:161 recipients = (raw.get("to") or []) + (raw.get("cc") or [])  ← AGAIN
```

**Three chances, all missed.** Nobody ever had to re-derive it; it was already there, twice. That is
this plan's thesis in four lines of one repository.

Why it matters: *"was this person written TO, or copied?"* is the difference between a participant
and an observer — and the Radhesh finding (*a person introduced and then never in a `To:` field*) is
a question about exactly that.

| Written premise | Verdict |
|---|---|
| `to`/`cc` not separated | ⚠️ **worse** — separated, then flattened twice |
| calendar attendees not identities | ✅ confirmed, and they lose two things (§3) |
| `meeting_kind` absent | ✅ confirmed |
| E5 · bcc governed by `visibility_rules` | ❌ **bcc is not available at all** — §4 |

---

## 2. ⛔ The cost check decided the design, for the fourth time

`cache.KEY_COMPONENTS` includes **`envelope_hash`**, and `extract()` passes
`envelope=call.envelope` — **the rendered prompt block string**.

> Rendering a `cc:` line into `_envelope_block` changes that string **on every event** and
> re-extracts the entire corpus.

So the split crosses on the **CONTRACT** and the prompt is left byte-identical. And that is not a
compromise:

**The model does not need cc-from-to to read a message.** `to: a, b, c` is what the prompt has
always said and what the model was calibrated on. The split is a **Layer 2 join key**. Paying a
re-extraction to tell a model something irrelevant to it would be the worst of both outcomes.

Pinned by `test_the_rendered_envelope_block_is_byte_identical`.

---

## 3. What was built

### 3.1 · 13-U1 — the split survives, additively

`to_recipients` / `cc_recipients` / `bcc_recipients` on `RawObject` **and** `SourceEvent`, and
`landing/normalize.py` carries them.

**`recipients` keeps meaning exactly what it meant** — everyone on the message. It is read by the
gate, by `derive_visibility`, by the audience multiplier and by the thread reconstructor, and a step
that redefined it to *"to only"* would silently change the audience size on every scored signal in
the system. That is the shape of mistake steps 9 and 12 both made; this one is additive by
construction and a test asserts it.

### 3.2 · 13-U2 — an attendee is a person

`calendar.py` read `[a.get("email") for a in attendees if a.get("email")]`, which threw away two
things:

| | |
|---|---|
| **the person** | an attendee with a display name and no address — a room, or a guest invited by name — **vanished entirely**. Dropping them decides for Layer 2, invisibly |
| **`responseStatus`** | the difference between *"we invited them"* and *"they came"*, and P4 asks about meetings that **happened** |

Both survive now. `recipients` and `raw["attendees"]` are byte-identical to before; the richer list
travels beside them, verified end to end through the real `_to_raw`.

### 3.3 · 13-U3 — meeting kind, and why it is worth so little effort

On the pilot's 7 calendar events, **5 were cohort sessions** where no follow-up is expected.
*"0 of 7 followed up"* is a true number and a misleading finding.

`calendar.py` already recorded the cost in its own comment: *"a meeting cannot be told apart from a
broadcast, and 'send a recap' shipped on twenty-person cohort workshops the founder attended as one
participant."*

**The rung order was corrected once, and the correction matters.** `COHORT` now goes FIRST:

* it **needs no domains** — twenty people on a recurring invite is a session whoever organised it;
* it is the only rung that can only ever **SUPPRESS** an expectation. Being wrong here costs a
  missed nudge; being wrong the other way costs a founder a recap email to twenty strangers.

With the domain check first, a twenty-person recurring session whose owner we could not identify
came back `UNKNOWN` and would have been chased. Caught by
`test_meeting_kind_reaches_the_raw_payload`.

### 3.4 · 13-U5 — joinability

*"What share of calendar attendees have an email-side counterpart key."* Without it **P4's answer is
unfalsifiable**: *"no follow-up found"* could mean no follow-up happened, or that the two sides were
never joinable at all — and those have opposite fixes. Gemini's 18-of-18 with a different
denominator.

Zero attendees reports 0, not a perfect join.

---

## 4. E5 is wrong: bcc is not available

The step says *"bcc respects `visibility_rules.py`"*. `grep -rn "bcc" genios_engine/capture/
connectors/` returns **nothing** — Gmail's API does not hand it to us, and on a message we RECEIVED
the bcc list is invisible by definition.

There is nothing for `visibility_rules` to govern. The field exists on both contracts so a source
that DOES supply it has somewhere to put it, and **it is empty everywhere today**. An empty field
with a recorded reason is honest; a missing one means the next connector author invents a key and
the split drifts again.

---

## 5. What was NOT built

**13-U4 · participation edges as observations** (`sent_to`, `cc_on`, `attended`,
`introduced_in_thread`).

Three of the four are now **derivable** from what this step preserved — `to_recipients`,
`cc_recipients` and the attendee list are the edges, stated as data rather than as rows.
`introduced_in_thread` is the fourth and it is genuinely different: it needs the thread's history,
which is a cross-event question, and **step 12 deferred fulfilment detection for exactly the same
reason** — L1's unit of work is one event.

Materialising edges L2 can already derive would be storing a join twice, and the two copies drift.
Recorded rather than half-built.

---

## 6. Guards held

| | |
|---|---|
| The rendered envelope block | **byte-identical** — no `cc:` line, no `envelope_hash` change, no re-extraction |
| `vocabulary_fingerprint` | `a3d5496aa0d3` |
| `recipients` | unchanged meaning and unchanged contents, on email and calendar both |
| §9 · L1 does not resolve identity | `keshav@rocketsdr.com` and `keshav@gmail.com` stay **two** identities; the module is checked for `difflib`/`fuzz`/`embedding` and has none |

---

## 7. Test result

```
FULL SUITE      12669 passed · 1061 skipped · 152 xfailed · 14 failed
                                                           └── all 14 pre-existing
before step 13: 12646 passed · 14 failed
```

**Zero regressions, +23 tests.** No migration, no model call, no re-extraction, no prompt change.

---

## 8. What this step does NOT do

* **It does not resolve any identity.** §9 — that is Layer 2's, and doing it here would put the
  graph back inside the capture layer with less information than the layer that owns the question.
* **It does not give L2 the split yet.** `runner.py:161` still flattens `raw["to"] + raw["cc"]`.
  The keys now exist on the typed event; teaching L2 to read them is a Layer 2 change.
* **It does not measure joinability on real data.** The function exists; the figure needs the
  corpus — Harsh's.
