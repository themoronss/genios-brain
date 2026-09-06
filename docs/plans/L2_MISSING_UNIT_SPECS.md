# Layer 2 v2 — The Missing Unit Specs

> **Created:** 2026-09-06 · **Status:** Active
>
> **Purpose:** the 27 Layer 2 unit specs the group docs promise in prose but never wrote —
> so no wave has to derive its own spec mid-build, which is what cost Layer 1 three rework cycles.

---

## 1. Why this file exists

Layer 1's build record names the same defect six times: *a unit built, tested, and called by
nothing on a real request path.* It names a second one three times, and this file is about that
one — **L1.5.4, L1.5.6 and L1.4.8 had no spec.** The agent implementing each derived one in the
middle of the build, and each derivation produced a defect that only adversarial review caught.
Writing the spec first is the cheapest correction available in this whole layer.

Layer 2 arrives with the same hole, unevenly distributed. Counted from the group docs:

| Group | Components declared | Unit specs written | Units the doc actually promises |
|---|---|---|---|
| L2.1 Enterprise Context Graph | 8 | 1 | 4 |
| L2.2 Graph Engines | 8 | 2 | 5 |
| L2.3 Cross-Correlation | 8 | 3 | 8 |
| L2.4 Analytic Stratum | 8 | 18 | 20 |
| L2.5 Context Quality | 8 | 1 | 7 |
| L2.6 Situation Candidate Generator | 3 | 3 | 5 |
| L2.7 Business Situation Engine | 8 | 5 | 7 |
| **Total** | **51** | **33** | **56** |

**L2.4 is the only group that states its own promise.** Its component map carries a `Units`
column; the other six do not, so `scripts/unit_ledger.py` read their promise as *unstated* and
reported Layer 2's gap as **2** when the real gap was **23**. A group that never says how many
units it owes cannot be under-delivered against — which is why the ledger's L2 rows read green
while six of seven groups were between 25% and 60% specified.

This file closes 21 of those 23 by writing the spec, and completes 6 more that exist as a
heading with no acceptance criteria. The remaining 2 (`L2.4.7-U2`, `L2.4.8-U2`) are L2.4's and
are out of scope here — L2.4 states its promise and the ledger already tracks it.

**What this file is not.** It is not a decision. Where the plan contradicts itself or leaves a
choice genuinely open, §3 names the contradiction and the spec says which reading it assumed.
Layer 1's plan contradicted itself on wave assignment twice and both were caught only in review;
those are recorded here in advance instead.

---

## 2. Promise ledger

> **This table is machine-read.** `scripts/unit_ledger.py` parses it as the `Units` promise for
> the six Layer 2 groups whose own component maps have no `Units` column, and parses the unit
> headings below it as written specs. Change a number here and the ratchet moves.

| # | Component | Units | Written before this file | Supplied here |
|---|---|---|---|---|
| L2.1.3 | Temporal View | 1 | 0 | `-U1` |
| L2.1.4 | Authority View | 2 | 1 | `-U2` |
| L2.1.7 | Resource View | 1 | 0 | `-U1` |
| L2.2.1 | Graph Builder (+ M-2) | 1 | 0 | `-U1` |
| L2.2.4 | Graph Deduplicator (+ M-1) | 1 | 0 | `-U1` |
| L2.2.5 | Freshness Manager | 1 | 1 | — |
| L2.2.7 | Version Manager | 2 | 1 | `-U2` |
| L2.3.2 | Cross Conversation (+ M-3) | 1 | 0 | `-U1` |
| L2.3.3 | Cross User | 1 | 0 | `-U1` |
| L2.3.4 | Cross Timeline (+ M-5) | 2 | 1 | `-U2` |
| L2.3.5 | Cross Resource | 1 | 0 | `-U1` |
| L2.3.6 | Cross Domain | 1 | 0 | `-U1` |
| L2.3.7 | Cross Organization | 1 | 1 | acceptance only |
| L2.3.8 | Dependency Correlation | 1 | 1 | — |
| L2.5.1 | Confidence Calculation | 1 | 0 | `-U1` |
| L2.5.3 | Conflict Detection | 1 | 0 | `-U1` |
| L2.5.5 | Missing Context Detection | 2 | 1 | `-U2` |
| L2.5.6 | Evidence Aggregation | 1 | 0 | `-U1` |
| L2.5.7 | Context Completeness | 1 | 0 | `-U1` |
| L2.5.8 | Context Validation | 1 | 0 | `-U1` |
| L2.6.1 | Pattern Matcher | 3 | 1 | `-U2`, `-U3` |
| L2.6.2 | Candidate Builder | 1 | 1 | acceptance only |
| L2.6.3 | Candidate Scorer | 1 | 1 | acceptance only |
| L2.7.2 | Situation Builder + Framing | 2 | 2 | acceptance only |
| L2.7.3 | Situation Clustering | 2 | 1 | `-U1` |
| L2.7.4 | Situation Prioritization | 1 | 1 | — |
| L2.7.7 | Situation Lifecycle | 1 | 1 | — |
| L2.7.8 | Situation Publisher | 1 | 0 | `-U1` |
| L2.1.1 | Entity View | 0 | — | preserve |
| L2.1.2 | Relationship View | 0 | — | preserve |
| L2.1.5 | Ownership View | 0 | — | preserve |
| L2.1.6 | Communication View | 0 | — | preserve |
| L2.1.8 | Knowledge View | 0 | — | preserve |
| L2.2.2 | Graph Updater | 0 | — | preserve |
| L2.2.3 | Graph Validator | 0 | — | preserve |
| L2.2.6 | Lifecycle Manager | 0 | — | preserve |
| L2.2.8 | Consistency Checker | 0 | — | preserve |
| L2.3.1 | Cross Tool | 0 | — | preserve |
| L2.5.2 | Freshness Evaluation | 0 | — | preserve |
| L2.5.4 | Noise Detection | 0 | — | preserve |
| L2.7.1 | Situation Detection | 0 | — | preserve |
| L2.7.5 | Situation Confidence | 0 | — | preserve — see §3 **A-4** for L2.7.5 |
| L2.7.6 | Situation State | 0 | — | preserve |

**The fifteen zero rows are the point of the bottom half of this table.** They are ✅ in their
group doc and the instruction is *preserve*, so they owe nothing — but *"owes nothing"* and
*"nobody said"* are different states, and a ledger that cannot tell them apart reports an
unspecified group as green. Zero is a stated promise here.

**L2.4 is deliberately absent.** Its own component map carries a `Units` column and the ledger
reads it there; a supplement may fill in an unstated promise, never override a stated one.

---

## 3. Contradictions and ambiguities — flagged, NOT resolved

Each of these is a place where the plan says two things, or does not say enough. The spec below
states which reading it assumed and marks the assumption. **None of them should be closed by an
implementing agent.**

### A-1 · Doc 07's central defect claim is stale against HEAD

Doc 07 opens on *"`DEFAULT_IMPORTANCE_BP = 5000` line 39 … `importance_bp=DEFAULT_IMPORTANCE_BP`
line 235 … every `BusinessSituationObject` ever produced carries importance 5000."*

**That is no longer true in this repo.** `genios_engine/context/situation_bso.py` now reads
Layer 1's score out of `qualified_signals` (`gather_l1_signals`, line 217) and branches at
lines 437-448 across four sources — `l1_qualified_signals`, `l1_unscored`, `l1_all_retired`,
`default` — recording which one fired in `metadata['importance_source']`. The constant survives
at line 52 as the documented fallback and its docstring says so.

**What L2.7.4-U1 still owes is steps 2 through 6** — corroboration, the three L2-only modifiers,
the coverage penalty, the clamp and the stored components. None of those exist. Step 1 is done.

**Consequence for the H5 gate:** *"situations at exactly 5000 < 5%"* is now a measure of the
`importance_source='default'` share, not of a hardcode. An agent reading doc 07 literally will
re-fix a fixed thing and may reintroduce the constant on the way. The doc's line numbers should
be re-verified before X5 opens.

### A-2 · L2.2.4 — doc 00 promises an LLM site into a component doc 02 forbids touching

MAP A assigns **M-1 (ambiguous entity linking)** to L2.2.4. Doc 02's L2.2.4 section says the
component is *"preserve, do not touch"* and that *"no PR in the Layer 2 plan touches
`identity.py` or `merge.py` while doing something else."*

Both hold only if M-1 lands **outside** those two files. Two readings are available and the plan
picks neither: (a) a new module that `identity.py` calls at one named seam, or (b) a proposer
that never resolves anything and only writes `merge_proposals` for a human. **`L2.2.4-U1` below
assumes (b)** because it leaves the deterministic cascade byte-identical. Confirm before X7.

### A-3 · L2.3's group gate forbids the LLM that two of its own components require

Doc 03 assigns **M-3** (L2.3.2) and **M-5** (L2.3.4) to this group, and then its group acceptance
gate runs:

```
grep -rn "LLMClient\|anthropic" genios_engine/context/correlation*.py    # no matches
```

A component cannot both host an LLM site and pass a gate asserting no LLM client is reachable
from its file. The gate is satisfiable only if the two call sites live elsewhere — and there is
already a home: `genios_engine/context/llm/client.py`. **`L2.3.2-U1` and `L2.3.4-U2` below assume
that reading**, which keeps the grep true as literally written. It still reads like an oversight
in the gate rather than a design, and the owner should say which.

### A-4 · The `analytic_score` axis is specified twice, in two different groups

Doc 05 L2.5.1: *"One addition: an `analytic_score` axis…"* Doc 07 L2.7.5: *"One change only: add
an `analytic_score` axis…"* Same function, same field, two owners. The code has five scoring
functions (`evidence`, `freshness`, `consistency`, `identity`, `coverage` — `situations.py`
102-227), so doc 08's `confidence_vector` of *"6 axes"* and the three gates demanding *"all 6"*
are already counting this one addition, once.

**This file gives it one id — `L2.5.1-U1` — and leaves L2.7.5 at zero units.** If two distinct
changes were intended, this is wrong and the plan must say what the second one is.

### A-5 · L2.7.3 numbers its only spec `-U2` and has no `-U1`

`L2.7.3-U2` (clustering judgment, M-8) opens *"deterministic shared-entity clustering runs first"*
— and that deterministic clustering, **BLG-17**, has no spec block anywhere, though MAP D lists it
as a Layer 2 algorithm owned by L2.7.3. A skipped index is indistinguishable from a lost spec.
**`L2.7.3-U1` below is written as the spec-of-record for the existing deterministic clustering**
so the algorithm has an addressable id. If the intent was "BLG-17 is finished, it owes no spec",
the component should say *0 units* rather than skip an index.

### A-6 · Six of these units have no wave

Doc 09's eight waves name **components**, not units, and six of the units below fall in no wave
that obviously owns them: `L2.2.1-U1`, `L2.3.3-U1`, `L2.3.5-U1`, `L2.3.6-U1`, `L2.5.6-U1`,
`L2.5.7-U1`. Each spec below carries a **`WHEN — proposed`** line. *Proposed* means exactly that:
Layer 1's plan contradicted itself on wave assignment twice, and a wave is an owner's decision.

### A-7 · The confidence vector is a float percent; the doctrine says integer basis points

`situations.py:209` returns `int(round(100 * known / len(expected)))` on a 0..100 scale
(`SCORE_MAX = 100`, line 176; `COVERAGE_UNKNOWN = -1`, line 181). Doc 00 and doc 08's validator
**V-8** say integer basis points and reject any float in a score path. Three units below
(`L2.5.5-U2`, `L2.5.7-U1`, `L2.5.8-U1`) read that number and one of them gates publication on it.

The plan never reconciles the two scales. Either the vector stays on percent and doc 08 documents
`confidence_vector: Mapping[str, int]` as percent, or `situations.py` migrates to basis points —
and that file is item 3 on doc 09's *must not regress* list. **The specs below read the number
through `coverage_is_known()` and do not convert it**, so neither choice is pre-empted.

### A-8 · `L2.3.7` is a safety component with no acceptance criteria

`L2.3.7-U1` is three sentences ending *"test the negative case first: a fact from context A must
**not** appear in context B"*, and doc 03's group gate makes that a **safety gate** at
*0 leaks*. There is no unit acceptance list, no failure-mode table and no named file. §4 supplies
them; the *content* is derived from the group gate, not invented, but it was never written down
and a safety component specified in prose is how a leak ships.

### A-9 · Doc 09's H3 row asks one function to be two different statistics

Doc 09's H3 row reads *"nearest-rank matches the existing `support_situations.percentile_bp`
exactly"*, resting on doc 04 line 554: *"`support_situations.py:405 percentile_bp()` already
implements nearest-rank"*. **It does not.** That function is MID-RANK — it counts a tie as HALF —
and `context/analytic/cohort.percentile_bp` is nearest-rank (`rank = count(v <= value)`). The two
answer different questions and therefore cannot agree: a population of three identical values puts
its member at **5000** under one and **10000** under the other, and the general disagreement is
about `5000 // n`.

Doc 04's own acceptance figure settles which one L2.4.5 owes — *"the lowest value in a cohort of 10
-> percentile_bp near 1000"* is the nearest-rank number (mid-rank gives 500). **The comparator
therefore used `cohort.percentile_bp` and left `support_situations.percentile_bp` alone.**
Reconciling the support module onto nearest-rank was tried and refused for a stated regression, not
a preference: a uniformly aged backlog would land every open loop on exactly 10000, the
`pctl < AGING_PERCENTILE_BP` guard in `read_backlog_items` would stop holding for all of them, and a
desk whose five loops were all raised this morning would report five aging findings.

What the row is really protecting — that there are not two copies of ONE statistic quietly
disagreeing — holds by construction: the comparator imports `cohort.percentile_bp` and defines no
percentile of its own, and `tests/context/analytic/test_h34_gate_probes.py` pins both functions on
one population so neither can drift onto the other's answer. **The row as written is still
unsatisfiable and an owner should rewrite it** to name the two statistics apart rather than assert
an equality that cannot exist.

### A-10 · A quartile cohort's SLOT has no addressable id, only a name

`cohort.quartile_cohorts` mints the shipped reference populations and `cohort._system_cohort_id`
hashes the quartile **slot** into an opaque content-addressed id. There is consequently no public
way to ask *"which cohort is the top quartile of this family"* — the slot exists in the code that
writes it and nowhere in the schema that reads it.

`comparator.reference_cohorts()` therefore selects on the cohort NAME suffix (`"· top quartile"`,
`TOP_SLOT_SUFFIX`) plus `created_by == SYSTEM_AUTHOR`. **That is a string match standing in for a
key.** It works because both halves are minted by the same module, and it breaks silently the day
anyone renames a slot or a tenant authors a cohort whose name ends the same way. The honest fix is
a `slot` column, or a slot enum on the cohort row, and it is a schema decision this file does not
get to make.

### A-11 · `metric_history`'s DDL has no row shape for a coverage-false observation

`history.gap_point` returns `coverage_ready=None` for a period with no reading, and the docstring
argues why it must not be `False`: a gap cannot tell *"no source could have carried this"* from
*"a connected source carried nothing"*, and `False` is the licence to make a negative inference.
Only a row the sampler actually wrote can settle it.

**The doc's DDL cannot hold that row.** `value_bp not null` means a coverage-false observation —
which by definition has no value — has nowhere to live, so the distinction is representable in the
contract and not in the table. The assumption made: **gaps stay in memory as `MetricPoint`s and are
never persisted**, so nothing is lost that was ever written down. Making the negative inference
available to L3/L4 needs `value_bp` nullable plus a `sample_reason` that says which kind of absence
it is, and that is a migration nobody has proposed.

### A-12 · Doc 06's reverse prompt writes an `ImportanceScorer` signature the module did not land

Doc 06's reverse prompt for L1.6.7 writes `score_importance` with an `extraction` argument
returning a `(bp, components)` tuple. `capture/esqe/importance.py` landed it taking the whole
`NormalizedSignal` — L1.6.2 has already read the extraction into `primary_amount`, `primary_date`
and `attribution`, so the extraction argument would be a second, staler copy of what the signal
already carries — and returning a typed `ImportanceScore` rather than a tuple.

**`qualification.ImportanceScorer` depends on the landed API, and no shim was written.** A shim is
the worse outcome: it would put two signatures for one algorithm in the tree and let a caller pick
the one the doc describes rather than the one the scorer implements. The doc's prompt is the thing
that is stale; an owner should correct doc 06 rather than the code.

### A-13 · `l1_signals`' envelope is an addition to the DDL doc 06 prints

Doc 06 prints the `l1_signals` DDL. `signal_store` writes one more column — `envelope`, carrying
`source`, `object_type`, `triage_lane`, `recipients`, `versions` and `schema_version` — added by
**migration 0089**, because a stored signal that could not round-trip its own envelope would come
back out of the database as a different object from the one that went in.

**It is an addition, not a disagreement**, and it is recorded here for the reason A-12 is: a
reviewer diffing the shipped table against doc 06 will find a column the doc does not mention and
has no way to tell a deliberate extension from a drift. Doc 06's DDL block should absorb it.

