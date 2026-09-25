# The Gemini/Claude benchmark — why it happened, and where GeniOS actually stands

**2026-09-25** · measured against `genios-vs-llm-benchmark.html` (23 Sept 2026, one mailbox)

---

## 1. The one sentence that explains every failure in the document

**Neither model has an index. Both retrieve at question time — so their coverage is the size of
their context window, and the only difference is whether they said so.**

| | Gemini | Claude |
|---|---|---|
| read | ~18 threads | 37 threads |
| of | ~465 | ~465 |
| **said** | ⛔ **"18 of 18"** | ✅ **"~8%"** |

**Gemini did not query the denominator. Claude did.** That single API call is the entire difference
between the two columns, and everything downstream follows from it:

| Gemini's answer | what it actually means |
|---|---|
| *"0 explicit commitments"* (P2) | *"0 in the 4% I looked at"* |
| *"No relationships meet the criteria"* (P3) | *"none in the 4%"* |
| *"40 meetings, 0 follow-ups"* (P4) | ⛔ **40 calendar events checked against ONE email thread** |

⛔ **An empty result over an unmeasured slice, reported as a fact about the business.** That is the
exact failure the four specs name thirteen times and call `scoped_absence` — and it is the failure
GeniOS is being built to make impossible.

---

## 2. ⛔ GeniOS already has the cure. It does not administer it.

### 2.1 · The coverage primitive is built, and it was built from THIS benchmark

`genios_engine/capture/coverage/signal_coverage.py`:

```python
indexed: int              # how many objects we actually landed
claimed_total: int | None # ⛔ None means the provider gave us no count — NOT zero
is_estimate: bool         # Gmail's resultSizeEstimate, labelled as an estimate
cursor_exhausted: bool    # did we reach the end, or stop
completeness_bp -> int | None
```

Its own comments, unprompted:

> *"An estimate stored without its label becomes a fact at the first reader, and **'465 of 465'
> then reads as a count somebody could be held to.**"*

> *"**`None` RATHER THAN 10000 IS THE WHOLE POINT.** No denominator means no ratio, and a confident
> 100% here is the exact failure this step exists to prevent."*

⛔ **It uses the benchmark's own number — 465.** Layer 1 step 5 was built from this document.

### 2.2 · ⛔ And `context/` reads it ZERO times

> ## ⛔ CORRECTION — 2026-09-25, during L3-02
>
> **This section was wrong as written, and the correction matters.** The grep behind it asked for
> `signal_coverage|completeness_bp|claimed_total|cursor_exhausted` — the **per-sweep quantitative**
> symbols. Those are indeed not read outside `capture/`. But it was presented as *"`context/` reads
> L1's coverage zero times"*, and that is false: **`context/` reads `source_coverage` in five
> places** (`correlation_resource`, `situations` ×2, `importance`, `support_situations`) and
> `coverage_ready` appears in **forty-odd modules** across `capture`, `context`, `contracts`,
> `packs`, `reason` and `api`.
>
> **Two different things were conflated.** *Domain readiness* — can we see this domain for this org
> — is built, persisted and read everywhere. *Quantitative sweep coverage* — how much of this
> window did we land — is measured and persisted (migration **0178**, on `l1_sync_runs`) and
> **had one writer and zero readers**. The second is what the benchmark needs, and L3-02 built the
> read. The conclusion of this section survives; its evidence did not.

| package | reads L1's coverage |
|---|---|
| `context/` **(the situation builder)** | ⛔ **ZERO** |
| `packs/` | ⛔ ZERO |
| `deliver/` **(the card)** | ⛔ ZERO |
| `executive/` · `feedback/` | ⛔ ZERO |
| `reason/` | 2 files |
| `api/` | 1 file |

**So the layer that builds the `BusinessSituationObject` cannot know what fraction of the mailbox it
saw, and the card cannot print it.**

⛔ **Asked P1 today, GeniOS would make Gemini's mistake with better data underneath** — it would
answer from what it indexed and have no field in which to say *"of 465."*

**This is `not_carried` — L1 step 18's class — at the largest seam in the product:** *"every
measured loss is a value that is computed correctly and then not carried."*

### 2.3 · The bounces are already built too

`capture/delivery_status.py` — **step 2 of Layer 1** — opens with:

> *"On 11 August the tenant pitched Afore and Surge. Three of those messages never reached anyone —
> `madison@afore.vc` and `joseph@afore.vc` did not exist, and `apply@surgeahead.com` failed
> permanently after 47 hours of retries."*

✅ **Benchmark check #1 is done.** And it already handles the coverage case the specs demand:
*"both must stay silent: telling a founder their pitch bounced while Gmail is [down]…"*

---

## 3. ⛔ Why P3, P4 and P5 are IMPOSSIBLE today — and it is one constant

```python
# genios_engine/capture/connectors/backfill.py
DEFAULT_BACKFILL_DAYS = 60
```

| prompt | window asked | GeniOS window | |
|---|---|---|---|
| P1 | 30 days | 60 | ✅ answerable |
| P2 | 60 days | 60 | ✅ answerable |
| **P3** | **6 months** | 60 | ⛔ **impossible** |
| **P4** | **12 months** | 60 | ⛔ **impossible** |
| **P5** | **all time** | 60 | ⛔ **impossible** |

