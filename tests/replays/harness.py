"""The replay harness: pinned world, disabled model, deterministic double-run.

Everything here exists to make one sentence checkable: *given exactly this evidence, the system
must reach exactly this decision, and must refuse when the evidence is not there.*
"""
from __future__ import annotations

import json
import re
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from genios_engine.capture.semantic import injection as _inj

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


# =================================================================================================
# THE RECORDED MODEL (STEP-01 §3.2) — what a golden case is replayed with
# =================================================================================================
#
# `NoLLM` above is right for a replay that asserts deterministic reasoning. A founder case is the
# other kind: it runs the REAL chain, and no mail reaches memory without a model answer — one mail
# costs about three calls (the junk filter, relevance, extraction). So the answers are recorded,
# once, into a cassette, and replayed by the prompt's own hash.

#: A recorded answer is found by the hash of the prompt it answered, after removing only what the
#: engine mints at random. Two things, both measured by running one case twice and diffing every
#: prompt:
#:
#:   * the injection fence's nonce (`capture/semantic/injection.fence` — 64 fresh bits per prompt,
#:     by design);
#:   * an id `platform/ids.new_id` minted for this run — `sit_<24 hex>` and the like. The
#:     resolution prompt names its situation by one, and a fresh tenant mints a fresh one.
#:
#: Ids are RENUMBERED, not erased: each distinct id becomes `<prefix>_#<n>` in order of first
#: appearance, so a prompt about two situations never reads the same as one about one situation
#: twice. Anything added here must be minted, never content: a rule that forgave content would let
#: a changed prompt replay an old answer, which is the stale cassette this key exists to catch.
_VOLATILE: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(rf"{re.escape(_inj.FENCE_LEAD)}({_inj.OPEN_LABEL}|{_inj.CLOSE_LABEL})_"
                rf"[0-9a-f]{{{_inj.NONCE_CHARS}}}{re.escape(_inj.FENCE_TAIL)}"),
     rf"{_inj.FENCE_LEAD}\1_{'0' * _inj.NONCE_CHARS}{_inj.FENCE_TAIL}"),
)
#: `new_id(prefix)` = `<prefix>_` + 24 hex characters (`platform/ids.py`).
_MINTED_ID = re.compile(r"(?<![0-9A-Za-z_])([a-z]+)_([0-9a-f]{24})(?![0-9A-Za-z])")

#: How a prompt says which model site wrote it: (site, module under `genios_engine/`, the phrase
#: its prompt opens with). `test_recorded_llm` holds each phrase to its module, so a reworded
#: prompt moves its marker instead of turning every call into `unknown`. Order matters only where
#: one phrase contains another (the two junk-filter prompts).
SITE_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("junk_gate", "capture/gate/relevance.py",
     "You are a junk filter deciding whether ONE email"),
    ("junk_gate_batch", "capture/gate/relevance.py",
     "You are a junk filter deciding which of SEVERAL emails"),
    ("relevance", "capture/esqe/relevance.py",
     "You are classifying messages for a company's business-intelligence system."),
    ("domains", "capture/domain/proposer.py",
     "You label a business message with the domains it belongs to."),
    ("extraction", "capture/semantic/profiles.py", "You extract structured facts from"),
    ("resolution", "context/lifecycle/prompt.py",
     "You read ONE message that landed on an open business situation"),
    ("decider", "reason/llm_decision_maker.py",
     "You are the chief of staff of a busy founder."),
    ("r1", "reason/llm_interpretation.py",
     "You are R1, the reader inside GeniOS's reasoning layer."),
    ("narrator", "deliver/render.py", "You are GeniOS, writing ONE decision card"),
    ("bundle_narrator", "reason/bundle/prompt.py",
     "You are the reasoning narrator for GeniOS."),
    ("angle", "context/angles/asker.py", "You classify one subject for an automated system."),
    ("cohort", "context/analytic/cohort.py",
     "A founder described a group of records they want to compare against."),
    ("screen_insight", "reason/moments/screen_insight.py",
     "You sit beside a busy manager and read what is on their screen right now."),
    ("org_rule_extract", "packs/brains/org_rule_extract.py",
     "You are reading ONE internal company document and extracting the RULES it states."),
)


