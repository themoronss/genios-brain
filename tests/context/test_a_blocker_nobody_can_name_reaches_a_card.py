"""The fourth field the dependency correlator publishes, and the only one nothing read.

`correlation_dependency` resolves both ends of every dependency claim. When the BLOCKED end
resolves and the BLOCKER end does not, it refuses to invent a node — *"a false chain is worse than
a missing one"* — and files a typed absence carrying the name and the sentence that named it.
`MissingPrerequisite` gives its own examples: *"Finance", "legal", "the security review"*.

Those are usually not resolver failures. They are real blockers that were never people in a
mailbox, so the graph is correct to hold no node for them — and the dependency is real anyway. It
was computed on every sweep since the correlator shipped and selected by no query in the engine.

THE SHARPEST TEST HERE IS `test_the_card_may_not_say_nobody_is_there_unless_we_looked`. The
correlator's header draws the line and this reading is the first thing able to cross it: *"'we
could not find the blocker' is not the same claim as 'the blocker does not exist', and only the
second one licenses telling a human there is nobody there."* One is a fact about a search; the
other is a fact about the world.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.blocker_situations import (ANCHOR_UNNAMED_BLOCKER, BLOCKER_FIELD,
                                                      MAX_PER_NODE, blocker_key,
                                                      gather_unnamed_blockers,
                                                      read_unnamed_blockers)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "o"
PERSON = "n_rohit"


def _absence(named="Finance", quote="we're blocked on Finance until they sign off",
             absence_type="unknowable") -> dict:
    entry: dict = {
        "blocker_named": named,
        "absence": {"subject_node_id": PERSON, "expected_fact": "dependency.blocker",
                    "absence_type": absence_type, "coverage_ready": None, "coverage_basis": None},
    }
    if quote is not None:
        entry["evidence"] = [{"quote": quote, "start_offset": 0, "end_offset": len(quote),
                              "verified": False, "source_ref": "prepared_content:pc_x"}]
    return entry


def _rows(*entries, node=PERSON) -> dict:
    return {node: {"absences": list(entries)}}


def _facts(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


def _read(rows):
    return read_unnamed_blockers(rows, NOW)


# ── the reading exists at all ────────────────────────────────────────────────────────────────

def test_a_named_blocker_becomes_a_finding() -> None:
    [finding] = _read(_rows(_absence()))
    facts = _facts(finding)
    assert finding.anchor == ANCHOR_UNNAMED_BLOCKER
    assert finding.concerns_node == PERSON
    assert facts["blocker.named"] == "Finance"
    assert facts["blocker.quote"] == "we're blocked on Finance until they sign off"


def test_the_field_is_spelled_once_and_imported_from_its_writer() -> None:
    """`correlation_dependency` builds the name from `FACT_PREFIX`, so a literal here would keep
    selecting nothing the day the prefix moved. The same trap `condition_situations` records
    against its own twin, and what `test_nothing_is_written_and_never_read` hunts."""
    from genios_engine.context.correlation_dependency import FIELD_MISSING_PREREQUISITE

    assert BLOCKER_FIELD is FIELD_MISSING_PREREQUISITE


def test_the_anchor_routes_to_a_situation_type() -> None:
    """A reading whose anchor no domain declares is SILENTLY SKIPPED — the failure mode
    `condition-now-satisfied` sat in for months, authored and approved and bound to nothing."""
    from genios_engine.context.domain_spec import domains_declaring, spec_for

    assert domains_declaring(ANCHOR_UNNAMED_BLOCKER) == ("admin",)
    assert spec_for("admin").type_for(ANCHOR_UNNAMED_BLOCKER) == "blocked_on_unnamed"


def test_the_reading_is_dispatched_on_a_sweep() -> None:
    """Being written is not being read — the whole reason this module exists."""
    from genios_engine.context.outreach_situations import READINGS

    assert ANCHOR_UNNAMED_BLOCKER in {anchor for anchor, _ in READINGS}


# ── the claim the card is not allowed to make ────────────────────────────────────────────────

def test_the_card_may_not_say_nobody_is_there_unless_we_looked() -> None:
    """THE LINE THE CORRELATOR DRAWS, AND THIS IS THE FIRST THING ABLE TO CROSS IT.
    `AbsenceType.GENUINELY_ABSENT` is reached only when a coverage basis was declared; everything
    else is `UNKNOWABLE`. "We could not find it" is a fact about this system. "It is not in your
    records" is a claim about the world, and only the second one lets somebody stop waiting.
    """
    [weak] = _read(_rows(_absence(absence_type="unknowable")))
    assert _facts(weak)["blocker.we_searched"] is False
    assert "could not find" in weak.display_name
    assert "not in your records" not in weak.display_name

    [strong] = _read(_rows(_absence(absence_type="genuinely_absent")))
    assert _facts(strong)["blocker.we_searched"] is True
    assert "not in your records" in strong.display_name


def test_an_unrecognised_absence_type_reads_as_the_weaker_claim() -> None:
    """A value this reading does not know is not a licence. Absent, misspelled, renamed upstream —
    each lands on "we could not find it", which is the sentence that is always true."""
    for value in (None, "", "genuinely absent", "GENUINELY_ABSENT_LATER", "unknown"):
        [finding] = _read(_rows(_absence(absence_type=value)))
        assert _facts(finding)["blocker.we_searched"] is False, value
        assert "could not find" in finding.display_name


def test_the_gaps_are_declared_rather_than_discovered() -> None:
    """`blocker.identity` is absent BY DEFINITION — the absence is the finding — and
    `blocker.stated_at` for a duller reason: the published payload carries no timestamp anywhere,
    so nothing here can say how long this has been true without inventing it from the sweep."""
    [finding] = _read(_rows(_absence()))
    assert finding.missing == ["blocker.identity", "blocker.stated_at"]
    assert not any(name.endswith("age_days") or name.endswith("stated_at")
                   for name, _v, _k in finding.facts)


# ── one finding per absence, and they end separately ─────────────────────────────────────────

def test_two_blockers_on_one_subject_are_two_findings() -> None:
    """They end one at a time: the day "Finance" resolves, that absence is gone and "the security
    review" is still open. One card per subject would close both or neither."""
    findings = _read(_rows(_absence("Finance"), _absence("the security review")))
    assert len(findings) == 2
    assert len({f.canonical_key for f in findings}) == 2
    assert {_facts(f)["blocker.named"] for f in findings} == {"Finance", "the security review"}


