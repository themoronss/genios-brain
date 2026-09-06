"""G9 · INDEPENDENT gate probes — written to disagree with the units they check.

    pytest tests/capture/test_g9_gate_probes.py -q

WHY A SECOND FILE. `tests/capture/{connectors,acquire,coverage}` and `test_webhook_parity.py`
are the suites the wave's own authors wrote. A gate that is only ever checked by the code that
claims to pass it is a gate that measures its author's intent. These probes were written from
G9's four stated criteria and the six defect statements ALONE, re-deriving each expected value
by a different route than the unit does — a subprocess for cross-process jitter, a naive
per-character origin table for offsets, a real `run_sync` sweep for coverage — so that a unit
which quietly stopped doing its job fails here even if its own suite still agrees with it.

EVERY PROBE IS PAIRED WITH ITS OWN NEUTRALISATION. A probe that passes proves nothing until it
is shown to fail when the fix is taken away, so each block breaks the fix IN MEMORY — a
monkeypatched digest, a `coverage_fn` of None, a lane whose store is missing — and asserts the
probe notices. A probe that still passes with the fix removed is a probe that was measuring
nothing, and the assertion pairs are what stop this file from becoming that.

NOTHING HERE TOUCHES A NETWORK OR A CLOCK: connectors are fed canned pages, `eval_time` is a
parameter, and the subprocess the jitter probe spawns runs this repository's own module under a
different `PYTHONHASHSEED`.
"""

from __future__ import annotations

import ast
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from genios_engine.capture.acquire.jitter import (DEFAULT_SPREAD_BP, JitterKey, jitter_offset)
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.backfill import (BackfillWindow, DEFAULT_BACKFILL_DAYS,
                                                       backfill_window_for, with_backfill_days)
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.connectors.dispatch import webhook_to_raw
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.pipeline import capture_event
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.preprocess import pii
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.capture.semantic import batch as batch_mod
from genios_engine.capture.semantic import extractor as ex
from genios_engine.capture.semantic import sink_guard as guard_mod
from genios_engine.capture.semantic.cache import InMemoryExtractionCache
from genios_engine.capture.semantic.evidence_binder import ModelSpan, align_span
from genios_engine.capture.semantic.open_lane import InMemoryOpenLaneStore
from genios_engine.capture.semantic.sink_guard import guard_typed_sink, sift_untyped_lanes
from genios_engine.capture.semantic.vocabulary import UNTYPED_LANE_KEYS, UNTYPED_LANES
from genios_engine.capture.validate.spans import SpanVerdict, verify_span
from genios_engine.contracts.connection import Connection
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.source_event import SyncMode

WAVE = "W9"
GATE = "G9"

REPO_ROOT = Path(__file__).resolve().parents[2]
ENGINE_ROOT = REPO_ROOT / "genios_engine"

#: Verdicts that mean "these words are literally in that text" — ALG-08 has no similarity step.
_GROUNDED = (SpanVerdict.VERIFIED, SpanVerdict.VERIFIED_WHITESPACE,
             SpanVerdict.VERIFIED_RELOCATED, SpanVerdict.VERIFIED_FUZZY)


# =============================================================================================
# G9 criterion 1 · webhook and poll produce IDENTICAL rows for the same message
# =============================================================================================


#: One gmail message, in the raw shape BOTH doors are handed. The poll door receives it inside
#: a Composio list page; the webhook door receives it inside a trigger envelope.
MESSAGE = {
    "id": "msg_g9_parity",
    "threadId": "thread_g9",
    "internalDate": "1756900000000",
    "labelIds": ["INBOX"],
    "payload": {
        "headers": [{"name": "From", "value": '"Priya Rao" <priya@acme.example>'},
                    {"name": "To", "value": "founder@acme.example"},
                    {"name": "Subject", "value": "Revised contract"}],
        "parts": [{"mimeType": "text/plain", "filename": "", "body": {"data": base64.urlsafe_b64encode(
            b"Budget approved. Send the revised contract by Friday.").decode()}}],
    },
}


def _gmail_parser():
    """The real connector with its transport removed — a full-fetch would be a network call."""
    from genios_engine.capture.connectors.composio import ComposioGmailConnector
    connector = ComposioGmailConnector(api_key="", user_id="")
    connector._execute = lambda slug, args: {}
    return connector


class _PollDoor:
    """A sweepable connector that parses `page` with the REAL gmail parser."""

    source = "gmail"

    def __init__(self, page: dict) -> None:
        self._page = page

    def _batch(self) -> SourceBatch:
        return _gmail_parser()._to_batch(self._page)

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return self._batch()

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return self._batch()

    def fetch_content(self, object_ref: str) -> dict:
        return {}


#: Per-ROW, or deliberately caller-chosen — everything else, `dedup_key` above all, is compared.
_PATH_SPECIFIC = {"event_id", "captured_at"}


def _rows(repo: InMemorySourceEventRepository) -> list[dict]:
    """The LANDED rows, comparable: sorted, with the two per-row fields removed."""
    return sorted(({k: v for k, v in event.model_dump().items() if k not in _PATH_SPECIFIC}
                   for event in repo._by_key.values()),
                  key=lambda row: row["dedup_key"])


def _capture_kwargs() -> dict:
    return dict(org_id="org_g9_parity", connection_id="con_g9_parity",
                mailbox_owner="founder@acme.example",
                coverage_fn=lambda domain: {"coverage_ready": True})


def test_probe_webhook_and_poll_land_identical_rows_for_one_message():
    """G9-1, measured on the ROWS rather than on the parsed objects.

    The criterion says *rows*, and a row is what a duplicate lands as. So both doors are driven
    all the way through the pipeline into a repository and the persisted `SourceEvent`s are
    compared — which additionally exercises the gate, the normalizer and the dedup key, none of
    which an equality over two `RawObject`s would touch.
    """
    poll_repo = InMemorySourceEventRepository()
    run_sync(_PollDoor({"data": {"messages": [MESSAGE]}}), repo=poll_repo, mode="incremental",
             source="gmail", **_capture_kwargs())

    hook_repo = InMemorySourceEventRepository()
    pushed = webhook_to_raw("gmail", {"message": MESSAGE},
                            connector_factory=_gmail_parser)
    assert pushed is not None, "the webhook door dropped a message the poll door landed"
    capture_event(pushed, repo=hook_repo, **_capture_kwargs())

    assert _rows(poll_repo) == _rows(hook_repo)
    assert _rows(poll_repo)[0]["dedup_key"].startswith("gmail:email_message:msg_g9_parity")


def test_probe_a_message_that_arrived_through_BOTH_doors_lands_once():
    """The consequence the criterion exists for. Two doors that disagree on `dedup_key` double
    every message on every recovery sync — so the same repository is shown both doors."""
    repo = InMemorySourceEventRepository()
    swept = run_sync(_PollDoor({"data": {"messages": [MESSAGE]}}), repo=repo,
                     mode="incremental", source="gmail", **_capture_kwargs())
    assert swept.emitted == 1

    pushed = webhook_to_raw("gmail", {"message": MESSAGE}, connector_factory=_gmail_parser)
    result = capture_event(pushed, repo=repo, **_capture_kwargs())
    assert result.outcome == "duplicate", result.outcome
    assert repo.count() == 1


