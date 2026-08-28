"""Shared pytest fixtures for API tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.services.dataset_registry import registry
from app.services.object_storage import MemoryObjectStore, reset_object_store


@pytest.fixture()
def object_store(monkeypatch: pytest.MonkeyPatch) -> Iterator[MemoryObjectStore]:
    store = MemoryObjectStore()
    reset_object_store(store)
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_secret_key", "")
    monkeypatch.setattr(settings, "supabase_storage_bucket", "datasets")
    registry.clear()
    yield store
    registry.clear()
    reset_object_store(None)


@pytest.fixture()
def client(object_store: MemoryObjectStore) -> Iterator[TestClient]:
    del object_store
    yield TestClient(app)
