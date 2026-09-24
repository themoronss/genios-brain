# Re-analysis — what Layer 2 already is

**Run 2026-09-24**, deeper than [`03-PRE-FLIGHT.md`](03-PRE-FLIGHT.md), against `speedrun008`.

⛔ **The first plan was written against the wrong premise.** It read Layer 2 as *half-built* and set
out to build the missing half. **Layer 2 is not half-built. It is built and unswitched** — and
almost everything the plan proposed to create already exists, usually in a stronger form.

---

## 1. ⛔ All five benchmark prompts already have a situation type

This is the finding that changes the plan. `domain_spec` registers **five domains** and each declares
its own situation types **and the fields that type is expected to know**.

| benchmark prompt | L2 situation type | expected fields it declares |
|---|---|---|
| **P1** relationship ledger | **`awaiting_response`** · `reply_owed` | `days_waiting` · `follow_up_count` · `counterparty_role` · ⛔ **`their_normal_reply_days`** · `objective` |
| **P2** commitment ledger | **`commitment_overdue`** | `days_overdue` · `action` · `owed_to` · `owner` · ⛔ **`delivered_at`** |
| **P3** cold threads | **`organization_gone_quiet`** | `contacted` · `awaiting` · ⛔ **`longest_wait_days`** · `relationship` |
| **P4** meeting × email | **`meeting_follow_through`** | `external_counterparty` · `start_at` · `status` · ⛔ **`recap_sent`** |
| **P5** conditional triggers | **`condition_in_review`** · `condition_satisfied` | `actor` · `action` · `text` · ⛔ **`quote`** · `age_days` |

⛔ **`their_normal_reply_days` is P1's "their median reply time" — the one column BOTH Gemini and
Claude skipped.** Layer 2 declared it as an expectation before either model was asked the question.

**The vocabulary to beat the benchmark is already written down.** Nothing has run it.

### Admin declares twelve situation types

```
account_admin · admin_contact · admin_period_review · document_under_control
awaiting_response · reply_owed · commitment_overdue · meeting_follow_through
cohort_outreach_gap · condition_in_review · condition_satisfied · blocked_on_unnamed
```

plus `campaign_awaiting_reply` and `organization_gone_quiet` in its expectations.

---

## 2. ⛔ `fundraising` IS a registered Layer 2 domain

Step 4 said fundraising was dark. **True — but the cause was stated wrongly.**

```python
'fundraising': {'company': 'investor_relationship',
                'person':  'investor_contact',
                'deal':    'investor_relationship'}
```

with expectations `funding.round`, `application_status`, `thread.ball_in_court`, `party.role`.

**Layer 2 mints investor situations today.** They die one layer later, at `l3_domain_for`, because
**no fundraising corpus was authored** — and `live_lane()` refuses a `None` domain.

⛔ **So the fix is not in Layer 2 at all. The situations exist; the doctrine to read them does not.**
That is a corpus-authoring task, and step 4 must say so plainly.

---

## 3. ⛔ Typed absence already exists — with five states, not three

`context/quality/missing.py` — **BLG-15, TYPED ABSENCE**:

```
fact present, current                 → PRESENT
fact present, too old to rely on      → STALE
the expectation does not apply        → NOT_EXPECTED
coverage_ready is not TRUE            → UNKNOWABLE        (False AND None both land here)
a source could have carried it,
every one we can see was checked,
and none did                          → GENUINELY_ABSENT
```

> *"`coverage_ready` is consulted **BEFORE** absence is ever concluded... Doc 05's own failure table
> names the alternative — `UNKNOWABLE` read as `GENUINELY_ABSENT` — as **the worst output the
> quality group can emit**, because it is a false negative inference about a customer delivered with
> a confident receipt."*

⛔ **`step-02-U3` proposed exactly this as new — "an empty `unknowns` under low coverage is
refused". It exists, it is typed five ways rather than binary, and it consults L1's `coverage_ready`
already.** The plan was going to rebuild it worse.

### And the licence is wired end to end

```
quality/missing.py          types the absence
situation_bso.py:2089-90    fills `unknowable` + `absent` into the slice
context_adapter.py:227      reads the licence; refuses to infer absent on an UNKNOWABLE field
```

`quality/inference.py` names why it had to be built:

> *"An org with no mailbox connected therefore satisfies `absent: thread.last_inbound` on every
> situation it has, and the authored rules that read it fire on a blind spot."*

**That bug is fixed.** Both halves are wired.

