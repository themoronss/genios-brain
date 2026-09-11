# L2.7 — Business Situation Engine

**Group responsibility:** turn a graph pattern into a named business reality.

**Group law:** *L2 may say "there is an AWS renewal situation." It may not say "don't
renew AWS."*

**Package:** `genios_engine/context/situations.py`, `situation_bso.py`
**Output:** `BusinessSituationObject` — Layer 2's only output
**LLM sites:** **M-4 (resolution), M-6 (framing), M-7 (timeline), M-8 (clustering).**
Four sites — this is the most LLM-dependent group in Layer 2, because framing a situation
is *construction*, not checking.

---

## Component map

| # | Component | BLG / LLM | Wave | Status |
|---|---|---|---|---|
| L2.7.1 | Situation Detection | — | — | ✅ exists |
| L2.7.2 | **Situation Builder + Framing** | **M-6, M-7** | **X6** | ⚠️ **assembles; does not FRAME** |
| L2.7.3 | Situation Clustering | BLG-17, **M-8** | X6 | ✅ deterministic exists |
| L2.7.4 | **Situation Prioritization** | **BLG-18** | **X5** | 🔴 **BROKEN — hardcoded 5000** |
| L2.7.5 | Situation Confidence | — | — | ✅ **strong** |
| L2.7.6 | Situation State | — | — | ✅ exists |
| L2.7.7 | **Situation Lifecycle** | BLG-19, **M-4** | **X6** | 🔴 **cannot detect a STATED resolution** |
| L2.7.8 | Situation Publisher | — | X5 | ⚠️ update for QES input |

**Two defects, not one.** The hardcoded importance flattens ranking. The lifecycle gap
turns the product into a nagging machine.

---

# 🔴 L2.7.4 · Situation Prioritization (BLG-18) — the fix

### The defect

`context/situation_bso.py`:

```python
DEFAULT_IMPORTANCE_BP = 5000          # line 39
...
importance_bp=DEFAULT_IMPORTANCE_BP,  # line 235
```

**Every `BusinessSituationObject` ever produced carries importance 5000.**

The `BusinessSituationObject` contract *requires* `importance_bp`
(`contracts/domain_expertise.py:65`, validated by `require_bp`). L2 has nothing to
compute it from — so it satisfies the contract with a constant.

### The full chain, end to end

```
L1 refuses to stamp importance_bp          contracts/gated_event.py:28  (deliberate)
   |
   v
L2's BSO contract REQUIRES importance_bp   contracts/domain_expertise.py:65
   |
   v
L2 hardcodes 5000                          situation_bso.py:39          <-- HERE
   |
   v
every situation is equally important
   |
   v
"193 of 223 signals scored an identical 50"  reason/reasoners/priority.py:165-197
   |
   v
priority_override supplied for every candidate
   |
   v
"the formula has never once decided anything"  reason/decision_maker.py:243
   |
   v
two different tenants receive IDENTICAL rankings
```

**This is one constant, and it is the reason ranking does not work anywhere in GeniOS.**

L1 v2's ALG-17 is the **supply** side of the fix. BLG-18 is the **demand** side. Neither
works alone: L1 can compute importance perfectly and L2 will still stamp 5000 over it
unless this unit changes.

### L2.7.4-U1 · Situation importance composition (BLG-18)

**WHAT** — Composes a situation's importance from its constituent signals **plus** what
only L2 knows.

**WHY** — A situation is not one signal. It is several signals about one thing, plus
graph context none of them had individually.

**WHERE** — `genios_engine/context/situations.py`
**WHEN** — X5. Requires L1 v2 W7 shipped (signals arriving with real `importance_bp`), and
L2.4 (the analytic stratum) for the modifiers.

**HOW** (BLG-18) — integer basis points throughout:

