from datetime import datetime, timedelta, timezone

import pytest

from app.store import DeviceStore


class FakeClock:
    def __init__(self):
        self.now = datetime(2026, 9, 21, 10, 30, tzinfo=timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += timedelta(seconds=seconds)


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def store(clock):
    return DeviceStore(clock=clock)