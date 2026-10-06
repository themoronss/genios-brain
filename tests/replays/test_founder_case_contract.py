"""STEP-01 · the founder case is a type with rules, and an empty set fails.

    pytest tests/replays/test_founder_case_contract.py -q

The founder set is the second exam (`speedrun008/YC-II W27/` STEP-01 §1). Its cases are synthetic —
invented names and text, modelled on the real items by sender and date only — and each one is judged
against the real chain. These tests hold the contract the cases are written against, on cases built
here, so the rules are proven before a single case is authored:

  * a must-abstain case carries a WITNESS. Today nothing gets a card, so an abstain case without
    one would pass on nothing — the "a pass over an empty table is not a pass" defect;
  * what the engine cannot express yet (workstream, stage, lane, the brief) is DECLARED with its
    reason, never silently skipped and never counted as a pass;
  * no real person or organisation from the founder's mailbox appears anywhere in a case;
  * an empty or missing set is an error, never "0 cases passed".
"""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone

import pytest

from tests.replays import founder_case as fc
from tests.replays.harness import load_specs


def _case(**overrides) -> dict:
    """The smallest valid must-detect case. Every test mutates one rule out of it."""
    case = {
        "case_id": "F90",
        "title": "An investor asks for the deck before a partner meeting",
        "kind": "must_detect",
        "label_row": 10,
        "labelled_by": "claude",
        "replays": [],
        "founder": {"name": "Arjun Rao", "email": "arjun@nimbuslabs.test",
                    "company": "Nimbus Labs", "timezone": "Asia/Kolkata"},
        "sweeps": ["2026-09-18T12:00:00Z"],
        "objects": [{
            "id": "ask", "source": "gmail", "sweep": 0,
            "occurred_at": "2026-09-18T09:30:00Z",
            "from": "Kavya Menon <kavya@lotusvc.test>", "to": ["arjun@nimbuslabs.test"],
            "thread": "t-lotus", "subject": "Deck before Monday?",
            "body": "Hi Arjun, could you send the latest deck before our partners meet on Monday?",
            "labels": ["INBOX", "IMPORTANT"],
        }],
        "expected": {
            "gate": {"ask": "emitted"},
            "memory": {"ask": True},
            "cards": [{"about": ["Kavya", "Lotus"], "min": 1, "max": 1,
                       "mentions": ["deck"]}],
            "workstream": "investor",
            "lane": "decision",
        },
        "forbidden": {"names": [], "phrases": ["last chance"]},
        "witness": None,
        "not_expressible": {
            "workstream": "STEP-09 — the engine forms no workstream yet",
            "lane": "F10 — cards.output_lane is written NULL",
        },
    }
    case.update(overrides)
    return case


def _abstain(**overrides) -> dict:
    case = _case(case_id="F91", kind="must_abstain",
                 title="A program newsletter is archived, never a card")
    case["expected"] = {"gate": {"ask": "dropped"},
                        "cards": [{"about": ["Lotus"], "min": 0, "max": 0}]}
    case["not_expressible"] = {}
    case["witness"] = {"stage": "gate", "objects": ["ask"]}
    case.update(overrides)
    return case


def _parse(case: dict) -> fc.FounderCase:
    return fc.parse_case(copy.deepcopy(case), source="test.json")


# =================================================================================================
# 1 · a valid case parses into the shape the runner and the marking read
# =================================================================================================
def test_a_valid_case_parses_with_its_instants_objects_and_expectations():
    case = _parse(_case())
    assert case.case_id == "F90" and case.kind == "must_detect"
    assert case.sweeps == (datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc),)
    (obj,) = case.objects
    assert obj.object_id == "ask" and obj.source == "gmail" and obj.sweep == 0
    assert obj.sender_email == "kavya@lotusvc.test"
    assert case.expected_gate == {"ask": "emitted"} and case.expected_memory == {"ask": True}
    (card,) = case.cards
    assert card.min == 1 and card.max == 1 and card.about == ("Kavya", "Lotus")
    assert card.mentions == ("deck",)
    assert case.expressible("cards") and case.expressible("gate")
    assert not case.expressible("workstream") and not case.expressible("lane")
    assert "STEP-09" in case.not_expressible["workstream"]


