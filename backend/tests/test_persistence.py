"""Persistence across a fresh registry cache and mocked Supabase HTTP."""

from __future__ import annotations

import json
from types import SimpleNamespace
from urllib.parse import urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.dataset_registry import (
    DatasetRecord,
    DatasetRegistry,
    csv_key,
    json_key,
    registry,
)
from app.services.object_storage import (
    MemoryObjectStore,
    StorageError,
    SupabaseObjectStore,
    reset_object_store,
)

_FAKE_SUPABASE_URL = "https://example.supabase.co"
_FAKE_SECRET = "sb_secret_test_key"
_BUCKET = "datasets"

VALID_CSV = (
    "region,sales,profit\n"
    "east,10,1\n"
    "west,20,2\n"
    "east,30,3\n"
    "west,40,4\n"
).encode("utf-8")


def _upload(client: TestClient, content: bytes = VALID_CSV) -> str:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", content, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["dataset_id"]


def _configure_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.1-flash-lite")


class _ScriptedModels:
    def __init__(self, script: list[object]) -> None:
        self.script = list(script)

    def generate_content(self, **kwargs):
        del kwargs
        return self.script.pop(0)


def _text_response(text: str) -> SimpleNamespace:
    content = SimpleNamespace(
        role="model",
        parts=[SimpleNamespace(text=text, function_call=None)],
    )
    return SimpleNamespace(
        text=text,
        function_calls=None,
        candidates=[SimpleNamespace(content=content)],
    )


class _FailingPutStore(MemoryObjectStore):
    def __init__(self, fail_on: str) -> None:
        super().__init__()
        self.fail_on = fail_on

    def put(self, key: str, data: bytes, content_type: str) -> None:
        if key.endswith(self.fail_on):
            raise StorageError(502, "Object storage request failed.")
        super().put(key, data, content_type)


def _assert_storage_auth_headers(request: httpx.Request) -> None:
    assert request.headers.get("apikey") == _FAKE_SECRET
    authorization = request.headers.get("authorization", "")
    assert authorization == ""
    assert "Bearer" not in authorization


def _make_supabase_store(handler) -> SupabaseObjectStore:
    store = SupabaseObjectStore(_FAKE_SUPABASE_URL, _FAKE_SECRET, _BUCKET)
    store._client = httpx.Client(transport=httpx.MockTransport(handler))
    return store


def test_upload_persists_csv_and_metadata(
    client: TestClient, object_store: MemoryObjectStore
) -> None:
    dataset_id = _upload(client)
    assert csv_key(dataset_id) == f"{dataset_id}.csv"
    assert json_key(dataset_id) == f"{dataset_id}.json"
    assert object_store.get(csv_key(dataset_id)) == VALID_CSV
    meta = object_store.get(json_key(dataset_id))
    assert meta is not None
    payload = json.loads(meta.decode("utf-8"))
    assert payload["dataset_id"] == dataset_id
    assert payload["original_filename"] == "sales.csv"
    assert payload["rows"] == 4
    assert payload["columns"] == 3
    assert payload["column_names"] == ["region", "sales", "profit"]
    record = registry.get(dataset_id)
    assert record is not None
    assert record.rows == 4
    assert record.column_names == ["region", "sales", "profit"]


def test_metadata_and_csv_retrieval_without_cache(
    client: TestClient, object_store: MemoryObjectStore
) -> None:
    dataset_id = _upload(client)
    registry.clear()
    record = registry.get(dataset_id)
    csv_bytes = registry.get_csv_bytes(dataset_id)
    assert record is not None
    assert record.original_filename == "sales.csv"
    assert csv_bytes == VALID_CSV
    del object_store


def test_fresh_registry_instance_loads_existing_dataset(
    client: TestClient, object_store: MemoryObjectStore
) -> None:
    dataset_id = _upload(client)
    registry.clear()
    fresh = DatasetRegistry()
    record = fresh.get(dataset_id)
    assert record is not None
    assert record.dataset_id == dataset_id
    assert record.original_filename == "sales.csv"
    assert record.rows == 4
    assert record.columns == 3
    assert record.column_names == ["region", "sales", "profit"]
    assert fresh.get_csv_bytes(dataset_id) == VALID_CSV
    del object_store