### A-14 · Doc 05's absence cascade puts `STALE` on an unreachable branch

Doc 05's L2.5.5-U1 writes the cascade as:

```
if fact present                              -> PRESENT
elif coverage_ready is False for its domain  -> UNKNOWABLE
elif a source could carry it and none did    -> GENUINELY_ABSENT
elif the fact was present and is now stale   -> STALE
else                                         -> NOT_EXPECTED
```

**The fourth branch cannot be reached.** A fact that *was present* is caught by the first branch,
and anything falling past the third has already been concluded to be carried by nothing — so
`STALE` is unreachable as written and `NOT_EXPECTED` absorbs every case the third branch does not
claim. Written literally, the cascade produces no `STALE` at all and types an inapplicable
expectation as `GENUINELY_ABSENT` — the exact false negative inference the section's own failure
table calls the worst output in the group.

**The reading assumed by `context/quality/missing.py`:** presence is examined FIRST and splits
`PRESENT` from `STALE`; the expectation guard runs next (`NOT_EXPECTED`); coverage is the last
gate before `GENUINELY_ABSENT`. The HARD RULE the doc is actually protecting — *"coverage_ready is
checked FIRST, before concluding anything is absent"* — is kept exactly: nothing reaches
`GENUINELY_ABSENT` without passing the coverage check, and `None` lands with `False`. An owner
should correct the doc's ordering rather than the code.

A second, smaller assumption sits under the same unit. The doc says *"expectation maps are
declared per domain … live in code with a version"* and gives that registry its own unit
(`L2.5.5-U2`, unbuilt). Until it lands, `expectations_from_spec` reads
`domain_spec.expected_fields` — the map `situations.coverage_score` and
`situation_bso._missing_paths` ALREADY score against. A third list would be a third opinion about
what a situation type should know, and the failure mode of three opinions is a permanent false
finding. `L2.5.5-U2` replaces the source without changing the cascade.

---

### A-15 · `L2.6.1-U1`'s worked example names a node type and an inference the graph cannot support

Two things in doc 06's `vendor_renewal_unowned` YAML do not survive contact with this repo's graph,
and X6 had to choose a reading for each. Both are recorded here rather than resolved.