```
1. BASE — the strongest constituent signal, not the average.
   base_bp = max(signal.importance_bp for signal in situation.signals)

   Why max and not mean: a situation containing one critical signal and four routine
   ones is a critical situation. Averaging would bury it — which is precisely the
   "small critical things get buried" failure Globe names at L4.

2. CORROBORATION — independent signals about the same subject raise it, bounded.
   distinct_sources = count of distinct source systems across constituent signals
   corroboration_bp = min(1500, (distinct_sources - 1) * 500)

   Rule 11 compliant: the raise is bounded and its evidence is nameable — the
   additional sources ARE the named independent evidence.

3. L2-ONLY MODIFIERS — the part no signal could know alone:

   a. TREND            declining trend on a related metric       +1000
                       (from L2.4.3; requires trend_confidence_bp >= 5000)
   b. COHORT POSITION  bottom decile of its cohort               +1000
                       top decile on a risk metric               +1000
                       (from L2.4.5; requires population >= 5)
   c. ANOMALY          flagged vs its own baseline               +800
                       (from L2.4.8)
   d. DEPENDENCY       N items blocked on this situation         +200 * min(N, 5)
                       (from L2.3.8 — the cost is the blocked work)
   e. CONFLICT         an unresolved material conflict           +700
                       (from L1 v2 L1.5.5 — we may be about to say something false)
   f. STALENESS        newest evidence older than 90 days        -1500

4. COVERAGE PENALTY — an honest discount for what we cannot see.
   if coverage_ready is False for the situation's domain:
       importance_bp = importance_bp * 8 // 10
   We are less sure this matters, because we cannot see all of it.

5. CLAMP  0 .. 10000

6. COMPONENTS — store every term, as at L1. "Why is this a 7400?" must be answerable
   from stored data without recomputation.
```

**Design points:**

- **`max`, not `mean`, in step 1.** This is the single most important choice in the
  formula. Averaging is how a critical signal gets buried under routine ones.
- **Step 3 is the justification for the whole analytic stratum.** Trend, cohort position
  and anomaly are things *no individual signal could know*. This is where L2 earns its
  place in the stack rather than passing L1's numbers through.
- **Step 4 is honesty, not caution.** Discounting for missing coverage means the system
  says "I am less sure this matters" rather than pretending its view is complete.

**LLM** — no. **EMBEDDINGS** — no.

**STORAGE** — `situations.importance_bp` + `situations.importance_components` (JSONB) +
`importance_version`.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| L1 not yet shipping real importance | back to a flat distribution | **gate**: if >90% of incoming signals carry importance 5000, log `L1_IMPORTANCE_NOT_ACTIVE` loudly rather than producing a fake spread |
| Modifiers dominate the base | a routine signal with a trend outranks a critical one | modifiers are capped at +4000 total; the base can reach 10000 alone |
| Trend confidence too low to trust | noise amplified into importance | modifier 3a requires `trend_confidence_bp >= 5000` |
| Cohort too small | meaningless percentile drives importance | modifier 3b requires `population >= 5` |
| Version drift after a weight change | historical importance incomparable | `importance_version` stored on every situation |

**ACCEPTANCE**
```
pytest tests/context/test_situation_importance.py -q
python scripts/situation_importance_distribution.py --org <pilot> --since 30d
```

Required unit rows:
- a situation of one signal at 8100 -> base 8100, not 5000
- one critical (9000) + four routine (3000) -> **>= 9000**, proving `max` not `mean`
- three distinct sources -> +1000 corroboration, capped at 1500
- a declining trend with `trend_confidence_bp = 4000` -> **no** trend modifier
- `coverage_ready=False` -> importance is 80% of the same situation with coverage
- every situation carries populated `importance_components`
- determinism: same inputs twice -> identical

Required distribution rows (the real gate):

| Metric | Gate |
|---|---|
| distinct `importance_bp` values across 30 days | **> 50** |
| p90 − p50 spread | **> 1500** |
| situations still at exactly 5000 | **< 5%** |
| situations whose importance changed after L2.4 landed | **> 0** — proves the modifiers fire |

