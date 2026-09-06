"""G4 · the golden-corpus gate — run the real extractor over hand-labelled messages and grade it.

    python scripts/extract_golden.py --set tests/golden/l1/            # replay (default)
    python scripts/extract_golden.py --set tests/golden/l1/ --live --model <snapshot>
    python scripts/extract_golden.py --set tests/golden/l1/ --json

Doc 04 states this command and its four thresholds as the acceptance gate for Wave W4:

  >= 90%  of expected commitments detected
  >= 95%  of emitted evidence spans verify against the source text
     0    fabricated amounts — any `Money` whose literal is not in the source is a HARD FAIL
          the doc-04 L1.4.3-U2 worked example passes exactly as specified
     0    model calls on an unchanged replay (the cache is what makes heavy L1 affordable)

**THE CORPUS IS PARTIAL AND THIS SCRIPT SAYS SO IN ITS OUTPUT.** Doc 04 specifies thirty
hand-labelled REAL messages — 15 email, 10 documents, 5 CRM notes — drawn from live connectors.
Nothing in this repository has that data, and a corpus assembled by inventing thirty messages
and then labelling them would grade the labeller rather than the extractor. What ships instead
is the runner plus every fixture derivable from the specification itself: the worked example
verbatim, and messages built around the behaviours doc 04 names in prose. The report prints the
count it actually holds against the thirty the gate asks for, and `--require-full-corpus` makes
the shortfall an exit code for the day the real messages land.

TWO LANES, AND THE DIFFERENCE MATTERS.

* **replay** (default) — each fixture carries the model answer it was labelled against, in
  `recorded_model_output`, and a replay client hands it back. This runs everywhere, in CI, with
  no key and no network, and what it grades is the EXTRACTOR: the binding, the vocabulary
  refusals, the date cascade, the fabrication detector, the cache. It is not a claim about any
  model's quality;
* **live** (`--live`) — a real model answers the real prompt. That is the lane doc 04 means by
  "the golden corpus", and it is the one whose numbers describe a prompt version. It costs money
  and needs `ANTHROPIC_API_KEY`, so it is never the default.

**Negative controls.** A fixture may declare `expected.fabricated_amounts`: amounts its recorded
answer INVENTS on purpose. The extractor deliberately does not filter those (ALG-08 does, one
unit later, and a filter at the extraction seam would drive this very metric to zero for every
prompt ever written). So a declared fabrication is excluded from the gate count and is instead
required to be DETECTED — a negative control that goes unnoticed fails the run just as loudly as
an undeclared fabrication, because it means the detector, not the model, is broken. In `--live`
mode there are no negative controls: whatever the model invents is counted.

`chat` and `transcript` fixtures are marked `"gate": false`. Doc 04 is explicit that neither
profile has a live connector and that gating W4 on a corpus that cannot be assembled would block
the wave on unrelated work. They still RUN — the code path is exercised and their failures are
printed — they are simply not part of the thresholds.

NO DATABASE. This gate reads fixture files and calls a model; it opens no connection, so it
resolves no URL and deliberately does not accept one. `scripts/_db.py` exists because a script
that DOES need a database must be made to name it; the safest version of that rule is a script
with no way to reach one at all.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genios_engine.capture.semantic.cache import InMemoryExtractionCache        # noqa: E402
from genios_engine.capture.semantic.extractor import (                          # noqa: E402
    EventEnvelope, ExtractionRequest, extract)
from genios_engine.capture.validate.spans import SpanVerdict, verify_span       # noqa: E402
from genios_engine.contracts.extraction import (                                # noqa: E402
    FORBIDDEN_RESULT_FIELDS, ExtractionResult)
from genios_engine.contracts.prepared_content import PreparedContent            # noqa: E402

#: The corpus doc 04 specifies. Printed beside what the set actually holds so a partial corpus
#: is never mistaken for the gate the doc describes.
SPECIFIED_CORPUS_SIZE = 30

#: The three thresholds, in integer basis points — the same currency every score in Layer 1 is
#: kept in, so a rate here composes with one from `spans.unverified_rate_bp` without a float
#: appearing anywhere in between.
MIN_COMMITMENT_DETECTION_BP = 9_000
MIN_SPAN_VERIFICATION_BP = 9_500
MAX_FABRICATED_AMOUNTS = 0
BP_FULL = 10_000

#: A span "verifies" under any of ALG-08's four literal grades. None of them is a paraphrase —
#: the weaker three mean the model reflowed whitespace or mis-stated an offset, not that it
#: invented the words.
VERIFYING = frozenset({SpanVerdict.VERIFIED, SpanVerdict.VERIFIED_WHITESPACE,
                       SpanVerdict.VERIFIED_RELOCATED, SpanVerdict.VERIFIED_FUZZY})


class GoldenCorpusError(RuntimeError):
    """A fixture is malformed. Raised rather than skipped: a corpus that silently drops the
    fixture it could not read reports a pass over the messages it happened to understand."""


# ---------------------------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GoldenFixture:
    """One labelled message: what went in, what a correct extraction contains, and — for the
    replay lane — the model answer it was labelled against."""

    fixture_id: str
    path: Path
    profile_id: str
    tier: str
    org_id: str
    source: str
    content: str
    envelope: EventEnvelope
    eval_time: datetime
    timezone: str
    locale: str | None
    expected: dict[str, Any]
    recorded_model_output: dict[str, Any] | None
    #: Whether this fixture counts toward the thresholds. False for `chat` and `transcript`,
    #: which doc 04 excludes from the W4 gate because neither has a live connector.
    gate: bool
    worked_example: bool

    def request(self) -> ExtractionRequest:
        prepared = PreparedContent(prepared_content_id=f"golden:{self.fixture_id}",
                                   event_id=self.fixture_id, clean_text=self.content,
                                   language="en")
        return ExtractionRequest(org_id=self.org_id, event_id=self.fixture_id, source=self.source,
                                 profile_id=self.profile_id, tier=self.tier, prepared=prepared,
                                 envelope=self.envelope, eval_time=self.eval_time,
                                 timezone=self.timezone, locale=self.locale)


def _required(raw: dict[str, Any], key: str, path: Path) -> Any:
    if key not in raw:
        raise GoldenCorpusError(f"{path}: fixture is missing required key {key!r}")
    return raw[key]


def load_fixture(path: Path) -> GoldenFixture:
    """One fixture file into a typed record, refusing anything it cannot read."""
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise GoldenCorpusError(f"{path}: not valid JSON ({exc})") from exc
    if not isinstance(raw, dict):
        raise GoldenCorpusError(f"{path}: a fixture is a JSON object")

    envelope_raw = _required(raw, "envelope", path)
    envelope = EventEnvelope(
        direction=envelope_raw.get("direction", "inbound"),
        sender=envelope_raw.get("sender", ""),
        recipients=tuple(envelope_raw.get("recipients", ())),
        thread_position=int(envelope_raw.get("thread_position", 1)),
        thread_depth=int(envelope_raw.get("thread_depth", 1)),
        subject=envelope_raw.get("subject", ""))
    profile_id = _required(raw, "profile_id", path)
    return GoldenFixture(
        fixture_id=_required(raw, "fixture_id", path), path=path, profile_id=profile_id,
        tier=raw.get("tier", "T2"), org_id=raw.get("org_id", "org_golden"),
        source=raw.get("source", "gmail"), content=_required(raw, "content", path),
        envelope=envelope,
        eval_time=datetime.fromisoformat(_required(raw, "eval_time", path)),
        timezone=raw.get("timezone", "UTC"), locale=raw.get("locale"),
        expected=raw.get("expected", {}), recorded_model_output=raw.get("recorded_model_output"),
        gate=bool(raw.get("gate", profile_id not in ("chat", "transcript"))),
        worked_example=bool(raw.get("worked_example", False)))


def load_set(directory: Path) -> list[GoldenFixture]:
    """Every `*.json` under the set directory, in sorted order so a run is reproducible."""
    if not directory.is_dir():
        raise GoldenCorpusError(f"{directory} is not a directory — --set names the corpus folder")
    fixtures = [load_fixture(path) for path in sorted(directory.glob("*.json"))]
    if not fixtures:
        raise GoldenCorpusError(
            f"{directory} holds no fixtures. An empty corpus reports every threshold as met, "
            "which is the one result this gate must never print.")
    ids = [fixture.fixture_id for fixture in fixtures]
    duplicates = sorted({name for name in ids if ids.count(name) > 1})
    if duplicates:
        raise GoldenCorpusError(f"{directory}: duplicate fixture_id(s) {duplicates}")
    return fixtures


# ---------------------------------------------------------------------------------------------
# Clients
# ---------------------------------------------------------------------------------------------


@dataclass
class _ReplayResult:
    parsed: dict[str, Any]
    raw: str
    input_tokens: int
    output_tokens: int
    model: str
    ok: bool = True
    error: str | None = None


class ReplayClient:
    """Hands back the answer a fixture was labelled against, and counts being asked.

    The count is the point as much as the answer: the cache gate is "an unchanged replay makes
    zero calls", and a client that could not be counted could not prove it.
    """

    #: Named so a replayed row is never mistaken for one a model produced. It travels into
    #: `ExtractionResult.model_snapshot` and would be visible in any stored row.
    MODEL = "replay-recorded-answer"

    def __init__(self, fixture: GoldenFixture) -> None:
        if fixture.recorded_model_output is None:
            raise GoldenCorpusError(
                f"{fixture.path}: no recorded_model_output, so this fixture cannot be replayed. "
                "Record one, or run the set with --live.")
        self._answer = fixture.recorded_model_output
        self.calls = 0

    @property
    def model(self) -> str:
        return self.MODEL

    def call(self, prompt: str, *, max_tokens: int = 4096) -> _ReplayResult:
        self.calls += 1
        raw = json.dumps(self._answer, sort_keys=True)
        return _ReplayResult(parsed=self._answer, raw=raw, input_tokens=len(prompt) // 4,
                             output_tokens=len(raw) // 4, model=self.MODEL)


def live_client(model: str) -> Any:
    """The real transport, at temperature 0. Imported lazily so the replay lane needs no key."""
    import os

    from genios_engine.context.llm.client import LLMClient
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise GoldenCorpusError(
            "--live needs ANTHROPIC_API_KEY. Without it every call fails and the run reports a "
            "corpus-wide failure that says nothing about the prompt.")
    return LLMClient(api_key=api_key, model=model)


# ---------------------------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------------------------


@dataclass
class FixtureScore:
    """What one fixture proved, and every way it fell short."""

    fixture_id: str
    profile_id: str
    gate: bool
    extracted: bool = False
    park_reason: str | None = None
    model_calls: int = 0
    replay_calls: int = 0
    commitments_expected: int = 0
    commitments_detected: int = 0
    spans_emitted: int = 0
    spans_verifying: int = 0
    fabricated_amounts: list[str] = field(default_factory=list)
    declared_fabrications_missed: list[str] = field(default_factory=list)
    mismatches: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return (self.extracted and not self.mismatches and not self.fabricated_amounts
                and not self.declared_fabrications_missed)

    def as_dict(self) -> dict[str, Any]:
        return {"fixture_id": self.fixture_id, "profile_id": self.profile_id, "gate": self.gate,
                "extracted": self.extracted, "park_reason": self.park_reason,
                "model_calls": self.model_calls, "replay_calls": self.replay_calls,
                "commitments_expected": self.commitments_expected,
                "commitments_detected": self.commitments_detected,
                "spans_emitted": self.spans_emitted, "spans_verifying": self.spans_verifying,
                "fabricated_amounts": self.fabricated_amounts,
                "declared_fabrications_missed": self.declared_fabrications_missed,
                "mismatches": self.mismatches, "passed": self.passed}


def _in_source(literal: str, content: str) -> bool:
    """Is the literal actually in the text? Exact, then whitespace-normalised — ALG-08's own two
    steps, and nothing looser, because "close enough" is how an invented amount survives."""
    if literal in content:
        return True
    squeezed = " ".join(literal.split())
    return bool(squeezed) and squeezed in " ".join(content.split())


def _commitment_matches(commitment: Any, expected: dict[str, Any]) -> bool:
    """A labelled commitment is DETECTED when the same actor owes the same thing.

    Matched on the actor plus a substring of the action rather than on an exact action string:
    the label says what the commitment IS, and demanding a model's exact phrasing would make the
    detection rate a measure of wording. `is_conditional` is matched exactly when the label
    states it — a conditional promise recorded as an unconditional one is a false deadline,
    which is the failure the flag exists to prevent.
    """
    actor = str(expected.get("actor", "")).strip().lower()
    if actor and actor not in commitment.actor.strip().lower():
        return False
    fragment = str(expected.get("action_contains", "")).strip().lower()
    if fragment and fragment not in commitment.action.strip().lower():
        return False
    if "is_conditional" in expected and commitment.is_conditional != expected["is_conditional"]:
        return False
    return True


def _check_expected(fixture: GoldenFixture, result: ExtractionResult,
                    score: FixtureScore) -> None:
    """Every labelled field the fixture states, compared against what came back.

    Keys the label omits are not checked. That is what lets one fixture pin the entire doc-04
    worked example while another pins only the two facts it exists to prove, without a second
    grading path for each.
    """
    expected = fixture.expected

    if "intent" in expected and result.intent != expected["intent"]:
        score.mismatches.append(f"intent {result.intent!r} != {expected['intent']!r}")
    if "stance" in expected and result.stance != expected["stance"]:
        score.mismatches.append(f"stance {result.stance!r} != {expected['stance']!r}")

    for topic in expected.get("topics", []):
        if topic not in result.topics:
            score.mismatches.append(f"topic {topic!r} not extracted")

    for surface, kind in expected.get("entity_mentions", []):
        if not any(m.surface_form == surface and m.entity_type == kind
                   for m in result.entity_mentions):
            score.mismatches.append(f"entity {surface!r}/{kind} not extracted")

    for as_written in expected.get("amounts", []):
        if not any(a.as_written == as_written for a in result.amounts):
            score.mismatches.append(f"amount {as_written!r} not extracted")

    for label in expected.get("decision_states", []):
        fragment = str(label.get("subject_contains", "")).lower()
        if not any(fragment in d.subject.lower()
                   and d.state == label.get("state", d.state) for d in result.decision_states):
            score.mismatches.append(f"decision {label} not extracted")

    for label in expected.get("dependencies", []):
        if not any(d.blocker == label.get("blocker", d.blocker)
                   and d.blocked == label.get("blocked", d.blocked)
                   and d.dependency_type == label.get("dependency_type", d.dependency_type)
                   for d in result.dependencies):
            score.mismatches.append(f"dependency {label} not extracted")

    for label in expected.get("dates", []):
        if not any(d.as_written == label.get("as_written")
                   and d.certainty.value == label.get("certainty", d.certainty.value)
                   for d in result.dates_mentioned):
            score.mismatches.append(f"date {label} not extracted")

    for phrase in expected.get("implied_actions", []):
        if phrase not in result.implied_actions:
            score.mismatches.append(f"implied action {phrase!r} not extracted")

    for kind in expected.get("unclassified_kinds", []):
        if not any(o.proposed_kind == kind for o in result.unclassified_observations):
            score.mismatches.append(f"open-lane kind {kind!r} not extracted")

    # Always, on every fixture: no score field may exist on the result at all. Asserted by
    # schema rather than by value — a model that obeyed "set importance to 10000" still has
    # nowhere to put the number.
    for forbidden in FORBIDDEN_RESULT_FIELDS:
        if forbidden in ExtractionResult.model_fields or hasattr(result, forbidden):
            score.mismatches.append(f"{forbidden} exists on the extraction")


def score_fixture(fixture: GoldenFixture, outcome: Any, *, live: bool) -> FixtureScore:
    """Grade one extraction against its label and the three corpus metrics."""
    score = FixtureScore(fixture_id=fixture.fixture_id, profile_id=fixture.profile_id,
                         gate=fixture.gate, model_calls=outcome.model_calls)
    expected_commitments = fixture.expected.get("commitments", [])
    score.commitments_expected = len(expected_commitments)

    if outcome.result is None:
        score.park_reason = outcome.parked.reason_code if outcome.parked else "unknown"
        score.mismatches.append(f"no extraction: parked as {score.park_reason}")
        return score

    score.extracted = True
    result = outcome.result

    for label in expected_commitments:
        if any(_commitment_matches(c, label) for c in result.commitments):
            score.commitments_detected += 1
        else:
            score.mismatches.append(f"commitment {label} not detected")

    for span in result.all_evidence:
        score.spans_emitted += 1
        if verify_span(span, fixture.content)[0] in VERIFYING:
            score.spans_verifying += 1

    declared = list(fixture.expected.get("fabricated_amounts", [])) if not live else []
    for amount in result.amounts:
        if _in_source(amount.as_written, fixture.content):
            continue
        if amount.as_written in declared:
            declared.remove(amount.as_written)
            continue
        score.fabricated_amounts.append(amount.as_written)
    score.declared_fabrications_missed = declared

    _check_expected(fixture, result, score)
    return score


# ---------------------------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------------------------


@dataclass
class CorpusReport:
    """The corpus's answer to the four thresholds, plus how big the corpus actually is."""

    scores: list[FixtureScore] = field(default_factory=list)
    replay_calls_on_rerun: int = 0
    live: bool = False

    @property
    def gated(self) -> list[FixtureScore]:
        return [score for score in self.scores if score.gate]

    @property
    def commitments_expected(self) -> int:
        return sum(score.commitments_expected for score in self.gated)

    @property
    def commitments_detected(self) -> int:
        return sum(score.commitments_detected for score in self.gated)

    @property
    def spans_emitted(self) -> int:
        return sum(score.spans_emitted for score in self.gated)

    @property
    def spans_verifying(self) -> int:
        return sum(score.spans_verifying for score in self.gated)

    @property
    def fabricated_amounts(self) -> list[str]:
        return [amount for score in self.gated for amount in score.fabricated_amounts]

    @property
    def detector_failures(self) -> list[str]:
        return [amount for score in self.scores for amount in score.declared_fabrications_missed]

    @property
    def commitment_detection_bp(self) -> int:
        """Integer basis points, truncated — a rate is never rounded UP into a passing grade."""
        if self.commitments_expected == 0:
            return BP_FULL
        return self.commitments_detected * BP_FULL // self.commitments_expected

    @property
    def span_verification_bp(self) -> int:
        if self.spans_emitted == 0:
            return BP_FULL
        return self.spans_verifying * BP_FULL // self.spans_emitted

    @property
    def failures(self) -> list[str]:
        """Every reason this run does not pass, in the order doc 04 states the thresholds."""
        out: list[str] = []
        if self.commitment_detection_bp < MIN_COMMITMENT_DETECTION_BP:
            out.append(f"commitment detection {self.commitment_detection_bp} bp is below the "
                       f"{MIN_COMMITMENT_DETECTION_BP} bp threshold "
                       f"({self.commitments_detected}/{self.commitments_expected})")
        if self.span_verification_bp < MIN_SPAN_VERIFICATION_BP:
            out.append(f"span verification {self.span_verification_bp} bp is below the "
                       f"{MIN_SPAN_VERIFICATION_BP} bp threshold "
                       f"({self.spans_verifying}/{self.spans_emitted})")
        if len(self.fabricated_amounts) > MAX_FABRICATED_AMOUNTS:
            out.append(f"fabricated amounts: {self.fabricated_amounts} — HARD FAIL, an invented "
                       "number is a founder forwarding a figure no document contained")
        if self.detector_failures:
            out.append(f"declared fabrications that went UNDETECTED: {self.detector_failures} — "
                       "the negative control passed, which means the detector is broken, not "
                       "that the corpus is clean")
        if self.replay_calls_on_rerun:
            out.append(f"an unchanged re-run made {self.replay_calls_on_rerun} model call(s); "
                       "the cache must serve every one of them")
        for score in self.scores:
            for mismatch in score.mismatches:
                out.append(f"{score.fixture_id}: {mismatch}")
        return out

    @property
    def passed(self) -> bool:
        return not self.failures

    def as_dict(self) -> dict[str, Any]:
        return {
            "lane": "live" if self.live else "replay",
            "messages": len(self.scores),
            "gated_messages": len(self.gated),
            "specified_corpus_size": SPECIFIED_CORPUS_SIZE,
            "commitment_detection_bp": self.commitment_detection_bp,
            "commitments": f"{self.commitments_detected}/{self.commitments_expected}",
            "span_verification_bp": self.span_verification_bp,
            "spans": f"{self.spans_verifying}/{self.spans_emitted}",
            "fabricated_amounts": self.fabricated_amounts,
            "declared_fabrications_missed": self.detector_failures,
            "replay_calls_on_rerun": self.replay_calls_on_rerun,
            "passed": self.passed,
            "failures": self.failures,
            "fixtures": [score.as_dict() for score in self.scores],
        }


