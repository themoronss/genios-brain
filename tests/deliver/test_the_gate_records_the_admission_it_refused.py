r"""The gate writes down WHY it refused, and something reads it.

⛔ WHAT WAS WRONG. `deliver/gate.describe_decision` — *"The loggable record of one admission —
verdict, reason, and the settings behind it"* — was in `__all__` and called by nothing. Meanwhile
`gate.admit`'s docstring had already said what it was for:

    "Returns the context alongside the verdict so the caller can put the resolved settings into the
     audit row. 'It was held because quiet hours' is only half an answer; '…and this tenant's quiet
     hours are 21:00–08:00 Asia/Kolkata' is the half that ends the support ticket."

⛔ BOTH REFUSAL PATHS ALREADY HAD BOTH HALVES IN HAND AND DROPPED ONE. `outbox._suppress` and
`outbox._defer` are handed `(decision, context)` and wrote `{"reason": decision.reason_code}` — the
thinnest possible record. `decision.detail` and the entire resolved context went on the floor.
And `_defer` took `context` as a parameter and **read nothing from it**: presence without effect, in
the signature.

⛔ AND THE PLAN'S TWO CANDIDATE SINKS WERE BOTH WRONG.

  * `spine.log_delivery_event` directly — the right TABLE, the wrong CALL. `_mark_lifecycle` is the
    canonical wrapper and its docstring says why: "column + event row together" so the two "cannot
    disagree". Calling the logger directly writes the event and leaves `lifecycle` stale.
  * `store.log_event` — card-scoped. A gate decision is about a DELIVERY.
  * ⛔ The real sink is `_mark_lifecycle`'s own `detail` dict, which the plan never listed.

⛔ AND THE WRITER ALONE WOULD HAVE BEEN DECORATION. `GET /api/org/{org_id}/delivery/results/
{delivery_id}` — the endpoint a support question lands on — selected `kind, occurred_at, actor` from
`delivery_events` and **not `detail`**. So the record would have been written and read by nothing,
which is the exact defect `STEP-09 §4` warned about: *inventing a record nobody reads is presence
without effect.* **The reader is half this unit.**
"""
from __future__ import annotations

import ast
import inspect
import json
from datetime import datetime, timedelta, timezone

from genios_engine.contracts.delivery import DeliveryDecision, DeliveryVerdict
from genios_engine.deliver import delivery_health as H
from genios_engine.deliver import outbox
from genios_engine.deliver.gate import DeliveryContext, describe_decision
from genios_engine.deliver.policy import DeliveryPolicy
from genios_engine.deliver.timing import AttentionProfile, AttentionState

NOW = datetime(2026, 10, 1, 22, 30, tzinfo=timezone.utc)


def _ctx(**over) -> DeliveryContext:
    """A resolved context carrying `admit`'s own worked example: 21:00-08:00 Asia/Kolkata."""
    kwargs = {"policy": DeliveryPolicy(),
              "profile": AttentionProfile(timezone="Asia/Kolkata",
                                          quiet_start_hour=21, quiet_end_hour=8),
              "state": AttentionState()}
    kwargs.update(over)
    return DeliveryContext(**kwargs)


# ---------------------------------------------------------------------------------------------
# a connection that remembers what it was asked to write
# ---------------------------------------------------------------------------------------------

class _Conn:
    def __init__(self, log: list) -> None:
        self.log = log

    def execute(self, statement, params=None):
        self.log.append((" ".join(str(statement).split()), dict(params or {})))

        class _R:
            def mappings(self_inner):
                return self_inner

            def all(self_inner):
                return []

            def first(self_inner):
                return None

            def scalar(self_inner):
                return None
        return _R()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Engine:
    def __init__(self) -> None:
        self.log: list = []

    def begin(self):
        return _Conn(self.log)

    def connect(self):
        return _Conn(self.log)


def _row(**over) -> dict:
    row = {"id": "ob_1", "org_id": "org_1", "card_id": "card_1",
           # ⛔ `_mark_lifecycle` only writes the event when the row carries a delivery_id —
           # "rows enqueued before L6-05 stamped one get the column update only".
           "delivery_id": "del_1", "attempts": 0}
    row.update(over)
    return row


def _decision(verdict=DeliveryVerdict.DEFER, **over) -> DeliveryDecision:
    kwargs = {"verdict": verdict, "unit": "timing", "reason_code": "quiet_hours",
              "not_before": NOW + timedelta(hours=9),
              "detail": {"window": "21:00-08:00", "tz": "Asia/Kolkata"}}
    kwargs.update(over)
    return DeliveryDecision(**kwargs)


def _events(engine: _Engine) -> list[dict]:
    """Every `delivery_events` insert, with its detail decoded."""
    out = []
    for sql, params in engine.log:
        if sql.startswith("insert into delivery_events"):
            out.append({**params, "detail": json.loads(params.get("detail") or "{}")})
    return out


# ---------------------------------------------------------------------------------------------
# 1 · the record, written
# ---------------------------------------------------------------------------------------------