**REVERSE PROMPT**
```
TASK: Fix situation prioritization. This is the demand side of the ranking unlock.

THE DEFECT: genios_engine/context/situation_bso.py line 39 defines
DEFAULT_IMPORTANCE_BP = 5000 and line 235 stamps it on EVERY BusinessSituationObject.
The BSO contract requires importance_bp (contracts/domain_expertise.py:65) and L2 has
nothing to compute it from, so it satisfies the contract with a constant.

Downstream: reason/reasoners/priority.py:165-197 records "193 of 223 signals scored an
identical 50", which forces priority_override on every candidate, which is why
reason/decision_maker.py:243 records "the formula has never once decided anything".
One constant flattens ranking across the whole product.

PREREQUISITES (both, this will not work without them):
  - L1 v2 W7 shipped: incoming signals carry a real importance_bp
  - L2.4 analytic stratum: trend, cohort position, anomaly available

FILE: genios_engine/context/situations.py

Implement:
  def compose_situation_importance(signals, graph_context, *, eval_time)
        -> tuple[int, dict[str, int]]     # (importance_bp, components)

FORMULA: the 6 ordered steps in doc 07 section L2.7.4-U1.

HARD RULES:
1. Step 1 is max(), NOT mean(). A situation with one critical signal and four routine
   ones is critical. Averaging buries it. Test this pair explicitly.
2. INTEGER MATH ONLY. No float. Source-grep test.
3. eval_time is an explicit parameter. No datetime.now().
4. ALWAYS return the components dict. Store it as JSONB alongside the score.
5. Modifiers are capped at +4000 combined. The base alone can reach 10000.
6. Trend modifier requires trend_confidence_bp >= 5000. Cohort modifier requires
   population >= 5. A weak input must not become a strong modifier.
7. GUARD: if more than 90% of incoming signals carry exactly 5000, do NOT produce a
   synthetic spread. Log L1_IMPORTANCE_NOT_ACTIVE loudly and keep the base. A fake
   distribution is worse than a flat one because it looks like it works.
8. Store importance_version. Weights are a versioned constant.

THEN: replace the DEFAULT_IMPORTANCE_BP usage at situation_bso.py:235 with the composed
value. Keep the constant defined and used ONLY as the documented fallback when a
situation somehow has no signals — and make that path log.

MIGRATION: add importance_components jsonb and importance_version text to situations.

TEST tests/context/test_situation_importance.py — every unit row in the doc 07
ACCEPTANCE list.
ALSO write scripts/situation_importance_distribution.py reporting distinct values, p50,
p90 and the share still at exactly 5000.
```

---

# 🔴 L2.7.7 · Situation Lifecycle + Resolution Detection (M-4)

> **The second defect, and the one the customer feels first.** A situation that resolved
> but stays open is a nagging machine, and Globe names the consequence exactly:
> *"It told me about a contract I cancelled last week"* — instant credibility loss.

### The defect

`situations.py:278 decide_lifecycle` is genuinely good code — the fact/human distinction
is correct and thoughtfully documented. But there are **only two ways a situation ends:**

| Path | Trigger | Reversible? |
|---|---|---|
| `RESOLVED_BY_FACT` | `terminal_by_fact` | ✅ recomputed each pass |
| `RESOLVED_BY_HUMAN` | someone clicks | reopens on new evidence |

And `terminal_by_fact` is **only** `normalize_stage(deal.stage) in {closedwon, closedlost}`
(`situations.py:80`, `:417`). **One field. One source. Two values.**

**There is no third path: resolved because somebody SAID so.**

| What happens | Today |
|---|---|
| HubSpot stage → closed-won | ✅ resolves |
| Someone clicks "handled" | ✅ resolves |
| *"All sorted, we signed yesterday"* | ❌ **bumps `last_seen_at` → looks MORE active** |
| A commitment fulfilled in an email | ❌ never detected |
| A decision made in a thread | ❌ never detected |

**A stated resolution makes the situation look more alive, not less.** That is the exact
inversion of what the founder experiences.

### Why deterministic cannot close this

A rule can check `stage == closedwon`. It cannot read a paragraph and decide the thing is
over. That is **construction of meaning**, not checking — and it is why M-4 exists.

