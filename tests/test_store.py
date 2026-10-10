from datetime import timedelta

import pytest

from app.store import DuplicateDevice, UnknownDevice


def test_register_creates_offline_device(store):
    d = store.register("d1", "Device 1")
    assert (d.id, d.name) == ("d1", "Device 1")
    assert d.last_heartbeat is None
    assert d.online is False


def test_register_duplicate_rejected(store):
    store.register("d1", "A")
    with pytest.raises(DuplicateDevice):
        store.register("d1", "B")


def test_heartbeat_unknown_device(store, clock):
    with pytest.raises(UnknownDevice):
        store.heartbeat("nope", clock(), "OK")


def test_heartbeat_marks_online_and_stores_metrics(store, clock):
    store.register("d1", "A")
    d = store.heartbeat("d1", clock(), "OK", cpu_usage=42, signal_strength=-71)
    assert d.online is True
    assert d.last_heartbeat == clock()
    assert (d.last_status, d.cpu_usage, d.signal_strength) == ("OK", 42, -71)


def test_online_exactly_at_timeout(store, clock):
    store.register("d1", "A")
    store.heartbeat("d1", clock(), "OK")
    clock.advance(30)
    assert store.get("d1").online is True


def test_offline_just_after_timeout(store, clock):
    store.register("d1", "A")
    store.heartbeat("d1", clock(), "OK")
    clock.advance(30.001)
    assert store.get("d1").online is False


def test_heartbeat_revives_offline_device(store, clock):
    store.register("d1", "A")
    store.heartbeat("d1", clock(), "OK")
    clock.advance(60)
    assert store.get("d1").online is False
    store.heartbeat("d1", clock(), "OK")
    assert store.get("d1").online is True


def test_never_heartbeated_device_stays_offline(store, clock):
    store.register("d1", "A")
    clock.advance(1000)
    assert store.get("d1").online is False


def test_liveness_uses_server_time_not_device_timestamp(store, clock):
    store.register("d1", "A")
    d = store.heartbeat("d1", clock() - timedelta(days=1), "OK")
    assert d.online is True


def test_out_of_order_heartbeat_does_not_move_data_backwards(store, clock):
    store.register("d1", "A")
    t = clock()
    store.heartbeat("d1", t, "OK", cpu_usage=10)
    d = store.heartbeat("d1", t - timedelta(seconds=10), "OK", cpu_usage=99)
    assert d.last_heartbeat == t
    assert d.cpu_usage == 10


def test_summary_counts(store, clock):
    for i in ("d1", "d2", "d3"):
        store.register(i, i)
    store.heartbeat("d1", clock(), "OK")
    clock.advance(20)
    store.heartbeat("d2", clock(), "OK")
    clock.advance(15)  # d1 is 35s old (offline), d2 is 15s old (online), d3 never seen
    assert store.summary() == {"total": 3, "online": 1, "offline": 2}