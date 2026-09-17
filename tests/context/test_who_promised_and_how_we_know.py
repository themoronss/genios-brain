"""An owner somebody STATED and an owner we attributed are not the same claim.

`_resolve_subject` returns the named actor when the extractor named one and it resolved, and the
speaker otherwise. That fork is the provenance of every commitment owner in the system, and it was
computed and discarded on every promise: "Sunil said he would send it Friday" and an email from
Sunil saying "I'll send it Friday" produced byte-identical rows, though the first states an owner
and the second assumes one.

`quality/missing.py` names what the distinction is for — "there is a renewal, and no owner is
recorded" is not missing data, it IS the intelligence. A renewal whose owner we GUESSED is the
third state, and it was indistinguishable from a stated one.
"""
import pytest
from datetime import datetime, timedelta, timezone

from genios_engine.context.outreach_situations import read_overdue_commitments
from genios_engine.context.vocabulary import (OWNER_BASIS, OWNER_DECLARED, OWNER_INFERRED,
                                              OWNER_UNKNOWN, owner_basis)

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
OVERDUE = (NOW - timedelta(days=8)).isoformat()


# ── the vocabulary ───────────────────────────────────────────────────────────────────────────

def test_the_three_states_are_closed() -> None:
    assert OWNER_BASIS == {OWNER_DECLARED, OWNER_INFERRED, OWNER_UNKNOWN}


@pytest.mark.parametrize("stored, expected", [
    ("declared", OWNER_DECLARED),
    ("inferred", OWNER_INFERRED),
    ("unknown", OWNER_UNKNOWN),
    ("  DECLARED  ", OWNER_DECLARED),
])
def test_a_stored_basis_round_trips(stored: str, expected: str) -> None:
    assert owner_basis(stored) == expected


@pytest.mark.parametrize("legacy, expected", [
    ("declared_by_source", OWNER_DECLARED),     # documents.py, before the vocabulary existed
    ("inferred_from_qes", OWNER_INFERRED),      # qes_adapter.py, same
])
def test_the_two_dialects_already_in_the_tables_still_classify(legacy: str, expected: str) -> None:
    """Mapped rather than migrated: nothing reads these rows, so a migration would be motion with
    no beneficiary, while a reader that understands them keeps every historical row usable."""
    assert owner_basis(legacy) == expected


@pytest.mark.parametrize("value", [None, "", "   ", "nonsense", 7, object()])
def test_anything_unplaceable_is_unknown_and_never_declared(value: object) -> None:
    """The failure this refuses: a value we cannot interpret being read as a statement somebody
    made. Unknown is the conservative answer, exactly as it is for a merge proposal whose
    strength we cannot size."""
    assert owner_basis(value) == OWNER_UNKNOWN


# ── what the pipeline records ────────────────────────────────────────────────────────────────

def test_the_pipeline_writes_declared_when_the_extractor_named_the_actor() -> None:
    """Read off the source: the basis is decided by the same fork that decides the owner, so the
    two can never disagree about which one happened."""
    import inspect

    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "named_actor = _resolve_subject(cm.get(\"actor\"), name_to_node, None)" in source
    assert "owner_basis = OWNER_DECLARED if named_actor else OWNER_INFERRED" in source


def test_a_relayed_promise_is_not_the_relays() -> None:
    """The fallback is POSITIONAL here, which is why U1.2 moved every other content write and
    missed this one. A promise carried by an intro network is not the network's."""
    import inspect

    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "subj = named_actor or (None if transcript_mode else speaker_node)" in source


def test_the_basis_is_never_written_without_the_owner() -> None:
    """A basis alone would describe how sure we are about a name we did not record."""
    import inspect

    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert '("commitment.owner_basis", owner_basis, "enum"))\n                               if owner_email else ())' in source


# ── what the reading carries ─────────────────────────────────────────────────────────────────

def _rows(**extra):
    base = {"_node_type": "commitment", "_name": "send the deck",
            "commitment.due_at": OVERDUE, "commitment.status": "open",
            "_owner_name": "Sunil", "_owner_key": "sunil@sanchiconnect.tech"}
    base.update(extra)
    return {"n1": base}


def _facts(rows):
    [finding] = read_overdue_commitments(rows, NOW, {})
    return dict((f[0], f[1]) for f in finding.facts)


@pytest.mark.parametrize("stored, expected", [
    (OWNER_DECLARED, OWNER_DECLARED),
    (OWNER_INFERRED, OWNER_INFERRED),
    ("declared_by_source", OWNER_DECLARED),
])
def test_the_card_carries_the_basis_it_was_given(stored: str, expected: str) -> None:
    facts = _facts(_rows(**{"commitment.owner_basis": stored}))
    assert facts["commitment.owner_basis"] == expected
    assert facts["commitment.owner"] == "Sunil"


def test_an_owner_from_the_edge_with_no_basis_fact_is_unknown() -> None:
    """A real case, not only a legacy one: the `owns` edge is written from the actor
    unconditionally, while `commitment.owner` is written only when that node resolves to an
    address. The edge can name somebody the facts do not."""
    assert _facts(_rows())["commitment.owner_basis"] == OWNER_UNKNOWN


def test_no_owner_means_no_basis() -> None:
    """Absent is left absent — the discipline this reading already keeps for the owner itself."""
    facts = _facts(_rows(_owner_name=None, _owner_key=None))
    assert "commitment.owner" not in facts
    assert "commitment.owner_basis" not in facts


def test_the_owner_is_still_named_in_the_sentence_whatever_the_basis() -> None:
    """An earlier cut withheld the name on `unknown` and that was over-hedging twice: `unknown`
    means we did not record HOW we know, not that we invented it, and withholding the name drops
    the card back to rendering the promise's own text as its subject."""
    for stored in (OWNER_DECLARED, OWNER_INFERRED, "nonsense", None):
        rows = _rows(**{"commitment.owner_basis": stored})
        [finding] = read_overdue_commitments(rows, NOW, {})
        assert finding.display_name == "Sunil — promise past due"
