"""Login and session payloads."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.kundali import KundaliOut
from app.schemas.user import BirthDetailsIn, RegisterFields, UserOut
from app.validation import password_strength


class RegisterIn(RegisterFields):
    birth_details: BirthDetailsIn | None = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "Asha Rao",
                "email": "asha@example.com",
                "phone": "9876543210",
                "password": "starlight-7",
                "gender": "female",
                "birth_details": {
                    "date_of_birth": "1994-11-02",
                    "time_of_birth": "06:45:00",
                    "place_of_birth": "Pune",
                },
            }
        }
    )


class LoginIn(BaseModel):
    identifier: str = Field(
        min_length=3,
        max_length=120,
        description="Email address or phone number",
    )
    password: str


class RefreshIn(BaseModel):
    refresh_token: str = Field(min_length=10)


class LogoutIn(BaseModel):
    refresh_token: str = Field(min_length=10)


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, value: str) -> str:
        return password_strength(value)


class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
    user: UserOut
    kundali: KundaliOut | None = None
