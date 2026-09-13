"""Capture policy — what a device may capture, for whom, and what is never captured.

TWO HALVES, ONE EFFECTIVE POLICY (migration 0141). The org row (`capture_policies`) says what is
ALLOWED; the seat row (`seat_capture_settings`) says what that person opted into and what they
additionally block. A seat only ever narrows the org. Both default OFF — an org with no row
captures nothing.

THE SENSITIVE LIST IS CODE, NOT DATA. Banking and payments, password managers, SSO / 2FA / OAuth
pages, HR and health, terminals and IDEs, GeniOS itself: merged into every effective policy and
not removable by any row. The device applies the same list before capture; the server applies it
again on upload (`check_session`) because a device is not a trust boundary.

BLOCK PATTERN GRAMMAR — one string list (`effective.blocked_domains`), three kinds of entry, so
the device gate and this gate can implement it identically:

  * ``example.com``   host is ``example.com`` or ends with ``.example.com``;
  * ``*bank*``        a host glob — ``*`` is the only wildcard, matched against the whole host;
  * ``/login``        a PATH marker — blocked when any path segment equals ``login`` or starts
                      with it followed by a non-letter (``/login.php``, ``/o/oauth2/auth``), so
                      ``/in/loginov`` on LinkedIn is not a login page.

A URL whose scheme is not http(s) (``chrome://password-manager``, ``about:``, ``file:``) is
blocked outright. Bundle ids are matched against `SENSITIVE_BUNDLE_IDS` (``*`` wildcard).

`policy_version` is a short hash of the EFFECTIVE policy, so a device compares one string to know
whether anything that governs it changed — including a pause running out.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from urllib.parse import urlsplit

from sqlalchemy import text

from genios_engine.platform.config import get_settings

#: The DEDICATED readers. Since D2 was revised (2026-09-13, plan §3.7) every app is read:
#: `allowed_apps` says which of these dedicated readers are enabled, and everything else — or a
#: dedicated app whose reader is off — is the generic reader's, which runs when `generic_web` is
#: on for both the org and the seat.
APP_IDS: tuple[str, ...] = ("gmail", "whatsapp", "linkedin", "slack", "outlook", "gcal")
#: All six by default. Also the column default in 0141.
DEFAULT_ALLOWED_APPS: tuple[str, ...] = APP_IDS
#: A session from the generic reader (`screen_doc` blocks, native or web). `web` is an alias.
GENERIC_APP = "generic"
GENERIC_ALIASES = frozenset({"generic", "web"})
DEFAULT_RETENTION_DAYS = 90

SENSITIVE_DOMAINS: tuple[str, ...] = (
    # banking / payments / brokerage
    "*bank*", "paypal.com", "dashboard.stripe.com", "dashboard.razorpay.com", "paytm.com",
    "pay.google.com", "wise.com", "onlinesbi.sbi", "onlinesbi.com", "sbi.co.in", "kotak.com",
    "chase.com", "wellsfargo.com", "americanexpress.com", "citi.com", "capitalone.com",
    "zerodha.com", "groww.in",
    # password managers
    "1password.com", "1password.eu", "bitwarden.com", "lastpass.com", "dashlane.com",
    "keepersecurity.com",
    # SSO / 2FA / OAuth
    "accounts.google.com", "login.microsoftonline.com", "login.live.com", "okta.com",
    "oktapreview.com", "auth0.com", "onelogin.com", "duosecurity.com", "appleid.apple.com",
    "account.apple.com", "idmsa.apple.com",
    "/oauth", "/login", "/signin", "/sign-in", "/sso", "/saml", "/2fa", "/mfa",
    # HR / payroll / health
    "bamboohr.com", "myworkday.com", "workday.com", "gusto.com", "rippling.com", "greythr.com",
    "keka.com", "darwinbox.in", "darwinbox.com", "zenefits.com", "adp.com", "practo.com",
    "1mg.com", "zocdoc.com", "*mychart*",
)

SENSITIVE_BUNDLE_IDS: tuple[str, ...] = (
    # terminals
    "com.apple.Terminal", "com.googlecode.iterm2", "dev.warp.Warp-Stable", "net.kovidgoyal.kitty",
    "io.alacritty", "org.alacritty", "com.mitchellh.ghostty",
    # IDEs / editors
    "com.microsoft.VSCode", "com.microsoft.VSCodeInsiders", "com.todesktop.230313mzl4w4u92",
    "dev.zed.Zed", "com.sublimetext.*", "com.jetbrains.*", "com.apple.dt.Xcode",
    # password managers / keychain
    "com.1password.*", "com.agilebits.onepassword*", "com.bitwarden.desktop",
    "com.lastpass.LastPass", "com.dashlane.*", "com.apple.keychainaccess", "com.apple.Passwords",
    # GeniOS itself
    "ai.genios.*",
)

# Settings-derived: the GeniOS product's own hosts are sensitive too (the dashboard shows other
# people's cards). Read from the deployment, so a white-labelled domain is covered.
def _own_domains() -> tuple[str, ...]:
    s = get_settings()
    out = {d.strip().lower() for d in (s.platform_domains or "").split(",") if d.strip()}
    host = _host_of(s.dashboard_url or "")
    if host:
        out.add(host)
    return tuple(sorted(out))


def sensitive_defaults() -> list[str]:
    """The patterns no org or seat row can remove: the list above plus GeniOS's own hosts."""
    return sorted(set(SENSITIVE_DOMAINS) | set(_own_domains()))


