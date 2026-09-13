"""P2 §3.1 — screen session rendering (pure) and the screen relevance gate slot."""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import genios_engine.capture.screen.relevance as REL
import genios_engine.capture.screen.render as R

SEAT = "rohit@acme.test"
RECEIVED = datetime(2026, 9, 17, 5, 0, tzinfo=timezone.utc)


def _li(messages, context=None, **extra):
    return {"session_key": "li:conv:abc:2026-09-17T10", "thread_key": "li:conv:abc",
            "app": "linkedin", "title": "Priya Shah",
            "participants": [{"name": "Priya Shah",
                              "linkedin_url": "https://in.linkedin.com/in/PriyaShah/?trk=x#f"},
                             {"self": True, "name": "Rohit"}],
            "context_messages": context or [], "messages": messages,
            "url": "https://www.linkedin.com/messaging/thread/abc/", **extra}


def _msg(text, out=False, ts="2026-09-17T10:41:40+05:30", sender="Priya Shah"):
    return {"sender": "self" if out else sender, "ts": ts, "text": text, "is_outgoing": out}


def test_out_and_in_become_two_objects_with_their_own_actors():
    objs = R.render_session(_li([_msg("I'll send the proposal by Friday", out=True),
                                 _msg("Great, thanks", ts="2026-09-17T10:45:00+05:30")]),
                            seat_email=SEAT, watermark=9, received_at=RECEIVED)
    assert [o.direction for o in objs] == ["out", "in"]
    out, inc = objs[0].raw, objs[1].raw
    assert out.source == "screen_session" and out.object_type == "screen_chat_thread"
    assert out.source_object_id == "li:conv:abc#9#out"
    assert inc.source_object_id == "li:conv:abc#9#in"
    assert out.content_version == "9" and out.raw["message_watermark"] == 9
    assert out.actor_email == SEAT and out.raw["labelIds"] == ["SENT"]
    assert out.raw["body"] == "Rohit: I'll send the proposal by Friday"
    assert "labelIds" not in inc.raw
    assert inc.raw["body"] == "Priya Shah: Great, thanks"
    assert inc.occurred_at == datetime(2026, 9, 17, 5, 15, tzinfo=timezone.utc)
    assert SEAT in inc.recipients
    assert out.visibility is None                     # the door sets it, not the renderer


def test_li_actor_is_the_normalised_profile_url():
    inc = R.render_session(_li([_msg("going with another vendor")]), seat_email=SEAT,
                           watermark=3, received_at=RECEIVED)[0].raw
    assert inc.actor_email == "li:https://www.linkedin.com/in/priyashah"
    assert inc.actor_name == "Priya Shah"


def test_email_counterparty_wins_over_li_and_none_when_unknown():
    s = _li([_msg("hi", sender="Ana Ruiz")], app="gmail")
    s["participants"] = [{"name": "Ana Ruiz", "email": "Ana@Vendor.test"},
                         {"name": "Bo", "linkedin_url": "https://linkedin.com/in/bo"},
                         {"self": True}]
    inc = R.render_session(s, seat_email=SEAT, watermark=1, received_at=RECEIVED)[0].raw
    assert inc.object_type == "screen_email_thread" and inc.actor_email == "ana@vendor.test"
    s["participants"] = [{"name": "X"}, {"name": "Y"}, {"self": True}]
    s["messages"] = [_msg("hi", sender="Zed")]
    assert R.render_session(s, seat_email=SEAT, watermark=1,
                            received_at=RECEIVED)[0].raw.actor_email is None


def test_context_is_quoted_under_its_header_after_the_new_lines():
    objs = R.render_session(_li([_msg("New thing")],
                                context=[_msg("old one"), _msg("older", out=True)]),
                            seat_email=SEAT, watermark=4, received_at=RECEIVED)
    body = objs[0].raw.raw["body"]
    head, _, ctx = body.partition("\n\n")
    assert head == "Priya Shah: New thing"
    assert ctx.splitlines() == [R.CONTEXT_HEADER, "> Priya Shah: old one", "> Rohit: older"]


