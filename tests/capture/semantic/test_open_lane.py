"""L1.4.5 · the OPEN LANE — capture, promotion, discovery, and the fence around all three.

    pytest tests/capture/semantic/test_open_lane.py -q

The doc-04 acceptance for U1 is two lines, and both are asserted here for real:

    rows persist; span validation runs on them
    NO module under genios_engine/packs/ or reason/ imports open_lane

The first is a real-PostgreSQL round trip (`pytest.mark.pg`), not an in-memory dict pretending to
be a table — the SQL, the content-addressed primary key and the org FK are the parts that can be
silently wrong. The second is a property of the SOURCE TREE, asserted with `ast` the way
`tests/test_layer_topology.py` does it: no imports executed, no ordering to get wrong. It is
checked twice, because an import fence a raw query walks around is not a fence — the second pass
looks for the TABLE NAME in string literals under those two trees.

Everything else in this file exists because the lane has exactly one way to fail quietly. It is a
discovery mechanism whose output nobody consumes automatically: if capture drops observations, or
if the report double-counts a replay, nothing breaks and no alarm fires — the vocabulary simply
never grows, and the reason is invisible. So each stated behaviour gets a row: the cap keeps the
five MOST CONFIDENT, a fabricated receipt is stored flagged rather than trusted or deleted, a
re-extract writes nothing new, an unverified kind cannot vote itself into the vocabulary, and a
promotion is refused five specific ways before it is allowed once.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta
from datetime import timezone as _timezone
from pathlib import Path

import pytest

from genios_engine.capture.semantic.open_lane import (DISCOVERY_WINDOW_DAYS, MAX_EXAMPLE_QUOTES,
                                                      MAX_KIND_CHARS, OPEN_LANE_RETENTION_DAYS,
                                                      PROMOTION_MIN_OCCURRENCES, UNNAMEABLE_KIND,
                                                      InMemoryOpenLaneStore, ObservationRow,
                                                      PromotionDecision, PromotionRefused,
                                                      canonical_kind, capture_unclassified,
                                                      discovery_report, promote_kind)
from genios_engine.capture.validate.spans import SpanVerdict
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import (MAX_UNCLASSIFIED_PER_EXTRACTION, ExtractionResult,
                                                UnclassifiedObservation)

ORG = "org_open_lane_tests"
EVENT = "evt_open_lane"
SOURCE_REF = f"prepared_content:{EVENT}"

#: The substrate every span in this file points into. One sentence per observation, each phrase
#: occurring exactly once so a span is unambiguous and `find` is a safe way to build one.
SOURCE = ("Legal put a security review in front of the renewal, and procurement froze the budget "
          "until April. Our champion Priya moved to a new team last week.")


def _span(quote: str, *, start: int | None = None, verified: bool = False) -> EvidenceSpan:
    """A receipt built by FINDING the quote, so no offset in this file is hand-counted.

    `start` overrides the found offset — that is how a RELOCATED grade is staged: the words are
    real, the coordinates are not, which is the commonest real extractor failure and the one the
    lane must store corrected rather than as sent.
    """
    found = SOURCE.find(quote)
    assert found >= 0, f"quote is not in the source, so no span can point at it: {quote!r}"
    assert SOURCE.find(quote, found + 1) < 0, f"{quote!r} occurs twice; offsets would be a coin flip"
    offset = found if start is None else start
    return EvidenceSpan(source_ref=SOURCE_REF, quote=quote, start_offset=offset,
                        end_offset=offset + len(quote), verified=verified)


def _observation(kind: str, quote: str, *, description: str = "something new",
                 confidence_bp: int = 7000,
                 spans: list[EvidenceSpan] | None = None) -> UnclassifiedObservation:
    return UnclassifiedObservation(proposed_kind=kind, description=description,
                                   evidence=spans if spans is not None else [_span(quote)],
                                   confidence_bp=confidence_bp)


def _result(*observations: UnclassifiedObservation) -> ExtractionResult:
    """A minimal C-09 carrying only the open lane. Provenance is required by the contract, so it
    is supplied — the rest of the extraction is not what this unit reads."""
    return ExtractionResult(intent="inform", stance="neutral",
                            unclassified_observations=list(observations),
                            model_snapshot="fake-model-1", prompt_version="p1",
                            schema_version="s1", extraction_profile="email",
                            input_tokens=10, output_tokens=5)


@pytest.fixture
def store() -> InMemoryOpenLaneStore:
    return InMemoryOpenLaneStore()


# ═════════════════════════════════════════════════════════════════════════════════════════════
# canonical_kind — the grouping key, and why the report is not empty
# ═════════════════════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("label, expected", [
    ("renewal_risk", "renewal_risk"),                 # already canonical: unchanged
    ("Renewal Risk", "renewal_risk"),                 # title case
    ("  RENEWAL   RISK  ", "renewal_risk"),           # padding and a run of spaces
    ("Renewal-Risk!", "renewal_risk"),                # punctuation folds to the separator
    ("budget freeze (Q3)", "budget_freeze_q3"),       # parentheses do not survive as characters
    ("security-review→legal", "security_review_legal"),   # non-ascii separator
    ("???", UNNAMEABLE_KIND),                         # nothing nameable is left
    ("🙂", UNNAMEABLE_KIND),                          # ditto, and it must not crash
])
def test_canonical_kind_folds_spelling_so_one_pattern_is_one_candidate(label, expected):
    """Four spellings of one thing must be ONE bucket.

    Without folding, "Renewal Risk" seen twice, "renewal risk" seen twice and "Renewal-Risk!"
    seen twice is three candidates at 2 each — all under the bar of 5 — and the discovery report
    proposes nothing while the pattern is sitting right there six times over.
    """
    assert canonical_kind(label) == expected


def test_canonical_kind_truncates_a_label_the_index_could_not_hold():
    """A model that emits a paragraph as a label must not be able to write an index entry the
    server refuses, and the raw label is kept on the row so nothing is actually lost."""
    kind = canonical_kind("x" * (MAX_KIND_CHARS * 3))
    assert len(kind) == MAX_KIND_CHARS


# ═════════════════════════════════════════════════════════════════════════════════════════════
# U1 · capture
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_capture_persists_the_observation_with_its_receipt(store, eval_time):
    """The base case: one observation in, one row out, readable back by org and event."""
    capture = capture_unclassified(
        _result(_observation("Security Review", "Legal put a security review")),
        org_id=ORG, event_id=EVENT, source_text=SOURCE, eval_time=eval_time, store=store)

    assert (capture.stored, capture.over_cap, capture.unverified) == (1, 0, 0)
    (row,) = store.observations_for(org_id=ORG, event_id=EVENT)
    assert row.proposed_kind == "security_review"
    assert row.proposed_kind_raw == "Security Review"          # the model's own words survive
    assert row.quote == "Legal put a security review"
    assert row.start_offset == SOURCE.find("Legal put a security review")
    assert row.verified is True
    assert row.span_verdict == SpanVerdict.VERIFIED.value
    assert row.created_at == eval_time
    assert row.promoted_to is None


def test_capture_of_an_extraction_with_no_observations_touches_no_storage(store, eval_time):
    """The overwhelmingly common case must cost nothing — no row, no write."""
    capture = capture_unclassified(_result(), org_id=ORG, event_id=EVENT, source_text=SOURCE,
                                   eval_time=eval_time, store=store)
    assert capture == type(capture)()
    assert store.rows == {}


def test_span_validation_runs_on_them_and_corrects_the_extractor_offsets(store, eval_time):
    """A real quote at invented coordinates is stored at the coordinates it ACTUALLY occupies.

    A row that kept the model's offsets would highlight unrelated text when a reviewer clicks the
    receipt — worse than an honest failure, because the reader checks one receipt, sees nonsense,
    and stops trusting the ones that are right.
    """
    real = SOURCE.find("procurement froze the budget")
    capture = capture_unclassified(
        _result(_observation("Budget Freeze", "procurement froze the budget",
                             spans=[_span("procurement froze the budget", start=real + 9)])),
        org_id=ORG, event_id=EVENT, source_text=SOURCE, eval_time=eval_time, store=store)

    (row,) = store.observations_for(org_id=ORG, event_id=EVENT)
    assert row.start_offset == real                                   # corrected, not trusted
    assert row.span_verdict == SpanVerdict.VERIFIED_RELOCATED.value
    assert row.verified is True
    assert capture.unverified == 0


def test_a_fabricated_receipt_is_stored_flagged_never_trusted_and_never_dropped(store, eval_time):
    """The model invented the sentence. The row stays, the checkmark does not.

    Two failures are being refused at once. DROPPING would contradict the ALG-08 policy row for
    `UnclassifiedObservation` (keep-and-flag) and erase the only record that the extractor is
    inventing. TRUSTING is worse: `EvidenceSpan.verified` is an ordinary field an extractor can
    set itself, and the fabricated span below arrives carrying `verified=True`.
    """
    invented = EvidenceSpan(source_ref=SOURCE_REF, quote="Priya resigned in protest",
                            start_offset=0, end_offset=25, verified=True)
    capture = capture_unclassified(
        _result(_observation("Champion Loss", "", spans=[invented])),
        org_id=ORG, event_id=EVENT, source_text=SOURCE, eval_time=eval_time, store=store)

    (row,) = store.observations_for(org_id=ORG, event_id=EVENT)
    assert capture.unverified == 1
    assert row.verified is False                       # the extractor's own flag was taken away
    assert row.span_verdict == SpanVerdict.UNVERIFIED.value
    assert row.quote == "Priya resigned in protest"    # kept verbatim: evidence about the model


def test_the_strongest_receipt_is_the_one_stored(store, eval_time):
    """An observation citing an invention FIRST and a real quote second is stored against the
    real one. Taking `evidence[0]` would file a substantiated observation as a fabrication and
    keep it out of the promotion count forever."""
    invented = EvidenceSpan(source_ref=SOURCE_REF, quote="Priya resigned in protest",
                            start_offset=0, end_offset=25)
    real = _span("Priya moved to a new team")
    capture_unclassified(
        _result(_observation("Champion Loss", "", spans=[invented, real])),
        org_id=ORG, event_id=EVENT, source_text=SOURCE, eval_time=eval_time, store=store)

    (row,) = store.observations_for(org_id=ORG, event_id=EVENT)
    assert row.verified is True
    assert row.quote == "Priya moved to a new team"


def test_span_verdict_declaration_order_is_strongest_first():
    """`_best_receipt` picks the minimum by `tuple(SpanVerdict)` index, so this file depends on
    the enum's documented declaration order. Pinned here rather than restated as a second copy
    of the order inside `open_lane.py`: if somebody reorders the enum, this fails instead of the
    lane quietly starting to store the weakest receipt it can find."""
    assert tuple(SpanVerdict) == (SpanVerdict.VERIFIED, SpanVerdict.VERIFIED_WHITESPACE,
                                  SpanVerdict.VERIFIED_RELOCATED, SpanVerdict.VERIFIED_FUZZY,
                                  SpanVerdict.UNVERIFIED, SpanVerdict.INVALID_BOUNDS)


def test_the_cap_keeps_the_most_confident_and_counts_the_rest(store, eval_time):
    """`MAX_UNCLASSIFIED_PER_EXTRACTION` is applied at the SINK as a trim, never as a raise.

    The contract deliberately refuses to enforce the cap, because an extraction that raised on
    its sixth observation would lose the other five and the whole message with them. So the
    behaviour under test is: keep the five most confident, count the overflow, lose nothing else.
    """
    quotes = ["Legal put a security review", "procurement froze the budget", "until April",
              "Our champion Priya", "moved to a new team", "last week", "in front of the renewal"]
    observations = [_observation(f"kind {i}", quote, confidence_bp=1000 * (i + 1))
                    for i, quote in enumerate(quotes)]
    capture = capture_unclassified(_result(*observations), org_id=ORG, event_id=EVENT,
                                   source_text=SOURCE, eval_time=eval_time, store=store)

    assert capture.stored == MAX_UNCLASSIFIED_PER_EXTRACTION
    assert capture.over_cap == len(quotes) - MAX_UNCLASSIFIED_PER_EXTRACTION
    kept = {row.proposed_kind for row in store.observations_for(org_id=ORG, event_id=EVENT)}
    assert kept == {"kind_2", "kind_3", "kind_4", "kind_5", "kind_6"}      # the confident five


def test_re_extracting_the_same_event_writes_nothing_new(store, eval_time):
    """A replay must not vote twice.

    Observation ids are content-addressed, so re-running the pipeline over an event is a no-op.
    With random ids a re-sync would double every kind's frequency — and frequency is the ONLY
    number deciding whether a word enters the closed vocabulary, so the threshold would be
    measuring how often we re-ran ingestion.
    """
    result = _result(_observation("Security Review", "Legal put a security review"))
    first = capture_unclassified(result, org_id=ORG, event_id=EVENT, source_text=SOURCE,
                                 eval_time=eval_time, store=store)
    second = capture_unclassified(result, org_id=ORG, event_id=EVENT, source_text=SOURCE,
                                  eval_time=eval_time + timedelta(days=1), store=store)

    assert (first.stored, second.stored) == (1, 0)
    assert len(store.observations_for(org_id=ORG, event_id=EVENT)) == 1


def test_two_orgs_noticing_the_same_thing_are_two_rows(store, eval_time):
    """The content address includes the org. Two tenants seeing the same pattern is the strongest
    possible promotion evidence — collapsing them into one row would delete exactly that."""
    result = _result(_observation("Security Review", "Legal put a security review"))
    for org in (ORG, "org_other"):
        capture_unclassified(result, org_id=org, event_id=EVENT, source_text=SOURCE,
                             eval_time=eval_time, store=store)
    assert len(store.rows) == 2


# ═════════════════════════════════════════════════════════════════════════════════════════════
# U3 · the discovery report
# ═════════════════════════════════════════════════════════════════════════════════════════════

def _seed(store: InMemoryOpenLaneStore, kind: str, *, n: int, at: datetime, org: str = ORG,
          verified: bool = True, quote: str = "Legal put a security review") -> None:
    """n rows of one kind, one per hour, so `created_at` ordering is total and deterministic."""
    store.add([ObservationRow(
        observation_id=f"obs_{kind}_{org}_{i}", org_id=org, event_id=f"{EVENT}_{i}",
        proposed_kind=kind, proposed_kind_raw=kind, description="d",
        quote=f"{quote} {i}", source_ref=SOURCE_REF, start_offset=0, end_offset=10,
        confidence_bp=7000, verified=verified,
        span_verdict=SpanVerdict.VERIFIED.value if verified else SpanVerdict.UNVERIFIED.value,
        created_at=at + timedelta(hours=i)) for i in range(n)])


def test_report_lists_only_kinds_that_cleared_the_bar_most_frequent_first(store, eval_time):
    """Doc 04's query: `having count(*) >= 5`, `order by n desc`.

    Below the bar a "pattern" is a coincidence, and a vocabulary member no rule ever matches is
    worse than no member at all — it is a word in a closed set that means nothing.
    """
    _seed(store, "budget_freeze", n=9, at=eval_time - timedelta(days=3))
    _seed(store, "security_review", n=5, at=eval_time - timedelta(days=2))
    _seed(store, "champion_loss", n=4, at=eval_time - timedelta(days=1))       # under the bar

    report = discovery_report(store, eval_time=eval_time)
    assert [row.proposed_kind for row in report.rows] == ["budget_freeze", "security_review"]
    assert [row.occurrences for row in report.rows] == [9, 5]
    assert report.window_days == DISCOVERY_WINDOW_DAYS
    assert report.min_occurrences == PROMOTION_MIN_OCCURRENCES


def test_report_counts_org_spread_and_the_window_it_was_counted_over(store, eval_time):
    """Org count is what separates "one customer's habit" from "a thing that happens", and the
    window is what keeps a kind that stopped appearing from being proposed forever."""
    _seed(store, "budget_freeze", n=3, at=eval_time - timedelta(days=2), org="org_a")
    _seed(store, "budget_freeze", n=3, at=eval_time - timedelta(days=2), org="org_b")
    _seed(store, "budget_freeze", n=6, at=eval_time - timedelta(days=400), org="org_c")  # stale

    (row,) = discovery_report(store, eval_time=eval_time).rows
    assert (row.occurrences, row.orgs) == (6, 2)
    assert row.first_seen == eval_time - timedelta(days=2)


def test_an_unsubstantiated_kind_is_reported_but_never_promotable(store, eval_time):
    """A kind seen 8 times whose receipts are all inventions is a prompt that has started
    hallucinating in a new direction — not a discovery. It must be VISIBLE (so a human can see
    it) and un-promotable (so it cannot vote itself into the vocabulary)."""
    _seed(store, "phantom_kind", n=8, at=eval_time - timedelta(days=2), verified=False)
    _seed(store, "budget_freeze", n=6, at=eval_time - timedelta(days=2))

    rows = {row.proposed_kind: row for row in discovery_report(store, eval_time=eval_time).rows}
    assert rows["phantom_kind"].occurrences == 8
    assert rows["phantom_kind"].verified_occurrences == 0
    assert rows["phantom_kind"].promotable is False
    assert rows["budget_freeze"].promotable is True
    assert [row.proposed_kind for row in
            discovery_report(store, eval_time=eval_time).promotable] == ["budget_freeze"]


def test_example_quotes_are_off_by_default_capped_and_verified_only(store, eval_time):
    """The quotes are customer message CONTENT crossing the cross-org admin boundary, so they are
    opt-in, bounded, and never a sentence the model invented."""
    _seed(store, "budget_freeze", n=6, at=eval_time - timedelta(days=2))
    _seed(store, "budget_freeze", n=2, at=eval_time - timedelta(days=1), verified=False,
          org="org_b", quote="never written anywhere")

    assert discovery_report(store, eval_time=eval_time).rows[0].example_quotes == ()
    quotes = discovery_report(store, eval_time=eval_time, examples=99).rows[0].example_quotes
    assert len(quotes) == MAX_EXAMPLE_QUOTES                       # clamped, not obeyed
    assert all("never written anywhere" not in quote for quote in quotes)


# ═════════════════════════════════════════════════════════════════════════════════════════════
# U2 · promotion — human-gated, five refusals and one success
# ═════════════════════════════════════════════════════════════════════════════════════════════

def _decision(**overrides) -> PromotionDecision:
    base = dict(proposed_kind="budget_freeze", vocabulary_member="budget_freeze",
                decided_by="harsh@genios", schema_version_before="2026.1",
                schema_version_after="2026.2")
    return PromotionDecision(**{**base, **overrides})


@pytest.mark.parametrize("overrides, because", [
    ({"decided_by": "   "},
     "no human is recorded as deciding, so nothing distinguishes this from an automatic edit"),
    ({"vocabulary_member": "Budget Freeze"},
     "a rule is written against the member name; 'Budget Freeze' is not a name a rule can match"),
    ({"schema_version_after": "2026.1"},
     "without the version bump the extraction cache keeps answering with the old vocabulary"),
])
def test_promotion_is_refused_when_the_decision_is_not_admissible(store, eval_time, overrides,
                                                                  because):
    """Each row is one way a promotion stops being a human act with a code change attached."""
    _seed(store, "budget_freeze", n=9, at=eval_time - timedelta(days=2))
    with pytest.raises(PromotionRefused):
        promote_kind(store, _decision(**overrides), eval_time=eval_time)
    assert store.promotion_of("budget_freeze") is None, because


def test_promotion_is_refused_below_the_evidence_bar(store, eval_time):
    """Four sightings is not a pattern. The message must carry the number, or the reviewer goes
    back to the report to guess which of five rules they tripped."""
    _seed(store, "budget_freeze", n=PROMOTION_MIN_OCCURRENCES - 1, at=eval_time - timedelta(days=2))
    with pytest.raises(PromotionRefused, match="4 substantiated occurrence"):
        promote_kind(store, _decision(), eval_time=eval_time)


def test_unverified_rows_do_not_count_toward_the_bar(store, eval_time):
    """Twenty fabricated sightings and four real ones is still four. This is the rule that stops
    a hallucinating prompt from writing its own vocabulary."""
    _seed(store, "budget_freeze", n=4, at=eval_time - timedelta(days=2))
    _seed(store, "budget_freeze", n=20, at=eval_time - timedelta(days=3), org="org_b",
          verified=False)
    with pytest.raises(PromotionRefused, match="4 substantiated occurrence"):
        promote_kind(store, _decision(), eval_time=eval_time)


def test_promotion_stamps_every_historical_row_across_orgs(store, eval_time):
    """The stamped rows ARE the provenance of the new vocabulary member — the answer to "why does
    this kind exist?" — and they are exempted from the 180-day purge by the same act."""
    _seed(store, "budget_freeze", n=5, at=eval_time - timedelta(days=2), org="org_a")
    _seed(store, "budget_freeze", n=4, at=eval_time - timedelta(days=3), org="org_b")
    _seed(store, "security_review", n=6, at=eval_time - timedelta(days=2))

    promotion = promote_kind(store, _decision(), eval_time=eval_time)

    assert promotion.rows_marked == 9
    assert promotion.candidate.verified_occurrences == 9
    assert promotion.promoted_at == eval_time
    stamped = [row for row in store.rows.values() if row.proposed_kind == "budget_freeze"]
    assert {row.promoted_to for row in stamped} == {"budget_freeze"}
    assert {row.promoted_by for row in stamped} == {"harsh@genios"}
    assert {row.promoted_schema_version for row in stamped} == {"2026.2"}
    assert {row.reviewed_at for row in stamped} == {eval_time}
    untouched = [row for row in store.rows.values() if row.proposed_kind == "security_review"]
    assert {row.promoted_to for row in untouched} == {None}


