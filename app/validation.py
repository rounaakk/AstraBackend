"""Shared input normalization for account fields."""

import re


def clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not 2 <= len(cleaned) <= 80:
        raise ValueError("Name must be between 2 and 80 characters")
    return cleaned


def normalize_phone(value: str) -> str:
    raw = re.sub(r"[\s\-()]", "", value.strip())
    if raw.startswith("00"):
        raw = "+" + raw[2:]
    if re.fullmatch(r"[6-9]\d{9}", raw):
        raw = "+91" + raw
    if not re.fullmatch(r"\+\d{8,15}", raw):
        raise ValueError("Enter a valid phone number with country code")
    return raw


def password_strength(value: str) -> str:
    if len(value) > 72:
        raise ValueError("Password must be at most 72 characters")
    if len(value.strip()) < 8:
        raise ValueError("Password must be at least 8 characters")
    return value
