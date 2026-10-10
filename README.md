# Mini Device Fleet Monitor

A small HTTP service that tracks heartbeats from a fleet of devices and reports each one as ONLINE (heartbeat received in the last 30 seconds) or OFFLINE. Includes a device simulator and automated tests.

## Design

- `app/models.py` validates input (Pydantic), `app/store.py` holds all logic, `app/main.py` is a thin FastAPI layer mapping errors to 404, 409 and 422.
- The store is an in-memory registry guarded by one lock, and returns copies so callers can't modify stored state outside it.
- **Status is computed on every read and never stored**, so it can't go stale and needs no background thread or timer.
- **Liveness uses the server's receive time**, not the device's timestamp, so a device with a wrong clock still gets the right status.
- The clock is injected into the store, so tests simulate time passing instead of waiting 30 seconds.

## Prerequisites

Python 3.9 or newer (tested on 3.13).

## Build

```bash
git clone https://github.com/aniruddh-pooli/Simnovus.git
cd Simnovus
python -m venv .venv
source .venv/bin/activate        
pip install -r requirements.txt
```

No compile step.

## Run the application

```bash
python -m uvicorn app.main:app --port 8000
```

Interactive API docs: http://127.0.0.1:8000/docs

## Run the simulator

With the server running, in a second terminal (venv active):

```bash
python simulator/simulate.py                        # 5 devices, heartbeat every 5s
python simulator/simulate.py --drop device-03:20    # device-03 stops after 20s
```

Options: `--url`, `--devices`, `--interval`, `--drop DEVICE_ID:SECONDS` (repeatable). A fleet summary prints every interval; a dropped device shows as OFFLINE about 30 seconds after it stops. Ctrl+C quits.

## Run the tests

```bash
python -m pytest -v
```

Covers registration, heartbeats, validation, error codes, status, summary and the 30-second boundary (ONLINE at exactly 30s, OFFLINE at 30.001s). Timeout tests use a fake clock, so there are no sleeps.

## Example requests

```bash
curl -X POST localhost:8000/devices -H 'Content-Type: application/json' \
  -d '{"id":"device-01","name":"Lab Device 01"}'

curl -X POST localhost:8000/devices/device-01/heartbeat -H 'Content-Type: application/json' \
  -d '{"timestamp":"2026-09-21T10:30:00Z","status":"OK","cpu_usage":42,"signal_strength":-71}'

curl localhost:8000/devices
curl "localhost:8000/devices?status=OFFLINE"
curl localhost:8000/devices/device-01
curl localhost:8000/summary     # {"total": 5, "online": 4, "offline": 1}
```

| Endpoint                                          | Success | Errors                                          |
|---------------------------------------------------|---------|-------------------------------------------------|
| POST /devices                                     | 201     | 409 duplicate id, 422 invalid body              |
| POST /devices/{id}/heartbeat                      | 200     | 404 unknown device, 422 invalid body            |
| GET /devices (optional ?status=ONLINE or OFFLINE) | 200     | 422 invalid filter                              |
| GET /devices/{id}                                 | 200     | 404 unknown device                              |
| GET /summary                                      | 200     | none |

Error examples:

```bash
curl -i localhost:8000/devices/nope
# 404 {"detail":"Device 'nope' not found"}

curl -i -X POST localhost:8000/devices -H 'Content-Type: application/json' \
  -d '{"id":"device-01","name":"dup"}'
# 409 {"detail":"Device 'device-01' already exists"}

curl -i -X POST localhost:8000/devices -H 'Content-Type: application/json' \
  -d '{"id":"has space","name":"x"}'
# 422 Pydantic validation error
```

## Assumptions

- A device that never sent a heartbeat is OFFLINE (`last_heartbeat` is null).
- A heartbeat exactly 30s old still counts as ONLINE.
- Timestamps without a timezone are treated as UTC.
- Re-registering an existing id returns 409.
- Heartbeats require `timestamp` and `status`; `cpu_usage` and `signal_strength` are optional.
- Device ids may contain letters, digits, `.`, `_` and `-`.
- An out-of-order heartbeat proves the device is alive but doesn't overwrite newer data.


## Known limitations

- In memory only: a restart loses all devices, and a running simulator then gets 404s until restarted.
- Single process; separate workers would not share state.
- No authentication, heartbeat history, alerts or device deletion.
- A device stopped with `--drop` can't be restarted without restarting the simulator.

## With one more day

- SQLite persistence and heartbeat history.
- Per-device authentication tokens.
- Record and alert on ONLINE/OFFLINE transitions.
- Simulator re-registers devices after a 404.
- Dockerfile and CI.

## AI Usage

- Tools used: ChatGPT

- Used for: Driving test case ideation, reviewing implementation correctness, and brainstorming simulator architecture.

- Changed or rejected: Rejected the initial suggestion of running only continuous heartbeats; instead, refined the simulator approach to support stopping and resuming individual devices through a control API.

- Personally verified: Ran the automated test suite and manually tested the backend and simulator to verify device registration, heartbeat handling, and correct online/offline status transitions.