def test_promotion_returns_the_edit_and_never_performs_it(store, eval_time):
    """This unit hands back the two changes a human makes; it does not make them. Both halves
    must be in the instruction — the member alone, without the schema bump, is a promotion that
    is real in the vocabulary file and invisible in every extraction."""
    _seed(store, "budget_freeze", n=6, at=eval_time - timedelta(days=2))
    edit = promote_kind(store, _decision(), eval_time=eval_time).vocabulary_edit
    assert "budget_freeze" in edit
    assert "vocabulary.py" in edit
    assert "EXTRACTION_SCHEMA_VERSION" in edit and "2026.2" in edit


def test_a_promoted_kind_leaves_the_report_and_cannot_be_promoted_twice(store, eval_time):
    """After the bump, a straggling extraction from the old cache can still write rows for a kind
    that now HAS a name. Re-proposing it would send the reviewer round the same loop, and
    re-stamping would overwrite the provenance of a member that already exists."""
    _seed(store, "budget_freeze", n=6, at=eval_time - timedelta(days=2))
    promote_kind(store, _decision(), eval_time=eval_time)
    _seed(store, "budget_freeze", n=6, at=eval_time - timedelta(days=1), org="org_late")

    assert discovery_report(store, eval_time=eval_time).rows == ()
    with pytest.raises(PromotionRefused, match="already promoted"):
        promote_kind(store, _decision(schema_version_after="2026.3"), eval_time=eval_time)


