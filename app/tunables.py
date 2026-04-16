"""
Runtime tunables — every value a deploy might want to override.

Rule: no magic numbers or magic lists in business logic. If it could vary
by deploy, region, or customer, it lives here and reads from env.

Every setting has:
  - A public name used elsewhere in the codebase
  - An env var that can override it
  - A sensible, documented default

All lists are comma-separated in env. Dicts are JSON.

Examples:
    GENIOS_BROADCAST_LOCAL_PATTERNS="noreply,info,newsletter"
    GENIOS_BROADCAST_DOMAINS="mailchimp,sendgrid"
    GENIOS_BROADCAST_MIN_ONEWAY_COUNT=3
    GENIOS_MEETING_TITLE_TOPICS='{"interview":["interview","screening"]}'
"""
import json
import os
import re
from typing import Dict, List


def _env_csv(name: str, default: List[str]) -> List[str]:
    raw = os.getenv(name)
    if raw is None:
        return list(default)
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    try:
        return int(raw) if raw is not None else default
    except ValueError:
        return default


def _env_json(name: str, default: dict) -> dict:
    raw = os.getenv(name)
    if raw is None:
        return dict(default)
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, dict) else dict(default)
    except json.JSONDecodeError:
        return dict(default)


# ── Broadcast / marketing sender detection ─────────────────────────────────
# These identify senders that aren't real relationships. All overridable via
# env so each deploy (or region) can tune the list without code changes.

BROADCAST_LOCAL_PATTERNS: List[str] = _env_csv(
    "GENIOS_BROADCAST_LOCAL_PATTERNS",
    default=[
        "noreply", "no-reply", "notifications", "notification", "notify",
        "information", "info", "communications", "comms",
        "newsletter", "updates", "update", "mailer",
        "promo", "marketing", "support", "hello", "contacts", "contact",
        "team", "community.manager", "community-manager",
        "vacancy", "vacancies", "careers", "jobs",
        "contract.notes", "contract-notes", "billing", "accounts", "account",
        "system", "do-not-reply", "donotreply",
    ],
)

BROADCAST_DOMAINS: List[str] = _env_csv(
    "GENIOS_BROADCAST_DOMAINS",
    default=[
        "naukri", "shine", "luma-mail",
        "sendgrid", "mailgun", "amazonses", "mailchimp",
        "marketing-email", "campaign-monitor",
    ],
)

# Behavioral threshold: a sender with no replies who has sent at least this
# many messages is treated as broadcast even if the address looks human.
BROADCAST_MIN_ONEWAY_COUNT: int = _env_int("GENIOS_BROADCAST_MIN_ONEWAY_COUNT", 3)


def broadcast_local_regex() -> re.Pattern:
    """Compile the local-part (before @) broadcast regex from the config list."""
    if not BROADCAST_LOCAL_PATTERNS:
        return re.compile(r"(?!x)x")  # matches nothing
    escaped = "|".join(re.escape(p) for p in BROADCAST_LOCAL_PATTERNS)
    return re.compile(rf"(?:^|[.-])(?:{escaped})(?:@|[.-])")


def broadcast_domain_regex() -> re.Pattern:
    """Compile the domain-part broadcast regex from the config list."""
    if not BROADCAST_DOMAINS:
        return re.compile(r"(?!x)x")
    escaped = "|".join(re.escape(p) for p in BROADCAST_DOMAINS)
    return re.compile(rf"(?:@|\.)(?:{escaped})\.")


def broadcast_local_sql_regex() -> str:
    """SQL-safe regex string for PostgreSQL's `~` operator."""
    if not BROADCAST_LOCAL_PATTERNS:
        return "^$"
    alt = "|".join(re.escape(p) for p in BROADCAST_LOCAL_PATTERNS)
    return f"(^|[.-])({alt})(@|[.-])"


def broadcast_domain_sql_regex() -> str:
    if not BROADCAST_DOMAINS:
        return "^$"
    alt = "|".join(re.escape(p) for p in BROADCAST_DOMAINS)
    return f"(@|\\.)({alt})\\."


# ── Meeting title topic extraction ─────────────────────────────────────────
# Used as a cheap fallback when the calendar LLM extractor hasn't enriched
# an event. Override via env to support non-English or domain-specific titles.

MEETING_TITLE_TOPIC_MAP: Dict[str, List[str]] = _env_json(
    "GENIOS_MEETING_TITLE_TOPICS",
    default={
        "interview": ["interview", "screening"],
        "standup":   ["standup", "daily"],
        "1:1":       ["1:1", "1-on-1", "one on one"],
        "roadmap":   ["roadmap", "planning"],
        "demo":      ["demo", "walkthrough"],
        "kickoff":   ["kickoff", "kick-off"],
        "review":    ["review", "retro"],
        "hiring":    ["hiring"],
        "pricing":   ["pricing"],
        "onboarding":["onboarding"],
        "discovery": ["discovery"],
        "renewal":   ["renewal"],
    },
)

TITLE_TOPIC_STOPWORDS: List[str] = _env_csv(
    "GENIOS_TITLE_TOPIC_STOPWORDS",
    default=[
        "meeting", "call", "chat", "sync", "catch-up", "catchup",
        "with", "and", "the", "a", "an", "for", "re",
    ],
)
TITLE_TOPIC_MIN_LEN: int = _env_int("GENIOS_TITLE_TOPIC_MIN_LEN", 4)
