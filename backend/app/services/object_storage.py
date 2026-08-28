"""Object storage for uploaded datasets.

Production uses the Supabase Storage REST API via httpx. Tests inject an
in-memory store. Unconfigured processes fail closed (503) instead of storing
bytes in RAM that vanish on restart. The Vercel filesystem is never the
source of truth.
"""

from __future__ import annotations

from threading import Lock
from urllib.parse import quote

import httpx

from app.config import settings

_REQUEST_TIMEOUT_SECONDS = 30.0


class StorageError(Exception):
    """Object-store failure mapped to an HTTP status by the dataset service."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


class ObjectStore:
    """Minimal object store: put, get, and delete bytes by key."""

    def put(self, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError


class MemoryObjectStore(ObjectStore):
    """Process-local bytes map. Tests inject this via reset_object_store()."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str) -> None:
        del content_type
        with self._lock:
            self._objects[key] = data

    def get(self, key: str) -> bytes | None:
        with self._lock:
            return self._objects.get(key)

    def delete(self, key: str) -> None:
        with self._lock:
            self._objects.pop(key, None)


class SupabaseObjectStore(ObjectStore):
    """Supabase Storage REST client. The secret key stays on the server."""

    def __init__(self, base_url: str, secret_key: str, bucket: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._secret_key = secret_key
        self._bucket = bucket.strip().strip("/") or "datasets"
        self._client = httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS)

    def _headers(self, content_type: str | None = None) -> dict[str, str]:
        # sb_secret_ keys are not JWTs. Current Supabase docs require them on
        # the apikey header only; Authorization: Bearer causes Invalid JWT.
        headers = {"apikey": self._secret_key}
        if content_type:
            headers["Content-Type"] = content_type
            headers["x-upsert"] = "true"
        return headers

    def _encode_key(self, key: str) -> str:
        # Keep "." so objects are {dataset_id}.csv / {dataset_id}.json, not %2E.
        return quote(key, safe=".")

    def _object_url(self, key: str) -> str:
        """Upload and delete path: /storage/v1/object/{bucket}/{key}."""
        return (
            f"{self._base_url}/storage/v1/object/"
            f"{self._bucket}/{self._encode_key(key)}"
        )

    def _download_url(self, key: str) -> str:
        """Private-bucket download: /storage/v1/object/authenticated/{bucket}/{key}."""
        return (
            f"{self._base_url}/storage/v1/object/authenticated/"
            f"{self._bucket}/{self._encode_key(key)}"
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            response = self._client.post(
                self._object_url(key),
                headers=self._headers(content_type),
                content=data,
            )
        except httpx.HTTPError as exc:
            raise StorageError(502, "Object storage request failed.") from exc
        if response.status_code >= 400:
            raise StorageError(502, "Object storage request failed.")

    def get(self, key: str) -> bytes | None:
        try:
            response = self._client.get(
                self._download_url(key),
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise StorageError(502, "Object storage request failed.") from exc
        if response.status_code == 404:
            return None
        if response.status_code in {401, 403}:
            raise StorageError(502, "Object storage authentication failed.")
        if response.status_code >= 400:
            raise StorageError(502, "Object storage request failed.")
        return response.content

    def delete(self, key: str) -> None:
        try:
            response = self._client.delete(
                self._object_url(key),
                headers=self._headers(),
            )
        except httpx.HTTPError as exc:
            raise StorageError(502, "Object storage request failed.") from exc
        if response.status_code == 404:
            return
        if response.status_code in {401, 403}:
            raise StorageError(502, "Object storage authentication failed.")
        if response.status_code >= 400:
            raise StorageError(502, "Object storage request failed.")


_active_store: ObjectStore | None = None


def reset_object_store(store: ObjectStore | None = None) -> None:
    """Replace the process store. Tests use this to inject memory storage."""
    global _active_store
    _active_store = store


def get_object_store() -> ObjectStore:
    """Return the configured store. Never falls back to RAM or local disk."""
    global _active_store
    if _active_store is not None:
        return _active_store
    if settings.supabase_configured:
        _active_store = SupabaseObjectStore(
            settings.supabase_url,
            settings.supabase_secret_key,
            settings.supabase_storage_bucket,
        )
        return _active_store
    raise StorageError(503, "Object storage is not configured.")
