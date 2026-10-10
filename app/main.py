from typing import List, Optional

from fastapi import FastAPI, HTTPException

from app.models import DeviceIn, DeviceOut, HeartbeatIn, Status, SummaryOut
from app.store import Device, DeviceStore, DuplicateDevice, UnknownDevice


def to_out(d: Device) -> DeviceOut:
    return DeviceOut(
        id=d.id,
        name=d.name,
        status=Status.ONLINE if d.online else Status.OFFLINE,
        last_heartbeat=d.last_heartbeat,
        last_status=d.last_status,
        cpu_usage=d.cpu_usage,
        signal_strength=d.signal_strength,
    )


def create_app(store: Optional[DeviceStore] = None) -> FastAPI:
    store = store if store is not None else DeviceStore()
    app = FastAPI(title="Mini Device Fleet Monitor")

    @app.post("/devices", response_model=DeviceOut, status_code=201)
    def register_device(body: DeviceIn):
        try:
            return to_out(store.register(body.id, body.name))
        except DuplicateDevice:
            raise HTTPException(409, f"Device '{body.id}' already exists")

    @app.post("/devices/{device_id}/heartbeat", response_model=DeviceOut)
    def heartbeat(device_id: str, body: HeartbeatIn):
        try:
            return to_out(
                store.heartbeat(
                    device_id, body.timestamp, body.status, body.cpu_usage, body.signal_strength
                )
            )
        except UnknownDevice:
            raise HTTPException(404, f"Device '{device_id}' not found")

    @app.get("/devices", response_model=List[DeviceOut])
    def list_devices(status: Optional[Status] = None):
        devices = [to_out(d) for d in store.list()]
        return [d for d in devices if status is None or d.status == status]

    @app.get("/devices/{device_id}", response_model=DeviceOut)
    def get_device(device_id: str):
        try:
            return to_out(store.get(device_id))
        except UnknownDevice:
            raise HTTPException(404, f"Device '{device_id}' not found")

    @app.get("/summary", response_model=SummaryOut)
    def summary():
        return store.summary()

    return app


app = create_app()