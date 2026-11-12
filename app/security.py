"""Password hashing and access tokens."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def create_access_token(user_id: str, token_version: int) -> tuple[str, int]:
    settings = get_settings()
    expires_in = settings.access_token_minutes * 60
    payload = {
        "sub": user_id,
        "ver": token_version,
        "type": "access",
        "exp": datetime.now(timezone.utc) + timedelta(seconds=expires_in),
    }
    token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    return token, expires_in


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.secret_key, algorithms=["HS256"])
