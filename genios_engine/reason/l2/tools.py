"""GeniOS-008 L2 R7 · the Tool Gateway — the arithmetic the model is never asked to do.

The spec's line (Context-First §3): deterministic code supports the reasoning — retrieval, ids, exact
arithmetic when a numeric question really arises — and never decides. So the tools here compute, from the
run's own inputs and `eval_time` only (no clock, no database, no network), the few numbers a judgment
about timing needs: how long since the newest signal, whose turn it is, the nearest due date and whether
it has passed, how many of their messages wait behind our last one. Each result is printed in the TOOLS
block under a `tool:` id with the n it rests on, so the model may cite it and the check can hold a number
the model repeats to the line that printed it.

This is where the 23 formula reasoners' useful arithmetic belongs (L2-H1): a date window, a count, a gap
— as EVIDENCE. Their scores (risk, priority, confidence) are not tools and are not carried.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .inputs import L2Signal


@dataclass(frozen=True, slots=True)
class ToolResult:
    tool_id: str                      # `tool:<name>` — what the dossier prints and a fact may cite
    says: str                         # one line, the number in it
    value: Any                        # the value, for the receipt


def _hours(later: datetime, earlier: datetime) -> int:
    return int((later - earlier).total_seconds() // 3600)


def run_tools(signals: Sequence[L2Signal], *, eval_time: datetime, file: Any = None) -> tuple[ToolResult, ...]:
    """Every tool that has something to say about these signals at `eval_time`. Pure."""
    out: list[ToolResult] = []
    dated = [s for s in signals if s.occurred_at is not None]
    if dated:
        newest = max(dated, key=lambda s: s.occurred_at)
        h = _hours(eval_time, newest.occurred_at)
        out.append(ToolResult("tool:newest_signal_age", f"the newest signal arrived {h} hours before this run "
                              f"(of {len(dated)} dated signals)", h))
    turns = [s for s in dated if s.ball_in_court and s.ball_in_court != "unknown"]
    if turns:
        last = max(turns, key=lambda s: s.occurred_at)
        out.append(ToolResult("tool:whose_turn", f"as of the newest signal with a turn, the turn is with: "
                              f"{last.ball_in_court}", last.ball_in_court))
    elif file is not None and getattr(file, "whose_move", None):
        out.append(ToolResult("tool:whose_turn", f"the file says the move is {file.whose_move}", file.whose_move))
    due = [s for s in signals if s.due_at is not None]
    if due:
        nearest = min(due, key=lambda s: s.due_at)
        h = _hours(nearest.due_at, eval_time)
        out.append(ToolResult("tool:nearest_due",
                              (f"the nearest due date is {nearest.due_at:%Y-%m-%d}, {h} hours from now" if h >= 0
                               else f"the nearest due date was {nearest.due_at:%Y-%m-%d}, {-h} hours ago — past due"),
                              {"due_at": nearest.due_at.isoformat(), "hours": h}))
    by_thread: dict[str, list[L2Signal]] = {}
    for s in dated:
        if s.thread_key:
            by_thread.setdefault(s.thread_key, []).append(s)
    waiting = 0
    for thread in by_thread.values():
        ours = [s.occurred_at for s in thread if s.direction == "outbound"]
        last_ours = max(ours) if ours else None
        waiting += sum(1 for s in thread if s.direction == "inbound" and (last_ours is None or s.occurred_at > last_ours))
    if by_thread:
        out.append(ToolResult("tool:unanswered_inbound",
                              f"{waiting} inbound signal(s) arrived after our last message in their thread "
                              f"(over {len(by_thread)} thread(s))", waiting))
    if file is not None and getattr(file, "days_quiet", None) is not None:
        days = int(file.days_quiet)
        out.append(ToolResult("tool:days_quiet", f"the file has been quiet {days} days", days))
    money = amounts_tool(signals)
    if money is not None:
        out.append(money)
    return tuple(out)


def _money(minor: int) -> str:
    return f"{minor // 100:,}.{minor % 100:02d}"


def amounts_tool(signals: Sequence[L2Signal]) -> ToolResult | None:
    """L2 rebuild · the money the signals name, per currency, and — where one currency names two or more — how far
    the largest is above the smallest, in money and in percent. ARITHMETIC ONLY: which amount is the old price and
    which the new is a reading of the words, and that is the model's; this says what the numbers are. Pure."""
    by_cur: dict[str, set[int]] = {}
    for s in signals:
        for cur, minor in getattr(s, "amounts", ()) or ():
            by_cur.setdefault(cur, set()).add(minor)
    if not by_cur:
        return None
    parts, value = [], {}
    for cur in sorted(by_cur):
        amounts = sorted(by_cur[cur])
        said = f"{cur} " + ", ".join(_money(a) for a in amounts)
        entry: dict[str, Any] = {"amounts": amounts}
        low, high = amounts[0], amounts[-1]
        if len(amounts) > 1 and low > 0:
            pct = round((high - low) * 100 / low)
            said += f" — the largest is {pct}% above the smallest ({cur} {_money(high - low)} more)"
            entry.update(difference=high - low, percent=pct)
        parts.append(said)
        value[cur] = entry
    return ToolResult("tool:amounts", "amounts the signals name: " + "; ".join(parts), value)


def measured_inputs(tools: Sequence[ToolResult]) -> dict[str, Any]:
    """The tool results as the plan compiler and the receipt read them."""
    return {t.tool_id.split(":", 1)[1]: t.value for t in tools}


__all__ = ["ToolResult", "measured_inputs", "run_tools"]