def test_probe_the_row_comparison_is_sensitive_to_a_real_divergence():
    """NEUTRALISATION. An equality between two rows built by one helper would pass whatever the
    parsers did. Change the message the webhook door is handed and the comparison must break —
    and a source with no parser at all must still be reported as the dropped lane it is."""
    changed = json.loads(json.dumps(MESSAGE))
    changed["payload"]["headers"][2] = {"name": "Subject", "value": "Something else entirely"}
    changed["id"] = "msg_g9_other"

    poll_repo = InMemorySourceEventRepository()
    run_sync(_PollDoor({"data": {"messages": [MESSAGE]}}), repo=poll_repo, mode="incremental",
             source="gmail", **_capture_kwargs())
    hook_repo = InMemorySourceEventRepository()
    capture_event(webhook_to_raw("gmail", {"message": changed}, connector_factory=_gmail_parser),
                  repo=hook_repo, **_capture_kwargs())
    assert _rows(poll_repo) != _rows(hook_repo), (
        "the comparison cannot tell two different messages apart, so its agreement above was "
        "vacuous")

    assert webhook_to_raw("a_source_with_no_parser", {"message": MESSAGE}) is None


# =============================================================================================
# G9 criterion 2 · EVERY swept event carries a non-null coverage_ready
# =============================================================================================


class _TwoMessageConnector:
    """A connector that hands the sweep two distinct emails and one page. No network."""

    source = "gmail"

    def __init__(self, ids: tuple[str, ...] = ("m_g9_a", "m_g9_b")) -> None:
        self.ids = ids

    def _objects(self) -> list[RawObject]:
        return [RawObject(source="gmail", object_type="email_message", source_object_id=i,
                          occurred_at=datetime(2026, 7, 28, 9, 14, tzinfo=timezone.utc),
                          actor_email="priya@acme.example", actor_type="external_contact",
                          raw={"subject": "Revised contract",
                               "body": "Budget approved. Please send the contract by Friday."})
                for i in self.ids]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def fetch_content(self, object_ref: str) -> dict:
        return {"body": "Budget approved. Please send the contract by Friday."}


def _sweep(coverage_fn) -> list[Any]:
    """One real `run_sync` over two emails; the gated events it emitted."""
    summary = run_sync(_TwoMessageConnector(), org_id="org_g9_cov", connection_id="con_g9_cov",
                       repo=InMemorySourceEventRepository(), mode="incremental",
                       source="gmail", coverage_fn=coverage_fn)
    return list(summary.gated)


def test_probe_every_swept_event_carries_a_non_null_coverage_ready():
    """G9-2, measured on a real sweep rather than on a single `capture_event` call.

    The recorded defect is a POPULATION statement — `coverage_ready` was None on 100% of events
    ever produced — so the probe is a population too: every event the sweep emitted, not one.
    """
    gated = _sweep(lambda domain: {"coverage_ready": True})
    assert len(gated) == 2, gated
    assert all(event.coverage_ready is not None for event in gated), \
        [(e.event_id, e.coverage_ready) for e in gated]
    assert all(event.coverage_ready is True for event in gated)


def test_probe_a_sweep_that_declares_nothing_still_produces_the_old_null_population():
    """NEUTRALISATION. Take the declaration away — the exact pre-fix call — and the whole
    population goes back to None. This is what proves the probe reads the wiring and not some
    default that would have been True either way."""
    gated = _sweep(None)
    assert len(gated) == 2, gated
    assert all(event.coverage_ready is None for event in gated)


def test_probe_a_false_verdict_is_carried_as_false_not_collapsed_to_none():
    """"Under-connected" and "unclassified" are different states. A probe that only checked
    `is not None` would pass on a wiring that hard-coded True, so the third value is asserted
    too."""
    gated = _sweep(lambda domain: {"coverage_ready": False})
    assert all(event.coverage_ready is False for event in gated)


def test_probe_no_capture_entry_in_the_engine_omits_the_declaration():
    """The population argument, as a property of the source tree.

    A sweep that declares coverage everywhere today is one forgotten keyword away from the
    100%-None population again, and the forgetting is silent: `coverage_fn` defaults to None on
    every entry point. So every `run_sync`/`capture_event`/`ingest_manual` call inside
    `genios_engine/` is read with `ast` and required to name the keyword.
    """
    entries = {"run_sync", "capture_event", "ingest_manual", "ingest_internal_knowledge"}
    offenders: list[str] = []
    for py in ENGINE_ROOT.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in entries):
                continue
            names = {kw.arg for kw in node.keywords}
            if "coverage_fn" in names or None in names:      # `**kw` forwards it
                continue
            offenders.append(f"{py.relative_to(REPO_ROOT)}:{node.lineno} {node.func.id}")
    assert not offenders, ("these capture entries do not declare coverage, so every event they "
                           f"produce carries coverage_ready=None: {offenders}")


# =============================================================================================
# G9 criterion 3 · the backfill window is per-connection, and widening it does not duplicate
# =============================================================================================


def _connection(days: int | None) -> Connection:
    config = {} if days is None else {"backfill_days": days}
    return Connection(org_id="org_g9_bf", composio_user_id="org_g9_bf",
                      source_type="gmail", config=config)


@pytest.mark.parametrize("days,expected,why", [
    (None, DEFAULT_BACKFILL_DAYS, "an unset connection gets the wide default, not the old 60"),
    (60, 60, "a connection stamped with the legacy value keeps it until an admin raises it"),
    (900, 900, "an admin's own number is honoured, not clamped to a module constant"),
])
def test_probe_the_window_is_read_off_the_connection_not_a_module_constant(days, expected, why):
    """G9-3a. Two connections, two windows, in one process — the property a constant cannot have."""
    assert backfill_window_for(_connection(days)).days == expected, why


def test_probe_two_connections_in_one_process_hold_different_windows():
    """The defect was a MODULE constant: every tenant, forever, the same two months. The probe
    that a constant cannot survive is two connections disagreeing at the same instant."""
    narrow, wide = _connection(60), _connection(900)
    assert backfill_window_for(narrow).days != backfill_window_for(wide).days
    assert backfill_window_for(narrow).gmail_query() == "newer_than:60d"
    assert backfill_window_for(wide).gmail_query() == "newer_than:900d"


def test_probe_widening_the_window_re_lands_nothing_because_the_dedup_key_holds():
    """G9-3b. Widen the window, re-sweep, and the ledger must absorb every message it already saw.

    The dedup key is (org, source, source_object_id) shaped — NOT a function of the window — so a
    wider second pass that re-reads the first pass's messages plus older ones must land only the
    older ones. That is the whole safety property behind letting an operator raise the window on
    a live tenant.
    """
    repo = InMemorySourceEventRepository()
    narrow = run_sync(_TwoMessageConnector(("m_old_1", "m_old_2")), org_id="org_g9_bf",
                      connection_id="con_g9_bf", repo=repo, mode="backfill", source="gmail",
                      coverage_fn=lambda d: {"coverage_ready": True})
    assert narrow.emitted == 2 and narrow.duplicate == 0
    landed_after_narrow = repo.count()

    # The wider window re-reads both of those AND reaches one further back.
    wider = run_sync(_TwoMessageConnector(("m_old_1", "m_old_2", "m_older_3")),
                     org_id="org_g9_bf", connection_id="con_g9_bf", repo=repo, mode="backfill",
                     source="gmail", coverage_fn=lambda d: {"coverage_ready": True})
    assert wider.duplicate == 2, "the two already-seen messages must be refused as duplicates"
    assert wider.emitted == 1, "only the message the wider window newly reached may land"
    assert repo.count() == landed_after_narrow + 1


def test_probe_the_duplicate_check_is_sensitive_to_a_genuinely_new_message():
    """NEUTRALISATION for the row above: a sweep of three NEW ids must land three. Without this
    the duplicate count could be produced by a repo that refuses everything."""
    repo = InMemorySourceEventRepository()
    summary = run_sync(_TwoMessageConnector(("n1", "n2", "n3")), org_id="org_g9_bf",
                       connection_id="con_g9_bf", repo=repo, mode="backfill", source="gmail",
                       coverage_fn=lambda d: {"coverage_ready": True})
    assert (summary.emitted, summary.duplicate) == (3, 0)


