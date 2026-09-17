"""Every other receipt can pass while a tenant's feed is dead.

L2 marks a situation dormant after `DORMANT_AFTER_DAYS` of silence — measured on the pilot, the
boundary is exact: every dormant situation is at least 44 days stale and every active one is at
most 44. So a tenant nothing has arrived for in that long has, provably, no working set left to
reason about. The graph is still there, the packs are still compiled, the cards are still in the
table, and seventeen receipts still say PASS. Nothing said the feed had stopped.

WHY THE THRESHOLD IS IMPORTED AND NOT CHOSEN. Any other number here would be a second opinion
about when quiet becomes empty, and the two would drift the first time one was tuned. The receipt
asks exactly the question L2's own lifecycle already answers.

WHY `captured_at` AND NOT `occurred_at`. This asks whether OUR pipeline is receiving. A backfill
of last quarter's mail is healthy ingestion of old messages, and judging it on the message dates
would report a working connector as a dead one.

`platform/receipts.py` had no test at all before this file — twenty structural claims, each one a
SQL string and a lambda, none of them exercised. The last two tests here are about the module
rather than the new receipt, for that reason.
"""
from __future__ import annotations

import re

import pytest

from genios_engine.capture.pipeline import JUDGED_DROP_CODES, JUDGED_DROP_PAYLOAD_TTL_DAYS
from genios_engine.context.situations import DORMANT_AFTER_DAYS
from genios_engine.platform.receipts import Receipt, receipts

CLAIM = "the tenant is still being fed"
REVIEWABLE = "every drop we might be wrong about can still be reviewed"


def _fed() -> Receipt:
    return next(r for r in receipts("org_x") if r.claim == CLAIM)


def _reviewable() -> Receipt:
    return next(r for r in receipts("org_x") if r.claim == REVIEWABLE)


# =============================================================================================
# the boundary, and the empty tenant
# =============================================================================================
@pytest.mark.parametrize("days", [0, 1, DORMANT_AFTER_DAYS - 1])
def test_a_tenant_that_is_being_fed_passes(days):
    assert _fed().expect(days) is True


@pytest.mark.parametrize("days", [DORMANT_AFTER_DAYS, DORMANT_AFTER_DAYS + 1, 10_000])
def test_a_feed_quiet_past_the_dormancy_window_fails(days):
    """At exactly the window the working set is empty, so the boundary is `<`, not `<=`."""
    assert _fed().expect(days) is False


def test_a_tenant_nothing_has_ever_arrived_for_fails():
    """`max(captured_at)` over no rows is NULL, and `expect` would have read that as falsey —
    reporting the loudest possible version of this failure as a pass. The `coalesce` sentinel is
    what makes an empty tenant fail for the right reason, so the sentinel and the predicate are
    tested TOGETHER: reading the constant out of the SQL and asking `expect` about it is the only
    way this catches someone lowering one without the other."""
    sql = _fed().sql
    match = re.search(r"coalesce\([^,]+,\s*(\d+)\s*\)", sql)

    assert match, f"the receipt no longer coalesces its NULL: {sql}"
    assert _fed().expect(int(match.group(1))) is False, (
        f"an org with no events at all returns {match.group(1)} and that value PASSES — a tenant "
        "nothing has ever been captured for is being reported as ready")


def test_the_threshold_is_layer_twos_and_not_a_second_copy():
    """A duplicated constant is the failure this codebase names everywhere. If the dormancy window
    moves, this receipt must move with it."""
    assert _fed().expect(DORMANT_AFTER_DAYS - 1) is True
    assert _fed().expect(DORMANT_AFTER_DAYS) is False
    assert str(DORMANT_AFTER_DAYS) in _fed().sql, (
        "the receipt's own sentinel no longer derives from DORMANT_AFTER_DAYS")


def test_the_receipt_is_layer_one_and_reads_the_capture_table():
    """Its layer is where an operator looks when ingestion is the suspect, and `occurred_at`
    would make a healthy backfill look like a dead connector."""
    fed = _fed()

    assert fed.layer == "L1"
    assert "source_events" in fed.sql and "captured_at" in fed.sql
    assert "occurred_at" not in fed.sql
    assert fed.detail, "a receipt with no detail is a number nobody can act on"


# =============================================================================================
# the module — twenty claims that had no test
# =============================================================================================
def test_every_receipt_is_one_scalar_select_with_a_predicate():
    """`evaluate` calls `.scalar()` on the result and hands it to `expect`. A receipt returning
    two columns, or none, reads as ERROR at runtime and nowhere else."""
    for r in receipts("org_x"):
        assert r.sql.lower().lstrip().startswith("select"), r.claim
        assert callable(r.expect), r.claim
        assert r.layer.startswith("L"), r.claim


def test_every_org_scoped_receipt_binds_the_org_it_was_asked_about():
    """`evaluate` passes `:org` only when the SQL mentions it. A receipt that forgot the filter
    answers about the WHOLE DEPLOYMENT while appearing on one tenant's readiness page — every
    other tenant's parked queue reported as this one's."""
    scoped = [r for r in receipts("org_x") if "org_id" in r.sql]

    assert scoped, "no receipt is org-scoped any more"
    for r in scoped:
        assert ":org" in r.sql, (
            f"{r.claim!r} filters on org_id without binding :org — it reads a literal or nothing")


