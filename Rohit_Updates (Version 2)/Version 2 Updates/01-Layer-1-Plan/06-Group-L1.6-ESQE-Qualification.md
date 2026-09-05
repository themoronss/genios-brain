# L1.6 — ESQE / Qualification (Stage S4)

> **The single gateway.** Nothing reaches Layer 2 except through this group.
> Today only 2 of these 10 components exist, which is why L1 currently routes events
> instead of qualifying signals.

**Group responsibility:** decide **what kind of thing** this is, **whether it matters**,
and **how big it is**.

**Group law:** *All scoring lives here, and none of it is done by a model.*

**Package:** `genios_engine/capture/esqe/`
**Input:** validated `ExtractionResult` + `RoutedEvent` + `list[Conflict]`
**Output:** `QualifiedEnterpriseSignal` (C-12)
**LLM sites:** LLM-5 only — ambiguous business relevance, under 5% of events.

---

## Component map

| # | Component | ALG | Units | Wave | Status |
|---|---|---|---|---|---|
| L1.6.1 | Signal Detector | ALG-15 | 2 | W6 | **NEW** |
| L1.6.2 | Signal Normalizer | — | 1 | W6 | NEW |
| L1.6.3 | Signal Classifier | ALG-16 | 2 | W6 | **NEW** |
| L1.6.4 | Source Analyzer | — | 1 | W6 | partial |
| L1.6.5 | Business Relevance | — | 2 | W6 | substituted today |
| L1.6.6 | Domain Mapping | — | 1 | W6 | exists |
| L1.6.7 | **Importance Scoring** | ALG-17 | 3 | W7 | **NEW — the unlock** |
| L1.6.8 | Qualification Engine | ALG-18 | 2 | W7 | partial |
| L1.6.9 | Signal Lifecycle Manager | ALG-19 | 2 | W8 | NEW |
| L1.6.10 | Signal Publisher | — | 2 | W8 | rewrite |

---

# L1.6.1 · Signal Detector (ALG-15)

### L1.6.1-U1 · Detection predicates

**WHAT** — Decides whether this event contains a business signal at all, and how many.

**WHY** — Globe calls this *"the first gate in the entire system — a miss here is
unrecoverable downstream, no matter how good L4 is."* Today it does not exist: a grep
of `capture/` for `signal_type` returns zero hits. So nothing downstream can branch on
what kind of thing happened.

**CRITICAL DESIGN CHANGE vs Globe:** Globe put an LLM here (weight 45) reading raw
text. In v2 the detector is **deterministic**, because by the time it runs, S2 has
already done the semantic work. The detector reads the **typed extraction**, not prose.

**WHERE** — `genios_engine/capture/esqe/detector.py`

**HOW** (ALG-15) — predicate table over `ExtractionResult`:

| Signal | Predicate |
|---|---|
| `COMMITMENT_MADE` | `len(commitments) > 0` |
| `COMMITMENT_DUE` | a commitment whose `due.latest <= eval_time + 7d` |
| `DEADLINE_STATED` | a `ResolvedDate` with `certainty in {EXACT, RANGE}` and no commitment attached |
| `DECISION_PENDING` | a `DecisionState` with `state in {pending, blocked}` |
| `DECISION_MADE` | a `DecisionState` with `state == made` |
| `APPROVAL_REQUESTED` | `intent == approve` OR a `Dependency` with `type == approval` |
| `CONTRACT_RENEWAL` | `contract_renewal in topics` OR (a `Money` AND a recurrence) |
| `FINANCIAL_OBLIGATION` | a `Money` AND (a due date OR `intent == commit`) |
| `RISK_FLAGGED` | `stance == negative` AND a named entity, OR a risk topic |
| `OPPORTUNITY_SIGNAL` | a satisfied condition, OR `stance == positive` with a next step |
| `RELATIONSHIP_CHANGE` | a `roles[]` change, or a new party entering a known thread |
| `INFORMATION_CONFLICT` | `len(conflicts) > 0` on a material field |
| `ESCALATION` | `intent == escalate` OR authority increase in the recipient set |
| `ANOMALY` | structural outlier — none of the above but the event is non-routine |