# ── pattern matching ──────────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=1024)
def _glob(pattern: str) -> re.Pattern:
    return re.compile("^" + ".*".join(re.escape(p) for p in pattern.split("*")) + "$")


def _host_of(url: str) -> str:
    try:
        parts = urlsplit(url if "://" in url else "https://" + url)
        return (parts.hostname or "").strip(".").lower()
    except ValueError:
        return ""


def _path_hit(path: str, marker: str) -> bool:
    token = marker.strip("/").lower()
    if not token:
        return False
    for seg in path.lower().split("/"):
        if seg == token or (seg.startswith(token) and not seg[len(token)].isalpha()):
            return True
    return False


def _host_hit(host: str, pattern: str) -> bool:
    if "*" in pattern:
        return bool(_glob(pattern).match(host))
    return host == pattern or host.endswith("." + pattern)


def url_block_reason(url: str | None, patterns) -> str | None:
    """Why `url` is blocked under `patterns`, or None. No URL (a native app) is not blocked here."""
    if not url:
        return None
    raw = url.strip()
    try:
        parts = urlsplit(raw if "://" in raw or ":" in raw.split("/", 1)[0] else "https://" + raw)
    except ValueError:
        return "domain_blocked"
    if parts.scheme.lower() not in ("http", "https"):
        return "domain_blocked"
    host = (parts.hostname or "").strip(".").lower()
    if not host:
        return "domain_blocked"
    for pattern in patterns:
        if pattern.startswith("/"):
            if _path_hit(parts.path or "", pattern):
                return "domain_blocked"
        elif _host_hit(host, pattern):
            return "domain_blocked"
    return None


def bundle_blocked(bundle_id: str | None) -> bool:
    if not bundle_id:
        return False
    b = bundle_id.strip()
    return any(bool(_glob(p).match(b)) if "*" in p else b == p for p in SENSITIVE_BUNDLE_IDS)


def is_blocked(url: str | None, bundle_id: str | None, policy: dict) -> bool:
    """The privacy gate: is this URL / app never to be captured under `policy` (an effective
    policy dict, or the full policy document)? The sensitive defaults apply even to a policy
    that somehow lacks them."""
    eff = policy.get("effective", policy) if isinstance(policy, dict) else {}
    patterns = tuple(eff.get("blocked_domains") or ()) + SENSITIVE_DOMAINS
    return bundle_blocked(bundle_id) or url_block_reason(url, patterns) is not None


# ── validation of what a person types ─────────────────────────────────────────────────────────
_PATTERN_OK = re.compile(r"^(/[a-z0-9._~-]+|[a-z0-9*][a-z0-9.*-]*)$")


