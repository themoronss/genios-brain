"""Composio's current (V3) webhook deliveries: the signature, the envelope, and which connection
a delivery belongs to. Before this every real delivery was refused (hex-over-body signature check)
or unroutable (identity read from the top level instead of `metadata`)."""
import base64
import hashlib
import hmac

from genios_engine.capture.connectors.composio_push import parse_push, pick_connection
from genios_engine.contracts.connection import Connection
from genios_engine.platform.auth import verify_standard_webhook, verify_webhook_hmac

SECRET = "composio_test_secret"
TS = "1700000000"


def _sign(body: bytes, wid: str = "msg_1", ts: str = TS, secret: str = SECRET) -> str:
    """What Composio sends (the SDK's `_verify_webhook_signature`, run in reverse)."""
    digest = hmac.new(secret.encode(), f"{wid}.{ts}.".encode() + body, hashlib.sha256).digest()
    return "v1," + base64.b64encode(digest).decode()


def _ok(body: bytes, sig: str, *, now: int = int(TS) + 5, secret: str = SECRET) -> bool:
    return verify_standard_webhook(body, webhook_id="msg_1", timestamp=TS, signature=sig,
                                   secret=secret, now=now)


def test_a_delivery_signed_the_way_composio_signs_it_verifies():
    body = b'{"type":"composio.trigger.message"}'
    assert _ok(body, _sign(body))


def test_the_old_body_only_check_refuses_a_real_composio_signature():
    """Why every real delivery used to 401."""
    body = b'{"type":"composio.trigger.message"}'
    assert not verify_webhook_hmac(body, _sign(body), SECRET)


def test_a_tampered_body_or_wrong_secret_is_refused():
    body = b'{"a":1}'
    assert not _ok(b'{"a":2}', _sign(body))
    assert not _ok(body, _sign(body), secret="another")


def test_a_replayed_delivery_outside_the_window_is_refused_even_when_signed():
    body = b'{"a":1}'
    assert not _ok(body, _sign(body), now=int(TS) + 301)


def test_any_of_several_signatures_in_the_header_may_match():
    body = b'{"a":1}'
    assert _ok(body, "v1,bm90LWl0 " + _sign(body))


def test_missing_headers_are_refused():
    assert not verify_standard_webhook(b"{}", webhook_id=None, timestamp=TS, signature="v1,x",
                                       secret=SECRET)


def _v3(slug: str, data: dict | None = None, kind: str = "composio.trigger.message") -> dict:
    return {"id": "msg_1", "type": kind, "data": data or {"messageId": "m1"},
            "metadata": {"trigger_slug": slug, "user_id": "org_1",
                         "connected_account_id": "ca_1"}}


def test_a_v3_trigger_names_its_owner_and_its_source_from_metadata():
    push = parse_push(_v3("GMAIL_NEW_GMAIL_MESSAGE"))
    assert (push.user_id, push.source_type, push.data, push.skip_reason) == \
        ("org_1", "gmail", {"messageId": "m1"}, None)
    assert parse_push(_v3("GOOGLECALENDAR_EVENT_CREATED_TRIGGER")).source_type == "gcal"


def test_a_v3_event_that_is_not_a_trigger_is_acknowledged_not_ingested():
    push = parse_push(_v3("", kind="composio.connected_account.expired"))
    assert push.skip_reason and push.user_id is None


def test_a_v3_trigger_for_a_toolkit_with_no_ingest_lane_is_skipped_not_guessed():
    assert parse_push(_v3("SLACK_RECEIVE_MESSAGE")).skip_reason


def test_the_legacy_envelope_still_parses():
    push = parse_push({"user_id": "org_1", "data": {"message": {"messageId": "m1"}}})
    assert (push.user_id, push.source_type) == ("org_1", None)
    assert push.data == {"message": {"messageId": "m1"}}


def test_a_gmail_push_reaches_the_gmail_connection_when_calendar_shares_the_org_label():
    """`composio_user_id` is the org's label, so both connections carry it."""
    cal = Connection(org_id="org_1", composio_user_id="org_1", source_type="gcal")
    mail = Connection(org_id="org_1", composio_user_id="org_1", source_type="gmail")
    assert pick_connection([cal, mail], parse_push(_v3("GMAIL_NEW_GMAIL_MESSAGE"))) is mail
    assert pick_connection([cal, mail],
                           parse_push(_v3("GOOGLECALENDAR_EVENT_CREATED_TRIGGER"))) is cal


def test_a_push_for_an_org_with_no_such_connection_matches_nothing():
    cal = Connection(org_id="org_1", composio_user_id="org_1", source_type="gcal")
    assert pick_connection([cal], parse_push(_v3("GMAIL_NEW_GMAIL_MESSAGE"))) is None
