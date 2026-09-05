# L1 Contracts — every typed object at the Layer 1 seam

> **Build these first (Wave W0).** Nothing else in Layer 1 compiles until these exist.
> Every one lives in `genios_engine/contracts/`. Contracts may import `platform` and
> stdlib only — never `capture`, never `context`.

---

## Contract inventory

| # | Type | File | Crosses a layer boundary? |
|---|---|---|---|
| C-01 | `EvidenceSpan` | `contracts/evidence.py` | yes (embedded) |
| C-02 | `Money` | `contracts/units.py` | yes (embedded) |
| C-03 | `ResolvedDate` | `contracts/units.py` | yes (embedded) |
| C-04 | `EntityMention` | `contracts/extraction.py` | yes (embedded) |
| C-05 | `Commitment` | `contracts/extraction.py` | yes (embedded) |
| C-06 | `DecisionState` | `contracts/extraction.py` | yes (embedded) |
| C-07 | `Dependency` | `contracts/extraction.py` | yes (embedded) |
| C-08 | `UnclassifiedObservation` | `contracts/extraction.py` | yes (embedded) |
| C-09 | `ExtractionResult` | `contracts/extraction.py` | **internal to L1** |
| C-10 | `Conflict` | `contracts/conflict.py` | yes (embedded) |
| C-11 | `SignalType` (enum) | `contracts/signal.py` | yes |
| C-12 | **`QualifiedEnterpriseSignal`** | `contracts/signal.py` | **yes — THE L1 -> L2 boundary** |

---

## Universal rules for every contract here

1. **Envelope on anything that crosses a layer.** `org_id`, `schema_version`,
   `trace_id`, `visibility`. Reuse the existing `ContractEnvelope`.
2. **Integer basis points only.** Every score is `int` in `0..10000`, suffixed `_bp`.
   No `float` may appear in any field of any contract in this document.
3. **Money is never a float.** `Money` = integer minor units + ISO 4217 code.
4. **Every claim carries evidence.** Any field asserting something about the world
   carries at least one `EvidenceSpan`. A claim with an empty `evidence` list fails
   validation and is not publishable.
5. **Validators live beside the type**, and run at the seam that produced the object —
   not three layers later.

---

## C-01 · EvidenceSpan

The anti-hallucination primitive. Everything else depends on it.

```python
class EvidenceSpan(BaseModel):
    """A verbatim pointer back into source text.

    This is what makes a claim auditable. `quote` must appear byte-for-byte in the
    prepared content at [start_offset:end_offset]. L1.5.1 validates that; a span that
    does not resolve marks its parent claim unverified.
    """
    source_ref: str          # "prepared_content:<event_id>" | "chunk:<doc_id>:<n>"
    quote: str               # verbatim, <= 400 chars
    start_offset: int        # inclusive, into prepared clean_text
    end_offset: int          # exclusive
    verified: bool = False   # set True ONLY by L1.5.1, never by the model
```

**Validator:** `end_offset > start_offset`; `len(quote) == end_offset - start_offset`;
`quote` non-empty.

---

## C-02 · Money

```python
class Money(BaseModel):
    """Integer minor units + ISO code. Never a float, never a formatted string.

    $84,000 -> Money(minor_units=8_400_000, currency="USD")
    "$84K"  -> the SAME object. Normalization happens once, at L1.5.3.
    """
    minor_units: int
    currency: str            # ISO 4217, uppercase
    as_written: str          # "$84K" — kept for the card and for conflict display
```

**Validator:** `currency` matches `^[A-Z]{3}$`.

---

## C-03 · ResolvedDate

The point of this type is that **"next week" is not a date** — it is a range plus a
certainty. Collapsing it to a single timestamp invents precision.