**Three of five prompts are outside the window by construction.** Not badly answered — *not
answerable*.

And the module says exactly why the default is low:

> *"It was 540 for a while; a first Sync then walked 18 months of mail before Layer 2 ran at all —
> hours with an empty graph — which is not what a user pressing Sync asked for."*

⛔ **So this is a SETTING, not a build.** `backfill_days` is per-connection in
`Connection.config`. Raising it for the pilot is an operator action — **and it is the cheapest
possible move on this entire board.**

⚠️ **But raising it alone is a trap.** At 540 days the first sync walks 18 months before Layer 2
runs — *"hours with an empty graph."* The window and a **progressive sync** have to move together,
or the pilot's first impression is a blank product.

---

## 4. The six checks, scored against the code today

| | check | state |
|---|---|---|
| **1** | **Catch the bounces** | ✅ **BUILT** — `capture/delivery_status.py`, names Afore/Surge by address |
| **2** | **Catch the Radhesh miss** | ⛔ **absent** — `recipient_graph` / `never_emailed` return zero. Needs `requested_from` ＋ `responds_to` over the recipient graph → **L3-09** ＋ Cross User |
| **3** | **P3/P4 at full scope** | ⛔ **blocked by `DEFAULT_BACKFILL_DAYS = 60`** — a setting, plus progressive sync |
| **4** | **Report true coverage** | ⚠️ **HALF** — the primitive is built at L1 and **read by nobody**. → **L3-02** |
| **5** | **Resolve the 3one4 contradiction with the verbatim quote** | ✅ **the mechanism exists** — `graph_source_refs` carries `{span, text, page, bbox}`. Gemini's *"$2–3k MRR"* is what a system with no receipt requirement produces |
| **6** | **Stay in scope** | ⛔ **absent** — `observation_interval` returns zero. Claude answered a 30-day prompt with 90-day data; nothing in GeniOS pins a window to a question → **L3-02** |

**Two built, one is a setting, three are steps already in the plan.**

---

## 5. ⛔ What the benchmark changes in the plan

### 5.1 · It confirms the wave order, from evidence rather than from specs

Waves 1 and 2 were put first because the specs' P0 is *"prevent damaging behaviour."* **The
benchmark is that P0 happening, measured, on a real mailbox.** Gemini's *"0 commitments"* and
*"18 of 18"* are `scoped_absence` and the coverage record, failing in public.

### 5.2 · It adds one step, and it is small

| | | |
|---|---|---|
| ⛔ **L3-02b** | **Carry L1's coverage across the seam** | `SignalCoverage` onto the QES → the situation → the card. **The value exists and is dropped.** One seam, no new measurement, no model call |

Everything else the benchmark asks for is already a step: check 2 → **L3-09**, check 3 → a setting
＋ **L3-06**, check 4 → **L3-02/02b**, check 6 → **L3-02**.

### 5.3 · It gives every step a pass/fail test

The plan's steps were graded against spec case IDs. **They can now be graded against five prompts
and one real mailbox** — which is a far harder and far more honest bar.

| step | the prompt that proves it |
|---|---|
| L3-02 / 02b | **P1** — *"state how many threads you read versus how many exist"* |
| L3-03 `scoped_absence` | **P2** — Gemini's *"0 commitments"* must become *"0 in the 8% read"* |
| L3-06 the timer | **P5** — a condition met months ago, noticed with no new mail |
| L3-08 Cross Tool | **P4** — ⛔ *40 meetings joined against **one** email thread* |
| L3-09 typed relations | **P3** — terminal state needs `responds_to` and `fulfills` |
| L3-17 the read | **P2** — *"the 11 Aug template went to 10+ people who had asked specific questions"* |

---

## 6. ⛔ Three honest things this document says that the plan cannot fix

**1 · N = 1, and it is the friendliest possible mailbox.** Claude won P2 because the sent folder is
39 threads in 90 days — *"the win is a property of your low outbound volume, not proof Claude would
scale."* **The same flatters GeniOS.** A high-volume mailbox is where the index actually pays, and
it is where this must be re-run before any claim is made.

**2 · The GeniOS column is empty.** Until the same five prompts run through GeniOS, this document
is a two-way comparison. **Beating Gemini proves nothing — Gemini is the floor. Claude with plain
connectors is the competitor, because that is what every prospect already has for free.**

**3 · Finding #5 is not an engineering finding.** Six rejections in six weeks, then 28 days of zero
outbound. The document says it plainly: *"a founder-behaviour problem in the data, not a product or
architecture problem."* **No step in this plan changes it** — though L3-06 and L3-17 are exactly
what would have surfaced it on day 3 instead of day 28.

---

## 7. The wedge, stated precisely

> *"ChatGPT/Claude read 8% of your inbox and tell you it's 100%. We read all of it."*

**Half of that sentence is already true and unshipped.** GeniOS indexes rather than retrieves, so
coverage is a property of the **sync**, not of the **question** — and L1 already measures it
honestly, down to refusing to print 100% when it cannot prove it.

⛔ **What is missing is not the measurement. It is the six inches between `capture/` and
`context/`.**
