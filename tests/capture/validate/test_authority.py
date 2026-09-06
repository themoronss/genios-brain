"""G1 · ALG-14 (L1.5.8-U1) — the authority ranking table.

*A signed PDF is not a Slack aside.* Everything below tests one of three properties, and
each is a property the rest of Layer 1 silently depends on:

* **The table is the doc's table.** Seven classes, the exact seven ranks doc 05 prints, and
  the exact seven ``evidence_authority_multiplier_bp`` values doc 06 prints. A drifted row
  is invisible at every call site and re-tunes conflict resolution globally.
* **The order is strict and total.** ALG-12 subtracts two ranks and resolves on a gap of
  >= 2. That arithmetic is only meaningful if every pair of classes is comparable and no two
  classes share a rank — a duplicate rank turns an authority resolution into a coin-flip.
* **It never raises, and an unknown provenance falls to the floor.** Doc 05's acceptance is
  literal: "unmapped prefix -> rank 0 and a logged warning, never a crash." Ranking high on
  an unknown source is the one failure that cannot be walked back, because a rank-6 unknown
  wins every conflict it touches.

The last block reconciles ALG-14's 0..6 scale with the partial 0..4 table that already
exists at ``capture/internal_knowledge.py``, by asserting against Layer 2's real
``FACT_CONF_BY_RANK`` rather than against a restated copy of it.
"""

from __future__ import annotations

import dataclasses
import itertools
import logging

import pytest

from genios_engine.capture.internal_knowledge import (CANON_AUTHORITY_RANK,
                                                      OBSERVED_AUTHORITY_RANK, is_canon)
from genios_engine.capture.validate.authority import (AUTHORITY_RANK, LEGACY_RANK,
                                                      MAX_AUTHORITY_RANK,
                                                      OBJECT_TYPE_AUTHORITY,
                                                      RANK_MULTIPLIER_BP, SOURCE_AUTHORITY,
                                                      SOURCE_OBJECT_AUTHORITY,
                                                      SOURCE_REF_PREFIX_AUTHORITY,
                                                      UNMAPPED_AUTHORITY, Authority,
                                                      AuthorityBasis, AuthorityWeight,
                                                      Provenance, multiplier_bp_of, rank_of,
                                                      to_legacy_rank, weigh_authority)
from genios_engine.context.pipeline import FACT_CONF_BY_RANK

WAVE = "W1"
GATE = "G1"

LOGGER_NAME = "genios_engine.capture.validate.authority"

#: Doc 05's table, strongest first. Restated here rather than imported so the test asserts
#: against the DOCUMENT; deriving it from `AUTHORITY_RANK` would make every assertion below
#: tautological — the classic test that cannot fail.
SPEC_LADDER: tuple[tuple[Authority, int], ...] = (
    (Authority.SIGNED_DOCUMENT, 6),
    (Authority.COMPANY_CANON, 5),
    (Authority.STRUCTURED_SOURCE, 4),
    (Authority.ATTACHMENT, 3),
    (Authority.EMAIL_PROSE, 2),
    (Authority.CHAT_ASIDE, 1),
    (Authority.INFERRED, 0),
)

#: Doc 06, ALG-17 term 6 — `evidence_authority_multiplier_bp`, restated from the doc.
SPEC_MULTIPLIER_BP: tuple[tuple[int, int], ...] = (
    (6, 10000), (5, 9500), (4, 9000), (3, 8500), (2, 8000), (1, 6500), (0, 4000),
)

STRONGEST_FIRST: tuple[Authority, ...] = tuple(a for a, _ in SPEC_LADDER)


# ── the table itself ──────────────────────────────────────────────────────────────────

@pytest.mark.parametrize(("authority", "expected_rank"), SPEC_LADDER,
                         ids=[a.value for a, _ in SPEC_LADDER])
def test_each_class_carries_the_rank_doc_05_prints(authority: Authority,
                                                   expected_rank: int) -> None:
    """One row per row of the spec table. These seven integers ARE the algorithm."""
    assert rank_of(authority) == expected_rank


def test_the_table_covers_the_contract_enum_exactly() -> None:
    """A class with no row would raise `KeyError` inside a capture sync; a row with no class
    is a rank nothing can ever reach. Both are caught by comparing the two sets."""
    assert set(AUTHORITY_RANK) == set(Authority)