```python
class DateCertainty(str, Enum):
    EXACT      = "exact"        # "October 15, 2026"
    RANGE      = "range"        # "next week", "end of month"
    RELATIVE   = "relative"     # "soon", "shortly"  -> range is a heuristic guess
    UNRESOLVED = "unresolved"   # could not be resolved; earliest/latest are None

class ResolvedDate(BaseModel):
    as_written: str                  # "pretty soon", "by Friday"
    earliest: datetime | None
    latest: datetime | None
    certainty: DateCertainty
    resolved_against: datetime       # the eval_time used — replay needs this
    evidence: list[EvidenceSpan]
```

**Validator:** if `certainty == EXACT` then `earliest == latest`. If
`certainty == UNRESOLVED` then both are `None`. Otherwise `earliest <= latest`.

---

## C-04..C-08 · Extraction payload types

```python
class EntityMention(BaseModel):
    surface_form: str                # exactly as written: "AWS", "Amazon Web Services"
    entity_type: str                 # person | organization | vendor | product | document | project
    canonical_hint: str | None       # L1.5.4 fills this; L2 is authoritative
    evidence: list[EvidenceSpan]
    confidence_bp: int

class Commitment(BaseModel):
    actor: str                       # who owes it
    action: str                      # what they owe
    beneficiary: str | None          # who they owe it to
    due: ResolvedDate | None
    is_conditional: bool             # "I'll send it once legal confirms"
    condition_text: str | None
    evidence: list[EvidenceSpan]
    confidence_bp: int

class DecisionState(BaseModel):
    subject: str                     # "AWS renewal", "pricing"
    state: str                       # pending | made | blocked | deferred | abandoned
    blocked_on: str | None
    owner: str | None
    evidence: list[EvidenceSpan]
    confidence_bp: int

class Dependency(BaseModel):
    """A blocks B. This is what makes a deadline more than a calendar entry."""
    blocker: str
    blocked: str
    dependency_type: str             # approval | information | delivery | decision
    evidence: list[EvidenceSpan]
    confidence_bp: int

class UnclassifiedObservation(BaseModel):
    """THE OPEN LANE.

    Something the model noticed that has no name in the current vocabulary. It is
    stored, never consumed by any rule, and reviewed weekly. This is the only
    mechanism by which GeniOS can discover a pattern nobody wrote a rule for.

    Rules MUST NOT read this table. If a kind here proves recurrent it is promoted
    into the canonical vocabulary by a human, with a version bump.
    """
    proposed_kind: str               # the model's own free-text label
    description: str
    evidence: list[EvidenceSpan]
    confidence_bp: int
```

---

## C-09 · ExtractionResult

The complete S2 output. **Internal to L1** — L2 never sees this, it sees the QES.

```python
class ExtractionResult(BaseModel):
    # --- what the message means ---
    intent: str                                  # closed set, see doc 04
    topics: list[str]
    stance: str                                  # positive | neutral | cautious | negative | mixed

    # --- what it contains ---
    entity_mentions: list[EntityMention]
    amounts: list[Money]
    dates_mentioned: list[ResolvedDate]
    commitments: list[Commitment]
    decision_states: list[DecisionState]
    dependencies: list[Dependency]
    implied_actions: list[str]
    questions: list[str]
    roles: list[dict]
    relationships: list[dict]
    scheduling_proposals: list[dict]

    # --- the discovery lane ---
    unclassified_observations: list[UnclassifiedObservation]

    # --- trust ---
    field_confidence: dict[str, int]             # per-field, basis points
    all_evidence: list[EvidenceSpan]

    # --- provenance (required for replay) ---
    model_snapshot: str                          # exact model id used
    prompt_version: str
    schema_version: str
    extraction_profile: str                      # email | chat | transcript | document | crm_note
    input_tokens: int
    output_tokens: int

    # --- FORBIDDEN ---
    # importance_bp   <- NEVER. Computed at L1.6.7 from validated facts.
    # priority_bp     <- NEVER. That is Layer 4.
```

---

## C-10 · Conflict

Two sources disagree about the same field. The contract deliberately has **no
`winner`** — surfacing beats silently picking.