def test_profile_after_fresh_registry_cache(client: TestClient) -> None:
    dataset_id = _upload(client)
    registry.clear()
    response = client.get(f"/api/datasets/{dataset_id}/profile")
    assert response.status_code == 200
    assert response.json()["dataset_id"] == dataset_id
    assert response.json()["rows"] == 4


def test_statistics_after_fresh_registry_cache(client: TestClient) -> None:
    dataset_id = _upload(client)
    registry.clear()
    response = client.get(f"/api/datasets/{dataset_id}/statistics")
    assert response.status_code == 200
    assert response.json()["numeric_columns"] == ["sales", "profit"]


def test_visualizations_after_fresh_registry_cache(client: TestClient) -> None:
    dataset_id = _upload(client)
    registry.clear()
    response = client.get(f"/api/datasets/{dataset_id}/visualizations")
    assert response.status_code == 200
    assert "histogram" in response.json()["available_charts"]


def test_chat_lookup_after_fresh_registry_cache(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    registry.clear()
    fake = SimpleNamespace(models=_ScriptedModels([_text_response("There are 4 rows.")]))
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    response = client.post(
        "/api/chat",
        json={"dataset_id": dataset_id, "message": "How many rows?"},
    )
    assert response.status_code == 200
    assert response.json()["dataset_id"] == dataset_id
    assert "test-key" not in str(response.json())


def test_missing_dataset_is_404(client: TestClient) -> None:
    response = client.get(
        "/api/datasets/00000000-0000-0000-0000-000000000000/profile"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found."


def test_invalid_csv_leaves_no_objects(
    client: TestClient, object_store: MemoryObjectStore
) -> None:
    malformed = b'date,region\n"unclosed quote,east\n'
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("broken.csv", malformed, "text/csv")},
    )
    assert response.status_code == 400
    assert object_store._objects == {}


def test_metadata_upload_failure_deletes_csv(client: TestClient) -> None:
    store = _FailingPutStore(".json")
    reset_object_store(store)
    registry.clear()
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", VALID_CSV, "text/csv")},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Object storage request failed."
    assert store._objects == {}


def test_csv_upload_failure_leaves_no_metadata(client: TestClient) -> None:
    store = _FailingPutStore(".csv")
    reset_object_store(store)
    registry.clear()
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", VALID_CSV, "text/csv")},
    )
    assert response.status_code == 502
    assert store._objects == {}


def test_supabase_http_failure_is_502() -> None:
    captured: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["apikey"] = request.headers.get("apikey", "")
        captured["authorization"] = request.headers.get("authorization", "")
        return httpx.Response(500, json={"statusCode": 500})

    transport = httpx.MockTransport(handler)
    store = SupabaseObjectStore(
        "https://example.supabase.co",
        "sb_secret_test_key",
        "datasets",
    )
    store._client = httpx.Client(transport=transport)
    with pytest.raises(StorageError) as exc:
        store.put("abc.csv", b"col\n1\n", "text/csv")
    assert exc.value.status_code == 502
    assert captured["apikey"] == "sb_secret_test_key"
    assert captured["authorization"] == ""
    assert "sb_secret_test_key" not in str(exc.value)
    assert "Bearer" not in captured["authorization"]


