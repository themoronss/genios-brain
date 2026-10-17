"""STEP-13b · M37's acceptance on the golden set — the expert holds the GeniOS Engine, and the check holds what it makes of it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… GENIOS_GOLDEN_REQUIRED=1 pytest tests/replays/test_the_engine_is_in_the_experts_hands.py -q

Tree `yc2_w27_s13b` M37.C6.L-integration.V14.U04. No spend: every case runs through the REAL chain with its model answered from its
cassette. Three things are measured:

  1 · THE ENGINE IS IN THE DOSSIER. Of the authored answers' files, at least 57 print an engine line of the authored or learned
      families (not a unit's reading) in the section WHAT THE ENGINE KNOWS ABOUT ITS SITUATIONS, and every investor file prints the
      investor playbook and the engine section's fundraising capability lines.
  2 · EACH WAY OF SAYING MORE THAN THE ENGINE SAYS IS CAUGHT, WITH ITS REASON, ON ITS OWN CASE, AND REACHES NO CARD - by mutation of
      F11's served answer (an investor file): an engine id never printed (`unknown_evidence`), an own line with a number
      (`own_states_a_number`), an own line naming the file's person (`own_names_the_file`), a fact citing only an engine line
      (`engine_is_no_fact`), an engine line's name planted in a pattern not on that line (`unsupported`), and a line cited by its
      WORDS - a head line is read as its id and counted (`by_line`, V9.U04), a section title still drops `unknown_evidence`.
  3 · THE NEGATIVE CONTROL. With the engine sections off, an authored line citing an engine line drops `unknown_evidence`; with
      them on, the same line stands.
"""
from __future__ import annotations

import re
from functools import lru_cache

import pytest

from genios_engine.contracts.claim_check import (DROPPED, ENGINE_IS_NO_FACT, KEPT, NOTED, OWN_NAMES_THE_FILE,
                                                 OWN_STATES_A_NUMBER, SHOWN, UNKNOWN_EVIDENCE, UNSUPPORTED, BY_LINE,
                                                 CheckedReview)
from genios_engine.contracts.engine_read import family_of
from tests.replays.harness import RecordedLLM, identify_site
from tests.replays.test_every_claim_is_checked import (AUTHORED, CASES, Mutation, _carrying, _mutated_run,
                                                       _scratch_db, _the_mutated_review)

pytestmark = [pytest.mark.pg, pytest.mark.golden]

SECTION = "## WHAT THE ENGINE KNOWS ABOUT ITS SITUATIONS"
_LINE = re.compile(r"^- \[([^\[\]\s]+)\]", re.M)
_KEY = re.compile(r"^Counterparty: .*? <([^>]+)> \(", re.M)


def _engine_section(dossier: str) -> str:
    if SECTION not in dossier:
        return ""
    return dossier.split(SECTION, 1)[1].split("\n## ", 1)[0]


@lru_cache(maxsize=1)
def _first_dossiers() -> dict[tuple[str, str], str]:
    """Every authored case replayed from its cassette: the FIRST dossier the expert is shown for each file."""
    from tests.replays import cassettes
    from tests.replays.engine_runner import run_case
    from tests.replays.expert_citations import dossier as dossier_of

    class _Keeping(RecordedLLM):
        def __init__(self, cassette):
            super().__init__(cassette)
            self.rows: list[tuple[str, str]] = []

        def call(self, prompt, **kw):
            if identify_site(prompt) == "expert":
                m = _KEY.search(prompt)
                if m:
                    self.rows.append((m.group(1), dossier_of(prompt)))
            return super().call(prompt, **kw)
    out: dict[tuple[str, str], str] = {}
    for case_id in AUTHORED:
        llm = _Keeping(cassettes.load(CASES[case_id]))
        run_case(CASES[case_id], llm)
        for key, text in llm.rows:
            out.setdefault((case_id, key), text)
    return out


def _entries() -> list[tuple[str, str]]:
    return [(c, e["when"][0].strip("<>")) for c in AUTHORED for e in CASES[c].model["expert"]]


def _authored_lines(dossier: str) -> list[str]:
    """The engine lines of the section that are the corpus's or the brains' own - not a reasoning unit's reading."""
    return [i for i in _LINE.findall(_engine_section(dossier)) if family_of(i) and not i.startswith("ru:")]


# ── 1 · the engine is in the dossier ─────────────────────────────────────────────────────────────────────────

def test_at_least_57_of_the_authored_answers_dossiers_print_an_engine_line():
    _scratch_db()
    dossiers = _first_dossiers()
    entries = _entries()
    printed = [(c, k) for c, k in entries if _authored_lines(dossiers[(c, k)])]
    assert len(printed) >= 57, f"{len(printed)} of {len(entries)} authored answers' dossiers print an engine line"
    assert len(entries) >= 94, "the authored set the acceptance counts"