@pytest.mark.parametrize("days", [0, -1, 3651])
def test_probe_an_unhonourable_window_is_refused_at_the_edit_not_at_the_next_sync(days):
    """A window of zero syncs nothing while reporting success. It must fail where the admin typed
    it, not silently at 3am."""
    with pytest.raises(ValueError):
        with_backfill_days(_connection(None), days)


# =============================================================================================
# G9 criterion 4 · jitter is deterministic ACROSS PROCESSES and spreads across keys
# =============================================================================================


_JITTER_SNIPPET = (
    "import json,sys;"
    "sys.path.insert(0, %r);"
    "from genios_engine.capture.acquire.jitter import JitterKey, jitter_offset;"
    "print(json.dumps([jitter_offset(JitterKey('org_%%d' %% i, 'con_%%d' %% i, 'gmail'),"
    " interval_seconds=900).offset_seconds for i in range(40)]))"
)


def _offsets_in_a_fresh_process(hash_seed: str) -> list[int]:
    """The same 40 offsets, computed by a DIFFERENT interpreter under a chosen PYTHONHASHSEED."""
    env = dict(os.environ, PYTHONHASHSEED=hash_seed)
    out = subprocess.run([sys.executable, "-c", _JITTER_SNIPPET % str(REPO_ROOT)],
                         capture_output=True, text=True, env=env, cwd=str(REPO_ROOT), timeout=120)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def _offsets_here() -> list[int]:
    return [jitter_offset(JitterKey(f"org_{i}", f"con_{i}", "gmail"),
                          interval_seconds=900).offset_seconds for i in range(40)]


@pytest.mark.slow
def test_probe_offsets_are_byte_identical_in_two_other_interpreters():
    """G9-4a. "Deterministic across processes" is not a property `random.seed` or `hash()` has,
    and it cannot be probed inside one interpreter — so two child interpreters with deliberately
    different `PYTHONHASHSEED` values recompute the same 40 offsets."""
    mine = _offsets_here()
    assert _offsets_in_a_fresh_process("0") == mine
    assert _offsets_in_a_fresh_process("12345") == mine


def test_probe_a_process_salted_digest_would_not_survive_that_check(monkeypatch):
    """NEUTRALISATION. `hash()` is the function the module says it must not use; under two
    PYTHONHASHSEEDs it gives two answers, so the cross-process probe above is measuring the
    stability of blake2b rather than restating that a pure function is pure."""
    seeds = ("0", "12345")
    snippet = ("import json,sys;sys.path.insert(0, %r);"
               "print(json.dumps([hash('org_%%d|con_%%d|gmail' %% (i, i)) for i in range(40)]))"
               % str(REPO_ROOT))
    runs = []
    for seed in seeds:
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run([sys.executable, "-c", snippet], capture_output=True, text=True,
                             env=env, cwd=str(REPO_ROOT), timeout=120)
        assert out.returncode == 0, out.stderr
        runs.append(json.loads(out.stdout))
    assert runs[0] != runs[1], (
        "PYTHONHASHSEED did not change hash() in this build, so the cross-process probe proves "
        "less than it claims — check the child processes really got the env var")


def test_probe_the_offsets_actually_spread_rather_than_stacking():
    """G9-4b. Determinism alone is satisfied by "every connection gets offset 0", which is the
    herd the unit exists to break. So the spread is measured: many distinct offsets, both signs,
    and no single second holding a large share of a 400-connection tenant fleet."""
    offsets = [jitter_offset(JitterKey(f"org_{i}", f"con_{i}", "gmail"),
                             interval_seconds=900).offset_seconds for i in range(400)]
    distinct = set(offsets)
    assert len(distinct) > 100, f"only {len(distinct)} distinct offsets across 400 keys"
    assert min(offsets) < 0 < max(offsets), "the spread must be signed, not one-sided"
    busiest = max(offsets.count(o) for o in distinct)
    assert busiest < 40, f"{busiest}/400 connections land on one second — still a herd"
    bound = 900 * DEFAULT_SPREAD_BP // 10_000
    assert all(abs(o) <= bound for o in offsets)


def test_probe_the_source_participates_in_the_key_so_two_lanes_do_not_collide():
    """One Composio connection backs gmail and gcal; if both derived the same offset the two
    heaviest calls of that tenant would land on the same second — a herd of two."""
    base = dict(org_id="org_g9_j", connection_id="con_g9_j")
    gmail = jitter_offset(JitterKey(**base, source="gmail"), interval_seconds=900)
    gcal = jitter_offset(JitterKey(**base, source="gcal"), interval_seconds=900)
    assert gmail.fraction_bp != gcal.fraction_bp


# =============================================================================================
# D1 · model offsets -> binder alignment -> spans.py resolves the quote in the ORIGINAL text
#
# The chain has three coordinate systems and the defect class is confusing two of them. The
# probe therefore never trusts an offset it did not re-derive: the ORACLE below is a naive
# per-character origin table built by expanding the segment map, which is obviously correct and
# obviously not how `align_span` works. The two agreeing is evidence; one of them alone is not.
# =============================================================================================

#: Literals `capture/preprocess/pii.py`'s real detectors match. Real ones keep the whole chain
#: under test — a hand-planted "[MASK]" would prove this file's own arithmetic.
PAN = "ABCDE1234F"
IFSC = "HDFC0001234"


def _origins(prepared) -> list[tuple[int, int]]:
    """One entry per PREPARED character: the source region that character stands for.

    A masked segment's characters all stand for the WHOLE masked region — atomicity as data.
    """
    out: list[tuple[int, int]] = []
    for seg in prepared.offset_map:
        width = seg.prep_end - seg.prep_start
        if seg.masked:
            out.extend([(seg.src_start, seg.src_end)] * width)
        else:
            out.extend((seg.src_start + i, seg.src_start + i + 1) for i in range(width))
    return out


def _align_and_resolve(original: str, quote: str, *, source_ref="prepared_content:evt_g9_d1"):
    """The whole D1 chain for one quote, plus the oracle's answer for the same region."""
    prepared = preprocess(original, event_id="evt_g9_d1")
    view_start = prepared.clean_text.index(quote)
    aligned = align_span(ModelSpan(quote=quote, view_start=view_start,
                                   view_end=view_start + len(quote)),
                         prepared, source_ref=source_ref)
    assert aligned is not None, f"the binder refused a quote it was shown: {quote!r}"
    origins = _origins(prepared)
    oracle_start = origins[view_start][0]
    oracle_end = origins[view_start + len(quote) - 1][1]
    return prepared, aligned, (oracle_start, oracle_end)