```python
class ConflictClaim(BaseModel):
    value: Any
    authority: str               # signed_document | attachment | email_prose | chat_aside | structured_source
    authority_rank: int          # from ALG-14
    evidence: list[EvidenceSpan]

class Conflict(BaseModel):
    field: str                   # "contract.value", "renewal.date"
    claims: list[ConflictClaim]  # >= 2
    resolution: str              # unresolved_surface_both | resolved_by_authority | resolved_by_recency
    resolved_value: Any | None   # set ONLY when resolution != unresolved_surface_both
    detected_at: datetime
```

**Validator:** `len(claims) >= 2`; if `resolution == "unresolved_surface_both"` then
`resolved_value is None`.

---

## C-11 · SignalType

The closed taxonomy. Adding a member is a schema version bump and a corpus review —
never a casual edit.

```python
class SignalType(str, Enum):
    COMMITMENT_MADE      = "commitment_made"
    COMMITMENT_DUE       = "commitment_due"
    DEADLINE_STATED      = "deadline_stated"
    DECISION_PENDING     = "decision_pending"
    DECISION_MADE        = "decision_made"
    APPROVAL_REQUESTED   = "approval_requested"
    CONTRACT_RENEWAL     = "contract_renewal"
    FINANCIAL_OBLIGATION = "financial_obligation"
    RISK_FLAGGED         = "risk_flagged"
    OPPORTUNITY_SIGNAL   = "opportunity_signal"
    RELATIONSHIP_CHANGE  = "relationship_change"
    INFORMATION_CONFLICT = "information_conflict"
    ESCALATION           = "escalation"
    ANOMALY              = "anomaly"
```

---

## C-12 · QualifiedEnterpriseSignal — THE boundary object

```python
class QualifiedEnterpriseSignal(BaseModel):
    """Layer 1's only output. Nothing else crosses the L1 -> L2 seam.

    Replaces GatedEvent. GatedEvent carried the ROUTING half of L1's job
    (structured vs needs-extraction) and, by its own docstring, "was missing its
    qualifying half". This object carries both.
    """
    # --- envelope ---
    org_id: str
    schema_version: int = 1
    trace_id: str
    visibility: Visibility            # source-stamped; never widened

    # --- identity ---
    signal_id: str
    event_id: str
    source: str
    object_type: str
    occurred_at: datetime

    # --- QUALIFICATION (the half that does not exist today) ---
    signal_type: SignalType
    domain_hints: list[DomainHint]
    importance_bp: int                # deterministic, ALG-17
    triage_lane: str                  # P0..P3, processing order only

    # --- semantic payload ---
    extraction: ExtractionResult

    # --- trust ---
    evidence_refs: list[EvidenceSpan]
    conflicts: list[Conflict]
    confidence_bp: int                # composed, ALG-13
    confidence_vector: dict[str, int] # evidence | expertise | freshness | coverage
    coverage_ready: bool | None       # can we make a NEGATIVE inference here?

    # --- lifecycle ---
    state: str                        # active | superseded | expired | resolved
    supersedes: str | None
    expires_at: datetime | None

    # --- provenance ---
    internal_kind: str | None         # company canon authority class
    recipients: tuple[str, ...]
    versions: dict[str, Any]          # every version that produced this
```

### Publication validator (runs at L1.6.10, blocks emit)

| # | Rule | On failure |
|---|---|---|
| V-1 | envelope complete, `visibility is not None` | park `visibility_unknown` |
| V-2 | `signal_type` in `SignalType` | reject |
| V-3 | `0 <= importance_bp <= 10000` | reject |
| V-4 | `evidence_refs` non-empty | reject — a claim with no receipt is a guess |
| V-5 | every `EvidenceSpan.verified is True` | downgrade `confidence_bp`, emit anyway, flag |
| V-6 | `confidence_bp <= min(source confidences)` unless independent evidence is named | reject (Rule 11) |
| V-7 | no `float` anywhere in the serialized object | reject |

---

## Migration from `GatedEvent`