def test_a_reviewer_may_paste_the_raw_label_instead_of_the_canonical_one(store, eval_time):
    """The report shows quotes and raw labels beside the canonical key; a decision typed as
    "Budget Freeze" must reach the same bucket rather than silently promoting nothing."""
    _seed(store, "budget_freeze", n=6, at=eval_time - timedelta(days=2))
    promotion = promote_kind(store, _decision(proposed_kind="Budget Freeze"), eval_time=eval_time)
    assert promotion.rows_marked == 6


# ═════════════════════════════════════════════════════════════════════════════════════════════
# Retention
# ═════════════════════════════════════════════════════════════════════════════════════════════

def test_purge_clears_the_window_and_spares_promoted_rows(store, eval_time):
    """180 days rolling, `promoted_to` exempt — deleting a promoted row would leave a word in the
    closed vocabulary with no record of why it is there."""
    old = eval_time - timedelta(days=OPEN_LANE_RETENTION_DAYS + 1)
    _seed(store, "stale_kind", n=3, at=old)
    _seed(store, "budget_freeze", n=6, at=old, org="org_b")
    promote_kind(store, _decision(), eval_time=old + timedelta(hours=6),
                 window_days=OPEN_LANE_RETENTION_DAYS)

    purged = store.purge_expired(eval_time=eval_time)

    assert purged == 3
    assert {row.proposed_kind for row in store.rows.values()} == {"budget_freeze"}


