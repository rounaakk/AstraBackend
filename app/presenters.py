"""Map stored records to API models."""

from datetime import timedelta

from app.models import BirthDetails, UserRecord
from app.schemas.kundali import KundaliOut
from app.schemas.user import BirthDetailsOut, UserOut
from app.services.auth import IssuedTokens
from app.schemas.auth import AuthResponse
from app.store.memory import store


def birth_details_out(birth: BirthDetails) -> BirthDetailsOut:
    offset = birth.local_datetime.utcoffset() or timedelta(0)
    total_seconds = int(offset.total_seconds())
    sign = "+" if total_seconds >= 0 else "-"
    total_seconds = abs(total_seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes = remainder // 60
    return BirthDetailsOut(
        date_of_birth=birth.date_of_birth,
        time_of_birth=birth.time_of_birth,
        place_of_birth=birth.place_of_birth,
        resolved_name=birth.resolved_name,
        region=birth.region,
        country=birth.country,
        label=birth.label,
        latitude=birth.latitude,
        longitude=birth.longitude,
        timezone=birth.timezone,
        utc_offset=f"{sign}{hours:02d}:{minutes:02d}",
        local_datetime=birth.local_datetime,
        utc_datetime=birth.utc_datetime,
    )


def user_out(user: UserRecord) -> UserOut:
    return UserOut(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        gender=user.gender,  # type: ignore[arg-type]
        created_at=user.created_at,
        updated_at=user.updated_at,
        birth_details=birth_details_out(user.birth) if user.birth else None,
        has_kundali=store.get_kundali(user.id) is not None,
    )


def stored_kundali(user_id: str) -> KundaliOut | None:
    chart = store.get_kundali(user_id)
    if chart is None:
        return None
    return KundaliOut.model_validate(chart)


def auth_response(user: UserRecord, tokens: IssuedTokens) -> AuthResponse:
    return AuthResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
        user=user_out(user),
        kundali=stored_kundali(user.id),
    )
