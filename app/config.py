"""Runtime settings loaded from the environment."""

import os
from dataclasses import dataclass
from functools import lru_cache


@dataclass(frozen=True)
class Settings:
    secret_key: str
    access_token_minutes: int
    refresh_token_days: int
    default_secret: bool


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


@lru_cache
def get_settings() -> Settings:
    default_secret = "dev-only-change-this-secret-key!!"
    secret = os.getenv("SECRET_KEY", default_secret)
    return Settings(
        secret_key=secret,
        access_token_minutes=_int_env("ACCESS_TOKEN_MINUTES", 60 * 24),
        refresh_token_days=_int_env("REFRESH_TOKEN_DAYS", 30),
        default_secret=secret == default_secret,
    )