**The anchor.** The example writes `anchor: {node_type: contract}`. Nothing in the engine mints a
`contract` node: `capture/structured/registry.py` mints `subscription` (Stripe), `product_account`
(the client's own database), `deal`, `meeting`, `person` and `company`, and `correlation.
ANCHOR_PRIORITY` ranks `subscription` as a system-of-record business object exactly as it ranks a
deal. A pattern anchored on a node type nothing creates is a pattern that can never fire — the
precise failure the fire report exists to make visible — so **the shipped seed pattern anchors on
`subscription`** and keeps doc 06's `pattern_id`. If a `contract` node type is coming from a
document-extraction lane, the seed file is a one-line change; if it is not, doc 06's example should
be respelled.

**The missing-edge inference.** The example's `{kind: edge, type: owns, op: missing}` makes a
NEGATIVE claim, and L2.5.5's whole argument is that a negative claim is licensed only where a
source that could have carried the fact was checked. `MissingFact` carries that licence for FACTS
and nothing carries it for EDGES: an org with no CRM connected has no `owns` edges at all, so
"nobody owns this contract" would be true of every contract in the company. **X6's evaluator
therefore satisfies an `edge ... missing` condition only where the slice declares that edge type in
`GraphSlice.edge_coverage`**, and fails it with `edge_absence_unknowable` otherwise — the same
shape as `UNKNOWABLE`, applied to a table that has no typed-absence row of its own. The provider
that fills `edge_coverage` is a seam in `context/patterns/store.py` and defaults to EMPTY, so the
condition currently never holds on a real tenant and the fire report says so. Making it hold needs
an owner's decision about where edge coverage is recorded, which is a schema question this file
does not get to answer.

**Also recorded, smaller:** doc 06's `{kind: fact, field: ..., op: missing}` is not implementable
for the same reason and is REFUSED at registration by the shipped schema. Absence is expressible
only through `kind: absence`, which consumes the typed answer. If the plan intended fact-absence to
be a shorthand for a typed absence, the doc should say so; read literally it is the conflation
L2.5.5 exists to prevent, one grammar up.

### A-16 · M-4's output shape names a `confidence_bp` that doc 12's first rule forbids

Doc 07's `L2.7.7-U1` states M-4's return as `{verdict, scope, speaker_role, quote, offsets,
**confidence_bp**}`. Doc 12's first cross-cutting rule states: *"No `_bp` output, ever. No LLM at
L2 produces a number that feeds ranking."* Both cannot be honoured literally at the same site.

**Assumed:** the model returns a **certainty BAND** out of a closed vocabulary
(`EXPLICIT_COMPLETION` · `IMPLIED_COMPLETION` · `INTENT_ONLY` · `AMBIGUOUS`) and
`lifecycle/contract.CERTAINTY_BP` turns that band into basis points. A `confidence_bp` in the
payload is parsed into `ResolutionDescription.raw_confidence_bp`, **stored on the claim and read
by nothing that decides** — so a prompt-injected `"confidence_bp": 10000` buys nothing, and the
number is still there if anyone later wants to measure how well the model's own certainty tracked
ours. `tests/context/lifecycle/test_resolution.py::test_the_model_never_supplies_the_number_the_floor_reads`
pins the discard.

The same reading resolves the `speaker_role` field beside it: the model may say who it thinks
spoke, and the value is recorded, but AUTHORITY is derived from the sender's address against the
org's own "who is us" set (`lifecycle/authority.py`). A role read out of prose is a reading; a
role read off an address is a fact we hold.

### A-17 · Doc 07's gate reads `status == ACTIVE`, which makes `CONTRADICTED` unreachable

L2.7.7-U1's gate fires only when `situation.status == ACTIVE`. Failure mode 5 of the same section
requires *"done"* … *"actually not yet"* to REOPEN — but by the time the second message lands, the
first one has moved the situation to `resolved`, so a literal gate would never look at it and the
wrong close would be permanent. That contradicts doc 12's own description of
`RESOLVED_BY_STATEMENT` as *"reversible by design … even a wrong close is recoverable on the next
drain."*

**Assumed:** the gate also fires on `resolved` and `partial` rows **whose `resolved_by` is
`statement`** — the states this unit itself produced. It does not fire on a human's resolution (a
person's decision is not overturned by a sentence; the existing `last_seen_at > resolved_at` rule
already reopens those) and it does not fire on a fact's (a fact beats a statement, always).

### A-18 · `active_situations` filters on `status = 'active'`, so a `partial` situation disappears

`STATUS_PARTIALLY_RESOLVED` is required by doc 07 and doc 12 case 2 as a state distinct from both
`active` and `resolved`. `situations.active_situations` — the read the Reasoning Engine and
`/api/org/{org}/situations` both use — selects `status = 'active'`, so a situation that has three
of five obligations discharged **drops out of that read entirely**, taking the two outstanding
obligations with it. That is a milder version of the exact failure the state exists to prevent.

**RESOLVED AT THE H6 GATE.** `active_situations` now reads `status in ('active', 'partial')`.

The wave recorded this as a decision it could not make — *"widening it is a decision about what
'active' means to every consumer of that endpoint"* — and on the face of it that is right. But the
framing had the direction wrong. This is not a gap the wave declined to close; it is a
**regression the wave caused**: before `STATUS_PARTIALLY_RESOLVED` existed, a situation with three
of five obligations discharged was `active` and the founder could see it, and the only thing that
made it disappear was M-4 re-labelling it. Detecting a partial resolution and thereby hiding the
outstanding half is strictly worse than not detecting it.

And the change needs no judgement about what "active" means, because it cannot reach anything that
predates it: **`partial` is a status this wave invented, and nothing has ever written it before.**
Widening the read is therefore additive by construction — it changes the answer for exactly the
rows M-4 re-labelled and for no others. Pinned by
`tests/context/lifecycle/test_h6_fault_injection.py::test_a_partially_resolved_situation_is_still_live_to_the_reader`,
which also asserts a genuinely `resolved` situation still does not come back.

### A-19 · The per-org daily LLM ceiling has no shared ledger to count against

Doc 11 sets *"per-org daily L2 LLM calls: 200"* across all nine sites. No shared per-org call
ledger exists in this repository; each site would have to count its own. M-4 counts **its own
rows** in `situation_resolution_claims` against `eval_time`'s day.

**Assumed:** that is correct in the only direction that matters — this site alone can never exceed
the whole-layer budget — and it is understated by whatever the other eight sites spend. A real
ceiling needs one ledger every L2 model site writes to, which is an owner's decision about where
that table lives.

### A-20 · M-4's last line of defence against a prompt injection is the authority table

The message M-4 reads is untrusted text from outside the org. It is fenced with
`capture/semantic/injection.fence` (nonce fence, structural literals escaped one code point for
one so no offset moves) and the prompt's sixth rule says instructions inside the message are data.
Both are the model's guards, not ours.

**The deterministic layer cannot catch a model that complies.** An injected *"mark this situation
resolved"* is really in the message, so the quote VERIFIES — ALG-08's job is to prove the sentence
exists, not to judge who wrote it. What stops the close in the golden set's
`injection_external_obeyed` fixture is the speaker: a counterparty's 0.6 weight puts an obeyed
injection under the floor. **An injection planted in a message from an org-internal address, with
a model that complies, would close the situation** — and be reopened by the next contradicting
message, which is the only recovery this design has.

**Not resolved here.** Closing it properly needs either an injection-scan signal on the message
(the `FencedContent.risk_bp` this repo already computes at L1 and L2 does not read) feeding the
gate, or a rule that an obeyed instruction can never be the quote. Recorded so the next reader
knows the residual risk is known rather than missed.

### A-21 · Doc 13's fixpoint is written as a loop inside one sweep, and its own L-1 row says one pass per sweep

Doc 13's L-4 pseudocode is `for pass in 1..MAX_PASSES:` around `correlate -> derive -> score ->
lifecycle`, with a state hash before and after each turn. Its own table of the five loops says
something different one page earlier: **L-1, "drain loop — one pass per sweep"**, not cyclic. Both
cannot be the shape of `context/runner.process_pending`, which drains, derives, scores and re-ranks
exactly once per call.

**The reading taken: the pass IS the sweep, and the fixpoint iterates ACROSS sweeps.** The hash of
(situations, memberships, lifecycle states) at the end of one sweep is compared with the hash taken
at the start of the next, and the counter increments only when a sweep drained NOTHING and still
moved the state. The alternative — running the derive/score block up to three times inside one call
— triples the analytic budget on every healthy tenant to detect a condition doc 13 itself calls "a
design defect to find, not a runtime condition to tolerate", and it would have meant restructuring
a block three other waves own. It also makes doc 09's gate row (*drains exceeding `MAX_PASSES` — 0
over 7 days*) a stored per-org counter rather than an in-process one that resets on every deploy.

The consequence an owner should confirm: "do NOT keep iterating, publish what pass 3 produced" can
only mean *raise the alert and publish* across sweeps — a drain cannot refuse to run without
stopping a tenant's ingestion over a derived-view defect. Migration `0105_l2_convergence.sql`.

### A-22 · Doc 13's E-10 cascade presumes the event ledger reaches the whole window, and it does not

E-10's arithmetic is `if org_activity == 0 -> ORG_INACTIVE`, where `org_activity` is "total events
across ALL sources in the period". On this repo that count comes from `source_events`, which is a
LIVE table: raw payloads expire, old rows are pruned, and `sampler.backfill_org` deliberately
reconstructs **eighteen months** of `metric_history` from a ledger that may hold far less.

Applied literally, every period older than the ledger counts zero events, reads as an org-wide
shutdown, and is excluded from the fit — so a tenant whose events have aged out has EVERY trend it
owns silently retracted. That is a strictly worse failure than the false churn alarm the rule
exists to prevent, and the existing trend suite caught it: `test_trend.test_the_sweep_writes_the_
trend_fact` seeds a declining series on an org with no `source_events` at all, and the correction
turned `DECLINING` into `INSUFFICIENT_HISTORY`.

**The reading taken: a silence is only measurable inside the span the ledger demonstrably covers.**
`gap_reason.classify_window` classifies nothing before the first period in the window that carried
any event; a window with no events anywhere classifies nothing at all and corrects nothing.
Trailing silence IS classified — the drain just ran, so we were watching — which is the asymmetry
that keeps the false-churn case working. Doc 13 should say which end of the ledger it trusts.

### A-23 · Doc 13 does not say where a gap reason is CONSUMED, and the only honest seam rewrites the trend's own fact

E-10 ends at "only `GENUINELY_ZERO` may contribute to a trend" and names no caller.
`trend.refresh_trend_facts` publishes `derived.trend.<metric>` on a version-keyed row and takes no
classifier, and the alternative seams are both worse: a second `derived.gap_corrected_trend.*`
family leaves two answers on one node for every downstream reader to choose between, and threading
a classifier through `compute_trend` changes a pure function three waves already test.

**The reading taken:** `gap_reason.refresh_gap_corrected_trends` runs on the drain immediately
after the trend pass and before `refresh_situation_importance` (modifier 3a reads
`derived.trend.*`), recomputes only the pairs whose window holds an unmeasurable period, and writes
back through `trend._write_trend_fact` — the SAME upsert on the SAME `fv_trend_*` row. One trend
algorithm, one fact per (node, metric); this module changes only the series it is computed over.
Importing another module's private writer is the cost, and it is deliberate: two copies of one
upsert is the exact defect `analytic/publish.py` was written to delete.

### A-28 · H8's "situations produced by both paths" does not say which two paths, and the two candidates measure opposite things

> Numbered A-28 because A-24..A-27 were added by later waves BELOW §4's heading rather than in this section; they are §3 rows living in the wrong place, and renumbering another wave's assumptions to tidy that would break every reference to them.

Doc 09's H8 table prints `| situations produced by both paths | 100% |` and names neither path.
Two readings are available in this tree and they are not close:

1. **anchor-based detection vs the pattern registry.** Doc 06's MIGRATE line is explicit —
   *"keep anchor-based detection running alongside. Compare fire sets on a pilot for 7 days before
   switching. Do not delete the anchor path in this wave"* — and `context/patterns` writes only its
   own three tables, so both paths genuinely run and can be diffed.
2. **the publish path with the v2 enrichments disabled vs enabled.** This is the reading L1's G10
   takes one layer down (old extraction vs new lane), but at L2 it does not exist: the analytic
   stratum, the composer and M-4 change a situation's NUMBERS, not the SET of situations
   `refresh_situations` writes, so this comparison is 100% by construction on every tenant and
   measures nothing.

**The reading taken:** (1). `scripts/l2_shadow_diff.py` reads the row as a LOSS check — every LIVE
situation the anchor path produced in the window (`context_situations.computed_at` in window,
`status in ('active','partial')`) must have a `pattern_fires` row on the same `anchor_node_id` in
the same window. Below 100% the answer to "may the anchor path be deleted" is no, and the report
names the situations that would disappear. The founder-visible-regression row is the same question
restricted to subjects a card is actually built on.

**What this makes measurable, and what it does not.** Under reading (1) the row is expected to FAIL
on a tenant until the registry's pattern set covers that tenant's situation set — which is
precisely the seven-day evidence doc 06 asks for before the switch, so a failing row here is the
gate working rather than the gate being wrong. Under reading (2) it would pass on day one and tell
nobody anything.

**Consequence if the other reading was intended:** the gate is trivially green and doc 06's
seven-day comparison has no report behind it. The line should be re-worded to name its two paths.

---

## 4. The specs

Format follows the group docs exactly: **WHAT / WHY / WHERE / WHEN / HOW / FAILURE MODES /
ACCEPTANCE**, with a **REVERSE PROMPT** on the units that carry the most blast radius — the same
selection rule doc 02, 03, 05, 06 and 07 use.

Every spec obeys the four Layer 2 laws and the two build doctrines that survived Layer 1:

* **integer basis points, no float in any score path** — `x * 9 // 10`, never `x * 0.9`;
* **no clock in logic** — `eval_time` is a parameter, never `datetime.now()`;
* **the model may describe, never score** — no LLM output reaches a `_bp` field;
* **a unit is done when a real request path reaches it** — "green and called by nothing" is the
  defect Layer 1 shipped six times. Where the caller is not obvious from **WHERE**, the spec
  carries an explicit **WIRED AT** line naming it; everywhere else the ACCEPTANCE rows say which
  path the proof must drive, and a test that constructs the collaborator itself proves the unit,
  not the wiring.

---

# L2.1 · Enterprise Context Graph

## ⚠️ L2.1.3 · Temporal View

### L2.1.3-U1 · Temporal fields feed the sampler

**WHAT** — The one function that turns a node's temporal fields into the sample the metric
history store appends: `temporal_metrics(node, facts, edges, *, period_start, period_end)
-> list[MetricPoint]`.

**WHY** — Doc 01 closes L2.1.3 with *"Nothing to build here beyond ensuring the temporal fields
feed the sampler."* That sentence is a unit, and it is the seam on which the entire analytic
stratum stands: `valid_from`, `last_reinforced` and edge age are the only temporal truth the graph
holds, and L2.4.1's `metric_history` is empty until something reads them into `MetricPoint`s.
Left unwritten, X1 ships a table and X2 computes trends over nothing — the exact shape of the
Layer 1 defect where a unit is green and no request path reaches it.

It is also the boundary that keeps doc 09's *must not regress* item 6 true: **this function only
ever reads `graph_facts`; it never stops it overwriting.** Two tables, two questions.

**WHERE** — `genios_engine/context/analytic/temporal.py`
**WHEN** — X1, with `L2.4.1-U1`. Requires nothing from Layer 1.

**HOW** — pure, injected inputs, integer only:

```
for each temporal field the registry declares for this node type:
    age_days        = (period_end - valid_from).days                    -> unit "days"
    since_reinforced= (period_end - last_reinforced).days               -> unit "days"
    edge_age_days   = per edge type, oldest unresolved edge             -> unit "days"

emit MetricPoint(
    metric        = the REGISTERED metric name (an enum, never a free string)
    value_bp      = the integer above           # unit "days" is not a ratio; no bp scaling
    observed_at   = period_end                  # the PERIOD, never the compute time
    known         = the underlying field is non-null
    coverage_ready= the node's coverage_ready, carried through unchanged
)

a null temporal field emits a point with known=False and value_bp=None — NEVER 0.
```

**Period boundaries come from the one shared function** L2.4.1-U1 names, so backfilled and live
points are indistinguishable to a reader. This unit must not compute its own.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A null `valid_from` emitted as day 0 | a node with no recorded start looks infinitely old, and every trend over it declines | `known=False, value_bp=None`; V-3 rejects a point that carries both |
| Metric named as a free string | the series splits silently on a rename and the trend resets to `INSUFFICIENT_HISTORY` | metric names come from the registered enum; an unregistered name raises at call time |
| This unit computes its own period boundary | phantom changepoints where backfill and live sampling disagree | boundaries are a parameter, produced by L2.4.1's shared function |
| `coverage_ready` dropped | a coverage gap becomes a real zero downstream | carried through unchanged; a point with no coverage value carries `None`, and `None` is `UNKNOWABLE` |

**ACCEPTANCE**
```
pytest tests/context/analytic/test_temporal.py -q
# a node with valid_from 30 days before period_end -> one point, value_bp 30, known=True
# a node with valid_from null -> one point, known=False, value_bp None (NOT 0)
# last_reinforced later than valid_from -> two distinct metrics, not one
# coverage_ready None on the node -> None on every point it produces
# an unregistered metric name raises rather than writing
# same node and period evaluated twice -> identical points (no clock read)
```

**WIRED AT** — called by the metric sampler (`L2.4.2-U1`) inside the drain, not by a test. The
acceptance suite above proves the function; `tests/context/analytic/test_sampler.py` must contain
one row proving the **sampler** produces temporal points on a real drain, or this unit is
unwired and does not count as done.

---

## ❌ L2.1.4 · Authority View

### L2.1.4-U2 · Authority resolution and approver load

**WHAT** — The read side of the Authority view: `resolve_authority(org, subject_type, amount,
*, as_of) -> AuthorityAnswer` and `approver_load(org, node_id, *, as_of) -> ApproverLoad`.

**WHY** — `L2.1.4-U1` builds the table. Nothing reads it. Doc 01 names three readers explicitly
and none of them can call a table: Layer 4's **Policy** unit (*"which organisational rules bind"*),
Layer 4's **Constraint** unit (*"what cannot happen"*), and the **Founder Bottleneck** surface
Globe rates highest — *"this person is the only approver for N open items"*, which doc 01 calls
*"an Authority-view query"* in those words. `L2.6.1-U1`'s `@authority_threshold` reference also
resolves through here, so *"high value"* means this company's threshold rather than a constant.

A store with no reader is the Layer 1 defect in its purest form. This unit is the reader.

**WHERE** — `genios_engine/context/authority.py` (beside `L2.1.4-U1`)
**WHEN** — X7, with `L2.1.4-U1`.

**HOW** — deterministic, no LLM, no clock:

```
resolve_authority(org, subject_type, amount_minor_units, currency, *, as_of):
  1. SELECT the rules for (org, subject_type) whose validity window contains as_of
  2. rank by SOURCE, never by recency:  admin_declared 10000 > discovered 8000 > inferred 5000
  3. drop every `inferred` rule from the ENFORCEABLE answer; return them separately as
     `suggestions` — doc 01: an inferred rule proposes, a human confirms
  4. among enforceable rules, choose the tightest threshold the amount crosses;
     a rule with threshold_minor_units NULL applies at any value and is the floor
  5. no rule matched -> AuthorityAnswer(kind=NO_AUTHORITY_RULE)
     which is NOT the same as "anyone may approve" and must not be read as permissive
  6. return approver, delegate, the rule_id that decided, and its source rank

approver_load(org, node_id, *, as_of):
  count the open items for which this node is the ONLY enforceable approver,
  by joining the rules valid at as_of against open decision/approval situations.
  sole_approver_count is the Founder Bottleneck number. It is a COUNT, not a score.
```

**Currency is compared, never converted.** A rule in INR and an amount in USD do not match; the
answer is `NO_AUTHORITY_RULE` for that rule, not an implied conversion. A converted threshold is
an invented governance rule.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| `NO_AUTHORITY_RULE` read as "anyone may approve" | a card names no approver and reads as approved | it is a distinct enum member, never an empty list or `None`; the contract has no permissive default |
| An inferred rule returned in the enforceable answer | the system invents governance | inferred rules are returned in a separate `suggestions` field the enforceable path cannot reach |
| Ranked by recency instead of source | a newly discovered document overrides an admin's declaration | rank is by source first; recency only breaks ties **within** a source rank |
| `as_of` defaulted to now inside the function | March's decision re-judged against September's rules | `as_of` is a required keyword argument with no default |
| Cross-currency threshold compared numerically | an ₹80,000 contract clears a $50,000 threshold | currency equality is required before a threshold comparison |

**ACCEPTANCE**
```
pytest tests/context/test_authority.py -q
# an admin_declared rule outranks a discovered rule for the same class and amount
# an inferred rule never appears in the enforceable answer, and DOES appear in suggestions
# no matching class -> NO_AUTHORITY_RULE, and the enum member is not falsy-equal to "approved"
# a rule valid Jan-Mar answers as_of=Feb and does not answer as_of=Apr
# a threshold in INR does not match an amount in USD
# a node that is the only approver on 4 open items -> sole_approver_count == 4
# as_of is required: calling without it raises TypeError (source-level, no clock)
```

**WIRED AT** — `L2.6.1-U2`'s `@authority_threshold` resolution and the L4 Policy/Constraint units.
A test that constructs the rule rows itself proves the query; the wiring test is the one where a
**pattern** carrying `@authority_threshold` evaluates against a real org's rules.

---

## ⚠️ L2.1.7 · Resource View

### L2.1.7-U1 · `deal.value` from a verified, unconflicted `Money`

**WHAT** — Derives `deal.value` from exactly one `Money` claim, or leaves it `unknown` and says
why: `derive_deal_value(money_claims, conflicts, *, eval_time) -> DealValueDecision`.

**WHY** — `derived.py:198` records the current restraint in its own words: *"`deal.value` is
deliberately NOT derived. There is no honest way to infer a number nobody stated"* — and
`derived.py:385-387` records the cost: `deal.value` is present on **exactly one** node, and 501
runs abstained with `INSUFFICIENT_CONTEXT` partly for that reason.

**The restraint was correct on its stated premise, and Layer 1 v2 changed the premise.** `Money`
now arrives normalized (ALG-10), span-verified (ALG-08), authority-ranked (ALG-14) and with
conflicts detected (ALG-12) — `contracts/units.py:84` carries `minor_units`, `currency` and
`as_written`. The number is no longer inferred; it is quoted.

Two things downstream are blocked on it: Layer 1's ALG-17 monetary term, and `L2.7.4-U1`'s base.

**WHERE** — `genios_engine/context/derived.py` (new function; the existing restraint comment
stays and is amended, not deleted — it is the record of why this took two versions)
**WHEN** — X7. Requires L1 v2 W8 (QES publishing carries verified `Money` and `Conflict`).

**HOW** — a refusal cascade, in this order:

```
1. FILTER   keep only Money claims whose evidence span verifies against source (ALG-08)
            an unverified amount is dropped, never ranked
2. CONFLICT if ALG-12 reports an unresolved conflict on this subject_key ->
            DealValueDecision(known=False, reason=CONFLICTED, conflict_ref=<id>)
            The field stays `unknown` and the Conflict is LINKED, so a card can show
            "$84K in the email, $74K in the attached PDF" instead of picking one.
3. RANK     among the survivors, highest authority rank wins (ALG-14: a signed document
            beats a mail body). Ties inside a rank break by the LATER claim.
4. CURRENCY claims in different currencies are a CONFLICT, not a comparison. Never convert.
5. DECIDE   DealValueDecision(known=True, minor_units, currency, winning_claim_ref,
                              reason=VERIFIED_UNCONFLICTED, rank, rejected=[...])
6. RECORD   the rejected claims and the rule that decided travel with the decision.
            "Why is this deal worth $84K?" must be answerable without recomputation.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A conflicted amount derived anyway | a wrong number flows straight into prioritisation — the failure `derived.py:198` was written to prevent | step 2 is unconditional and precedes ranking; a conflicted subject can never reach step 5 |
| An unverified span ranked | the model's paraphrase becomes a contract value | step 1 drops it before ranking; there is no "low confidence" derivation path |
| Currencies converted | an invented FX rate becomes a business fact | step 4 makes cross-currency a conflict; conversion appears nowhere |
| The winner not recorded | a value nobody can defend in a review | `winning_claim_ref` and `rejected` are required fields on the decision |
| Value re-derived per drain from a changing rank | the number oscillates between two claims | ranking is total and deterministic — authority, then recency, then claim id |

**ACCEPTANCE**
```
pytest tests/context/test_deal_value.py -q
# a single verified unconflicted Money -> known=True, minor_units matches, reason VERIFIED_UNCONFLICTED
# the same claim with an unresolved ALG-12 conflict -> known=False, reason CONFLICTED, conflict_ref set
# an unverified span -> never derives, and does not appear in `rejected` as a near-miss winner
# a signed-document claim and a mail-body claim -> the document wins, both recorded
# two claims in USD and INR -> CONFLICTED, and no conversion appears anywhere in the module
# two runs over the same claims -> byte-identical decision
# no float: source-grep the module for `/` and `float(` in the value path
```

**REVERSE PROMPT**
```
TASK: Derive deal.value — but only from a claim we can quote and nobody contradicts.
FILE: genios_engine/context/derived.py

THE HISTORY: derived.py:198 refuses to derive this field, and it was RIGHT on its premise —
"there is no honest way to infer a number nobody stated". Do not delete that comment. Amend
it. L1 v2 changed the premise: Money now arrives span-verified (ALG-08), normalized (ALG-10),
authority-ranked (ALG-14) with conflicts detected (ALG-12). The number is quoted, not inferred.

THE COST OF LEAVING IT: derived.py:385-387 — deal.value present on exactly ONE node, 501 runs
abstaining with INSUFFICIENT_CONTEXT. L1's ALG-17 monetary term and L2.7.4's base both need it.

IMPLEMENT:
  def derive_deal_value(money_claims, conflicts, *, eval_time) -> DealValueDecision   # PURE

ALGORITHM: the 6 ordered steps in L2.1.7-U1.

HARD RULES:
1. CONFLICT CHECK BEFORE RANKING. A conflicted subject leaves the field unknown and LINKS the
   conflict. Never pick a winner from a conflicted set — the card shows both numbers.
2. UNVERIFIED SPAN NEVER DERIVES. There is no low-confidence path. Drop it in step 1.
3. NEVER CONVERT CURRENCY. Two currencies are a conflict. An invented FX rate is a fabricated
   business fact and it would flow into prioritisation.
4. INTEGER minor_units only. No float anywhere in the module's value path.
5. eval_time is a parameter. No datetime.now().
6. RECORD the winner, the rule that chose it, and every rejected claim on the decision object.

TEST tests/context/test_deal_value.py — every row in the L2.1.7-U1 ACCEPTANCE list.
WIRE IT at the deal roll-up (compute_deal_view, derived.py:189) and prove the wiring with a
test that drives THAT function, not derive_deal_value directly.
```

---

# L2.2 · Graph Engines

## ✅ L2.2.1 · Graph Builder — the one gap: M-2

### L2.2.1-U1 · Ambiguous edge typing (M-2)

**WHAT** — Types the edges the deterministic rule table cannot: `type_edge(candidate, rule_result,
*, budget) -> EdgeTypeJudgment`, consulted only on the ambiguous remainder.

**WHY** — MAP A lists **M-2 · Ambiguous edge typing · L2.2.1 · deterministic gate: rule table ·
T1 · 2-10 fires/day**. Doc 02 never mentions it: the component is marked ✅ and the LLM site has
no spec anywhere in the plan. It is the smallest of the nine sites and the easiest to lose, and
losing it means the ambiguous remainder keeps being dropped — which is the same silent-discard
failure doc 03 names for L2.3.2's gray band.

An untyped edge is not a neutral outcome. `L2.2.5-U1` decays by edge type, `L2.3.8-U1` traverses
by edge type, and `L2.6.1-U1` matches `{kind: edge, type: owns}` — an edge with no type is
invisible to all three.

**WHERE** — `genios_engine/context/edge_typing.py`, with the call site in
`genios_engine/context/llm/` (see **A-3** — the same separation the L2.3 gate assumes)
**WHEN — proposed** — X7, beside the other graph-engine work (**A-6**).

**HOW**

```
1. GATE (deterministic)  the existing rule table runs FIRST and decides everything it can.
                         The model sees a candidate only when the table returns AMBIGUOUS —
                         two rules matched, or none did and both endpoints resolved.
2. NARROW                the model chooses from the REGISTERED edge-type enum only.
                         It may not propose a new type. A new edge type is a migration.
3. CALL (T1)             input: both endpoint node types, their display names, the evidence
                         span, and the candidate types. Output:
                         {edge_type, confidence_bp, quote, offsets} — describing, not scoring.
4. VALIDATE              span verifies against source (guard.py evidence_ok); edge_type is in
                         the enum; below the floor -> NO EDGE, not a guessed one.
5. RECORD                the edge carries typed_by = "rule" | "model" and the rule/prompt
                         version, so a later audit can separate the two populations.
```

**`confidence_bp` here is the model's own certainty and it never reaches a ranking path.** It
gates the edge's existence and is stored for audit. Doctrine: the model may judge a relationship;
it may not produce a number that ranks anything.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Model invents an edge type | a type no consumer knows about, silently invisible | choice is constrained to the registered enum; anything else is a validation failure |
| Model consulted where the table already decided | cost and drift on cases that were settled | the gate is unconditional and precedes the call; a rule result other than `AMBIGUOUS` never calls |
| A guessed edge on an unresolved endpoint | a false relationship in the graph, which `L2.3.8-U1` will then traverse into a phantom chain | both endpoints must be identity-resolved before the candidate is eligible |
| Budget exhausted, edge silently dropped | the ambiguous remainder is lost again | on exhaustion the candidate is **parked** with `typed_by="deferred"` and counted; never silently discarded |

**ACCEPTANCE**
```
pytest tests/context/test_edge_typing.py -q
# a candidate the rule table types -> zero model calls (assert the client is never invoked)
# a candidate with two matching rules -> one call, and the returned type is from the enum
# a returned type outside the enum -> no edge written
# an unverified span -> no edge written
# an unresolved endpoint -> not eligible, no call
# budget exhausted -> parked with typed_by="deferred", counted, and NOT dropped
# every written edge carries typed_by and the rule/prompt version
```

---

## ✅ L2.2.4 · Graph Deduplicator — the one gap: M-1 (see **A-2**)

### L2.2.4-U1 · Ambiguous entity linking (M-1), as a proposer

**WHAT** — For the pairs the alias-and-domain cascade leaves undecided, proposes a merge for a
human: `propose_link(pair, cascade_result, *, budget) -> MergeProposal | None`.

**WHY** — MAP A lists **M-1 · Ambiguous entity linking · L2.2.4 · deterministic gate: alias +
domain cascade · T1 · 1-5 fires/day**. Doc 02 assigns L2.2.4 no unit and instructs *preserve, do
not touch*. **A-2 records the contradiction.** This spec assumes the reading that keeps both
statements true: the model **never resolves an identity** and never writes to `graph_nodes` or
`source_identity_map`. It writes a row to `merge_proposals` — the table that already exists for
exactly this, reviewable, recorded and reversible.

`identity.py:25` — *"No edit distance, no embeddings, no '0.87 similar'"* — survives untouched,
because a proposal is not a resolution. Doc 02's worst case, *"two half-correct situations
instead of one correct one"*, is avoided in the direction that matters: nothing merges without a
human.

**WHERE** — `genios_engine/context/merge_proposer.py` (new; **not** `identity.py`, **not**
`merge.py`)
**WHEN** — X7. Its own PR, per doc 02's instruction.

**HOW**

```
1. GATE      the alias + domain cascade in identity.py runs unchanged and decides everything
             it can. Only pairs it leaves UNDECIDED are eligible.
2. FILTER    both nodes must be the same node_type, in the same org, and neither already the
             subject of an open proposal. A second proposal on an open pair is a duplicate.
3. CALL (T1) input: both display names, their canonical keys, their strongest evidence spans,
             and the counterparties each has been seen with.
             output: {same_entity: bool, reason, quote, offsets, confidence_bp}
4. VALIDATE  spans verify; below the floor -> nothing written at all.
5. PROPOSE   write merge_proposals(..., proposed_by="model", prompt_version=...).
             STATUS IS ALWAYS PENDING. There is no auto-apply path in this module,
             and no code path in it writes graph_nodes, source_identity_map or merge_history.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A model-proposed merge auto-applies | a merge nobody reviewed, in the component doc 02 calls the strongest in Layer 2 | this module has no writer for anything but `merge_proposals`; the acceptance suite asserts that at source level |
| Proposal spam on the same pair | a review queue nobody reads | step 2 refuses a pair with an open proposal; one pending proposal per pair, ever |
| The cascade is bypassed | a resolvable pair goes to the model, and `identity.py:25` is broken by the back door | the gate is unconditional; a pair the cascade decides never reaches step 3 |
| `identity.py` edited to call this | doc 02's instruction violated, review scope widened | the seam is the drain, not `identity.py`; the wiring test drives the drain |

**ACCEPTANCE**
```
pytest tests/context/test_merge_proposer.py -q
# a pair the cascade resolves -> zero model calls
# an ambiguous pair, same_entity=True -> exactly one merge_proposals row, status pending
# the same pair again while the proposal is open -> no second row, no second call
# same_entity=False -> nothing written
# below the confidence floor -> nothing written
# source-grep: this module contains no INSERT/UPDATE against graph_nodes,
#   source_identity_map or merge_history
# git diff for this PR touches neither identity.py nor merge.py
```

---

## ⚠️ L2.2.7 · Version Manager

### L2.2.7-U2 · Snapshot writer and cadence

**WHAT** — `take_snapshot(conn, org_id, *, at) -> str` plus the policy that decides when it runs.

**WHY** — `L2.2.7-U1` specs `read_graph(org, as_of)` and names `take_snapshot` in its reverse
prompt without specifying it. **A read with no writer answers every as-of query with an empty
graph** — the spec's own edge case, *"as_of before the first snapshot returns an empty graph"*,
becomes the only case. This is the "built and called by nothing" defect at table scope: the
migration lands, `graph_snapshots` stays empty, and the security-review question doc 02 exists to
answer is still unanswerable.

The cadence is as load-bearing as the writer. Doc 02: *weekly, plus one before any bulk merge
operation.* The pre-merge snapshot is the one that matters — a merge is the single operation that
makes history unrecoverable.

**WHERE** — `genios_engine/context/graph_store.py` (beside `read_graph`) + the drain's periodic
hook
**WHEN** — X7, with `L2.2.7-U1`.

**HOW**

```
take_snapshot(conn, org_id, *, at):
  1. read the live graph at `at` (nodes, facts, edges valid at that instant)
  2. serialize to OBJECT STORAGE; the row carries a payload_ref, never the payload
  3. insert graph_snapshots(org_id, snapshot_at=at, graph_version, node_count, payload_ref)
     the primary key (org_id, snapshot_at) makes a re-run for the same instant idempotent
  4. return payload_ref

CADENCE — a decision table, not a cron guess:
  weekly floor        no snapshot in 7 days              -> take one
  pre-merge           before ANY bulk merge operation    -> take one, unconditionally
  post-backfill       after a historical backfill lands  -> take one
  retention           24 months, matching metric_history
```

**Claim the work in the database, not in the process.** The drain runs in several workers; two
workers taking the same weekly snapshot is a wasted serialization of the whole graph. The weekly
path claims a row before it serializes — the same pattern the Layer 6 weekly job already uses.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Writer never scheduled | `read_graph` answers every as-of query empty and looks broken rather than unfed | the cadence table is part of this unit, and the acceptance suite drives the **scheduler**, not the function |
| Two workers snapshot at once | the graph serialized twice per week | DB claim before serialization |
| Bulk merge runs with no prior snapshot | the pre-merge state is unrecoverable — a hard failure, since a merge is irreversible in history terms | the merge path calls `take_snapshot` first and **fails closed** if it cannot |
| Payload written into the row | an unbounded column and a table nobody can query | `payload_ref` only; the acceptance suite asserts the row size bound |
| Snapshot at a clock read | two snapshots that cannot be ordered against the deltas between them | `at` is a required parameter |

**ACCEPTANCE**
```
pytest tests/context/test_point_in_time.py -q
# take_snapshot writes exactly one row and stores a payload_ref, not a payload
# the same (org, at) twice -> one row (idempotent), second wins
# a bulk merge with a failing snapshot writer -> the merge does not run
# no snapshot in 8 days -> the cadence decides "take one"; 3 days -> "skip"
# two concurrent weekly claims -> exactly one serialization
# read_graph(as_of=<between two snapshots>) uses the earlier one plus deltas
# retention prunes past 24 months and leaves the remaining series readable
```

**WIRED AT** — the periodic drain hook and `merge.py`'s bulk path. A test that calls
`take_snapshot` directly proves the writer; the wiring rows above (cadence, pre-merge fail-closed)
are the ones that prove a real path reaches it.

---

# L2.3 · Cross-Correlation Engine

## ⚠️ L2.3.2 · Cross Conversation

### L2.3.2-U1 · Ambiguous conversation matching (M-3)

**WHAT** — Decides whether two conversations the deterministic joins left undecided are about the
same thing: `match_conversations(pair, join_result, *, budget) -> ConversationMatch`.

**WHY** — Doc 03 states the gap in one line and gives it no spec: *"`thread_correlations` — clear
cases only; **gray band dropped**"*, and *"today the ambiguous middle is silently dropped rather
than escalated, and that gray band is where the cross-tool value lives."* MAP A budgets it at
3-15 fires/day.

A dropped gray-band pair is not a neutral outcome either: the two conversations become two
situations about one reality, and `L2.7.3` then has nothing to merge because it merges by shared
entity and the shared entity is exactly what the join could not establish.

**WHERE** — `genios_engine/context/correlation_match.py`, with the model call in
`genios_engine/context/llm/` — see **A-3**, which this placement assumes rather than resolves.
**WHEN** — X6, with the other LLM sites.

**HOW**

```
1. GATE (deterministic)  subject / participant / time joins run first and settle every clear
                         case. A pair is eligible only when the joins are INCONCLUSIVE —
                         partial participant overlap, or a subject match outside joins_window.
2. BOUND                 candidate pairs come from the same org and the same domain, within
                         merged_span. Never an org-wide cross product.
3. CALL (T1)             input: both subjects, participant sets, first/last timestamps, and one
                         representative quote from each.
                         output: {same_subject: bool, reason, quotes[2], offsets, confidence_bp}
4. VALIDATE              both quotes verify against their sources; below the floor -> no link.
5. LINK                  write a thread correlation with linked_by="model" and the prompt
                         version. A model-made link is DISTINGUISHABLE from a joined one for
                         the rest of its life, so the two populations can be measured apart.
```

**The tenant node stays excluded.** Doc 09's must-not-regress item 4 is about anchors, and the
same hazard applies here: a pair whose only shared participant is the tenant node or a
`NON_ANCHORING_ROLE` connector (`correlation.py:159`) is **not eligible**. Without that, an
introduction bot present in 254 threads becomes a shared participant in every pair.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Over-linking merges two real subjects | one situation covering two realities — worse than two situations, because nothing downstream can split it | asymmetric floor: linking requires more confidence than not linking; a single shared participant is never sufficient |
| Connector or tenant node as the shared participant | every conversation fuses, exactly the `boardy.ai` failure `choose_anchors` documents | ineligible by rule, before the call |
| Org-wide candidate generation | quadratic cost and a budget blown in one drain | step 2's bounding is part of the unit, not the caller |
| Model links, nobody can tell later | the joined and judged populations become unmeasurable | `linked_by` + prompt version on every link |
| Budget exhausted | back to silently dropping the gray band | on exhaustion the pair is **parked and counted**, and the count is reported |

**ACCEPTANCE**
```
pytest tests/context/test_correlation_match.py -q
# a pair the deterministic joins settle -> zero model calls
# an inconclusive pair, same_subject=True -> one link, linked_by="model", prompt version stored
# a pair whose only shared participant is a NON_ANCHORING_ROLE node -> ineligible, no call
# a pair whose only shared participant is the tenant node -> ineligible, no call
# same_subject=False -> no link
# an unverified quote -> no link
# budget exhausted -> parked and counted, never dropped
```

---

## ⚠️ L2.3.3 · Cross User

### L2.3.3-U1 · Role synthesis across systems

**WHAT** — Synthesizes what a person **is** to the org from their behaviour across every system:
`synthesize_roles(person_node, observations, edges, *, eval_time) -> tuple[RoleAssertion, ...]`.

**WHY** — Doc 03's component map states the gap in five words: *"`lift_people_to_their_companies`
— a lift, not role synthesis."* The lift promotes a person to their employer so a conversation
anchors on the company; it says nothing about what that person does. `correlation.py:440`'s
`_lift_roles` carries roles it did not derive.

Roles are consumed by three things that currently guess: `L2.7.7-U1`'s speaker-authority table
(*owner* vs *org-internal* vs *external counterparty* vs *service account* — four role
judgments), `L2.1.4-U2`'s approver resolution, and `NON_ANCHORING_ROLES` at `correlation.py:159`,
which today is a hand-listed frozenset.

**WHERE** — `genios_engine/context/roles.py`
**WHEN — proposed** — X7 (**A-6**).

**HOW** — deterministic, evidence-counted, no LLM:

```
for each person node, over the observation window:
  DECIDER      appears as the actor on decision_states with state="made"        >= 2
  APPROVER     named as approver in an authority rule, OR approved N of N in a class
  OWNER        holds `owns` edges, or is ball_in_court on open loops            >= 1
  INTRODUCER   appears in >= 3 threads whose first message introduces two other parties
  MACHINE      address matches a service-account pattern, or no human-authored body ever
  EXTERNAL     email domain not in the org's own domain set
  CHAMPION     highest inbound+outbound count at a counterparty account

each assertion carries: role, evidence_count, first_seen, last_seen, the observation ids.
A role is ASSERTED, never scored. There is no role confidence_bp — the evidence count is
the honest number and a consumer decides what threshold it needs.
```

**A person holds several roles at once**, and they are context-scoped: the same human can be
`EXTERNAL` in the vendor context and `CHAMPION` in the customer one. That scoping is
`L2.3.7-U1`'s, and this unit emits role assertions **per context**, never one global role.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| One global role per person | the same human is a vendor contact and a customer champion, and one of the two facts is destroyed | assertions are per (person, context); the API returns a tuple, never a single role |
| `MACHINE` missed | `L2.7.7-U1` accepts a resolution stated by a no-reply autoresponder, which its own table says to ignore entirely | the machine test runs first and is not overridable by any other role |
| Role asserted on one observation | a single introduction makes someone an `INTRODUCER` forever | minimum evidence counts above, and `last_seen` lets a consumer age them |
| A role scored | the model or a formula ranks people | there is no score in the output; the acceptance suite asserts no `_bp` field exists on `RoleAssertion` |
| `NON_ANCHORING_ROLES` diverges from these names | the hand-listed frozenset and the synthesized roles disagree, and anchoring silently changes | the frozenset is defined in terms of this enum after this unit lands |

**ACCEPTANCE**
```
pytest tests/context/test_roles.py -q
# a person with 2 decision_states state="made" -> DECIDER with evidence_count 2
# the same person with 1 -> no DECIDER assertion
# a no-reply address -> MACHINE, and no other role is asserted for it
# a person at a non-org domain -> EXTERNAL in that context only
# a person appearing as vendor contact and customer champion -> two assertions, two contexts
# RoleAssertion has no field ending in _bp (source-level assertion)
# eval_time is a parameter: the same inputs at two eval_times give the same roles
```

---

## ❌ L2.3.4 · Cross Timeline

### L2.3.4-U2 · Condition parsing (M-5)

**WHAT** — Turns a stated condition into a checkable predicate, or refuses:
`parse_condition(condition_text, graph_vocabulary, *, budget) -> ConditionPredicate | Unparseable`.

**WHY** — `L2.3.4-U1` specs the store-index-sweep-satisfy-half-life cycle and folds the parse into
step 2 with three example translations and no spec of its own. It is the unlock of the surface
doc 03 calls *"the one Globe calls the surface people remember"*, and it is a **separate public
callable with a different failure mode**: the sweep re-evaluates predicates cheaply on every
drain, the parse happens once per condition and is the only part that can be wrong in a way that
nags a real person.

Doc 03 is explicit that a regex cannot do it: *"come back when you have two enterprise
references"* is semantic. It is equally explicit about the refusal path — *"unparseable -> stored,
checked by human review only."*

**WHERE** — `genios_engine/context/conditions.py`, model call in `genios_engine/context/llm/`
(**A-3**)
**WHEN** — X6.

**HOW**

```
1. DETERMINISTIC FIRST  date patterns ("after March 1", "in Q3") and simple count patterns
                        ("once we have 2 X") resolve without a call. This is the volume control.
2. VOCABULARY BOUND     the model may only emit predicates over REGISTERED fact names, metrics
                        and node types — the same vocabulary L2.6.1 patterns validate against.
                        A predicate over an unknown field is UNPARSEABLE, not a new field.
3. CALL (T2)            input: the condition text, the speaker, the subject, and the vocabulary.
                        output: a predicate TREE ({op, field, comparator, value}), never SQL,
                        never a code string, plus a quote and offsets.
4. VALIDATE             the tree type-checks against the vocabulary; every leaf comparator is
                        one of the registered set; the quote verifies against source.
5. STORE                parseable   -> the dormant condition carries the predicate and is swept
                        unparseable -> stored with reason, surfaced in a REVIEW QUEUE, never
                                       auto-fired and never shown as a card
```

**The model writes the predicate; a deterministic engine evaluates it.** Same discipline as M-9
cohort authoring in doc 00, and for the same reason: a judgment that becomes data can be
reviewed, diffed and corrected; a judgment that stays in the model cannot.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A rhetorical line parsed into a predicate | the product nags about a throwaway sentence | only `is_conditional=true` commitments (`contracts/extraction.py:230`) are eligible; the rest never reach step 3 |
| Predicate emitted as SQL or code | injection, and a predicate nobody can review | output is a typed tree; the acceptance suite asserts no string is ever executed or interpolated into SQL |
| Predicate over an unregistered field | a condition that can never be satisfied, silently | vocabulary-bound at step 2; unknown field -> UNPARSEABLE with a reason |
| Unparseable conditions accumulate invisibly | a growing pile nobody sees | the review queue is queryable and its depth is reported |
| Budget exhausted | conditions stop being indexed and the surface quietly dies | fall back to the deterministic patterns and LOG; never silently skip |

**ACCEPTANCE**
```
pytest tests/context/test_conditions.py -q
# "after March 1" -> parsed deterministically, zero model calls
# "once we have two enterprise references" -> a predicate tree over registered fields
# a predicate naming an unregistered field -> UNPARSEABLE with reason, not a new field
# an is_conditional=false commitment -> never eligible, zero calls
# the returned predicate is a tree; no code path interpolates it into SQL (source-grep)
# an unparseable condition is queryable in the review queue and never fires
# budget exhausted -> deterministic-only, and the fallback is logged
```

**REVERSE PROMPT**
```
TASK: Parse stated conditions into checkable predicates. This is the unlock for the
"a partner said they'd revisit once you had two enterprise references — you closed the second
11 days ago" surface.
FILE: genios_engine/context/conditions.py (model call in genios_engine/context/llm/)

INPUT EXISTS: L1 emits Commitment.is_conditional + condition_text
(contracts/extraction.py:230,233). Nothing consumes them.

IMPLEMENT:
  def parse_condition(condition_text, graph_vocabulary, *, budget)
        -> ConditionPredicate | Unparseable

ALGORITHM: the 5 ordered steps in L2.3.4-U2.

HARD RULES:
1. DETERMINISTIC FIRST. Dates and simple counts never reach the model.
2. THE MODEL WRITES DATA, NOT CODE. Output is a typed predicate tree. Never SQL, never a
   Python string, never anything eval'd. A judgment that becomes data can be reviewed.
3. VOCABULARY-BOUND. Predicates may only name registered facts, metrics and node types —
   the same vocabulary L2.6.1 validates patterns against. Unknown field -> UNPARSEABLE.
4. UNPARSEABLE IS A REAL, FIRST-CLASS OUTCOME. Store it with its reason, put it in a review
   queue, and never let it fire. Guessing here nags a real person about a throwaway line.
5. Only is_conditional=true commitments are eligible. Do not scan free text for conditions.
6. Budget exhausted -> deterministic patterns only, and LOG. Never silently skip.
7. eval_time is a parameter. The parse must not read a clock.

TEST tests/context/test_conditions.py — every row in the L2.3.4-U2 ACCEPTANCE list.
WIRE IT into L2.3.4-U1's step 2 and prove it with a test that drives the SWEEP end to end:
a conditional commitment from four months ago, satisfied by today's graph, emitting
condition_satisfied with BOTH spans.
```

---

## ⚠️ L2.3.5 · Cross Resource

### L2.3.5-U1 · Contract ↔ spend correlation

**WHAT** — Links a contract to the money that actually moved against it:
`correlate_contract_spend(contracts, spend_events, *, eval_time) -> tuple[ContractSpendLink, ...]`.

**WHY** — Doc 03's component map names the gap exactly: *"`lift_companies_to_their_deals`; **no
contract↔spend**."* The lift is a correlation between a company and its deal; nothing joins a
contract to invoices, payments or committed spend.

Without it, three of Globe's Admin surfaces have no substrate — renewal exposure, a vendor
consuming more than its contract, and spend continuing on a cancelled agreement — and `L2.6.1`'s
`vendor_renewal_unowned` pattern can match on value while having no idea what has actually been
paid.

**WHERE** — `genios_engine/context/correlation_resource.py`
**WHEN — proposed** — X7 (**A-6**).

**HOW** — deterministic joins only; no model in this unit:

```
1. RESOLVE   both sides resolve through the identity cascade to the same vendor node.
             An unresolved side produces NO link.
2. JOIN      ranked, strongest first:
               a. an explicit contract reference on the spend record        -> exact
               b. same vendor node AND spend date inside the contract term  -> strong
               c. same vendor node, no term overlap                         -> UNATTRIBUTED
3. AGGREGATE per contract, integer minor units, per currency, never converted:
               committed_minor_units   from the contract
               spent_minor_units       sum of exact + strong links in the term
               unattributed_minor_units    kept SEPARATE, never folded into spent
4. FACTS     write contract.spend_to_date and contract.unattributed_spend as derived facts.
             Absent coverage for a spend source -> the fact is UNKNOWN, never 0 (Law 4).
5. OBSERVE   spend after a contract's end date -> `spend_past_term` observation.
             This is a finding, not an error.
```

**Unattributed spend is reported, never distributed.** Splitting an unmatched invoice across
contracts by ratio invents a number, and that number would flow into renewal exposure.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Unattributed spend folded into `spent` | overstated consumption drives a false renewal alarm | held in its own field; the acceptance suite asserts the two never sum in this module |
| Currencies summed | a meaningless total | aggregation is per currency; a multi-currency contract returns per-currency totals, not one |
| No spend source connected, `spent` written as 0 | *"this vendor stopped billing"* invented out of a missing connector | Law 4 — no coverage means `UNKNOWN`; `L2.5.5-U1` types it `UNKNOWABLE` |
| Both sides unresolved, link guessed | spend attributed to the wrong vendor | step 1 refuses; an unresolved side is not a weak link, it is no link |

**ACCEPTANCE**
```
pytest tests/context/test_correlation_resource.py -q
# a spend record carrying a contract reference -> exact link
# same vendor, date inside the term, no reference -> strong link
# same vendor, date outside every term -> UNATTRIBUTED, and not counted in spent
# no spend connector for the org -> contract.spend_to_date is UNKNOWN, not 0
# spend dated after the contract end -> spend_past_term observation
# spend in two currencies -> two per-currency totals, no conversion anywhere
# an unresolved vendor on either side -> no link written
```

---

## ⚠️ L2.3.6 · Cross Domain

### L2.3.6-U1 · Domain carry verification

**WHAT** — Records, on every correlation, **which domain was chosen, by what origin rank, and
whether that origin was verified** — and degrades an unverified carry instead of propagating it
silently: `verify_domain_carry(hints, chosen, *, eval_time) -> DomainCarry`.

**WHY** — Doc 03's component map says only *"`resolve_domain`; degraded-carry unverified"*. That
phrase is the whole spec and it is genuinely terse — **this unit is the reading this file
assumes, and the owner should confirm it (see A-6).**

The reading is grounded in the code. `resolve_domain` (`correlation.py:138`) ranks hints by origin
— `scope`/`source`/`prior` at 0, `model` at 1, `keyword` at 2, unrecognised at `_UNRANKED = 2` —
and returns the winning domain **with the rank discarded**. Downstream, that domain becomes the
correlation key, `context_situations.domain`, and the hint Layer 3 resolves a corpus folder from
(the module says so at lines 156-159). So a domain chosen from a bare keyword match is
indistinguishable from one declared by scope, and a wrong choice routes a situation to the wrong
domain expertise with no trace of how it was picked.

**WHERE** — `genios_engine/context/correlation.py` (`resolve_domain` gains a sibling that returns
the carry; the existing signature stays for its callers)
**WHEN — proposed** — X7 (**A-6**).

**HOW**

```
DomainCarry(domain, origin, rank, verified, degraded, competing_domains)

verified   = the winning hint's origin is scope | source | prior          (rank 0)
degraded   = the winner is `model` or `keyword` or unrecognised, OR two hints of DIFFERENT
             domains tied at the same rank
competing  = every other distinct domain among the hints, kept, never discarded

CONSEQUENCES, and they are the point:
  * degraded=True is written onto the situation and reaches the BSO metadata, so L3 can
    see that its corpus folder was chosen from a keyword.
  * degraded=True lowers no score by itself. It is a FACT about provenance. L2.5.1-U1's
    analytic axis and L2.5.8-U1's floor decide what to do with it.
  * an unrecognised origin stays at _UNRANKED and is recorded BY NAME, so a typo in an
    origin string is visible rather than silently ranking beside a keyword.
```

**`resolve_domain`'s behaviour must not change.** It is the correlation key and doc 09's
must-not-regress list protects the anchor path around it. This unit **adds** provenance; it does
not re-decide.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| The chosen domain changes | every existing correlation key moves and situations re-key | this unit returns provenance only; a regression test pins `resolve_domain`'s output over a fixture set |
| `degraded` used as a score | provenance quietly becomes ranking, which is Layer 4's job | it is a boolean; the acceptance suite asserts no arithmetic path reads it |
| Competing domains discarded | the tie that caused a misroute is unrecoverable at review time | `competing_domains` is retained on the carry and stored |
| A typo'd origin string ranks as a keyword | a mislabelled hint is invisible | unrecognised origins are recorded by name and counted |

**ACCEPTANCE**
```
pytest tests/context/test_correlation.py -q
# a scope-origin hint -> verified=True, degraded=False
# a keyword-only hint -> verified=False, degraded=True, and the domain is UNCHANGED
# two different domains tied at rank 0 -> degraded=True, both in competing_domains
# an unrecognised origin -> recorded by name, rank _UNRANKED, degraded=True
# resolve_domain's return value is byte-identical to today's over the fixture corpus
# no arithmetic reads `degraded` (source-level assertion)
```

---

## ❌ L2.3.7 · Cross Organization — acceptance for an existing spec (see **A-8**)

### L2.3.7-U1 · Same party, different context

Doc 03 writes this unit's **WHAT / WHY / HOW** and stops. Doc 03's group gate then makes it a
**safety gate at zero leaks**. The missing half is supplied here; nothing in the doc's three
sentences is changed.

**WHERE** — `genios_engine/context/org_context.py`, built on `c63def1`'s subject-exclusion
visibility (doc 03 names the commit)
**WHEN** — X7.

**HOW — restated from doc 03, as an ordered rule:**

```
1. ONE identity. The party is merged as a single node, through the existing cascade.
2. N context-scoped ROLE EDGES: (party) --acts_as[vendor|customer|investor|advisor]--> (org)
   Each edge carries the context and the visibility scope it was learned under.
3. A FACT is stored against (party, context), never against the party alone.
4. A read is ALWAYS context-qualified. There is no unqualified read of a party's facts.
5. Cross-context surfacing requires visibility to permit it EXPLICITLY. The default is deny.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A fact learned in the vendor context surfaces in the investor context | **a data leak between customer relationships — the blocker class doc 03 says stops four customer types being onboarded** | default-deny cross-context reads; the negative test is written first |
| Identity split to avoid the leak | two half-correct parties, the exact failure `identity.py` was built to prevent | identity merges; contexts do not — one node, N role edges |
| An unqualified read added later for convenience | the guarantee erodes silently | there is no unqualified read in the API surface; the acceptance suite asserts the signature requires a context |
| A situation spanning two contexts | a card mixing a vendor negotiation with an investor update | correlation anchors are context-scoped; a cross-context anchor is refused, not merged |

**ACCEPTANCE**
```
pytest tests/context/test_org_context.py -q
# THE NEGATIVE CASE FIRST: a fact written in context A is NOT returned by a read in context B
# the same party in two contexts -> one node, two acts_as edges
# a read with no context argument -> TypeError (there is no unqualified read)
# visibility explicitly permitting a cross-context read -> the fact IS returned, and the
#   permission that allowed it is named in the result
# a correlation anchor spanning two contexts -> refused, two situations, not one
# 0 leaks over the group-gate fixture corpus
```

---

# L2.5 · Context Quality Engine

## ✅ L2.5.1 · Confidence Calculation — the one addition (see **A-4**)

### L2.5.1-U1 · The `analytic_score` axis

**WHAT** — A sixth confidence axis measuring the quality of the **comparative** inputs an
importance number leaned on: `analytic_score(trends, cohort_positions, anomalies) -> tuple[int,
str]` — the score and the weakest reason.

**WHY** — Doc 05 asks for it once and doc 07 asks for it again (**A-4**); doc 08's
`confidence_vector` says *"6 axes, not a scalar"* and the code has five. The gap is real: after
`L2.7.4-U1` lands, a situation's importance can be raised +1000 by a cohort position computed
over 5 members and +1000 by a trend with `trend_confidence_bp` of exactly 5000. Nothing downstream
can currently tell that from a situation whose modifiers came from a 200-member cohort and eight
periods of history. **Same importance, wildly different certainty, and no axis carries it.**

Doc 05 states the requirement in one sentence: *"A situation whose importance leaned on a
5-member cohort should be visibly less certain than one that leaned on 200."*

**WHERE** — `genios_engine/context/situations.py`, beside the other five axes
**WHEN** — X5, with `L2.7.4-U1`. It measures that unit's inputs and must land with it.

**HOW** — the weakest-link composition the other axes already use, integer only:

```
inputs, each capped, each with a floor:
  population        the SMALLEST population_size across the cohort positions used
  trend_confidence  the LOWEST trend_confidence_bp across the trends used
  history_depth     the FEWEST point_count across those trends
  anomaly_periods   the FEWEST periods_used across the anomalies used

score = the MINIMUM of the four sub-scores, not their mean.
  Same reason `score_situation` reports a `weakest` field: an average hides the one thin
  input that the importance actually leaned on.

NO analytic input used at all -> the axis is NOT 0.
  0 would say "the comparative evidence is bad". The truth is "no comparison was made",
  which is a different fact and must not depress the vector. It returns the same
  not-applicable sentinel `coverage_score` uses for an unregistered domain
  (`COVERAGE_UNKNOWN`, situations.py:181), read through `coverage_is_known`.
```

**Scale — see A-7.** The five existing axes are int percent on `SCORE_MAX = 100`. This one joins
them on that scale rather than introducing basis points into a vector that is not on them. If the
vector migrates to bp, all six migrate together; this unit does not fork the scale.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Averaged instead of minimised | one thin cohort hides behind three strong trends, and the axis says "certain" about the input the importance actually used | minimum, with the weakest reason returned beside it |
| "No analytic input" scored 0 | every situation predating L2.4 looks untrustworthy, and the vector's other five axes get overridden by an absence | the not-applicable sentinel, read through `coverage_is_known` |
| The vector collapsed to a scalar downstream | doc 09's must-not-regress item 3 broken, and Globe's named correctness defect reintroduced | the axis is added to the vector, and the existing scalar-collapse test extends to six |
| Axis lands after L2.7.4 | modifiers fire for a release with no way to see how thin their inputs were | it is scheduled in X5 **with** L2.7.4, not after |

**ACCEPTANCE**
```
pytest tests/context/test_situation_confidence.py -q
# a 200-member cohort + 8-point trend -> a materially higher axis than a 5-member cohort
#   + 4-point trend, with the same importance_bp
# three strong trends and one 5-member cohort -> the axis reports the COHORT as weakest
# no trends, no cohorts, no anomalies -> not-applicable, and coverage_is_known() is False
#   for it; it does NOT read as 0
# the confidence vector has 6 axes and score_situation still reports a `weakest`
# integer only: no float in the axis path (source-grep)
```

---

## ⚠️ L2.5.3 · Conflict Detection

### L2.5.3-U1 · Cross-time conflict detection

**WHAT** — Finds contradictions that only exist **across events over time**, which L1 structurally
cannot see: `detect_cross_time_conflicts(claims_by_subject, *, eval_time) -> tuple[Discrepancy,
...]`.

**WHY** — Doc 05 sets out the split and writes no unit for L2's half:

```
L1 conflict:  two claims in one document group   ($84K email vs $74K attached PDF)
L2 conflict:  two claims across time             (March contract vs September amendment)
```

L1 cannot see the second: the claims are in different thread groups and L1 v2's `L1.5.5` runs
inside one. The doc gives the algorithm in two sentences — group by `subject_key` (ALG-22, reused)
across the whole graph, resolve by authority then by recency **within** the same authority rank —
and leaves both the failure modes and the acceptance unwritten. That is the shape of the L1.5.4
gap that needed rework.

It also feeds two things directly: `consistency_score` (`situations.py:143`, which already reads
`discrepancies`), and `L2.7.4-U1` modifier 3e, which raises importance by 700 for an unresolved
material conflict.

**WHERE** — `genios_engine/context/quality/conflict_time.py`
**WHEN** — X6.

**HOW**

```
1. GROUP     by subject_key across the WHOLE graph, not the thread. Reuse ALG-22's key
             function; a second implementation would silently group differently.
2. PAIR      within a subject, compare claims that assert the same field with different
             values. Same value = corroboration, not conflict — it is not even examined.
3. RESOLVE   authority rank first (ALG-14: signed document > mail body).
             ONLY WITHIN an equal rank does recency decide.
             So an amendment beats an original when BOTH are signed documents, and a later
             email never beats an earlier signed contract.
4. MATERIAL  a conflict is material when the field is one a decision depends on — value,
             date, party, obligation. A changed spelling is not a discrepancy.
5. EMIT      write to `discrepancies`, which already feeds consistency_score. Both claims and
             both evidence spans are retained. L2 SURFACES contradictions; it does not
             silently pick a winner and hide the loser.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Recency applied across authority ranks | a casual email overrides a signed contract — the single most damaging resolution error available here | rank is compared first and unconditionally; recency is scoped inside a rank |
| A second `subject_key` implementation | claims group differently from L1 and conflicts are missed or invented | ALG-22's function is imported, not reimplemented; the acceptance suite asserts the import |
| Every trivial difference emitted | `consistency_score` collapses for every org and every situation looks contradictory | the materiality test at step 4, on a declared field list |
| A winner picked and the loser dropped | the card shows one number and cannot show the other, which is the whole value of a conflict | both claims are retained on the discrepancy row |
| Re-emitted every drain | duplicate rows and a growing table | the discrepancy key is (subject_key, field, claim_a, claim_b); re-detection updates, never inserts |

**ACCEPTANCE**
```
pytest tests/context/quality/test_conflict_time.py -q
# a March contract and a September amendment, both signed -> conflict, amendment wins on recency
# a March signed contract and a September email -> the CONTRACT wins; recency does not apply
# two claims with the same value across time -> no conflict, no row
# a spelling difference on a non-material field -> no conflict
# the same conflict detected on two drains -> one row, updated
# both claims and both evidence spans are present on the emitted discrepancy
# the subject_key function is imported from L1, not redefined (source-level assertion)
```

---

## ❌ L2.5.5 · Missing Context Detection

### L2.5.5-U2 · The expectation map registry

**WHAT** — The declaration of what a well-formed situation of each type should carry, and the
validator that keeps it honest: `expectations_for(situation_type, version) -> ExpectationMap`.

**WHY** — `L2.5.5-U1` says *"Expectation maps are declared per domain"* and *"live in code with a
version. Not inferred"*, and specs the cascade that consumes them without specifying the maps
themselves. The consequence is concrete and already visible in this codebase: `coverage_score`
(`situations.py:189`) takes `expected: dict[str, str]` and, in its own comment at lines 196-203,
records that scoring an empty expectation as 100 *"let 34 of one org's 73 situations report
`missing=[]` and full coverage"* — a green light *"earned by ignorance"*.

So the map is not a lookup table. **It is the thing that decides whether absence is a finding or
noise**, it is what `L2.6.1-U1`'s `{kind: absence}` conditions resolve against, and it is the
input `L2.5.8-U1` gates publication on. Unspecified, each of those three derives its own.

**WHERE** — `genios_engine/context/quality/expectations.py`
**WHEN** — X6, before `L2.5.5-U1` is wired (the cascade cannot run without a map).

**HOW**

```
an ExpectationMap entry, per situation type, per version:
  field            the registered fact path             "deal.value", "contract.owner"
  label            plain language, for the card         "deal value"
  domain           which coverage domain could carry it "crm" | "mail" | "billing" | ...
  expected_when    a guard, so a map is not blindly universal:
                     always | when_fact_present(<field>) | when_stage_in(<...>)
  finding_if_absent  True  -> GENUINELY_ABSENT is a FINDING ("no owner on this work item")
                     False -> absence is merely incomplete, not interesting

RULES:
  * versioned. `expectation_version` is stored on every situation scored against it, so a
    coverage number from March is comparable with September's or is knowably not.
  * START MINIMAL. Doc 05's own mitigation: "maps are per situation type and start minimal"
    because "everything is incomplete, nothing publishes" is the failure of a broad map.
  * every `field` must exist in the registered fact vocabulary at REGISTRATION time —
    the same discipline as pattern conditions. A map naming a field nobody writes produces a
    permanent GENUINELY_ABSENT and a permanent false finding.
  * every `domain` must be a real coverage domain, or the absence can never be typed
    UNKNOWABLE and every gap in it reads as a finding.
  * an unregistered situation type returns NO map, and no map is the third state
    coverage_score already has — never an empty map, which reads as "we expect nothing".
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Empty map read as "nothing expected" | the `situations.py:196-203` failure repeats: full coverage earned by ignorance | absent map is a distinct state (`COVERAGE_UNKNOWN`), not an empty dict |
| A field nobody writes | a permanent false finding on every situation of that type | registration-time validation against the fact vocabulary |
| A domain that maps to no connector | absence never types `UNKNOWABLE`, and a missing connector produces confident findings | registration-time validation against the coverage domains |
| Map broadened to look thorough | nothing publishes, and the held count spikes | maps start minimal; a version that raises the field count is reviewed against the held-situation count before activation |
| Version not stored | coverage numbers across time are incomparable | `expectation_version` on every scored situation |

**ACCEPTANCE**
```
pytest tests/context/quality/test_expectations.py -q
# a registered situation type -> its map, with every field in the fact vocabulary
# an unregistered situation type -> NO map (distinct from an empty map), and coverage_score
#   reports COVERAGE_UNKNOWN rather than 100
# a map naming an unregistered fact field -> raises at REGISTRATION, not at evaluation
# a map naming an unknown coverage domain -> raises at REGISTRATION
# expected_when=when_stage_in([...]) -> the field is not expected outside those stages
# finding_if_absent=False -> a GENUINELY_ABSENT field lowers coverage and emits no finding
# expectation_version travels onto every situation scored against the map
```

**WIRED AT** — `coverage_score(present_fields, expected)` at `situations.py:189`, which today has
**nobody supplying `expected`**. The wiring test is the one where `refresh_situations` produces a
situation whose `missing` list came from a registered map — not a test that calls
`expectations_for` and passes the result to `coverage_score` by hand.

---

## ⚠️ L2.5.6 · Evidence Aggregation

### L2.5.6-U1 · Evidence aggregation as a named component

**WHAT** — One function that assembles a situation's evidence set from every source that carries
some: `aggregate_evidence(l1_spans, correlation_refs, observations, *, limit) -> EvidenceSet`.

**WHY** — Doc 05's map says *"flows, not a named component"*, which is an accurate description of
the code: `situation_bso.py` assembles evidence inline (`gather_evidence_and_signals` at line 120,
then the merge at lines 456-459, where L1 spans lead, `reconstructed` receipts are dropped and the
list is truncated at `MAX_EVIDENCE`). That logic is correct and it is **invisible** — it lives in
the middle of the publisher, is exercised by no test of its own, and `L2.7.8-U1` is about to
change the publisher around it.

Naming it is not tidying. Three separate specs assert something about evidence — doc 07's
publisher gate (*"every published BSO carries >= 1 verified evidence span"*), `L2.6.2-U1`'s
per-condition evidence, and `L2.5.8-U1`'s floor — and none of them can be tested against a
function that does not exist.

**WHERE** — `genios_engine/context/quality/evidence.py`; `situation_bso.py` calls it
**WHEN — proposed** — X6, immediately before `L2.7.8-U1` rewrites the publisher (**A-6**).

**HOW** — extraction of existing behaviour, with the ordering made explicit:

```
1. RANK    L1's verified spans first — they are span-validated verbatim quotes.
           Then correlation graph refs, as context.
           Then observation refs.
2. DROP    the synthetic `reconstructed` receipt, whenever a real span exists. It exists only
           so the BSO contract's non-empty rule holds when there is nothing real to show.
3. DEDUPE  by the span key (source ref + offsets), keeping the highest-ranked copy.
4. CAP     at MAX_EVIDENCE, and record `evidence_truncated` + the true count. A truncated set
           that does not say it was truncated is how "only 3 sources" becomes a wrong claim.
5. REPORT  verified_span_count, source_count and distinct_source_systems — the three numbers
           `evidence_score` (situations.py:102) and the publisher gate both need.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Truncation invisible | a card says "3 pieces of evidence" when there were 40 | `evidence_truncated` and the true count travel with the set |
| The `reconstructed` receipt kept beside real spans | a synthetic receipt is shown to a user as evidence | dropped whenever a real span exists — existing behaviour, now testable |
| Ordering changes silently in a publisher refactor | the card's lead quote changes with no diff to explain it | the ordering is this unit's, with its own test |
| Deduped across different offsets | two genuinely different quotes from one email collapse to one | the span key includes offsets |

**ACCEPTANCE**
```
pytest tests/context/quality/test_evidence.py -q
# L1 verified spans lead, correlation refs follow, observations last
# a reconstructed receipt beside a real span -> dropped
# a reconstructed receipt with NO real span -> kept (the contract requires >= 1)
# the same span twice from two paths -> one entry, highest rank kept
# two quotes from one email at different offsets -> two entries
# 40 candidates with MAX_EVIDENCE=10 -> 10 entries, evidence_truncated=True, true_count=40
# verified_span_count counts only spans that verify
```

---

## ⚠️ L2.5.7 · Context Completeness

### L2.5.7-U1 · Completeness beyond support

**WHAT** — Situation-type-general completeness: `completeness(situation, expectation_map,
missing_facts) -> Completeness`, replacing the support-only implementation.

**WHY** — Doc 05's map: *"`support_situations` only"*. `support_situations.py` is 1,608 lines and
the completeness logic in it is written against support's own fields. Every other situation type —
renewal, commitment, meeting, deal, founder-bottleneck — either has no completeness or borrows
support's.

This matters at exactly one place, and it is a gate: `L2.5.8-U1` holds a situation below a
completeness floor. A floor that only knows how to measure support situations either passes
everything else unexamined or holds everything else forever.

**WHERE** — `genios_engine/context/quality/completeness.py`
**WHEN — proposed** — X6, with `L2.5.5-U2` and `L2.5.8-U1` (**A-6**).

**HOW**

```
completeness = f(expectation map, typed absences, evidence set) and NOTHING type-specific:

  expected_count        from L2.5.5-U2's map for this situation type
  present_count         fields the situation actually carries
  unknowable_count      absences typed UNKNOWABLE by L2.5.5-U1
  genuinely_absent      absences typed GENUINELY_ABSENT

  covered   = present_count
  knowable  = expected_count - unknowable_count       # what we could ever have known
  score     = COVERAGE_UNKNOWN            if knowable == 0     (we cannot judge this)
            = the existing coverage_score computation over `knowable`, otherwise

THE RULE THAT MAKES IT HONEST: a field nobody could have seen is removed from the
DENOMINATOR, not counted as missing. Counting it as missing punishes an org for not
connecting a source; counting it as present invents coverage. Removing it says
"of what we could know, we know this much" — and `knowable == 0` says "we could know
nothing here", which is a different sentence from "we know nothing".
```

**Scale — see A-7.** This unit reads and returns the existing percent scale and its
`COVERAGE_UNKNOWN` sentinel unchanged; it does not fork the vector onto basis points.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| `UNKNOWABLE` counted as missing | an org with three connectors looks permanently incomplete, and `L2.5.8-U1` holds everything it produces | removed from the denominator; the acceptance suite pins the arithmetic |
| `UNKNOWABLE` counted as present | invented coverage, and a confident card built on a missing connector | it is in neither numerator nor denominator |
| `knowable == 0` scored 0 | a whole domain reads as broken because nothing in it is connected | returns `COVERAGE_UNKNOWN`, read through `coverage_is_known` |
| Support's implementation left in place beside this one | two completeness numbers that disagree, and no way to know which a gate read | `support_situations` calls this unit; the acceptance suite asserts one implementation |

**ACCEPTANCE**
```
pytest tests/context/quality/test_completeness.py -q
# 5 expected, 3 present, 0 unknowable -> the same number today's coverage_score returns
# 5 expected, 3 present, 2 unknowable -> scored over 3 knowable, NOT over 5
# 5 expected, 0 present, 5 unknowable -> COVERAGE_UNKNOWN, and coverage_is_known() is False
# a renewal situation and a support situation with identical shapes -> identical scores
# support_situations produces its completeness through THIS function (source-level assertion)
```

---

## ❌ L2.5.8 · Context Validation

### L2.5.8-U1 · The publication floor gate

**WHAT** — The last check before a candidate becomes a published situation: `admit(candidate,
confidence_vector, missing_facts, *, floors) -> Admission` — `PUBLISH` or `HELD` with the axis
that held it.

**WHY** — Doc 05 gives this component a WHAT, a HOW and an ACCEPTANCE and **no unit heading**, so
the ledger never counted it and no wave owns it. It is the enforcement point for the group's own
law — *"Most damaging false positives originate here, not at L4"* — and for the rule
`L2.5.5-U1` states but cannot itself enforce: *"if the situation depends on an `UNKNOWABLE` fact,
it BLOCKS publication rather than emitting a hedged card."*

Doc 05 is equally clear about the second half, and it is the half that usually gets dropped:
*"the count of held situations is surfaced, because hiding that things were filtered is how a
system loses trust."*

**WHERE** — `genios_engine/context/quality/validation.py`, called by the publisher
(`L2.7.8-U1`) before it emits
**WHEN** — X6.

**HOW** — deterministic, ordered, and every refusal names its reason:

```
1. DEPENDENCY BLOCK   the situation's type declares which expected facts it DEPENDS on.
                      Any dependency typed UNKNOWABLE -> HELD(reason=UNKNOWABLE_DEPENDENCY).
                      This precedes every score check: a hedged card is not a lesser card,
                      it is a card built on something we cannot see.
2. FLOOR CHECK        each confidence axis against its declared floor. Below any floor ->
                      HELD(reason=<axis>_below_floor). The axis is NAMED, never "low confidence".
3. EVIDENCE FLOOR     zero verified spans -> HELD(reason=NO_VERIFIED_EVIDENCE). Doc 07's
                      publisher gate requires >= 1 on every published BSO; this is where
                      that becomes true rather than hoped for.
4. HOLD               a HELD candidate is STORED, not discarded, with its reason and the
                      inputs that held it. It is re-evaluated on the next drain and
                      PUBLISHES BY ITSELF when new evidence lifts it — no human action.
5. SURFACE            held_count by reason is queryable. Filtering nobody can see is
                      indistinguishable from a system that found nothing.
```

**Floors are declared data, versioned, per situation type** — not constants in the function. A
floor change is reviewable and its effect on the held count is measurable before activation.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A held candidate discarded | evidence arrives later and the situation is gone; the system silently lost a real finding | HELD candidates are stored and re-evaluated every drain |
| Held candidates never re-published | a permanent shadow backlog that looks like nothing is happening | step 4 re-evaluates unconditionally; the acceptance suite proves a lift-and-publish |
| Held count hidden | the group law's own trust argument is broken, and nobody can tell suppression from silence | `held_count` by reason is queryable, and the H6 gate reads it |
| Floors hardcoded | a threshold change is a code change nobody can review or measure | floors are versioned data, stored with the admission |
| Score check before the dependency check | a situation built on an `UNKNOWABLE` fact publishes because its evidence score is high | the order is fixed and tested; the dependency block is first |

**ACCEPTANCE**
```
pytest tests/context/quality/test_validation.py -q
# a candidate depending on an UNKNOWABLE fact -> HELD(UNKNOWABLE_DEPENDENCY), even with
#   every confidence axis at maximum
# a candidate below the freshness floor -> HELD, reason names FRESHNESS, not "low confidence"
# zero verified evidence spans -> HELD(NO_VERIFIED_EVIDENCE)
# a HELD candidate is stored, and the same candidate with new evidence PUBLISHES on the next
#   drain with no human action
# held_count by reason is queryable and non-zero after the rows above
# floors come from versioned data: changing the data changes the outcome with no code change
# nothing is ever deleted by this unit (source-level: no DELETE in the module)
```

**REVERSE PROMPT**
```
TASK: Build the publication floor gate. This is where L2 stops shipping confidently-wrong cards.
FILE: genios_engine/context/quality/validation.py

THE GROUP LAW: "Most damaging false positives originate here, not at L4." A card that is
confidently wrong is almost always a quality failure wearing a reasoning failure's clothes.

PREREQUISITES: L2.5.5-U1 (typed absence), L2.5.5-U2 (expectation maps), L2.5.1-U1 (the 6-axis
vector). Without typed absence this gate cannot tell "we looked and there is nothing" from
"we cannot see".

IMPLEMENT:
  def admit(candidate, confidence_vector, missing_facts, *, floors) -> Admission   # PURE

ALGORITHM: the 5 ordered steps in L2.5.8-U1.

HARD RULES:
1. THE DEPENDENCY BLOCK RUNS FIRST, before any score. A situation depending on an UNKNOWABLE
   fact is HELD however strong its other axes are. A hedged card is not a lesser card.
2. HELD IS NOT DISCARDED. Store the candidate, its reason and the inputs that held it. It
   re-evaluates every drain and publishes ITSELF when evidence lifts it. Nothing is deleted.
3. NAME THE AXIS. "low confidence" is not a reason. The reason names which floor, and the
   values that failed it, so a human can argue with it.
4. SURFACE THE HELD COUNT by reason. Doc 05: hiding that things were filtered is how a system
   loses trust. The H6 gate reads this number.
5. FLOORS ARE VERSIONED DATA, not constants in the function.
6. PURE. floors, vector and missing_facts are injected. No clock, no DB read inside.
7. Integer comparisons only. No float in the gate path.

TEST tests/context/quality/test_validation.py — every row in the L2.5.8-U1 ACCEPTANCE list.
WIRE IT into the publisher (L2.7.8-U1) BEFORE the BSO is emitted, and prove the wiring with a
test that drives the publisher: a below-floor candidate produces NO BusinessSituationObject
and one held row.
```

---

# L2.6 · Situation Candidate Generator

## ⚠️ L2.6.1 · Pattern Matcher

### L2.6.1-U2 · The pattern evaluator

**WHAT** — `match(pattern, graph_slice, *, eval_time) -> MatchResult | None`: the pure function
that decides whether a declared pattern holds right now, and returns the evidence for **each**
condition.

**WHY** — `L2.6.1-U1` specifies the registry — the schema, registration-time validation, the
`@`-reference resolution. Its reverse prompt names two files, `registry.py` **and** `matcher.py`,
and specs only the first. They are two public callables with different properties: the registry is
a declaration validated once at registration; the evaluator is a pure function run over every
candidate slice on every drain, and it is the one whose performance and determinism decide whether
patterns can replace anchor-based detection at all.

Doc 09's H8 gate asks for *"a pattern-matched situation with per-condition evidence"* on a real
tenant. Per-condition evidence is produced here, not in the registry.

**WHERE** — `genios_engine/context/patterns/matcher.py`
**WHEN** — X6, with `L2.6.1-U1`.

**HOW**

```
match(pattern, graph_slice, *, eval_time):
  1. ANCHOR       the slice's anchor must satisfy pattern.anchor.node_type, or return None
                  immediately. This is the cheap rejection and it runs first.
  2. RESOLVE      every @-reference (@authority_threshold, @anchor) against the slice at
                  eval_time — never against a constant, never against a clock.
  3. REQUIRED     evaluate every `conditions` entry. ALL must hold. Short-circuit on the
                  first failure, but record WHICH one failed for the fire-rate report.
  4. EVIDENCE     each satisfied condition records the fact / edge / observation / absence /
                  trend / cohort / anomaly object that satisfied it. A condition satisfied
                  with no recoverable evidence object is a FAILED condition — "this fired
                  because of these five facts" is the contract, and an unevidenced condition
                  breaks it.
  5. OPTIONAL     evaluate `optional_signals`. Each satisfied one contributes its declared
                  weight_bp to match_strength_bp. They never gate the fire.
  6. RETURN       MatchResult(pattern_id, pattern_version, situation_type, matched_nodes,
                              matched_edges, per_condition_evidence, match_strength_bp,
                              eval_time)

ABSENCE CONDITIONS — the rule that inverts the whole system if it is written backwards:
  GENUINELY_ABSENT satisfies an absence condition.
  UNKNOWABLE does NOT.  STALE does NOT.  NOT_EXPECTED does NOT.
  Getting this backwards produces confident findings out of missing connectors, which is
  the exact failure L2.5.5 exists to prevent.

TREND / COHORT / ANOMALY conditions carry their own floors, and the floors live with the
condition kind, not with each pattern: trend requires trend_confidence_bp >= 5000, cohort
requires population_size >= 5 (Law 2), anomaly requires periods_used >= 6.
```

**Determinism is a property of this function, and it is testable.** The same graph slice and the
same `eval_time` must produce a byte-identical `MatchResult` — same order of matched nodes, same
order of evidence. Ordering that depends on dict iteration or a set is a defect here, because
`L2.7.3`'s clustering and the fire-rate report both diff these results across runs.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| `UNKNOWABLE` satisfies an absence condition | a missing connector becomes a confident finding — the worst output the pattern system can produce | only `GENUINELY_ABSENT` satisfies; the acceptance suite has a row per absence type |
| A condition satisfied with no evidence object | the situation is an assertion, and doc 08's `matched_conditions` is empty where it matters | an unevidenced satisfaction is treated as a failure |
| Non-deterministic ordering | the same reality produces two different results, and clustering sees two situations | matched nodes and evidence are sorted by id; the acceptance suite runs the same slice twice and compares bytes |
| `@`-reference resolved against a constant | "high value" stops meaning this org's threshold | resolution goes through `L2.1.4-U2` at `eval_time`; the suite proves two orgs with different thresholds match differently on the same amount |
| Optional signals gating the fire | a pattern silently requires 7 conditions when it declares 5 | optional signals contribute only to `match_strength_bp`; the suite fires a pattern with zero optional signals satisfied |
| A clock read inside the evaluator | a pattern that fires differently on replay | `eval_time` is a required keyword argument |

**ACCEPTANCE**
```
pytest tests/context/patterns/test_matcher.py -q
# a 5-condition pattern fires only when all 5 hold; 4 of 5 -> None, with the failing
#   condition recorded
# an optional_signal satisfied raises match_strength_bp and is NOT required to fire
# an absence condition: GENUINELY_ABSENT satisfies; UNKNOWABLE, STALE and NOT_EXPECTED do not
# a trend condition with trend_confidence_bp 4000 -> does not satisfy
# a cohort condition with population_size 4 -> does not satisfy
# @authority_threshold: two orgs, different thresholds, same amount -> different outcomes
# every satisfied condition carries an evidence object; one without -> the match fails
# the same slice and eval_time twice -> byte-identical MatchResult
# no datetime.now() in the module (source-grep)
```

**REVERSE PROMPT**
```
TASK: Build the pattern evaluator. The registry declares patterns; this decides whether one
holds, and produces the per-condition evidence that makes a situation explainable.
FILE: genios_engine/context/patterns/matcher.py

PREREQUISITES: L2.6.1-U1 (the registry and its schema), L2.5.5-U1 (typed absence), L2.4.3 /
L2.4.5 / L2.4.8 (trend, cohort, anomaly), L2.1.4-U2 (@authority_threshold resolution).

IMPLEMENT:
  def match(pattern, graph_slice, *, eval_time) -> MatchResult | None      # PURE

ALGORITHM: the 6 ordered steps in L2.6.1-U2.

HARD RULES:
1. GENUINELY_ABSENT satisfies an absence condition. UNKNOWABLE DOES NOT. Write this test
   first. Backwards, it turns every missing connector into a confident finding.
2. PER-CONDITION EVIDENCE IS MANDATORY. A condition satisfied with no recoverable evidence
   object FAILS. "This fired because of these five facts" is the contract with L3.
3. DETERMINISTIC ORDERING. Sort matched nodes and evidence by id. No dict or set iteration
   order in the output. Test byte-equality across two runs.
4. eval_time is a required keyword argument. No datetime.now() anywhere in the module.
5. @-references resolve against the graph at eval_time, never a constant.
6. Optional signals contribute weight_bp to match_strength only. They never gate the fire.
7. Condition-kind floors live with the KIND, not the pattern: trend >= 5000 confidence,
   cohort >= 5 population, anomaly >= 6 periods.
8. PURE. The graph slice is injected. No DB access in this module.

TEST tests/context/patterns/test_matcher.py — every row in the L2.6.1-U2 ACCEPTANCE list.
```

### L2.6.1-U3 · The six seed patterns

**WHAT** — The six registered patterns doc 06 names, as data, with their expected fire rates.

**WHY** — Doc 06's reverse prompt says *"SHIP these patterns first (they are Globe's V1-reachable
surfaces): `commitment_unresolved` · `relationship_going_cold` · `meeting_preparation_gap` ·
`founder_bottleneck` · `condition_now_satisfied` · `vendor_renewal_unowned`"* and specs none of
them. Doc 06's group gate then requires **>= 6 registered patterns** and doc 09's H8 requires a
real pattern-matched situation on a pilot tenant.

