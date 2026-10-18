r"""A card becomes deliverable the moment a channel exists.

⛔ WHAT WAS WRONG. `outbox.revive_undeliverable` — *"Re-open every row this org parked only because
it had nowhere to send it… **This is the answer to 'a card must become deliverable the moment a
channel exists'.** The alternative designs were considered and rejected"* — had **no caller.** It
listed the two designs it beat to get there, and nothing invoked it.

The failure had a shape: **a tenant registers Slack on Tuesday, and every card parked before Tuesday
— parked ONLY because there was nowhere to send it — stays parked forever.**

⛔ AND THE PLAN WAS WRONG ABOUT ITS OWN RISK, IN THE DIRECTION OF CAUSING HARM. `STEP-15 §3` said a
revived card must not resurrect one past `expires_at`, and proposed adding that bound. The function's
own docstring refutes it:

    "Reviving a stale card is SAFE, and that is not an accident of ordering: the drain re-proves
     graph/pack/card authority immediately before every send, so a revived row whose card has since
     expired or been revoked is `cancelled` on its way out rather than delivered. Waking an old
     message and letting the authority check kill it is strictly better than leaving it dead,
     because the second option cannot tell 'we chose not to send' from 'we lost it'."

⛔ **The proposed bound would have destroyed exactly that distinction** — the third retracted fix in
this programme, after L4's F9 and F10.

⛔ AND THE OTHER `org_channels` WRITER IS A TRAP. `platform/seats.py` writes the `in_app` PULL
surface, and says so: *"It is emphatically NOT a transport… Making that row a transport is what
produced production's entire delivery history: 3 rows, all `failed_terminal`."* So the trigger is the
REGISTRATION route, and the gate is `deliverable_channels` — whose docstring is the reason it is not
a hand-written condition: *"Two conditions, and **every historical delivery failure in this database
is one of them being assumed rather than checked**."*
"""
from __future__ import annotations

import ast
import inspect

import pytest

from genios_engine.api import channel_routes
from genios_engine.deliver import delivery_health as H
from genios_engine.deliver.outbox import NO_TRANSPORT_ERROR, UNDELIVERABLE, revive_undeliverable


class _Conn:
    """A connection that remembers its statements and answers the channel query from a list."""

    def __init__(self, log: list, registered: list[str]) -> None:
        self.log, self.registered = log, registered

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.log.append((sql, dict(params or {})))
        rows = [(ch,) for ch in self.registered] if "from org_channels where" in sql else []

        class _R:
            rowcount = 1

            def __iter__(self_inner):
                return iter(rows)
        return _R()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Engine:
    def __init__(self, registered: list[str]) -> None:
        self.log: list = []
        self.registered = registered
        self.begins = 0

    def begin(self):
        self.begins += 1
        return _Conn(self.log, self.registered)


@pytest.fixture()
def save(monkeypatch):
    """`PUT /channels/slack`, called as a function so FastAPI's Depends is out of the way."""
    def _save(*, registered=("slack",), active=True):
        engine = _Engine(list(registered))
        monkeypatch.setattr(channel_routes, "_graph",
                            type("G", (), {"engine": engine})())
        body = channel_routes.SlackConfig(
            webhook_url="https://hooks.slack.com/services/T/B/x", active=active)
        result = channel_routes.set_slack("org_1", body, org="org_1")
        return result, engine
    return _save


def _revives(engine: _Engine) -> list[dict]:
    return [params for sql, params in engine.log
            if sql.startswith("update delivery_outbox set status='queued'")]


# ---------------------------------------------------------------------------------------------
# 1 · the promise, kept
# ---------------------------------------------------------------------------------------------

def test_registering_a_channel_revives_the_parked_backlog(save) -> None:
    """⛔ THE SENTENCE THE DOCSTRING QUOTES, MADE TRUE."""
    result, engine = save()
    revives = _revives(engine)
    assert len(revives) == 1, f"expected one revive, got {len(revives)}"
    assert revives[0]["ch"] == "slack"
    assert revives[0]["parked"] == UNDELIVERABLE
    assert revives[0]["legacy"] == NO_TRANSPORT_ERROR
    assert result["saved"] is True


def test_the_count_is_returned_and_not_merely_done(save) -> None:
    """⛔ A count nobody can see is a count nobody checks — the lesson `STEP-09` paid for, where a
    record was written and no endpoint read it. The one question this answers is *"did registering
    the channel actually clear my backlog?"*"""
    result, _ = save()
    assert "revived" in result, "the route does not say how many rows it re-opened"
    assert isinstance(result["revived"], int)


def test_the_revive_shares_the_upsert_s_transaction(save) -> None:
    """⛔ One `begin()`, deliberately: the revive must see the row it was triggered by, and a
    registration that commits without it leaves the backlog parked until somebody re-saves the same
    webhook."""
    _, engine = save()
    assert engine.begins == 1, f"the route opened {engine.begins} transactions"
    sqls = [sql for sql, _ in engine.log]
    assert any(s.startswith("insert into org_channels") for s in sqls)
    assert sqls.index(next(s for s in sqls if s.startswith("insert into org_channels"))) < \
        sqls.index(next(s for s in sqls
                        if s.startswith("update delivery_outbox set status='queued'"))), \
        "the revive ran before the registration it is triggered by"


# ---------------------------------------------------------------------------------------------
# 2 · ⛔ the gate — and the trap the plan did not know about
# ---------------------------------------------------------------------------------------------

def test_a_channel_with_no_adapter_is_never_revived(save) -> None:
    """⛔ THE TRAP. `platform/seats.py` writes the `in_app` PULL surface into the same table, and its
    docstring records what treating it as a transport cost: *"production's entire delivery history:
    3 rows, all `failed_terminal`."* `get_channel('in_app')` is None — there is nothing to send."""
    _, engine = save(registered=("in_app",))
    assert _revives(engine) == [], "a pull surface with no adapter triggered a revive"


