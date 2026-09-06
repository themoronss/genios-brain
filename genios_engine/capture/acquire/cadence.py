"""L1.2.6-U1 · Per-source polling cadence.

One global `sync_interval_hours = 6.0` polled a mailbox and a quarterly-updated Notion page at
exactly the same rate, which is wrong in both directions at once: mail arrives every minute and
was six hours stale, while Notion was re-listed four times a day to find nothing. Cadence is a
property of the SOURCE, and it is CONFIGURATION rather than a constant — an operator retunes a
provider's poll rate from the environment, and a single connection whose owner wants tighter or
looser polling carries its own override in `Connection.config`.

Everything here is integer SECONDS. A cadence expressed as `0.25` hours is a float that has to be
multiplied by 3600 at every use site, and the one place that forgets is a schedule nobody can
explain; the parser accepts the human form (`15m`, `12h`) once, at the edge, and every value that
crosses a boundary afterwards is an int.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from genios_engine.contracts.connection import Connection

#: Nothing may poll faster than this. A 10-second cadence is not a cadence, it is a denial of
#: service against the provider that will end in a rate-limit ban for every tenant on the key.
MIN_INTERVAL_SECONDS = 60
#: Nor slower than this: a source polled less than weekly is indistinguishable from a source that
#: silently stopped, and a cursor that old makes every resume a catch-up.
MAX_INTERVAL_SECONDS = 7 * 24 * 3600

_UNITS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_DURATION = re.compile(r"^(\d+)([smhd]?)$")


@dataclass(frozen=True)
class SourceCadence:
    """One row of the policy: this source polls every `interval_seconds`."""
    source: str
    interval_seconds: int


@dataclass(frozen=True)
class CadencePolicy:
    """The whole configured table plus the fallback for a source nobody has tuned yet.

    A tuple of typed rows rather than a `dict[str, int]` so the policy can cross a function
    boundary as a value with a shape, and so an operator's typo (`gmial=15m`) is inspectable
    instead of being a key that silently never matches.
    """
    entries: tuple[SourceCadence, ...]
    default_seconds: int

    def interval_for(self, source: str) -> int:
        for e in self.entries:
            if e.source == source:
                return e.interval_seconds
        return self.default_seconds

    def has(self, source: str) -> bool:
        return any(e.source == source for e in self.entries)


def parse_duration_seconds(raw: str) -> int:
    """`15m` / `12h` / `900` / `1d` -> integer seconds. Raises on anything else.

    Loud, because this parses operator configuration at startup: a cadence string the parser did
    not understand must not degrade to "the default", which looks exactly like a working config.
    """
    m = _DURATION.match(raw.strip().lower())
    if not m:
        raise ValueError(f"unparseable cadence duration: {raw!r} (expected e.g. 15m, 2h, 900)")
    return int(m.group(1)) * _UNITS[m.group(2) or "s"]


#: The shipped table. Gmail polls fast because the poll is the SAFETY NET behind a webhook, not
#: the primary path; Notion polls at 12h because a page edited quarterly does not repay a list
#: call every hour. Numbers straight out of the L1.2.6-U1 plan, in seconds.
DEFAULT_CADENCE_POLICY = CadencePolicy(
    entries=(
        SourceCadence("gmail", 15 * 60),
        SourceCadence("gcal", 3600),
        SourceCadence("hubspot", 2 * 3600),
        SourceCadence("notion", 12 * 3600),
        SourceCadence("gdrive", 6 * 3600),
        SourceCadence("database", 3600),
    ),
    #: the historical `sync_interval_hours` — an unknown source behaves exactly as it does today
    default_seconds=6 * 3600,
)


def load_cadence_policy(spec: str | None, *,
                        base: CadencePolicy = DEFAULT_CADENCE_POLICY) -> CadencePolicy:
    """Overlay an operator's `"gmail=5m,notion=1d"` string onto the shipped table.

    Overlay rather than replace: an operator retuning gmail must not have to restate hubspot,
    and a source dropped from the string keeps the reviewed default instead of falling back to
    the coarse catch-all. `default=` sets the fallback for unlisted sources.
    """
    if not spec or not spec.strip():
        return base
    entries = {e.source: e.interval_seconds for e in base.entries}
    default_seconds = base.default_seconds
    for part in spec.split(","):
        if not part.strip():
            continue
        if "=" not in part:
            raise ValueError(f"cadence spec entry must be source=duration, got {part!r}")
        source, raw = part.split("=", 1)
        source = source.strip().lower()
        seconds = parse_duration_seconds(raw)
        if not MIN_INTERVAL_SECONDS <= seconds <= MAX_INTERVAL_SECONDS:
            raise ValueError(
                f"cadence for {source!r} is {seconds}s, outside "
                f"[{MIN_INTERVAL_SECONDS}, {MAX_INTERVAL_SECONDS}]")
        if source == "default":
            default_seconds = seconds
        else:
            entries[source] = seconds
    return CadencePolicy(
        entries=tuple(SourceCadence(s, entries[s]) for s in sorted(entries)),
        default_seconds=default_seconds)


def connection_override_seconds(connection: Connection) -> int | None:
    """The per-connection cadence override, read out of `Connection.config`.

    Lives here so the untyped `config` dict is opened at exactly one place and an `int | None`
    is what the scheduler ever sees. An unusable value (a word, a negative, a list) is ignored
    rather than raised on: this is tenant-authored JSON reached from a background sweep, and one
    bad row must not take the sweep down for every other org. Out-of-range numbers are NOT
    ignored — they are clamped by `resolve_cadence`, which records that it happened.
    """
    cfg = connection.config or {}
    raw = cfg.get("cadence_seconds")
    if isinstance(raw, bool):                      # bool is an int in Python; never a cadence
        raw = None
    if isinstance(raw, (int, float)) and raw > 0:
        return int(raw)
    minutes = cfg.get("cadence_minutes")
    if isinstance(minutes, bool):
        minutes = None
    if isinstance(minutes, (int, float)) and minutes > 0:
        return int(minutes * 60)
    text = cfg.get("cadence")
    if isinstance(text, str):
        try:
            return parse_duration_seconds(text)
        except ValueError:
            return None
    return None


@dataclass(frozen=True)
class CadenceRequest:
    source: str
    override_seconds: int | None = None


@dataclass(frozen=True)
class Cadence:
    """The resolved interval and WHY it is that number.

    `origin` exists so an admin console can answer "why is this connection polling every 6
    hours" without re-deriving the decision: `default` means nobody tuned this source,
    `override_clamped` means a tenant asked for something the platform refused.
    """
    source: str
    interval_seconds: int
    origin: str            # override | override_clamped | policy | default


def resolve_cadence(request: CadenceRequest, *,
                    policy: CadencePolicy = DEFAULT_CADENCE_POLICY) -> Cadence:
    """Per-source cadence, with the per-connection override taking precedence — U1's public unit."""
    if request.override_seconds is not None:
        wanted = int(request.override_seconds)
        clamped = max(MIN_INTERVAL_SECONDS, min(MAX_INTERVAL_SECONDS, wanted))
        return Cadence(request.source, clamped,
                       "override" if clamped == wanted else "override_clamped")
    source = request.source
    if policy.has(source):
        return Cadence(source, policy.interval_for(source), "policy")
    return Cadence(source, policy.default_seconds, "default")
