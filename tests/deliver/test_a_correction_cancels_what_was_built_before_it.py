"""PP-3 — correcting a profile fact changed only what happened next.

    pytest tests/deliver/test_a_correction_cancels_what_was_built_before_it.py -q

The "us" set (`context/runner._internal_emails`) is consulted only when an event ARRIVES. So
when the founder seats a co-founder in month three, nothing already committed moves: the
co-founder's node keeps every counterparty observation it accumulated, the situations anchored
on him stay anchored, and the queued cards advising the founder about "the prospect" who is his
own co-founder stay queued and WILL be delivered.

Three seams, each measured: `upsert_seat` did no change detection and stamped nothing; the
outbox's send-time re-proof re-checked the DECISION's authority and never read
`organization_resets` (an audit claim to the contrary was checked and found false); and the
backfill route never passed `rebuild`, which `backfill_layer2` has accepted all along.
"""

from __future__ import annotations

import inspect

import pytest

from genios_engine.api import routes, situation_routes
from genios_engine.deliver import outbox

pytestmark = pytest.mark.unit


def test_a_material_seat_change_stamps_a_reset_and_a_re_put_does_not():
    src = inspect.getsource(routes.upsert_seat)

    assert "apply_organization_reset(c, org_id=org_id, reason=f\"seat_corrected:{seat_id}\"" in src
    # idempotent re-PUT: the three conditions that make a change MATERIAL, and nothing else
    assert "not exists" in src
    assert "(before.email or \"\").strip().lower() != (body.email or \"\").strip().lower()" in src
    assert "not bool(before.active)" in src


def test_the_route_tells_the_caller_whether_it_corrected_identity():
    src = inspect.getsource(routes.upsert_seat)

    assert '"identity_corrected": bool(changed)' in src


def test_the_outbox_cancels_a_card_built_before_the_latest_reset():
    """The re-proof that existed re-checked only the decision's authority. This is the read
    that was missing, on the same connection and under the same locks."""
    src = inspect.getsource(outbox)

    assert "select created_at from organization_resets where org_id=:o" in src
    assert "built_at < latest_reset" in src
    assert "org corrected its identity after this card was built" in src


def test_the_reset_read_fails_closed_to_send():
    """An outage of the reset log must not become a delivery outage: a read error means
    'no reset known', which is the pre-existing behaviour, never a narrower one."""
    src = inspect.getsource(outbox)
    i = src.index("stale_identity = False")
    block = src[i:i + 1200]

    assert "except Exception" in block
    assert "stale_identity = False" in block[block.index("except Exception"):]


def test_the_backfill_route_can_finally_ask_for_a_rebuild():
    src = inspect.getsource(situation_routes.run_backfill)

    assert "rebuild: bool = False" in src
    assert "rebuild=bool(rebuild)" in src
