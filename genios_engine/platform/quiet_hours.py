"""A quiet window in a person's own local time — the shared primitive.

Cross-cutting (platform) so a Layer 4 reader can ask "is it quiet for this seat now?" without
importing Layer 6's delivery model. Same rules as `deliver/timing.AttentionProfile.is_quiet`:
start inclusive, end exclusive, a start after the end wraps midnight, weekends optionally quiet,
an equal start and end is REFUSED (zero hours or twenty-four? — ambiguity that would silently mute
a channel forever), and an unknown timezone is refused rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


@dataclass(frozen=True, slots=True)
class QuietWindow:
    timezone: str = "UTC"
    start_hour: int = 21                  # local hour the window opens, inclusive
    end_hour: int = 8                     # local hour it closes, exclusive
    weekends: bool = False                # Saturday and Sunday entirely quiet

    def __post_init__(self) -> None:
        for label, hour in (("start_hour", self.start_hour), ("end_hour", self.end_hour)):
            if isinstance(hour, bool) or not isinstance(hour, int) or not 0 <= hour <= 23:
                raise ValueError(f"{label} must be an integer hour 0..23")
        if self.start_hour == self.end_hour:
            raise ValueError("start_hour and end_hour are equal: no window, or a silent one")
        try:
            ZoneInfo(str(self.timezone))
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone {self.timezone!r}") from exc

    @property
    def zone(self) -> ZoneInfo:
        return ZoneInfo(str(self.timezone))

    def is_quiet(self, local: datetime) -> bool:
        """Is this local wall-clock moment inside the window?"""
        if self.weekends and local.weekday() >= 5:            # Saturday=5, Sunday=6
            return True
        if self.start_hour < self.end_hour:                   # 00:00–08:00, same day
            return self.start_hour <= local.hour < self.end_hour
        return local.hour >= self.start_hour or local.hour < self.end_hour

    def is_quiet_at(self, instant: datetime) -> bool:
        """`is_quiet` for an aware instant, converted into the window's zone."""
        return self.is_quiet(instant.astimezone(self.zone))


__all__ = ["QuietWindow"]