**A registry with no entries is the Layer 1 defect at data scope**: registry and matcher both
green, both reachable, and the product detects nothing. These six are what make the wave visible.

Each is also the acceptance test for a different condition kind, which is why they must land
together: `vendor_renewal_unowned` exercises `fact`+`temporal`+`absence`+`edge`,
`relationship_going_cold` exercises `trend`+`cohort`, `founder_bottleneck` exercises
`L2.1.4-U2`'s `sole_approver_count`, `condition_now_satisfied` exercises `L2.3.4`'s
`condition_satisfied` observation.

**WHERE** — `genios_engine/context/patterns/seed/*.yaml`
**WHEN** — X6, after `L2.6.1-U2`.

**HOW** — each pattern declares, in the doc 06 schema:

```
pattern_id · version · domain · anchor · conditions · optional_signals · emits.situation_type
PLUS, and doc 06 requires it of every pattern:
  expected_fire_rate     fires per 100 anchors per 30 days, declared before activation
  owner                  who reviews it when it misfires
  first_evidence         the fixture proving it fires, and the one proving it does not

conditions must be MINIMAL. Doc 06's own failure table: a loose pattern "fires constantly,
becomes noise"; a tight one "never fires". The seed set starts tight and is loosened against
the pilot's fire report, never the other way round.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A seed pattern with no declared fire rate | it activates unmeasured, and doc 06's 10x guard has nothing to compare against | `expected_fire_rate` is required by the schema; registration fails without it |
| Two seed patterns overlapping | three cards for one reality | doc 06's answer: patterns may overlap, situations must not — `L2.7.3-U1` merges by shared entity, and the pair is a required test row |
| A pattern referencing a condition kind that is not yet built | silent non-fire | registration-time validation (`L2.6.1-U1`); a seed pattern for an unbuilt kind is not shipped |
| Shipped with anchor-based detection deleted | no comparison, no way back | doc 06 is explicit: keep the anchor path running alongside, compare fire sets on a pilot for 7 days |

**ACCEPTANCE**
```
pytest tests/context/patterns/test_seed_patterns.py -q
# all six register, and the registry reports >= 6
# each pattern has a POSITIVE fixture that fires and a NEGATIVE fixture that does not
# each declares expected_fire_rate and an owner
# no seed pattern references a condition kind that is not implemented
# the vendor_renewal_unowned fixture and the commitment_unresolved fixture over one shared
#   entity produce two matches and ONE clustered situation
# every seed match carries per-condition evidence for every required condition
```

---

## ⚠️ L2.6.2 · Candidate Builder — acceptance for an existing spec

### L2.6.2-U1 · Candidate Builder

Doc 06 writes three sentences: *"Assembles a match into a provisional object: matched nodes,
matched edges, the evidence that satisfied **each** condition. Per-condition evidence is required —
'this fired because of these five facts' is what makes a situation explainable."* No file, no
failure modes, no acceptance. Supplied here.

**WHERE** — `genios_engine/context/patterns/candidate.py`
**WHEN** — X6.

**HOW**

```
build_candidate(match_result, graph_slice, *, eval_time) -> SituationCandidate

  matched_nodes / matched_edges   carried from the MatchResult, sorted, not re-derived
  per_condition_evidence          carried unchanged. This unit does not re-evaluate a
                                  condition; re-deriving evidence here is how the match and
                                  the candidate come to disagree.
  members                         the events and signals attached to the matched nodes
  provisional_type                match_result.situation_type — provisional because
                                  L2.7.3 clustering may merge this candidate into another
  pattern_id + pattern_version    carried, so the candidate names what produced it
  NO SCORE                        scoring is L2.6.3-U1's. A candidate is not ranked here.
  NO PUBLICATION                  a candidate is not a situation. L2.5.8-U1 admits it.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Evidence re-derived instead of carried | the candidate's explanation disagrees with the match that produced it, and neither is wrong-looking | carried unchanged; the acceptance suite compares object identity/equality with the match's |
