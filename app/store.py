import threading
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, List, Optional

OFFLINE_AFTER = timedelta(seconds=30)


class DuplicateDevice(Exception):
    pass


class UnknownDevice(Exception):
    pass


@dataclass
class Device:
    id: str
    name: str
    last_heartbeat: Optional[datetime] = None  
    received_at: Optional[datetime] = None     
    last_status: Optional[str] = None
    cpu_usage: Optional[float] = None
    signal_strength: Optional[int] = None
    online: bool = False                       

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DeviceStore:
    def __init__(
        self,
        clock: Callable[[], datetime] = utcnow,
        timeout: timedelta = OFFLINE_AFTER,
    ):
        self._clock = clock
        self._timeout = timeout
        self._devices: Dict[str, Device] = {}
        self._lock = threading.Lock()

    def register(self, device_id: str, name: str) -> Device:
        with self._lock:
            if device_id in self._devices:
                raise DuplicateDevice(device_id)
            device = Device(id=device_id, name=name)
            self._devices[device_id] = device
            return self._view(device, self._clock())

    def heartbeat(
        self,
        device_id: str,
        timestamp: datetime,
        status: str,
        cpu_usage: Optional[float] = None,
        signal_strength: Optional[int] = None,
    ) -> Device:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                raise UnknownDevice(device_id)
            now = self._clock()
            device.received_at = now
            if device.last_heartbeat is None or timestamp >= device.last_heartbeat:
                device.last_heartbeat = timestamp
                device.last_status = status
                device.cpu_usage = cpu_usage
                device.signal_strength = signal_strength
            return self._view(device, now)

    def get(self, device_id: str) -> Device:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                raise UnknownDevice(device_id)
            return self._view(device, self._clock())

    def list(self) -> List[Device]:
        with self._lock:
            now = self._clock()
            return [self._view(d, now) for d in self._devices.values()]

    def summary(self) -> Dict[str, int]:
        devices = self.list()
        online = sum(d.online for d in devices)
        return {"total": len(devices), "online": online, "offline": len(devices) - online}

    def _view(self, device: Device, now: datetime) -> Device:
        online = device.received_at is not None and now - device.received_at <= self._timeout
        return replace(device, online=online)