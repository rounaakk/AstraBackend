"""In-memory records for accounts, birth details, and sessions."""

from dataclasses import dataclass
from datetime import date, datetime, time


@dataclass
class BirthDetails:
    date_of_birth: date
    time_of_birth: time
    place_of_birth: str
    resolved_name: str
    region: str
    country: str
    label: str
    latitude: float
    longitude: float
    timezone: str
    local_datetime: datetime
    utc_datetime: datetime


@dataclass
class UserRecord:
    id: str
    full_name: str
    email: str
    phone: str
    password_hash: str
    gender: str | None
    created_at: datetime
    updated_at: datetime
    token_version: int = 0
    birth: BirthDetails | None = None


@dataclass
class RefreshSession:
    token: str
    user_id: str
    expires_at: datetime
