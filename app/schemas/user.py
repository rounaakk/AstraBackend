"""Account and birth-detail payloads."""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.validation import clean_name, normalize_phone, password_strength


class BirthDetailsIn(BaseModel):
    date_of_birth: date = Field(description="Local date of birth, YYYY-MM-DD")
    time_of_birth: time = Field(description="Local time of birth")
    place_of_birth: str = Field(min_length=2, max_length=120, description="City or place name")
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    timezone: str | None = Field(
        default=None,
        description="IANA timezone, for example Asia/Kolkata. Resolved from the place when omitted.",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date_of_birth": "1994-11-02",
                "time_of_birth": "06:45:00",
                "place_of_birth": "Pune",
            }
        }
    )

    @field_validator("date_of_birth")
    @classmethod
    def supported_year(cls, value: date) -> date:
        if value.year < 1800 or value.year > 2100:
            raise ValueError("Date of birth must be between 1800 and 2100")
        return value

    @field_validator("place_of_birth")
    @classmethod
    def clean_place(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if len(cleaned) < 2:
            raise ValueError("Place of birth is too short")
        return cleaned

    @model_validator(mode="after")
    def coordinates_together(self) -> "BirthDetailsIn":
        if (self.latitude is None) ^ (self.longitude is None):
            raise ValueError("Latitude and longitude must be provided together")
        return self


class BirthDetailsOut(BaseModel):
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
    utc_offset: str
    local_datetime: datetime
    utc_datetime: datetime


class UserOut(BaseModel):
    id: str
    full_name: str
    email: EmailStr
    phone: str
    gender: Literal["male", "female", "other"] | None
    created_at: datetime
    updated_at: datetime
    birth_details: BirthDetailsOut | None
    has_kundali: bool


class UpdateProfileIn(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    gender: Literal["male", "female", "other"] | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return clean_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_phone(value)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateProfileIn":
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if "full_name" in self.model_fields_set and not self.full_name:
            raise ValueError("Name cannot be empty")
        if "email" in self.model_fields_set and not self.email:
            raise ValueError("Email cannot be empty")
        if "phone" in self.model_fields_set and not self.phone:
            raise ValueError("Phone cannot be empty")
        return self


class RegisterFields(BaseModel):
    full_name: str
    email: EmailStr
    phone: str
    password: str
    gender: Literal["male", "female", "other"] | None = None

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        return clean_name(value)

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        return normalize_phone(value)

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        return password_strength(value)