| A candidate published directly | the floor gate is bypassed and confidently-wrong cards ship | this module emits no `BusinessSituationObject`; source-level assertion |
| `pattern_version` dropped | a pattern change cannot be traced to the situations it altered | both id and version are required fields |
| A condition with no evidence tolerated here | `L2.6.1-U2`'s guarantee is undone one layer later | a match arriving with an unevidenced condition raises; it should have failed upstream |

**ACCEPTANCE**
```
pytest tests/context/patterns/test_candidate.py -q
# a 5-condition match -> a candidate with 5 per-condition evidence entries
# the evidence entries are equal to the match's, not recomputed (mutate the graph between
#   match and build: the candidate still carries what the match saw)
# pattern_id and pattern_version are present on every candidate
# the candidate carries no score field (source-level assertion)
# a match with an unevidenced condition -> raises
```

---

## ❌ L2.6.3 · Candidate Scorer — acceptance for an existing spec

### L2.6.3-U1 · Candidate Scorer

Doc 06 writes two sentences: *"Match strength (required conditions are binary; `optional_signals`
contribute `weight_bp`) plus quality carry-through from L2.5. **Still not a situation, still not a
decision** — the scorer only decides whether a candidate is worth promoting."* Supplied here.

**WHERE** — `genios_engine/context/patterns/scorer.py`
**WHEN** — X6.

