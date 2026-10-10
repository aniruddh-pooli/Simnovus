import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(store):
    return TestClient(create_app(store))


def hb(clock, **extra):
    body = {"timestamp": clock().isoformat().replace("+00:00", "Z"), "status": "OK"}
    body.update(extra)
    return body


def register(client, device_id="d1", name="Device 1"):
    return client.post("/devices", json={"id": device_id, "name": name})


def test_register_device(client):
    r = register(client)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "d1" and body["status"] == "OFFLINE" and body["last_heartbeat"] is None


def test_register_duplicate_returns_409(client):
    register(client)
    assert register(client).status_code == 409


@pytest.mark.parametrize(
    "payload",
    [{"id": "", "name": "x"}, {"id": "has space", "name": "x"}, {"id": "a"}, {"name": "x"}],
)
def test_register_invalid_returns_422(client, payload):
    assert client.post("/devices", json=payload).status_code == 422


def test_heartbeat_makes_device_online(client, clock):
    register(client)
    r = client.post("/devices/d1/heartbeat", json=hb(clock, cpu_usage=42, signal_strength=-71))
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ONLINE"
    assert body["last_heartbeat"].startswith("2026-09-21T10:30:00")
    assert body["cpu_usage"] == 42 and body["signal_strength"] == -71


def test_heartbeat_unknown_device_returns_404(client, clock):
    assert client.post("/devices/nope/heartbeat", json=hb(clock)).status_code == 404


@pytest.mark.parametrize(
    "override",
    [{"cpu_usage": 150}, {"timestamp": "not-a-date"}, {"status": ""}],
)
def test_heartbeat_invalid_returns_422(client, clock, override):
    register(client)
    assert client.post("/devices/d1/heartbeat", json=hb(clock, **override)).status_code == 422


def test_heartbeat_missing_status_returns_422(client):
    register(client)
    r = client.post("/devices/d1/heartbeat", json={"timestamp": "2026-09-21T10:30:00Z"})
    assert r.status_code == 422


def test_naive_timestamp_treated_as_utc(client):
    register(client)
    r = client.post("/devices/d1/heartbeat", json={"timestamp": "2026-09-21T10:30:00", "status": "OK"})
    assert r.status_code == 200
    assert r.json()["last_heartbeat"].startswith("2026-09-21T10:30:00")


def test_get_device_and_404(client):
    register(client)
    assert client.get("/devices/d1").json()["id"] == "d1"
    assert client.get("/devices/nope").status_code == 404


def test_30_second_timeout_through_api(client, clock):
    register(client)
    client.post("/devices/d1/heartbeat", json=hb(clock))
    clock.advance(29)
    assert client.get("/devices/d1").json()["status"] == "ONLINE"
    clock.advance(2)  # 31s since last heartbeat
    assert client.get("/devices/d1").json()["status"] == "OFFLINE"
    client.post("/devices/d1/heartbeat", json=hb(clock))
    assert client.get("/devices/d1").json()["status"] == "ONLINE"


def test_list_and_filter_by_status(client, clock):
    register(client, "d1")
    register(client, "d2")
    client.post("/devices/d1/heartbeat", json=hb(clock))
    assert len(client.get("/devices").json()) == 2
    online = client.get("/devices", params={"status": "ONLINE"}).json()
    assert [d["id"] for d in online] == ["d1"]
    offline = client.get("/devices", params={"status": "OFFLINE"}).json()
    assert [d["id"] for d in offline] == ["d2"]
    assert client.get("/devices", params={"status": "bogus"}).status_code == 422


def test_summary(client, clock):
    register(client, "d1")
    register(client, "d2")
    client.post("/devices/d1/heartbeat", json=hb(clock))
    assert client.get("/summary").json() == {"total": 2, "online": 1, "offline": 1}
    clock.advance(31)
    assert client.get("/summary").json() == {"total": 2, "online": 0, "offline": 2}