def test_a_gmail_object_becomes_the_message_the_provider_would_return():
    """The runner hands the REAL connector mapping a provider-shaped message, so the header class —
    labels, List-Unsubscribe, the attachment parts — is read by production code, not re-typed."""
    raw = _case()
    raw["objects"][0]["headers"] = {"List-Unsubscribe": "<mailto:u@lotusvc.test>"}
    raw["objects"][0]["attachments"] = [{"filename": "deck.pdf", "mime": "application/pdf",
                                         "fetch": "refused"}]
    message = _parse(raw).objects[0].provider_message()
    headers = {h["name"]: h["value"] for h in message["payload"]["headers"]}
    assert headers["From"] == "Kavya Menon <kavya@lotusvc.test>"
    assert headers["To"] == "arjun@nimbuslabs.test" and headers["Subject"] == "Deck before Monday?"
    assert headers["List-Unsubscribe"] == "<mailto:u@lotusvc.test>"
    assert message["labelIds"] == ["INBOX", "IMPORTANT"] and message["threadId"] == "t-lotus"
    parts = message["payload"]["parts"]
    assert parts[0]["mimeType"] == "text/plain"
    assert parts[1]["filename"] == "deck.pdf" and parts[1]["body"]["attachmentId"]
    assert message["messageTimestamp"] == "2026-09-18T09:30:00+00:00"


def test_a_calendar_object_becomes_the_event_the_provider_would_return():
    raw = _case()
    raw["objects"].append({
        "id": "call", "source": "gcal", "sweep": 0, "occurred_at": "2026-09-18T10:00:00Z",
        "summary": "Nimbus x Lotus", "start": "2026-09-22T10:00:00Z",
        "end": "2026-09-22T10:30:00Z", "organizer": "kavya@lotusvc.test",
        "attendees": ["kavya@lotusvc.test", "arjun@nimbuslabs.test"]})
    event = _parse(raw).objects[1].provider_event()
    assert event["summary"] == "Nimbus x Lotus"
    assert event["start"] == {"dateTime": "2026-09-22T10:00:00Z"}
    assert {a["email"] for a in event["attendees"]} == {"kavya@lotusvc.test",
                                                        "arjun@nimbuslabs.test"}
    assert any(a.get("self") for a in event["attendees"]), "the founder's own entry is `self`"


# =================================================================================================
# 2 · the rules a case is written against
# =================================================================================================
def test_a_must_abstain_case_without_a_witness_is_refused():
    with pytest.raises(fc.CaseError, match="witness"):
        _parse(_abstain(witness=None))


def test_a_must_abstain_case_with_a_witness_parses():
    case = _parse(_abstain())
    assert case.witness.stage == "gate" and case.witness.objects == ("ask",)
    assert case.cards[0].max == 0


def test_a_witness_names_a_stage_the_runner_reports():
    with pytest.raises(fc.CaseError, match="stage"):
        _parse(_abstain(witness={"stage": "vibes", "objects": ["ask"]}))


def test_a_must_detect_case_expects_at_least_one_card():
    raw = _case()
    raw["expected"]["cards"][0]["min"] = 0
    with pytest.raises(fc.CaseError, match="must_detect"):
        _parse(raw)


def test_what_the_engine_cannot_express_must_be_declared_with_its_reason():
    raw = _case()
    del raw["not_expressible"]["workstream"]
    with pytest.raises(fc.CaseError, match="workstream"):
        _parse(raw)


def test_a_declared_gap_needs_a_reason():
    raw = _case()
    raw["not_expressible"]["lane"] = "  "
    with pytest.raises(fc.CaseError, match="reason"):
        _parse(raw)


@pytest.mark.parametrize("where", ["body", "subject", "from", "title", "forbidden"])
def test_no_real_name_from_the_mailbox_appears_anywhere(where):
    raw = _case()
    real = sorted(fc.REAL_NAMES)[0]
    if where == "body":
        raw["objects"][0]["body"] += f" Regards from {real.title()}."
    elif where == "subject":
        raw["objects"][0]["subject"] = f"Re: {real}"
    elif where == "from":
        raw["objects"][0]["from"] = f"Someone <x@{real.lower().replace(' ', '')}.com>"
    elif where == "title":
        raw["title"] = f"About {real}"
    else:
        raw["forbidden"]["names"] = [real]
    with pytest.raises(fc.CaseError, match="real name"):
        _parse(raw)