def test_a_deferred_delivery_records_the_settings_behind_the_verdict() -> None:
    """⛔ THE POINT, and it is `admit`'s own sentence: *"'It was held because quiet hours' is only
    half an answer; '…and this tenant's quiet hours are 21:00–08:00 Asia/Kolkata' is the half that
    ends the support ticket."*"""
    engine, out = _Engine(), {"deferred": 0}
    outbox._defer(engine, _row(), _decision(), _ctx(), NOW, out)

    events = _events(engine)
    assert len(events) == 1, f"expected one lifecycle event, got {len(events)}"
    detail = events[0]["detail"]
    assert detail["verdict"] == "defer"
    assert detail["unit"] == "timing"
    assert detail["reason_code"] == "quiet_hours"
    assert detail["not_before"], "a hold with no window end is not an answer"
    assert detail["detail"] == {"window": "21:00-08:00", "tz": "Asia/Kolkata"}, (
        "the gate's own detail was dropped")

    # ⛔ AND THE SETTINGS, which is `admit`'s own worked example and the point of the whole unit:
    # "'It was held because quiet hours' is only half an answer; '…and this tenant's quiet hours
    # are 21:00-08:00 Asia/Kolkata' is the half that ends the support ticket."
    settings = detail["settings"]
    assert settings["profile"]["quiet_start_hour"] == 21
    assert settings["profile"]["quiet_end_hour"] == 8
    assert settings["profile"]["timezone"] == "Asia/Kolkata"
    assert "policy" in settings and "interrupts_last_hour" in settings
    assert out["deferred"] == 1


def test_a_suppressed_delivery_records_the_same_way() -> None:
    """Terminal, and distinct from `cancelled` and `failed_terminal` — *"three different fixes, so
    three different statuses"* — so its record must say which of the three it was."""
    engine, out = _Engine(), {"suppressed": 0}
    decision = _decision(DeliveryVerdict.SUPPRESS, unit="policy",
                         reason_code="channel_disconnected", not_before=None,
                         detail={"channel": "slack"})
    outbox._suppress(engine, _row(), decision, _ctx(), out)

    detail = _events(engine)[0]["detail"]
    assert detail["verdict"] == "suppress"
    assert detail["unit"] == "policy"
    assert detail["not_before"] is None, "a suppression has no window; it is over"
    assert detail["detail"] == {"channel": "slack"}


def test_the_record_is_no_longer_only_a_reason_code() -> None:
    """⛔ The defect, pinned from the other side. Both paths wrote `{"reason": ...}` — one key, and
    the key was not even the one the contract calls it (`reason_code`)."""
    engine = _Engine()
    outbox._defer(engine, _row(), _decision(), _ctx(), NOW, {"deferred": 0})
    detail = _events(engine)[0]["detail"]
    assert set(detail) >= {"verdict", "unit", "reason_code", "not_before", "detail", "settings"}
    assert "reason" not in detail, (
        "the thin record is back -- and `reason` was never the contract's name for it")


def test_a_config_error_reaches_the_record() -> None:
    """⛔ A gate that decided on broken configuration must say so IN the record. `_suppress` already
    put it into `last_error`; `describe_decision` is what puts it where an API can read it."""
    engine = _Engine()
    ctx = _ctx(config_error="quiet_hours: unparseable timezone 'Asia/Kolkatta'")
    # ⛔ `not_before=None` is not tidying: `DeliveryDecision` REFUSES a suppression that carries a
    # clock -- "only a deferral carries a clock" -- and this test first built an illegal one. The
    # contract caught it, which is the contract working.
    decision = _decision(DeliveryVerdict.SUPPRESS, not_before=None)
    outbox._suppress(engine, _row(), decision, ctx, {"suppressed": 0})
    detail = _events(engine)[0]["detail"]
    assert "Kolkatta" in detail["config_error"], "the top-level flag lost the reason"
    assert "Kolkatta" in detail["settings"]["config_error"], (
        "the settings blob must carry it too -- that is the shape the preview endpoint reads")


def test_a_row_with_no_delivery_id_still_updates_its_column() -> None:
    """⛔ `_mark_lifecycle`'s own rule: *"rows enqueued before L6-05 stamped one get the column
    update only, which still fixes what the APIs read."* The record is a bonus, never a
    precondition — a row must not stop being marked because it predates an identity."""
    engine = _Engine()
    outbox._defer(engine, _row(delivery_id=None), _decision(), _ctx(), NOW,
                  {"deferred": 0})
    assert _events(engine) == [], "an event was written for a row with no delivery identity"
    assert any(sql.startswith("update delivery_outbox set lifecycle") for sql, _ in engine.log), (
        "the lifecycle column was not updated, which is the part that always works")


# ---------------------------------------------------------------------------------------------
# 2 · ⛔ the reader — without it the writer is decoration
# ---------------------------------------------------------------------------------------------

