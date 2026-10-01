# Step 2 — The bounce / DSN path

**Status:** NOT STARTED · **PREMISE CORRECTED 2026-09-23 — read §0 first** · **Effort:** days · **Depends on:** nothing · **Engine:** D (deterministic)
**Moves:** metric 6 — benchmark objects present. **This is the demo.**

---

## 0. PREMISE CORRECTION — measured in production, 2026-09-23

**This step was written believing the gate deletes bounces. It does not — not these ones.**

```
mailer-daemon events for the pilot org:   outcome = emitted   n = 5
signals produced from those events:                           n = 0
```

Five Delivery Status Notifications **passed the gate and were emitted**, with `prepared_content`
rows. The reason N-03 did not fire is in its own condition:

```python
if not att and machine:          # ← `not att`
    return ("N-03", "drop")
```

A Gmail DSN carries the original message back as an attachment, so `has_attachment=True`,
so `not att` is False, so **N-03 never fires on it.** The `_DEAD_SENDER` regex is real and the
comment *"a bounce carries no business signal ever"* is still wrong — but it is **not what is
losing the finding here.**

### The real gap is one stage later

```
bounce lands  →  gate passes it  →  extraction runs  →  NO predicate fires  →  0 signals  →  L2 never hears
```

### What this changes in the plan below

| Unit | Was | Now |
|---|---|---|
| 2-U2 gate exemption | the core of the step | **narrowed** — only needed for an **attachment-less** DSN, which N-03 still drops. Verify before building |
| 2-U1 DSN parser | needed | **unchanged, and now the first unit** |
| 2-U3 `DELIVERY_FAILURE` type | needed | **unchanged** |
| 2-U4 predicate | needed | **unchanged — this is where the finding is actually lost** |
| 2-U5 join to the sent message | needed | **unchanged** |
| T1 "a bounce reaches the gate" | RED first | **would have passed immediately.** Rewrite it as: a bounce **produces a signal** |

**Why this correction exists at all:** the plan's own rule is *prove the defect first*. T1 as
originally written would have gone green on today's code and the step would have "proved" a defect
that was not there.

---

## 1. Why this step exists

The benchmark's own words about its single most valuable finding:

> *"Three pitch emails on 11 Aug never reached anyone: `madison@afore.vc` → 550 5.1.1 address not
> found · `joseph@afore.vc` → 550 5.1.1 address not found · `apply@surgeahead.com` → permanent
> failure after 47h of retries. **You believe you pitched Afore and Surge. You didn't.**"*

Layer 1 **deletes this class of mail on purpose**, and twice over:

```python
# genios_engine/capture/gate/rules.py:13-17
# Only DEAD mail is hard-dropped on the sender alone: a bounce/mailer-daemon carries no
# business signal ever.
_DEAD_SENDER = re.compile(r"(mailer-daemon|bounces?@|postmaster@)", re.I)

# :356 — a DSN carries `Auto-Submitted: auto-replied`, so N-01 catches it first
if header(hdrs, "Auto-Submitted", "no") not in ("no", ""):
    return ("N-01", "drop")                  # machine acknowledgement

# :359
if not att and machine:
    return ("N-03", "drop")                  # dead mail (bounce/mailer-daemon)
```

**The comment is false, and the benchmark is the proof.** A bounce is not noise *about* a message.
It is **a fact about a message you sent** — the only record that it did not arrive. On the pilot,
`N-03` dropped **82 emails** and nobody knows how many were bounces.

Why this is the demo: both Gemini and Claude were run against the same mailbox. Claude found the
bounces only because this founder's sent folder is unusually small (39 threads / 90 days) and it
could read essentially all of it. **GeniOS can find them on any mailbox, at any volume**, because
it is a deterministic join over indexed mail — no context window involved.

## 2. Current status — with evidence

| What | State | Where |
|---|---|---|
| DSN detection | none | — |
| `mailer-daemon` sender | **dropped** N-03 | `gate/rules.py:359` |
| `Auto-Submitted` header | **dropped** N-01 | `gate/rules.py:356` |
| RFC 3464 `message/delivery-status` parsing | **does not exist** | grep finds no parser |
| A signal type for it | **does not exist** | `SignalType` has 15 members, none is a delivery failure |
| Join from a failure back to the sent message | **does not exist** | — |

**The exemption pattern already exists and must be copied, not invented.** `availability_marker`
(N-05) does exactly this job for out-of-office mail:

```python
# gate/rules.py:350-353
# N-05 — an availability notice from a real sender passes every traffic-shape rule below: a
# vacation responder carries Auto-Submitted (N-01) and often Precedence: bulk (N-04), which
# would otherwise drop the one message that says who is away.
if availability_marker(ctx.raw) and not (machine and not att):
    return None
```

A DSN is the same shape of problem with the same shape of answer. **Follow this precedent
exactly** — a new bespoke branch in the gate is how that function becomes unreadable.

## 3. Expected result — the number that must move

| | Before | After |
|---|---|---|
| Delivery-failure signals on an 11-Aug replay | **0** | **3** — `madison@afore.vc`, `joseph@afore.vc`, `apply@surgeahead.com` |
| Each carrying the sent message it failed | n/a | **yes, as evidence** |
| `N-03` drop count | 82 | 82 minus the DSNs; **the delta is the finding** |
| Benchmark objects present | 16 of 38 | 17 of 38 |

**Prediction before starting:** on the pilot corpus, the `N-03` bucket contains a small number of
true DSNs — probably single digits, since the benchmark found three in one day of a fundraising
push. **If the replay finds zero, the parser is wrong, not the mailbox** — the bounce notices are
known to be sitting in that inbox.

## 4. Edge cases and failure scenarios

| # | Scenario | What must happen | Why |
|---|---|---|---|
| E1 | Soft bounce (4.x.x — mailbox full, greylisted) | a **separate** state from a hard bounce; retryable, not "never delivered" | telling a founder their pitch failed when it was retried and delivered is worse than silence |
| E2 | Hard bounce (5.x.x) | `DELIVERY_FAILURE`, terminal | the actual finding |
| E3 | Delayed-delivery notice (`Auto-Submitted`, still trying) | **not** a failure yet | Surge's took 47h of retries before failing — during those 47h the true answer is "unknown" |
| E4 | DSN with no parseable `Original-Message-Id` | keep the signal, mark the join **unresolved** | a failure with no linkable message is still a failure; a fabricated join is worse |
| E5 | The sent message was never indexed | join fails; signal stands with `linked=false` | absence of evidence is not evidence of absence |
| E6 | Non-RFC-3464 vendor bounce (plain-text body only) | best-effort parse, and when it fails, park — **never guess a recipient** | a wrong address in a "your pitch failed" card is a credibility loss |
| E7 | An out-of-office also carries `Auto-Submitted` | N-05's existing path must keep working | do not regress availability handling while exempting DSNs |
| E8 | A genuine `noreply@` newsletter | still drops at N-03 | the exemption must be narrow: DSN structure, not sender name |
| E9 | The same bounce arrives twice (retry notice + final) | one signal, superseded or updated | ALG-19's supersession, keyed on the failed message |
| E10 | A bounce for a message sent by someone else in the org | attribute to the actual sender, not the mailbox owner | `_envelope_direction` and `mailbox_owner` already exist for this |

**E1/E3 are the ones most likely to be got wrong.** "Bounced" and "still trying" and "delayed but
delivered" are three different truths, and only the first is the finding.

## 5. How to do it — unit by unit

### 2-U1 · The DSN recogniser *(pure, no I/O)*
A function that answers: *is this raw object a delivery status notification, and what does it say?*
Reads the MIME structure for `multipart/report; report-type=delivery-status` and the
`message/delivery-status` part. Returns `None` when it is not a DSN.

**Artifact:** a new module under `capture/` — sibling to `gate/rules.py`'s helpers.
**Output:** `original_recipient`, `action` (failed / delayed / delivered), `status` (5.1.1),
`diagnostic_code`, `original_message_id`. Every field optional; **`None` is a real answer.**

### 2-U2 · The gate exemption
In `gate/rules.py`, exempt a recognised DSN from N-01 and N-03, **exactly as `availability_marker`
is exempted**. One condition, at the same place, in the same style.

### 2-U3 · The signal type
Add `DELIVERY_FAILURE` to `SignalType` in `contracts/signal.py`.
**This is a deliberate contract change.** The enum is closed and the contract says so — a type
invented at a call site would be a signal nobody reviewed. It also makes the taxonomy **16**, so
the prose correction in step 7 must account for it.

### 2-U4 · The predicate
A detector predicate in `esqe/detector.py` that fires `DELIVERY_FAILURE` when U1's parse says
`action == failed` and the status is 5.x.x. Deterministic, over a typed claim — **not over one of
the untyped bags** (see step 4 for why that matters).

