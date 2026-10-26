"""G012 H-26 · block F carries what the file's own mailboxes read — the absence rule reads block F alone.

    pytest tests/reason/l2/test_block_f_says_what_the_files_mailbox_read.py -q

On the design partner's org (local copy, 25 Oct) 64 file judgments said "find out" — 48 on files where block F said
"No source said how much of it was read: a negative claim is not licensed" — while block D's WHAT WAS CHECKED could
already say the mailbox read past our last mail, and the founder's own cards say "Gmail fully read — no reply".
"""
from __future__ import annotations

import inspect
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.context.coverage_receipt import MailboxReceipt
from genios_engine.reason.l2 import dossier as D
from genios_engine.reason.l2 import sweep

pytestmark = pytest.mark.unit

AT = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)
SENT = datetime(2026, 8, 26, 10, 20, tzinfo=timezone.utc)
MAILBOX = MailboxReceipt(connection_id="con_gmail", address=None, window_days=180,
                         window_start=datetime(2026, 4, 27, tzinfo=timezone.utc), last_finished_at=AT,
                         last_completed=True)


def _parts(*, mailboxes=(MAILBOX,), since=SENT, covered=True):
    return SimpleNamespace(numbers=SimpleNamespace(mailboxes=mailboxes, no_reply_since=since,
                                                   no_reply_can_be_said=covered))


def test_a_mailbox_that_read_past_our_last_mail_licenses_no_reply_in_block_f():
    reads = D.file_reads(_parts())
    assert "reads 180 days back" in reads[0] and "last sync completed" in reads[0]
    assert "may be said of this file" in reads[1]
    block = D._coverage(SimpleNamespace(coverage=(), unresolved=()), SimpleNamespace(truncated=False), None, reads)
    assert "is not licensed" not in block and "may be said of this file" in block


def test_no_mailbox_or_no_completed_read_licenses_nothing():
    assert D.file_reads(_parts(mailboxes=())) == ()
    assert any("may NOT be said" in r for r in D.file_reads(_parts(covered=False)))
    block = D._coverage(SimpleNamespace(coverage=(), unresolved=()), SimpleNamespace(truncated=False), None, ())
    assert "is not licensed" in block


def test_the_pass_hands_each_file_judgment_its_files_reads():
    assert "reads=file_reads(parts) if parts is not None else ()" in inspect.getsource(sweep.l2_pass)
    assert D.L2_DOSSIER_VERSION == "l2-dossier.v6"
