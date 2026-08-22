"""Time, as a dependency.

Every read in Grid Lab asks a clock what "now" means. In live mode that is wall time; in
replay mode it is a point inside a recorded day, advancing at whatever multiple of real
time we choose.

This one indirection buys three things that would each be worth it alone:

* the whole system is testable offline and deterministically;
* a demo can play a real historical event on demand, instead of hoping the live grid does
  something interesting at 17:00;
* the API key can arrive later — the trial should not be started until early September,
  and nothing here waits for it.

See ``docs/adr/0004-live-vs-replay-clock.md``.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Something that can say what time it is."""

    def now(self) -> datetime:
        """The current instant, timezone-aware, UTC."""
        ...


class LiveClock:
    """Wall time."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def __repr__(self) -> str:
        return "LiveClock()"


class ReplayClock:
    """A clock positioned inside a recorded window, optionally running fast.

    Construction pins ``t0``; the clock then advances at ``speed`` times real time from the
    moment it was started. At speed 60, one real second is one simulated minute, so a
    24-hour day plays in 24 minutes — and at 1440 it plays in one.

    The clock can be paused, resumed and moved, because a demo is a performance: being able
    to stop on the interesting hour and talk over it matters more than smooth playback.
    """

    def __init__(
        self,
        start: datetime,
        *,
        end: datetime | None = None,
        speed: float = 60.0,
        loop: bool = True,
    ) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        if end is not None and end <= start:
            raise ValueError("end must be after start")

        self._start = _as_utc(start)
        self._end = _as_utc(end) if end else None
        self._speed = speed
        self._loop = loop

        self._position = self._start
        self._anchor: float | None = time.monotonic()

    # -- reading -------------------------------------------------------------

    def now(self) -> datetime:
        moment = self._position
        if self._anchor is not None:
            elapsed = time.monotonic() - self._anchor
            moment = self._position + timedelta(seconds=elapsed * self._speed)

        if self._end is None:
            return moment

        if moment <= self._end:
            return moment

        if not self._loop:
            return self._end

        # Wrap, so an unattended demo screen keeps moving instead of freezing on the last
        # frame. Modulo rather than reset, so the position stays continuous.
        span = (self._end - self._start).total_seconds()
        overshoot = (moment - self._start).total_seconds() % span
        return self._start + timedelta(seconds=overshoot)

    @property
    def running(self) -> bool:
        return self._anchor is not None

    @property
    def speed(self) -> float:
        return self._speed

    @property
    def window(self) -> tuple[datetime, datetime | None]:
        return self._start, self._end

    # -- transport controls --------------------------------------------------

    def pause(self) -> None:
        if self._anchor is None:
            return
        self._position = self.now()
        self._anchor = None

    def resume(self) -> None:
        if self._anchor is not None:
            return
        self._anchor = time.monotonic()

    def seek(self, moment: datetime) -> None:
        """Jump to an instant, clamped to the recorded window."""
        target = _as_utc(moment)
        if target < self._start:
            target = self._start
        if self._end is not None and target > self._end:
            target = self._end
        self._position = target
        if self._anchor is not None:
            self._anchor = time.monotonic()

    def set_speed(self, speed: float) -> None:
        if speed <= 0:
            raise ValueError("speed must be positive")
        # Bank the elapsed simulated time before changing the rate, or the new speed is
        # retroactively applied to time already played.
        self._position = self.now()
        if self._anchor is not None:
            self._anchor = time.monotonic()
        self._speed = speed

    def progress(self) -> float:
        """Position within the window, 0.0 to 1.0. Returns 0.0 for an open-ended clock."""
        if self._end is None:
            return 0.0
        span = (self._end - self._start).total_seconds()
        return min(1.0, max(0.0, (self.now() - self._start).total_seconds() / span))

    def __repr__(self) -> str:
        state = "running" if self.running else "paused"
        return f"ReplayClock({self.now().isoformat()}, {state}, x{self._speed:g})"


class FrozenClock:
    """A clock that does not move. For tests that must be exactly reproducible."""

    def __init__(self, moment: datetime) -> None:
        self._moment = _as_utc(moment)

    def now(self) -> datetime:
        return self._moment

    def set(self, moment: datetime) -> None:
        self._moment = _as_utc(moment)

    def advance(self, delta: timedelta) -> None:
        self._moment += delta

    def __repr__(self) -> str:
        return f"FrozenClock({self._moment.isoformat()})"


def _as_utc(moment: datetime) -> datetime:
    """Naive datetimes are assumed UTC. Everything internal is already UTC."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)
