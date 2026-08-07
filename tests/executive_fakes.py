"""An in-memory stand-in for Postgres, so Layer 5's orchestrator can actually execute in CI.

CI has no service containers, which left ``executive/sweep.py`` and ``executive/execution_store.py``
— the two modules that tie the whole layer together — provable only by static analysis. Static
analysis proves the SQL names real columns and binds real parameters. It cannot prove that a
COMPLETE verdict closes the row *and* writes the outcome *and* logs the event, which is the part
that actually matters.

**What this double is, precisely.** It keeps real rows in real dicts and implements what each
statement *means*, dispatching on a distinctive fragment of its text. It is not a SQL engine and
does not pretend to be one: it will not catch a syntax error, a bad join, or a predicate that
means something different in Postgres than it looks like it means.

**So what does it prove?** The control flow. Given a world, does the sweep reach the right
verdict, take the right branch, write the right rows in the right order, and stay idempotent when
run twice. That is the layer's logic, and it is exactly what was untested.

The division of labour is deliberate and worth stating, because a double like this is dangerous
if mistaken for the real thing:

  * ``test_executive_store_schema.py`` proves the SQL is *well-formed* against the migrations.
  * ``test_executive_sweep.py`` (via this file) proves the orchestration is *correct*.
  * A run against real Postgres — still outstanding — proves the two meet.

Every statement the store or sweep can issue must be handled here. An unrecognised statement
raises rather than returning empty: a silent empty result would make a test pass by skipping the
very write it was written to check.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any


class Row(dict):
    """Attribute access on top of a mapping — the two shapes SQLAlchemy rows are used in.

    The store reads results both ways (``row.seat_id`` and ``row["state"]``, plus ``dict(row)``
    in the API), so the double has to support both or it would quietly force the production code
    into one style.
    """

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError as exc:                       # pragma: no cover - diagnostic only
            raise AttributeError(name) from exc


class Result:
    """What ``conn.execute`` returns, in the four shapes Layer 5 consumes."""

    def __init__(self, rows: list[dict] | None = None, rowcount: int | None = None) -> None:
        self._rows = [Row(item) for item in (rows or [])]
        self.rowcount = len(self._rows) if rowcount is None else rowcount

    def first(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def all(self):
        return list(self._rows)

    def scalar(self):
        return next(iter(self._rows[0].values())) if self._rows else None

    def mappings(self):
        return self


class UnhandledStatement(AssertionError):
    """A statement this double does not model.

    Raised, never swallowed. If a new query were answered with an empty result by default, the
    first test to depend on it would pass while proving nothing — which is worse than no test.
    """


class FakeDB:
    """The world: five Layer 5 tables plus the handful of upstream rows the layer reads."""

    def __init__(self, *, org_id: str = "org_1") -> None:
        self.org_id = org_id
        # Layer 5's own tables.
        self.executions: list[dict] = []
        self.execution_actions: list[dict] = []
        self.execution_escalations: list[dict] = []
        self.execution_events: list[dict] = []
        self.execution_outcomes: list[dict] = []
        # The world Layer 5 reads but never writes.
        self.seats: dict[str, dict] = {}
        self.channels: list[str] = []
        self.observations: list[dict] = []          # {node_id, kind, occurred_at}
        self.facts: dict[str, dict] = {}            # node_id -> {field: value}
        self.nodes: dict[str, dict] = {}            # node_id -> attrs
        self.plannable: list[dict] = []             # rows the authority query would return
        self.authority_ok: bool = True
        # Layer 5.2's tables, so the executive→delivery bridge can be exercised end to end.
        self.delivery_outbox: list[dict] = []
        self.cards: list[dict] = []                 # {card_id, signal_id}
        # Everything that ran, for order-of-writes assertions.
        self.log: list[tuple[str, dict]] = []

    # -- helpers a test uses to set the world up ------------------------------------------

    def add_seat(self, seat_id: str, *, email: str = "", role: str = "member",
                 active: bool = True, manager: str | None = None) -> None:
        self.seats[seat_id] = {"seat_id": seat_id, "email": email, "role": role,
                               "active": active, "manager_seat_id": manager}

    def observe(self, node_id: str, kind: str, at: datetime) -> None:
        self.observations.append({"node_id": node_id, "kind": kind, "occurred_at": at})

    def set_facts(self, node_id: str, facts: dict, attrs: dict | None = None) -> None:
        self.facts[node_id] = dict(facts)
        self.nodes[node_id] = dict(attrs or {})

    def open_execution(self) -> dict | None:
        return next((row for row in self.executions if row["closed_at"] is None), None)

    def events_of(self, kind: str) -> list[dict]:
        return [item for item in self.execution_events if item["kind"] == kind]

    def statements(self) -> list[str]:
        return [sql for sql, _ in self.log]

    # -- dispatch ---------------------------------------------------------------------------

    def execute(self, sql: str, params: dict) -> Result:
        self.log.append((sql, dict(params)))
        for fragment, handler in self._routes():
            if fragment in sql:
                return handler(sql, params)
        raise UnhandledStatement(f"the fake database does not model: {sql[:160]}")

    def _routes(self):
        # Ordered most-specific first: "select 1 from org_seats" must not be caught by the
        # broader org_seats route, and the manager join must not be caught by either.
        return (
            # The Layer 5.2 bridge. Matched first because these join across both layers' tables
            # and would otherwise be caught by the single-table routes below.
            ("from execution_events e join executions x", self._notifiable_events),
            ("from executions x join cards k", self._linkable_commitments),
            ("insert into delivery_outbox", self._insert_outbox),
            ("update executions set card_id=", self._link_card),
            ("insert into execution_events", self._insert_event),
            ("insert into executions", self._insert_execution),
            ("insert into execution_actions", self._insert_action),
            ("insert into execution_escalations", self._insert_escalation),
            ("insert into execution_outcomes", self._insert_outcome),
            # Supersede is a literal-state update and must be matched before the generic
            # guarded transition, which would otherwise swallow it and look for a :frm bind
            # that this statement does not carry.
            ("update executions set state='cancelled'", self._supersede),
            ("update executions set state=", self._transition),
            ("update executions set reminder_count", self._count_reminder),
            ("update execution_escalations set fired_at", self._fire_rung),
            ("update executions set escalation_count", self._count_escalation),
            ("update execution_actions set completed_at", self._complete_action),
            ("update executions set first_touch_at", self._touch),
            ("update executions set assignee", self._reassign),
            ("update executions set next_check_at", self._schedule),
            ("update executions set delivered_at", self._deliver),
            ("select * from executions where org_id=", self._load_execution),
            ("select * from executions where closed_at is null", self._due),
            # The API's projections. Matched by their trailing clauses so they cannot be
            # confused with the store's own single-purpose reads above.
            ("capability_id, payload from executions", self._api_commitment),
            # Matched on the queue's distinctive ordering rather than on its where clause: the
            # where clause is assembled from optional filters and its shortest form is a prefix
            # of the API's own open-row existence check.
            ("order by closed_at is not null", self._api_queue),
            ("from execution_actions where org_id=:o and execution_id=:x order by ordinal",
             self._api_actions),
            ("from execution_escalations where org_id=:o and execution_id=:x order by day_offset",
             self._api_ladder),
            ("from execution_events where org_id=:o and execution_id=:x order by occurred_at",
             self._api_events),
            ("select detail,occurred_at from execution_events", self._delivery_reminder),
            ("select event_id from execution_events", self._delivery_superseding_event),
            ("select graph_version from graph_versions", self._graph_version),
            ("select id from orgs where id=", self._org),
            ("select payload,state,signal_id from executions", self._execution_delivery_row),
            ("select reminder_count, last_reminded_at from executions", self._reminder_state),
            ("select execution_id from executions", self._superseding),
            ("select day_offset from execution_escalations", self._fired_days),
            ("select action_id, completed_at from execution_actions", self._completions),
            ("select 1 from execution_events", self._dismissed),
            ("select 1 from executions where org_id=", self._execution_is_open),
            ("select 1 from signals s", self._authority),
            ("select kind, max(occurred_at)", self._observed),
            ("select 1 from graph_nodes", self._node_exists),
            ("select attrs from graph_nodes", self._node_attrs),
            ("select field, value from graph_facts", self._node_facts),
            ("select value from graph_facts", self._subject_status),
            ("select channel from org_channels", self._active_channels),
            ("join org_seats m", self._manager_of),
            ("role='admin'", self._admins),
            ("select 1 from org_seats", self._seat_is_active),
            ("select seat_id from org_seats", self._active_seat),
            ("from signals s", self._plannable),
        )

    # -- writes -------------------------------------------------------------------------------

    def _insert_event(self, sql, p) -> Result:
        # `detail` is jsonb: Postgres hands it back as a parsed object, not the string that was
        # cast in. Storing the string here would let a test read a shape production never sees.
        self.execution_events.append({
            "event_id": p["e"], "org_id": p["o"], "execution_id": p["x"], "kind": p["k"],
            "reason_code": p["r"], "actor": p["a"], "from_state": p["f"], "to_state": p["t"],
            "detail": json.loads(p["d"]) if isinstance(p["d"], str) else p["d"],
            "occurred_at": p["at"]})
        return Result(rowcount=1)

    def _insert_execution(self, sql, p) -> Result:
        # The partial unique index: one live commitment per decision. A second insert is
        # absorbed, which is what makes the planning pass safe to run on a timer.
        clash = any(row["decision_hash"] == p["dh"] and row["closed_at"] is None
                    for row in self.executions)
        if clash:
            return Result([])
        self.executions.append({
            "org_id": p["o"], "execution_id": p["x"], "decision_hash": p["dh"],
            "reasoning_run_id": p["rr"], "candidate_id": p["cd"], "context_snapshot_id": p["cs"],
            "config_snapshot_id": p["cfg"], "capability_id": p["cap"],
            "capability_version": p["capv"], "play_id": p["play"], "plan_hash": p["ph"],
            "plan_revision": 1, "state": p["st"], "goal": p["goal"], "subject_ref": p["sref"],
            "subject_type": p["stype"], "assignee": p["asg"], "audience": p["aud"],
            "channel_id": p["ch"], "channel_class": p["chc"], "interrupt": p["int"],
            "routing_rule": p["rule"], "priority_bp": p["pri"], "confidence_bp": p["conf"],
            "band": p["band"], "created_at": p["cat"], "deadline_at": p["dl"],
            "expires_at": p["exp"], "next_check_at": p["nca"], "delivered_at": None,
            "first_touch_at": None, "closed_at": None, "close_reason": None,
            "superseded_by": None, "reminder_count": 0, "last_reminded_at": None,
            "escalation_count": 0, "card_id": p["card"], "signal_id": p["sig"],
            "payload": p["pl"]})
        return Result([{"execution_id": p["x"]}])

    def _insert_action(self, sql, p) -> Result:
        key = (p["o"], p["x"], p["a"])
        if any((r["org_id"], r["execution_id"], r["action_id"]) == key
               for r in self.execution_actions):
            return Result(rowcount=0)
        self.execution_actions.append({
            "org_id": p["o"], "execution_id": p["x"], "action_id": p["a"], "ordinal": p["ord"],
            "stage": p["stg"], "kind": p["k"], "label": p["l"], "requires_approval": p["ra"],
            "read_only": p["ro"], "deadline_at": p["dl"], "completed_at": None,
            "completed_by": None})
        return Result(rowcount=1)

    def _insert_escalation(self, sql, p) -> Result:
        key = (p["o"], p["x"], p["d"])
        if any((r["org_id"], r["execution_id"], r["day_offset"]) == key
               for r in self.execution_escalations):
            return Result(rowcount=0)
        self.execution_escalations.append({
            "org_id": p["o"], "execution_id": p["x"], "day_offset": p["d"], "action": p["a"],
            "audience": p["au"], "interrupt": p["i"], "fires_at": p["f"], "fired_at": None,
            "target_seat": None, "reason_code": p["r"]})
        return Result(rowcount=1)

    def _insert_outcome(self, sql, p) -> Result:
        if any(r["execution_id"] == p["x"] for r in self.execution_outcomes):
            return Result(rowcount=0)
        self.execution_outcomes.append({
            "outcome_id": p["id"], "org_id": p["o"], "execution_id": p["x"],
            "decision_hash": p["dh"], "capability_id": p["cap"], "play_id": p["p"],
            "terminal_state": p["ts"], "reason_code": p["rc"], "label": p["lb"],
            "created_at": p["cat"], "closed_at": p["clo"], "seconds_to_close": p["sec"],
            "actions_total": p["at_"], "actions_completed": p["ac"], "progress_bp": p["pb"],
            "reminders_sent": p["rs"], "escalations_fired": p["ef"], "band": p["band"],
            "routing_rule": p["rule"], "outcome_kind": p["ok"], "assignee": p["asg"],
            "subject_ref": p["sref"]})
        return Result(rowcount=1)

    def _row(self, p):
        return next((r for r in self.executions
                     if r["org_id"] == p.get("o") and r["execution_id"] == p.get("x")), None)

    def _transition(self, sql, p) -> Result:
        row = self._row(p)
        # The guarded update: state must still be what the caller believed it was. A lost race
        # is a rowcount of zero, never an overwrite.
        if row is None or row["state"] != p["frm"] or row["closed_at"] is not None:
            return Result(rowcount=0)
        row["state"] = p["to"]
        if p["close"]:
            row["closed_at"] = p["at"]
            row["close_reason"] = p["reason"]
            row["next_check_at"] = None
        else:
            row["next_check_at"] = p["nca"]
        return Result(rowcount=1)

    def _count_reminder(self, sql, p) -> Result:
        row = self._row(p)
        if row is None:
            return Result(rowcount=0)
        row["reminder_count"] += 1
        row["last_reminded_at"] = p["at"]
        row["next_check_at"] = p["nca"]
        return Result(rowcount=1)

    def _fire_rung(self, sql, p) -> Result:
        rung = next((r for r in self.execution_escalations
                     if r["execution_id"] == p["x"] and r["day_offset"] == p["d"]
                     and r["fired_at"] is None), None)
        if rung is None:
            return Result(rowcount=0)
        rung["fired_at"] = p["at"]
        rung["target_seat"] = p["t"]
        return Result(rowcount=1)

    def _count_escalation(self, sql, p) -> Result:
        row = self._row(p)
        if row is not None:
            row["escalation_count"] += 1
        return Result(rowcount=1 if row else 0)

    def _complete_action(self, sql, p) -> Result:
        action = next((r for r in self.execution_actions
                       if r["execution_id"] == p["x"] and r["action_id"] == p["a"]
                       and r["completed_at"] is None), None)
        if action is None:
            return Result(rowcount=0)
        action["completed_at"] = p["at"]
        action["completed_by"] = p["by"]
        return Result(rowcount=1)

    def _touch(self, sql, p) -> Result:
        row = self._row(p)
        if row is not None and row["first_touch_at"] is None:
            row["first_touch_at"] = p["at"]
        return Result(rowcount=1 if row else 0)

    def _reassign(self, sql, p) -> Result:
        row = self._row(p)
        if row is None or row["closed_at"] is not None:
            return Result(rowcount=0)
        row["assignee"], row["audience"], row["routing_rule"] = p["a"], p["au"], p["r"]
        return Result(rowcount=1)

    def _supersede(self, sql, p) -> Result:
        row = self._row(p)
        if row is None or row["closed_at"] is not None:
            return Result(rowcount=0)
        row.update(state="cancelled", closed_at=p["at"], close_reason="replanned",
                   superseded_by=p["by"], next_check_at=None)
        return Result(rowcount=1)

    def _schedule(self, sql, p) -> Result:
        row = self._row(p)
        if row is not None:
            row["next_check_at"] = p["n"]
        return Result(rowcount=1 if row else 0)

    def _deliver(self, sql, p) -> Result:
        row = self._row(p)
        if row is not None and row["delivered_at"] is None:
            row["delivered_at"] = p["n"]
        return Result(rowcount=1 if row else 0)

    # -- reads ----------------------------------------------------------------------------------

    def _load_execution(self, sql, p) -> Result:
        row = self._row(p)
        return Result([row] if row else [])

    def _due(self, sql, p) -> Result:
        now = p["n"]
        rows = [r for r in self.executions
                if r["closed_at"] is None
                and (r["next_check_at"] is None or r["next_check_at"] <= now)
                and (("o" not in p) or r["org_id"] == p["o"])]
        rows.sort(key=lambda r: (r["next_check_at"] is not None,
                                 -r["priority_bp"], r["execution_id"]))
        return Result(rows[:p["l"]])

    @staticmethod
    def _projection(sql: str) -> list[str]:
        """The column list the caller actually asked for.

        Read off the statement rather than hard-coded, so the double cannot quietly hand back a
        column the API stopped selecting — which is exactly how a test starts asserting on a
        field production no longer returns.
        """
        head = sql.split(" from ", 1)[0]
        return [name.strip() for name in head.removeprefix("select ").split(",")]

    def _project(self, sql: str, row: dict) -> dict:
        return {name: row.get(name) for name in self._projection(sql)}

    def _api_queue(self, sql, p) -> Result:
        rows = [r for r in self.executions if r["org_id"] == p["o"]]
        if "closed_at is null" in sql:
            rows = [r for r in rows if r["closed_at"] is None]
        if "state=:s" in sql:
            rows = [r for r in rows if r["state"] == p["s"]]
        if "assignee=:a" in sql:
            rows = [r for r in rows if r["assignee"] == p["a"]]
        rows.sort(key=lambda r: (r["closed_at"] is not None, r["deadline_at"],
                                 -r["priority_bp"]))
        return Result([self._project(sql, r) for r in rows[:p["l"]]])

    def _api_commitment(self, sql, p) -> Result:
        row = self._row(p)
        return Result([self._project(sql, row)] if row else [])

    def _api_actions(self, sql, p) -> Result:
        rows = sorted((r for r in self.execution_actions if r["execution_id"] == p["x"]),
                      key=lambda r: r["ordinal"])
        return Result([self._project(sql, r) for r in rows])

    def _api_ladder(self, sql, p) -> Result:
        rows = sorted((r for r in self.execution_escalations if r["execution_id"] == p["x"]),
                      key=lambda r: r["day_offset"])
        return Result([self._project(sql, r) for r in rows])

    def _api_events(self, sql, p) -> Result:
        rows = sorted((r for r in self.execution_events if r["execution_id"] == p["x"]),
                      key=lambda r: r["occurred_at"], reverse=True)
        return Result([self._project(sql, r) for r in rows[:100]])

    def _reminder_state(self, sql, p) -> Result:
        row = self._row(p)
        return Result([{"reminder_count": row["reminder_count"],
                        "last_reminded_at": row["last_reminded_at"]}] if row else [])

    def _fired_days(self, sql, p) -> Result:
        return Result([{"day_offset": r["day_offset"]} for r in self.execution_escalations
                       if r["execution_id"] == p["x"] and r["fired_at"] is not None])

    def _completions(self, sql, p) -> Result:
        return Result([{"action_id": r["action_id"], "completed_at": r["completed_at"]}
                       for r in self.execution_actions
                       if r["execution_id"] == p["x"] and r["completed_at"] is not None])

    def _superseding(self, sql, p) -> Result:
        rows = [r for r in self.executions
                if r["subject_ref"] == p["n"] and r["play_id"] == p["p"]
                and r["closed_at"] is None and r["execution_id"] != p["x"]
                and r["created_at"] > p["cat"]]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return Result([{"execution_id": rows[0]["execution_id"]}] if rows else [])

    def _dismissed(self, sql, p) -> Result:
        hit = any(e["execution_id"] == p["x"] and e["kind"] == "execution.cancelled"
                  and e["reason_code"] == "human_dismissed" for e in self.execution_events)
        return Result([{"?": 1}] if hit else [])

    def _delivery_reminder(self, sql, p) -> Result:
        row = next((event for event in self.execution_events
                    if event["org_id"] == p["o"] and event["execution_id"] == p["x"]
                    and event["event_id"] == p["event"]
                    and event["kind"] == "execution.reminded"), None)
        return Result([{"detail": row["detail"], "occurred_at": row["occurred_at"]}]
                      if row else [])

    def _delivery_superseding_event(self, sql, p) -> Result:
        stale_kinds = {
            "execution.action_completed", "execution.reminded", "execution.started",
            "execution.waiting", "execution.blocked", "execution.unblocked",
            "execution.replanned", "execution.completed", "execution.cancelled",
            "execution.expired", "execution.archived",
        }
        if "event" not in p:
            hit = next((event for event in self.execution_events
                        if event["org_id"] == p["o"]
                        and event["execution_id"] == p["x"]
                        and event["kind"] in stale_kinds), None)
        else:
            hit = next((event for event in self.execution_events
                        if event["org_id"] == p["o"] and event["execution_id"] == p["x"]
                        and event["event_id"] != p["event"]
                        and ((event["kind"] == "execution.cancelled"
                              and event["reason_code"] == "human_dismissed")
                             or (event["kind"] == "execution.reminded" and
                                 (event["occurred_at"] > p["reminded"] or
                                  (event["occurred_at"] == p["reminded"] and
                                   event["event_id"] > p["event"])))
                             or (event["occurred_at"] >= p["reminded"]
                                 and event["kind"] in stale_kinds
                                 and event["kind"] != "execution.reminded"))), None)
        return Result([{"event_id": hit["event_id"]}] if hit else [])

    def _graph_version(self, sql, p) -> Result:
        return Result([{"graph_version": 1}])

    def _org(self, sql, p) -> Result:
        return Result([{"id": p["o"]}] if p.get("o") == self.org_id else [])

    def _execution_delivery_row(self, sql, p) -> Result:
        row = self._row(p)
        if row is None or row["closed_at"] is not None:
            return Result([])
        if row["state"] not in {"pending", "running", "waiting", "blocked"}:
            return Result([])
        if "now" in p and row["expires_at"] <= p["now"]:
            return Result([])
        if any(event["execution_id"] == p["x"]
               and event["kind"] == "execution.cancelled"
               and event["reason_code"] == "human_dismissed"
               for event in self.execution_events):
            return Result([])
        return Result([{"payload": row["payload"], "state": row["state"],
                        "signal_id": row.get("signal_id")}])

    def _execution_is_open(self, sql, p) -> Result:
        row = self._row(p)
        if row is None or row["closed_at"] is not None:
            return Result([])
        # The bridge's pre-send liveness check adds an expiry bound; the API's open-row check
        # does not. Honouring :now only when it is bound keeps one handler honest for both.
        if "now" in p and row["expires_at"] <= p["now"]:
            return Result([])
        if "human_dismissed" in sql and any(
                event["execution_id"] == p["x"]
                and event["kind"] == "execution.cancelled"
                and event["reason_code"] == "human_dismissed"
                for event in self.execution_events):
            return Result([])
        return Result([{"?": 1}])

    def _notifiable_events(self, sql, p) -> Result:
        kinds, channel = set(p["kinds"]), p["ch"]
        rows = []
        for event in sorted(self.execution_events, key=lambda e: e["occurred_at"]):
            if event["org_id"] != p["o"] or event["kind"] not in kinds:
                continue
            row = next((r for r in self.executions
                        if r["execution_id"] == event["execution_id"]), None)
            if row is None or row["closed_at"] is not None:
                continue
            if row["channel_id"] != channel or row["assignee"] is None:
                continue
            key = f"{p['prefix']}{event['execution_id']}:{event['event_id']}"
            if any(o["card_id"] == key and o["channel"] == channel
                   for o in self.delivery_outbox):
                continue
            rows.append({"event_id": event["event_id"],
                         "execution_id": event["execution_id"],
                         "reason_code": event["reason_code"], "detail": event["detail"],
                         "occurred_at": event["occurred_at"], "goal": row["goal"],
                         "assignee": row["assignee"], "card_id": row["card_id"],
                         # Layer 5's own routing decision, carried through to the outbox row so
                         # Layer 5.2's gate judges *when* using what Layer 5 actually decided.
                         "band": row["band"], "channel_class": row["channel_class"],
                         "interrupt": row["interrupt"]})
        return Result(rows[:p["l"]])

    def _insert_outbox(self, sql, p) -> Result:
        if any(o["org_id"] == p["o"] and o["card_id"] == p["c"] and o["channel"] == p["ch"]
               for o in self.delivery_outbox):
            return Result(rowcount=0)
        # The delivery object travels with the row (migration 0042). Defaults mirror the column
        # defaults so a caller that predates the gate still produces a judgeable candidate.
        self.delivery_outbox.append({"id": p["i"], "org_id": p["o"], "card_id": p["c"],
                                     "channel": p["ch"], "payload": p["p"],
                                     "status": "queued",
                                     "recipient": p.get("seat"),
                                     "band": p.get("band", "standard"),
                                     "channel_class": p.get("cclass", "chat"),
                                     "interrupt": bool(p.get("interrupt", False)),
                                     "defer_count": 0})
        return Result(rowcount=1)

    def _linkable_commitments(self, sql, p) -> Result:
        rows = []
        for row in self.executions:
            if (row["org_id"] != p["o"] or row["card_id"] is not None
                    or row["signal_id"] is None or row["closed_at"] is not None):
                continue
            card = next((c for c in self.cards if c["signal_id"] == row["signal_id"]), None)
            if card is not None:
                rows.append({"execution_id": row["execution_id"], "card_id": card["card_id"]})
        return Result(rows[:p["l"]])

    def _link_card(self, sql, p) -> Result:
        row = self._row(p)
        if row is None or row["card_id"] is not None:
            return Result(rowcount=0)
        row["card_id"] = p["c"]
        return Result(rowcount=1)

    def _authority(self, sql, p) -> Result:
        return Result([{"?": 1}] if self.authority_ok else [])

    def _observed(self, sql, p) -> Result:
        wanted, node, since = set(p["k"]), p["n"], p["since"]
        seen: dict[str, datetime] = {}
        for item in self.observations:
            if item["node_id"] != node or item["kind"] not in wanted:
                continue
            if item["occurred_at"] <= since:
                continue
            current = seen.get(item["kind"])
            if current is None or item["occurred_at"] > current:
                seen[item["kind"]] = item["occurred_at"]
        return Result([{"kind": kind, "seen": at} for kind, at in sorted(seen.items())])

    def _node_exists(self, sql, p) -> Result:
        return Result([{"?": 1}] if p["n"] in self.nodes else [])

    def _node_attrs(self, sql, p) -> Result:
        return Result([{"attrs": self.nodes[p["n"]]}] if p["n"] in self.nodes else [])

    def _node_facts(self, sql, p) -> Result:
        return Result([{"field": field, "value": value}
                       for field, value in sorted(self.facts.get(p["n"], {}).items())])

    def _subject_status(self, sql, p) -> Result:
        for field in ("account.status", "deal.status", "relationship.status"):
            if field in self.facts.get(p["n"], {}):
                return Result([{"value": self.facts[p["n"]][field]}])
        return Result([])

    def _active_channels(self, sql, p) -> Result:
        return Result([{"channel": name} for name in self.channels])

    def _manager_of(self, sql, p) -> Result:
        seat = self.seats.get(p["s"]) or {}
        manager = self.seats.get(seat.get("manager_seat_id") or "")
        return Result([{"seat_id": manager["seat_id"]}] if manager and manager["active"] else [])

    def _admins(self, sql, p) -> Result:
        return Result([{"seat_id": s} for s in sorted(
            k for k, v in self.seats.items() if v["active"] and v["role"] == "admin")])

    def _seat_is_active(self, sql, p) -> Result:
        seat = self.seats.get(p["s"])
        return Result([{"?": 1}] if seat and seat["active"] else [])

    def _active_seat(self, sql, p) -> Result:
        needle = str(p.get("s") or "").lower()
        for seat_id, seat in self.seats.items():
            if not seat["active"]:
                continue
            if seat_id.lower() == needle or str(seat["email"]).lower() == needle:
                return Result([{"seat_id": seat_id}])
        return Result([])

    def _plannable(self, sql, p) -> Result:
        taken = {r["decision_hash"] for r in self.executions if r["closed_at"] is None}
        return Result([row for row in self.plannable
                       if row["decision_hash"] not in taken][:p["l"]])


class FakeConn:
    def __init__(self, db: FakeDB) -> None:
        self.db = db

    def execute(self, statement, params=None) -> Result:
        return self.db.execute(" ".join(str(statement).split()), dict(params or {}))


class _Ctx:
    def __init__(self, conn: FakeConn) -> None:
        self.conn = conn

    def __enter__(self) -> FakeConn:
        return self.conn

    def __exit__(self, *exc) -> bool:
        return False


class FakeEngine:
    """``begin()`` and ``connect()`` both hand back the same connection.

    Transaction isolation is not modelled, deliberately. The sweep's per-row transaction exists
    so one malformed commitment cannot roll back the twenty processed before it, and that
    property is proven by the error-path test rather than by emulating MVCC here — pretending to
    model transactions would be the kind of half-truth that makes a double dangerous.
    """

    def __init__(self, db: FakeDB) -> None:
        self.db = db
        self._conn = FakeConn(db)

    def begin(self) -> _Ctx:
        return _Ctx(self._conn)

    def connect(self) -> _Ctx:
        return _Ctx(self._conn)


__all__ = ["FakeConn", "FakeDB", "FakeEngine", "Result", "Row", "UnhandledStatement"]
