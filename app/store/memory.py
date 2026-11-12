"""Process-local store for accounts, sessions, and kundali charts.

Everything in this store disappears when the API process stops. Run a single
worker so every request sees the same data.
"""

import copy
import secrets
import threading
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.models import BirthDetails, RefreshSession, UserRecord


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.users: dict[str, UserRecord] = {}
        self.email_index: dict[str, str] = {}
        self.phone_index: dict[str, str] = {}
        self.kundalis: dict[str, dict] = {}
        self.refresh_tokens: dict[str, RefreshSession] = {}
        self.refresh_by_user: dict[str, set[str]] = {}

    def clear(self) -> None:
        with self._lock:
            self.users.clear()
            self.email_index.clear()
            self.phone_index.clear()
            self.kundalis.clear()
            self.refresh_tokens.clear()
            self.refresh_by_user.clear()

    def create_user(
        self,
        *,
        full_name: str,
        email: str,
        phone: str,
        password_hash: str,
        gender: str | None,
    ) -> UserRecord:
        with self._lock:
            if email in self.email_index:
                raise DuplicateEmail()
            if phone in self.phone_index:
                raise DuplicatePhone()
            now = _utcnow()
            user = UserRecord(
                id=str(uuid4()),
                full_name=full_name,
                email=email,
                phone=phone,
                password_hash=password_hash,
                gender=gender,
                created_at=now,
                updated_at=now,
            )
            self.users[user.id] = user
            self.email_index[email] = user.id
            self.phone_index[phone] = user.id
            return user

    def delete_user(self, user_id: str) -> None:
        with self._lock:
            user = self.users.pop(user_id, None)
            if user is None:
                return
            self.email_index.pop(user.email, None)
            self.phone_index.pop(user.phone, None)
            self.kundalis.pop(user_id, None)
            for token in self.refresh_by_user.pop(user_id, set()):
                self.refresh_tokens.pop(token, None)

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._lock:
            return self.users.get(user_id)

    def get_by_email(self, email: str) -> UserRecord | None:
        with self._lock:
            user_id = self.email_index.get(email)
            return self.users.get(user_id) if user_id else None

    def get_by_phone(self, phone: str) -> UserRecord | None:
        with self._lock:
            user_id = self.phone_index.get(phone)
            return self.users.get(user_id) if user_id else None

    def update_user(self, user_id: str, changes: dict) -> UserRecord:
        with self._lock:
            user = self.users[user_id]
            if "email" in changes and changes["email"] != user.email:
                if changes["email"] in self.email_index:
                    raise DuplicateEmail()
                self.email_index.pop(user.email, None)
                user.email = changes["email"]
                self.email_index[user.email] = user.id
            if "phone" in changes and changes["phone"] != user.phone:
                if changes["phone"] in self.phone_index:
                    raise DuplicatePhone()
                self.phone_index.pop(user.phone, None)
                user.phone = changes["phone"]
                self.phone_index[user.phone] = user.id
            if "full_name" in changes:
                user.full_name = changes["full_name"]
            if "gender" in changes:
                user.gender = changes["gender"]
            user.updated_at = _utcnow()
            return user

    def update_password(self, user_id: str, password_hash: str) -> UserRecord:
        with self._lock:
            user = self.users[user_id]
            user.password_hash = password_hash
            user.token_version += 1
            user.updated_at = _utcnow()
            for token in self.refresh_by_user.pop(user_id, set()):
                self.refresh_tokens.pop(token, None)
            return user

    def save_birth_and_kundali(self, user_id: str, birth: BirthDetails, chart: dict) -> None:
        with self._lock:
            user = self.users[user_id]
            user.birth = birth
            user.updated_at = _utcnow()
            self.kundalis[user_id] = chart

    def save_kundali(self, user_id: str, chart: dict) -> None:
        with self._lock:
            self.kundalis[user_id] = chart
            self.users[user_id].updated_at = _utcnow()

    def get_kundali(self, user_id: str) -> dict | None:
        with self._lock:
            chart = self.kundalis.get(user_id)
            return None if chart is None else copy.deepcopy(chart)

    def save_refresh(self, user_id: str, lifetime: timedelta) -> str:
        token = secrets.token_urlsafe(32)
        session = RefreshSession(token=token, user_id=user_id, expires_at=_utcnow() + lifetime)
        with self._lock:
            self.refresh_tokens[token] = session
            self.refresh_by_user.setdefault(user_id, set()).add(token)
            return token

    def take_refresh(self, token: str) -> RefreshSession | None:
        with self._lock:
            session = self.refresh_tokens.pop(token, None)
            if session is None:
                return None
            tokens = self.refresh_by_user.get(session.user_id)
            if tokens is not None:
                tokens.discard(token)
                if not tokens:
                    self.refresh_by_user.pop(session.user_id, None)
            if session.expires_at <= _utcnow():
                return None
            return session

    def delete_refresh(self, token: str) -> None:
        self.take_refresh(token)


class DuplicateEmail(Exception):
    """Raised inside the store and translated by the service layer."""


class DuplicatePhone(Exception):
    """Raised inside the store and translated by the service layer."""


store = MemoryStore()
