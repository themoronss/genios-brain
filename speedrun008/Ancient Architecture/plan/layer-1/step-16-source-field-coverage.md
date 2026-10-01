# Step 16 — Source field coverage

**Status:** NOT STARTED · **Effort:** weeks · **Depends on:** nothing (start with 1 and 2) · **Engine:** D
**Moves:** metrics 3 and 6 — everything downstream, because nothing can be extracted from a field that was never fetched

> **Added 2026-09-23 after a reasoning pass.** Steps 1–15 all assume the raw object already
> contains the field. **None of them checks that assumption.** This is the defect class Rohit
> named from experience: *"body uthaya hi nahi, subject uthaya hi nahi, sent hai ya inbox uthaya
> hi nahi."*

---

## 1. Why this step exists

Every other step in this plan improves what L1 *does with* a field. This one asks the question
that comes before all of them:

> **Did we fetch the field at all?**

A field that the connector never pulled cannot be extracted, cannot be validated, cannot be scored
and cannot be published. It fails **silently** — no error, no drop row, no trace entry. It simply
is not there, and every layer downstream behaves as though the world does not contain it.

This is the most expensive class of bug in the layer because it is **invisible to every existing
test**. A unit test on the extractor passes perfectly well on a raw dict that was assembled by the
test itself.

### Three confirmed instances, found by reading the connectors today

**1 · Gmail: `bcc` is never captured.**
`grep -c "bcc" connectors/composio.py` → **0**. The raw dict carries `to` and `cc`. C-12's
`recipients` is built as `tuple(to_emails) + tuple(cc_emails)`. A bcc'd recipient does not exist
anywhere in Layer 1.

**2 · Gmail: `In-Reply-To` and `References` are never captured — and ALG-03 asks for them.**

```python
# structural/threads.py:83 — ThreadMessage
# `in_reply_to`/`references` are the RFC 5322 headers, optional because the Gmail path does
# not carry them yet; when they are absent the chain is reconstructed from `occurred_at`
```

The connector surfaces only `_NOISE_HEADERS` — a curated eight for the N-01/N-02/N-04 rules —
plus `Reply-To`/`Sender`. So `assemble_chain()` (L1.3.6-U2) exists, is tested, and **always falls
back to chronology** on the only mail source we have. A branched thread is reconstructed as a
straight line.

**3 · Calendar: attendee response status is thrown away.**

```python
# connectors/calendar.py:118
attendees = [a.get("email") for a in (ev.get("attendees") or []) if a.get("email")]
```

Google returns `responseStatus` (`accepted` / `declined` / `tentative` / `needsAction`),
`displayName`, `optional`, `resource`. All of it is flattened to a list of email strings.

**So the benchmark's own line — *"Engramme: invites for 25 and 26 Sept, both marked Tentative"* —
is a fact GeniOS structurally cannot see.** Also absent: `recurrence`, `conferenceData` /
`hangoutLink`, `visibility`, `transparency`.

### The pattern

In all three cases the **downstream code is built and correct**. `assemble_chain` handles
`References`. `visibility_rules.py` governs bcc. Step 13 wants attendee identities. The failure is
one layer earlier, at the point of fetch, and nothing anywhere declares what *should* have been
fetched.

---

## 2. Current status

| Source | Captured | Confirmed missing |
|---|---|---|
| **gmail message** | subject · body (full, MIME-walked) · snippet · labelIds (**so SENT/INBOX is there**) · 8 noise headers · Reply-To · Sender · to · cc · has_attachment · important_attachment · threadId · sender | **bcc · In-Reply-To · References · Message-ID header · internalDate** |
| **gmail attachment** | filename · extracted text · mime · to · cc · parent thread | inherits the above |
| **gcal event** | summary · start · end · status · attendees (emails only) · description · location · organizer · calendar_owner · updated · attachments | **attendee responseStatus · displayName · optional · recurrence · conferenceData · visibility · transparency** |
| **hubspot deal** | mapped fields via ALG-21 registry | **unaudited** |
| **notion / gdrive / linear / postgres** | mapped fields | **unaudited** |