### 2-U5 · The join
Resolve `original_message_id` against the sent event. The joined sent message becomes the
signal's evidence. When the join fails, the signal still publishes with the join marked
unresolved (E4, E5).

### 2-U6 · Importance
A hard delivery failure on an outbound message is intrinsically important — it is a **known
negative outcome of an action the tenant took**. It must clear the qualification floor. Do this
through ALG-17's **existing** terms (signal-type nudge, actor authority), **never by special-casing
the score**.

## 6. Test cases

**RED first — each must fail on today's code for the stated reason.**

| # | Test | Asserts | Fails today because |
|---|---|---|---|
| T1 | a hard-bounce fixture reaches the gate | it is **not** dropped | N-01 drops it on `Auto-Submitted` |
| T2 | the DSN recogniser on an RFC 3464 fixture | recipient, 5.1.1, diagnostic, original id all parsed | no parser exists |
| T3 | a soft bounce (4.x.x) | **not** a `DELIVERY_FAILURE` | nothing distinguishes them |
| T4 | a delayed notice | **not** a failure | same |
| T5 | end to end: bounce + its sent message | one `DELIVERY_FAILURE` signal citing the sent message | the type does not exist |
| T6 | bounce with no original id | signal publishes, join unresolved | — |
| T7 | an out-of-office fixture | still takes the N-05 path unchanged | **regression guard** |
| T8 | a `noreply@` newsletter | still drops at N-03 | **regression guard** — the exemption must not widen |
| T9 | the same bounce twice | one signal, second supersedes | — |
| T10 | the signal clears the tenant floor | published, not in `qualification_drops` | — |

T7 and T8 are the two that keep this step from breaking the noise gate. Write them first.

## 7. Verify commands

```bash
uv run --no-sync pytest tests/capture/gate -q -p no:randomly
uv run --no-sync pytest tests/capture/test_g9_gate_probes.py -q -p no:randomly
uv run --no-sync pytest tests/capture/esqe/test_detector.py -q -p no:randomly
uv run --no-sync pytest tests/contracts/test_l1_contracts.py -q -p no:randomly
uv run --no-sync pytest tests/capture/test_delivery_failure.py -q -p no:randomly   # new

# the proof, on real data
python scripts/pipeline_funnel_report.py --org <org> --database-url "<url>"
```

## 8. Done criteria

**Ticked 2026-09-24**, retroactively — this step was completed before the four-rule checklist in
`plan/README.md` was being enforced, and its criteria were left blank. Two closed, four are
Harsh's and are marked open rather than quietly ticked.

- [x] **T1–T10 all pass, and T1–T6 were RED first** — 19 tests in
      `tests/capture/test_delivery_failure.py`, green. **T1 as written would have passed on
      unchanged code** — see §0 — so it was rewritten against the real defect
      (`envelope_bulk_headers` short-circuiting) before anything was built.
- [ ] **a replay of the tenant's 11 Aug mail yields three delivery-failure signals** — needs a
      scratch Postgres and migration 0176. **Harsh, items 1–2 of `HARSH-ORDER.md`.**
- [ ] **each cites its own sent message as evidence** — same replay, same blocker.
- [ ] **the `N-03` before/after delta is recorded in `STATUS.md`** — the BEFORE is recorded
      (5 bounce events emitted, **0** signals). The AFTER needs the replay.
- [x] `tests/capture/test_g9_gate_probes.py` still passes (it had 1 pre-existing failure — it must
      not gain a second)
- [x] **soft bounces and delay notices produce no failure signal** — `_DELAY_MARKERS` are checked
      BEFORE failure markers, and `status.failed` is False for a delay and for an unclassifiable
      report. *Telling a founder their pitch bounced while Gmail is still delivering it is worse
      than telling them nothing.*

## 9. What this step must NOT do

- **Do not widen the gate exemption beyond DSN structure.** It keys on the MIME report type, never
  on the sender's name. E8 is the guard.
- **Do not special-case importance.** If a delivery failure does not clear the floor through
  ALG-17's existing terms, that is a finding about the floor (step 8), not a licence to bypass it.
- **Do not guess a recipient** from an unparseable body. Park it.
- **Do not report a soft bounce as a failure.**
- **Do not touch N-02, N-04, N-06 or the availability path.**
