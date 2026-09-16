"""Screen triage — the free question asked before the paid one (SCREEN_COST_LATENCY_FIX.md §2.2).

`_screen_insight` used to send EVERY unjudged screen with ≥ 30 characters to the model, including
the ones a rule could have refused for nothing: a news site, a settings pane, a shopping cart, a
family chat. The 24 h thread verdict only helps AFTER that first call has been paid for. Measured
on one seat, 3.7 h, 14 Sep: 224 calls, ₹30.

The rules here are not new. They are the promoter lane's own (`capture/screen/relevance.py`), so
the product has ONE spelling of "this screen is work":

    entities     the device's matcher already found a person or company from the seat's slice in
                 the visible text — the strongest signal there is, and it costs nothing;
    participant  a counterparty with an email or a LinkedIn URL (a dedicated reader's output) —
                 something a resolver can turn into a graph id;
    work surface a WORK_HOSTS site, a WORK_BUNDLES / WORK_EXES app, or one of the apps that are a
                 work surface by construction (Slack, Teams, Outlook, Mail);
    otherwise    SKIPPED — no model call, counted with its reason.

NOTHING IS LOST BY SKIPPING. The screen still reaches the promoter, and an unjudged thread is
still queued for the hourly memory batch (`screen_memory_batch`, half price), which judges work /
personal itself. A skipped screen arrives late and cheap instead of instantly and dear — it does
not disappear. That is the difference between this and the `screen_generic_daily_cap` that hid a
seat's data on 14 Sep, and it is why the skip is counted and visible in `GET /v1/capture/policy`.

Governed by `screen_insight_triage_enabled` (default on): one env var switches it off.
"""
from __future__ import annotations

from genios_engine.capture.screen.relevance import WORK_BUNDLES, WORK_EXES, WORK_HOSTS

#: Why a screen was not judged. Counted per seat per day and reported in the capture policy.
NO_WORK_SIGNAL = "no_work_signal"
PERSONAL_CHAT = "personal_chat_no_known_contact"

#: Messengers a manager's private life lives on too. A chat here with nobody this org knows is
#: most likely family or friends: the promoter parks it, so the instant lane must not pay for it.
#: (`capture/screen/relevance` held this list until the per-thread verdict replaced its use there.)
PERSONAL_CHAT_APPS: frozenset[str] = frozenset({"whatsapp", "imessage", "messages", "telegram",
                                                "signal", "instagram", "messenger"})

#: Apps that ARE a work surface, whoever is on the other side: a company mailbox or a company
#: chat. Kept here and not in `relevance.WORK_BUNDLES` on purpose — that constant also routes the
#: promoter's keep/park decision, and widening it would change what the memory lane extracts.
WORK_SURFACE_APPS: frozenset[str] = frozenset({
    "slack", "teams", "outlook", "gmail", "mail", "superhuman", "spark", "hey", "front",
    "linear", "jira", "notion", "salesforce", "hubspot", "zoho", "freshdesk", "zendesk",
    "intercom",
})
WORK_SURFACE_BUNDLES: tuple[str, ...] = (
    "com.apple.mail", "com.microsoft.Outlook", "com.tinyspeck.slackmacgap",
    "com.microsoft.teams2", "com.readdle.smartemail", "com.superhuman",
    "com.missiveapp", "com.flexibits.fantastical", "com.apple.iCal",
)
WORK_SURFACE_EXES: frozenset[str] = frozenset({
    "outlook.exe", "slack.exe", "hxoutlook.exe", "olk.exe",
})
#: The same, on the web. `relevance.WORK_HOSTS` deliberately carries no mailbox — the promoter
#: routes mail by its own rules — but for the instant lane a company mailbox or calendar IS the
#: work signal: a new client's first mail names nobody in the graph yet. `web.whatsapp.com` is
#: NOT here on purpose: a personal messenger stays gated on a known contact, web or native.
WORK_SURFACE_HOSTS: tuple[str, ...] = (
    "mail.google.com", "calendar.google.com", "outlook.live.com", "outlook.office.com",
    "outlook.office365.com", "mail.zoho.com", "mail.zoho.in", "app.slack.com",
    "teams.microsoft.com", "teams.live.com", "mail.yahoo.com", "app.frontapp.com",
    "mail.superhuman.com", "app.missiveapp.com",
)


def _host_of(url_domain: str | None, thread_key: str | None) -> str:
    """The site this screen is on: the reported domain, else the host inside a `doc:` key."""
    host = (url_domain or "").strip().lower().strip(".")
    if host:
        return host
    key = (thread_key or "").strip()
    if not key.startswith("doc:") or ":title:" in key:
        return ""
    rest = key.split(":", 2)[2] if key.count(":") >= 2 else ""
    return rest.split("/", 1)[0].strip().lower().strip(".")


def is_work_host(host: str) -> bool:
    return bool(host) and any(host == w or host.endswith("." + w)
                              for w in WORK_HOSTS + WORK_SURFACE_HOSTS)


def is_work_app(app: str | None, bundle_id: str | None) -> bool:
    """A work surface by app name or bundle id / executable (Windows sends the exe as bundle)."""
    a = (app or "").strip().lower()
    if a and a in WORK_SURFACE_APPS:
        return True
    b = (bundle_id or "").strip()
    if not b:
        return False
    if b.lower().endswith(".exe"):
        return b.lower() in WORK_EXES or b.lower() in WORK_SURFACE_EXES
    return any(b.startswith(w) for w in WORK_BUNDLES + WORK_SURFACE_BUNDLES)


def has_known_counterparty(entities, participants) -> bool:
    """Someone or something this org already knows is on screen. `entities` are slice node ids the
    device's matcher resolved; a participant with an email or a LinkedIn URL is resolvable by id.
    A participant with only a display name is NOT a signal — that is every unknown number."""
    if [e for e in (entities or []) if str(e or "").strip()]:
        return True
    for p in participants or []:
        email = getattr(p, "email", None) if not isinstance(p, dict) else p.get("email")
        linkedin = getattr(p, "linkedin_url", None) if not isinstance(p, dict) else p.get("linkedin_url")
        if str(email or "").strip() or str(linkedin or "").strip():
            return True
    return False


def skip_reason(*, app: str | None, bundle_id: str | None, url_domain: str | None,
                thread_key: str | None, entities=None, participants=None) -> str | None:
    """Why this screen must not cost a model call, or None when it is worth judging."""
    known = has_known_counterparty(entities, participants)
    if known:
        return None
    a = (app or "").strip().lower()
    if a in PERSONAL_CHAT_APPS:
        # The promoter already parks a personal-messenger chat with no known contact; the instant
        # lane must not pay for what the memory lane refuses.
        return PERSONAL_CHAT
    if is_work_app(a, bundle_id) or is_work_host(_host_of(url_domain, thread_key)):
        return None
    return NO_WORK_SIGNAL


__all__ = ["NO_WORK_SIGNAL", "PERSONAL_CHAT", "PERSONAL_CHAT_APPS", "WORK_SURFACE_APPS", "WORK_SURFACE_BUNDLES",
           "WORK_SURFACE_EXES", "WORK_SURFACE_HOSTS", "has_known_counterparty", "is_work_app", "is_work_host",
           "skip_reason"]