# ═════════════════════════════════════════════════════════════════════════════════════════════
# THE FENCE — doc 04's second assert, twice
# ═════════════════════════════════════════════════════════════════════════════════════════════

_ENGINE_ROOT = Path(__file__).resolve().parents[3] / "genios_engine"
#: The two trees that decide what the product DOES. A rule may not read an unreviewed label.
_FENCED_TREES = ("packs", "reason")
_TABLE = "unclassified_observations"


def _fenced_files() -> list[Path]:
    files = [py for tree in _FENCED_TREES for py in (_ENGINE_ROOT / tree).rglob("*.py")]
    assert files, "the fenced trees are empty — this assertion would pass vacuously"
    return files


def test_no_pack_or_reasoner_imports_the_open_lane():
    """Doc 04's own acceptance line, as a property of the source tree.

    An unclassified observation must never reach the rules engine. Rows here are free-form labels
    the model chose its own words for, unreviewed and unpromoted; a rule matching on one would
    change behaviour whenever the model's phrasing drifted, which is not a rule. The fault is not
    hypothetical — `context/extract/vocab.py` reached 268 distinct free-form field names in one
    org, 192 of them used exactly once. `ast`, so nothing is imported and no ordering matters.
    """
    offenders: list[str] = []
    for py in _fenced_files():
        for node in ast.walk(ast.parse(py.read_text(), filename=str(py))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""] + [alias.name for alias in node.names]
            if any("open_lane" in name for name in names):
                offenders.append(f"{py.relative_to(_ENGINE_ROOT)}:{node.lineno}")
    assert offenders == [], (
        "a pack or reasoner imports the open lane: the closed vocabulary would be closed in name "
        f"only. Offending sites: {offenders}")