### L2.7.7-U1 · Resolution detection (M-4)

**WHAT** — Judges whether a message landing on an open situation states that it is resolved.

**WHERE** — `genios_engine/context/lifecycle/resolution.py`
**WHEN** — X6. Requires L1 v2 QES input (evidence spans).

**HOW — deterministic gate first, then the model:**

```
1. GATE (deterministic — no LLM yet)
   fires ONLY when:
     situation.status == ACTIVE
     AND a new signal landed on it this drain
     AND terminal_by_fact is False        <- a fact beats a statement, always
   Otherwise: no call. This is the volume control.

2. CANDIDATE (deterministic)
   the signal's extraction already carries decision_states[] and commitments[]
   from L1. If a DecisionState says state == "made" for this subject -> strong prior.

3. M-4 CALL (T2)
   input:  the situation's subject, its open obligations, and the new message text
   asks:   does this message state that this specific thing is complete?
   returns: {verdict, scope, speaker_role, quote, offsets, confidence_bp}
   verdict in {RESOLVED, PARTIALLY_RESOLVED, NOT_RESOLVED, CONTRADICTED}

4. VALIDATE (deterministic)
   span must verify against source (reuse L1's ALG-08)
   speaker authority check (below)
   confidence floor

5. APPLY
   RESOLVED_BY_STATEMENT   -> a NEW resolution path, reversible like RESOLVED_BY_FACT
   PARTIALLY_RESOLVED      -> a NEW state, not a full close
   below floor             -> human review queue, NOT a card
```

### The two new states

```python
RESOLVED_BY_STATEMENT = "statement"      # joins fact | human
STATUS_PARTIALLY_RESOLVED = "partial"    # 3 of 5 obligations done
```

`RESOLVED_BY_STATEMENT` behaves like `RESOLVED_BY_FACT`, **deliberately**: re-derived each
pass, and it **un-resolves itself** when new evidence contradicts it. Following the
existing docstring's own reasoning — *"the system should not need a human to undo a
conclusion it drew from data that has since changed."*

### Speaker authority — who says it matters

| Speaker | Effect |
|---|---|
| the obligation's **owner** | full weight |
| org-internal, not the owner | 0.8 weight |
| **external counterparty** | 0.6 weight — *"we're done"* from a vendor is a claim, not a fact |
| automated / service account | **ignored entirely** |

**FAILURE MODES — this is the most dangerous LLM site in Layer 2**

| # | Case | Consequence | Mitigation |
|---|---|---|---|
| 1 | *"we should wrap this up"* read as resolved | **premature close — the founder loses the thread** | verdict requires a completion statement, not an intent; confidence floor |
| 2 | 3 of 5 commitments done | whole situation closes | `PARTIALLY_RESOLVED` is a distinct state |
| 3 | Vendor says "done", org disagrees | wrong close | speaker-authority weighting |
| 4 | *"well that's sorted then 🙄"* | sarcasm read literally | low confidence -> review queue; never auto-close on a single short message |
| 5 | Thread says "done" then "actually not yet" | stale close | **latest statement wins**; `CONTRADICTED` reopens |
| 6 | **Hinglish**: *"ho gaya"*, *"kal kar denge"* | missed or mis-read | the codebase is already multilingual — `triage.py` carries `jaldi\|turant\|kal\|parso`. The prompt must handle mixed-script input, and the golden set must include it |
| 7 | Budget exhausted | silent miss | **fail to `terminal_by_fact`** — we may miss a resolution; we never invent one |

**Failure direction is asymmetric and the design must respect it:** missing a resolution
costs one unnecessary nudge. Inventing one **loses the thread entirely** and the founder
never learns it happened. Every threshold leans toward *not closing*.

**ACCEPTANCE**
```
pytest tests/context/lifecycle/test_resolution.py -q
```
Required: *"all sorted, we signed yesterday"* on an open renewal → `RESOLVED_BY_STATEMENT`
with a verifying span; *"we should wrap this up"* → `NOT_RESOLVED`; 3-of-5 →
`PARTIALLY_RESOLVED`; a vendor-stated close → reduced weight, below floor without
corroboration; `"done"` then `"actually not yet"` → open; a Hinglish *"ho gaya"* fixture
→ detected; `terminal_by_fact=True` → **no LLM call at all**; budget exhausted → falls to
fact-only and logs.