def test_the_deny_list_matches_whole_words_not_fragments():
    """`Sal` is on the list; `salary` and `Salesforce` are not that person."""
    raw = _case()
    raw["objects"][0]["body"] += " The salary band is attached."
    assert "sal" in {n.lower() for n in fc.REAL_NAMES}
    _parse(raw)


def test_an_expectation_must_name_an_object_of_the_case():
    raw = _case()
    raw["expected"]["memory"] = {"nope": True}
    with pytest.raises(fc.CaseError, match="nope"):
        _parse(raw)


def test_an_object_cannot_land_after_the_sweep_that_reads_it():
    raw = _case()
    raw["objects"][0]["occurred_at"] = "2026-09-18T12:00:01Z"
    with pytest.raises(fc.CaseError, match="after"):
        _parse(raw)


def test_sweeps_are_ordered_and_timezone_aware():
    with pytest.raises(fc.CaseError, match="order"):
        _parse(_case(sweeps=["2026-09-18T12:00:00Z", "2026-09-17T12:00:00Z"]))
    with pytest.raises(fc.CaseError, match="timezone"):
        _parse(_case(sweeps=["2026-09-18T12:00:00"]))


def test_who_labelled_it_is_one_of_two():
    with pytest.raises(fc.CaseError, match="labelled_by"):
        _parse(_case(labelled_by="intern"))


def test_an_unknown_key_is_a_typo_not_an_extension():
    with pytest.raises(fc.CaseError, match="expectd"):
        _parse(_case(expectd={}))


def test_a_gate_expectation_uses_the_capture_vocabulary():
    raw = _case()
    raw["expected"]["gate"] = {"ask": "kept"}
    with pytest.raises(fc.CaseError, match="kept"):
        _parse(raw)


def test_a_case_can_expect_a_mail_archived_with_its_rule():
    """STEP-03 (`yc2_w27_s03/M21.C5.L-contract.V0.U01`): the gate archives what it used to drop — kept,
    read by no model — so a case can say exactly that, with the rule (`archived:N-02`)."""
    raw = _case()
    raw["expected"]["gate"] = {"ask": "archived:N-02"}
    assert _parse(raw).expected_gate == {"ask": "archived:N-02"}
    assert "archived" in fc.GATE_OUTCOMES


# =================================================================================================
# 3 · the set: its own folder, never read by the Atlas loader, and never empty
# =================================================================================================
def test_an_empty_set_is_an_error_not_zero_cases(tmp_path):
    with pytest.raises(AssertionError, match="no founder cases"):
        fc.load_cases(tmp_path)


def test_a_missing_set_is_an_error(tmp_path):
    with pytest.raises(AssertionError, match="missing"):
        fc.load_cases(tmp_path / "absent")


def test_two_files_cannot_claim_one_case_id(tmp_path):
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_text(json.dumps(_case()))
    with pytest.raises(fc.CaseError, match="F90"):
        fc.load_cases(tmp_path)


def test_the_loader_reads_a_folder_of_cases_in_id_order(tmp_path):
    (tmp_path / "z.json").write_text(json.dumps(_case()))
    (tmp_path / "a.json").write_text(json.dumps(_abstain()))
    assert [c.case_id for c in fc.load_cases(tmp_path)] == ["F90", "F91"]


def test_the_founder_folder_is_not_read_by_the_atlas_loader():
    """`load_specs` globs one level; the founder set lives one level down, so the twelve Atlas
    replays stay exactly twelve however many founder cases are added."""
    assert fc.FOUNDER_DIR.parent.name == "specs"
    assert all(s.source and "/" not in s.source for s in load_specs())
    assert len(load_specs()) == 12


def test_a_known_gap_is_named_in_a_sentence():
    assert _parse(_case(blocked_on="F04 — a meeting becomes a deadline that expires")).blocked_on
    with pytest.raises(fc.CaseError, match="blocked_on"):
        _parse(_case(blocked_on="todo"))