@pytest.mark.parametrize("original,quote,why", [
    ("Send the invoice to Priya by Friday and copy Rohit.",
     "Send the invoice", "no mask at all — prepared and source are the same string"),
    (f"{PAN} is the PAN. Send the invoice to Priya by Friday.",
     "Send the invoice", "the mask is at OFFSET 0, so every later offset is shifted"),
    ("Line one is here.\r\nSend the invoice to Priya by Friday.\r\nLine three.",
     "Send the invoice", "CRLF — a \\r that a naive line-based map would eat"),
    ("Payment 💸 confirmed 𝔘nicode beyond the BMP. Send the invoice to Priya.",
     "Send the invoice", "astral characters — surrogate-pair counting would shift the offsets"),
    ("Invoice 💸 for Priya. Send the invoice to Priya by Friday.",
     "by Friday", "the quote sits AFTER an astral character"),
    (f"Refs {PAN} {IFSC} follow. Send the invoice to Priya by Friday.",
     "Send the invoice", "two ADJACENT masks (one space apart) before the quote"),
])
def test_probe_an_aligned_quote_resolves_in_the_original_text(original, quote, why):
    """D1. `verify_span` is run against the ORIGINAL — the string with the PII still in it — at
    the offsets the binder produced. That is the only claim that matters: a receipt a human can
    open. The oracle checks the arithmetic independently, and the verdict checks the result."""
    prepared, aligned, oracle = _align_and_resolve(original, quote)

    assert not aligned.crosses_mask, why
    assert (aligned.source_start, aligned.source_end) == oracle, why
    assert original[aligned.source_start:aligned.source_end] == quote, why

    verdict, corrected = verify_span(
        EvidenceSpan(source_ref="prepared_content:evt_g9_d1", quote=quote,
                     start_offset=aligned.source_start, end_offset=aligned.source_end,
                     verified=False),
        original)
    assert verdict is SpanVerdict.VERIFIED, (verdict, why)
    assert corrected.verified is True and corrected.quote == quote


def _mask_token(prepared) -> tuple[int, int]:
    """The (start, end) of the FIRST masked segment in the prepared text."""
    for segment in prepared.offset_map:
        if segment.masked:
            return segment.prep_start, segment.prep_end
    raise AssertionError("nothing was masked, so there is no mask to probe")


def test_probe_a_quote_strictly_inside_a_mask_expands_to_the_whole_token():
    """A mask is atomic: there is no source character at "the third character of [PAN]". A quote
    that lies strictly INSIDE the token must resolve to the whole original PII, and must say that
    it expanded — a caller comparing `len(quote)` to the region width would otherwise read a
    correct expansion as an off-by-N and "correct" it into the wrong sentence."""
    original = f"The PAN is {PAN} and the invoice follows."
    prepared = preprocess(original, event_id="evt_g9_d1")
    token_start, token_end = _mask_token(prepared)
    quote = prepared.clean_text[token_start + 1:token_end - 1]        # "PAN", inside "[PAN]"
    assert quote and quote.strip()

    aligned = align_span(ModelSpan(quote=quote, view_start=token_start + 1,
                                   view_end=token_end - 1),
                         prepared, source_ref="prepared_content:evt_g9_d1")
    assert aligned is not None
    assert aligned.crosses_mask is True
    assert original[aligned.source_start:aligned.source_end] == PAN
    assert aligned.source_end - aligned.source_start != len(quote), (
        "the region did not expand, so a mask was treated as if it had an interior")


def test_probe_a_quote_crossing_a_mask_boundary_covers_the_whole_pii_plus_the_words():
    """The mixed case: real words on one side, a mask on the other."""
    original = f"The PAN is {PAN} and the invoice follows."
    prepared = preprocess(original, event_id="evt_g9_d1")
    start = prepared.clean_text.index("is ")
    end = prepared.clean_text.index("]") + 1
    quote = prepared.clean_text[start:end]

    aligned = align_span(ModelSpan(quote=quote, view_start=start, view_end=end), prepared,
                         source_ref="prepared_content:evt_g9_d1")
    assert aligned is not None and aligned.crosses_mask is True
    region = original[aligned.source_start:aligned.source_end]
    assert region == f"is {PAN}", region


def test_probe_the_alignment_is_sensitive_to_a_broken_source_end(monkeypatch):
    """NEUTRALISATION 1. `_source_end` exists because `to_source_offset` cannot answer for an
    EXCLUSIVE end: it locates the segment CONTAINING an offset, and an end sits one past the
    last character it covers, so at a segment boundary it resolves into the NEXT segment and
    truncates the region to nothing. Put that naive reader back and the probe must break."""
    from genios_engine.capture.semantic import evidence_binder as binder

    original = f"The PAN is {PAN} and the invoice follows."
    prepared = preprocess(original, event_id="evt_g9_d1")
    token_start, token_end = _mask_token(prepared)
    start = prepared.clean_text.index("is ")
    # The quote ENDS strictly inside the mask token — the one position at which the two readers
    # can disagree, because every segment boundary is a point where they agree by construction.
    end = token_end - 1
    quote = prepared.clean_text[start:end]
    span = ModelSpan(quote=quote, view_start=start, view_end=end)

    good = align_span(span, prepared, source_ref="prepared_content:evt_g9_d1")
    assert good is not None
    assert original[good.source_start:good.source_end] == f"is {PAN}", (
        "the exclusive end did not reach the end of the masked region")

    monkeypatch.setattr(binder, "_source_end",
                        lambda prepared, prep_end: prepared.to_source_offset(prep_end))
    broken = align_span(span, prepared, source_ref="prepared_content:evt_g9_d1")
    assert broken is not None
    assert original[broken.source_start:broken.source_end] != f"is {PAN}", (
        "the naive end reader produced the SAME region as the real one, so this probe cannot "
        "tell a broken alignment from a working one")
    assert broken.source_end < good.source_end, (
        "the naive reader is supposed to TRUNCATE the region into the mask's start")


def test_probe_the_alignment_is_sensitive_to_a_dropped_chunk_offset(monkeypatch):
    """NEUTRALISATION 2. `prepared = view + chunk.start_offset` is U2's stated rule. Drop the
    chunk term — the single most likely way to confuse the `view` and `prepared` frames — and
    the probe must stop resolving."""
    from genios_engine.capture.documents.chunking import Chunk

    original = "Preamble sentence that pads the front. Send the invoice to Priya by Friday."
    prepared = preprocess(original, event_id="evt_g9_d1")
    split = prepared.clean_text.index("Send")
    chunk = Chunk(text=prepared.clean_text[split:], start_offset=split,
                  end_offset=len(prepared.clean_text), index=0, oversized=False)
    quote = "Send the invoice"
    span = ModelSpan(quote=quote, view_start=0, view_end=len(quote))

    aligned = align_span(span, prepared, source_ref="prepared_content:evt_g9_d1", chunk=chunk)
    assert aligned is not None
    assert original[aligned.source_start:aligned.source_end] == quote

    no_chunk = align_span(span, prepared, source_ref="prepared_content:evt_g9_d1")
    assert no_chunk is not None
    assert original[no_chunk.source_start:no_chunk.source_end] != quote, (
        "dropping the chunk offset changed nothing, so the chunk term is not load-bearing here "
        "and the probe above proves less than it claims")


# =============================================================================================
# D2 + D5 · a total loss PARKS with a reason, and the monitor COUNTS it
# =============================================================================================


#: The doc-04 worked example's own event id, so a span built here and a span built by the
#: extractor name ONE frame — two frames make the binder raise, which would be a probe bug.
PREPARED_ID = "evt_g9_extract"
FENCE_NONCE = "deadbeefcafe0009"

#: "the caller did not say", so that `open_lane=None` (the pre-fix wiring) stays expressible and
#: distinguishable from omitting the keyword entirely.
_ABSENT = object()


@pytest.fixture
def probe_request(worked_example_text, eval_time):
    """Factory for one `ExtractionRequest`. Built here rather than imported from
    `tests/capture/semantic/test_extractor.py`: a probe that shares the unit's own fixtures
    shares its assumptions, which is the thing this file exists not to do."""
    from genios_engine.contracts.prepared_content import PreparedContent

    def _build(**overrides):
        prepared = PreparedContent(prepared_content_id=PREPARED_ID, event_id=PREPARED_ID,
                                   clean_text=worked_example_text, language="en")
        kwargs = dict(org_id="org_g9_probe", event_id=PREPARED_ID, source="gmail",
                      profile_id="email", tier="T2", prepared=prepared,
                      envelope=ex.EventEnvelope(
                          direction="inbound", sender="priya@acme.example",
                          recipients=("rohit@vendor.example",),
                          thread_position=2, thread_depth=3, subject="Annual contract"),
                      eval_time=eval_time, timezone="UTC", locale="en_US")
        kwargs.update(overrides)
        return ex.ExtractionRequest(**kwargs)
    return _build


