"""U10 · the needs queue is written, and the sweep writes it.

    pytest tests/context/test_residue_reaches_the_sweep.py -q

`detect_residue` has measured the gap since it shipped. `needs_from_residue` turned the gap into a
question. Neither filed a row, so the executor read an empty table — built, tested, green, and called
by nothing. This is the wire.

⛔ THE TEST THAT MATTERS IS `do nothing` vs `do update`. Residue is re-derived every sweep, and a
re-derived need is always born `open`. An upsert that UPDATED would reset every closed need back to
`open` on the next sweep: a question answered "the document does not exist" would be re-asked forever,
the executor would re-fetch and re-charge each time, and the system would learn that its questions are
always eventually answered. One SQL verb undoes the exclusion rule three of four residue kinds exist
to protect.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.context import evidence_need_store, runner
from genios_engine.context.evidence_need_store import close_need, store_needs
from genios_engine.contracts.evidence import EvidenceNeed

pytestmark = pytest.mark.unit


def _need(need_id="en_1", **over):
    kwargs = dict(need_id=need_id, org_id="o", trace_id="t",
                  question="Is there source material we have not fetched?",
                  why_it_matters="The situation cannot publish without it.",
                  subject_ref="signal:SIG-1")
    kwargs.update(over)
    return EvidenceNeed(**kwargs)


class _Conn:
    """Records the SQL it is handed. `rowcount` is what an upsert actually reports."""

    def __init__(self, rowcounts=None):
        self.sql: list[str] = []
        self.params: list[dict] = []
        self._rowcounts = list(rowcounts or [])

    def execute(self, statement, params=None):
        self.sql.append(str(statement))
        self.params.append(params or {})
        rowcount = self._rowcounts.pop(0) if self._rowcounts else 1
        return type("R", (), {"rowcount": rowcount, "mappings": lambda s: iter(())})()


# =================================================================================================
# 1 · ⛔ a closed need is never reopened
# =================================================================================================
def test_the_insert_does_nothing_on_conflict_and_never_updates():
    """⛔ THE ONE THAT MATTERS. `do update` would reset every `met` and `unavailable` need to `open`
    on the next sweep, because residue is re-derived every sweep and a re-derived need is born
    `open`."""
    sql = str(evidence_need_store._INSERT).lower()
    assert "on conflict" in sql
    assert "do nothing" in sql
    assert "do update" not in sql


def test_no_statement_in_this_module_updates_a_needs_state_except_a_close():
    """A second path that could move `state` would be a second place the reopening bug could live."""
    for name in ("_INSERT", "_OPEN"):
        assert "set state" not in str(getattr(evidence_need_store, name)).lower()


def test_a_close_only_touches_a_need_that_is_still_open():
    """Two concurrent executor passes must not both win. The predicate is the guard — one statement,
    no read-modify-write."""
    sql = str(evidence_need_store._CLOSE).lower()
    assert "state = 'open'" in sql


# =================================================================================================
# 2 · what store_needs reports
# =================================================================================================
def test_it_counts_new_rows_not_rows_offered():
    """⛔ A count of needs derived would report the same number every sweep — it would read as
    activity and mean nothing. A zero must mean "nothing new to ask"."""
    conn = _Conn(rowcounts=[1, 0, 1])
    assert store_needs(conn, [_need("a"), _need("b"), _need("c")]) == 2


def test_an_empty_list_writes_nothing_at_all():
    conn = _Conn()
    assert store_needs(conn, []) == 0
    assert conn.sql == []


def test_every_need_field_reaches_the_row():
    conn = _Conn()
    store_needs(conn, [_need(unacceptable_sources=("model_paraphrase",),
                             acceptable_sources=("signed_contract",))])
    params = conn.params[0]
    assert "signed_contract" in params["acceptable"]
    assert "model_paraphrase" in params["unacceptable"]
    assert params["state"] == "open"


# =================================================================================================
# 3 · closing a need
# =================================================================================================
@pytest.mark.parametrize("state", ["open", "pending", "", "MET"])
def test_a_need_closes_only_as_met_or_unavailable(state):
    with pytest.raises(ValueError):
        close_need(_Conn(), "en_1", state=state)


def test_closing_unavailable_without_a_reason_is_refused_by_name():
    """The database constraint says the same thing. Refusing here too means the caller gets a name
    for its mistake instead of an IntegrityError three frames down."""
    with pytest.raises(ValueError, match="carries its reason"):
        close_need(_Conn(), "en_1", state="unavailable", reason="   ")


def test_closing_a_need_someone_else_already_closed_returns_false_not_an_error():
    """⛔ Not a failure to retry. It means another pass settled this question first and its answer
    stands; overwriting would reset `closed_at` and lose when it was actually settled."""
    assert close_need(_Conn(rowcounts=[0]), "en_1", state="met") is False
    assert close_need(_Conn(rowcounts=[1]), "en_1", state="met") is True


# =================================================================================================
# 4 · the queue is read oldest first
# =================================================================================================
def test_the_executors_queue_is_oldest_first():
    """A steady stream of new needs must not starve one that has been waiting a week."""
    sql = str(evidence_need_store._OPEN).lower()
    assert "order by created_at" in sql
    assert "state = 'open'" in sql


# =================================================================================================
# 5 · ⛔ the sweep actually calls it
# =================================================================================================
def test_the_sweep_files_needs_from_its_own_residue():
    """⛔ THE SIX-TIMES DEFECT, PREVENTED. `needs_from_residue` was built, tested and green, and
    nothing called it. This test is the thing that fails if that happens again."""
    source = inspect.getsource(runner.process_pending)
    assert "needs_from_residue" in source
    assert "file_needs" in source


def test_the_sweep_files_after_it_measures():
    """The questions come from the measurement, so filing before detecting would file last sweep's
    residue every time."""
    source = inspect.getsource(runner.process_pending)
    assert source.index("detect_residue") < source.index("needs_from_residue")


def test_the_count_reaches_the_sweep_result():
    """⛔ `not_carried`: a value computed correctly and dropped at the boundary. This programme has
    found that shape six times; the wire is not done until the number is reported."""
    source = inspect.getsource(runner.process_pending)
    assert '"evidence_needs_filed": needs_filed' in source


def test_filing_never_breaks_ingestion():
    """A sweep that could not file its questions has lost a cycle of visibility. A sweep that died
    trying has lost the tenant's mail."""
    source = inspect.getsource(runner.process_pending)
    after = source[source.index("needs_from_residue"):]
    assert "except Exception" in after


def test_the_trace_id_is_derived_not_minted():
    """`process_pending` promises that the same graph at the same `eval_time` replays identically. A
    random trace would be the one field in the row a replay could not reproduce."""
    source = inspect.getsource(runner.process_pending)
    assert "stable_id(\"trace\"" in source


def test_file_needs_swallows_and_reports_zero(monkeypatch):
    class _Boom:
        class engine:
            @staticmethod
            def begin():
                raise RuntimeError("database is down")

    assert evidence_need_store.file_needs(_Boom(), [_need()]) == 0


def test_file_needs_does_no_work_for_an_empty_list():
    class _Never:
        class engine:
            @staticmethod
            def begin():
                raise AssertionError("must not open a transaction for nothing")

    assert evidence_need_store.file_needs(_Never(), []) == 0
