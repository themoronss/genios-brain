# L2.5 — Context Quality Engine

**Group responsibility:** stop GeniOS reasoning confidently over stale, partial or
contradictory context.

**Group law:** *Most damaging false positives originate here, not at L4.* A card that is
confidently wrong is almost always a quality failure wearing a reasoning failure's clothes.

**Status:** 4 of 8 built. The confidence machinery is excellent; the absence-handling is missing.

---

## Component map

| # | Component | BLG | Status |
|---|---|---|---|
| L2.5.1 | Confidence Calculation | BLG-14 | ✅ **strong — a real vector** |
| L2.5.2 | Freshness Evaluation | — | ✅ |
| L2.5.3 | Conflict Detection | — | ⚠️ `discrepancies`; **L1 v2 now does the hard part** |
| L2.5.4 | Noise Detection | — | ✅ |
| **L2.5.5** | **Missing Context Detection** | **BLG-15** | ❌ **MISSING** |
| L2.5.6 | Evidence Aggregation | — | ⚠️ flows, not a named component |
| L2.5.7 | Context Completeness | — | ⚠️ `support_situations` only |
| **L2.5.8** | **Context Validation** | — | ❌ MISSING |

---

# ❌ L2.5.5 · Missing Context Detection (BLG-15)

> Globe: *"the most underrated component in the layer — **absence is itself
> intelligence**."*

### L2.5.5-U1 · Typed absence

**WHAT** — Detects and **types** what is missing, rather than letting a gap read as a zero.

**WHY** — Three different things currently look identical downstream:

| The situation | What it means | What it looks like today |
|---|---|---|
| No support tickets, Zendesk connected | genuinely healthy | `0` |
| No support tickets, Zendesk not connected | **unknowable** | `0` |
| No owner recorded on a work item | **a real finding** | absent |

**Conflating the first two is how a false churn signal is born.** "Ticket count dropped to
zero" is great news or no news at all, and today nothing can tell them apart.

The third is the interesting one: *"there is a renewal but no amendment, and no owner is
recorded"* is not missing data — **it is the intelligence.** Globe's Ownership surface is
built entirely on typed absence.

**Input now exists:** L1 v2's `coverage_ready` (finally wired — see L1 doc 01) carries
whether the org's sources could have carried this fact at all.

**WHERE** — `genios_engine/context/quality/missing.py`

**HOW** (BLG-15) — every expected-but-absent fact resolves to exactly one type:

```
for each (subject, expected_fact) in the domain's expectation map:

  if fact present                              -> PRESENT
  elif coverage_ready is False for its domain  -> UNKNOWABLE
       # no connected source could carry this. Never infer from it.
  elif a source could carry it and none did    -> GENUINELY_ABSENT
       # this is a FINDING. "no owner", "no amendment", "no reply"
  elif the fact was present and is now stale   -> STALE
  else                                         -> NOT_EXPECTED
```

**The distinction that matters most: `UNKNOWABLE` vs `GENUINELY_ABSENT`.**
- `GENUINELY_ABSENT` licenses a negative inference — *"nobody owns this"* is safe to say.
- `UNKNOWABLE` licenses nothing. It must degrade the situation's `coverage_score` and, if
  the situation depends on it, block publication rather than produce a hedged card.

**Expectation maps** are declared per domain (which facts a well-formed situation of this
type should carry) — the same declarative discipline as cohorts. `coverage_score` at
`situations.py:189` already takes `expected: dict[str, str]`; this unit supplies it.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| `UNKNOWABLE` treated as `GENUINELY_ABSENT` | **false negative-inference — the worst output in this group** | `coverage_ready` checked first, always; a `None` coverage is treated as `UNKNOWABLE`, never as absent |
| Expectation map too broad | everything is incomplete, nothing publishes | maps are per situation type and start minimal |
| `coverage_ready` never wired | every absence is `UNKNOWABLE` | L1 doc 01 L1.1-U1 wires it; this unit's acceptance depends on it |

**ACCEPTANCE**
```
pytest tests/context/quality/test_missing.py -q
# no tickets + zendesk connected -> GENUINELY_ABSENT
# no tickets + no support connector -> UNKNOWABLE
# coverage_ready = None -> UNKNOWABLE (never absent)
# no owner on a work item -> GENUINELY_ABSENT and emitted as a finding
# a situation depending on an UNKNOWABLE fact does not publish a hedged card
```

