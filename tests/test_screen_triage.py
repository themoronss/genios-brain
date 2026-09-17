"""Screen triage — the free question asked before the paid one (SCREEN_COST_LATENCY_FIX.md §2.2).

A screen no rule can call work must not buy a model call; a screen that names someone this org
knows always must. Nothing is deleted either way: a skipped screen still reaches the promoter and
the hourly memory batch, so the rules here decide WHEN a judgement is paid for, never whether the
text survives.
"""

from __future__ import annotations

from genios_engine.contracts.moments import Participant
from genios_engine.reason.moments import screen_triage as T


def reason(**kw):
    base = {"app": None, "bundle_id": None, "url_domain": None, "thread_key": None,
            "entities": [], "participants": []}
    return T.skip_reason(**{**base, **kw})


def test_a_known_person_on_screen_is_always_judged():
    # The device's matcher resolved a slice node in the visible text — the cheapest strong signal.
    assert reason(app="generic", url_domain="some-unknown-vendor.example",
                  entities=["node_person_17"]) is None
    # …and so is a counterparty a resolver can turn into an id.
    assert reason(app="whatsapp", thread_key="wa:chat:1",
                  participants=[Participant(name="Priya", email="priya@acme.com")]) is None


def test_an_unknown_website_costs_nothing():
    assert reason(app="generic", url_domain="timesofindia.indiatimes.com",
                  thread_key="doc:com.google.Chrome:timesofindia.indiatimes.com/news") == T.NO_WORK_SIGNAL
    assert reason(app="generic", url_domain="amazon.in") == T.NO_WORK_SIGNAL


def test_a_conversation_is_judged_whoever_is_in_it():
    # The product decision of 2026-09-14: instant intelligence on ANY screen, not only on known
    # people. A new client's first message names nobody in the graph yet — refusing it would
    # refuse the wedge. Only a PAGE is ever refused; a family chat is answered `work:false` by
    # the judge itself, once, and the 24 h verdict keeps it quiet after that.
    assert reason(app="whatsapp", thread_key="wa:chat:someone-new",
                  participants=[Participant(name="Karan")]) is None
    assert reason(app="generic", url_domain="web.whatsapp.com") is None
    assert reason(app="generic",
                  thread_key="doc:com.google.Chrome:www.linkedin.com/messaging/thread/9") is None
    assert T.is_conversation("slack", None, None) and not T.is_conversation("generic", None, None)


def test_a_work_surface_is_judged_even_with_nobody_known_on_it():
    # A new client's first mail names nobody in the graph yet — the mailbox itself is the signal.
    assert reason(app="generic", url_domain="mail.google.com",
                  thread_key="doc:com.google.Chrome:mail.google.com/mail/u/0#inbox/FMfc") is None
    assert reason(app="slack") is None
    assert reason(app="generic", bundle_id="com.tinyspeck.slackmacgap") is None
    assert reason(app="generic", bundle_id="Outlook.exe") is None
    assert reason(app="generic", url_domain="app.hubspot.com") is None


def test_the_host_is_found_in_the_thread_key_when_the_device_sends_no_domain():
    assert reason(app="generic",
                  thread_key="doc:com.google.Chrome:notion.so/team/Acme-plan") is None
    assert reason(app="generic",
                  thread_key="doc:com.google.Chrome:reddit.com/r/india") == T.NO_WORK_SIGNAL
    # A native app key carries a title, not a host, and must not be read as one.
    assert reason(app="generic",
                  thread_key="doc:com.apple.Preview:title:invoice pdf") == T.NO_WORK_SIGNAL


def test_a_display_name_alone_is_not_a_known_counterparty():
    # Every unknown number has a display name; only an id-shaped handle counts.
    assert not T.has_known_counterparty([], [Participant(name="Karan")])
    assert T.has_known_counterparty([], [Participant(name="Karan", linkedin_url="https://x/in/k")])
    assert not T.has_known_counterparty(["", "  "], [])
