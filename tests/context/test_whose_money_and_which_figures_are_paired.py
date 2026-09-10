"""BM-2 and BM-4 — the engine could not tell revenue from spend, and said five numbers were
compared when they were not.

    pytest tests/context/test_whose_money_and_which_figures_are_paired.py -q

BM-2. A SaaS founder's Stripe account holds their CUSTOMERS' subscriptions. Every active one
is a paying customer and a renewal that means money coming IN. Nothing on the fact, the node,
the mapping or the pattern distinguished that from their AWS bill — `StructuredMapping` had no
notion of whose money it is, and `stripe.subscription.v1` writes exactly two facts, neither of
which says.

And the LIVE half was a source prior: `stripe -> admin`, unconditional, ahead of any pattern.

BM-4. `_counts`' docstring said *"each figure is paired with its previous-window twin because
a single number is not a finding"*. Two of the seven are. The other five are point-in-time
stocks with no time bound anywhere in their SQL — and the same false sentence was pasted into
three shipped situation files. The numbers are NOT changed here: scoping the aggregate or
fixing a double-count would move a figure a shipped card gates on, which is a day-one
behaviour change and belongs in its own unit. What is corrected is the claim.
"""

from __future__ import annotations

import inspect
import pathlib

import pytest

from genios_engine.capture.structured.apply import apply_mapping
from genios_engine.capture.structured.registry import StructuredMapping, mapping_from_dict
from genios_engine.context import periodic

pytestmark = pytest.mark.unit


def mapping(**kw):
    base = {"mapping_id": "m1", "source": "stripe", "object_type": "subscription",
            "identity_field": "id", "node_type": "subscription", "fields": (),
            "intent": "record"}
    return StructuredMapping(**{**base, **kw})


# =============================================================================================
# BM-2 — whose money.
# =============================================================================================
def test_a_mapping_can_say_whose_money_this_is():
    got = apply_mapping(mapping(money_direction="we_sell"), {"id": "sub_1"})

    assert got["subscription.money_direction"] == "we_sell"


def test_an_undeclared_mapping_writes_no_direction():
    """"We do not know whose money this is" must stay distinguishable from "it is ours" — the
    distinction the field exists for, and one a default would destroy on every source written
    before it."""
    got = apply_mapping(mapping(), {"id": "sub_1"})

    assert "subscription.money_direction" not in got


def test_the_declaration_survives_the_config_loader():
    loaded = mapping_from_dict({
        "mapping_id": "m1", "source": "stripe", "object_type": "subscription",
        "identity_field": "id", "node_type": "subscription", "fields": [],
        "intent": "record", "money_direction": "we_buy"})

    assert loaded.money_direction == "we_buy"


def test_the_fact_is_not_called_direction():
    """`RelationMap.direction` fifty lines up means graph EDGE direction and
    `pipeline._envelope_direction` means inbound/outbound MAIL. Three senses of one word in one
    package is how a reader picks the wrong one."""
    got = apply_mapping(mapping(money_direction="we_sell"), {"id": "sub_1"})

    assert "subscription.direction" not in got


def test_a_tenant_can_say_their_stripe_is_revenue():
    """THE LIVE HALF. `stripe -> admin` is unconditional and ahead of any pattern: it assumes
    the tenant is a BUYER, and for a SaaS founder it filed all of their revenue under
    back-office."""
    from genios_engine.capture.domain import hints

    body = inspect.getsource(hints.domain_hints)

    assert "authored_priors.get((source or \"\").strip().lower()) or _SOURCE_PRIOR.get(source)" \
        in body


# =============================================================================================
# BM-4 — which figures are actually compared.
# =============================================================================================
def test_the_docstring_no_longer_claims_every_figure_has_a_twin():
    doc = inspect.getdoc(periodic._counts) or ""

    assert "TWO OF THE SEVEN ARE PAIRED" in doc
    assert "point-in-time stocks" in doc.lower()


def test_the_docstring_says_why_they_cannot_be_paired():
    """Not laziness: `graph_facts.valid_from` records when we INGESTED a fact, not when it
    became true, so a prior-window count would answer "how many we had heard about" — a number
    that moves when a backfill runs."""
    doc = inspect.getdoc(periodic._counts) or ""

    assert "valid_from" in doc
    assert "backfill" in doc


def test_the_docstring_says_the_aggregate_is_org_wide():
    """Computed once above the per-domain loop and splatted into every domain's inputs, so a
    support period review carries `period.open_deals`."""
    doc = inspect.getdoc(periodic._counts) or ""

    assert "ONCE for the org" in doc


@pytest.mark.parametrize("name", ["pipeline-period-review.yaml", "queue-period-review.yaml",
                                  "admin-service-under-load.yaml"])
def test_the_same_false_claim_was_removed_from_the_corpus(name):
    """The sentence was PASTED into three shipped files. A docstring corrected in one place and
    left wrong in three is a correction that did not happen."""
    corpus = pathlib.Path(__file__).resolve().parents[2] / "Domain Expertise"
    found = [p for p in corpus.rglob(f"situations/{name}")]

    assert found, name
    text = found[0].read_text()
    assert "COUNT and its previous-window twin" not in text
    assert "ONLY ONE OF THEM HAS A TWIN" in text


def test_the_seven_field_names_did_not_move():
    """They are `vocabulary.yaml` entries and four live authored gates. Correcting a claim must
    not rename a fact."""
    source = inspect.getsource(periodic)

    for field in ("period.open_deals", "period.events_this_window",
                  "period.events_prev_window", "period.commitments_open",
                  "period.commitments_overdue", "period.active_situations",
                  "period.counterparties_awaiting_us"):
        assert field in source, field
