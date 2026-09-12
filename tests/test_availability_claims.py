"""Availability claims: strict validation and deterministic date resolution.

The model quotes words; the dates are computed here against the MESSAGE date. A stated phrase we
cannot read drops the claim; a date is never invented."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from genios_engine.context.extract.availability import (resolve_window,
                                                         validate_availability_claims)
from genios_engine.context.extract.extractor import build_prompt, extract
from genios_engine.context.pipeline import (EXTRACTION_SCHEMA_VERSION, PROMPT_VERSION,
                                            _from_cache, _names_sender, _to_cache)
from genios_engine.contracts.availability import AvailabilityClaim, normalize_kind

BASE = date(2026, 9, 10)                       # a Thursday
MSG_AT = datetime(2026, 9, 10, 9, 30, tzinfo=timezone.utc)


# ── date resolution ─────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("from_text,to_text,start,end", [
    ("15th", "22nd", date(2026, 9, 15), date(2026, 9, 22)),
    ("15-22 Sept", None, date(2026, 9, 15), date(2026, 9, 22)),
    ("Sept 15-22", None, date(2026, 9, 15), date(2026, 9, 22)),
    ("15th Sept to 22nd Sept", None, date(2026, 9, 15), date(2026, 9, 22)),
    ("15/09", "22/09", date(2026, 9, 15), date(2026, 9, 22)),       # day first (India)
    ("2026-09-15", "2026-09-22", date(2026, 9, 15), date(2026, 9, 22)),
    ("28 Dec", "3 Jan", date(2026, 12, 28), date(2027, 1, 3)),      # crosses the year
    ("next week", None, date(2026, 9, 14), date(2026, 9, 18)),       # Mon–Fri of next week
    ("this week", None, date(2026, 9, 10), date(2026, 9, 11)),
    ("Mon to Wed", None, date(2026, 9, 14), date(2026, 9, 16)),
    ("today", None, BASE, BASE),                                     # "sick today" = one day
    ("tomorrow", "Friday", date(2026, 9, 11), date(2026, 9, 11)),    # Friday IS tomorrow
    ("for 2 weeks", None, BASE, date(2026, 9, 23)),
])
def test_explicit_and_relative_ranges(from_text, to_text, start, end):
    w = resolve_window(from_text, to_text, BASE)
    assert (w.start, w.end) == (start, end)


@pytest.mark.parametrize("from_text,to_text", [("kal se 3 din", None), ("kal se", "3 din")])
def test_hinglish_kal_se_3_din(from_text, to_text):
    w = resolve_window(from_text, to_text, BASE)
    assert (w.start, w.end) == (date(2026, 9, 11), date(2026, 9, 13))


def test_hinglish_range_se_tak():
    w = resolve_window("15 se 22 tak", None, BASE)
    assert (w.start, w.end) == (date(2026, 9, 15), date(2026, 9, 22))


def test_back_on_monday_ends_the_day_before():
    w = resolve_window(None, "back on Monday", BASE)
    assert (w.start, w.end) == (BASE, date(2026, 9, 13))
    assert w.from_stated is False and w.to_stated is True


def test_open_start_is_open_ended():
    w = resolve_window("from next week", None, BASE)
    assert w.start == date(2026, 9, 14) and w.end is None


def test_no_dates_at_all_defaults_start_to_message_date_open_ended():
    w = resolve_window(None, None, BASE)
    assert (w.start, w.end, w.from_stated) == (BASE, None, False)


def test_unreadable_stated_phrase_is_malformed():
    assert resolve_window("blorp", None, BASE) is None
    assert resolve_window(None, "whenever", BASE) is None


def test_end_before_start_is_malformed():
    assert resolve_window("22nd", "2026-09-15", BASE) is None


# ── claim validation ────────────────────────────────────────────────────────────────────────

CONTENT = ("Out of Office\n\nI am on leave from 15th to 22nd September. "
           "For the audit please reach Priya (priya@acme.io). kal se 3 din chutti for Ravi.")


def _claim(**kw):
    base = {"person": "sender", "kind": "leave", "from": "from 15th", "to": "22nd September",
            "coverage_person": "priya@acme.io",
            "evidence_text": "I am on leave from 15th to 22nd September"}
    base.update(kw)
    return base


def test_valid_claim_resolves_against_message_date():
    [c] = validate_availability_claims([_claim()], content=CONTENT, base=MSG_AT)
    assert c == AvailabilityClaim(person=None, kind="leave", from_date=date(2026, 9, 15),
                                  to_date=date(2026, 9, 22), coverage_person="priya@acme.io",
                                  evidence="I am on leave from 15th to 22nd September",
                                  from_stated=True, to_stated=True)
    assert c.value() == {"kind": "leave", "from": "2026-09-15", "to": "2026-09-22",
                         "cover": "priya@acme.io"}


def test_hinglish_claim_about_a_named_person():
    [c] = validate_availability_claims(
        [{"person": "Ravi", "kind": "chutti", "from": "kal se 3 din", "to": None,
          "evidence_text": "kal se 3 din chutti for Ravi"}], content=CONTENT, base=MSG_AT)
    assert (c.person, c.kind, c.from_date, c.to_date) == (
        "Ravi", "leave", date(2026, 9, 11), date(2026, 9, 13))


@pytest.mark.parametrize("bad", [
    {"evidence_text": "I will be on a beach"},                   # evidence not in the message
    {"kind": "sabbatical_of_the_soul"},                          # outside the closed vocabulary
    {"from": "the 45th of never"},                               # phrase not in the message
    {"from": 15},                                                # non-string date
    {"from": "2026-09-01"},                                      # ISO date the quote never states
])
def test_malformed_claims_are_dropped(bad):
    assert validate_availability_claims([_claim(**bad)], content=CONTENT, base=MSG_AT) == []


def test_model_resolved_iso_is_accepted_only_when_the_quote_corroborates_it():
    ok = validate_availability_claims([_claim(**{"from": "2026-09-15", "to": "2026-09-22"})],
                                      content=CONTENT, base=MSG_AT)
    assert ok and (ok[0].from_date, ok[0].to_date) == (date(2026, 9, 15), date(2026, 9, 22))


def test_no_date_ooo_is_open_ended_from_message_date():
    [c] = validate_availability_claims(
        [{"person": "sender", "kind": "out of office", "from": None, "to": None,
          "evidence_text": "Out of Office"}], content=CONTENT, base=MSG_AT)
    assert (c.kind, c.from_date, c.to_date, c.from_stated) == ("ooo", BASE, None, False)


def test_absurd_windows_are_dropped():
    content = "on leave from 2026-09-15 to 2028-09-15 on the 15th"
    assert validate_availability_claims(
        [{"kind": "leave", "from": "2026-09-15", "to": "2028-09-15",
          "evidence_text": "on leave from 2026-09-15 to 2028-09-15"}],
        content=content, base=MSG_AT) == []


def test_duplicates_collapse_and_non_lists_are_empty():
    assert len(validate_availability_claims([_claim(), _claim()], content=CONTENT,
                                            base=MSG_AT)) == 1
    assert validate_availability_claims(None, content=CONTENT, base=MSG_AT) == []
    assert validate_availability_claims({"kind": "leave"}, content=CONTENT, base=MSG_AT) == []


def test_kind_synonyms():
    assert normalize_kind("Out of Office") == "ooo"
    assert normalize_kind("vacation") == "leave"
    assert normalize_kind("unwell") == "sick"
    assert normalize_kind("half-day") == "partial"
    assert normalize_kind("wfh") is None


def test_names_sender_is_conservative():
    assert _names_sender("Anisha Sharma", "anisha.sharma@acme.io")
    assert _names_sender("Anisha", "anisha@acme.io")
    assert not _names_sender("Priya", "anisha@acme.io")
    assert not _names_sender("Anisha Sharma", "anisha@acme.io")


# ── extraction contract ─────────────────────────────────────────────────────────────────────

class _Res:
    ok, raw, input_tokens, output_tokens, error = True, "{}", 1, 1, None

    def __init__(self, parsed):
        self.parsed = parsed


class _LLM:
    model = "fake"

    def __init__(self, parsed):
        self.parsed = parsed

    def call(self, prompt, *, max_tokens=4096):
        return _Res(self.parsed)


def test_extractor_carries_availability_and_prompt_asks_for_it():
    ex = extract(_LLM({"relevance": 0.2, "availability": [_claim()]}), source="gmail",
                 content=CONTENT)
    assert ex.availability == [_claim()]
    prompt = build_prompt("slack", "hi")
    assert '"availability"' in prompt and "AVAILABILITY" in prompt
    assert "Never compute, convert or guess a" in prompt


def test_cache_round_trip_keeps_availability_and_key_versions_moved():
    ex = extract(_LLM({"availability": [_claim()]}), source="gmail", content=CONTENT)
    assert _from_cache(_to_cache(ex)).availability == [_claim()]
    assert PROMPT_VERSION == "b3-5" and EXTRACTION_SCHEMA_VERSION == "4"