@pytest.fixture
def run(probe_request, fake_llm):
    """`run(answer, ...)` -> (outcome, client). The fence nonce is pinned so the prompt is a
    stable string and the cache key is reproducible across runs."""
    def _run(*responses, store=None, llm=None, open_lane=_ABSENT, **overrides):
        client = llm if llm is not None else fake_llm(*responses)
        kwargs = {} if open_lane is _ABSENT else {"open_lane": open_lane}
        outcome = ex.extract(probe_request(**overrides), llm=client, store=store,
                             nonce=FENCE_NONCE, **kwargs)
        return outcome, client
    return _run


@pytest.fixture
def worked_payload(worked_example_text):
    """A correct model answer for the worked example, in the MODEL's own output shape."""
    def cite(quote):
        start = worked_example_text.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    return {
        "intent": "commit", "stance": "cautious",
        "topics": ["contract_renewal"],
        "entity_mentions": [
            {"surface_form": "Rohit", "entity_type": "person",
             "evidence": cite("Rohit"), "confidence_bp": 9000},
            {"surface_form": "Finance", "entity_type": "organization",
             "evidence": cite("Finance"), "confidence_bp": 8800},
        ],
        "commitments": [
            {"actor": "Finance", "action": "confirm absorption of increase",
             "is_conditional": True, "evidence": cite("Finance to confirm"),
             "confidence_bp": 8000},
        ],
    }


def _total_loss_answer() -> dict:
    """`{}` — a legal mapping that names none of the fields it was asked for."""
    return {}


def test_probe_a_total_loss_parks_with_a_reason_and_caches_nothing(run):
    """D2. The failure is silent by construction: a conforming, well-typed result with nothing
    in it looks exactly like a newsletter, so it cached as a success and every later replay
    returned the same nothing for zero model calls, forever. The three things that must all be
    true are asserted together, because any one of them alone is satisfiable by accident."""
    store = InMemoryExtractionCache()
    outcome, llm = run(_total_loss_answer(), _total_loss_answer(), store=store)

    assert outcome.result is None
    assert outcome.parked is not None
    assert outcome.parked.reason_code == ex.PARK_TOTAL_LOSS
    assert len(store) == 0, "the loss was cached, so it is now permanent"
    assert llm.call_count == 2, "the one repair retry must still be spent before parking"
    assert "no field" in outcome.parked.trace[0]["failure"]


def test_probe_a_message_that_genuinely_said_nothing_is_still_cached(run):
    """SENSITIVITY, and the boundary the fix must not cross. A newsletter ANSWERED the schema and
    claimed nothing; parking it would fill the queue with every "thanks!" in the org. A probe
    that only checked "empty parks" would be satisfied by a rule that parks both."""
    store = InMemoryExtractionCache()
    outcome, llm = run({"intent": "inform", "stance": "neutral", "topics": ["newsletter"],
                        "entity_mentions": [], "commitments": []}, store=store)
    assert outcome.parked is None and outcome.result is not None
    assert len(store) == 1
    assert llm.call_count == 1


def test_probe_the_park_is_sensitive_to_the_total_loss_rule_being_removed(run, monkeypatch):
    """NEUTRALISATION. Take `total_loss_failure` away — return None, its pre-fix answer for
    every input — and the empty answer must go straight back to being a cached success."""
    monkeypatch.setattr(ex, "total_loss_failure", lambda diagnostics, result: None)
    store = InMemoryExtractionCache()
    outcome, llm = run(_total_loss_answer(), store=store)

    assert outcome.parked is None, "the park survived the rule's removal — it came from elsewhere"
    assert outcome.result is not None
    assert len(store) == 1, "the pre-fix behaviour is a cached nothing, and that is what D2 ends"
    assert llm.call_count == 1


def test_probe_the_monitor_counts_the_loss_instead_of_reading_zero(run, worked_payload):
    """D5. Every counter that existed reads ZERO on a total loss, because each counts a REFUSAL
    and the refusals happen before `claims_in` moves — so an answer whose every claim died
    produced the same numbers as a newsletter. `claims_offered` counts what the MODEL PUT in the
    lanes, before this module's refusals, which is the only number that can tell the two apart.

    The old counter is asserted to still read zero on the same run. That is the sensitivity
    check: if `claims_offered` were merely `claims_in` renamed, this row could not hold.
    """
    spoiled = dict(worked_payload)
    for field in ex.CLAIM_FIELDS:
        entries = worked_payload.get(field)
        if entries:
            spoiled[field] = [dict(e, confidence_bp=e["confidence_bp"] / 10_000)
                              for e in entries if "confidence_bp" in e]
    spoiled["amounts"] = []

    lost, _ = run(spoiled, spoiled)
    assert lost.parked is not None and lost.parked.reason_code == ex.PARK_TOTAL_LOSS
    assert lost.diagnostics.claims_in == 0, "the OLD monitor — still reading zero, as recorded"
    assert lost.diagnostics.claims_offered > 0, "the new monitor read zero too; D5 is not fixed"
    assert lost.diagnostics.confidence_rejects == lost.diagnostics.claims_offered

    good, _ = run(worked_payload)
    assert good.diagnostics.claims_offered > 0
    assert good.diagnostics.claims_bound > 0

    assert f"{lost.diagnostics.claims_offered} claim(s)" in lost.parked.trace[0]["failure"], (
        "the park row does not say HOW MUCH was lost, so nobody can act on it")


# =============================================================================================
# D3 · a field outside the closed vocabulary lands in the OPEN LANE and nowhere else
# =============================================================================================

#: A name no consumer reads, in the shape the recorded failure took: `context/extract/vocab.py`
#: reached 268 distinct field names in one org, 192 used exactly once.
INVENTED_KEY = "deal_stage"
EVIDENCE_SENTENCE = "We can move forward with the annual contract."


def _result_with(lane: str, entry: dict):
    """A minimal `ExtractionResult` carrying ONE entry in ONE of the three untyped lanes.

    The provenance block is required by C-09 — an extraction that cannot say which model, prompt
    and schema produced it is not storable — so it is filled with the smallest legal values.
    """
    from genios_engine.contracts.extraction import ExtractionResult
    return ExtractionResult(intent="inform", stance="neutral", model_snapshot="probe-model-1",
                            prompt_version="p1", schema_version="s1", extraction_profile="email",
                            input_tokens=10, output_tokens=5, **{lane: [entry]})


@pytest.mark.parametrize("lane", list(UNTYPED_LANES))
def test_probe_an_invented_key_in_each_lane_lands_in_the_open_lane_and_nowhere_else(lane):
    """D3, once per lane the review named — `roles`, `relationships`, `scheduling_proposals`.

    Three claims, and the third is the one a lenient implementation loses: the key must be GONE
    from the lane, PRESENT in the open lane, and the declared keys beside it must be untouched.
    A guard that dropped the whole entry would satisfy the first two and destroy the extraction.
    """
    declared = sorted(UNTYPED_LANE_KEYS[lane] - {"evidence_text"})[0]
    entry = {declared: "Finance", INVENTED_KEY: "negotiation",
             "evidence_text": EVIDENCE_SENTENCE}
    sifted = sift_untyped_lanes(_result_with(lane, entry), source_ref="prepared_content:evt_g9")

    kept = getattr(sifted.result, lane)
    assert kept == [{declared: "Finance", "evidence_text": EVIDENCE_SENTENCE}], kept
    assert [r.key for r in sifted.refused] == [INVENTED_KEY]
    assert [r.lane for r in sifted.refused] == [lane]

    observed = {o.proposed_kind for o in sifted.result.unclassified_observations}
    assert INVENTED_KEY in observed, observed

    # "and nowhere else": the name must not survive anywhere in the three lanes.
    surviving = json.dumps({name: getattr(sifted.result, name) for name in UNTYPED_LANES})
    assert INVENTED_KEY not in surviving, surviving


