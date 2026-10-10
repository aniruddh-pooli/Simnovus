from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class Status(str, Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"


class DeviceIn(BaseModel):
    id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    name: str = Field(min_length=1, max_length=128)


class HeartbeatIn(BaseModel):
    timestamp: datetime
    status: str = Field(min_length=1, max_length=32)
    cpu_usage: Optional[float] = Field(default=None, ge=0, le=100)
    signal_strength: Optional[int] = None

    @field_validator("timestamp")
    @classmethod
    def to_utc(cls, v: datetime) -> datetime:
        # Naive timestamps are assumed to be UTC.
        return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


class DeviceOut(BaseModel):
    id: str
    name: str
    status: Status
    last_heartbeat: Optional[datetime] = None
    last_status: Optional[str] = None
    cpu_usage: Optional[float] = None
    signal_strength: Optional[int] = None


class SummaryOut(BaseModel):
    total: int
    online: int
    offline: int