**"Unaudited" is the point.** Nobody has ever listed, per source, what the API offers versus what
we take. That list does not exist, so the gap cannot be measured — only stumbled into.

---

## 3. Expected result — the number that must move

| | Before | After |
|---|---|---|
| Sources with a declared field manifest | **0 of 9 buildable** | 9 of 9 |
| Fields fetched but undeclared | unknown | 0 |
| Fields declared but not fetched | unknown | 0, or each one carries a written reason |
| `assemble_chain` running on real headers | **never** | on every Gmail thread |
| Attendee response status | discarded | preserved |
| bcc | invisible | captured, and governed by `visibility_rules` |

**Prediction:** the audit finds **more** gaps than the three above, because three were found by
reading two connectors for twenty minutes. **If the audit finds only three, it was not thorough.**

---

## 4. Edge cases and failure scenarios

| # | Scenario | What must happen | Why |
|---|---|---|---|
| **E1** | A field is fetched but never read by anything | that is **not** a defect — record it as `captured, unused` | over-fetching costs payload size, not correctness; deleting it later is cheap, re-adding it means a re-sync |
| **E2** | A field the API offers is deliberately not taken | the manifest carries the **reason** | a silent omission and a considered one look identical without this |
| **E3** | `bcc` | captured, but `visibility_rules.py` already governs who could see it — **do not bypass that** | a bcc is visible only to the sender; leaking it is a privacy defect, not a feature |
| E4 | The provider adds a field | the manifest drifts. A test must notice | this is how the drift restarts |
| E5 | The provider **removes** a field | the structured lane's `absent_names` already exists for exactly this — reuse it | `structured/lane.py` reports a column that appears empty on every object |
| E6 | Adding a field changes the dedup key | a mutable source needs its `version_field`; adding a field must not silently re-land the corpus | `source_registry`'s `immutable` / `version_field` contract |
| E7 | Payload size grows | raw payloads are encrypted with a TTL; measure the delta | a correctness fix that doubles storage is a trade, not a free win |
| E8 | A newly captured field is PII | `preprocess/pii.py` masks the prepared text; a new raw field must be considered | masking is on the prepared seam, not the raw payload |
| E9 | Back-capture | new fields do **not** appear on already-landed events without a re-sync | say so, rather than letting a partial corpus look complete |

**E1 is the discipline that keeps this step honest.** The goal is not "fetch everything". It is
**"know what we fetch, and why we do not fetch the rest."**

---

## 5. How to do it — unit by unit

### 16-U1 · The field manifest, per source *(no code change)*
For each of the 9 buildable sources, a table with four columns:

```
provider field  |  captured?  |  read by  |  reason if not captured
```

`read by` is found by grep: which module consumes `raw["<field>"]`. A field with no reader is
`captured, unused` (E1), which is information, not a defect.

### 16-U2 · The three confirmed gaps, closed
| Gap | Change |
|---|---|
| Gmail `In-Reply-To` / `References` | add to the surfaced headers → **`assemble_chain` starts running on real data** |
| Gmail `bcc` | capture, and route through `visibility_rules` |
| Calendar attendee objects | keep `responseStatus`, `displayName`, `optional` instead of flattening to emails |

### 16-U3 · The drift ratchet
A test that compares each connector's captured set against its manifest and **fails in both
directions** — an undeclared capture, and a declared field that stopped arriving. Same shape as
`tests/test_every_llm_call_site_is_metered.py`, which already does this for model call sites and
is the proven pattern in this codebase.

### 16-U4 · Re-sync
New fields do not retrofit onto landed events. Plan the re-sync, and **record in `STATUS.md` which
events predate which field** — otherwise the corpus is silently mixed.

### 16-U5 · Audit the remaining six
`hubspot`, `notion`, `gdrive`, `linear`, `postgres`, `database` — same manifest, same ratchet.

---

## 6. Test cases