@pytest.mark.parametrize("lane", list(UNTYPED_LANES))
def test_probe_a_lane_of_only_declared_keys_is_returned_untouched(lane):
    """SENSITIVITY. A sift that emptied every lane would pass the row above. An entry made only
    of declared keys must come back identical, and must reach no storage at all."""
    entry = {key: "x" for key in sorted(UNTYPED_LANE_KEYS[lane])}
    sifted = sift_untyped_lanes(_result_with(lane, entry), source_ref="prepared_content:evt_g9")
    assert getattr(sifted.result, lane) == [entry]
    assert sifted.refused == ()
    assert list(sifted.result.unclassified_observations) == []


def test_probe_the_sift_is_sensitive_to_the_key_vocabulary_being_opened(monkeypatch):
    """NEUTRALISATION. The closure IS the fix. Open the three key sets — the pre-fix state, in
    which `_Shape.MAPPING_LIST` asked only whether a key was a string — and the invented name
    must sail through into the lane again."""
    from types import MappingProxyType

    opened = MappingProxyType({lane: frozenset(UNTYPED_LANE_KEYS[lane]) | {INVENTED_KEY}
                               for lane in UNTYPED_LANES})
    monkeypatch.setattr(guard_mod, "untyped_lane_sets", lambda: opened)

    entry = {"party": "Finance", INVENTED_KEY: "negotiation"}
    sifted = sift_untyped_lanes(_result_with("roles", entry), source_ref="prepared_content:evt_g9")
    assert sifted.refused == ()
    assert getattr(sifted.result, "roles") == [entry], (
        "the sift refused the key even with the vocabulary opened, so it is not the vocabulary "
        "doing the work and the probe above measured something else")


# =============================================================================================
# D6a · the discovery lane has a real PRODUCER, and a row actually reaches it
#
# This is the one defect in the subsystem that raises no alarm of its own. A lane with no
# producer breaks nothing: the table simply stays empty, the weekly report says "no candidates",
# and the vocabulary quietly stops growing from evidence. So the probe is not "does something
# call `capture_unclassified`" — that can be satisfied by a helper nothing calls either — it is
# "drive the SHIPPING extraction path and count the rows that land".
# =============================================================================================


def _answer_with_an_invented_role_key() -> dict:
    """A model answer that fills `roles` with a key outside the closed set for that lane."""
    return {"intent": "inform", "stance": "neutral",
            "roles": [{"party": "Finance", INVENTED_KEY: "negotiation",
                       "evidence_text": "I still need Finance to confirm"}]}


def test_probe_a_row_reaches_the_discovery_lane_through_the_shipping_extract_path(run):
    """D6a. `extract()` is the only entry the pipeline uses, so it is the only place the guard
    can be wired and still be reached. Three things must hold at once:

    * the refused key is GONE from the lane the caller receives;
    * a row for it is IN the open-lane store;
    * the CACHED row is the sifted one — the guard has to run on the value the cache thunk
      returns, because every later replay reads the row and not the caller.
    """
    lane_store = InMemoryOpenLaneStore()
    cache = InMemoryExtractionCache()
    outcome, _ = run(_answer_with_an_invented_role_key(), store=cache, open_lane=lane_store)

    assert outcome.parked is None, outcome.parked
    assert outcome.result is not None
    assert outcome.result.roles == [{"party": "Finance",
                                     "evidence_text": "I still need Finance to confirm"}]

    rows = lane_store.observations_for(org_id="org_g9_probe", event_id=PREPARED_ID)
    assert [row.proposed_kind for row in rows] == [INVENTED_KEY], rows

    replayed, llm = run(_answer_with_an_invented_role_key(), store=cache,
                        open_lane=lane_store)
    assert replayed.cache_hit is True and llm.call_count == 0
    assert INVENTED_KEY not in json.dumps(replayed.result.roles), (
        "the cache kept the UNSIFTED dicts, so every replay restores the invented name")


def test_probe_the_discovery_row_is_sensitive_to_the_lane_store_being_absent(run):
    """NEUTRALISATION. `open_lane=None` is the pre-fix wiring and must behave exactly as it did:
    the run works, nothing is persisted. A probe that could not tell the two apart would be
    asserting that an in-memory store accepts writes."""
    lane_store = InMemoryOpenLaneStore()
    outcome, _ = run(_answer_with_an_invented_role_key(), store=InMemoryExtractionCache(),
                     open_lane=None)
    assert outcome.result is not None
    assert lane_store.observations_for(org_id="org_g9_probe", event_id=PREPARED_ID) == ()


def test_probe_the_open_lane_has_a_producer_reachable_from_the_pipeline():
    """The source-tree half. `capture_unclassified` must be reachable from `capture/pipeline.py`
    by CALLS, not merely defined: before the wiring landed, the only caller of the only caller
    was nothing at all, which every unit test in the subsystem passed straight through.
    """
    callers: dict[str, set[str]] = {}
    for py in ENGINE_ROOT.rglob("*.py"):
        module = "genios_engine." + str(py.relative_to(ENGINE_ROOT).with_suffix("")).replace("/", ".")
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        names = {node.func.id for node in ast.walk(tree)
                 if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
        callers[module] = names

    assert "capture_unclassified" in callers["genios_engine.capture.semantic.sink_guard"]
    assert "guard_typed_sink" in callers["genios_engine.capture.semantic.extractor"], (
        "nothing in the extractor calls the sink guard, so the guard's own caller is unreachable "
        "and the discovery lane cannot receive a row from a real extraction")
    assert "extract" in callers["genios_engine.capture.pipeline"]


# =============================================================================================
# D6b · the pipeline CALLS extract(), and the structured bypass still costs nothing
# =============================================================================================


class _RaisingLLM:
    """A model that RAISES on contact. Stricter than a fake with no canned answers: there is no
    count to be off by, and no way for a swallowed exception to look like a zero."""

    model = "must-never-be-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        raise AssertionError("the structured bypass paid for a model call")


def _lane(llm, **over):
    from genios_engine.capture import pipeline as P
    kwargs = dict(llm=llm, eval_time=datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc))
    kwargs.update(over)
    return P.SemanticLane(**kwargs)


def _email_object() -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id="m_d6b",
                     occurred_at=datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc),
                     actor_email="buyer@acme.example", recipients=("founder@acme.example",),
                     raw={"subject": "Contract",
                          "body": "We can move forward with the annual contract."})


def _crm_object() -> RawObject:
    """A typed CRM record — the structured lane the gate short-circuits."""
    return RawObject(source="hubspot", object_type="deal", source_object_id="deal_d6b",
                     occurred_at=datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc),
                     actor_email="founder@acme.example", content_version="v1",
                     raw={"dealname": "Acme", "dealstage": "contractsent", "amount": "84000"})


def _capture(raw, lane):
    return capture_event(raw, org_id="org_d6b", connection_id="con_d6b",
                         repo=InMemorySourceEventRepository(),
                         mailbox_owner="founder@acme.example", semantic=lane,
                         coverage_fn=lambda domain: {"coverage_ready": True})


