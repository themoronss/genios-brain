"""STEP-12 · the ideal reader cites what the dossier in front of it shows.

    pytest tests/replays/test_the_ideal_reader_cites_what_it_is_shown.py -q

Tree `yc2_w27_s12` M33.C2.L-data.V0.U03 (`tests/replays/expert_citations.py`, read by `ideal_reader`), `03` F177.
An authored review cites the ids of the dossier it was written against. Served to a dossier that shows the
same lines under other ids — the first-connect door mints ids in another order — it cites the ids shown
there, line for line; a citation whose line that dossier does not hold exactly once stays as authored, for
the contract to refuse. And the table of where every authored citation points is current: every id every
case's answers cite has its line.
"""
from __future__ import annotations

import pytest

from tests.replays import expert_citations as X
from tests.replays.founder_case import load_cases

pytestmark = pytest.mark.unit

SWEEP = """DOSSIER dossier.v1 — file node_aaa
- [evt_aaa] 2026-08-11 09:20 Marco Ruiz <marco@altavia.test> “Re: Arjun <> Marco Ruiz”
- [loop:loop_111] an open ask — a short deck — asked by Marco, owed by us
- [num:usual_gap] the usual gap between their mails: five days (n = 2)
- [sit:sit_x1] account_admin (admin) · active"""
DOOR = SWEEP.replace("evt_aaa", "evt_bbb").replace("loop_111", "loop_222").replace("sit_x1", "sit_y2")

ANSWER = {
    "facts": [{"claim": "Marco asked for a short deck", "evidence": ["evt_aaa", "num:usual_gap"]},
              {"claim": "His ask is open and waits on us", "evidence": ["loop:loop_111"]},
              {"claim": "The file sits under an account situation", "evidence": ["sit:sit_x1"]}],
    "inferences": [{"claim": "He is screening a raise", "based_on": ["fact:1", "evt_aaa"]}],
    "proposed_kind": {"kind": "investor", "why": "he backs software", "evidence": ["evt_aaa"]},
    "mode": "act"}


def _prompt(text: str) -> str:
    return f"You are the expert.\n<dossier>\n{text}\n</dossier>\nAnswer as JSON."


def _spots():
    return {cid: [list(spot)] for cid, spot in X.where(SWEEP).items() if cid in X.cited(ANSWER)}


def test_each_cited_id_is_found_on_its_line_and_which_of_its_ids_it_is():
    spots = X.where("- [card:card_1] a card about [evt_aaa], surfaced")
    assert spots == {"card:card_1": ("- [#] a card about [#], surfaced", 0),
                     "evt_aaa": ("- [#] a card about [#], surfaced", 1)}
    assert X.cited(ANSWER) == {"evt_aaa", "num:usual_gap", "loop:loop_111", "sit:sit_x1"}


def test_a_dossier_showing_the_same_lines_under_other_ids_is_cited_by_its_own_ids():
    served = X.translate(ANSWER, _prompt(DOOR), _spots())
    assert served["facts"][0]["evidence"] == ["evt_bbb", "num:usual_gap"]
    assert served["facts"][1]["evidence"] == ["loop:loop_222"]
    assert served["facts"][2]["evidence"] == ["sit:sit_y2"]
    assert served["inferences"][0]["based_on"] == ["fact:1", "evt_bbb"], "a fact's number is no id"
    assert served["proposed_kind"]["evidence"] == ["evt_bbb"]
    assert served["mode"] == "act" and ANSWER["facts"][0]["evidence"][0] == "evt_aaa", \
        "the authored answer itself is never changed"


def test_a_dossier_that_shows_the_cited_ids_is_answered_as_authored():
    assert X.translate(ANSWER, _prompt(SWEEP), _spots()) is ANSWER


def test_a_line_held_twice_or_not_at_all_is_never_guessed():
    twice = DOOR + "\n" + DOOR.splitlines()[1].replace("evt_bbb", "evt_ccc")
    served = X.translate(ANSWER, _prompt(twice), _spots())
    assert served["facts"][0]["evidence"][0] == "evt_aaa", "two lines alike: no guess"
    assert served["facts"][1]["evidence"] == ["loop:loop_222"], "the rest still translates"
    gone = "\n".join(line for line in DOOR.splitlines() if "loop_222" not in line)
    assert X.translate(ANSWER, _prompt(gone), _spots())["facts"][1]["evidence"] == ["loop:loop_111"]


def test_an_id_with_no_recorded_line_stays_as_authored():
    spots = {k: v for k, v in _spots().items() if k != "sit:sit_x1"}
    assert X.translate(ANSWER, _prompt(DOOR), spots)["facts"][2]["evidence"] == ["sit:sit_x1"]