**One event may produce MORE THAN ONE signal.** That is correct and expected. An email
containing a commitment and a deadline is two signals sharing one `trace_id`.

**LLM** — no. **STORAGE** — pure.

**FAILURE MODES**
- Zero signals detected on a real business email -> the `no_signal_rate` counter is
  monitored; a sustained rise means the predicate table is too narrow.
- Every event produces 6 signals -> `signals_per_event` p95 monitored; cap at 5 per
  event, keep the highest-importance 5.

**ACCEPTANCE**
```
pytest tests/capture/esqe/test_detector.py -q
```
One table row per predicate, plus: the worked example from doc 04 L1.4.3-U2 produces
exactly `{CONTRACT_RENEWAL, DECISION_PENDING, APPROVAL_REQUESTED}` and no others.

---

# L1.6.3 · Signal Classifier (ALG-16)

### L1.6.3-U1 · Primary type selection

**WHAT** — When predicates fire for several types, picks the primary and records
secondaries.

**HOW** — fixed precedence, highest first. Precedence is a constant, not a score, so it
is reproducible:

```
INFORMATION_CONFLICT > ESCALATION > APPROVAL_REQUESTED > CONTRACT_RENEWAL >
COMMITMENT_DUE > DECISION_PENDING > FINANCIAL_OBLIGATION > DEADLINE_STATED >
RISK_FLAGGED > COMMITMENT_MADE > DECISION_MADE > OPPORTUNITY_SIGNAL >
RELATIONSHIP_CHANGE > ANOMALY
```

Rationale for the top three: a conflict means we may be about to tell the founder
something false; an escalation is time-bound; an approval request is blocking someone.
Those outrank everything descriptive.

**ACCEPTANCE** — an event firing 4 predicates gets exactly one `signal_type` and 3
`secondary_types`, deterministically, in two separate runs.

---

# L1.6.2 · Signal Normalizer

### L1.6.2-U1 · Canonical signal shape

**WHAT** — Coerces a detected signal into the canonical field set before classification.

**WHY** — The detector reads different parts of the extraction for different types
(commitments, decision states, dates). Without a normalizing step every downstream unit
would need to know which shape it was handed.

**WHERE** — `genios_engine/capture/esqe/normalize.py`

