"""Test isolation for the in-memory store."""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.store.memory import store


@pytest.fixture(autouse=True)
def reset_store(monkeypatch):
    monkeypatch.setenv("ASTRA_DISABLE_REMOTE_GEOCODE", "1")
    store.clear()
    yield
    store.clear()


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client
