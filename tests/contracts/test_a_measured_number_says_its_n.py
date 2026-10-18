"""STEP-10 · a number the expert may read says what it rests on, and is never "normal" on too little.

    .venv/bin/python -m pytest tests/contracts/test_a_measured_number_says_its_n.py -q

`contracts/measured` (tree `yc2_w27_s10 · M29.C1.L-contract.V0.U01`). On the golden set the only reply
times that existed rested on one reply counted twice, with no n beside them (`STEP-10` §8.1). Every
number a file shows is now a `Measured` — value, n, basis, source — and below `NORMAL_AT` (5, `06` D37)
it is shown as what it is, never as a habit.
"""
from __future__ import annotations

import pytest

from genios_engine.contracts.measured import (MEASURED_HERE, NORMAL_AT, PLAYBOOK_PRIOR, Measured,
                                              count_of, median_of, rate_of)

pytestmark = pytest.mark.unit


def test_normal_needs_five_observations():
    assert NORMAL_AT == 5
    assert median_of([1, 2, 3, 4], basis="person").sparse
    five = median_of([1, 2, 3, 4, 5], basis="person")
    assert not five.sparse and five.normal and five.value == 3.0


@pytest.mark.parametrize("values, words", [
    ([], "not measured"),
    ([1.92], "once: 1.92 days"),
    ([1, 3], "2 times, median 2 days — too few to call normal"),
    ([1, 2, 2, 3, 9], "usually 2 days (n=5, person)"),
])
def test_it_says_what_it_rests_on(values, words):
    assert median_of(values, basis="person").says() == words


def test_a_sparse_number_is_never_said_as_a_habit():
    for n in range(1, NORMAL_AT):
        assert "usually" not in median_of([2.0] * n, basis="tenant").says()


def test_a_prior_is_never_labelled_measured():
    prior = Measured(value=7.0, n=0, basis="investor follow-up", source=PLAYBOOK_PRIOR, unit="days")
    assert not prior.normal and "not measured here" in prior.says()
    assert prior.as_dict()["source"] == PLAYBOOK_PRIOR
    widely_held = Measured(value=7.0, n=40, basis="investor follow-up", source=PLAYBOOK_PRIOR)
    assert not widely_held.normal, "a prior, however many it rests on, is not this tenant's normal"


@pytest.mark.parametrize("bad", [
    dict(value=1.0, n=1, basis="person", source="guessed"),
    dict(value=1.0, n=-1, basis="person"),
    dict(value=1.0, n=1, basis=" "),
    dict(value=None, n=2, basis="person"),
    dict(value=1.0, n=0, basis="person"),
])
def test_a_malformed_number_is_refused(bad):
    with pytest.raises(ValueError):
        Measured(**bad)


def test_a_rate_rests_on_its_total():
    r = rate_of(5, 8, basis="connector")
    assert (r.value, r.n, r.k, r.unit, r.stat, r.sparse) == (0.625, 8, 5, "ratio", "rate", False)
    assert rate_of(0, 0, basis="connector").says() == "not measured"
    with pytest.raises(ValueError):
        rate_of(3, 2, basis="connector")


@pytest.mark.parametrize("hits, total, words", [(5, 8, "5 of 8"), (1, 3, "1 of 3"),
                                                (0, 4, "0 of 4"), (2, 3, "2 of 3")])
def test_a_rate_says_how_many_of_how_many_never_a_habit(hits, total, words):
    """STEP-10's worker found the median's words on a rate: "usually 0.625 ratio (n=8, connector)"."""
    r = rate_of(hits, total, basis="connector")
    assert r.says() == words and "usually" not in r.says()


def test_a_rate_keeps_its_hits_so_the_words_never_round():
    """2 of 3 is stored as 0.667; 0.667 × 3 is 2.001 — the words come from k, not from the value."""
    assert rate_of(2, 3, basis="wave").says() == "2 of 3"
    assert rate_of(1, 3000, basis="wave").says() == "1 of 3000", "0.000 × 3000 would say 0 of 3000"
    assert rate_of(5, 8, basis="wave").as_dict()["k"] == 5
    assert rate_of(0, 0, basis="wave").k is None, "a rate of nobody has no hits either"


@pytest.mark.parametrize("k, words", [(8, "8"), (1, "1"), (0, "none")])
def test_a_count_is_what_it_counts(k, words):
    """Found the same way: "3 times, median 3 count — too few to call normal"."""
    c = count_of(k, basis="connector")
    assert (c.value, c.n, c.stat, c.says()) == (k, k, "count", words)
    assert not c.sparse and not c.normal, "a count is exact, and never a habit"


def test_a_count_of_nothing_is_none_not_unmeasured():
    assert count_of(0, basis="connector").as_dict()["says"] == "none"
    with pytest.raises(ValueError):
        count_of(-1, basis="connector")


@pytest.mark.parametrize("bad", [
    dict(value=2, n=3, basis="connector", stat="count"),
    dict(value=None, n=0, basis="connector", stat="count"),
    dict(value=0.5, n=4, basis="connector", stat="rate"),
    dict(value=0.5, n=4, basis="connector", stat="rate", k=5),
    dict(value=1.0, n=1, basis="person", stat="mean"),
])
def test_a_malformed_kind_of_number_is_refused(bad):
    with pytest.raises(ValueError):
        Measured(**bad)


def test_the_dict_carries_everything_a_reader_needs():
    d = median_of([1.92], basis="person").as_dict()
    assert d == {"value": 1.92, "n": 1, "basis": "person", "source": MEASURED_HERE,
                 "unit": "days", "stat": "median", "k": None, "sparse": True,
                 "says": "once: 1.92 days"}