**HOW** — for every detected signal, populate: `subject_key` (ALG-22), `subject_label`
(human-readable), `primary_entity`, `primary_date` (the `ResolvedDate` most relevant to
this type), `primary_amount`, `evidence_refs` (union of the triggering claims' spans).
Missing values are `None`, never invented.

**LLM** — no. **STORAGE** — pure.

**ACCEPTANCE** — every detected signal type produces a fully-shaped record; a
`COMMITMENT_DUE` carries the commitment's `due` as `primary_date`; a
`RELATIONSHIP_CHANGE` carries `primary_date=None` without error.

---

# L1.6.4 · Source Analyzer

### L1.6.4-U1 · Provenance and actor authority

**WHAT** — Assigns the two authority inputs importance scoring needs:
`evidence_authority_rank` (what kind of artifact) and `actor_authority_bp` (who said it).

**WHY** — *A signed PDF is not a Slack aside*, and a message from the CFO is not a
message from a service account. ALG-17 terms 3 and 6 both come from here.

**WHERE** — `genios_engine/capture/esqe/source_analyzer.py`

**HOW**
```
evidence_authority_rank  -> delegate to ALG-14 (L1.5.8), do not reimplement
actor_authority_bp       -> lookup cascade:
    1. graph authority view (if the person is known and has a role)  -> role ladder
    2. internal_kind present                                         -> 9000
    3. connection owner / mailbox owner                              -> 8000
    4. same-domain colleague                                         -> 5000
    5. external counterparty                                         -> 5000
    6. automated / no-reply / service account pattern                -> 1000
    7. unknown                                                       -> 3000
```

**Existing code to extend, not replace:** `capture/internal_knowledge.py:113`
`authority_rank_for()` already covers the `internal_kind` classes. Machine senders are
already detected — commit `fc25ea1` makes them `service` nodes rather than `person`.
Reuse both.

**LLM** — no. **STORAGE** — pure.

**ACCEPTANCE** — a CFO-sent message scores above an unknown external; a `no-reply@`
sender scores 1000; an uploaded policy document gets `internal_kind` authority.

---

# L1.6.5 · Business Relevance (LLM-5)

### L1.6.5-U1 · Rules-first relevance

**WHAT** — Decides whether a detected signal is about the company's operation at all.

**WHY** — A newsletter can contain a date, an amount and an implied action, and would
otherwise qualify as `FINANCIAL_OBLIGATION`. This is the last filter before scoring.

**HOW — rules handle the overwhelming majority; the model sees under 5%:**
```
DETERMINISTIC FIRST (commit c373a9d established this order — keep it):
  known counterparty in the graph                    -> RELEVANT, no LLM
  internal_kind present                              -> RELEVANT, no LLM
  structured source                                  -> RELEVANT, no LLM
  bulk/marketing headers, list-unsubscribe present   -> NOT RELEVANT, no LLM
  sender is a service account AND no typed claims    -> NOT RELEVANT, no LLM

AMBIGUOUS REMAINDER -> LLM-5, cheap tier, batched
```

**LLM** — **yes, LLM-5**, cheap tier, batched, ambiguous remainder only. Why a rule
cannot do it: an unknown sender writing about a real obligation is indistinguishable
from a vendor pitch by header alone.

**Budget guard** — if the ambiguous share exceeds 10% of events for an org, that is a
graph-coverage problem (too few known counterparties), not a relevance problem. Alert
rather than spend.

**ACCEPTANCE**
```
pytest tests/capture/esqe/test_relevance.py -q
# a known counterparty is RELEVANT with zero LLM calls
# a list-unsubscribe newsletter is NOT RELEVANT with zero LLM calls
# an unknown sender with a typed obligation reaches the LLM
# LLM share on a 1000-event fixture corpus is under 5%
```

---

# L1.6.6 · Domain Mapping

### L1.6.6-U1 · Domain tagging — ✅ exists, one rule to preserve

**WHAT** — Tags the signal with its business domain(s) from the capability registry.

**WHERE** — `capture/domain/hints.py` (exists, keep).

**THE RULE THAT MUST NOT BE LOST:** *never filter here.* Globe is explicit — dropping
signals whose domain is not yet covered breaks cross-domain correlation permanently. An
uncovered domain gets a **degraded-compile flag and an observation card**, not a discard.

A signal may carry **several** domains. An AWS renewal is Admin *and* Finance *and*
Engineering; L2's cross-domain correlator depends on all three being present.

**ACCEPTANCE** — a signal in an uncovered domain is published with a degraded flag, not
dropped; a multi-domain signal retains every tag.

---

# L1.6.7 · Importance Scoring (ALG-17)

> **The unlock.** This is the missing input that leaves Layer 4's utility formula dead.

### L1.6.7-U1 · The formula

**WHAT** — Computes `importance_bp` — *how big is this thing, intrinsically*.

**WHY** — Trace the current failure chain:

```
L1 stamps no importance_bp
  -> L4 has no per-event importance to score on
     -> priority_override replaces the utility formula outright
        -> decision_maker.py:243 records: "the formula has never once decided anything"
           -> ranking collapses to 30 authored constants in situation YAML
              -> two different tenants receive IDENTICAL rankings
```

**Layer 4's ranking failure is a Layer 1 hole.** Fill it here and the formula upstream
starts deciding.

### The two numbers are different — this resolves the v1 objection

The current code refuses `importance_bp` at L1 on the grounds that it would be *"the
priority/importance conflation the spec forbids"* (`contracts/gated_event.py:28`). That
objection is answered by keeping them as two distinct fields:

| | `importance_bp` — **L1** | `priority_bp` — **L4** |
|---|---|---|
| Question | *how big is this thing?* | *what should this person do first?* |
| Scope | intrinsic to the event | relative to the person's whole book |
| Inputs | amount, deadline, authority, criticality | importance + effort + risk + context |
| Changes when the book changes? | **no** | yes |
| Example | an \$84K renewal is big on any day | it may rank 3rd today, 1st tomorrow |

An \$84K contract is a big thing regardless of what else is happening. That is
importance. Whether the founder should look at it before the board deck is priority.
**Both are currently missing**, which is why nothing computes either.

**WHERE** — `genios_engine/capture/esqe/importance.py`
**WHEN** — W7. Requires L1.5.2 (dates), L1.5.3 (money), L1.5.8 (authority).

**HOW** (ALG-17) — all integer basis points, all inputs from **validated** S3 facts:

```
importance_bp = clamp(0, 10000,
      (W_MONEY     * monetary_exposure_bp
     + W_DEADLINE  * deadline_proximity_bp
     + W_AUTHORITY * actor_authority_bp
     + W_CRITICAL  * entity_criticality_bp
     + W_TYPE      * signal_type_weight_bp) / 10000
    * evidence_authority_multiplier_bp / 10000
)

W_MONEY     = 3000
W_DEADLINE  = 2500
W_AUTHORITY = 1500
W_CRITICAL  = 2000
W_TYPE      = 1000
                        # weights sum to 10000
```

**Term definitions — every one deterministic:**

**1. `monetary_exposure_bp`** — log-scaled against the org's own baseline, not an
absolute scale. \$84K means something different to a 5-person company than to a 500-person one.
```
if no Money on the signal:            0
baseline = org's p50 deal/contract value over the last 365 days
           (if unknown: fall back to 0 and set coverage flag `no_money_baseline`)
ratio_bp = min(10000, amount * 10000 // max(baseline, 1))
monetary_exposure_bp = log_scale_bp(ratio_bp)     # integer log lookup table, 20 buckets
```
Log scaling matters: without it every large number becomes urgent and small critical
things get buried — Globe's own named L4 failure mode.

**2. `deadline_proximity_bp`** — from the **validated** `ResolvedDate`, using
`earliest` (the conservative edge):
```
certainty == UNRESOLVED             -> 0
certainty == RELATIVE               -> computed value * 5 // 10   (halved: it is a guess)
days = (earliest - eval_time).days
days <= 0    -> 10000     (overdue)
days <= 2    ->  9000
days <= 7    ->  7500
days <= 14   ->  6000
days <= 30   ->  4000
days <= 90   ->  2000
else         ->   500
```
The RELATIVE halving is important: *"renewal coming up pretty soon"* must not score the
same as *"renewal on October 15"*.

**3. `actor_authority_bp`** — the sender's authority, from the graph's authority view if
known, else from the connection role:
```
founder / owner / signatory        10000
executive / approver above threshold 8000
manager                             6000
employee                            4000
external counterparty               5000
automated / service account         1000
unknown                             3000
```

**4. `entity_criticality_bp`** — is the named entity mission-critical to this org?
```
tagged mission_critical in Organization Brain   10000
top-decile counterparty by contract value        8000
active deal / open contract                      6000
known entity, no special status                  4000
first-seen entity                                2000
```

**5. `signal_type_weight_bp`** — a small nudge by type, not the dominant term:
```
INFORMATION_CONFLICT 9000 · ESCALATION 9000 · APPROVAL_REQUESTED 8000
CONTRACT_RENEWAL 8000 · COMMITMENT_DUE 7500 · FINANCIAL_OBLIGATION 7000
DECISION_PENDING 6500 · DEADLINE_STATED 6000 · RISK_FLAGGED 6000
COMMITMENT_MADE 5000 · DECISION_MADE 4000 · OPPORTUNITY_SIGNAL 5500
RELATIONSHIP_CHANGE 3500 · ANOMALY 3000
```

**6. `evidence_authority_multiplier_bp`** — from ALG-14, so a signed document outweighs
a Slack aside on identical facts:
```
rank 6 -> 10000   rank 5 -> 9500   rank 4 -> 9000
rank 3 -> 8500    rank 2 -> 8000   rank 1 -> 6500   rank 0 -> 4000
```

**LLM** — **no, absolutely not.** This produces a number. The number is consumed by
ranking. Ranking must be byte-identical across machines and across replays.

**STORAGE** — pure function. The result is stored on the QES; every term is also stored
in `importance_components` so the score can be explained.

```python
importance_components = {
    "monetary_exposure_bp": 7200,
    "deadline_proximity_bp": 6000,
    "actor_authority_bp": 8000,
    "entity_criticality_bp": 6000,
    "signal_type_weight_bp": 8000,
    "evidence_authority_multiplier_bp": 8500,
    "baseline_used": 4500000,
    "eval_time": "2026-09-03T09:04:11Z",
}
```
**Storing the components is mandatory.** *"Why is this an 8100?"* must be answerable
without re-running anything.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| No money baseline for a new org | every money term = 0 | fall back to an industry-neutral absolute ladder, flag `baseline_estimated` |
| Overweighted money | every large number is urgent; small critical things buried | log scaling + W_MONEY capped at 3000 of 10000 |
| RELATIVE dates treated as exact | invented urgency | the 5//10 halving, tested |
| Score drift after a weight change | historical scores incomparable | weights are versioned; `importance_version` stored on every QES |

**ACCEPTANCE**
```
pytest tests/capture/esqe/test_importance.py -q
```
Required rows:
- \$84K renewal, 12 days out, CFO sender, mission-critical vendor, signed PDF ->
  `importance_bp` in `[7500, 8500]`
- the same event with `certainty=RELATIVE` instead of EXACT -> **strictly lower**
- the same event from a service account -> strictly lower
- the same event with the amount at the org p50 -> strictly lower
- a newsletter with no money, no date, no entity -> `< 2000`
- **determinism:** the same input twice -> byte-identical output
- **no floats:** source-grep on the module

**REVERSE PROMPT**
```
TASK: Build importance scoring. This unlocks Layer 4's dead ranking formula.
FILE: genios_engine/capture/esqe/importance.py

BACKGROUND YOU MUST READ FIRST:
  genios_engine/reason/decision_maker.py:231-256
It records: "the formula has never once decided anything" — because priority_override
is supplied for every candidate. The root cause is that L1 never stamps an intrinsic
importance for L4 to score with. This unit fixes that.

Also read genios_engine/contracts/gated_event.py:28, which REFUSES importance at L1 on
the grounds it would conflate importance with priority. That objection is answered by
keeping two distinct fields: importance_bp (L1, intrinsic) and priority_bp (L4,
relative). Add a docstring in this module stating that distinction explicitly.

Implement:
  def score_importance(signal, extraction, org_baseline, *, eval_time) \
        -> tuple[int, dict[str, int]]      # (importance_bp, components)

FORMULA: exactly as specified in doc 06 L1.6.7-U1, including:
  - the 5 weighted terms (weights sum to 10000)
  - the evidence_authority multiplier
  - log-scaled monetary exposure against the ORG's p50 baseline, not an absolute scale
  - deadline_proximity halved (* 5 // 10) when certainty == RELATIVE
  - clamp to 0..10000

HARD RULES:
1. NO LLM. This module must not import any llm module. Add an import-graph test.
2. INTEGER MATH ONLY. No float anywhere. Implement log_scale_bp() as a 20-bucket
   integer lookup table, not math.log. Source-grep test for "float(" and "math.log".
3. eval_time is an EXPLICIT parameter. No datetime.now() in this module. Source-grep test.
4. ALWAYS return the components dict alongside the score. "Why is this an 8100?" must be
   answerable from stored data without recomputation.
5. Weights live in a versioned constant IMPORTANCE_WEIGHTS_V1. Store importance_version
   on every scored signal.
6. Inputs come ONLY from VALIDATED S3 facts (Money from L1.5.3, ResolvedDate from
   L1.5.2, authority rank from L1.5.8). Never from the raw model output.

TEST tests/capture/esqe/test_importance.py — table-driven, every row from the
ACCEPTANCE list in doc 06 L1.6.7-U1, plus:
  - determinism: same input twice -> identical int
  - monotonicity: increasing amount never decreases the score
  - monotonicity: a nearer deadline never decreases the score
  - a missing baseline sets baseline_estimated and does not crash

ACCEPTANCE: pytest tests/capture/esqe/test_importance.py -q -> pass, 0 skips
```

### L1.6.7-U2 · Org baseline computation

**WHAT** — Computes the org's p50 contract/deal value over 365 days.

**WHY** — Importance is relative to the company, not absolute.

**HOW** — nightly job; `percentile_bp` already exists in
`context/support_situations.py:405` — reuse it, do not write a second percentile.

**FAILURE MODE** — a new org has no history -> `baseline_estimated` flag + neutral
absolute ladder. Never block scoring on a missing baseline.

### L1.6.7-U3 · Explanation renderer

**WHAT** — Turns `importance_components` into one human sentence.

> *"Scored 8100: \$84K is ~2x your typical contract (7200), the cancellation window
> closes in 12 days (6000), and it came from your CFO on a signed agreement (8500x)."*

**LLM** — no. Template substitution. The numbers are already computed.

---

# L1.6.8 · Qualification Engine (ALG-18)

### L1.6.8-U1 · The floor

**WHAT** — The pass/fail gate. Below the tenant's floor, the signal is logged and dropped.

**WHY** — Globe: ESQE discards the ~92% that is not business-relevant *before it costs
anything downstream*. Today there is no floor at all (grep for a qualification threshold
in `gate/relevance.py` returns nothing), because there is no importance to threshold on.

**HOW** (ALG-18)
```
floor_bp = tenant.qualification_floor_bp        # default 2500

if importance_bp >= floor_bp:                       -> QUALIFY
if importance_bp <  floor_bp and conflicts:         -> QUALIFY  (conflicts always pass)
if importance_bp <  floor_bp and internal_kind:     -> QUALIFY  (company canon always passes)
otherwise:                                          -> DROP, LOGGED, PAYLOAD RETAINED 90d
```

**Drops are never silent.** The row records signal id, computed importance, every
component, and the floor it failed — so *"why did GeniOS not see this?"* is a query.

**FAILURE MODES**
- Floor too high -> misses. Monitored via `drop_rate` per org with an alert above 95%.
- Floor too low -> noise reaches L2 and costs money. Monitored via `qualify_rate`.
- **Floor tuning is a per-tenant setting with an owner and a changelog**, never a
  global constant edit.

**ACCEPTANCE**
```
pytest tests/capture/esqe/test_qualification.py -q
# below floor -> dropped, ledger row written WITH components and payload ref
# below floor + conflict -> qualified anyway
# below floor + internal_kind -> qualified anyway
# a dropped signal is fully reconstructable from its ledger row
```

---

# L1.6.9 · Signal Lifecycle Manager (ALG-19)

### L1.6.9-U1 · State machine

**WHAT** — Expire, supersede and revive signals.

**WHY** — *A renewal signal about a contract that was cancelled is dead, and must be
marked so* — otherwise L2 correlates a ghost and the founder is nudged about something
that resolved last week. This is Globe Rule 08 (*stale beats wrong*) applied at L1.

**HOW** (ALG-19)
```
states: active -> superseded | expired | resolved

SUPERSEDE  a newer signal with the same (subject_key, signal_type) and
           authority_rank >= the old one
           -> old.state = superseded, old.supersedes points forward
EXPIRE     expires_at passed
           -> state = expired.  expires_at defaults by type:
              COMMITMENT_DUE / DEADLINE_STATED -> the deadline + 30d
              CONTRACT_RENEWAL                 -> renewal date + 30d
              DECISION_PENDING                 -> 90d
              others                           -> 180d
RESOLVE    external evidence that the thing happened
           -> state = resolved
REVIVE     new evidence on an expired signal -> a NEW signal that `supersedes` the old.
           Never mutate an expired signal back to active.
```

**Revive creates a new row, never resurrects the old one.** History must stay readable.

**ACCEPTANCE**
```
pytest tests/capture/esqe/test_lifecycle.py -q
# supersede sets both sides' pointers
# a lower-authority newer signal does NOT supersede a higher-authority older one
# expiry is computed from the signal's own date fields, not from ingest time
# revive creates a new signal id and does not mutate the expired row
```

---

# L1.6.10 · Signal Publisher

### L1.6.10-U1 · Publication validator

**WHAT** — The last gate before L2. Runs V-1..V-7 from doc 08.

**HOW** — every rule in the doc-08 publication validator table, in order. V-1 through
V-4 and V-6/V-7 reject; V-5 downgrades and flags.

### L1.6.10-U2 · Emit and store

**WHAT** — Writes the QES to `qualified_signals` and hands it to L2.

**STORAGE**
```sql
create table if not exists qualified_signals (
    signal_id       text primary key,
    org_id          text not null,
    event_id        text not null,
    trace_id        text not null,
    signal_type     text not null,
    secondary_types jsonb not null default '[]',
    importance_bp   int  not null,
    importance_components jsonb not null,
    importance_version    text not null,
    confidence_bp   int  not null,
    confidence_vector     jsonb not null,
    domain_hints    jsonb not null default '[]',
    visibility      jsonb not null,
    coverage_ready  boolean,
    extraction_ref  text not null,      -- -> l1_extraction_results.processing_key
    evidence_refs   jsonb not null,
    conflict_ids    jsonb not null default '[]',
    state           text not null default 'active',
    supersedes      text,
    expires_at      timestamptz,
    internal_kind   text,
    occurred_at     timestamptz not null,
    created_at      timestamptz not null default now()
);
create index qs_by_org_state  on qualified_signals (org_id, state, importance_bp desc);
create index qs_by_trace      on qualified_signals (org_id, trace_id);
create index qs_by_type       on qualified_signals (org_id, signal_type, occurred_at desc);
```

Note `extraction_ref` is a **pointer**, not a copy. The extraction lives once, in the
cache, and every replay reads it there.

---

## Group acceptance gate (Layer 1 is complete when this passes)

```
pytest tests/capture/esqe -q                              # all pass, 0 skips
grep -rn "llm\|anthropic" genios_engine/capture/esqe/     # only detector-free relevance
grep -rn "float(" genios_engine/capture/esqe/             # no matches
python scripts/l1_end_to_end.py --org <pilot> --since 30d
```

The end-to-end script must report, for a real pilot tenant:

| Metric | Gate |
|---|---|
| events ingested | > 0 |
| qualified signals emitted | > 0 |
| every QES has `signal_type` in the enum | 100% |
| every QES has `importance_bp` in 0..10000 | 100% |
| every QES has `importance_components` populated | 100% |
| every QES has >= 1 verified evidence span | >= 95% |
| drop rate | between 60% and 95% |
| identical input replayed -> identical output | byte-identical |