`GatedEvent` is **not deleted** in v2. It is demoted to an internal S1->S2 handoff
type and renamed `RoutedEvent`. Reason: it carries genuinely good work (MUT-01
versionability, visibility stamping, domain hints) that must not be lost.

| GatedEvent field | Goes to |
|---|---|
| `event_id`, `org_id`, `source`, `object_type`, `occurred_at` | QES, unchanged |
| `route`, `structured_fields` | `RoutedEvent` (internal) |
| `domain_hints` | QES `domain_hints` |
| `deadline_at` | absorbed into `ExtractionResult.dates_mentioned` |
| `linkage_hints` | QES `extraction.relationships` (was persisted and unread) |
| `triage_lane` | QES `triage_lane` |
| `coverage_ready` | QES `coverage_ready` — **and now actually assigned** |
| `internal_kind`, `recipients`, `visibility`, `versions` | QES, unchanged |

---

## REVERSE PROMPT — Wave W0

```
TASK: Build the Layer 1 v2 contract types.

CONTEXT
- Repo: genios-brain. Package: genios_engine/contracts/
- Contracts may import platform + stdlib ONLY. Never capture/, context/, reason/.
- There is an existing test that enforces layer import direction:
  tests/test_layer_topology.py — it must stay green.

CREATE these files:
  genios_engine/contracts/evidence.py    -> EvidenceSpan
  genios_engine/contracts/units.py       -> Money, ResolvedDate, DateCertainty
  genios_engine/contracts/extraction.py  -> EntityMention, Commitment, DecisionState,
                                            Dependency, UnclassifiedObservation,
                                            ExtractionResult
  genios_engine/contracts/conflict.py    -> ConflictClaim, Conflict
  genios_engine/contracts/signal.py      -> SignalType, QualifiedEnterpriseSignal

RULES (non-negotiable)
1. pydantic BaseModel for every type.
2. NO float fields anywhere. Every score is `int` named `*_bp`, range 0..10000.
   Add a shared validator `require_bp(value, name)` in contracts/validators.py
   (one already exists there — reuse it, do not duplicate).
3. Money is integer minor_units + ISO 4217 currency. Never float, never a string.
4. Every type that asserts something about the world has a non-empty
   `evidence: list[EvidenceSpan]`.
5. ExtractionResult MUST NOT have importance_bp or priority_bp. Add a comment saying
   why: importance is computed deterministically at L1.6.7 from VALIDATED facts, and a
   model-produced score is not reproducible across replays.
6. Reuse the existing Visibility type from contracts/visibility.py. Do not redefine it.
7. Reuse the existing DomainHint from contracts/gated_event.py.

ALSO
- Rename GatedEvent -> RoutedEvent in contracts/gated_event.py, keep every existing
  field, and update all import sites. Add a module docstring explaining that this is now
  an INTERNAL S1->S2 handoff type and that QualifiedEnterpriseSignal is the layer
  boundary object.

TESTS to write (tests/contracts/test_l1_contracts.py):
- a float in any _bp field raises
- _bp outside 0..10000 raises
- EvidenceSpan with end_offset <= start_offset raises
- EvidenceSpan where len(quote) != end-start raises
- ResolvedDate EXACT with earliest != latest raises
- ResolvedDate UNRESOLVED with a non-None earliest raises
- Conflict with 1 claim raises
- Conflict resolution=unresolved_surface_both with a resolved_value raises
- Money with lowercase currency raises
- round-trip: QualifiedEnterpriseSignal -> model_dump_json -> reparse is identical

ACCEPTANCE
  python -m pytest tests/contracts/test_l1_contracts.py -q   -> all pass, 0 skips
  python -m pytest tests/test_layer_topology.py -q           -> still passes

DO NOT
- Do not wire these into any pipeline yet. W0 is types + tests only.
- Do not delete GatedEvent; rename it.
- Do not add an embeddings field. L1 v2 ships no embeddings (see 00-Overview MAP B).
```