**HOW** — integer basis points, no clock, no model:

```
score_candidate(candidate, quality, *, weights) -> CandidateScore

  match_strength_bp   required conditions are BINARY: all hold, or there is no candidate.
                      They contribute a fixed base. Only optional_signals vary the number,
                      each adding its declared weight_bp, and the sum is CLAMPED at 10000.
  quality_carry       the L2.5 vector, carried through — NOT recomputed and NOT averaged
                      into the strength. Two numbers, kept apart, because "five conditions
                      held" and "we are confident about the facts underneath" are different
                      claims and collapsing them destroys both.
  promote             a boolean against a declared floor. Promotion is not importance:
                      importance is L2.7.4-U1's and composes from L1 signals.

THIS SCORE NEVER REACHES importance_bp. A candidate score that leaked into ranking would
re-introduce a second, incompatible importance scale beside BLG-18's.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| The candidate score used as importance | two importance scales, and BLG-18's stored components stop explaining the number | `CandidateScore` has no `importance_bp` field, and `L2.7.4-U1` reads signals, never this; source-level assertion |
| Quality averaged into match strength | a strong pattern over weak facts scores like a weak pattern over strong facts | the two are separate fields on the result |
| Required conditions weighted | a pattern quietly fires at 4 of 5 conditions | required conditions are binary and cannot contribute a partial score |
| Float in the weight sum | non-reproducible promotion at the floor boundary | integer bp with a clamp; source-grep for float |

**ACCEPTANCE**
```
pytest tests/context/patterns/test_scorer.py -q
# all required conditions hold, zero optional -> the fixed base, exactly
# two optional signals at 1500 and 1000 -> base + 2500, clamped at 10000
# a candidate with a weak quality vector -> same match_strength, different quality_carry
# promote is False below the declared floor and True at it (boundary row)
# CandidateScore has no importance_bp field (source-level assertion)
# integer only: no float in the module (source-grep)
```

---

# L2.7 · Business Situation Engine

## ⚠️ L2.7.2 · Situation Builder + Framing — acceptance for two existing specs

### L2.7.2-U1 · Situation framing (M-6)

Doc 07 specs the HOW, the span constraint and three failure modes, and gives **no ACCEPTANCE
block** — the only M-site in the plan without one, and the one doc 09's H6 gate calls a **hard
fail** at *"M-6 fabricated facts: 0"* and *"M-6 visibility leaks: 0"*. The criteria are supplied
here from that gate; the design is doc 07's and is unchanged.

**ACCEPTANCE**
```
pytest tests/context/test_framing.py -q
# every noun in the headline traces to a supplied member fact; one that does not -> validation
#   fails and the DETERMINISTIC TEMPLATE headline is published instead
# every number in the output is templated: the model's output contains no digits that were
#   not substituted deterministically (assert on the pre-substitution string)
# a framing contradicting a matched pattern condition -> rejected; conditions are authoritative
# a member fact outside the situation's visibility scope is not supplied to the model,
#   and cannot appear in the output — 0 leaks over the fixture corpus
# budget exhausted -> the template headline publishes, and the fallback is LOGGED
# the same situation framed twice with a cached response -> identical output
# the model's output reaches no _bp field anywhere (source-level assertion)
```

### L2.7.2-U2 · Timeline narrative (M-7)

Doc 07 writes two sentences: *"Selects and orders the events that matter and states the shape
('promised in April, silent since June, deadline in twelve days'). Same span constraint.
Chronology stays deterministic; **selection and shape** are the model's contribution."*
Supplied here.

**WHERE** — `genios_engine/context/framing/timeline.py`
**WHEN** — X6, with `L2.7.2-U1`.

**HOW**

```
1. SORT (deterministic)   chronological order is computed, never asked for. The model never
                          orders events; a model-ordered timeline cannot be replayed.