def test_parts_above_forty_messages_and_above_the_char_budget():
    many = [_msg(f"message {i}") for i in range(85)]
    objs = R.render_session(_li(many), seat_email=SEAT, watermark=7, received_at=RECEIVED)
    ids = [o.raw.source_object_id for o in objs]
    assert ids == ["li:conv:abc#7#in#p1", "li:conv:abc#7#in#p2", "li:conv:abc#7#in#p3"]
    assert [len(o.messages) for o in objs] == [40, 40, 5]
    big = [_msg("x" * 2500) for _ in range(5)]
    parts = R.render_session(_li(big), seat_email=SEAT, watermark=8, received_at=RECEIVED)
    assert len(parts) >= 3
    for p in parts:
        assert len(p.raw.raw["subject"]) + 2 + len(p.raw.raw["body"]) <= R.MAX_CHARS
    huge = R.render_session(_li([_msg("y" * 20000)]), seat_email=SEAT, watermark=9,
                            received_at=RECEIVED)
    assert len(huge) == 1 and len(huge[0].raw.raw["body"]) <= R.MAX_CHARS


def _full(raw) -> int:
    """The prepared text the extractor is handed: subject + blank line + body."""
    return (len(raw["subject"]) + 2 if raw["subject"] else 0) + len(raw["body"])


def test_chat_boundary_new_text_splits_at_6k_and_the_full_body_stays_under_7_9k():
    ctx = [_msg("c" * 600, ts=None) for _ in range(20)]         # 12k of context on offer
    near = [_msg("n" * 1400) for _ in range(4)]                  # ~5.7k of new text
    objs = R.render_session(_li(near, context=ctx), seat_email=SEAT, watermark=1,
                            received_at=RECEIVED)
    assert len(objs) == 1, "context is trimmed first; new text under 6k is not split"
    body = objs[0].raw.raw["body"]
    new, _, ctx_part = body.partition("\n\n" + R.CONTEXT_HEADER + "\n")
    assert len(objs[0].raw.raw["subject"]) + 2 + len(new) <= R.MAX_CHARS
    assert 0 < len(ctx_part) and _full(objs[0].raw.raw) <= R.MAX_BODY
    assert ctx_part.count("\n") + 1 < len(ctx)                   # trimmed, most recent kept
    over = R.render_session(_li([_msg("n" * 1400) for _ in range(5)], context=ctx),
                            seat_email=SEAT, watermark=2, received_at=RECEIVED)
    assert len(over) == 2 and all(_full(o.raw.raw) <= R.MAX_BODY for o in over)


def test_generic_boundary_split_at_12k_full_body_under_15_9k():
    blocks = [{"role": "text", "text": "b" * 2900} for _ in range(4)]     # ~11.6k new
    ctx = [{"role": "text", "text": "k" * 900} for _ in range(10)]        # 9k context
    objs = R.render_session(_generic(blocks, ctx), seat_email=SEAT, watermark=1,
                            received_at=RECEIVED)
    assert len(objs) == 1 and _full(objs[0].raw.raw) <= R.MAX_BODY_GENERIC
    assert R.CONTEXT_HEADER in objs[0].raw.raw["body"]
    more = R.render_session(_generic(blocks + blocks, ctx), seat_email=SEAT, watermark=2,
                            received_at=RECEIVED)
    assert len(more) == 2 and all(_full(o.raw.raw) <= R.MAX_BODY_GENERIC for o in more)


def _generic(blocks, context_blocks=None, **extra):
    return {"session_key": "doc:crm:1", "thread_key": "doc:crm.acme.test/deals/42",
            "app": "generic", "title": "Acme — Deal", "blocks": blocks,
            "context_blocks": context_blocks or [], "bundle_id": "com.google.Chrome",
            "url": "https://crm.acme.test/deals/42", **extra}