def normalize_patterns(values) -> list[str]:
    """Lowercase, strip scheme / path / port from a pasted URL, keep the grammar above. Raises
    ValueError naming the first entry that is not a pattern."""
    out: list[str] = []
    for v in values or ():
        s = str(v or "").strip().lower()
        if not s:
            continue
        if not s.startswith("/") and ("://" in s or "/" in s or ":" in s):
            s = _host_of(s) or s
        s = s.removeprefix("www.") if s.startswith("www.") and "*" not in s else s
        if len(s) > 253 or not _PATTERN_OK.match(s):
            raise ValueError(f"not a domain or path pattern: {v!r}")
        if s not in out:
            out.append(s)
    return out


def normalize_apps(values) -> list[str]:
    out: list[str] = []
    for v in values or ():
        a = str(v or "").strip().lower()
        if a not in APP_IDS:
            raise ValueError(f"unknown app id: {v!r} (known: {', '.join(APP_IDS)})")
        if a not in out:
            out.append(a)
    return out


# ── the two halves and their merge ────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class OrgPolicy:
    enabled: bool = False
    allowed_apps: tuple[str, ...] = DEFAULT_ALLOWED_APPS
    blocked_domains: tuple[str, ...] = ()
    generic_web_allowed: bool = True              # D2 revised: every app is read (plan §3.7)
    draft_assist_allowed: bool = False
    retention_days: int = DEFAULT_RETENTION_DAYS


@dataclass(frozen=True)
class SeatSettings:
    enabled: bool = False
    draft_assist: bool = False
    generic_web: bool = True                      # still switchable off, per seat
    paused_until: datetime | None = None
    blocked_apps: tuple[str, ...] = ()
    blocked_domains: tuple[str, ...] = field(default=())


def _iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _aware(dt: datetime | None) -> datetime | None:
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def effective_policy(org: OrgPolicy, seat: SeatSettings, *, now: datetime) -> dict:
    """The merge. Computed AT `now`: a pause that has run out is no pause, and the version the
    device compares changes the moment it does."""
    paused = _aware(seat.paused_until)
    paused = paused if paused is not None and paused > now else None
    blocked = sorted(set(sensitive_defaults()) | set(org.blocked_domains)
                     | set(seat.blocked_domains))
    apps = sorted(set(org.allowed_apps) & set(APP_IDS) - set(seat.blocked_apps))
    return {
        "capture_on": bool(org.enabled and seat.enabled and paused is None),
        "apps": apps,
        "blocked_domains": blocked,
        "generic_web": bool(org.generic_web_allowed and seat.generic_web),
        "draft_assist": bool(org.draft_assist_allowed and seat.draft_assist),
        "paused_until": _iso(paused),
    }


