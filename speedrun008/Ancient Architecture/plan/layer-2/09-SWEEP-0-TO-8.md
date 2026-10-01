# Layer 2 · the 0→8 sweep — what nine steps left behind

**Run:** 2026-09-24 · after L2-8 · **13,122 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. What the sweep looked for

Not "are the tests green". **Is anything built and reached by nothing** — the defect this layer has
been closing since L2-0, and the one a green suite is worst at detecting.

Every module the nine steps added was audited for a real caller:

| verdict | modules |
|---|---|
| **called on a real path** | `domain_silence` · `expected_facts` · `proposal_gate` · `interpretation_store` · `claim_state` · `unroutable` · `situation_reasoner` · `card_source` |
| **read by a script, by design** | `quality/refusals` · `slice_weight` |
| **data, not behaviour** — checked at import and by tests, like `LAYERS.py` | `situation_stages` · `cutover` · `slice_silence` |

---

## 2. ⛔ Three things the steps themselves missed, all now closed

### 2.1 · L2-3 built a budget for L2-5, and L2-5 never read it

L2-3 measured that a 100-fact anchor produces a slice **as expensive as the thread it replaced**,
and set `SLICE_TOKEN_BUDGET = 2000` *"so L2-5's cost check argues about a number instead of a
feeling."*

**L2-5 shipped sending a slice to a model without consulting it.** The exact defect the layer has
been chasing, committed by the sequence itself, two steps apart.

Closed: `weigh_before_sending` measures the payload, the sweep counts `slice_over_budget`, and
**nothing is truncated** — *"dropping facts to hit a number is how a reasoner concludes from
evidence nobody chose to remove."* The callback is handed in, so the module still holds no I/O.

### 2.2 · S07 was OPEN — and closing it found a fixture that would have crashed the compiler

L2-1 corrected fifteen annotations and recorded that **no test drove the compiler with what
production sends.** The sweep wrote that test.

⛔ **It failed immediately** — `AttributeError: 'NoneType' object has no attribute 'overall_bp'`.
The shared fixture built a situation with `confidence=None`, and the compatibility property
`confidence_bp` dereferences it, so `expertise_builder.py:76` would have crashed on it.

**A fixture production would never produce proves nothing about production.** Now representative,
carrying a real `ConfidenceVector` and `ImportanceAttribution` — and the compile path's ten read
attributes are asserted to resolve.

### 2.3 · A guard that answered plausibly when called wrong, recorded twice and never hardened

`situation_admission_reason`'s `hasattr(authored, "get") else {}` meant a `SourceDocument` handed
in by mistake read `identity_status_absent` **for every document in the corpus**.

L2-0 hit it and reported *"all 69 situations inadmissible"*. L2-5 hit the same class with
`domains_declaring`. Both cost a debugging pass against a number that was never real.

⛔ **And fixing it broke a test that was right**, which sharpened the fix:

| input | is | verdict |
|---|---|---|
| `None` / `{}` | a file that **parsed to nothing** | **refuse** — *"an empty or malformed one must fail closed, not raise into a compile that would then have no route at all"* |
| a `SourceDocument` | a **caller error** | **raise**, naming the right call |

---

## 3. The registry after the sweep

```
40 scenarios · 12 failure classes

closed      29
guard        3
open         0      ⛔ and that is a claim, not a relief
harsh        7      a database read
impossible   1      S20 — `general` is claimed by all three corpora
```

⛔ **Zero OPEN is the assertion that matters.** Everything outstanding is either a number somebody
must read or a decision somebody must make. **No row is open because nobody got to it.**

---

## 4. What is genuinely left, and none of it is code

| # | what | who |
|---|---|---|
| **4e** | apply `0182_signal_situation.sql` | Harsh |
| **4f** | apply `0183_situation_interpretations.sql` | Harsh |
| **21** | run the L2 refusal report on the pilot | Harsh |
| **22** | decide: flip the 24 `draft` situations | Rohit |
| **24** | read `BY LAW`, then arm V-9 / V-10 | Harsh → Rohit |
| **25** | run `slice_weight.py` — L2-5's real p50/p90 | Harsh |
| **26** | ⛔ decide: point `fundraising` at `sales` | **Rohit** |
| **27** | run `card_collapse_report.py` — the 38→N number | Harsh |
| **28** | decide: activate `situation_reasoner` | Rohit |
| **29** | ⛔ read the shadow tallies — the cutover gate | **Harsh** |

**Two of these are the whole product**: #26, because the pilot is a fundraising founder and the
doctrine already exists; and #29, because it is the only thing standing between a layer that is
built and a layer that is on.

---

## 5. Seven switches, all off, each with its number

`reason/cutover.py`, and **a test reads the code and refuses a row that disagrees** — so a flip
that forgets to record itself fails the build.

```
require_admission      ⛔ free — 155 of 155 admissible. The plan budgeted for 334 going dark
publisher              #29
execution_mode         #29, and after the two above
fundraising_route      #26
observing_laws         #24
cards_from_situations  0182, then #27
situation_reasoner     0183, then #28
```

---

## 6. What the nine steps actually were

⛔ **Almost none of this layer was a build.** Of the 46 planned units:

| the plan said | it turned out to be |
|---|---|
| build the refusal accounting | **three quarters already existed** — `l1_refusal` had the score, `situation_admission_decisions` was the ledger, the declared-silence idiom existed twice |
| author a fundraising corpus | **it was authored, inside Sales**, and one `None` hid it |
| add six interpretation fields | **v2 was already full of interpretation** — what was missing was the LABEL |
| build a reasoner slice | **four of five criteria were already true** and nothing watched them |
| build a gate | **the gate existed**; Layer 2 owed the validator |
| 534 capabilities, 37% admissible | **155, and all of them** |
| ~40 situations, a 10× saving | **159, and 2.9×** |
| "the largest saving in the plan" | **about $3 a month** |

**The work was measuring, naming, wiring and guarding — not building.** Every step's premise check
changed its own step, and four of them changed a later one.
