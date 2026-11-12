"""Account login and session helpers."""

from dataclasses import dataclass
from datetime import timedelta

from app.config import get_settings
from app.errors import (
    DuplicateEmailError,
    DuplicatePhoneError,
    InvalidCredentialsError,
    PasswordReuseError,
)
from app.models import UserRecord
from app.security import create_access_token, hash_password, verify_password
from app.store.memory import DuplicateEmail, DuplicatePhone, store
from app.validation import normalize_phone


@dataclass(frozen=True)
class IssuedTokens:
    access_token: str
    refresh_token: str
    expires_in: int


def issue_tokens(user: UserRecord) -> IssuedTokens:
    access_token, expires_in = create_access_token(user.id, user.token_version)
    refresh_token = store.save_refresh(user.id, timedelta(days=get_settings().refresh_token_days))
    return IssuedTokens(access_token, refresh_token, expires_in)


def authenticate(identifier: str, password: str) -> UserRecord:
    user = _find_user(identifier)
    if user is None or not verify_password(password, user.password_hash):
        raise InvalidCredentialsError("Invalid email, phone, or password")
    return user


def rotate_refresh(refresh_token: str) -> UserRecord:
    session = store.take_refresh(refresh_token)
    if session is None:
        raise InvalidCredentialsError("Invalid or expired refresh token")
    user = store.get_user(session.user_id)
    if user is None:
        raise InvalidCredentialsError("Invalid or expired refresh token")
    return user


def logout(refresh_token: str) -> None:
    store.delete_refresh(refresh_token)


def change_password(user: UserRecord, current_password: str, new_password: str) -> UserRecord:
    if not verify_password(current_password, user.password_hash):
        raise InvalidCredentialsError("Current password is incorrect")
    if verify_password(new_password, user.password_hash):
        raise PasswordReuseError("New password must be different from the current password")
    return store.update_password(user.id, hash_password(new_password))


def create_account(
    *,
    full_name: str,
    email: str,
    phone: str,
    password: str,
    gender: str | None,
) -> UserRecord:
    try:
        return store.create_user(
            full_name=full_name,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            gender=gender,
        )
    except DuplicateEmail as exc:
        raise DuplicateEmailError("An account with this email already exists") from exc
    except DuplicatePhone as exc:
        raise DuplicatePhoneError("An account with this phone number already exists") from exc


def apply_profile_changes(user_id: str, changes: dict) -> UserRecord:
    try:
        return store.update_user(user_id, changes)
    except DuplicateEmail as exc:
        raise DuplicateEmailError("An account with this email already exists") from exc
    except DuplicatePhone as exc:
        raise DuplicatePhoneError("An account with this phone number already exists") from exc


def _find_user(identifier: str) -> UserRecord | None:
    value = identifier.strip()
    if "@" in value:
        return store.get_by_email(value.lower())
    try:
        phone = normalize_phone(value)
    except ValueError:
        return None
    return store.get_by_phone(phone)