def test_probe_an_unstructured_event_reaches_the_extractor(fake_llm):
    """D6b. Eleven modules under `capture/semantic/` were built and none was ever reached — no
    call site named `extractor.extract`, so the whole engine was dead weight that every test in
    `tests/capture/semantic/` proved correct and nothing ran."""
    llm = fake_llm({"intent": "inform", "stance": "neutral"})
    result = _capture(_email_object(), _lane(llm))

    assert result.outcome == "emitted"
    assert llm.call_count == 1, "the seam is still dead"
    assert result.extraction is not None and result.extraction.intent == "inform"
    assert "s2_semantic_extraction" in {r.stage for r in result.trace.records}


def test_probe_a_structured_object_makes_zero_calls_against_a_client_that_raises():
    """The other half, and the expensive one to get wrong: a lane that ignored the structured
    short-circuit would put an LLM bill on every CRM row a tenant has. Proved with a client that
    RAISES rather than with a call count, so there is no arithmetic to be wrong about."""
    result = _capture(_crm_object(), _lane(_RaisingLLM()))

    assert result.outcome == "emitted"
    assert result.gated is not None and result.gated.route == "structured"
    assert result.extraction is None
    assert any(r.stage == "s2_semantic_extraction" and r.reason_code == "structured_bypass"
               for r in result.trace.records), (
        "the bypass left no trace, so a lane that was never wired and a lane that declined are "
        "the same fact")


def test_probe_the_raising_client_would_actually_be_reached_on_the_unstructured_path():
    """SENSITIVITY. The zero-call assertion above is only meaningful if this client WOULD have
    been called on the other path. An email through the same lane must blow up."""
    with pytest.raises(AssertionError, match="paid for a model call"):
        _capture(_email_object(), _lane(_RaisingLLM()))


# =============================================================================================
# D10 · the cost estimate accounts for the FIXED per-call overhead
# =============================================================================================


def _probe_extraction_request(text: str, eval_time: datetime):
    """One planner request. `batch.ExtractionRequest` is the PLANNER's own type — a drain plans
    from event_id/profile/content before an `extractor.ExtractionRequest` exists — so the probe
    uses it rather than assuming the two names denote one class."""
    return batch_mod.ExtractionRequest(event_id="evt_g9_plan", profile_id="email",
                                       content=text, requested_tier="T2")


