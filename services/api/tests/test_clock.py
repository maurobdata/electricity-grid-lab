"""The clock is what makes replay and live the same code path, so it gets pinned."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from gridlab.clock import Clock, FrozenClock, LiveClock, ReplayClock

T0 = datetime(2026, 2, 4, 0, tzinfo=UTC)
T_END = datetime(2026, 2, 5, 23, tzinfo=UTC)


def test_all_three_satisfy_the_protocol() -> None:
    """Runtime-checkable, so a wrong object fails at wiring time rather than in a handler."""
    assert isinstance(LiveClock(), Clock)
    assert isinstance(FrozenClock(T0), Clock)
    assert isinstance(ReplayClock(T0), Clock)


def test_live_clock_is_utc_aware() -> None:
    """A naive datetime anywhere in this system eventually becomes a one-hour-wrong chart."""
    assert LiveClock().now().tzinfo is UTC


def test_replay_starts_at_t0() -> None:
    clock = ReplayClock(T0, end=T_END, speed=1.0)
    assert abs((clock.now() - T0).total_seconds()) < 0.5


def test_speed_multiplies_elapsed_time() -> None:
    clock = ReplayClock(T0, end=T_END, speed=3600.0)  # one real second is one sim hour
    time.sleep(0.05)
    elapsed = (clock.now() - T0).total_seconds()
    assert 100 < elapsed < 900


def test_pause_freezes_and_resume_continues() -> None:
    clock = ReplayClock(T0, end=T_END, speed=3600.0)
    time.sleep(0.02)
    clock.pause()
    frozen = clock.now()
    time.sleep(0.05)
    assert clock.now() == frozen
    assert not clock.running

    clock.resume()
    time.sleep(0.02)
    assert clock.now() > frozen
    assert clock.running


def test_seek_moves_to_an_instant() -> None:
    clock = ReplayClock(T0, end=T_END, speed=1.0)
    target = datetime(2026, 2, 5, 18, tzinfo=UTC)
    clock.seek(target)
    assert abs((clock.now() - target).total_seconds()) < 0.5


def test_seek_clamps_to_the_window() -> None:
    """A scrubber dragged off the end must not produce a timestamp with no data behind it."""
    clock = ReplayClock(T0, end=T_END, speed=1.0)
    clock.pause()

    clock.seek(T0 - timedelta(days=10))
    assert clock.now() == T0

    clock.seek(T_END + timedelta(days=10))
    assert clock.now() == T_END


def test_changing_speed_does_not_rewrite_history() -> None:
    """Elapsed simulated time is banked before the rate changes.

    Without that, switching from 1x to 3600x would retroactively apply the new speed to
    time already played and jump the clock forward by hours.
    """
    clock = ReplayClock(T0, end=T_END, speed=1.0)
    time.sleep(0.05)
    before = clock.now()
    clock.set_speed(3600.0)
    after = clock.now()
    assert after >= before
    assert (after - before).total_seconds() < 60


def test_speed_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        ReplayClock(T0, speed=0)
    with pytest.raises(ValueError, match="positive"):
        ReplayClock(T0, speed=1.0).set_speed(-1)


def test_end_must_follow_start() -> None:
    with pytest.raises(ValueError, match="after start"):
        ReplayClock(T_END, end=T0)


def test_looping_wraps_instead_of_freezing() -> None:
    """An unattended demo screen should keep moving, not stall on the last frame."""
    clock = ReplayClock(T0, end=T0 + timedelta(seconds=10), speed=1000.0, loop=True)
    time.sleep(0.05)
    now = clock.now()
    assert T0 <= now <= T0 + timedelta(seconds=10)


def test_non_looping_stops_at_the_end() -> None:
    clock = ReplayClock(T0, end=T0 + timedelta(seconds=1), speed=1000.0, loop=False)
    time.sleep(0.05)
    assert clock.now() == T0 + timedelta(seconds=1)


def test_progress_is_a_fraction_of_the_window() -> None:
    clock = ReplayClock(T0, end=T_END, speed=1.0)
    clock.pause()
    clock.seek(T0 + (T_END - T0) / 2)
    assert clock.progress() == pytest.approx(0.5, abs=0.01)


def test_open_ended_clock_reports_zero_progress() -> None:
    assert ReplayClock(T0, speed=1.0).progress() == 0.0


def test_frozen_clock_does_not_move() -> None:
    clock = FrozenClock(T0)
    first = clock.now()
    time.sleep(0.02)
    assert clock.now() == first

    clock.advance(timedelta(hours=3))
    assert clock.now() == T0 + timedelta(hours=3)


def test_naive_datetimes_are_accepted_as_utc() -> None:
    """Everything internal is UTC; a stray naive value should not raise mid-demo."""
    assert FrozenClock(datetime(2026, 2, 4)).now() == T0