def test_every_investor_file_prints_the_investor_playbook():
    _scratch_db()
    investors = {(c, k): d for (c, k), d in _first_dossiers().items() if "Kind of work: investor" in d}
    assert len(investors) >= 9, "the golden set's investor files (the file's kind of work is investor)"
    # The investor playbook is in the dossier (`[pb:…investor_relations.run_an_investor_conversation]`), and the engine
    # section adds the fundraising capability's own lines (`cap:founder_office.fundraising.investor_relations#…`).
    missing = [ck for ck, d in investors.items()
               if "[pb:founder_office.pb.investor_relations.run_an_investor_conversation]" not in d
               or not any(i.startswith("cap:founder_office.fundraising.investor_relations") for i in _authored_lines(d))]
    assert not missing, f"investor files that do not print the investor playbook and the engine's capability: {missing}"


# ── 2 · each way of saying more than the engine says is caught, with its reason, and reaches no card ──────────

def _first_engine_id(prompt: str, *families: str) -> str:
    found = [i for i in _authored_lines(prompt) if not families or i.split(":")[0] in families]
    assert found, "the dossier prints no such engine line - the engine did not reach this file"
    return found[0]


def _append_fact(claim: str, evidence):
    def mutate(answer, prompt):
        answer["facts"].append({"claim": claim, "evidence": evidence(answer, prompt), "quote": None})
        return answer
    return mutate


def _first_fact_evidence(answer):
    return list(answer["facts"][0]["evidence"])


def _own(claim: str):
    def mutate(answer, _prompt):
        answer["own"] = [{"kind": "practice", "claim": claim, "why": "a reply that waits loses the person's attention"}]
        return answer
    return mutate


def _pattern_on_the_engine(claim: str):
    def mutate(answer, prompt):
        answer["patterns"].append({"kind": "pattern", "claim": claim, "based_on": [_first_engine_id(prompt)]})
        return answer
    return mutate


CASE, KEY = "F11", "northfieldvc.test"


def _mutation(id_, mutate, line, verdict, reason, detail, *, echo):
    return Mutation(id_, CASE, KEY, 1, mutate, line, verdict, reason, detail, SHOWN, reads=(), echo=echo)


MUTATIONS = (
    _mutation("an_engine_id_never_printed",
              _append_fact("Tom wrote to us unprompted", lambda a, p: [*_first_fact_evidence(a), "rule:never_printed_anywhere"]),
              "fact:6", DROPPED, UNKNOWN_EVIDENCE, "rule:never_printed_anywhere", echo=("Tom wrote to us unprompted",)),
    _mutation("an_own_line_with_a_number", _own("a partner who writes unprompted answers within 3 days"),
              "own:1", DROPPED, OWN_STATES_A_NUMBER, "3", echo=("answers within 3 days",)),
    _mutation("an_own_line_naming_the_files_person", _own("Keller answers a request the same day"),
              "own:1", DROPPED, OWN_NAMES_THE_FILE, "keller", echo=("Keller answers a request",)),
    _mutation("a_fact_citing_only_an_engine_line",
              _append_fact("A first call follows a reply", lambda a, p: [_first_engine_id(p)]),
              "fact:6", DROPPED, ENGINE_IS_NO_FACT, "", echo=("A first call follows a reply",)),
    _mutation("an_engine_lines_name_planted_in_a_pattern",
              _pattern_on_the_engine("Zephyr Capital always follows the playbook"),
              "pattern:5", DROPPED, UNSUPPORTED, "Zephyr", echo=("Zephyr Capital always follows",)),
    _mutation("a_section_title_cited_by_its_words",
              _append_fact("The file is about investor work", lambda a, p: [*_first_fact_evidence(a), "THE FILE"]),
              "fact:6", DROPPED, UNKNOWN_EVIDENCE, "THE FILE", echo=("The file is about investor work",)),
)


@pytest.mark.parametrize("m", MUTATIONS, ids=lambda m: m.id)
def test_each_mutation_is_caught_with_its_reason(m):
    _scratch_db()
    ran = _mutated_run(m, checked=True)
    checked = CheckedReview.from_mapping(_the_mutated_review(m, ran)["checked"])
    found = [v for v in checked.verdicts if v.line == m.line and v.verdict == DROPPED]
    assert any(v.reason == m.reason and m.detail.lower() in v.detail.lower() for v in found), \
        f"{m.id}: no dropped {m.reason} ({m.detail!r}) on {m.line}: {checked.as_mapping()['verdicts']}"
    assert {(v.line, v.reason) for v in checked.dropped} == {(m.line, m.reason)}, \
        f"{m.id}: dropped {[(v.line, v.reason, v.detail) for v in checked.dropped]}"
    assert checked.fate == SHOWN, f"{m.id}: {checked.fate} - {checked.because}"