def test_the_same_blocker_named_twice_is_one_key() -> None:
    """Content-addressed and case/whitespace-insensitive, so "Finance" and " finance " are one
    absence rather than two cards saying the same sentence."""
    assert blocker_key(PERSON, "Finance") == blocker_key(PERSON, "  finance ")
    assert blocker_key(PERSON, "Finance") != blocker_key("n_other", "Finance")


def test_a_blocker_whose_name_has_a_delimiter_in_it_is_still_safe() -> None:
    """The name is FREE TEXT from a counterparty's sentence and the canonical key is parsed on a
    delimiter elsewhere in this layer, so it is hashed rather than interpolated."""
    [finding] = _read(_rows(_absence("legal: the india entity")))
    assert finding.canonical_key.count(":") == 1
    assert finding.canonical_key.startswith("blocker:")


# ── what does not become a card ──────────────────────────────────────────────────────────────

def test_an_absence_with_no_name_is_not_a_finding() -> None:
    """"Somebody is blocked by something" is not a card — the name is the only actionable part."""
    assert _read(_rows(_absence(named="   "))) == []
    assert _read(_rows({"absence": {"absence_type": "unknowable"}})) == []


def test_a_missing_quote_does_not_drop_a_real_blocker() -> None:
    """A claim reaching this point already passed `DependencyLink`'s evidence gate, so an absent
    quote here means the span did not survive serialisation. Dropping the finding for that would
    hide a real blocker to protect a formatting detail."""
    [finding] = _read(_rows(_absence(quote=None)))
    assert _facts(finding)["blocker.named"] == "Finance"
    assert "blocker.quote" not in _facts(finding)


def test_a_reserved_key_is_not_a_node() -> None:
    """`_gather` stamps reserved keys onto the same mapping the readers iterate."""
    rows = dict(_rows(_absence()))
    rows["_mailbox_owner"] = "someone@example.com"
    assert len(_read(rows)) == 1


@pytest.mark.parametrize("value", ["not json", "[]", '{"absences": "Finance"}', 42, None, {}])
def test_a_malformed_row_is_one_silent_blocker_and_never_an_exception(value) -> None:
    """A malformed row costs one finding; a raise costs every blocker on the tenant."""
    assert _read({PERSON: value}) == []


def test_the_stored_json_may_arrive_as_a_string() -> None:
    """Postgres hands back a mapping; a driver that has not decoded `jsonb` hands back text."""
    import json

    assert len(_read({PERSON: json.dumps({"absences": [_absence()]})})) == 1


def test_one_busy_subject_cannot_fill_a_feed() -> None:
    """Bounded like every reader here, and cut on a STABLE order — an unstable cut would open and
    close the same card on alternating sweeps."""
    many = [_absence(f"blocker {i:02d}") for i in range(MAX_PER_NODE + 4)]
    first = [_facts(f)["blocker.named"] for f in _read(_rows(*many))]
    second = [_facts(f)["blocker.named"] for f in _read(_rows(*reversed(many)))]
    assert len(first) == MAX_PER_NODE
    assert first == second


# ── end to end, through the query that actually runs ─────────────────────────────────────────

def test_the_gather_reads_what_the_correlator_wrote() -> None:
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table graph_facts (org_id text, subject_node_id text, field text, "
                       "value text, status text, valid_to text)"))
        c.execute(text("insert into graph_facts values (:o,:n,:f,:v,'active',null)"),
                  {"o": ORG, "n": PERSON, "f": BLOCKER_FIELD,
                   "v": '{"absences": [{"blocker_named": "legal"}]}'})
        # A retired row and another tenant's row are both invisible.
        c.execute(text("insert into graph_facts values (:o,:n,:f,:v,'active','2026-01-01')"),
                  {"o": ORG, "n": "n_old", "f": BLOCKER_FIELD, "v": "{}"})
        c.execute(text("insert into graph_facts values ('other',:n,:f,:v,'active',null)"),
                  {"n": "n_them", "f": BLOCKER_FIELD, "v": "{}"})
        held = gather_unnamed_blockers(c, ORG)

    assert set(held) == {PERSON}
    [finding] = _read(held)
    assert _facts(finding)["blocker.named"] == "legal"
