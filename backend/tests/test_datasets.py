"""Tests for CSV upload and object-store dataset persistence."""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.dataset_registry import csv_key, json_key, registry
from app.services.object_storage import MemoryObjectStore, StorageError, reset_object_store

VALID_CSV = (
    "date,region,sales,profit\n"
    "2024-01-01,east,100,20\n"
    "2024-01-02,west,200,40\n"
).encode("utf-8")


def _upload(
    client: TestClient,
    filename: str,
    content: bytes,
    content_type: str = "text/csv",
):
    return client.post(
        "/api/datasets/upload",
        files={"file": (filename, content, content_type)},
    )


def test_upload_returns_metadata_and_stores_uuid_objects(
    client: TestClient, object_store: MemoryObjectStore
) -> None:
    response = _upload(client, "sales.csv", VALID_CSV)
    assert response.status_code == 201
    payload = response.json()

    dataset_id = payload["dataset_id"]
    uuid.UUID(dataset_id)
    assert payload["original_filename"] == "sales.csv"
    assert payload["rows"] == 2
    assert payload["columns"] == 4
    assert payload["column_names"] == ["date", "region", "sales", "profit"]
    assert "stored_path" not in payload

    csv_bytes = object_store.get(csv_key(dataset_id))
    meta_bytes = object_store.get(json_key(dataset_id))
    assert csv_bytes == VALID_CSV
    assert meta_bytes is not None
    assert object_store.get("sales.csv") is None

    record = registry.get(dataset_id)
    assert record is not None
    assert record.dataset_id == dataset_id
    assert record.original_filename == "sales.csv"


def test_upload_rejects_non_csv_extension(client: TestClient) -> None:
    response = _upload(client, "notes.txt", VALID_CSV, "text/plain")
    assert response.status_code == 415
    assert response.json()["detail"] == "Only CSV files are accepted."


def test_upload_rejects_non_csv_mime_type(client: TestClient) -> None:
    response = _upload(client, "sales.csv", VALID_CSV, "image/png")
    assert response.status_code == 415
    assert response.json()["detail"] == "Only CSV files are accepted."


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = _upload(client, "empty.csv", b"")
    assert response.status_code == 400
    assert response.json()["detail"] == "The uploaded file is empty."


def test_upload_rejects_whitespace_only_file(client: TestClient) -> None:
    response = _upload(client, "blank.csv", b"  \n\n  ")
    assert response.status_code == 400
    assert response.json()["detail"] == "The uploaded file is empty."


def test_upload_rejects_invalid_csv(
    client: TestClient, object_store: MemoryObjectStore
) -> None:
    malformed = b'date,region\n"unclosed quote,east\n2024-01-01,west\n'
    response = _upload(client, "broken.csv", malformed)
    assert response.status_code == 400
    assert "could not be read as a CSV" in response.json()["detail"]
    assert object_store.get("broken.csv") is None
    assert list(object_store._objects) == []


def test_upload_rejects_oversized_file(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", 64)
    oversized = b"col1,col2\n" + b"x,y\n" * 40
    response = _upload(client, "large.csv", oversized)
    assert response.status_code == 413
    assert "maximum upload size" in response.json()["detail"]


def test_upload_strips_path_from_original_filename(
    client: TestClient, object_store: MemoryObjectStore
) -> None:
    response = _upload(client, "../../etc/passwd.csv", VALID_CSV)
    assert response.status_code == 201
    payload = response.json()
    assert payload["original_filename"] == "passwd.csv"
    dataset_id = payload["dataset_id"]
    assert set(object_store._objects) == {
        csv_key(dataset_id),
        json_key(dataset_id),
    }
