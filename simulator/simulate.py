import argparse
import random
import sys
import threading
import time
from datetime import datetime, timezone

import httpx


def parse_drop(value: str):
    device_id, _, seconds = value.partition(":")
    try:
        return device_id, float(seconds)
    except ValueError:
        raise argparse.ArgumentTypeError("expected DEVICE_ID:SECONDS, e.g. device-03:20")


def run_device(client, device_id, interval, stop, drop_after):
    started = time.monotonic()
    while not stop.is_set():
        if drop_after is not None and time.monotonic() - started >= drop_after:
            print(f"[{device_id}] simulated failure: no more heartbeats")
            return
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "OK",
            "cpu_usage": round(random.uniform(10, 80), 1),
            "signal_strength": random.randint(-90, -50),
        }
        try:
            client.post(f"/devices/{device_id}/heartbeat", json=payload).raise_for_status()
            print(f"[{device_id}] heartbeat sent")
        except httpx.HTTPError as e:
            print(f"[{device_id}] heartbeat failed: {e}")
        stop.wait(interval)


def main():
    p = argparse.ArgumentParser(description="Device heartbeat simulator")
    p.add_argument("--url", default="http://127.0.0.1:8000")
    p.add_argument("--devices", type=int, default=5)
    p.add_argument("--interval", type=float, default=5.0, help="seconds between heartbeats")
    p.add_argument("--drop", type=parse_drop, action="append", default=[],
                   metavar="DEVICE_ID:SECONDS", help="stop a device after N seconds (repeatable)")
    args = p.parse_args()

    ids = [f"device-{i:02d}" for i in range(1, args.devices + 1)]
    drops = dict(args.drop)
    stop = threading.Event()

    with httpx.Client(base_url=args.url, timeout=5) as client:
        try:
            for n, device_id in enumerate(ids, start=1):
                r = client.post("/devices", json={"id": device_id, "name": f"Lab Device {n:02d}"})
                if r.status_code not in (201, 409):  
                    r.raise_for_status()
        except httpx.HTTPError as e:
            sys.exit(f"Cannot reach the server at {args.url}: {e}\nIs it running?")

        for device_id in ids:
            threading.Thread(
                target=run_device,
                args=(client, device_id, args.interval, stop, drops.get(device_id)),
                daemon=True,
            ).start()

        print(f"Simulating {len(ids)} devices. Ctrl+C to stop.\n")
        try:
            while True:
                stop.wait(args.interval)
                s = client.get("/summary").json()
                down = [d["id"] for d in client.get("/devices", params={"status": "OFFLINE"}).json()]
                print(f"--- fleet: {s['online']} online / {s['offline']} offline {down or ''}")
        except KeyboardInterrupt:
            stop.set()
            print("\nStopped.")


if __name__ == "__main__":
    main()