def test_the_ideal_reader_serves_the_expert_the_ids_its_dossier_shows(monkeypatch):
    """The seam: an authored answer served through `IdealReader` cites the ids its prompt shows."""
    from tests.replays.ideal_reader import IdealReader
    case = next(c for c in load_cases() if (c.model or {}).get("expert"))
    entry = next(e for e in case.model["expert"] if len(e["when"]) == 1)
    key = entry["when"][0]
    target = next(i for i in sorted(X.cited(entry["answer"])) if i.startswith("evt_"))
    line = f"- [{target}] 2026-08-11 a mail on the file {key}"
    monkeypatch.setattr(X, "spots_for", lambda case_id: {target: [[X.shape(line), 0]]})
    prompt = _prompt(line.replace(target, "evt_moved"))
    served = IdealReader(case)._answer("expert", prompt)
    assert target not in X.cited(served) and "evt_moved" in X.cited(served)


def test_where_every_authored_citation_points_is_measured():
    """`expert_citations.json` is current: every id every case's authored answers cite has its line."""
    table = X._table()
    for case in load_cases():
        want = set().union(*(X.cited(e["answer"]) for e in (case.model or {}).get("expert") or ()))
        have = set(table.get(case.case_id, {}))
        assert want <= have, f"{case.case_id}: cited with no line recorded — {sorted(want - have)}"
        for cid, lines in table.get(case.case_id, {}).items():
            assert lines and all("[#]" in shape_ and int(index) >= 0 for shape_, index in lines), \
                (case.case_id, cid)


def test_a_line_printed_otherwise_as_time_passes_is_matched_by_any_of_its_shapes():
    """A situation's quiet days move between reviews: the line each dossier printed is kept, and the one
    the replaying dossier shows is the one matched."""
    later = DOOR.replace("account_admin (admin) · active", "account_admin (admin) · active · quiet 1.5 days")
    spots = _spots()
    spots["sit:sit_x1"] = [list(X.where(SWEEP)["sit:sit_x1"]),
                           list(X.where(SWEEP.replace("· active", "· active · quiet 1.5 days"))["sit:sit_x1"])]
    assert X.translate(ANSWER, _prompt(later), spots)["facts"][2]["evidence"] == ["sit:sit_y2"]
    only_first = {**spots, "sit:sit_x1": spots["sit:sit_x1"][:1]}
    assert X.translate(ANSWER, _prompt(later), only_first)["facts"][2]["evidence"] == ["sit:sit_x1"]


# ── a recording is replayed in its key's own frame (`tests/replays/harness`) ────────────────────
SWEPT = ("You are the founder's chief of staff, thirty years in the work.\n<dossier>\n"
         "- [evt_aaaaaaaaaaaaaaaaaaaaaaaa] a mail from Marco\n"
         "- [loop:loop_111111111111111111111111] his ask, owed by us\n</dossier>")
DOORED = SWEPT.replace("a" * 24, "b" * 24).replace("1" * 24, "2" * 24)


class _Says:
    model = "test"

    def __init__(self, parsed):
        self.parsed = parsed

    def call(self, prompt, **kw):
        from genios_engine.context.llm.client import LLMResult
        import json
        return LLMResult(parsed=self.parsed, raw=json.dumps(self.parsed), input_tokens=1,
                         output_tokens=1, model="test")


def test_a_recording_cites_the_ids_of_the_prompt_it_is_replayed_for():
    """The key forgives minted ids, so the door's prompt finds the sweep's recording — and the answer
    read back cites the door's own ids: what it said was "the first event this prompt names"."""
    from tests.replays.harness import CassetteRecorder, RecordedLLM, cassette_key
    said = {"facts": [{"claim": "Marco asked", "evidence": [f"evt_{'a' * 24}",
                                                           f"loop:loop_{'1' * 24}",
                                                           f"evt_{'f' * 24}"]}]}
    recorder = CassetteRecorder(_Says(said))
    assert recorder.call(SWEPT).parsed == said, "the chain is answered as the model said"
    [entry] = recorder.cassette.values()
    assert entry["framed"] and entry["parsed"]["facts"][0]["evidence"] == [
        "evt_#1", "loop:loop_#1", f"evt_{'f' * 24}"], "an id the prompt never named stays as written"
    assert cassette_key(DOORED) == cassette_key(SWEPT)
    replayed = RecordedLLM(recorder.cassette).call(DOORED).parsed
    assert replayed["facts"][0]["evidence"] == [f"evt_{'b' * 24}", f"loop:loop_{'2' * 24}",
                                                f"evt_{'f' * 24}"]
    assert RecordedLLM(recorder.cassette).call(SWEPT).parsed == said


def test_a_recording_made_before_the_frame_replays_as_it_was_written():
    from tests.replays.harness import RecordedLLM, cassette_key
    old = {cassette_key(SWEPT): {"site": "expert", "parsed": {"evidence": [f"evt_{'a' * 24}"]},
                                 "raw": None, "input_tokens": 1, "output_tokens": 1}}
    assert RecordedLLM(old).call(DOORED).parsed == {"evidence": [f"evt_{'a' * 24}"]}
