"""FROZEN dedup_key golden values. A changed key silently re-lands the entire corpus as
brand-new events — full LLM re-extraction spend, duplicated facts and observations across
every tenant — and there is no way to recover because dedup is the only defence. If this
test goes red you are about to ship that; change requires a deliberate migration plan,
never an edit here."""
from __future__ import annotations

from genios_engine.contracts.source_event import compute_dedup_key

GOLDEN = [
    # (source, object_type, source_object_id, content_version) -> frozen key
    (("gmail", "email", "18c4a9e2f7", None), "gmail:email:18c4a9e2f7"),
    (("gmail", "email", "18c4a9e2f7", ""), "gmail:email:18c4a9e2f7"),       # empty == None
    (("gcal", "event", "evt_91", "2026-07-22T10:00:00Z"),
     "gcal:event:evt_91:2026-07-22T10:00:00Z"),                             # mutable object
    (("notion", "page", "pg_1", None), "notion:page:pg_1"),
    (("hubspot", "deal", "223", "1722600000"), "hubspot:deal:223:1722600000"),
    (("database", "row", "deals:42", "wm_2026-08-01"), "database:row:deals:42:wm_2026-08-01"),
    (("upload", "document_chunk", "up_9:3", None), "upload:document_chunk:up_9:3"),
    (("human", "note", "hev_1", None), "human:note:hev_1"),
    (("agent", "action", "aev_7", None), "agent:action:aev_7"),
]


def test_dedup_keys_are_frozen():
    for args, expected in GOLDEN:
        assert compute_dedup_key(*args) == expected, (
            f"dedup_key for {args} changed — this re-lands the whole corpus; "
            "see the module docstring before touching anything")


def test_version_change_yields_new_key_unversioned_does_not():
    a = compute_dedup_key("gcal", "event", "e1", "v1")
    b = compute_dedup_key("gcal", "event", "e1", "v2")
    c = compute_dedup_key("gmail", "email", "m1")
    d = compute_dedup_key("gmail", "email", "m1")
    assert a != b          # a genuine edit re-lands
    assert c == d          # an immutable object never re-lands