def normalise_prompt(prompt: str) -> str:
    """The prompt with every random token replaced by a fixed one (`_VOLATILE`) and every minted
    id renumbered in order of first appearance (`_MINTED_ID`)."""
    for pattern, replacement in _VOLATILE:
        prompt = pattern.sub(replacement, prompt)
    seen: dict[str, str] = {}

    def renumber(match: re.Match[str]) -> str:
        token = match.group(0)
        if token not in seen:
            prefix = match.group(1)
            seen[token] = f"{prefix}_#{sum(1 for t in seen if t.startswith(prefix + '_')) + 1}"
        return seen[token]

    return _MINTED_ID.sub(renumber, prompt)


def cassette_key(prompt: str) -> str:
    """The engine's own prompt hash (`LLMClient.content_hash`), over the normalised prompt."""
    from genios_engine.context.llm.client import LLMClient
    return LLMClient.content_hash(normalise_prompt(prompt))


def identify_site(prompt: str) -> str:
    """Which model site wrote this prompt, or `unknown`. For reports and the ideal reader only —
    the cassette is keyed by the hash, never by the site."""
    for site, _module, marker in SITE_MARKERS:
        if marker in prompt:
            return site
    return "unknown"


class CassetteMiss(BaseException):
    """The chain asked the model something the cassette does not answer.

    A `BaseException`, deliberately: every model site in the chain sits inside `except Exception`
    so one failed call never stops a sweep. Here that would turn a missing recording into "the
    model said nothing", and the case would be judged on an answer nobody gave.
    """

    def __init__(self, site: str, key: str) -> None:
        self.site, self.key = site, key
        super().__init__(
            f"cassette miss at the {site} site (key {key[:12]}…): the chain asked the model "
            "something this case's recording does not answer. A prompt changed, or the case "
            "reached a site it never reached before — re-record deliberately "
            "(scripts/golden_eval.py --record), never by loosening the key.")


class RecordedLLM:
    """A model that answers only what was recorded. Same `.model` / `.call()` shape as `LLMClient`.

    Thread-safe: `run_sync` and the L2 drain both run thread pools over one client.
    """

    def __init__(self, cassette: Mapping[str, Mapping[str, Any]], *,
                 model: str = "claude-haiku-4-5-20251001") -> None:
        self._cassette = dict(cassette)
        self.model = model
        self._lock = threading.Lock()
        self.calls: list[tuple[str, str]] = []
        self.misses: list[tuple[str, str]] = []

    @staticmethod
    def content_hash(material: str) -> str:
        from genios_engine.context.llm.client import LLMClient
        return LLMClient.content_hash(material)

    def call(self, prompt: str, *, max_tokens: int = 4096, **_kw: Any):
        from genios_engine.context.llm.client import LLMResult
        key, site = cassette_key(prompt), identify_site(prompt)
        with self._lock:
            self.calls.append((site, key))
            entry = self._cassette.get(key)
            if entry is None:
                self.misses.append((site, key))
        if entry is None:
            raise CassetteMiss(site, key)
        parsed = entry.get("parsed")
        return LLMResult(parsed=parsed, raw=entry.get("raw") or json.dumps(parsed),
                         input_tokens=int(entry.get("input_tokens") or 0),
                         output_tokens=int(entry.get("output_tokens") or 0),
                         model=str(entry.get("model") or self.model))


class CassetteRecorder:
    """Wraps a model (the ideal reader, or the live one) and writes down every answer it gives.

    It refuses a failed answer: a cassette holds what the model SAID, and a failure recorded as an
    answer would replay the failure as the model's verdict.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self.model = getattr(inner, "model", "")
        self._lock = threading.Lock()
        self.cassette: dict[str, dict[str, Any]] = {}
        #: The same report a `RecordedLLM` keeps, so a recording run and its replay compare.
        self.calls: list[tuple[str, str]] = []
        self.misses: list[tuple[str, str]] = []

    @staticmethod
    def content_hash(material: str) -> str:
        from genios_engine.context.llm.client import LLMClient
        return LLMClient.content_hash(material)

    def call(self, prompt: str, *, max_tokens: int = 4096, **kw: Any):
        result = self._inner.call(prompt, max_tokens=max_tokens, **kw)
        if not getattr(result, "ok", True):
            raise RuntimeError(f"not recorded — the model call failed: {result.error}")
        entry = {"site": identify_site(prompt), "parsed": result.parsed, "raw": result.raw,
                 "input_tokens": result.input_tokens, "output_tokens": result.output_tokens,
                 "model": result.model}
        with self._lock:
            self.cassette[cassette_key(prompt)] = entry
            self.calls.append((entry["site"], cassette_key(prompt)))
        return result


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
