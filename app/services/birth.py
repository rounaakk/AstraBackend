"""Turn birth input into a timezone-aware birth instant."""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.errors import FutureBirthError
from app.models import BirthDetails
from app.schemas.user import BirthDetailsIn
from app.services.geocode import resolve_place


def build_birth_details(payload: BirthDetailsIn) -> BirthDetails:
    resolved = resolve_place(
        payload.place_of_birth,
        payload.latitude,
        payload.longitude,
        payload.timezone,
    )
    tz = ZoneInfo(resolved.timezone)
    local_dt = datetime.combine(payload.date_of_birth, payload.time_of_birth, tzinfo=tz)
    if local_dt > datetime.now(tz) + timedelta(minutes=5):
        raise FutureBirthError("Date and time of birth cannot be in the future")
    return BirthDetails(
        date_of_birth=payload.date_of_birth,
        time_of_birth=payload.time_of_birth.replace(microsecond=0),
        place_of_birth=payload.place_of_birth,
        resolved_name=resolved.name,
        region=resolved.region,
        country=resolved.country,
        label=resolved.label,
        latitude=round(resolved.latitude, 6),
        longitude=round(resolved.longitude, 6),
        timezone=resolved.timezone,
        local_datetime=local_dt,
        utc_datetime=local_dt.astimezone(timezone.utc),
    )