---

## 4. ⛔ The sentence that describes this whole engine

`quality/inference.py`:

> *"`UNKNOWABLE` is a well-typed value **nobody consults, which is indistinguishable from not having
> built it**."*

That is the eighth time this shape appears, and they are all the same shape:

| | built | switched on |
|---|---|---|
| `domain_shadow` compile | ✅ wired into the live sweep | ⛔ `live=False` for every caller |
| **R-1** ambiguity interpreter | ✅ contract stronger than this plan's | ⛔ *"has never fired on the pilot tenant"* |
| the authored corpus | ✅ 534 capabilities | ⛔ 200 admissible — 37% |
| typed absence | ✅ five states, wired | ⚠️ consulted by the compiler, **never surfaced to a human** |
| the 63 held situations | ✅ `l1_refusal()` fetches the score | ⛔ nothing renders it |
| 33 support situations | ✅ correct refusal | ⛔ *"which is why the miss was invisible"* |
| fundraising situations | ✅ minted by L2 | ⛔ no corpus to read them |
| L1's conversation fields | ✅ landed by step 18 | ⛔ `attention.py:66` still recomputes its own |

⛔ **Layer 2's problem is not construction. It is activation, and the absence of any surface that
says what was refused and why.**

---

## 5. What is GENUINELY missing — the short list

Measured by whether the name appears anywhere in `genios_engine`:

| | files | verdict |
|---|---|---|
| `observed_facts` | **0** | ⛔ genuinely missing |
| `inferred_state` | **0** | ⛔ genuinely missing |
| a Context Reasoner **site** | — | ⛔ missing (the R-1 *pattern* exists) |
| **Persona Brain** | — | ⛔ missing from `BrainKind` and from `ExpertisePackage` |
| card built from a situation | — | ⛔ missing — the loop runs over signals |
| `valid_until` **on a situation** | 8 files, none of them a situation | ⚠️ exists elsewhere |
| `reasoning_trace` | 1 file | ⚠️ barely |
| `hypotheses` | 4 files | ⚠️ present in prose, not as a contract field |
| goals | 0 | ⛔ missing |
| fundraising corpus | — | ⛔ missing, and it is authoring not code |

**Ten items. Four of them are real code. Two are content. The rest is wiring.**

---

## 6. The plan, corrected

| step | was | now |
|---|---|---|
| **L2-0** visible refusals | first | ⛔ **still first, and now larger** — eight unswitched things, not four |
| **L2-1** names | rename | unchanged |
| **L2-2** six fields | build six + four validators | ⛔ **build TWO** (`observed_facts`, `inferred_state`); `unknowns` is `missing_facts` and already better |
| **L2-3** evidence slice | new builder | ⛔ **`build_context_slice` exists and already carries typed absences** — extend it, do not replace it |
| **L2-4** domain compiler | fundraising is dark | ⛔ **restate**: L2 mints investor situations; the corpus to read them was never authored |
| **L2-5** reasoner | new metered site | register an R-site behind `RSiteGate` |
| **L2-6** gate | new gate | write the validator; the gate calls it |
| **L2-7** card | unchanged — ⛔ **this one is genuinely missing and is the step the founder sees** | |
| **L2-8** turn it on | cutover | ⛔ **the admission gap moves here**: 334 capabilities go dark on the flip |

---

## 7. ⛔ What this means for the benchmark claim

The six checks, re-answered against what was found:

| check | verdict |
|---|---|
| catch the bounces | L1 has `delivery_failure` ✅ |
| **catch the Radhesh miss** | `organization_gone_quiet` declares `contacted` vs `awaiting` — **the shape exists**; whether the recipient graph feeds it is untested |
| **P3 / P4 at full coverage** | `organization_gone_quiet` and `meeting_follow_through` **both exist with the right fields**; coverage is a sweep question, not a modelling one |
| report true coverage | ⛔ `coverage_ready` is consulted by the compiler and **never surfaced** — this is a rendering gap, not a data gap |
| resolve 3one4 with the quote | `condition_in_review` declares **`quote`** ✅ |
| stay in scope | a window is a parameter ✅ |

⛔ **Four of six are closer than the pre-flight pass concluded.** The gap is not capability. It is
that nothing has been run, and nothing surfaces what was refused.

---

## 8. The honest one-line summary

> **Layer 2 knows what to look for, knows what it does not know, refuses correctly when it should —
> and tells nobody. The work is to switch it on and let it speak, not to build it again.**