2. SELECT (M-7)           from the sorted events, which ones matter. The model returns event
                          IDS from the supplied set — never event text, never a new event.
3. SHAPE (M-7)            a shape label from a CLOSED set: steady | stalled | accelerating |
                          silent_since | deadline_approaching. Not free prose.
4. RENDER (deterministic) the sentence is templated from the shape label plus the selected
                          events' own dates. Every date and every interval is substituted,
                          never generated.
5. FALLBACK               validation failure or exhausted budget -> the deterministic
                          chronological timeline, unnarrated. A plainer card beats a wrong one.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| The model orders events | a timeline that changes between runs and cannot be replayed | ordering is deterministic; the model only selects from an ordered set |
| An event id not in the supplied set | a fabricated event on the card | returned ids are validated against the supplied set; an unknown id fails the whole narrative |
| An interval generated in prose ("about three months") | a number nobody can check, drifting from the dates | intervals are computed from the selected events and templated in |
| Free-text shape | an unbounded vocabulary nothing downstream can read | closed set, validated |
| Selection drops the event the situation is about | a narrative that omits its own subject | the anchor's own events are always retained regardless of selection |

**ACCEPTANCE**
```
pytest tests/context/test_timeline_narrative.py -q
# chronological order is identical with and without the model (the model cannot reorder)
# a returned event id outside the supplied set -> narrative rejected, fallback published
# a shape label outside the closed set -> rejected
# every interval in the output equals the computed difference between the selected dates
# the anchor's own events are present even when the model does not select them
# budget exhausted -> unnarrated chronological timeline, logged
```

---

## ⚠️ L2.7.3 · Situation Clustering

### L2.7.3-U1 · Deterministic shared-entity clustering (BLG-17)

**WHAT** — The deterministic merge that runs before any judgment: `cluster(candidates, *,
eval_time) -> tuple[Cluster, ...]`, merging candidates that share an entity.

**WHY** — **A-5**: MAP D lists **BLG-17 · Situation clustering · L2.7.3** as a Layer 2 algorithm,
doc 07 marks the component *"✅ deterministic exists"*, and the only spec written for it is
`-U2`, the LLM half, which opens *"Deterministic shared-entity clustering runs first and handles
the clear cases."* The clear-case half — the one that decides most of the outcomes and all of the
cheap ones — has no spec anywhere. This is the spec of record for it.