def test_ranks_are_distinct_so_the_order_is_strict() -> None:
    """Two classes sharing a rank makes them indistinguishable to ALG-12, which then falls
    through to the recency tie-break — a newer email quietly beating an older contract."""
    ranks = [rank_of(a) for a in Authority]
    assert sorted(ranks) == sorted(set(ranks))


def test_the_table_spans_zero_to_the_contract_ceiling() -> None:
    """`ConflictClaim.authority_rank` refuses anything above `MAX_AUTHORITY_RANK`, so a table
    whose top exceeded it would produce weights that cannot be stored on a conflict."""
    ranks = [rank_of(a) for a in Authority]
    assert min(ranks) == 0
    assert max(ranks) == MAX_AUTHORITY_RANK


@pytest.mark.parametrize("authority", list(Authority), ids=[a.value for a in Authority])
def test_ranks_are_exact_integers(authority: Authority) -> None:
    """No float, and no bool wearing an int's type — a `True` in this table compares equal to
    rank 1 and would silently rank a class as a chat aside."""
    rank = rank_of(authority)
    assert type(rank) is int


# ── the order ALG-12 subtracts across ─────────────────────────────────────────────────

@pytest.mark.parametrize(("stronger", "weaker"),
                         list(itertools.combinations(STRONGEST_FIRST, 2)),
                         ids=[f"{s.value}>{w.value}"
                              for s, w in itertools.combinations(STRONGEST_FIRST, 2)])
def test_every_pair_ordering_the_spec_asserts(stronger: Authority,
                                              weaker: Authority) -> None:
    """All 21 ordered pairs of the doc's ladder: a signed contract over canon over a CRM
    field over an attachment over email prose over a chat aside over an inference."""
    assert rank_of(stronger) > rank_of(weaker)


@pytest.mark.parametrize(("left", "right"),
                         list(itertools.permutations(list(Authority), 2)),
                         ids=[f"{a.value}|{b.value}"
                              for a, b in itertools.permutations(list(Authority), 2)])
def test_antisymmetry_distinct_classes_never_tie(left: Authority, right: Authority) -> None:
    """Totality's first half: any two distinct classes are comparable, and exactly one of the
    two directions holds."""
    assert (rank_of(left) > rank_of(right)) != (rank_of(right) > rank_of(left))


@pytest.mark.parametrize(("low", "mid", "high"),
                         list(itertools.permutations(list(Authority), 3)),
                         ids=[f"{a.value}.{b.value}.{c.value}"
                              for a, b, c in itertools.permutations(list(Authority), 3)])
def test_transitivity_over_the_full_source_set(low: Authority, mid: Authority,
                                               high: Authority) -> None:
    """Totality's second half, over every ordered triple. Integer ranks give this for free
    today — the test is here so that a future 'special case' comparison function cannot be
    introduced without the contradiction it creates showing up immediately."""
    if rank_of(high) > rank_of(mid) and rank_of(mid) > rank_of(low):
        assert rank_of(high) > rank_of(low)


def test_signed_document_clears_email_prose_by_the_gap_alg12_requires() -> None:
    """The G5 gate fixture in one line: the \\$74K signed contract must outrank the \\$84K
    email body by >= 2, or ALG-12 surfaces both with no recommendation and the worked example
    is unreproducible."""
    gap = rank_of(Authority.SIGNED_DOCUMENT) - rank_of(Authority.EMAIL_PROSE)
    assert gap >= 2


def test_adjacent_classes_never_auto_resolve() -> None:
    """The other side of the same rule, and the reason the ladder is evenly spaced: one step
    of authority is not enough to silence the other side, so no neighbouring pair may open a
    gap of 2."""
    for stronger, weaker in zip(STRONGEST_FIRST, STRONGEST_FIRST[1:]):
        assert rank_of(stronger) - rank_of(weaker) == 1


# ── the importance multiplier (ALG-17 term 6) ─────────────────────────────────────────

@pytest.mark.parametrize(("rank", "expected_bp"), SPEC_MULTIPLIER_BP,
                         ids=[f"rank{r}" for r, _ in SPEC_MULTIPLIER_BP])
def test_multiplier_is_the_bp_ladder_doc_06_prints(rank: int, expected_bp: int) -> None:
    """One row per row of doc 06's `evidence_authority_multiplier_bp` block."""
    assert RANK_MULTIPLIER_BP[rank] == expected_bp


@pytest.mark.parametrize("authority", list(Authority), ids=[a.value for a in Authority])
def test_multiplier_bp_of_is_total_and_in_range(authority: Authority) -> None:
    """Every class resolves to integer basis points inside 0..10000. A multiplier outside the
    range would scale importance past the scorer's own ceiling."""
    bp = multiplier_bp_of(authority)
    assert type(bp) is int
    assert 0 <= bp <= 10000