**REVERSE PROMPT**
```
TASK: Add resolution detection. Today L2 cannot tell when something ENDED.

THE DEFECT: situations.py:278 decide_lifecycle has exactly two resolution paths —
terminal_by_fact and RESOLVED_BY_HUMAN. And terminal_by_fact is ONLY
normalize_stage(deal.stage) in {closedwon, closedlost} (situations.py:80, :417). One
field, one source, two values.

So when someone writes "all sorted, we signed yesterday", that message bumps last_seen_at
and the situation looks MORE ACTIVE. The product nags the founder about work that is done.
Globe names the consequence: "It told me about a contract I cancelled last week."

FILES: genios_engine/context/lifecycle/resolution.py (new)
       genios_engine/context/situations.py (extend decide_lifecycle)

IMPLEMENT the 5 ordered steps in doc 07 section L2.7.7-U1.

ADD two states:
  RESOLVED_BY_STATEMENT = "statement"     # joins fact | human
  STATUS_PARTIALLY_RESOLVED = "partial"

RESOLVED_BY_STATEMENT must behave like RESOLVED_BY_FACT: re-derived every pass, and it
un-resolves itself when contradicted. Follow the reasoning already in decide_lifecycle's
docstring — the system should not need a human to undo a conclusion drawn from data that
has since changed.

HARD RULES:
1. DETERMINISTIC GATE FIRST. No LLM call unless status==ACTIVE and a new signal landed
   and terminal_by_fact is False. A FACT ALWAYS BEATS A STATEMENT.
2. The model returns a verdict + scope + speaker_role + quote + offsets + confidence.
   It NEVER returns a _bp score that feeds ranking, and it never sets the status directly.
3. Span must verify against source using L1's ALG-08 validator. Reuse it; do not write
   a second one. An unverified span -> no resolution.
4. SPEAKER AUTHORITY weighting per doc 07's table. A service account is ignored entirely.
5. LATEST STATEMENT WINS within a thread. A CONTRADICTED verdict reopens.
6. ASYMMETRIC THRESHOLDS. Missing a resolution costs one nudge; inventing one loses the
   thread. Lean toward NOT closing. Below the confidence floor goes to a human review
   queue, never to a card.
7. BUDGET EXHAUSTED -> fall back to terminal_by_fact and LOG. Never silently skip.
8. MULTILINGUAL. This codebase already handles Hinglish (triage.py: jaldi|turant|kal|
   parso). The prompt must handle mixed-script input and the golden set must include
   Hinglish resolution statements.

DO NOT change the existing fact/human paths. This is additive.

TEST tests/context/lifecycle/test_resolution.py — every row in doc 07's ACCEPTANCE list.
```

---

# ⚠️ L2.7.2 · Situation Builder + Framing (M-6, M-7)

**WHAT EXISTS** — `situation_bso.py` assembles entities, relationships, timeline and
dependencies into a valid object. That assembly is correct.

**WHAT IS MISSING** — it does not **frame**. A pattern match yields *"these five
conditions held"*. Turning that into *"the AWS renewal decision is unowned with 12 days
left on the cancellation window"* is **synthesis**, and no amount of assembly produces it.

Likewise the timeline: a chronological sort is not a **narrative**. Which events matter,
in what order, and what the shape of the story is — that is construction.

### L2.7.2-U1 · Situation framing (M-6)

**HOW — span-constrained, exactly like L1's extractor:**
```
input:  the situation's member facts, matched pattern conditions, entities, dates, amounts
asks:   frame this in one sentence, using ONLY the supplied facts
returns: {headline, subject_label, why_it_matters, evidence_span_refs}

CONSTRAINT: every noun and every number in the output must trace to a supplied fact.
            Numbers are TEMPLATED IN, never generated by the model.
```