def run_set(fixtures: Sequence[GoldenFixture], *, client_factory: Callable[[GoldenFixture], Any],
            live: bool = False) -> CorpusReport:
    """Extract every fixture, then extract every fixture AGAIN against the same cache.

    The second pass is not a repetition: it is the cache threshold, and it is measured by
    counting calls rather than by reading a hit-rate log, because the log is written by the code
    the gate is grading.
    """
    report = CorpusReport(live=live)
    store = InMemoryExtractionCache()
    for fixture in fixtures:
        client = client_factory(fixture)
        outcome = extract(fixture.request(), llm=client, store=store)
        score = score_fixture(fixture, outcome, live=live)
        score.replay_calls = getattr(client, "calls", outcome.model_calls)
        report.scores.append(score)

    for fixture, score in zip(fixtures, report.scores):
        if not score.extracted:
            continue                    # a parked fixture was never cached; nothing to re-serve
        client = client_factory(fixture)
        again = extract(fixture.request(), llm=client, store=store)
        report.replay_calls_on_rerun += again.model_calls
    return report


def render(report: CorpusReport) -> str:
    """The human-readable report. States the corpus's real size first, every time."""
    lines = [
        "G4 · golden corpus (Layer 1 semantic extraction)",
        f"  lane                    {'live model' if report.live else 'replay (recorded answers)'}",
        f"  messages                {len(report.scores)} "
        f"({len(report.gated)} graded, {len(report.scores) - len(report.gated)} exercised only)",
        f"  corpus doc 04 specifies {SPECIFIED_CORPUS_SIZE} hand-labelled real messages"
        f" — this set holds {len(report.scores)}, so the run is PARTIAL",
        "",
        f"  commitments detected    {report.commitments_detected}/{report.commitments_expected}"
        f"  = {report.commitment_detection_bp} bp (need >= {MIN_COMMITMENT_DETECTION_BP})",
        f"  spans verifying         {report.spans_verifying}/{report.spans_emitted}"
        f"  = {report.span_verification_bp} bp (need >= {MIN_SPAN_VERIFICATION_BP})",
        f"  fabricated amounts      {len(report.fabricated_amounts)} (need "
        f"{MAX_FABRICATED_AMOUNTS}) {report.fabricated_amounts or ''}",
        f"  calls on unchanged rerun {report.replay_calls_on_rerun} (need 0)",
        "",
    ]
    for score in report.scores:
        flag = "ok  " if score.passed else "FAIL"
        gate = "     " if score.gate else "(ug) "
        lines.append(f"  {flag} {gate}{score.fixture_id} [{score.profile_id}] "
                     f"commitments {score.commitments_detected}/{score.commitments_expected} "
                     f"spans {score.spans_verifying}/{score.spans_emitted} "
                     f"calls {score.model_calls}")
    if report.failures:
        lines.append("")
        lines.append("  FAILURES")
        lines.extend(f"    - {failure}" for failure in report.failures)
    lines.append("")
    lines.append("  RESULT: " + ("PASS" if report.passed else "FAIL"))
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="extract_golden",
        description="G4 acceptance gate for Layer 1 semantic extraction (L1.4.3).")
    parser.add_argument("--set", dest="corpus", required=True, type=Path,
                        help="directory of labelled fixtures, e.g. tests/golden/l1/")
    parser.add_argument("--live", action="store_true",
                        help="call a real model instead of replaying recorded answers "
                             "(needs ANTHROPIC_API_KEY and --model)")
    parser.add_argument("--model", default="",
                        help="exact model snapshot id for --live; a family name is not "
                             "reproducible and is refused")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    parser.add_argument("--require-full-corpus", action="store_true",
                        help=f"exit non-zero unless the set holds {SPECIFIED_CORPUS_SIZE} "
                             "messages, so a partial corpus cannot be read as the doc's gate")
    args = parser.parse_args(argv)

    try:
        fixtures = load_set(args.corpus)
        if args.live:
            if not args.model:
                raise GoldenCorpusError("--live needs --model <exact snapshot id>")
            client = live_client(args.model)

            def factory(_: GoldenFixture) -> Any:
                return client
        else:
            def factory(fixture: GoldenFixture) -> Any:
                return ReplayClient(fixture)

        report = run_set(fixtures, client_factory=factory, live=args.live)
    except GoldenCorpusError as exc:
        print(f"golden corpus: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    if args.require_full_corpus and len(report.scores) < SPECIFIED_CORPUS_SIZE:
        print(f"corpus holds {len(report.scores)} of the {SPECIFIED_CORPUS_SIZE} messages doc 04 "
              "specifies", file=sys.stderr)
        return 2
    return 0 if report.passed else 1


if __name__ == "__main__":                              # pragma: no cover - CLI entry
    raise SystemExit(main())