**REVERSE PROMPT**
```
TASK: Build missing-context detection. Absence is intelligence — but only when typed.
FILE: genios_engine/context/quality/missing.py

THE PROBLEM: three different things currently look identical downstream —
  (a) no support tickets, Zendesk connected      = genuinely healthy
  (b) no support tickets, no support connector   = UNKNOWABLE
  (c) no owner recorded on a work item           = a real finding
Conflating (a) and (b) is how a false churn signal is born.

PREREQUISITE: L1 v2 coverage wiring (L1 doc 01, L1.1-U1). coverage_ready must be
non-null on events, or every absence collapses to UNKNOWABLE.

Implement:
  class AbsenceType(str, Enum):
      PRESENT, UNKNOWABLE, GENUINELY_ABSENT, STALE, NOT_EXPECTED

  def classify_absence(subject, expected_fact, graph, coverage_map) -> AbsenceType
  def detect_missing(situation, expectation_map, coverage_map) -> list[MissingFact]

ALGORITHM: the ordered cascade in doc 05 section L2.5.5-U1.

HARD RULES:
1. coverage_ready is checked FIRST, before concluding anything is absent.
2. coverage_ready is None -> UNKNOWABLE. Never treat unknown coverage as absence. A
   false negative-inference is the worst thing this component can emit.
3. GENUINELY_ABSENT licenses a negative inference. UNKNOWABLE licenses NOTHING — it
   degrades coverage_score, and if the situation depends on that fact, it BLOCKS
   publication rather than emitting a hedged card.
4. Expectation maps are declared per situation type, start minimal, and live in code
   with a version. Not inferred.
5. PURE. graph and coverage_map are injected.

FEED coverage_score at situations.py:189, which already accepts expected: dict[str, str]
and currently has nobody supplying it.

TEST tests/context/quality/test_missing.py — every row in the ACCEPTANCE list.
```

---

# ✅ L2.5.1 · Confidence Calculation — preserve

`situations.py:102-227` computes a genuine **vector**: `evidence_score`,
`freshness_score`, `consistency_score`, `identity_score`, `coverage_score`, composed by
`score_situation`.

Globe's own open-blocker list names scalar confidence as a correctness defect —
*"cannot distinguish strong-evidence-no-expertise from weak-evidence"*. **L2 already
fixed it.** Do not collapse it to a scalar anywhere for convenience.

**One addition:** an `analytic_score` axis reflecting the quality of comparative inputs
(population size, trend confidence, history depth). A situation whose importance leaned
on a 5-member cohort should be visibly less certain than one that leaned on 200.

---

# ⚠️ L2.5.3 · Conflict Detection — the work moved to L1

**Change of ownership.** L1 v2's `L1.5.5` detects conflicts at extraction time, across
the thread group, with both claims and their evidence retained.

**L2's remaining job is narrower and different:** conflicts that only appear **across
events over time** — an amendment six months later contradicting an original contract.
L1 cannot see that; the claims are in different thread groups.

```
L1 conflict:  two claims in one document group   ($84K email vs $74K attached PDF)
L2 conflict:  two claims across time             (March contract vs September amendment)
```

**HOW** — group by `subject_key` (L1's ALG-22, reused) across the whole graph, not the
thread. Resolution by authority, then by recency **within** the same authority rank —
an amendment beats an original only when both are signed documents.

Continue writing to `discrepancies`; it already feeds `consistency_score`.

---

# ❌ L2.5.8 · Context Validation

**WHAT** — The final gate before candidate generation: is there enough here to publish
a situation at all?

**HOW** — deterministic floor check against the confidence vector. Below the floor the
situation is **held as a candidate**, not published — and the count of held situations is
surfaced, because hiding that things were filtered is how a system loses trust.

**ACCEPTANCE** — a below-floor situation is held, not published; the held count is
queryable; a held situation publishes automatically when new evidence lifts it.

---

## Group acceptance gate

```
pytest tests/context/quality -q
```

| Metric | Gate |
|---|---|
| absences classified as `UNKNOWABLE` when coverage is null | 100% |
| negative inferences drawn from `UNKNOWABLE` facts | **0** |
| confidence vector axes on every situation | all 6 |
| held-below-floor count queryable | yes |