def test_probe_a_planned_call_is_priced_above_its_body(worked_example_text, eval_time):
    """D10. The estimator charged `len(template)/4 + 900` while an assembled call carries the
    profile spine, the ~7,000-character schema block, the vocabulary block and the fence — on
    EVERY call. A governor short by that much authorises spend nobody approved and trips its
    daily breaker after the money is gone.

    The overhead is re-derived here from `fixed_prompt_tokens` and compared to the plan, so the
    probe measures whether the planner ACTUALLY ADDS IT rather than restating the constant.
    """
    from genios_engine.capture.semantic.batch import CHARS_PER_TOKEN, plan_batch

    plan = plan_batch([_probe_extraction_request(worked_example_text, eval_time)])
    assert len(plan.calls) == 1, plan
    call = plan.calls[0]

    body_tokens = -(-len(worked_example_text) // CHARS_PER_TOKEN)
    overhead = batch_mod.fixed_prompt_tokens("email")
    assert overhead > 1_000, (
        f"the measured fixed overhead is only {overhead} tokens; the schema block alone is "
        "~7,000 characters, so this is the term D10 says was missing")
    assert call.input_tokens >= body_tokens + overhead
    assert call.input_tokens - body_tokens >= overhead


def test_probe_the_price_is_sensitive_to_the_overhead_term_being_removed(
        monkeypatch, worked_example_text, eval_time):
    """NEUTRALISATION. Zero the fixed term — the pre-fix accounting — and the planned price must
    collapse to roughly the body. A probe that still passed would be measuring the body."""
    from genios_engine.capture.semantic.batch import plan_batch

    request = _probe_extraction_request(worked_example_text, eval_time)
    overhead = batch_mod.fixed_prompt_tokens("email")
    priced = plan_batch([request]).calls[0].input_tokens

    monkeypatch.setattr(batch_mod, "fixed_prompt_tokens", lambda profile_id: 0)
    unpriced = plan_batch([request]).calls[0].input_tokens

    assert priced - unpriced == overhead, (
        "removing the fixed term did not move the price by exactly that term, so the planner is "
        "not the thing charging it")
    assert unpriced < priced


def test_probe_the_overhead_is_generated_from_the_real_blocks_not_a_constant():
    """It is MEASURED, not assumed — that is the whole point of the unit. Adding a word to a
    closed set or a field to `ExtractionResult` must re-price the call by itself, so the number
    is re-derived here from the same generators the prompt uses."""
    from genios_engine.capture.semantic.batch import CHARS_PER_TOKEN, FENCE_OVERHEAD_CHARS
    from genios_engine.capture.semantic.schema_gen import generate_schema_block
    from genios_engine.capture.semantic.vocabulary import vocabulary_block

    generated = len(generate_schema_block()) + len(vocabulary_block()) + FENCE_OVERHEAD_CHARS
    assert batch_mod.fixed_prompt_tokens("email") >= -(-generated // CHARS_PER_TOKEN), (
        "the fixed overhead is smaller than the blocks it is supposed to contain, so it is a "
        "constant somebody typed rather than a measurement")


def test_probe_a_row_reaches_the_lane_through_capture_event_itself():
    """D6a end to end, through the door a sweep actually uses.

    `extract()` accepting an `open_lane` is necessary and not sufficient: the pipeline builds the
    request and the lane, so a `SemanticLane` that carries no store leaves the guard with nowhere
    to put the refused names and the discovery table stays empty exactly as before. This drives
    `capture_event` — the one entry every connector, the webhook and the manual door share.
    """
    from genios_engine.capture import pipeline as P
    from tests.capture.conftest import FakeLLM

    lane_store = InMemoryOpenLaneStore()
    llm = FakeLLM(_answer_with_an_invented_role_key())
    result = _capture(_email_object(), _lane(llm, open_lane=lane_store,
                                             cache=InMemoryExtractionCache()))

    assert result.extraction is not None, result.extraction_parked
    assert INVENTED_KEY not in json.dumps(result.extraction.roles), result.extraction.roles

    rows = lane_store.observations_for(org_id="org_d6b", event_id=result.event.event_id)
    assert [row.proposed_kind for row in rows] == [INVENTED_KEY], rows
    assert isinstance(P.SemanticLane(llm=llm, eval_time=result.event.occurred_at).open_lane,
                      type(None)), "a lane with no store must still be constructible"


def test_probe_the_lane_store_is_wired_by_the_factory_the_sweep_uses(monkeypatch):
    """The factory half. `make_semantic_lane` is what every sweep, the webhook and the manual
    door get their lane from, so a lane built there with `open_lane=None` would leave the whole
    production path unable to discover anything — while every test above still passed."""
    from genios_engine.platform import wiring

    store = wiring.make_open_lane_store()
    assert hasattr(store, "add") and hasattr(store, "observations_for"), (
        "the factory did not return something shaped like an OpenLaneStore")

    class _Settings:
        use_real_llm = True

    monkeypatch.setattr(wiring, "get_settings", lambda: _Settings())
    monkeypatch.setattr(wiring, "make_open_lane_store", lambda: "SENTINEL_STORE")
    monkeypatch.setattr(wiring, "make_extraction_cache", lambda: None)
    monkeypatch.setattr(wiring, "make_llm_client", lambda: object())
    monkeypatch.setattr(wiring, "_org_timezone", lambda engine, org_id: "UTC")
    built = wiring.make_semantic_lane("org_g9_wire", engine=None,
                                      activated=frozenset({"org_g9_wire"}))
    assert built is not None and built.open_lane == "SENTINEL_STORE", (
        "make_semantic_lane built a lane with no discovery store, so nothing a real tenant "
        "extracts can ever reach the open lane")


# =============================================================================================
# W0 / W1 / W2 still hold — the four invariants the earlier waves are worth nothing without.
#
# These are not G9's own criteria. They are here because G9 is the first wave to WIRE the
# earlier ones into a path that runs, and a wiring change is exactly how a frozen invariant
# stops holding without anybody editing the file that states it.
# =============================================================================================


def test_probe_a_fabricated_span_loses_its_verified_flag():
    """W1/ALG-08. `verified=True` means CHECKED, and the grader is the only thing allowed to set
    it — the moment an extractor can, the flag means "claimed" and the receipt system is over.
    So a span that cites a sentence the source does not contain must come back FALSE even though
    it arrived True."""
    source = "Budget approved. Please send the revised contract by Friday."
    fabricated = EvidenceSpan(source_ref="prepared_content:evt_g9_w1",
                              quote="I approve the discount to 40 percent",
                              start_offset=0, end_offset=36, verified=True)

    verdict, graded = verify_span(fabricated, source)
    assert verdict is SpanVerdict.UNVERIFIED, verdict
    assert graded.verified is False, "a fabricated receipt kept the flag it set on itself"

    real = EvidenceSpan(source_ref="prepared_content:evt_g9_w1", quote="Budget approved",
                        start_offset=0, end_offset=15, verified=False)
    real_verdict, real_graded = verify_span(real, source)
    assert real_verdict in _GROUNDED and real_graded.verified is True, (
        "the grader refuses everything, so the row above proves nothing about fabrication")


#: The sources a composition is allowed to speak for. Rule 11's ceiling is `min(sources)`.
_SOURCES = (6000, 7000, 9000)


@pytest.mark.parametrize("wanted,evidence,lift_bp,why", [
    (9500, (), 0, "an unnamed raise above the ceiling is the Rule 11 violation itself"),
    (5000, (), 0, "a LOWERING is always allowed — Rule 11 only constrains the upward direction"),
    (9500, ("thread:evt_2",), 8000, "a NAMED witness buys a bounded raise, never an exemption"),
    (9500, ("thread:evt_2",), 0, "a name with nothing behind it lifts by nothing"),
])
def test_probe_rule_11_binds_every_published_axis(wanted, evidence, lift_bp, why):
    """W1/Globe Rule 11: *a layer may lower confidence; it may only raise it by naming
    independent evidence.* Enforced by CLAMPING at the module boundary rather than by raising,
    because a composer that violates it still produces a number, and a wrong number that ships
    is worse than an exception.

    The row that matters is the third: naming buys a BOUNDED raise. Returning the wanted value
    unchanged — the shape this function once had — let one named aside at 100 bp lift a ceiling
    of 100 to 9003, which is not a rule with an exception but a rule with an off switch.
    """
    from genios_engine.capture.validate import confidence as C

    ceiling = C.rule_11_ceiling(_SOURCES)
    assert ceiling == min(_SOURCES), "the ceiling is min(sources), stated once"

    bounded = C.enforce_rule_11(wanted, ceiling_bp=ceiling, independent_evidence=evidence,
                                lift_bp=lift_bp)
    assert isinstance(bounded, int) and not isinstance(bounded, bool), (
        "a confidence is integer basis points, never a float")
    assert 0 <= bounded <= 10_000

    if wanted <= ceiling:
        assert bounded == wanted, why
    elif not evidence or lift_bp == 0:
        assert bounded == ceiling, why
    else:
        # The SIZE of the raise is the size of the addition, not the size of the request.
        assert ceiling < bounded < wanted, why


def test_probe_rule_11_is_sensitive_to_the_ceiling_being_absent():
    """SENSITIVITY. `rule_11_ceiling(())` is None and means *V-6 did not apply here* — not
    *V-6 passed*. A probe that could not tell those apart would report an unbounded composition
    as a compliant one."""
    from genios_engine.capture.validate import confidence as C

    assert C.rule_11_ceiling(()) is None
    assert C.enforce_rule_11(9500, ceiling_bp=None) == 9500
    assert C.enforce_rule_11(9500, ceiling_bp=6000) == 6000


def test_probe_structural_token_offsets_round_trip(worked_example_text):
    """W2. The structural scanner's offsets index the string it was handed, and a token that
    cannot be sliced back out of that string is an offset in some other frame."""
    from genios_engine.capture.structural.tokens import scan

    scanned = scan(worked_example_text)
    assert scanned.tokens, "the scanner produced no positioned tokens to round-trip"
    for token in scanned.tokens:
        sliced = worked_example_text[token.start_offset:token.end_offset]
        assert sliced == token.raw, (token, sliced)
    assert any(t.token_type == "currency_token" for t in scanned.tokens), (
        "the worked example contains $84K; a scan that found no currency token is not scanning")


@pytest.mark.pg
def test_probe_deleting_an_org_still_works_after_the_extraction_table_rename(live_db_url):
    """W0/W2 · the rename in migration 0080 (`l2_extraction_results` -> `l1_extraction_results`)
    moved a table that account erasure deletes from and that carries an org FK. A rename that
    left either half behind is invisible until the day a tenant asks to be deleted and the
    transaction fails — or, worse, succeeds while leaving their extracted content behind.

    Rolled back at the end: this probe writes, it does not keep.
    """
    from sqlalchemy import text as sql

    from genios_engine.platform.db import get_engine

    engine = get_engine(live_db_url)      # the repo's own driver normalisation, not sqlalchemy's
    org = "org_g9_erasure_probe"
    with engine.connect() as conn:
        tx = conn.begin()
        try:
            for table in ("l1_extraction_results", "unclassified_observations"):
                exists = conn.execute(sql("select to_regclass(:t)"), {"t": f"public.{table}"}
                                      ).scalar()
                assert exists is not None, f"{table} does not exist; migration 0080/0079 not applied"

            conn.execute(sql("insert into orgs (id, name, email) values (:o, 'G9 probe', :e) "
                             "on conflict (id) do nothing"),
                         {"o": org, "e": "g9probe@example.invalid"})
            conn.execute(sql(
                "insert into l1_extraction_results (processing_key, org_id, event_id, output) "
                "values (:k, :o, 'evt_g9_erasure', '{}'::jsonb) "
                "on conflict (processing_key) do nothing"),
                {"k": "g9probe-cache-key", "o": org})
            conn.execute(sql(
                "insert into unclassified_observations (observation_id, org_id, event_id, "
                "proposed_kind, proposed_kind_raw, description, quote, source_ref, start_offset, "
                "end_offset, confidence_bp, span_verdict) values (:i, :o, 'evt_g9_erasure', "
                "'deal_stage', 'Deal Stage', 'probe', 'a quote', "
                "'prepared_content:evt_g9_erasure', 0, 7, 5000, 'unverified') "
                "on conflict (observation_id) do nothing"),
                {"i": "g9probe-observation", "o": org})

            before = conn.execute(sql("select count(*) from l1_extraction_results where org_id=:o"),
                                  {"o": org}).scalar()
            assert before == 1, "the probe row did not land, so the deletion below proves nothing"

            deleted = conn.execute(sql("delete from orgs where id=:o"), {"o": org})
            assert deleted.rowcount == 1

            for table in ("l1_extraction_results", "unclassified_observations"):
                left = conn.execute(sql(f"select count(*) from {table} where org_id=:o"),
                                    {"o": org}).scalar()
                assert left == 0, (
                    f"{table} kept rows for a deleted org — the FK cascade did not survive the "
                    "rename, and a tenant's extracted content outlives their erasure request")
        finally:
            tx.rollback()