def test_an_agent_transport_is_never_revived(save) -> None:
    """⛔ `deliverable_channels` excludes `AGENT_TRANSPORTS` on top of both its conditions, because
    *"a human delivery may never ride an agent transport"* — those rows are resolved against
    `agent_registry`, not `org_channels`."""
    _, engine = save(registered=("agent_push",))
    assert _revives(engine) == []


def test_an_inactive_registration_revives_nothing(save) -> None:
    """A saved-but-disabled channel is not a channel. ⛔ The query is `where org_id=:o and active`,
    so this is carried by the gate rather than by a second condition at the call site."""
    engine = _Engine([])            # `active` is false, so the query returns no rows
    _, eng = save(registered=(), active=False)
    assert _revives(eng) == []


def test_only_the_deliverable_channel_is_revived_when_several_are_registered(save) -> None:
    """⛔ Registered ∩ has-an-adapter ∩ not-an-agent-transport. Today that is exactly `slack`."""
    _, engine = save(registered=("agent_push", "in_app", "slack"))
    revives = _revives(engine)
    assert [r["ch"] for r in revives] == ["slack"]


# ---------------------------------------------------------------------------------------------
# 3 · ⛔ the retraction, asserted so nobody re-adds it
# ---------------------------------------------------------------------------------------------

def test_the_revive_does_not_bound_on_expires_at() -> None:
    """⛔ THE FIX THIS STEP'S PLAN PROPOSED, AND WHY IT WOULD HAVE CAUSED HARM.

    `STEP-15 §3` said a revived card must not resurrect one past `expires_at`. The function's own
    docstring refutes it: the drain re-proves authority immediately before every send, so a revived
    row whose card has expired is **`cancelled` on its way out** — and *"waking an old message and
    letting the authority check kill it is strictly better than leaving it dead, because the second
    option cannot tell 'we chose not to send' from 'we lost it'."*

    An `expires_at` bound destroys exactly that distinction. Third retracted fix in this programme.
    """
    sql = " ".join(inspect.getsource(revive_undeliverable).split()).lower()
    assert "expires_at" not in sql, (
        "an expiry bound was added -- it cannot tell 'we chose not to send' from 'we lost it', "
        "which is the distinction the authority re-check exists to preserve")
    assert "attempts=0" in sql, (
        "the ladder must be clean: none of its slots were ever spent on a real attempt")


def test_the_revive_only_touches_rows_parked_for_this_one_reason() -> None:
    """*"only because it had nowhere to send it"* is a narrow predicate and must stay narrow.
    ⛔ `outbox.py` records that conflating this with a terminal failure *"burned the card forever"*,
    which is why `UNDELIVERABLE` is reported apart — and why the `failed_terminal` clause matches on
    one exact `last_error` string *"written by one branch and one branch only"*."""
    sql = " ".join(inspect.getsource(revive_undeliverable).split())
    assert "status=:parked" in sql
    assert "status='failed_terminal' and last_error=:legacy" in sql
    assert "status='cancelled'" not in sql, "a cancelled row stopped being live; it is not parked"


# ---------------------------------------------------------------------------------------------
# 4 · ⛔ the mutation shapes
# ---------------------------------------------------------------------------------------------

def test_the_gate_is_the_canonical_one_and_not_hand_written() -> None:
    """⛔ `deliverable_channels`'s docstring is the argument: *"Two conditions, and every historical
    delivery failure in this database is one of them being assumed rather than checked."* Writing
    `if body.active and ch == "slack"` at the call site is that mistake, by hand — and it is how
    production ended up with three `failed_terminal` rows on a channel with no transport."""
    tree = ast.parse(inspect.getsource(channel_routes.set_slack).lstrip())
    body = tree.body[0].body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    called = {n.func.id for stmt in body for n in ast.walk(stmt)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "revive_undeliverable" in called, "the route never revives"
    assert "deliverable_channels" in called, (
        "the route decides for itself which channels are deliverable -- re-deriving the two "
        "conditions by hand is the defect `deliverable_channels` exists to remove")


def test_removing_a_channel_does_not_revive() -> None:
    """A DELETE is the opposite event. ⛔ Even if it called the gate, the channel would no longer be
    registered — but it must not call it at all, because the revive is triggered by a channel
    coming into existence."""
    tree = ast.parse(inspect.getsource(channel_routes.remove_slack).lstrip())
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "revive_undeliverable" not in called


# ---------------------------------------------------------------------------------------------
# 5 · ⛔ the milestone
# ---------------------------------------------------------------------------------------------

def test_the_known_unwired_table_is_now_empty() -> None:
    """⛔ `deliver/` has no known-unwired defects left. The table held FIVE on 2026-10-01 —
    `lane_recall` ×3, `card_builder.resolved_person_name`, `outbox.revive_undeliverable` — and
    `STEP-14`, `STEP-08` and this step closed them.

    ⛔ Asserted as a STATE, not a membership list. Three tests in this programme broke by naming
    their contents, the third one written in the very step where I wrote the rule against it:
    **a membership list shrinks every time the work succeeds; an invariant does not.** An empty
    table is a legitimate state, and so is a non-empty one — what matters is that nothing left it
    without acquiring a caller.
    """
    assert H.KNOWN_UNWIRED == {}, (
        f"a defect is back in deliver/, which is fine and must name its step: "
        f"{sorted(H.KNOWN_UNWIRED)}")
    assert H.undeclared() == (), f"something became unreached: {H.undeclared()}"
    assert H.now_called() == (), f"a declared entry acquired a caller: {H.now_called()}"