def test_production_without_supabase_does_not_use_disk(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_secret_key", "")
    monkeypatch.setattr(settings, "supabase_storage_bucket", "")
    reset_object_store(None)
    registry.clear()
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", VALID_CSV, "text/csv")},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Object storage is not configured."
    assert "uploads" not in response.json()["detail"]


def test_development_without_supabase_does_not_use_memory(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "supabase_secret_key", "")
    monkeypatch.setattr(settings, "supabase_storage_bucket", "datasets")
    reset_object_store(None)
    registry.clear()
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", VALID_CSV, "text/csv")},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Object storage is not configured."


def test_supabase_put_and_get_use_expected_object_paths() -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        _assert_storage_auth_headers(request)
        if request.method == "GET":
            return httpx.Response(200, content=b"col\n1\n")
        return httpx.Response(200, json={"Key": "datasets/abc.csv"})

    store = _make_supabase_store(handler)
    store.put("abc.csv", b"col\n1\n", "text/csv")
    body = store.get("abc.csv")
    assert body == b"col\n1\n"
    put_path = urlparse(str(captured[0].url)).path
    get_path = urlparse(str(captured[1].url)).path
    assert put_path == "/storage/v1/object/datasets/abc.csv"
    assert get_path == "/storage/v1/object/authenticated/datasets/abc.csv"
    assert "%2E" not in put_path
    assert "%2E" not in get_path


def test_supabase_json_and_csv_keys_are_written() -> None:
    written: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        _assert_storage_auth_headers(request)
        path = urlparse(str(request.url)).path
        if request.method == "POST":
            written[path] = request.content
            return httpx.Response(200, json={"Key": path})
        return httpx.Response(404)

    store = _make_supabase_store(handler)
    reset_object_store(store)
    registry.clear()
    registry.persist(
        DatasetRecord(
            dataset_id="abc",
            original_filename="sales.csv",
            rows=1,
            columns=1,
            column_names=["col"],
        ),
        b"col\n1\n",
    )
    assert written["/storage/v1/object/datasets/abc.csv"] == b"col\n1\n"
    assert json.loads(written["/storage/v1/object/datasets/abc.json"]) == {
        "dataset_id": "abc",
        "original_filename": "sales.csv",
        "rows": 1,
        "columns": 1,
        "column_names": ["col"],
    }


def test_mocked_supabase_load_survives_fresh_registry(
    client: TestClient,
) -> None:
    objects: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        _assert_storage_auth_headers(request)
        path = urlparse(str(request.url)).path
        if request.method == "POST":
            objects[path.rsplit("/", 1)[-1]] = request.content
            return httpx.Response(200, json={"Key": path})
        if request.method == "GET":
            assert path.startswith("/storage/v1/object/authenticated/datasets/")
            key = path.rsplit("/", 1)[-1]
            data = objects.get(key)
            if data is None:
                return httpx.Response(404, json={"statusCode": 404})
            return httpx.Response(200, content=data)
        return httpx.Response(404)

    reset_object_store(_make_supabase_store(handler))
    registry.clear()
    dataset_id = _upload(client)
    # New store client + empty cache: same backend objects, fresh process.
    reset_object_store(_make_supabase_store(handler))
    registry.clear()
    response = client.get(f"/api/datasets/{dataset_id}/profile")
    assert response.status_code == 200
    assert response.json()["dataset_id"] == dataset_id
    assert csv_key(dataset_id) in objects
    assert json_key(dataset_id) in objects


def test_supabase_get_404_is_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_storage_auth_headers(request)
        return httpx.Response(404, json={"statusCode": 404})

    store = _make_supabase_store(handler)
    assert store.get("missing.json") is None


def test_supabase_get_401_is_not_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_storage_auth_headers(request)
        return httpx.Response(401, json={"statusCode": 401})

    store = _make_supabase_store(handler)
    with pytest.raises(StorageError) as exc:
        store.get("abc.json")
    assert exc.value.status_code == 502
    assert exc.value.detail == "Object storage authentication failed."


def test_supabase_get_403_is_not_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_storage_auth_headers(request)
        return httpx.Response(403, json={"statusCode": 403})

    store = _make_supabase_store(handler)
    with pytest.raises(StorageError) as exc:
        store.get("abc.json")
    assert exc.value.status_code == 502
    assert exc.value.detail == "Object storage authentication failed."


def test_supabase_get_400_is_not_missing() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_storage_auth_headers(request)
        return httpx.Response(400, json={"statusCode": 400})

    store = _make_supabase_store(handler)
    with pytest.raises(StorageError) as exc:
        store.get("abc.json")
    assert exc.value.status_code == 502
    assert exc.value.detail == "Object storage request failed."


def test_supabase_auth_failure_is_502_not_dataset_missing(
    client: TestClient,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        _assert_storage_auth_headers(request)
        if request.method == "GET":
            return httpx.Response(401, json={"statusCode": 401})
        return httpx.Response(200, json={"Key": "ok"})

    reset_object_store(_make_supabase_store(handler))
    registry.clear()
    response = client.get(
        "/api/datasets/00000000-0000-0000-0000-000000000000/profile"
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "Object storage authentication failed."
    assert response.json()["detail"] != "Dataset not found."