def policy_version(effective: dict) -> str:
    blob = json.dumps(effective, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def min_supported_app_version() -> str:
    return get_settings().desktop_min_app_version or "0.0.0"


def version_tuple(v: str | None) -> tuple[int, ...] | None:
    """'0.1.0', 'v0.2.3-beta.1' → (0, 1, 0) / (0, 2, 3). Unparseable → None (treated as too old)."""
    m = re.match(r"^\s*v?(\d+)(?:\.(\d+))?(?:\.(\d+))?", v or "")
    if not m:
        return None
    return tuple(int(g or 0) for g in m.groups())


def app_version_supported(v: str | None) -> bool:
    have, need = version_tuple(v), version_tuple(min_supported_app_version()) or (0, 0, 0)
    return have is not None and have >= need


def policy_document(org: OrgPolicy, seat: SeatSettings, *, now: datetime) -> dict:
    """The `GET /v1/capture/policy` body (contract §3.2)."""
    eff = effective_policy(org, seat, now=now)
    return {
        "policy_version": policy_version(eff),
        "min_supported_app_version": min_supported_app_version(),
        # Pinned 2026-09-13: `org.blocked_domains` is the admin's own list; the defaults no row
        # can remove are shown here, and merged into `effective.blocked_domains`.
        "sensitive_defaults": sensitive_defaults(),
        "org": {"enabled": org.enabled, "allowed_apps": list(org.allowed_apps),
                "blocked_domains": list(org.blocked_domains),
                "generic_web_allowed": org.generic_web_allowed,
                "draft_assist_allowed": org.draft_assist_allowed,
                "retention_days": org.retention_days},
        "seat": {"enabled": seat.enabled, "draft_assist": seat.draft_assist,
                 "generic_web": seat.generic_web, "paused_until": _iso(_aware(seat.paused_until)),
                 "blocked_apps": list(seat.blocked_apps),
                 "blocked_domains": list(seat.blocked_domains)},
        "effective": eff,
    }


# Rejection reasons for one uploaded session — the vocabulary of §3.3 `rejected[].reason`.
ORG_DISABLED = "capture_disabled"
SEAT_DISABLED = "seat_capture_disabled"
PAUSED = "paused"
APP_NOT_ALLOWED = "app_not_allowed"        # not a dedicated reader and not the generic one
READER_DISABLED = "reader_disabled"        # a dedicated reader the org or seat switched off
GENERIC_DISABLED = "generic_disabled"      # the generic reader, switched off by org or seat
DOMAIN_BLOCKED = "domain_blocked"
APP_BLOCKED = "app_blocked"
PRIVATE_WINDOW = "private_window"
INVALID = "invalid_session"


def check_session(org: OrgPolicy, seat: SeatSettings, *, app: str, url: str | None,
                  bundle_id: str | None, private_window: bool, now: datetime) -> str | None:
    """The server-side re-check of one session: the reason it is refused, or None to accept.
    Order is most-general first, so a disabled org reports that and not a per-URL detail. The
    sensitive URL / bundle checks apply to generic and dedicated sessions alike."""
    if not org.enabled:
        return ORG_DISABLED
    if not seat.enabled:
        return SEAT_DISABLED
    eff = effective_policy(org, seat, now=now)
    if eff["paused_until"] is not None:
        return PAUSED
    a = (app or "").strip().lower()
    if a in GENERIC_ALIASES:
        if not eff["generic_web"]:
            return GENERIC_DISABLED
    elif a not in APP_IDS:
        return APP_NOT_ALLOWED
    elif a not in eff["apps"]:
        return READER_DISABLED
    if private_window:
        return PRIVATE_WINDOW
    if bundle_blocked(bundle_id):
        return APP_BLOCKED
    if url_block_reason(url, eff["blocked_domains"]):
        return DOMAIN_BLOCKED
    return None


def should_write_presence(lease, fields: dict, *, now: datetime,
                          max_age: timedelta = timedelta(seconds=30)) -> bool:
    """Write the lease only when something changed or the row is older than `max_age`."""
    if lease is None or lease.get("updated_at") is None:
        return True
    if any(lease.get(k) != v for k, v in fields.items()):
        return True
    return now - _aware(lease["updated_at"]) >= max_age


def _org_from_row(r) -> OrgPolicy:
    if r is None or r.get("p_enabled") is None:
        return OrgPolicy()
    return OrgPolicy(enabled=bool(r["p_enabled"]),
                     allowed_apps=tuple(r.get("allowed_apps") or ()),
                     blocked_domains=tuple(r.get("p_blocked_domains") or ()),
                     generic_web_allowed=bool(r.get("generic_web_allowed")),
                     draft_assist_allowed=bool(r.get("draft_assist_allowed")),
                     retention_days=int(r.get("retention_days") or DEFAULT_RETENTION_DAYS))


def _seat_from_row(r) -> SeatSettings:
    if r is None or r.get("s_enabled") is None:
        return SeatSettings()
    return SeatSettings(enabled=bool(r["s_enabled"]), draft_assist=bool(r.get("draft_assist")),
                        generic_web=bool(r.get("generic_web")),
                        paused_until=_aware(r.get("paused_until")),
                        blocked_apps=tuple(r.get("blocked_apps") or ()),
                        blocked_domains=tuple(r.get("s_blocked_domains") or ()))


# ── storage ───────────────────────────────────────────────────────────────────────────────────
_LOAD = text(
    "select p.enabled as p_enabled, p.allowed_apps, p.blocked_domains as p_blocked_domains, "
    "p.generic_web_allowed, p.draft_assist_allowed, p.retention_days, "
    "s.enabled as s_enabled, s.draft_assist, s.generic_web, s.paused_until, s.blocked_apps, "
    "s.blocked_domains as s_blocked_domains, "
    "l.focus_app, l.bundle_id, l.dnd, l.idle, l.app_version, l.policy_version, "
    "l.updated_at as lease_updated_at "
    "from (select 1) as one "
    "left join capture_policies p on p.org_id = :o "
    "left join seat_capture_settings s on s.org_id = :o and s.seat_id = :s "
    "left join presence_leases l on l.org_id = :o and l.seat_id = :s "
    "and l.device_id = cast(:d as text)")

_PRESENCE_LEASE_TTL = timedelta(seconds=45)       # > the 30 s write interval + one 10 s heartbeat


class CaptureStore:
    """Every capture-side SQL statement. Each method is one short transaction of one or two
    statements — the session pooler is 8+4 connections and these endpoints are the chattiest the
    engine has (a heartbeat every 10 s per device)."""

    def __init__(self, engine) -> None:
        self.engine = engine

    def load(self, org_id: str, seat_id: str, device_id: str | None = None):
        """(OrgPolicy, SeatSettings, lease dict | None) in ONE statement."""
        with self.engine.connect() as c:
            row = c.execute(_LOAD, {"o": org_id, "s": seat_id, "d": device_id}).mappings().first()
        r = dict(row) if row is not None else None
        lease = None
        if r is not None and r.get("lease_updated_at") is not None:
            lease = {k: r.get(k) for k in ("focus_app", "bundle_id", "dnd", "idle", "app_version",
                                           "policy_version")}
            lease["updated_at"] = r["lease_updated_at"]
        return _org_from_row(r), _seat_from_row(r), lease

    def save_org_policy(self, org_id: str, changes: dict, *, updated_by: str | None) -> None:
        cols = ("enabled", "allowed_apps", "blocked_domains", "generic_web_allowed",
                "draft_assist_allowed", "retention_days")
        params = {"o": org_id, "by": updated_by}
        for col in cols:
            v = changes.get(col)
            params[col] = json.dumps(v) if isinstance(v, list) else v
        with self.engine.begin() as c:
            c.execute(text(
                "insert into capture_policies (org_id, enabled, allowed_apps, blocked_domains, "
                "generic_web_allowed, draft_assist_allowed, retention_days, updated_by, updated_at) "
                "values (:o, coalesce(:enabled, false), "
                "coalesce(cast(:allowed_apps as jsonb), '[\"gmail\", \"whatsapp\", \"linkedin\", "
                "\"slack\", \"outlook\", \"gcal\"]'::jsonb), "
                "coalesce(cast(:blocked_domains as jsonb), '[]'::jsonb), "
                "coalesce(:generic_web_allowed, true), coalesce(:draft_assist_allowed, false), "
                "coalesce(:retention_days, 90), :by, now()) "
                "on conflict (org_id) do update set "
                "enabled = coalesce(:enabled, capture_policies.enabled), "
                "allowed_apps = coalesce(cast(:allowed_apps as jsonb), capture_policies.allowed_apps), "
                "blocked_domains = coalesce(cast(:blocked_domains as jsonb), "
                "capture_policies.blocked_domains), "
                "generic_web_allowed = coalesce(:generic_web_allowed, "
                "capture_policies.generic_web_allowed), "
                "draft_assist_allowed = coalesce(:draft_assist_allowed, "
                "capture_policies.draft_assist_allowed), "
                "retention_days = coalesce(:retention_days, capture_policies.retention_days), "
                "updated_by = :by, updated_at = now()"), params)

    def save_seat_settings(self, org_id: str, seat_id: str, changes: dict) -> None:
        """`changes` may carry `paused_until` (with key present → set, even to NULL)."""
        params = {"o": org_id, "s": seat_id}
        for col in ("enabled", "draft_assist", "generic_web", "blocked_apps", "blocked_domains"):
            v = changes.get(col)
            params[col] = json.dumps(v) if isinstance(v, list) else v
        params["set_pause"] = "paused_until" in changes
        params["paused_until"] = changes.get("paused_until")
        with self.engine.begin() as c:
            c.execute(text(
                "insert into seat_capture_settings (org_id, seat_id, enabled, draft_assist, "
                "generic_web, paused_until, blocked_apps, blocked_domains, updated_at) "
                "values (:o, :s, coalesce(:enabled, false), coalesce(:draft_assist, false), "
                "coalesce(:generic_web, true), cast(:paused_until as timestamptz), "
                "coalesce(cast(:blocked_apps as jsonb), '[]'::jsonb), "
                "coalesce(cast(:blocked_domains as jsonb), '[]'::jsonb), now()) "
                "on conflict (org_id, seat_id) do update set "
                "enabled = coalesce(:enabled, seat_capture_settings.enabled), "
                "draft_assist = coalesce(:draft_assist, seat_capture_settings.draft_assist), "
                "generic_web = coalesce(:generic_web, seat_capture_settings.generic_web), "
                "paused_until = case when :set_pause then cast(:paused_until as timestamptz) "
                "else seat_capture_settings.paused_until end, "
                "blocked_apps = coalesce(cast(:blocked_apps as jsonb), "
                "seat_capture_settings.blocked_apps), "
                "blocked_domains = coalesce(cast(:blocked_domains as jsonb), "
                "seat_capture_settings.blocked_domains), updated_at = now()"), params)

    def insert_deltas(self, rows: list[dict], *, org_id: str, device_id: str,
                      now: datetime) -> set[tuple[str, int]]:
        """Insert held deltas; return the (session_key, watermark) pairs that were NEW. One
        multi-row insert (`unnest`) plus the device's `last_seen_at` — two statements whatever
        the batch size. A pair already stored is skipped by the primary key."""
        with self.engine.begin() as c:
            inserted: set[tuple[str, int]] = set()
            if rows:
                res = c.execute(text(
                    "insert into screen_session_deltas (org_id, device_id, session_key, "
                    "message_watermark, seat_id, app, thread_key, payload_enc, message_count, "
                    "captured_at, received_at, status) "
                    "select :o, :d, k, w, :s, a, t, p, n, ca, :now, 'held' from unnest("
                    "cast(:keys as text[]), cast(:wms as bigint[]), cast(:apps as text[]), "
                    "cast(:threads as text[]), cast(:payloads as bytea[]), cast(:counts as int[]), "
                    "cast(:caps as timestamptz[])) as u(k, w, a, t, p, n, ca) "
                    "on conflict (org_id, device_id, session_key, message_watermark) do nothing "
                    "returning session_key, message_watermark"),
                    {"o": org_id, "d": device_id, "s": rows[0]["seat_id"], "now": now,
                     "keys": [r["session_key"] for r in rows],
                     "wms": [r["message_watermark"] for r in rows],
                     "apps": [r["app"] for r in rows],
                     "threads": [r["thread_key"] for r in rows],
                     "payloads": [r["payload_enc"] for r in rows],
                     "counts": [r["message_count"] for r in rows],
                     "caps": [r["captured_at"] for r in rows]})
                inserted = {(x.session_key, int(x.message_watermark)) for x in res}
            c.execute(text("update devices set last_seen_at = :now "
                           "where org_id = :o and device_id = :d"),
                      {"now": now, "o": org_id, "d": device_id})
        return inserted

    def write_presence(self, *, org_id: str, seat_id: str, device_id: str, fields: dict,
                       now: datetime) -> None:
        """Upsert the lease and touch the device — ONE statement."""
        with self.engine.begin() as c:
            c.execute(text(
                "with lease as ("
                "insert into presence_leases (org_id, seat_id, device_id, focus_app, bundle_id, "
                "dnd, idle, app_version, policy_version, updated_at, expires_at) "
                "values (:o, :s, :d, :focus_app, :bundle_id, :dnd, :idle, :app_version, "
                ":policy_version, :now, :exp) "
                "on conflict (org_id, seat_id, device_id) do update set "
                "focus_app = excluded.focus_app, bundle_id = excluded.bundle_id, "
                "dnd = excluded.dnd, idle = excluded.idle, app_version = excluded.app_version, "
                "policy_version = excluded.policy_version, updated_at = excluded.updated_at, "
                "expires_at = excluded.expires_at returning 1) "
                "update devices set last_seen_at = :now, app_version = :app_version "
                "where org_id = :o and device_id = :d"),
                {"o": org_id, "s": seat_id, "d": device_id, "now": now,
                 "exp": now + _PRESENCE_LEASE_TTL, **fields})

    def purge_expired(self, *, now: datetime | None = None, batch: int = 5000,
                      max_batches: int = 20) -> dict:
        """Retention, on the scheduler heartbeat. Deltas older than their org's `retention_days`
        (90 without a policy row) go in batches of `batch`, each its own short transaction, so a
        large backlog never holds a long lock; dead presence leases and device codes go too."""
        now = now or datetime.now(timezone.utc)
        deleted = 0
        for _ in range(max_batches):
            with self.engine.begin() as c:
                n = c.execute(text(
                    "delete from screen_session_deltas t using ("
                    "select d.org_id, d.device_id, d.session_key, d.message_watermark "
                    "from screen_session_deltas d "
                    "left join capture_policies p on p.org_id = d.org_id "
                    "where d.received_at < :now - make_interval(days => ("
                    "select least(coalesce(min(retention_days), 90), 90) from capture_policies)) "
                    "and d.received_at < :now - make_interval(days => "
                    "coalesce(p.retention_days, 90)) limit :n) v "
                    "where t.org_id = v.org_id and t.device_id = v.device_id "
                    "and t.session_key = v.session_key "
                    "and t.message_watermark = v.message_watermark"),
                    {"now": now, "n": batch}).rowcount or 0
            deleted += n
            if n < batch:
                break
        with self.engine.begin() as c:
            leases = c.execute(text("delete from presence_leases where expires_at < :cut"),
                               {"cut": now - timedelta(days=1)}).rowcount or 0
            codes = c.execute(text("delete from device_auth_codes where expires_at < :cut"),
                              {"cut": now - timedelta(days=1)}).rowcount or 0
        return {"screen_session_deltas": deleted, "presence_leases": leases,
                "device_auth_codes": codes}


def screen_connection_id(seat_id: str) -> str:
    """The `source_events.connection_id` of a seat's promoted screen events — ONE definition,
    shared by the promoter that writes it and the shred that finds the seat's events by it."""
    return f"screen:{seat_id}"


def shred_seat_capture(conn, *, org_id: str, seat_id: str) -> int:
    """A removed seat's capture, gone in the caller's transaction: every uploaded delta (the
    crypto-shred the P1 plan asks for — nothing of theirs stays to be decrypted), the raw payload
    and prepared text of every screen event promoted from them (P2 §14), their presence and their
    opt-in. Returns deltas deleted."""
    screen_events = ("select event_id from source_events where org_id = :o "
                     "and source = 'screen_session' and connection_id = :c")
    params = {"o": org_id, "c": screen_connection_id(seat_id)}
    conn.execute(text(f"delete from raw_payloads where org_id = :o and event_id in "
                      f"({screen_events})"), params)
    conn.execute(text(f"delete from prepared_content where org_id = :o and event_id in "
                      f"({screen_events})"), params)
    n = conn.execute(text("delete from screen_session_deltas where org_id=:o and seat_id=:s"),
                     {"o": org_id, "s": seat_id}).rowcount or 0
    conn.execute(text("delete from presence_leases where org_id=:o and seat_id=:s"),
                 {"o": org_id, "s": seat_id})
    conn.execute(text("delete from seat_capture_settings where org_id=:o and seat_id=:s"),
                 {"o": org_id, "s": seat_id})
    return n


__all__ = ["APP_IDS", "CaptureStore", "DEFAULT_ALLOWED_APPS", "GENERIC_ALIASES", "GENERIC_APP",
           "OrgPolicy",
           "SENSITIVE_BUNDLE_IDS", "SENSITIVE_DOMAINS", "SeatSettings", "app_version_supported",
           "bundle_blocked", "check_session", "effective_policy", "is_blocked",
           "min_supported_app_version", "normalize_apps", "normalize_patterns",
           "policy_document", "policy_version", "screen_connection_id", "shred_seat_capture",
           "should_write_presence",
           "url_block_reason", "version_tuple"]