@pytest.mark.parametrize("m", MUTATIONS, ids=lambda m: m.id)
def test_a_caught_mutation_reaches_no_card(m):
    _scratch_db()
    ran = _mutated_run(m, checked=True)
    assert not _carrying(ran.cards, m.echo, questions=True), f"{m.id}: a card says {m.echo}"


def test_a_head_line_cited_by_its_words_is_read_as_its_id_and_counted():
    _scratch_db()
    m = _mutation("a_head_line_cited_by_its_words",
                  _append_fact("The file is about investor work", lambda a, p: [*_first_fact_evidence(a), "Kind of work: investor"]),
                  "fact:6", KEPT, "", "", echo=())
    ran = _mutated_run(m, checked=True)
    checked = CheckedReview.from_mapping(_the_mutated_review(m, ran)["checked"])
    assert not checked.dropped and checked.fate == SHOWN
    [note] = [v for v in checked.verdicts if v.line == "fact:6" and v.verdict == NOTED]
    assert note.reason == BY_LINE and note.detail == "Kind of work: investor -> file:kind"
    assert "file:kind" in checked.cited


# ── 3 · the negative control: the engine sections off ────────────────────────────────────────────────────────

def _cites_an_engine_section_line() -> Mutation:
    import json
    from pathlib import Path
    files = json.loads((Path(__file__).parent / "expert_files.json").read_text())
    engine_id = next(i for i in files[CASE][KEY]["evidence"] if i.startswith("cap:"))
    return _mutation("cites_a_line_only_the_engine_section_prints",
                     _append_fact("Tom wrote to us unprompted", lambda a, p: [*_first_fact_evidence(a), engine_id]),
                     "fact:6", DROPPED, UNKNOWN_EVIDENCE, engine_id, echo=())


def test_with_the_engine_sections_on_the_same_line_stands():
    _scratch_db()
    m = _cites_an_engine_section_line()
    ran = _mutated_run(m, checked=True)
    checked = CheckedReview.from_mapping(_the_mutated_review(m, ran)["checked"])
    assert not checked.dropped and checked.fate == SHOWN


def test_with_the_engine_sections_off_an_authored_line_citing_them_drops_unknown_evidence():
    """The engine-off dossier is a prompt no cassette holds, so the ideal reader answers it from the authored answers
    (`06` D49) - with the same one mutation served at the file's first review."""
    _scratch_db()
    import copy
    import dataclasses
    import json

    from sqlalchemy import text

    from genios_engine.api import routes
    from genios_engine.reason.expert import file_engine
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.ideal_reader import IdealReader
    from tests.replays.test_every_claim_is_checked import _serves

    m = _cites_an_engine_section_line()

    class _Reader:
        def __init__(self):
            self._reader, self.model, self.served = IdealReader(CASES[CASE]), "ideal", 0

        def content_hash(self, material):
            return self._reader.content_hash(material)

        def call(self, prompt, **kw):
            result = self._reader.call(prompt, **kw)
            if identify_site(prompt) == "expert" and _serves(prompt, KEY):
                self.served += 1
                if self.served == 1:
                    answer = m.mutate(copy.deepcopy(result.parsed), prompt)
                    return dataclasses.replace(result, parsed=answer, raw=json.dumps(answer))
            return result
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(file_engine, "read_file_engine",
                   lambda conn, org_id, work, lifecycle, **kw: file_engine.FileEngineParts(route_key="none"))
        run = run_case(CASES[CASE], _Reader(), keep=True)
    engine = routes._graph.engine
    try:
        with engine.connect() as c:
            rows = [r.checked for r in c.execute(text(
                "select r.checked from expert_reviews r join graph_nodes n on n.org_id = r.org_id "
                " and n.node_id = r.file_id and n.valid_to is null "
                "where r.org_id = :o and n.canonical_key = :k order by r.reviewed_at"), {"o": run.org_id, "k": KEY})]
    finally:
        remove_tenant(engine, run.org_id)
    checked = CheckedReview.from_mapping(rows[0])
    assert {(v.line, v.reason) for v in checked.dropped} == {("fact:6", UNKNOWN_EVIDENCE)}, checked.as_mapping()["verdicts"]
    assert checked.fate == SHOWN
