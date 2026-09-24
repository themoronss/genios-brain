# Step 13 — Cross-source identity keys

**Status:** NOT STARTED · **Effort:** weeks · **Depends on:** 3 · **Engine:** D + R, L only for the remainder
**Moves:** metric 6 — P4's blocked objects

> **Added after the first plan.** Steps 1–11 never addressed the join keys P4 needs.

## 1. Why this step exists

Benchmark P4 asks: *for every external meeting, was there a follow-up email within 7 days?* That
join needs one thing — **`Manik` on a calendar invite and `Manik` in an email must be the same
person.**

And the Radhesh finding needs the same machinery from the other side: *a person who was introduced
and then never appeared in a `To:` field.* That is a question about the **recipient graph**, and it
cannot be asked if recipients are not preserved as identities.

**The boundary, stated precisely, because it is easy to get wrong:**

> Layer 2 owns **identity resolution** — deciding that two mentions are one person.
> Layer 1 owns **preserving the keys that make resolution possible**, and never destroying them.

Today L1 has `EntityMention` (typed, with `surface_form`, `entity_type`, `canonical_hint`) and
`validate/canonical.py` ALG-11, which is deliberately **a hint** — "AWS" and "Amazon Web Services"
matched deterministically, no embeddings, and L2 stays authoritative. That design is right.
What is missing is that the **raw join keys never cross the seam** — `recipients` lives inside the
`envelope` JSON blob, which step 3's widened projection carries, and calendar attendees live in
structured fields nothing maps to a person.

## 2. Current status

| Key | Exists in L1? | Crosses the seam? |
|---|---|---|
| `message_id`, `thread_id` | yes | via `envelope` after step 3 |
| sender | yes | yes |
| `recipients` | **yes**, on C-12 as a tuple | inside `envelope` |
| cc / bcc | **not separated** from recipients | — |
| calendar attendees | in structured fields | not as identities |
| `meeting_id` ↔ person | **no mapping** | — |
| introduced-by / replied-to | **not modelled** | — |
| Meeting kind (cohort session vs external) | **no such field** | — |

**Meeting kind is a real gap and it is cheap.** On the pilot's 7 calendar events, **5 were cohort
sessions** where no follow-up is expected. Counting them as "0 of 7 followed up" is a true number
and a misleading finding.

## 3. Expected result

| | Before | After |
|---|---|---|
| Recipient roles | one tuple | `to` / `cc` / `bcc` distinguished |
| Calendar attendees | structured fields | attendee identities with the same key shape as email participants |
| Meeting kind | absent | `external` / `internal` / `cohort` / `unknown` |
| A person's appearances across sources | unjoinable | joinable by L2, because L1 kept the keys |

## 4. Edge cases

| # | Scenario | What must happen |
|---|---|---|
| E1 | Same display name, different address (`keshav@rocketsdr.com` vs `keshav@gmail.com`) | **two identities.** L1 must not merge them; the benchmark names this exact trap |
| E2 | Same address, different display names | one identity |
| E3 | A distribution list | a group, not a person |
| E4 | An address that is also the mailbox owner | `mailbox_owner` already exists; direction depends on it |
| E5 | bcc | visible only to the sender — **`visibility_rules.py` already governs this and must not be bypassed** |
| E6 | Calendar attendee with no email | keep the display name, mark the identity partial |
| E7 | Meeting kind is ambiguous | `unknown`, never guessed |
| E8 | L1 starts resolving identities | **boundary violation.** L1 preserves keys; L2 resolves |

## 5. How to do it

| Unit | What | Engine |
|---|---|---|
| 13-U1 | separate `to` / `cc` / `bcc` on the envelope | D |
| 13-U2 | calendar attendees emitted with the same participant shape as email | D |
| 13-U3 | `meeting_kind` — deterministic first (organiser domain, attendee count, recurrence), model only for the remainder | D, then **L** |
| 13-U4 | participation edges kept as observations: `sent_to`, `cc_on`, `attended`, `introduced_in_thread` | D |
| 13-U5 | a joinability report — what share of calendar attendees have an email-side counterpart key | D |

## 6. Test cases

T1 `to`/`cc`/`bcc` survive to the seam (RED today) · T2 same name + different domain stays **two**
identities · T3 a cohort session is not counted as an external meeting · T4 bcc respects
`visibility_rules` · T5 an attendee with no email keeps a partial identity · T6 **L1 does not merge
identities** — a boundary guard.

## 7. Verify

```bash
uv run --no-sync pytest tests/capture/connectors/test_calendar_actor_identity.py -q -p no:randomly
uv run --no-sync pytest tests/capture/validate/test_canonical.py -q -p no:randomly
uv run --no-sync pytest tests/test_l2_reads_what_l1_publishes.py -q -p no:randomly
```

## 8. Done criteria

**Ticked 2026-09-24.** Three closed, one half, one needs the corpus.

- [~] **`to`/`cc`/`bcc` distinguished and crossing the seam** — **distinguished and carried**
      (`RawObject` → `SourceEvent` → `normalize`), and `recipients` keeps its exact old meaning so
      nothing downstream shifts. **`bcc` is EMPTY everywhere and always will be from Gmail** — the
      API does not supply it and on a received message it is invisible by definition, so E5's
      *"bcc respects `visibility_rules`"* has nothing to govern. The field exists so a source that
      DOES supply it has somewhere to put it. **Half, and marked half.**
      *The seam itself:* the keys are on the typed event; `runner.py:161` still flattens
      `raw["to"] + raw["cc"]`, and teaching L2 to read them is a Layer 2 change.
- [x] **calendar attendees carry participant identities** — and two things stop being thrown away:
      an attendee with a display name and **no address** (a room, a guest invited by name) used to
      vanish at `if a.get("email")`, and `responseStatus` — *"we invited them"* vs *"they came"* —
      went with it. Verified end to end through the real `_to_raw`.
- [x] **`meeting_kind` present, `unknown` when it cannot be told** — and the rung order was
      **corrected**: `COHORT` goes first because it needs no domains and can only ever SUPPRESS a
      follow-up expectation. With the domain check first, a twenty-person recurring session with no
      identifiable owner came back `UNKNOWN` and would have been chased for a recap.
- [ ] **the joinability figure is in `STATUS.md`** — the function exists and is tested; the FIGURE
      needs the live corpus. **Harsh's.**
- [x] **T6 green — L1 still does not resolve identity** — `keshav@rocketsdr.com` and
      `keshav@gmail.com` stay **two** identities, and the module is checked for
      `difflib`/`fuzz`/`levenshtein`/`embedding` and has none.

### 8.1 · The cost check decided the design again

`cache.KEY_COMPONENTS` includes `envelope_hash`, and `extract()` hashes the **rendered prompt block
string**. Rendering a `cc:` line would change it on every event and re-extract the whole corpus.

So the split crosses on the CONTRACT and the prompt is byte-identical — and that is right on its own
terms: **the model does not need cc-from-to to read a message.** `to: a, b, c` is what it was
calibrated on. The split is a Layer 2 join key.

## 9. What this step must NOT do

**Do not resolve identities in L1.** That is L2's, and doing it here would put the graph back
inside the capture layer. Do not merge two addresses because the display names match — E1.
Do not bypass `visibility_rules.py` for bcc.
