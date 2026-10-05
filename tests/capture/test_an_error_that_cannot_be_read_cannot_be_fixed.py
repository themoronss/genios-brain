"""A stored failure keeps the provider's REASON, not just its identifier.

    pytest tests/capture/test_an_error_that_cannot_be_read_cannot_be_fixed.py -q

⛔ WHY THIS FILE EXISTS. Measured on the design partner's org, 2026-10-04: 85 attachments parked
since 03 Oct — 11 PDFs, 20 PNGs, 7 JPEGs and 47 calendar parts — 50 of them already through three
retries. `refetch_last_error` was EXACTLY 400 characters on every single one, and 48 of the 50
read, in full:

    RuntimeError: gmail attachment fetch failed for 1a0c6f4b…::ANGjdJ-gga9K8OYi94uBeK9HJ1Lf…

and then stopped. No reason. The retry ladder was working perfectly, classifying every failure as
`transient`, scheduling the next attempt — and reporting nothing anybody could act on.

⛔ THE CAUSE IS THE ORDER, NOT THE SIZE. The connector's message is
`"gmail attachment fetch failed for {message_id}::{attachment_id}: {reason}"`, a Gmail attachment
id is ~350 characters on its own, and the store caps at 400. The identifier consumed the whole
budget and the reason — the only part that says what to do — was cut off every time. Raising the
cap would have stored more identifier.

So the reason goes FIRST in the budget and the identifier is elided in the middle. Nothing is lost
that was not already recorded: `event_id` on the same row addresses the event exactly.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.parked.refetch import (
    ERROR_CAP,
    REASON_BUDGET,
    _readable_failure,
)

pytestmark = pytest.mark.unit

#: A real Gmail attachment id from the parked rows — this length is the whole problem.
_GMAIL_ID = "ANGjdJ-gga9K8OYi94uBeK9HJ1LfsSC0v5ldgmLXpoAR4MGnOVaY2HZtHqhaGaFpaunqfIyHTz1IiK5z" * 5
_REASON = "Invalid request: attachment not found or expired for this message"
_REAL = f"RuntimeError: gmail attachment fetch failed for 1a0c6f4b::{_GMAIL_ID}: {_REASON}"


def test_the_reason_survives_the_cap():
    """⛔ THE MUTATION THIS FILE REJECTS: going back to a head truncation. Fifty stored failures
    become unreadable again and the attachments stay stuck with nobody able to say why."""
    assert len(_REAL) > ERROR_CAP, "the fixture must exceed the cap or this proves nothing"
    stored = _readable_failure(_REAL)
    assert _REASON in stored, (
        "the provider's reason was cut off again — the identifier ate the budget, which is "
        "exactly the state that left 85 attachments stuck and undiagnosable")


def test_it_still_fits_the_column():
    assert len(_readable_failure(_REAL)) <= ERROR_CAP


def test_the_identifier_is_elided_not_dropped():
    """The id is still useful to a person holding a Gmail console; it just may not cost the
    reason. Both ends are kept so a human can recognise it."""
    stored = _readable_failure(_REAL)
    assert "…" in stored or "<id elided>" in stored
    assert "1a0c6f4b" in stored, "the message id is short and must survive intact"


def test_a_short_message_is_untouched():
    """The common path: most failures are already well under the cap and must pass through byte
    for byte, or every existing error string silently changes shape."""
    short = "RuntimeError: gmail attachment fetch failed for abc::def: quota exceeded"
    assert _readable_failure(short) == short


def test_a_message_with_no_reason_is_not_mangled():
    """Some failures genuinely carry no detail. There is nothing to protect, so the old behaviour
    stands rather than inventing structure that is not there."""
    bare = "RuntimeError: gmail attachment fetch failed for " + _GMAIL_ID
    out = _readable_failure(bare)
    assert out == bare[:ERROR_CAP]


def test_a_message_in_an_unknown_shape_is_not_mangled():
    """A failure from somewhere other than the attachment fetcher must not be reshaped by a rule
    written for one connector's sentence."""
    other = "ConnectionError: " + ("x" * 500)
    assert _readable_failure(other) == other[:ERROR_CAP]


def test_a_very_long_reason_is_still_allowed_its_share():
    """A reason longer than its budget is kept to the budget — the point is that it is PRESENT,
    not that it is complete."""
    long_reason = "Invalid request: " + ("detail " * 200)
    stored = _readable_failure(
        f"RuntimeError: gmail attachment fetch failed for m::{_GMAIL_ID}: {long_reason}")
    assert "Invalid request:" in stored
    assert len(stored) <= ERROR_CAP
    assert REASON_BUDGET <= ERROR_CAP


def test_the_writer_actually_uses_it():
    """⛔ THE MUTATION EVERY TEST ABOVE MISSES, AND THE REASON THIS ONE IS ON THE AST.

    Every assertion above calls `_readable_failure` directly. Restoring `error=message[:400]` at
    `_failed`'s call site therefore leaves them all green while putting the whole defect back —
    verified by doing exactly that: 7 passed. A test that cannot fail on the change it exists to
    prevent is decoration, and this is the third time in this session that a helper-only test has
    let its own call site rot.
    """
    import ast
    import inspect
    import textwrap

    from genios_engine.capture.parked import refetch

    tree = ast.parse(textwrap.dedent(inspect.getsource(refetch._failed)))
    error_kw = next((kw for node in ast.walk(tree)
                     if isinstance(node, ast.Call)
                     for kw in node.keywords if kw.arg == "error"), None)
    assert error_kw is not None, "_failed no longer passes an `error=` — re-point this test"

    called = {c.func.id for c in ast.walk(error_kw.value)
              if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "_readable_failure" in called, (
        "_failed stores the raw message again; a Gmail attachment id is ~350 characters and the "
        "column holds 400, so the provider's reason is cut off and 85 parked attachments go back "
        "to being undiagnosable")
    assert not any(isinstance(n, ast.Subscript) for n in ast.walk(error_kw.value)), (
        "a bare slice is back on the error path — that is the head truncation this file removed")
