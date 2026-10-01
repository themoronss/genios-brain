"""U06 · the one fact that would change the conclusion, asked for by name.

    pytest tests/contracts/test_evidence_need.py -q

⛔ THE EDGE THIS SYSTEM DID NOT HAVE. Layer 2 could only HOLD and wait. Meanwhile
`context/residue.py` was already computing the demand — `signal_unreached` measures *"the Layer 1
verdicts no Layer 2 reading consumes"* — and that number reached the model angles and stopped. The
measurement half existed; only the wire did not.

Three rules carry this contract, and each one is what separates it from a backfill:

  1. **`why_it_matters` is mandatory.** A need that cannot say why it changes the decision is not
     decision-relevant, and fetching for it spends a tenant's budget on curiosity.
  2. ⛔ **`unacceptable_sources` is real.** A vendor's quote email may not stand in for a signed
     contract. Without the negative list an executor that found *something* mentioning the right
     words would close the need, and Layer 2 would proceed on evidence that cannot carry the claim
     — worse than the hold it replaced, because the hold at least knew it was missing something.
  3. ⛔ **`unavailable` is a real outcome, not a failure.** A need that can never be met must CLOSE,
     with a reason. One left open forever is a hold that can never clear — the exact state this
     contract exists to end, re-created one layer down.
"""

from __future__ import annotations

import pathlib
import re

import pytest
from pydantic import ValidationError

from genios_engine.contracts.evidence import NEED_STATES, EvidenceNeed

pytestmark = pytest.mark.unit

_ROOT = pathlib.Path(__file__).resolve().parents[2]


def _need(**over):
    kwargs = dict(
        need_id="EN-31", org_id="org_x", trace_id="8f2a",
        question="Does the signed contract auto-renew, and with what notice?",
        why_it_matters="It moves the decision deadline from 20 Oct to 13 Oct.",
        subject_ref="contract:CTR-441",
        acceptable_sources=("signed_contract",),
        unacceptable_sources=("vendor_quote_email", "chat_message"),
    )
    kwargs.update(over)
    return EvidenceNeed(**kwargs)


# =================================================================================================
# 1 · a need has to say why it matters
# =================================================================================================
@pytest.mark.parametrize("field", ["question", "why_it_matters"])
def test_a_need_that_says_nothing_is_refused(field):
    with pytest.raises(ValidationError):
        _need(**{field: "   "})


# =================================================================================================
# 2 · ⛔ what would NOT settle it
# =================================================================================================
def test_an_unacceptable_source_cannot_close_the_need():
    need = _need()
    assert need.accepts("signed_contract") is True
    assert need.accepts("vendor_quote_email") is False
    assert need.accepts("chat_message") is False


def test_a_source_named_in_both_lists_is_refused():
    """An executor reading that could close the need with evidence the need itself rejects."""
    with pytest.raises(ValidationError) as exc:
        _need(acceptable_sources=("signed_contract",),
              unacceptable_sources=("signed_contract",))
    assert "both acceptable and unacceptable" in str(exc.value)


def test_with_no_acceptable_list_anything_not_forbidden_is_allowed():
    """An executor that only ever accepted an enumerated list could not answer a question nobody
    anticipated a source for."""
    need = _need(acceptable_sources=(), unacceptable_sources=("chat_message",))
    assert need.accepts("some_new_connector") is True
    assert need.accepts("chat_message") is False


# =================================================================================================
# 3 · ⛔ unavailable closes, with a reason
# =================================================================================================
def test_the_state_vocabulary_is_closed():
    assert NEED_STATES == ("open", "met", "unavailable")
    with pytest.raises(ValidationError):
        _need(state="pending")


def test_unavailable_without_a_reason_is_refused():
    """A need that closes without one is indistinguishable from a need nobody worked, and the card
    has nothing to say in place of the fact it was waiting for."""
    with pytest.raises(ValidationError) as exc:
        _need(state="unavailable")
    assert "carries its reason" in str(exc.value)


def test_unavailable_with_a_reason_is_accepted():
    need = _need(state="unavailable", unavailable_reason="Drive is not connected for this tenant")
    assert need.state == "unavailable"


def test_a_reason_on_an_open_need_is_refused():
    with pytest.raises(ValidationError):
        _need(unavailable_reason="but it is still open")


# =================================================================================================
# 4 · it is not a backfill
# =================================================================================================
def test_it_can_carry_a_cost_limit_and_an_expiry():
    """An unbounded fetch is a backfill wearing a question's clothes; an answer that arrives after
    the decision is not worth buying."""
    fields = EvidenceNeed.model_fields
    assert "max_cost_usd" in fields and "expires_at" in fields


def test_the_need_is_frozen():
    with pytest.raises(ValidationError):
        _need().question = "something else"


# =================================================================================================
# 5 · the table agrees with the contract
# =================================================================================================
def _migration() -> str:
    return (_ROOT / "migrations" / "0187_evidence_needs.sql").read_text(encoding="utf-8")


def test_the_table_holds_the_same_state_vocabulary():
    sql = _migration()
    found = re.search(r"check \(state in \(([^)]*)\)", sql)
    assert found, "the state check constraint is gone"
    states = tuple(s.strip().strip("'") for s in found.group(1).split(","))
    assert states == NEED_STATES, "the table and the contract disagree about what a need can be"


def test_the_table_refuses_a_reasonless_closure_too():
    """⛔ Both halves. The contract can refuse one at construction; anything holding a connection
    could write a row directly, so the constraint has to exist in the schema as well."""
    assert "evidence_needs_unavailable_has_a_reason" in _migration()


def test_the_table_carries_the_negative_list():
    assert "unacceptable_sources" in _migration()


def test_the_table_cascades_on_tenant_deletion():
    assert "evidence_needs_org_cascade_fk" in _migration()
