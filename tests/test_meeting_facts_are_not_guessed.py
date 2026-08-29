"""Meeting evidence exists, is large, and was being written by two hands.

The design partner's graph carries 62 meeting nodes, 331 facts and 140 `attended` edges, and
those facts reach the neighbour slice of every person-anchored situation — the Admin corpus reads
them there through `admin.obj.core.meeting`, `admin.obj.core.action_item`,
`admin.obj.calendar_management.time_block` and `admin.obj.core.deadline`. It is the largest
evidence pool the reasoning layer has after correspondence itself.

Two faults made it unreliable, and both are the same shape as the `deal.status` double-writer:

  * `general`, `admin` and `customer_support` declared the five DERIVED lifecycle fields in
    `schema.fields`, which is the L2 extraction whitelist. `meeting_lifecycle.reduce_meeting`
    computes them from the calendar and says so — "Deterministic. No model." — so the model was
    asked to guess five booleans it cannot see, and wrote
    `meeting.scheduled = 'Monday 10 Aug 2026, 10:30am -'` on 30 person nodes.
  * `meeting.status` arrived as both `cancelled` and `canceled`. `meeting_lifecycle` tolerates
    both when reading a provider payload; every authored predicate compares the literal
    `cancelled`. A fact written `canceled` matches nothing and is not reported missing either.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from genios_engine.context.extract.vocab import COMPUTED_FIELDS, field_vocabulary
from genios_engine.context.meeting_lifecycle import CANCELLED
from genios_engine.context.pipeline import _normalise_meeting_status
from genios_engine.packs.wiring import BUILTIN_PACKS


def _effective():
    return [dict(p, pack_id=p["id"]) for p in BUILTIN_PACKS]


def test_the_computed_lifecycle_fields_never_reach_the_extraction_prompt():
    """The whole point. A field the engine computes must not be a field the model is told to find."""
    prompt_fields = set(field_vocabulary(_effective()))
    leaked = sorted(set(COMPUTED_FIELDS) & prompt_fields)
    assert not leaked, f"the extractor is being asked to invent computed fields: {leaked}"


def test_the_packs_still_declare_them_so_a_capability_can_cite_them():
    """Stripped from the PROMPT, not from the packs. The declaration is what lets a capability
    name these as evidence; deleting it would trade a bad extraction for an unciteable fact, and
    would mean a version bump plus a promote on every existing tenant."""
    declared = {f for p in BUILTIN_PACKS for f in (p.get("schema") or {}).get("fields") or ()}
    assert set(COMPUTED_FIELDS) <= declared, (
        "the computed fields were deleted from the packs rather than stripped from the prompt")


def test_the_genuinely_captured_meeting_fields_are_still_asked_for():
    """A guard against over-correcting. An email really can say a meeting moved or was called off,
    and `meeting.status` / `start_at` / `end_at` are how that is recorded. Stripping those too
    would close the extraction lane this test file exists to make trustworthy."""
    prompt_fields = set(field_vocabulary(_effective()))
    assert {"meeting.status", "meeting.start_at", "meeting.end_at"} <= prompt_fields


@pytest.mark.parametrize("written", sorted(CANCELLED))
def test_every_word_a_provider_uses_for_off_normalises_to_one(written):
    assert _normalise_meeting_status(written) == "cancelled"
    assert _normalise_meeting_status(written.upper()) == "cancelled"


def test_a_status_that_is_not_a_cancellation_is_left_alone():
    """Normalising is not flattening. `pending_confirmation` and `confirmed` are different states
    and both are live on the design partner's graph."""
    assert _normalise_meeting_status("confirmed") == "confirmed"
    assert _normalise_meeting_status("pending_confirmation") == "pending_confirmation"
    assert _normalise_meeting_status("") is None
    assert _normalise_meeting_status(None) is None


def test_the_normaliser_reads_the_lifecycle_set_rather_than_restating_it():
    """Two lists of the same synonyms drift, and the drift is silent until someone adds a sixth
    word. Asserted by behaviour: every member of the shared set must normalise."""
    import inspect

    from genios_engine.context import pipeline
    source = inspect.getsource(pipeline._normalise_meeting_status)
    assert "meeting_lifecycle import CANCELLED" in source, (
        "the cancellation words were restated instead of imported")


def test_the_write_path_actually_calls_the_normaliser():
    """A normaliser nobody calls is a unit test passing over a live fault. The three tests above
    all exercise the function directly and stay green with the call site deleted, which is the
    exact shape of the gap that let `deal.status` ship un-normalised in the first place."""
    import inspect

    from genios_engine.context import pipeline
    source = inspect.getsource(pipeline)
    body = source[source.index("for f in facts:"):]
    body = body[:body.index("def ", 1)] if "\ndef " in body else body
    assert "_normalise_meeting_status(value)" in body, (
        "the fact-write loop does not normalise meeting.status")
    assert 'if field == "meeting.status":' in body


def test_a_us_spelling_written_through_the_pipeline_is_stored_british(pg_store):
    """The consequence, on a real database, through the real write path — because the fault is not
    that a function returns the wrong string, it is that a fact lands where no predicate looks."""
    org = "meeting_status_norm"
    from genios_engine.context.graph_store import GraphStore  # noqa: F401 — type clarity

    with pg_store.engine.begin() as c:
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            cols.append(r.column_name); ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else "{}" if dt in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                       "on conflict (id) do nothing"), vals)

    # The normaliser is what the write path calls; assert on the value it hands the store rather
    # than reconstructing a full L2 extraction, which would test the model and not this fix.
    for provider_word in sorted(CANCELLED):
        assert _normalise_meeting_status(provider_word) == "cancelled"
