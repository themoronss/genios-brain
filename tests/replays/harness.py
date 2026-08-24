"""The replay harness: pinned world, disabled model, deterministic double-run.

Everything here exists to make one sentence checkable: *given exactly this evidence, the system
must reach exactly this decision, and must refuse when the evidence is not there.*
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

SPEC_DIR = Path(__file__).parent / "specs"

#: The replay clock. Every fixture timestamp is expressed relative to this instant, so a replay
#: reads the same in June as in December. Nothing in a replay may call `datetime.now()`.
REPLAY_NOW = datetime(2026, 8, 22, 9, 0, tzinfo=timezone.utc)

#: Pinned world versions. A decision that changes when these do not is non-deterministic; a
#: decision that does NOT change when these do is ignoring its own provenance.
PINNED = {
    "graph_version": 4_211,
    "config_snapshot_id": "cfg_replay_v1",
    "corpus_version": "expertise@replay.v1",
    "pack": ("sales", "1.10.0"),
}


class NoLLM:
    """A model that refuses to be called.

    Determinism is the property under test, so a replay that quietly reached a model would be
    testing the model instead. Any call is a failure with a legible message rather than a silent
    fallback — a fallback would make the suite pass for the wrong reason.
    """

    calls: int = 0

    def call(self, *_a, **_kw):        # noqa: D102 — the message is the documentation
        NoLLM.calls += 1
        raise AssertionError(
            "a golden replay reached the LLM. Replays assert deterministic reasoning; if a "
            "decision needs a model to be reached, it is not a decision the replay can pin.")


@dataclass(frozen=True)
class Mutation:
    """One row of a replay's deterministic-mutations table."""

    mutation: str
    expected_decision: str
    prohibited: str
    pass_condition: str
    implemented: str                    # possible_today | blocked_missing_capability
    blocked_on: str = ""

    @property
    def is_blocked(self) -> bool:
        return self.implemented != "possible_today"


@dataclass(frozen=True)
class ReplaySpec:
    """A golden replay, transcribed from its specification document."""

    replay_id: str
    slug: str
    title: str
    failure_class: str
    summary: str
    mutations: tuple[Mutation, ...]
    business_subject: str = ""
    open_loop: str = ""
    why_now: str = ""
    current_failure: str = ""
    expected_behavior: str = ""
    layer_obligations: tuple[dict[str, str], ...] = ()
    prohibited_behaviors: tuple[str, ...] = ()
    passes_today: bool = False
    source: str = field(default="", compare=False)

    @property
    def blocked(self) -> tuple[Mutation, ...]:
        return tuple(m for m in self.mutations if m.is_blocked)

    @property
    def runnable(self) -> tuple[Mutation, ...]:
        return tuple(m for m in self.mutations if not m.is_blocked)


def _spec_from_dict(d: dict[str, Any], source: str = "") -> ReplaySpec:
    return ReplaySpec(
        replay_id=d["replay_id"],
        slug=d["slug"],
        title=d["title"],
        failure_class=d["failure_class"],
        summary=d["summary"],
        mutations=tuple(Mutation(
            mutation=m["mutation"], expected_decision=m["expected_decision"],
            prohibited=m["prohibited"], pass_condition=m["pass_condition"],
            implemented=m["implemented"], blocked_on=m.get("blocked_on", "") or "")
            for m in d.get("mutations", [])),
        business_subject=d.get("business_subject", "") or "",
        open_loop=d.get("open_loop", "") or "",
        why_now=d.get("why_now", "") or "",
        current_failure=d.get("current_failure", "") or "",
        expected_behavior=d.get("expected_behavior", "") or "",
        layer_obligations=tuple(d.get("layer_obligations", []) or ()),
        prohibited_behaviors=tuple(d.get("prohibited_behaviors", []) or ()),
        passes_today=bool(d.get("passes_today", False)),
        source=source,
    )


def load_specs() -> tuple[ReplaySpec, ...]:
    """Every transcribed replay, ordered by id.

    Missing specs are a hard error, not an empty run: a harness that silently reports "0 replays
    passed" is the failure mode this whole module exists to prevent.
    """
    if not SPEC_DIR.is_dir():
        raise AssertionError(f"replay specs directory missing: {SPEC_DIR}")
    files = sorted(SPEC_DIR.glob("*.json"))
    if not files:
        raise AssertionError(f"no replay specs found under {SPEC_DIR}")
    return tuple(sorted((_spec_from_dict(json.loads(p.read_text()), source=p.name) for p in files),
                        key=lambda s: s.replay_id))


def blocked_marker(mutation: Mutation) -> pytest.MarkDecorator:
    """Mark a mutation the engine cannot yet express.

    `strict=True` is the whole point: when the missing capability lands, this assertion starts
    passing, pytest fails it as an unexpected pass, and the marker must be removed. A blocked
    assertion therefore cannot outlive the gap it documents.
    """
    return pytest.mark.xfail(strict=True, reason=(
        f"blocked: {mutation.blocked_on or 'capability not implemented'} — "
        f"required: {mutation.expected_decision}"))