def test_multiplier_rises_with_rank() -> None:
    """The multiplier and the rank must agree about which source is stronger. If they ever
    disagreed, a signal could resolve a conflict by authority and then be ranked below the
    claim it beat."""
    by_rank = [RANK_MULTIPLIER_BP[rank_of(a)] for a in STRONGEST_FIRST]
    assert by_rank == sorted(by_rank, reverse=True)
    assert len(set(by_rank)) == len(by_rank)


def test_the_floor_discounts_rather_than_erases() -> None:
    """Rank 0 must not multiply to zero: an unrecognised provenance is a missing table row,
    and zeroing the term would delete the signal instead of discounting it."""
    assert multiplier_bp_of(Authority.INFERRED) > 0


# ── classification: which table answers, and with what ────────────────────────────────

CLASSIFICATION_CASES: tuple[tuple[str, Provenance, Authority, AuthorityBasis], ...] = (
    # 1 — executed, orthogonal to everything else
    ("executed attachment is a signed document",
     Provenance(source_ref="chunk:doc-1:0", source="gmail",
                object_type="email_attachment", executed=True),
     Authority.SIGNED_DOCUMENT, AuthorityBasis.EXECUTED),
    ("executed beats a chat aside's own tables",
     Provenance(source="slack", object_type="message", executed=True),
     Authority.SIGNED_DOCUMENT, AuthorityBasis.EXECUTED),
    # 2 — company canon, via the shared intake vocabulary
    ("uploaded pricing policy is canon",
     Provenance(source_ref="chunk:policy-9:2", source="upload",
                object_type="document_chunk", internal_kind="pricing"),
     Authority.COMPANY_CANON, AuthorityBasis.COMPANY_CANON_KIND),
    ("a canon alias still reaches canon",
     Provenance(source="internal", internal_kind="rate_card"),
     Authority.COMPANY_CANON, AuthorityBasis.COMPANY_CANON_KIND),
    ("canon outranks the system-of-record table",
     Provenance(source="hubspot", object_type="deal", internal_kind="policy"),
     Authority.COMPANY_CANON, AuthorityBasis.COMPANY_CANON_KIND),
    # 3 — the (source, object_type) disambiguators
    ("a bare 'message' from slack is a chat aside",
     Provenance(source_ref="prepared_content:evt-1", source="slack", object_type="message"),
     Authority.CHAT_ASIDE, AuthorityBasis.SOURCE_OBJECT),
    ("the same object type from gmail is prose",
     Provenance(source_ref="prepared_content:evt-1", source="gmail", object_type="message"),
     Authority.EMAIL_PROSE, AuthorityBasis.OBJECT_TYPE),
    # 4 — object type beats source, so a document shared into chat stays a document
    ("a PDF chunk shared into slack is an attachment",
     Provenance(source_ref="chunk:doc-4:1", source="slack", object_type="document_chunk"),
     Authority.ATTACHMENT, AuthorityBasis.OBJECT_TYPE),
    ("an email attachment is an attachment",
     Provenance(source_ref="chunk:doc-2:0", source="gmail",
                object_type="email_attachment"),
     Authority.ATTACHMENT, AuthorityBasis.OBJECT_TYPE),
    ("an email body is prose",
     Provenance(source_ref="prepared_content:evt-7", source="gmail",
                object_type="email_message"),
     Authority.EMAIL_PROSE, AuthorityBasis.OBJECT_TYPE),
    ("a hubspot deal is a structured source of record",
     Provenance(source_ref="structured:hubspot.deal.v1#amount", source="hubspot",
                object_type="deal"),
     Authority.STRUCTURED_SOURCE, AuthorityBasis.OBJECT_TYPE),
    ("an agent action is our own inference, not evidence",
     Provenance(source="agent", object_type="action"),
     Authority.INFERRED, AuthorityBasis.OBJECT_TYPE),
    # 5 — source, for sources with exactly one class
    ("a tenant database row with an unenumerable table name",
     Provenance(source_ref="structured:postgres.invoices.v1#total", source="postgres",
                object_type="invoices"),
     Authority.STRUCTURED_SOURCE, AuthorityBasis.SOURCE),
    ("slack with no object type is still chat",
     Provenance(source_ref="prepared_content:evt-3", source="slack"),
     Authority.CHAT_ASIDE, AuthorityBasis.SOURCE),
    ("geni os output re-entering as evidence floors at inferred",
     Provenance(source_ref="prepared_content:evt-9", source="genios"),
     Authority.INFERRED, AuthorityBasis.SOURCE),
    # 6 — the source_ref prefix, the coarse fallback
    ("a structured ref alone",
     Provenance(source_ref="structured:acme.orders.v1#total"),
     Authority.STRUCTURED_SOURCE, AuthorityBasis.SOURCE_REF_PREFIX),
    ("a document chunk ref alone",
     Provenance(source_ref="chunk:doc-11:3"),
     Authority.ATTACHMENT, AuthorityBasis.SOURCE_REF_PREFIX),
    ("a prepared-content ref alone reads as prose",
     Provenance(source_ref="prepared_content:evt-42"),
     Authority.EMAIL_PROSE, AuthorityBasis.SOURCE_REF_PREFIX),
    ("an unknown source still reaches the prefix table",
     Provenance(source_ref="prepared_content:evt-42", source="carrier_pigeon"),
     Authority.EMAIL_PROSE, AuthorityBasis.SOURCE_REF_PREFIX),
    # tolerance — casing and padding are not new source types
    ("case and whitespace fold to the same row",
     Provenance(source="  SlacK ", object_type=" Message "),
     Authority.CHAT_ASIDE, AuthorityBasis.SOURCE_OBJECT),
)