| # | Test | Asserts | RED today |
|---|---|---|---|
| T1 | a Gmail fixture with `In-Reply-To` | the header reaches `ThreadMessage.in_reply_to` | never captured |
| T2 | a branched thread | `assemble_chain` reconstructs the **branch**, not a straight line | falls back to chronology |
| T3 | a bcc'd message | the bcc recipient is captured **and** `visibility_rules` restricts it | not captured at all |
| T4 | a tentative calendar invite | `responseStatus == "tentative"` survives to the seam | flattened away |
| T5 | the drift ratchet | an undeclared captured field fails the test | no manifest |
| T6 | the drift ratchet, other way | a declared field that stops arriving fails the test | — |
| T7 | adding a field | does **not** change the dedup key or re-land the corpus | E6 |
| T8 | existing noise rules | N-01/02/04 still fire on the same headers | **regression guard** |

T2 is the one worth writing first — it proves a unit that has never once run on production data.

---

## 7. Verify commands

```bash
uv run --no-sync pytest tests/capture/connectors -q -p no:randomly
uv run --no-sync pytest tests/capture/structural -q -p no:randomly
uv run --no-sync pytest tests/capture/test_source_field_manifest.py -q -p no:randomly   # new
uv run --no-sync pytest tests/capture/gate -q -p no:randomly                            # T8

# after a re-sync — the corpus should not change shape, only gain fields
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"
```

## 8. Done criteria

- [x] a field manifest exists for **every source that lands an object**, each uncaptured field
      carrying a reason — `connectors/manifest.py`, **6 sources not 9**. The registry
      (`dispatch._PARSER_IMPORTS`) holds `gmail`, `gcal`, `gdrive`, `notion`, `linear`, `hubspot`.
      `postgres` and `database` in 16-U5 are one module and it emits no `RawObject`; `screen_session`
      is L1's own promoter, not a provider. **Inventing three manifests to reach 9 would have been
      the drift this step exists to end** — a table that disagrees with the code.
- [x] `In-Reply-To` / `References` captured — `composio._THREAD_HEADERS`, and carried onto the
      pipeline's `ThreadMessage`. **T2 passes and proves the opposite of what it was written to
      prove:** `assemble_chain` already reconstructs the branch correctly and is fed a **one-message
      list** by `pipeline.py`, so it still does not run on real threads. Capturing the headers is
      **necessary and not sufficient**; the limit is recorded rather than papered over.
- [~] `bcc` — **IMPOSSIBLE, not deferred.** Gmail's API does not supply it, and on a received
      message it is invisible by definition. Recorded in the manifest as `captured=False` with the
      reason, so it is never re-opened as an oversight. Step 13's `bcc_recipients` field already
      exists to carry one if a source ever offers one.
- [x] attendee `responseStatus` preserved — **already closed by step 13's `read_attendees`.** The
      manifest now says so, rather than leaving a stale TODO that disagrees with the code.
- [x] the drift ratchet fails in both directions — `undeclared_captures` / `missing_captures`, and
      **driven by the real connector's real output**, not by hand-passed sets
- [x] the re-sync boundary written into `STATUS.md` — §4 of the findings file, linked from STATUS
- [x] T8 green — the noise rules are untouched (`_NOISE_HEADERS` asserted byte-for-byte)
- [x] **NOT IN THE ORIGINAL LIST, and the largest finding of the step:** every prompt in production
      said `thread position: message 1 of 1`. Closed by `connectors/thread_position.py`.

## 9. What this step must NOT do

- **Do not fetch everything.** E1 — the goal is a known set with stated reasons, not a bigger
  payload.
- **Do not bypass `visibility_rules.py` for bcc.** Capturing it and exposing it are different
  decisions.
- **Do not change the dedup key** while adding fields. E6.
- **Do not claim the corpus is uniform** after adding a field. Old events do not have it until
  they are re-synced, and that boundary must be written down.
- **Do not touch the noise rules.** They read the same headers they always did.
