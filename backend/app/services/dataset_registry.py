"""Dataset metadata facade over object storage.

The source of truth is the object store (Supabase Storage in production).
The in-process cache is optional and must never be required for correctness.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from threading import Lock

from app.services.object_storage import StorageError, get_object_store


def csv_key(dataset_id: str) -> str:
    return f"{dataset_id}.csv"


def json_key(dataset_id: str) -> str:
    return f"{dataset_id}.json"


@dataclass
class DatasetRecord:
    """Internal record for an uploaded dataset. Not returned by the API."""

    dataset_id: str
    original_filename: str
    rows: int
    columns: int
    column_names: list[str]

    def to_json_bytes(self) -> bytes:
        return json.dumps(
            {
                "dataset_id": self.dataset_id,
                "original_filename": self.original_filename,
                "rows": self.rows,
                "columns": self.columns,
                "column_names": self.column_names,
            }
        ).encode("utf-8")

    @classmethod
    def from_json_bytes(cls, payload: bytes) -> DatasetRecord | None:
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            return None
        if not isinstance(data, dict):
            return None
        dataset_id = data.get("dataset_id")
        original_filename = data.get("original_filename")
        rows = data.get("rows")
        columns = data.get("columns")
        column_names = data.get("column_names")
        if not isinstance(dataset_id, str) or not dataset_id:
            return None
        if not isinstance(original_filename, str):
            return None
        if not isinstance(rows, int) or not isinstance(columns, int):
            return None
        if not isinstance(column_names, list) or not all(
            isinstance(name, str) for name in column_names
        ):
            return None
        return cls(
            dataset_id=dataset_id,
            original_filename=original_filename,
            rows=rows,
            columns=columns,
            column_names=column_names,
        )


class DatasetRegistry:
    """Lookup facade. Metadata and CSV bytes live in the object store."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._cache: dict[str, DatasetRecord] = {}

    def persist(self, record: DatasetRecord, csv_bytes: bytes) -> None:
        """Store CSV then metadata. Clean up any partial objects on failure."""
        store = get_object_store()
        csv_name = csv_key(record.dataset_id)
        meta_name = json_key(record.dataset_id)
        try:
            store.put(csv_name, csv_bytes, "text/csv")
        except StorageError:
            store.delete(meta_name)
            raise
        try:
            store.put(meta_name, record.to_json_bytes(), "application/json")
        except StorageError:
            store.delete(csv_name)
            raise
        with self._lock:
            self._cache[record.dataset_id] = record

    def add(self, record: DatasetRecord) -> None:
        """Persist metadata only. Prefer persist() for new uploads."""
        store = get_object_store()
        store.put(
            json_key(record.dataset_id),
            record.to_json_bytes(),
            "application/json",
        )
        with self._lock:
            self._cache[record.dataset_id] = record

    def get(self, dataset_id: str) -> DatasetRecord | None:
        with self._lock:
            cached = self._cache.get(dataset_id)
        if cached is not None:
            return cached
        payload = get_object_store().get(json_key(dataset_id))
        if payload is None:
            return None
        record = DatasetRecord.from_json_bytes(payload)
        if record is None:
            return None
        with self._lock:
            self._cache[dataset_id] = record
        return record

    def get_csv_bytes(self, dataset_id: str) -> bytes | None:
        return get_object_store().get(csv_key(dataset_id))

    def delete_objects(self, dataset_id: str) -> None:
        store = get_object_store()
        store.delete(csv_key(dataset_id))
        store.delete(json_key(dataset_id))
        with self._lock:
            self._cache.pop(dataset_id, None)

    def clear(self) -> None:
        """Drop the optional cache. Does not delete stored objects."""
        with self._lock:
            self._cache.clear()


registry = DatasetRegistry()