@pytest.mark.parametrize(("provenance", "expected_authority", "expected_basis"),
                         [(p, a, b) for _, p, a, b in CLASSIFICATION_CASES],
                         ids=[name for name, _, _, _ in CLASSIFICATION_CASES])
def test_the_cascade_picks_the_class_and_says_which_table_answered(
        provenance: Provenance, expected_authority: Authority,
        expected_basis: AuthorityBasis) -> None:
    """One row per cascade step, plus the two ambiguous cases the ordering exists for: a bare
    `message` that is chat on one source and prose on another, and a document shared into
    chat that must stay a document."""
    weight = weigh_authority(provenance)
    assert weight.authority is expected_authority
    assert weight.basis is expected_basis
    assert weight.rank == rank_of(expected_authority)
    assert weight.recognised is True


def test_the_worked_example_resolves_the_way_the_plan_says() -> None:
    """Doc 05's fixture, ranked: the signed contract arrives as an executed attachment and the
    "\\$84K" claim as the covering email's prose. The gap must be >= 2 so ALG-12 recommends
    the contract instead of surfacing both with no guidance."""
    contract = weigh_authority(Provenance(source_ref="chunk:contract-74k:0", source="gmail",
                                          object_type="email_attachment", executed=True))
    body = weigh_authority(Provenance(source_ref="prepared_content:evt-84k", source="gmail",
                                      object_type="email_message"))
    assert contract.rank - body.rank >= 2


def test_canon_detection_is_the_intake_door_s_own_definition() -> None:
    """`is_canon` is reused rather than re-listed, so a kind cannot be canon at the upload
    door and ordinary prose here. Both directions are checked: a declared kind and an alias
    reach canon, and a tag that is not canon does not."""
    for kind in ("pricing", "rate_card", "policy", "icp"):
        assert is_canon(kind)
        assert weigh_authority(Provenance(internal_kind=kind)).authority is (
            Authority.COMPANY_CANON)
    assert not is_canon("q3-misc-notes")
    assert weigh_authority(
        Provenance(source_ref="chunk:doc-3:0", internal_kind="q3-misc-notes")
    ).authority is Authority.ATTACHMENT


def test_our_own_output_can_never_corroborate_itself() -> None:
    """Every route by which a GeniOS-generated artifact re-enters capture must land on the
    floor. Anything above it would let yesterday's inference be cited as today's evidence."""
    for provenance in (Provenance(source="agent", object_type="action"),
                       Provenance(source="genios", source_ref="prepared_content:evt-1"),
                       Provenance(source="agent", source_ref="chunk:doc-1:0")):
        assert weigh_authority(provenance).rank == 0


# ── totality: the unknown never raises and never ranks high ───────────────────────────

