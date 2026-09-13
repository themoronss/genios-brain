"""Outbound egress guard (SSRF) — SCREEN_INTEL_P6_BUILD.md §3.7 (frozen).

Every URL GeniOS will POST to on a CLIENT's behalf (an agent webhook) passes through `check_url`
twice: when it is registered (`api/agent_mgmt_routes._clean_webhook_url`) and immediately before
every send (`deliver/channels/agent.py`). The second check is not redundant — DNS is the client's,
and a name that resolved to a public address at registration can resolve to 10.0.0.1 or the cloud
metadata service tomorrow.

Rules:
  * https only. The single exception is the DEV loopback: `http(s)://localhost` / `127.0.0.1` /
    `[::1]`, allowed only when `GENIOS_ENV` is EXPLICITLY `dev` / `development` / `test`. Unset
    or unknown is production (safe by default — see `is_dev`).
  * The host is resolved and EVERY address it resolves to must be public: private, loopback,
    link-local, CGNAT (100.64/10), multicast, reserved/unspecified and the metadata address
    (169.254.169.254, fd00:ec2::254) are refused. IPv4-mapped IPv6 is judged as the IPv4 it maps.
  * No userinfo in the URL (credentials in a webhook URL are a leak waiting to be logged).
  * No redirects — enforced by the sender (`follow_redirects=False`), stated here so the rule
    has one home.

`Target.addresses` are the addresses that were checked; the sender connects to one of them
(SNI + Host kept as the name) so a rebinding between the check and the connect cannot redirect
the request (`pinned_request`).
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Callable, Iterable
from urllib.parse import urlsplit, urlunsplit

from genios_engine.platform.config import get_settings

_DEV_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
_METADATA = frozenset({ipaddress.ip_address("169.254.169.254"),
                       ipaddress.ip_address("fd00:ec2::254")})
_CGNAT = ipaddress.ip_network("100.64.0.0/10")

Resolver = Callable[[str, int], Iterable[str]]


class EgressRefused(ValueError):
    """The URL may not be called. `code` is stable and machine-readable; the message is for humans."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Target:
    url: str
    scheme: str
    host: str                     # lower-cased, IPv6 without brackets
    port: int
    addresses: tuple[str, ...]    # the checked addresses; empty = dev loopback (not pinned)


#: The only environments where the loopback exception applies — named EXPLICITLY.
_DEV_ENVS = frozenset({"dev", "development", "test"})


def is_dev(env: str | None = None) -> bool:
    """SAFE BY DEFAULT. `Settings.env` defaults to "dev" for the rest of the engine, but egress does
    not trust that default: an UNSET `GENIOS_ENV` (the field not explicitly provided by the
    environment / .env) or any unknown value is production — https only, localhost refused.
    Local to this module; how other code reads GENIOS_ENV is unchanged."""
    if env is None:
        s = get_settings()
        if "env" not in s.model_fields_set:
            return False
        env = s.env
    return str(env or "").strip().lower() in _DEV_ENVS


def _system_resolver(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [str(i[4][0]).split("%", 1)[0] for i in infos]


def refusal_reason(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Why this address may not be called, or None when it is a public unicast address."""
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    if ip in _METADATA:
        return "metadata_address"
    if ip.version == 4 and ip in _CGNAT:
        return "cgnat_address"
    if ip.is_loopback:
        return "loopback_address"
    if ip.is_link_local:
        return "link_local_address"
    if ip.is_multicast:
        return "multicast_address"
    if ip.is_private:
        return "private_address"
    if ip.is_unspecified or ip.is_reserved or not ip.is_global:
        return "reserved_address"
    return None


def check_url(url: str | None, *, env: str | None = None,
              resolver: Resolver | None = None) -> Target:
    """The URL as a checked `Target`, or `EgressRefused`. Resolves DNS (a name that does not
    resolve is refused — there is nothing to call)."""
    raw = str(url or "").strip()
    if not raw:
        raise EgressRefused("url_missing", "No URL to call.")
    try:
        parts = urlsplit(raw)
        port = parts.port
    except ValueError as e:
        raise EgressRefused("url_invalid", f"Not a valid URL: {e}") from None
    scheme = (parts.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise EgressRefused("scheme_not_allowed", "The URL must start with https://.")
    host = (parts.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise EgressRefused("url_invalid", "The URL has no host.")
    if parts.username is not None or parts.password is not None:
        raise EgressRefused("userinfo_not_allowed", "Credentials may not be embedded in the URL.")
    port = port or (443 if scheme == "https" else 80)
    if host in _DEV_LOOPBACK_HOSTS:
        if not is_dev(env):
            raise EgressRefused("loopback_address",
                                "localhost is only allowed in a development deployment.")
        return Target(raw, scheme, host, port, ())
    if scheme != "https":
        raise EgressRefused("https_required", "The URL must use https:// (http is allowed only "
                                              "for localhost in development).")
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        addresses = [str(literal)]
    else:
        try:
            addresses = list(dict.fromkeys((resolver or _system_resolver)(host, port)))
        except (OSError, UnicodeError) as e:
            raise EgressRefused("dns_unresolvable", f"{host} does not resolve: {e}") from None
        if not addresses:
            raise EgressRefused("dns_unresolvable", f"{host} does not resolve.")
    for a in addresses:
        try:
            ip = ipaddress.ip_address(a)
        except ValueError:
            raise EgressRefused("dns_unresolvable", f"{host} resolved to a non-address.") from None
        reason = refusal_reason(ip)
        if reason is not None:
            raise EgressRefused(reason, f"{host} resolves to a non-public address ({reason}).")
    return Target(raw, scheme, host, port, tuple(addresses))


def pinned_request(target: Target) -> tuple[str, dict, dict]:
    """(url, headers, extensions) that connect to the CHECKED address while presenting the name
    (Host header + TLS SNI, so certificate verification is still against the name). A dev loopback
    target is returned unchanged."""
    if not target.addresses:
        return target.url, {}, {}
    ip = target.addresses[0]
    netloc_ip = f"[{ip}]" if ":" in ip else ip
    parts = urlsplit(target.url)
    default = 443 if target.scheme == "https" else 80
    netloc = netloc_ip if target.port == default else f"{netloc_ip}:{target.port}"
    host_header = target.host if ":" not in target.host else f"[{target.host}]"
    if target.port != default:
        host_header = f"{host_header}:{target.port}"
    url = urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))
    return url, {"Host": host_header}, {"sni_hostname": target.host}


__all__ = ["EgressRefused", "Target", "check_url", "is_dev", "pinned_request", "refusal_reason"]