**Numbers come from the template, not the model.** The model chooses the sentence; the
`$84,000` and the `12 days` are substituted deterministically. This is the same rule that
makes L1's render safe, applied here.

**FAILURE MODES**

| # | Case | Mitigation |
|---|---|---|
| 7 | Model invents a fact not in the members | span-constrained; any unsupported noun fails validation and falls back to a deterministic template headline |
| 8 | Framing contradicts the matched conditions | **pattern conditions are authoritative**; framing describes them and cannot override |
| 9 | A number drifts in the prose | numbers are templated, never generated |

**Fallback is a real path, not a theoretical one:** if framing fails validation or the
budget is out, the situation publishes with a **deterministic template headline**. A
plainer card is always better than a wrong one.

### L2.7.2-U2 · Timeline narrative (M-7)
Selects and orders the events that matter and states the shape (*"promised in April,
silent since June, deadline in twelve days"*). Same span constraint. Chronology stays
deterministic; **selection and shape** are the model's contribution.

### L2.7.3-U2 · Clustering judgment (M-8)
Deterministic shared-entity clustering runs first and handles the clear cases. M-8 sees
only the ambiguous pairs: *are these two situations one reality?* Without it the product
becomes, in Globe's words, *"noise on day two"* — three cards about one thing.

---

# ✅ L2.7.5 · Situation Confidence — preserve, do not touch

This component is **better than the Globe spec** and must survive the refactor.

`context/situations.py:102-227` computes a genuine confidence **vector**:

| score | function | what it measures |
|---|---|---|
| `evidence_score` | `:102` | event count and source count |
| `freshness_score` | `:120` | age of the newest supporting evidence |
| `consistency_score` | `:143` | open discrepancies against this subject |
| `identity_score` | `:153` | open merge proposals — is the entity resolved? |
| `coverage_score` | `:189` | present fields vs expected |
| `score_situation` | `:227` | composition |

Globe's own open-blocker list names *"confidence modelled as a scalar rather than a
vector — cannot distinguish strong-evidence-no-expertise from weak-evidence"* as a
correctness defect. **L2 already fixed it.** Do not collapse it back to a scalar for
convenience anywhere downstream.

**One change only:** add an `analytic_score` axis reflecting the quality of the
comparative inputs (population size, trend confidence, history depth), so a situation
whose importance leaned on a thin cohort is visibly less certain than one that did not.

---

# ⚠️ L2.7.8 · Situation Publisher — update for QES input

**WHAT** — Emits the `BusinessSituationObject`.

**CHANGE** — the input becomes `QualifiedEnterpriseSignal` rather than `GatedEvent`.
Concretely:

| BSO field | v1 source | v2 source |
|---|---|---|
| `signal_ids` | event ids | **QES signal ids** |
| `type` | `situation_type(anchor_type, domain)` | **QES `signal_type` + pattern match** (L2.6) |
| `importance_bp` | **hardcoded 5000** | **BLG-18** |
| `confidence_bp` | `score_situation` | unchanged, + `analytic_score` |
| `evidence` | event refs | **QES verified evidence spans** |
| `metadata` | — | + `conflicts`, `trends`, `cohort_positions` |

**The evidence upgrade is significant.** Today a situation's evidence is a list of event
references. In v2 it is a list of **span-validated verbatim quotes** — so a card can show
the sentence, not just name the email.

**ACCEPTANCE**
```
pytest tests/context/test_situation_publisher.py -q
# every published BSO carries >= 1 verified evidence span
# importance_bp is not 5000 unless the fallback path fired AND logged
# conflicts from L1 v2 arrive in metadata
```

---

## Group acceptance gate

```
pytest tests/context -q
python scripts/situation_importance_distribution.py --org <pilot> --since 30d
```

| Metric | Gate |
|---|---|
| distinct `importance_bp` values | > 50 |
| p90 − p50 | > 1500 |
| situations at exactly 5000 | < 5% |
| BSOs with a verified evidence span | 100% |
| confidence vector axes present | all 6 |
