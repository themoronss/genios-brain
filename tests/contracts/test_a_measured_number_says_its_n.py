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
                                              median_of, rate_of)

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
    assert (r.value, r.n, r.unit, r.sparse) == (0.625, 8, "ratio", False)
    assert rate_of(0, 0, basis="connector").says() == "not measured"
    with pytest.raises(ValueError):
        rate_of(3, 2, basis="connector")


def test_the_dict_carries_everything_a_reader_needs():
    d = median_of([1.92], basis="person").as_dict()
    assert d == {"value": 1.92, "n": 1, "basis": "person", "source": MEASURED_HERE,
                 "unit": "days", "sparse": True, "says": "once: 1.92 days"}