UNKNOWN_CASES: tuple[tuple[str, Provenance], ...] = (
    ("nothing known at all", Provenance()),
    ("an unmapped ref prefix", Provenance(source_ref="ftp:host/file.txt")),
    ("a ref with no prefix at all", Provenance(source_ref="garbage")),
    ("an empty ref", Provenance(source_ref="")),
    ("whitespace only", Provenance(source_ref="   ", source="  ", object_type="  ")),
    ("an unknown source and object type",
     Provenance(source="carrier_pigeon", object_type="scroll")),
    ("an unknown source with an unmapped prefix",
     Provenance(source_ref="fax:0012", source="fax_machine", object_type="page_scan")),
    ("a non-canon internal_kind and nothing else",
     Provenance(internal_kind="q3-misc-notes")),
    ("non-string junk from a connector payload",
     Provenance(source_ref=17, source=object(), object_type=3.5)),  # type: ignore[arg-type]
)


@pytest.mark.parametrize("provenance", [p for _, p in UNKNOWN_CASES],
                         ids=[name for name, _ in UNKNOWN_CASES])
def test_unknown_provenance_floors_at_rank_zero_instead_of_raising(
        provenance: Provenance) -> None:
    """Doc 05's acceptance: never a crash. A capture sync running unattended over real
    customer data cannot afford an exception here, and ranking an unknown HIGH is the one
    mistake that cannot be walked back — it wins every conflict it touches."""
    weight = weigh_authority(provenance)
    assert weight.authority is UNMAPPED_AUTHORITY
    assert weight.rank == 0
    assert weight.basis is AuthorityBasis.UNMAPPED
    assert weight.recognised is False


def test_the_floor_is_logged_so_the_missing_row_gets_added(
        caplog: pytest.LogCaptureFixture) -> None:
    """The other half of the acceptance line. A silent floor is indistinguishable from a
    correct answer, and the source stays under-ranked for as long as nobody looks."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    weigh_authority(Provenance(source="carrier_pigeon", object_type="scroll"))
    warnings = [r for r in caplog.records
                if r.name == LOGGER_NAME and r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "carrier_pigeon" in warnings[0].getMessage()


def test_a_recognised_provenance_logs_nothing(caplog: pytest.LogCaptureFixture) -> None:
    """The warning has to mean something. If a mapped source warned too, the signal would be
    noise inside the first hour of a real sync."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    weigh_authority(Provenance(source="gmail", object_type="email_message"))
    assert [r for r in caplog.records if r.name == LOGGER_NAME] == []


def test_the_same_provenance_always_ranks_the_same() -> None:
    """Replay determinism. Ranking feeds importance, importance feeds the founder's list
    order, and a list that re-orders on a re-run is a product nobody trusts twice."""
    provenance = Provenance(source_ref="chunk:doc-5:2", source="gmail",
                            object_type="email_attachment")
    first = weigh_authority(provenance)
    assert [weigh_authority(provenance) for _ in range(5)] == [first] * 5


# ── the tables are data, and data that cannot be edited at runtime ────────────────────

@pytest.mark.parametrize(("name", "table"), [
    ("AUTHORITY_RANK", AUTHORITY_RANK),
    ("RANK_MULTIPLIER_BP", RANK_MULTIPLIER_BP),
    ("SOURCE_REF_PREFIX_AUTHORITY", SOURCE_REF_PREFIX_AUTHORITY),
    ("SOURCE_OBJECT_AUTHORITY", SOURCE_OBJECT_AUTHORITY),
    ("OBJECT_TYPE_AUTHORITY", OBJECT_TYPE_AUTHORITY),
    ("SOURCE_AUTHORITY", SOURCE_AUTHORITY),
    ("LEGACY_RANK", LEGACY_RANK),
])
def test_tables_are_read_only(name: str, table: dict) -> None:
    """A module-level dict any importer can write to is a global that silently re-ranks every
    conflict in the process — and it would be invisible in a code review of this file."""
    with pytest.raises(TypeError):
        table["injected"] = Authority.SIGNED_DOCUMENT  # type: ignore[index]


@pytest.mark.parametrize("table", [SOURCE_REF_PREFIX_AUTHORITY, SOURCE_OBJECT_AUTHORITY,
                                   OBJECT_TYPE_AUTHORITY, SOURCE_AUTHORITY],
                         ids=["prefix", "source_object", "object_type", "source"])
def test_every_classification_row_points_at_a_rankable_class(table: dict) -> None:
    """A row naming a class the ranking table does not carry would raise on the one input
    that reaches it, months after the row was added."""
    for value in table.values():
        assert value in AUTHORITY_RANK