It is also the mitigation doc 06 relies on twice: *"patterns may overlap, situations must not"*.
With six seed patterns landing in the same wave, this is the only thing standing between the pilot
and doc 06's own *"three cards for one reality"*.

**WHERE** — `genios_engine/context/situations.py` (existing clustering, given a spec and a
version) — **this unit is documentation-and-tests-first: it must not change behaviour without a
recorded reason**
**WHEN** — X6, before `L2.7.3-U2`.

**HOW**

```
1. KEY        each candidate contributes its matched entity node ids.
2. MERGE      candidates sharing >= 1 entity id merge into one cluster — transitively, so
              A~B and B~C yield one cluster of three.
3. GUARD      a shared entity that is the TENANT node or a NON_ANCHORING_ROLE connector
              (correlation.py:159) does NOT merge. This is the same hazard choose_anchors
              documents: `boardy.ai` appearing in 254 threads would fuse the org into one
              cluster, and one card would cover 68 unrelated members.
4. TYPE       a cluster's type is the highest-priority member type, by a declared ladder —
              never the first-seen one, which would make output order-dependent.
5. AMBIGUOUS  candidates sharing NO entity but the same subject label, or sharing only a
              guarded entity, are emitted as an AMBIGUOUS PAIR — the input L2.7.3-U2 judges.
              Today they are simply separate; naming them is what makes M-8 possible.
6. STABLE     cluster ids are derived from the sorted member ids, so the same set of
              candidates yields the same cluster id on every run.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| The tenant node or a connector treated as a shared entity | every situation in the org fuses into one — doc 09 must-not-regress item 4, in a second place | step 3's guard, with the guarded set imported from `correlation.py`, not re-listed |
| Order-dependent cluster type or id | the same reality produces different clusters on two runs, and diffing the shadow path is impossible | type by declared ladder, id from sorted members |
| Transitive merge unbounded | one weak shared entity chains a hundred candidates | merges are transitive only over UNGUARDED entities; cluster size is reported and a cluster above a declared size is flagged, not silently accepted |
| Ambiguous pairs discarded | `L2.7.3-U2` has no input and M-8 never fires | step 5 emits them explicitly |

**ACCEPTANCE**
```
pytest tests/context/test_clustering.py -q
# two candidates sharing one company node -> one cluster
# A~B and B~C -> one cluster of three (transitive)
# two candidates sharing only the tenant node -> two clusters, and one AMBIGUOUS PAIR
# two candidates sharing only a NON_ANCHORING_ROLE node -> two clusters, one ambiguous pair
# the same candidate set in a different input order -> identical cluster ids and types
# a cluster above the declared size -> flagged, and still returned
# behaviour matches the existing implementation over the current fixture corpus, or the
#   difference is recorded in this file with its reason
```

### L2.7.3-U2 · Clustering judgment (M-8) — acceptance for an existing spec

Doc 07 writes three sentences and no acceptance. Supplied here; the design is unchanged.

**ACCEPTANCE**
```
pytest tests/context/test_clustering_judgment.py -q
# a pair the deterministic clustering merges -> zero model calls
# an ambiguous pair judged same_reality=True -> one merged situation, merged_by="model"
#   and the prompt version recorded
# same_reality=False -> two situations, and the pair is not re-judged on the next drain
#   unless its members changed
# the model's output reaches no _bp field and sets no status (source-level assertion)
# budget exhausted -> the pair stays separate, and the fallback is logged
# a pair whose only shared entity is guarded is never merged, whatever the model says
```

---

## ⚠️ L2.7.8 · Situation Publisher

### L2.7.8-U1 · Publishing on `QualifiedEnterpriseSignal` input

**WHAT** — The publisher, rewritten around the QES seam: `publish_situation(situation, signals,
graph_context, *, eval_time) -> BusinessSituationObject | Held`.

**WHY** — Doc 07 gives L2.7.8 a WHAT, a six-row field-mapping table and an ACCEPTANCE block, and
**no unit heading** — so no wave owns it, and it is the single place where every other Layer 2 v2
unit becomes visible to Layer 3. Doc 09's H8 pilot gate reads its output and nothing else.

The evidence half is the part doc 07 calls significant: *"Today a situation's evidence is a list
of event references. In v2 it is a list of span-validated verbatim quotes — so a card can show the
sentence, not just name the email."*

**Note A-1.** Two rows of doc 07's mapping table are already true at HEAD: `signal_ids` and
`evidence` come from `qualified_signals` today (`situation_bso.py:217, 450-459`), and
`importance_bp` already prefers L1's score over the constant. What is **not** true is the rest —
`type` from a pattern match, the analytic metadata, the `confidence_vector`, the floor gate.

**WHERE** — `genios_engine/context/situation_bso.py`
**WHEN** — X8, last. Every unit it composes must be green first.

**HOW** — composition only; this unit computes nothing itself:

```
1. ADMIT        L2.5.8-U1 first. HELD -> return Held(reason), emit NO BusinessSituationObject.
                A situation that should not publish must not be built and then discarded —
                building it is how a held situation leaks through a later code path.
2. COMPOSE      importance_bp        L2.7.4-U1                (not re-derived here)
                confidence_vector    the 6 axes incl. L2.5.1-U1's, never collapsed
                evidence             L2.5.6-U1's set, verified spans leading
                type                 the pattern's emits.situation_type when a pattern
                                     matched; the anchor-derived type otherwise, and
                                     `type_source` says WHICH — the two paths run alongside
                                     for the pilot's 7-day comparison
                pattern_id +
                matched_conditions   from L2.6.2-U1, per-condition evidence intact
                trends / cohort_positions / anomalies   from L2.4
                missing_facts        from L2.5.5-U1
                conflicts            L1 v2's plus L2.5.3-U1's
                coverage_ready       carried from the QES, never re-derived
                importance_components + importance_version   stored, always
3. VALIDATE     the contract's own rules run (they already do): >= 1 evidence, bp-validated,
                sorted unique signal_ids, known schema version.
4. EMIT         one BusinessSituationObject. Layer 3 is its only consumer.
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Publisher recomputes a number a unit already produced | two values for one field, and the stored components stop explaining the score | this unit composes only; the acceptance suite asserts no arithmetic on `_bp` fields in the module |
| A held situation built and then dropped | it leaks through a later path, and doc 05's whole gate is decorative | admission runs first, before construction |
| `confidence_vector` collapsed to a scalar for the contract's convenience | doc 09 must-not-regress item 3 | the vector is a mapping on the BSO; the existing scalar-collapse test extends to it |
| Pattern path replaces the anchor path immediately | no comparison, and no way back if the fire sets differ | both run; `type_source` records which produced the type; doc 06 requires 7 days of pilot comparison |
| Schema bumped non-additively | Layer 3 breaks on an old-shaped object | doc 08: additive only, and the round-trip test proves an old-shaped BSO still constructs |

**ACCEPTANCE**
```
pytest tests/context/test_situation_publisher.py -q
# every published BSO carries >= 1 VERIFIED evidence span (not a reconstructed receipt)
# a below-floor candidate -> Held, and NO BusinessSituationObject is constructed at all
# importance_bp equals L2.7.4-U1's output, and importance_components is populated
# importance_bp is the fallback constant ONLY on the documented no-signal path, and that
#   path logs
# conflicts from L1 v2 arrive in metadata; so do trends and cohort_positions when present
# a pattern-matched situation carries pattern_id and matched_conditions; an anchor-derived
#   one carries type_source="anchor" and no pattern_id
# the confidence vector has 6 axes on the emitted object
# an old-shaped BusinessSituationObject still constructs (additive-only proof)
```

**REVERSE PROMPT**
```
TASK: Publish the BusinessSituationObject on QES input. This is the seam where every Layer 2 v2
unit becomes visible to Layer 3, and doc 09's H8 pilot gate reads nothing else.
FILE: genios_engine/context/situation_bso.py

READ FIRST — the doc is stale here (see A-1). At HEAD this module ALREADY reads L1's score out
of qualified_signals (gather_l1_signals, line 217) and branches over four importance sources at
lines 437-448. Do not "fix" the hardcoded constant; it is already the documented fallback at
line 52. What is missing is everything else in doc 07's mapping table.

IMPLEMENT:
  def publish_situation(situation, signals, graph_context, *, eval_time)
        -> BusinessSituationObject | Held

ALGORITHM: the 4 ordered steps in L2.7.8-U1.

HARD RULES:
1. ADMISSION FIRST (L2.5.8-U1). A held situation is never constructed. Build-then-discard is
   how a held situation leaks through a later path.
2. COMPOSE, NEVER COMPUTE. Every number comes from the unit that owns it. No arithmetic on
   any _bp field in this module.
3. THE CONFIDENCE VECTOR STAYS A VECTOR — 6 axes. Never collapse it to a scalar for the
   contract's convenience. Doc 09 must-not-regress item 3.
4. BOTH TYPE PATHS RUN. Pattern-derived and anchor-derived, with type_source recording which.
   Do not delete the anchor path in this wave; the pilot compares fire sets for 7 days.
5. ADDITIVE SCHEMA ONLY. Bump BUSINESS_SITUATION_VERSION; change no existing field. Prove an
   old-shaped object still constructs.
6. eval_time is a parameter. No clock in this module.

TEST tests/context/test_situation_publisher.py — every row in the L2.7.8-U1 ACCEPTANCE list.
WIRED AT: the drain's situation refresh, not a test harness. The wiring proof is a real
refresh producing a BSO whose evidence is a verified span.
```

### A-24 · ALG-08 proves a quote exists; it does not prove the sender wrote it or that it is unnegated

**Recorded by the H6 gate, which found both of these by attacking the shipped code rather than by
reading it.** Doc 12's cross-cutting rule 5 says to reuse ALG-08 and not to write a second span
validator, and M-4 does. But ALG-08 answers exactly one question — *are these words in this
source?* — and two things it is silent about decide whether the words mean what the claim says.

**WHERE the words are.** Every mail client quotes the thread below the reply. `"all sorted, we
signed yesterday"` is genuinely present in a message whose live text reads *"I don't think this
ever happened, can you confirm?"* — present in the part someone else wrote three weeks ago. The
span verifies, the speaker is our own owner, the band is EXPLICIT_COMPLETION, and the situation
closes on a sentence the sender was arguing against. On a real inbox this is the single most
available route to a false close, and nothing in doc 12's nine cases names it.

**WHETHER the words are negated.** `"we have not signed the MSA yet"` contains `"signed the MSA"`
and contains `"we have not signed"` in full. Both verify. Doc 12 case 1 already makes a
forward-looking modal a hard negative **in deterministic code** rather than trusting the model's
band; a negator four words to the left of the quote is the same class of signal and is more
dangerous, because the sentence it falsifies reads as a completion report to anything matching on
substrings.

**ASSUMED, AND BUILT:** both are refusals `genios_engine/context/lifecycle/textguard.py` makes
after ALG-08 has spoken, wired into `judge.py` step 4b. Both are one-directional — they can turn a
close into a rejection and never the reverse — so the worst either costs is one unnecessary nudge,
which is the cheap error by doc 12's own table. **Neither is applied to `CONTRADICTED`**: a
contradiction is the reopen path, its quote is supposed to carry a negator, and guarding it would
make a wrong close permanent.

**The negator list is restricted to words that negate a VERB OF COMPLETION**, and that restriction
was learned by breaking a golden fixture: an earlier draft carried `nothing`, `none` and
`no longer`, and it refused `vendor_implied_nothing_pending`, because *"nothing pending from our
side"* is how English STATES a completion rather than how it denies one.

### A-25 · The golden set's false-positive rate is measured over answers that mostly concede the case

**Recorded by the H6 gate. This is a statement about what the number means, not a defect.**

`m4_resolution.json` reports 0 bp against a 200 bp ceiling, and that reproduces exactly. But of
its 28 must-not-close fixtures, only FOUR present the hardest shape — verdict `RESOLVED`, band
`EXPLICIT_COMPLETION`, an org-internal sender — and each of those four is caught by a different
named guard (the one-liner rule, the scope check twice, ALG-08). Every other must-not-close
fixture concedes the case in the answer itself: an `INTENT_ONLY` band, an `AMBIGUOUS` band, an
external or machine sender, or a `NOT_RESOLVED` verdict.

`tests/golden/l2/m4_adversarial.json` supplies only the hard shape. Five of its attacks are
guard-provable and all five are refused (two of them only because of **A-24**). **Eight are not**,
and they are committed with a `known_limit` field and a ratchet test so the count cannot grow: a
model that labels plain sarcasm, a forward-looking modal, a conditional, hearsay, or a resolution
of the wrong deliverable as `EXPLICIT_COMPLETION` — while quoting and scoping correctly — closes
the situation. There is no deterministic answer to that. Refusing it would require the code to
re-read the prose and overrule the description, which is the doctrine this unit is built on, read
backwards.

**What this means for the 2% gate.** The measured rate is a true statement about the guards and
not about any model's accuracy, because there is no live-model lane. The residual risk is bounded
by exactly one property — `RESOLVED_BY_STATEMENT` is re-derived every pass and un-resolves on
contradiction — so a wrong close survives only until the next message disputes it.

### A-26 · `may_infer_absent` and `lens_from_epochs` are exported and called by nothing

**Recorded by the H6 gate's wiring audit.** The negative-inference licence seam is wired at both
ends that matter — `absence_metadata` (producer) from `situation_bso.py`, and `read_licence` /
`read_string_set` (consumer) from `packs/compiler/context_adapter.py`. `may_infer_absent`, the
convenience predicate over the same metadata, has no production caller; neither does
`lens_from_epochs`, which replays a past coverage regime. Both are in `__all__`.

Not a broken seam and not a gate failure — the units doc 05 and doc 13 asked for are reached. They
are recorded because "exported, tested, called by nothing" is the exact shape of the defect Layer 1
shipped six times, and a later reader should know these two were counted and found harmless rather
than missed.

### A-27 · M-4 inherits a robot table tuned for the opposite cost function

**Recorded by the H6 gate.** Doc 07's authority table has four rows and the fourth is *automated /
service account — IGNORED ENTIRELY*; doc 12 case 7 is a bot closing a real situation with *"Your
ticket has been resolved"*. `authority.py` implements that row by importing
`capture/gate/rules.is_automated_sender`, which is right by doc 12's cross-cutting rule 5 — one
table, one answer — and it is where the reasoning stops being safe.

**That table is deliberately conservative, and its own docstring says why:** *"`support@`/`hello@`
are a real small business, and over-matching here costs a genuine sender 80% of its authority."*
That is a sound trade for L1's junk gate, where a false positive drops a real email. It is the
WRONG trade here, because M-4's false positive does not cost 80% of a weight — it closes a live
thread, which doc 12 calls the most expensive error in Layer 2.

**Measured:** `no-reply@`, `noreply@`, `do-not-reply@`, `notifications@`, `alerts@` and `notify@`
match. **`workflow@`, `jira@`, `bot@`, `system@`, `automated@` and `support@` do not.** An
automated completion notice from one of those, sent from an address the org has SEATED (so
`runner._internal_emails` calls it us), is weighed at `ROLE_INTERNAL` — and
`EXPLICIT_COMPLETION x 8000 / 10000 = 7200`, over the 7000 close floor. It closes.

**Bounded, but real.** Two things keep it narrow: L1's capture gate already drops `N-03
no_reply_sender` before L2 sees it, so the robots the table DOES know never arrive; and the address
must be an active seat, the owner, or the connected mailbox, which a machine account usually is
not. A shared operational mailbox (`support@`, `billing@`, `ops@`) that both is seated and emits
automated notices is the case that reaches the floor.

**NOT fixed here, on purpose.** The available patch is a second, wider regex inside M-4, and that
is precisely what rule 5 forbids and what the table's docstring warns costs real senders their
authority. The correct fix reads a per-EVENT automation verdict rather than guessing from an
address — `source_events.triage_lane` is already on the row `store.unexamined_messages` selects
from, and feeding it to `gate_decision` alongside the speaker role would answer *"was this message
machine-generated"* instead of *"does this address look like a robot"*. That is the same shape as
**A-20**'s recommendation and belongs with it in one pass over the gate's inputs.

---

## 5. What this file does not close

| # | Still open | Owner |
|---|---|---|
| 1 | `L2.4.7-U2` and `L2.4.8-U2` — the two units L2.4's own component map promises and does not write | L2.4, doc 04 |
| 2 | The thirteen contradictions in §3. Each spec states the reading it assumed; none of them is a decision this file may make | the plan's owner |
| 3 | Wave assignment for the six units marked **WHEN — proposed** (**A-6**) | the plan's owner |
| 4 | Doc 07's stale line references (**A-1**). The specs here are written against HEAD; the plan text is not | the plan's owner |
| 5 | Implementation. Every unit here is a spec, and a spec is green only when a real request path reaches the code it describes — the `WIRED AT` lines and the ACCEPTANCE rows name that path | the build waves |