def test_the_result_endpoint_returns_the_detail_it_now_writes() -> None:
    """⛔ THE HALF THE PLAN DID NOT HAVE. This endpoint is where *"why did my notification not
    arrive?"* lands, and it returned the event KINDS and not the reason.

    Asserted against the query text because the route needs a live database to call; the SELECT
    list is the whole claim, and it is one line.
    """
    from genios_engine.api import delivery_routes
    src = inspect.getsource(delivery_routes.get_result)
    query = " ".join(src.split())
    assert "from delivery_events" in query
    assert "select kind, occurred_at, actor, detail from delivery_events" in query, (
        "the endpoint does not read `detail`, so the gate's record is written and read by nothing")


def test_the_endpoint_still_returns_the_events_it_always_did() -> None:
    """A widened SELECT must not narrow the response. ⛔ The counterweight: a test that only checks
    `detail` is present would pass on a query that returned nothing else."""
    from genios_engine.api import delivery_routes
    query = " ".join(inspect.getsource(delivery_routes.get_result).split())
    for column in ("kind", "occurred_at", "actor"):
        assert column in query.split("from delivery_events")[0]


# ---------------------------------------------------------------------------------------------
# 3 · ⛔ the shape of the record, and the thing a future caller must not assume
# ---------------------------------------------------------------------------------------------

def test_the_record_carries_no_identity_of_its_own() -> None:
    """⛔ MEASURED AND PINNED, because it is the trap in this function's shape.

    `describe_decision(decision, context)` returns verdict, unit, reason_code, not_before, detail —
    and **no `org_id`, no `card_id`, no `delivery_id`.** It cannot be persisted as a standalone row;
    the caller must supply identity, which is why the sink is `_mark_lifecycle` (keyed on the row)
    rather than anything that takes the record alone.

    A future caller reading only the docstring — *"the loggable record of one admission"* — would
    reasonably assume it says WHICH admission. It does not.
    """
    record = describe_decision(_decision(), _ctx())
    assert not ({"org_id", "card_id", "delivery_id", "subject_id"} & set(record)), (
        f"the record now carries identity; the sink choice should be revisited: {sorted(record)}")


def test_a_clean_context_adds_no_top_level_config_error_key() -> None:
    """⛔ THE FLAG IS SEPARATE FROM THE BLOB, and the duplication is the cheap half of a trade.

    `describe_decision` adds `config_error` at the top level only when there IS one — its own
    contract. `to_semantic_dict` carries the key unconditionally, because the preview endpoint reads
    that shape. **A key that is always present and usually null teaches a reader to ignore it**, so
    the two live at two levels and mean two things: the flag says "a setting could not be used", the
    blob says "here is every setting, including that one".
    """
    record = describe_decision(_decision(), _ctx())
    assert "config_error" not in record, "the top-level flag must be conditional"
    assert record["settings"]["config_error"] is None, (
        "the blob carries the key unconditionally -- that is to_semantic_dict's contract, which the "
        "preview endpoint reads")


def test_the_settings_are_small_enough_to_write_on_every_refusal() -> None:
    """⛔ The record is written per refusal, so its size is a real cost. `describe_policy` and
    `describe_profile` both return flat dicts of scalars — measured at ~440 bytes of JSON, which is
    why nesting the whole context was affordable and why it is NOT written on the happy path."""
    import json
    blob = json.dumps(describe_decision(_decision(), _ctx()))
    assert len(blob) < 2000, f"the refusal record has grown to {len(blob)} bytes"


# ---------------------------------------------------------------------------------------------
# 4 · ⛔ the mutation shapes this programme has already paid for
# ---------------------------------------------------------------------------------------------

def test_both_refusal_paths_actually_REACH_the_recorder() -> None:
    """⛔ In L4, a boundary was IMPORTED and never USED while 15 tests passed. Read from the AST,
    docstring excluded BY IDENTITY rather than by value."""
    for fn in (outbox._defer, outbox._suppress):
        tree = ast.parse(inspect.getsource(fn).lstrip())
        body = tree.body[0].body
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
            body = body[1:]
        called = {n.func.id for stmt in body for n in ast.walk(stmt)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "describe_decision" in called, f"{fn.__name__} never calls the recorder"


def test_the_defer_path_now_reads_the_context_it_accepts() -> None:
    """⛔ `_defer` took `context` and used nothing from it. A parameter accepted and ignored is
    presence without effect in the signature, and the one thing a deferral's reader wants — the
    tenant's own window — was inside it."""
    tree = ast.parse(inspect.getsource(outbox._defer).lstrip())
    body = tree.body[0].body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    names = {n.id for stmt in body for n in ast.walk(stmt) if isinstance(n, ast.Name)}
    assert "context" in names, "_defer still ignores the context it is handed"


# ---------------------------------------------------------------------------------------------
# 5 · the declaration
# ---------------------------------------------------------------------------------------------

def test_the_declaration_no_longer_claims_it_is_unwired() -> None:
    assert "gate.describe_decision" not in H.UNREACHED
    assert "gate.describe_decision" not in H.DECLARED
    assert H.now_called() == (), f"a declared entry acquired a caller: {H.now_called()}"
    assert H.undeclared() == (), f"something became unreached: {H.undeclared()}"