def test_the_doc_defined_ref_shapes_each_map_to_exactly_one_rank() -> None:
    """Doc 08 fixes `prepared_content:<event_id>` and `chunk:<doc_id>:<n>`; doc 03 line 385
    adds `structured:<mapping_id>#<field>`. Every prefix the documents define must be in the
    table — a missing one sends a whole lane to the floor."""
    assert set(SOURCE_REF_PREFIX_AUTHORITY) == {"prepared_content", "chunk", "structured"}
    ranks = {prefix: rank_of(authority)
             for prefix, authority in SOURCE_REF_PREFIX_AUTHORITY.items()}
    assert ranks == {"prepared_content": 2, "chunk": 3, "structured": 4}


def test_provenance_and_weight_are_frozen() -> None:
    """A provenance a caller mutates between two calls is one claim with two ranks; a weight
    whose rank can be assigned is a rank that no longer comes from the table."""
    assert dataclasses.is_dataclass(Provenance)
    with pytest.raises(dataclasses.FrozenInstanceError):
        Provenance().source = "slack"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        AuthorityWeight(Authority.CHAT_ASIDE, AuthorityBasis.SOURCE).authority = (
            Authority.SIGNED_DOCUMENT)  # type: ignore[misc]


def test_a_weight_cannot_carry_a_rank_that_disagrees_with_the_table() -> None:
    """`rank` is derived, not stored, so there is no constructor argument through which a
    hand-set rank could enter and then be rendered as "the signed document has higher
    authority" beside a number nobody can reproduce."""
    for authority in Authority:
        weight = AuthorityWeight(authority, AuthorityBasis.SOURCE)
        assert weight.rank == AUTHORITY_RANK[authority]
        assert weight.multiplier_bp == RANK_MULTIPLIER_BP[AUTHORITY_RANK[authority]]


# ── reconciliation with the partial table in capture/internal_knowledge.py ────────────

@pytest.mark.parametrize("authority", list(Authority), ids=[a.value for a in Authority])
def test_every_class_translates_to_a_live_layer_2_confidence_tier(
        authority: Authority) -> None:
    """`to_legacy_rank` is the only sanctioned crossing between ALG-14's 0..6 scale and the
    0..4 scale `FACT_CONF_BY_RANK` is keyed by. Asserting against the real dict — not a
    restated copy — is what makes this catch a `KeyError` at the Layer 2 fact write."""
    assert to_legacy_rank(authority) in FACT_CONF_BY_RANK


def test_the_two_scales_genuinely_disagree_which_is_why_the_converter_exists() -> None:
    """The hazard in one assertion. Company canon is 5 here and 4 in `internal_knowledge`,
    and ALG-14's 4 means a CRM row — so passing an ALG-14 rank straight into a legacy call
    site silently demotes the company's own written policy to a third party's inference."""
    assert rank_of(Authority.COMPANY_CANON) != CANON_AUTHORITY_RANK
    assert to_legacy_rank(Authority.COMPANY_CANON) == CANON_AUTHORITY_RANK
    assert rank_of(Authority.STRUCTURED_SOURCE) == CANON_AUTHORITY_RANK


def test_observed_prose_is_the_one_rank_the_two_scales_agree_on() -> None:
    """Email prose is 2 on both ladders, which is exactly why the disagreement above is easy
    to miss: the most common case round-trips correctly."""
    assert rank_of(Authority.EMAIL_PROSE) == OBSERVED_AUTHORITY_RANK
    assert to_legacy_rank(Authority.EMAIL_PROSE) == OBSERVED_AUTHORITY_RANK


def test_the_translation_never_inverts_the_order() -> None:
    """Lossy is acceptable — signed and canon both collapse onto legacy 4 because Layer 2 has
    no tier above canon. Inverted is not: a stronger class must never translate to a weaker
    legacy tier, or the fact write would prefer the source ALG-12 rejected."""
    for stronger, weaker in itertools.combinations(STRONGEST_FIRST, 2):
        assert to_legacy_rank(stronger) >= to_legacy_rank(weaker)


def test_the_translation_is_not_a_subtraction() -> None:
    """Guards the obvious future "simplification". `rank - 1` happens to be right for exactly
    two of the seven classes and wrong for the other five — including both ends of the ladder,
    where it would send a signed contract to legacy 5 (not a key of `FACT_CONF_BY_RANK` at
    all) and an inference to -1."""
    off_by_one = {a for a in Authority if to_legacy_rank(a) == rank_of(a) - 1}
    assert off_by_one == {Authority.COMPANY_CANON, Authority.STRUCTURED_SOURCE}