def test_claims_are_unique_so_a_reader_can_name_the_one_that_failed():
    claims = [r.claim for r in receipts(None)]

    assert len(claims) == len(set(claims)), "two receipts share a claim"


# =============================================================================================
# the receipt that could never pass
# =============================================================================================
def test_a_deterministic_drop_is_not_counted_against_the_tenant():
    """Asked of EVERY drop, this counted 2,818 deterministic refusals that by documented policy
    retain nothing — "L1 stays a filter, not a warehouse" — so it could not pass on any tenant in
    any state. Permanent red teaches an operator to stop reading the page, which is the same
    failure as a skip reading as a pass, wearing the other colour."""
    sql = _reviewable().sql

    assert "reason_code in (" in sql, (
        "the receipt counts every drop again, including the deterministic ones that are "
        "DESIGNED to retain nothing — it can never pass")
    for code in JUDGED_DROP_CODES:
        assert repr(code) in sql or f"'{code}'" in sql, f"{code} is no longer asked about"


def test_the_judged_set_is_the_pipelines_and_not_a_second_opinion():
    """Which deletions are judgments is the pipeline's call — it is the module that decides which
    ones keep a body. A restated set here would answer about a policy the pipeline no longer has
    the first time one of them moved."""
    sql = _reviewable().sql
    quoted = {c for c in ("llm_junk", "low_relevance", "N-02", "N-03", "N-06")
              if f"'{c}'" in sql}

    assert quoted == set(JUDGED_DROP_CODES), (
        f"the receipt asks about {quoted}, the pipeline retains for {set(JUDGED_DROP_CODES)}")


def test_the_window_is_the_retention_policys_own():
    """A judged drop past its TTL is EXPECTED to have no payload. Counting it would make the
    receipt fail for a tenant doing everything right, forever."""
    assert f"'{JUDGED_DROP_PAYLOAD_TTL_DAYS} days'" in _reviewable().sql
    assert "captured_at" in _reviewable().sql


def test_one_unreviewable_judgment_is_enough_to_fail():
    """Not a rate. One model deletion nobody can look at is one the tenant cannot be told about."""
    assert _reviewable().expect(0) is True
    assert _reviewable().expect(1) is False
    assert _reviewable().expect(26) is False


# =============================================================================================
# the receipt whose detail named the wrong cause
# =============================================================================================
CHANNEL = "there is a channel this tenant can be reached on"
RAN = "the delivery control plane has run"


def _claims() -> list[str]:
    return [r.claim for r in receipts("org_x")]


def test_the_pull_surface_is_not_a_channel_anything_can_be_pushed_to():
    """All three orgs register `in_app` and nothing else. The card is already sitting on that
    surface — there is nothing to send — so counting it would report a tenant that can be reached
    when nobody can be reached, which is the most expensive possible false PASS on this page."""
    from genios_engine.deliver.routing import PULL_SURFACE

    sql = next(r for r in receipts("org_x") if r.claim == CHANNEL).sql

    assert f"'{PULL_SURFACE}'" not in sql, (
        f"{PULL_SURFACE!r} counts as a push channel; a tenant with only the pull surface would "
        "read as reachable")


def test_the_channel_set_is_the_drains_and_not_a_literal():
    """`deliverable_channels` computes registered AND implemented AND not-an-agent-transport in
    Python. A receipt that hard-coded 'slack' would keep saying so the day a second transport
    lands, and report a reachable tenant as unreachable."""
    from genios_engine.deliver.routing import AGENT_TRANSPORTS
    from genios_engine.deliver.units import _implemented_channels

    sql = next(r for r in receipts("org_x") if r.claim == CHANNEL).sql
    expected = set(_implemented_channels()) - set(AGENT_TRANSPORTS)

    assert expected, "no channel is deliverable at all — the intersection is empty in code"
    for channel in expected:
        assert f"'{channel}'" in sql, f"{channel} is deliverable but the receipt does not count it"
    for excluded in set(AGENT_TRANSPORTS):
        assert f"'{excluded}'" not in sql, (
            f"{excluded!r} is an agent transport and routing law 1 forbids a human delivery on it")


def test_the_precondition_is_asked_before_the_thing_it_gates():
    """An operator reads this page top to bottom. "Nothing was delivered" above "there is nowhere
    to deliver" is the same page in the wrong order, and the wrong half gets investigated."""
    claims = _claims()

    assert claims.index(CHANNEL) < claims.index(RAN)


def test_the_empty_outbox_no_longer_blames_the_scoring_formula():
    """The old detail read "push is gated on a band the scoring formula cannot reach". True when
    written; measured 2026-09-17 it is false — 71 of 133 cards sit at high or critical and 21
    pass the full eligibility filter. A detail naming the wrong cause sends someone to rewrite a
    formula that is working."""
    detail = next(r for r in receipts("org_x") if r.claim == RAN).detail

    assert "cannot reach" not in detail, "the stale diagnosis is back"
    assert "channel" in detail, "the detail does not point at the precondition receipt"