def test_no_pack_or_reasoner_names_the_open_lane_table_in_sql():
    """The other half of the same fence. An import fence a raw query walks around is not a fence:
    a reasoner could reach these rows with `select … from unclassified_observations` and never
    import a thing. String literals only, via `ast`, so a comment explaining the fence does not
    trip it."""
    offenders: list[str] = []
    for py in _fenced_files():
        for node in ast.walk(ast.parse(py.read_text(), filename=str(py))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if _TABLE in node.value:
                    offenders.append(f"{py.relative_to(_ENGINE_ROOT)}:{node.lineno}")
    assert offenders == [], (
        f"a pack or reasoner queries {_TABLE} directly, walking around the import fence: "
        f"{offenders}")


def test_the_open_lane_cannot_edit_the_closed_vocabulary():
    """U2 is human-gated *by construction*: this module has no way to write a file and does not
    import the vocabulary it proposes additions to. Promotion returns an instruction; a module
    that could perform it is a module through which the vocabulary grows itself, and one refactor
    later "human-in-the-loop" is a comment rather than a property."""
    source = (_ENGINE_ROOT / "capture" / "semantic" / "open_lane.py").read_text()
    tree = ast.parse(source)
    writers = {"open", "write_text", "write_bytes", "unlink", "system", "exec", "eval"}
    called: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in writers:
                called.append(f"{name}:{node.lineno}")
        if isinstance(node, ast.ImportFrom) and "vocabulary" in (node.module or ""):
            called.append(f"imports vocabulary:{node.lineno}")
    assert called == [], f"the open lane can reach the vocabulary or the filesystem: {called}"


def test_the_table_is_in_the_tenant_erasure_list():
    """`_ORG_SCOPED_TABLES` runs with no try/except, so a table missing from it leaks the rows of
    a deleted account — and these rows are message QUOTES. The list is read from the module
    rather than the file, so a rename that forgets this table fails here."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    assert _TABLE in _ORG_SCOPED_TABLES


# ═════════════════════════════════════════════════════════════════════════════════════════════
# REAL POSTGRESQL — "rows persist", asserted against a server
#
# The in-memory store above proves the LOGIC. Everything below is the half only a database can
# answer: that the migration's table matches the row type field for field, that the
# content-addressed primary key is what makes a replay idempotent (rather than a Python dict
# being idempotent on its own), that the report's SQL — a filtered aggregate with an
# already-promoted exclusion and a sliced array — computes what `_aggregate` computes, and that
# a tenant erasure through `_ORG_SCOPED_TABLES` actually removes these rows.
# ═════════════════════════════════════════════════════════════════════════════════════════════

_PG = pytest.mark.pg

_ORGS = (ORG, "org_open_lane_b")


@pytest.fixture
def lane_engine(live_db_url):
    """The scratch engine, with this file's orgs seeded and its rows removed before AND after.

    An org row that outlives its test is a plausible answer to the `select id from orgs limit 1`
    guard several other fixtures in this suite start with — which would make the next module seed
    nothing, assert on nothing, and pass for a reason nobody wrote down."""
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres open-lane tests skipped")
    from genios_engine.platform.db import get_engine
    engine = get_engine(live_db_url)
    _reset_pg(engine)
    _seed_orgs_pg(engine)
    yield engine
    _reset_pg(engine)


@pytest.fixture
def lane_store(live_db_url, lane_engine):
    """The real store, built from the URL exactly as `platform/wiring.py` builds it."""
    from genios_engine.capture.semantic.open_lane import PostgresOpenLaneStore
    return PostgresOpenLaneStore(live_db_url)


def _reset_pg(engine) -> None:
    from sqlalchemy import text as sql
    with engine.begin() as conn:
        conn.execute(sql("delete from unclassified_observations where org_id = any(:orgs)"),
                     {"orgs": list(_ORGS)})
        conn.execute(sql("delete from orgs where id = any(:orgs)"), {"orgs": list(_ORGS)})


def _seed_orgs_pg(engine) -> None:
    """The table carries an org FK, so the tenants have to exist. Required columns are DISCOVERED
    rather than listed, so a later migration adding one does not turn this file into a skip."""
    from sqlalchemy import text as sql
    with engine.begin() as conn:
        required = conn.execute(sql(
            "select column_name, data_type from information_schema.columns where "
            "table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        for org in _ORGS:
            cols, placeholders, values = ["id"], [":id"], {"id": org}
            for column in required:
                cols.append(column.column_name)
                placeholders.append(f":{column.column_name}")
                data_type = column.data_type
                values[column.column_name] = (
                    "2026-01-01T00:00:00Z" if ("time" in data_type or "date" in data_type)
                    else 0 if ("int" in data_type or "numeric" in data_type
                               or "double" in data_type)
                    else False if data_type == "boolean"
                    else "{}" if data_type in ("json", "jsonb") else "scratch")
            conn.execute(sql(f"insert into orgs ({', '.join(cols)}) values "
                             f"({', '.join(placeholders)}) on conflict (id) do nothing"), values)


@_PG
def test_pg_rows_persist_with_their_receipt_and_a_replay_writes_nothing(lane_store, eval_time):
    """Doc 04's U1 acceptance, against a server: rows persist, and the second capture of the same
    event is a no-op because the id is the content of the observation."""
    result = _result(_observation("Security Review", "Legal put a security review"),
                     _observation("Budget Freeze", "procurement froze the budget",
                                  confidence_bp=8200))
    first = capture_unclassified(result, org_id=ORG, event_id=EVENT, source_text=SOURCE,
                                 eval_time=eval_time, store=lane_store)
    second = capture_unclassified(result, org_id=ORG, event_id=EVENT, source_text=SOURCE,
                                  eval_time=eval_time + timedelta(days=2), store=lane_store)

    assert (first.stored, second.stored) == (2, 0)
    rows = lane_store.observations_for(org_id=ORG, event_id=EVENT)
    stored = {row.proposed_kind: row for row in rows}
    assert set(stored) == {"security_review", "budget_freeze"}
    assert stored["security_review"].quote == "Legal put a security review"
    assert stored["security_review"].start_offset == SOURCE.find("Legal put a security review")
    assert stored["security_review"].verified is True
    assert stored["security_review"].span_verdict == SpanVerdict.VERIFIED.value
    assert stored["budget_freeze"].confidence_bp == 8200
    assert stored["budget_freeze"].created_at == eval_time


@_PG
def test_pg_and_memory_report_the_same_thing_from_the_same_rows(lane_store, eval_time):
    """Two implementations of one contract, run over identical rows.

    This is the only thing that keeps the SQL and `_aggregate` honest with each other. Without
    it the hermetic tests above would be asserting a Python function the product never calls,
    and the query that ships would be unverified.
    """
    memory = InMemoryOpenLaneStore()
    rows: list[ObservationRow] = []
    for index, (kind, org, verified, days) in enumerate([
            ("budget_freeze", ORG, True, 2), ("budget_freeze", ORG, True, 3),
            ("budget_freeze", "org_open_lane_b", True, 4),
            ("budget_freeze", "org_open_lane_b", True, 5),
            ("budget_freeze", ORG, True, 6), ("budget_freeze", ORG, False, 7),
            ("security_review", ORG, True, 2), ("security_review", ORG, True, 3),
            ("champion_loss", ORG, True, 1)]):                       # under the bar, excluded
        rows.append(ObservationRow(
            observation_id=f"obs_pg_{index}", org_id=org, event_id=f"{EVENT}_{index}",
            proposed_kind=kind, proposed_kind_raw=kind, description="d",
            quote=f"quote {index}", source_ref=SOURCE_REF, start_offset=0, end_offset=7,
            confidence_bp=6000 + index, verified=verified,
            span_verdict=SpanVerdict.VERIFIED.value if verified else SpanVerdict.UNVERIFIED.value,
            created_at=eval_time - timedelta(days=days)))
    assert lane_store.add(rows) == len(rows)
    memory.add(rows)

    # 0 and the cap are the two values at which a missing clamp is INVISIBLE, so the range has
    # to reach past the cap: the SQL slices `array_agg` with the module constant and a Python
    # aggregation that trusted the caller's number returned six customer quotes where the server
    # returns three.
    for examples in (0, 1, MAX_EXAMPLE_QUOTES, MAX_EXAMPLE_QUOTES + 1, 99):
        from_pg = lane_store.candidates(eval_time=eval_time, window_days=DISCOVERY_WINDOW_DAYS,
                                        min_occurrences=PROMOTION_MIN_OCCURRENCES,
                                        examples=examples)
        from_memory = memory.candidates(eval_time=eval_time, window_days=DISCOVERY_WINDOW_DAYS,
                                        min_occurrences=PROMOTION_MIN_OCCURRENCES,
                                        examples=examples)
        assert from_pg == from_memory, f"the two stores disagree at examples={examples}"
        assert len(from_pg[0].example_quotes) <= MAX_EXAMPLE_QUOTES
    assert [row.proposed_kind for row in from_pg] == ["budget_freeze"]
    assert (from_pg[0].occurrences, from_pg[0].verified_occurrences, from_pg[0].orgs) == (6, 5, 2)
    assert from_pg[0].example_quotes == ("quote 0", "quote 1", "quote 2")


@_PG
def test_pg_promotion_stamps_history_and_removes_the_kind_from_the_report(lane_store, eval_time):
    """The `update … where proposed_kind = :k and promoted_to is null` and the report's
    already-promoted exclusion, both against the server that runs them in production."""
    capture_unclassified(_result(*[
        _observation("Budget Freeze", quote) for quote in
        ["Legal put a security review", "procurement froze the budget", "until April",
         "Our champion Priya", "moved to a new team"]]),
        org_id=ORG, event_id=EVENT, source_text=SOURCE, eval_time=eval_time - timedelta(days=1),
        store=lane_store)

    promotion = promote_kind(lane_store, _decision(), eval_time=eval_time)

    assert promotion.rows_marked == PROMOTION_MIN_OCCURRENCES
    assert lane_store.promotion_of("budget_freeze") == "budget_freeze"
    assert discovery_report(lane_store, eval_time=eval_time).rows == ()
    stamped = lane_store.observations_for(org_id=ORG, event_id=EVENT)
    assert {row.promoted_by for row in stamped} == {"harsh@genios"}
    assert {row.promoted_schema_version for row in stamped} == {"2026.2"}
    with pytest.raises(PromotionRefused, match="already promoted"):
        promote_kind(lane_store, _decision(schema_version_after="2026.3"), eval_time=eval_time)


@_PG
def test_pg_purge_enforces_the_180_day_clock_and_spares_promoted_rows(lane_store, eval_time):
    """The retention clock the heartbeat calls. `promoted_to` is exempt, so the provenance of a
    vocabulary member survives the window it was discovered in."""
    old = eval_time - timedelta(days=OPEN_LANE_RETENTION_DAYS + 10)
    rows = [ObservationRow(
        observation_id=f"obs_purge_{index}", org_id=ORG, event_id=f"{EVENT}_{index}",
        proposed_kind="stale_kind", proposed_kind_raw="stale kind", description="d",
        quote=f"quote {index}", source_ref=SOURCE_REF, start_offset=0, end_offset=7,
        confidence_bp=5000, verified=True, span_verdict=SpanVerdict.VERIFIED.value,
        created_at=old, promoted_to="stale_kind" if index == 0 else None)
        for index in range(4)]
    fresh = ObservationRow(**{**rows[0].__dict__, "observation_id": "obs_purge_fresh",
                              "promoted_to": None, "created_at": eval_time})
    lane_store.add(rows + [fresh])

    assert lane_store.purge_expired(eval_time=eval_time) == 3
    remaining = {row.observation_id for row in
                 lane_store.observations_for(org_id=ORG, event_id=f"{EVENT}_0")}
    assert remaining == {"obs_purge_0", "obs_purge_fresh"}


@_PG
def test_pg_tenant_erasure_removes_the_lane(lane_store, lane_engine, eval_time):
    """The erasure list is a list of table NAMES executed as `delete from <t> where org_id=:o`.
    Membership alone proves nothing — this runs that exact statement for every listed table and
    asserts the lane came back empty for the erased org and untouched for the other one."""
    from sqlalchemy import text as sql

    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    for org in _ORGS:
        capture_unclassified(_result(_observation("Security Review",
                                                  "Legal put a security review")),
                             org_id=org, event_id=EVENT, source_text=SOURCE,
                             eval_time=eval_time, store=lane_store)

    with lane_engine.begin() as conn:
        for table in _ORG_SCOPED_TABLES:
            conn.execute(sql(f"delete from {table} where org_id=:o"), {"o": ORG})

    assert lane_store.observations_for(org_id=ORG, event_id=EVENT) == ()
    assert len(lane_store.observations_for(org_id=_ORGS[1], event_id=EVENT)) == 1


@_PG
def test_pg_the_discovery_report_is_reachable_from_the_admin_console(lane_store, eval_time):
    """U3's acceptance in doc 04 is three clauses: the report runs, returns rows, and is reachable
    from the admin console. The first two are asserted above; this is the third, called through
    the endpoint's own handler rather than through a route table — a registered path that raises
    is not reachable.

    `examples` is asserted separately from the default call because it is the one place this
    console returns message CONTENT: opt-in, capped, verified quotes only.
    """
    from genios_engine.api import admin_routes
    from genios_engine.platform.auth import AuthCtx

    now = datetime.now(_timezone.utc)
    _seed(lane_store, "budget_freeze", n=6, at=now - timedelta(days=2))
    ctx = AuthCtx(org_id=ORG, actor_id="admin@genios", source="jwt")

    plain = admin_routes.discovery(days=30, min_occurrences=5, examples=0, ctx=ctx)
    reported = {row["proposed_kind"]: row for row in plain["rows"]}
    assert reported["budget_freeze"]["occurrences"] == 6
    assert reported["budget_freeze"]["verified_occurrences"] == 6
    assert reported["budget_freeze"]["promotable"] is True
    assert reported["budget_freeze"]["example_quotes"] == []      # content is opt-in
    assert plain["window_days"] == 30 and plain["min_occurrences"] == 5

    with_quotes = admin_routes.discovery(days=30, min_occurrences=5, examples=2, ctx=ctx)
    quoted = {row["proposed_kind"]: row for row in with_quotes["rows"]}
    assert len(quoted["budget_freeze"]["example_quotes"]) == 2


@_PG
def test_pg_the_promotion_gate_is_reachable_from_the_admin_console(lane_store, eval_time):
    """U2's other half of the same acceptance clause, and the one that was missing.

    `discovery_report` had a door (`GET /admin/discovery`); `promote_kind` had none, so the open
    lane could report for ever and the closed vocabulary could never grow from it — every
    discovery review ended in a report nobody could act on. Called through the endpoint's own
    handler, because a registered path that raises is not reachable.

    `decided_by` is asserted to be the AUTHENTICATED admin and not a body field: the whole point
    of the unit is that a promotion is an act somebody signed, and a signature the caller types
    is not one.
    """
    from genios_engine.api import admin_routes
    from genios_engine.platform.auth import AuthCtx

    now = datetime.now(_timezone.utc)
    _seed(lane_store, "budget_freeze", n=6, at=now - timedelta(days=2))
    ctx = AuthCtx(org_id=ORG, actor_id="admin@genios", source="jwt")
    body = admin_routes.PromotionBody(
        proposed_kind="budget_freeze", vocabulary_member="budget_freeze",
        schema_version_before="2026.1", schema_version_after="2026.2")

    promoted = admin_routes.promote_discovery_kind(body, ctx=ctx)

    assert promoted["decided_by"] == "admin@genios"
    assert promoted["rows_marked"] == 6
    assert promoted["vocabulary_member"] == "budget_freeze"
    assert "vocabulary.py" in promoted["vocabulary_edit"], (
        "the response does not tell the admin about the CODE half; the data half alone changes "
        "nothing about what gets extracted")
    assert lane_store.promotion_of("budget_freeze") == "budget_freeze"
    # and the report stops proposing what was just promoted
    assert admin_routes.discovery(days=30, min_occurrences=5, examples=0, ctx=ctx)["rows"] == []


@_PG
def test_pg_the_admin_console_refuses_a_promotion_the_unit_refuses(lane_store, eval_time):
    """Every refusal `promote_kind` makes has to survive the trip through the endpoint as a
    status a caller can act on, not as a 500. 409 rather than 400: each one is about the STATE of
    the evidence or the vocabulary, and the remedy is to change that state."""
    from fastapi import HTTPException

    from genios_engine.api import admin_routes
    from genios_engine.platform.auth import AuthCtx

    now = datetime.now(_timezone.utc)
    _seed(lane_store, "budget_freeze", n=6, at=now - timedelta(days=2))
    ctx = AuthCtx(org_id=ORG, actor_id="admin@genios", source="jwt")

    for body, why in (
        (admin_routes.PromotionBody(proposed_kind="budget_freeze",
                                    vocabulary_member="Budget Freeze",
                                    schema_version_before="2026.1",
                                    schema_version_after="2026.2"), "not snake_case"),
        (admin_routes.PromotionBody(proposed_kind="budget_freeze",
                                    vocabulary_member="budget_freeze",
                                    schema_version_before="2026.1",
                                    schema_version_after="2026.1"), "version not bumped"),
        (admin_routes.PromotionBody(proposed_kind="never_seen_at_all",
                                    vocabulary_member="never_seen_at_all",
                                    schema_version_before="2026.1",
                                    schema_version_after="2026.2"), "no evidence"),
    ):
        with pytest.raises(HTTPException) as raised:
            admin_routes.promote_discovery_kind(body, ctx=ctx)
        assert raised.value.status_code == 409, f"{why} came back as {raised.value.status_code}"
    assert lane_store.promotion_of("budget_freeze") is None, "a refused promotion stamped rows"


def test_the_store_never_hands_back_more_quotes_than_the_cap(store, eval_time):
    """`discovery_report` clamps `examples`; the STORE is a two-implementation seam and must clamp
    it too.

    `MAX_EXAMPLE_QUOTES` bounds how much customer message content crosses the cross-org admin
    boundary in one row. Postgres enforces it inside the `array_agg` slice — "never a caller's
    number" — so a Python aggregation that obeyed the caller was not merely a different answer,
    it was the LOOSER of the two: the hermetic store handed out every verified quote it had while
    production handed out three, and the disagreement was reachable from any caller holding the
    store rather than the report.
    """
    _seed(store, "budget_freeze", n=8, at=eval_time - timedelta(days=2))

    for examples in (MAX_EXAMPLE_QUOTES + 1, 99):
        (row,) = store.candidates(eval_time=eval_time, window_days=DISCOVERY_WINDOW_DAYS,
                                  min_occurrences=PROMOTION_MIN_OCCURRENCES, examples=examples)
        assert row.occurrences == 8
        assert len(row.example_quotes) == MAX_EXAMPLE_QUOTES, examples

    # and below the cap the caller's smaller number is still honoured
    (row,) = store.candidates(eval_time=eval_time, window_days=DISCOVERY_WINDOW_DAYS,
                              min_occurrences=PROMOTION_MIN_OCCURRENCES, examples=1)
    assert len(row.example_quotes) == 1