def test_generic_blocks_render_heading_kv_table_and_message():
    blocks = [{"role": "heading", "text": "Acme renewal"},
              {"role": "kv", "label": "Stage", "value": "Negotiation"},
              {"role": "table", "header": ["Invoice", "Due"], "rows": [["INV-9", "2026-09-20"]]},
              {"role": "message", "sender": "Priya", "ts": None, "text": "Send it Monday",
               "is_outgoing": False},
              {"role": "message", "text": "Will do", "is_outgoing": True},
              {"role": "text", "text": "Notes  here"}]
    objs = R.render_session(_generic(blocks, [{"role": "kv", "label": "Owner",
                                               "value": "Priya"}]),
                            seat_email=SEAT, watermark=3, received_at=RECEIVED,
                            captured_at=datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc),
                            alias_hits=2)
    assert len(objs) == 1
    raw = objs[0].raw
    assert raw.object_type == "screen_doc" and raw.source_object_id.endswith("#3#doc")
    assert raw.actor_email is None and raw.raw["alias_hits"] == 2
    assert raw.raw["block_stats"] == {"kv": 1, "table": 1}
    assert raw.raw["host"] == "crm.acme.test"
    assert raw.occurred_at == datetime(2026, 9, 17, 4, 0, tzinfo=timezone.utc)
    assert raw.raw["body"].splitlines() == [
        "Acme renewal", "Stage: Negotiation", "| Invoice | Due |", "| INV-9 | 2026-09-20 |",
        "Priya: Send it Monday", f"{SEAT}: Will do", "Notes here", "",
        R.CONTEXT_HEADER, "> Owner: Priya"]


def test_a_long_table_splits_into_parts_that_repeat_its_header():
    rows = [[f"INV-{i}", "x" * 100] for i in range(200)]
    objs = R.render_session(_generic([{"role": "table", "header": ["Invoice", "Memo"],
                                       "rows": rows}]),
                            seat_email=SEAT, watermark=5, received_at=RECEIVED)
    assert len(objs) >= 2
    assert all(o.raw.raw["body"].startswith("| Invoice | Memo |") for o in objs)
    assert objs[-1].raw.source_object_id.endswith(f"#p{len(objs)}")


def test_norm_linkedin_url():
    assert R.norm_linkedin_url("linkedin.com/in/Foo-Bar/") == "https://www.linkedin.com/in/foo-bar"
    assert R.norm_linkedin_url("https://www.linkedin.com/company/acme") is None
    assert R.norm_linkedin_url("https://evil.test/in/x") is None


# ── relevance ─────────────────────────────────────────────────────────────────────────────
class _CountingLLM:
    model = "stub"

    def __init__(self, disposition):
        self.calls, self.disposition = 0, disposition

    def call(self, prompt, max_tokens=None):
        self.calls += 1
        return SimpleNamespace(ok=True, model="stub", usage=None,
                               parsed={"disposition": self.disposition, "relevance": 0.1,
                                       "reason": "stub"})


def _ctx(object_type, raw):
    return SimpleNamespace(event=SimpleNamespace(object_type=object_type, source="screen_session",
                                                 source_object_id="x#1#doc"),
                           raw=raw, sender_known=False)


def _gate(llm):
    from genios_engine.capture.gate.relevance import LLMRelevanceClassifier
    return REL.ScreenDocRelevance(LLMRelevanceClassifier(llm))


def test_doc_rules_decide_before_any_model_call():
    llm = _CountingLLM("drop")
    g = _gate(llm)
    for raw in ({"alias_hits": 1}, {"block_stats": {"kv": 2, "table": 1}},
                {"host": "acme.my.salesforce.com"}, {"bundle_id": "com.microsoft.Excel"}):
        assert g.classify(_ctx("screen_doc", {"subject": "s", **raw}), None).disposition == "keep"
    assert llm.calls == 0


def test_a_model_drop_is_downgraded_to_park():
    llm = _CountingLLM("drop")
    v = _gate(llm).classify(_ctx("screen_doc", {"subject": "Cheap flights", "host": "x.test"}),
                            SimpleNamespace(clean_text="deals on flights"))
    assert v.disposition == "park" and llm.calls == 1
    v = _gate(llm).classify(_ctx("screen_chat_thread", {"subject": "promo"}),
                            SimpleNamespace(clean_text="buy now"))
    assert v.disposition == "park" and llm.calls == 2


def test_without_a_model_unmatched_docs_park_and_threads_route():
    g = REL.ScreenDocRelevance(None)
    assert g.classify(_ctx("screen_doc", {"host": "news.test"}), None).disposition == "park"
    assert g.classify(_ctx("screen_chat_thread", {}), None).disposition == "keep"
