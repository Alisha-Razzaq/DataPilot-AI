"""CSV upload, validation, storage, and dataset retrieval.

Upload and storage live here. Profiling calculations live in ``app.analysis``.
"""

from __future__ import annotations

import uuid
from io import BytesIO
from pathlib import Path

import pandas as pd
from fastapi import UploadFile, status

from app.analysis.profiler import profile_dataset
from app.analysis.statistics import analyze_dataset_statistics
from app.analysis.visualizations import (
    build_bar,
    build_catalog,
    build_heatmap,
    build_histogram,
    build_scatter,
)
from app.config import settings
from app.models.dataset import DatasetUploadResponse
from app.models.profile import DatasetProfileResponse
from app.models.statistics import DatasetStatisticsResponse
from app.models.visualization import (
    BarResponse,
    HeatmapResponse,
    HistogramResponse,
    ScatterResponse,
    VisualizationCatalogResponse,
    VisualizationError,
)
from app.services.dataset_registry import DatasetRecord, registry
from app.services.object_storage import StorageError

# MIME types commonly sent for CSV. Extension remains the primary check.
_ALLOWED_CSV_MIME_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
}

_READ_CHUNK_BYTES = 64 * 1024


class DatasetError(Exception):
    """Upload/load failure mapped to an HTTP status by the API layer."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _safe_display_filename(raw_name: str | None) -> str:
    """Return a basename for display. Never used as a storage path."""
    if not raw_name or not raw_name.strip():
        raise DatasetError(
            status.HTTP_400_BAD_REQUEST,
            "A filename is required.",
        )
    name = Path(raw_name.replace("\\", "/")).name
    if not name or name in {".", ".."}:
        raise DatasetError(
            status.HTTP_400_BAD_REQUEST,
            "A filename is required.",
        )
    return name


def _assert_csv_filename(filename: str) -> None:
    if Path(filename).suffix.lower() != ".csv":
        raise DatasetError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only CSV files are accepted.",
        )


def _assert_csv_mime_type(content_type: str | None) -> None:
    """Reject clearly non-CSV MIME types when the client sends one."""
    if not content_type:
        return
    media_type = content_type.split(";", 1)[0].strip().lower()
    if not media_type:
        return
    if media_type not in _ALLOWED_CSV_MIME_TYPES:
        raise DatasetError(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Only CSV files are accepted.",
        )


async def _read_limited(upload: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await upload.read(_READ_CHUNK_BYTES)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise DatasetError(
                status.HTTP_413_CONTENT_TOO_LARGE,
                f"File exceeds the maximum upload size of {max_bytes} bytes.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _load_csv_frame(content: bytes) -> pd.DataFrame:
    try:
        return pd.read_csv(BytesIO(content))
    except (
        pd.errors.EmptyDataError,
        pd.errors.ParserError,
        UnicodeDecodeError,
        OSError,
        ValueError,
    ) as exc:
        raise DatasetError(
            status.HTTP_400_BAD_REQUEST,
            "The uploaded file could not be read as a CSV.",
        ) from exc


def _raise_storage(exc: StorageError) -> None:
    raise DatasetError(exc.status_code, exc.detail) from exc


async def save_upload(upload: UploadFile) -> DatasetUploadResponse:
    """Validate a CSV upload, persist it, and return metadata."""
    original_filename = _safe_display_filename(upload.filename)
    _assert_csv_filename(original_filename)
    _assert_csv_mime_type(upload.content_type)

    content = await _read_limited(upload, settings.max_upload_bytes)
    if not content.strip():
        raise DatasetError(
            status.HTTP_400_BAD_REQUEST,
            "The uploaded file is empty.",
        )

    frame = _load_csv_frame(content)
    if frame.shape[1] == 0:
        raise DatasetError(
            status.HTTP_400_BAD_REQUEST,
            "The CSV file is empty or has no columns.",
        )

    dataset_id = str(uuid.uuid4())
    record = DatasetRecord(
        dataset_id=dataset_id,
        original_filename=original_filename,
        rows=int(frame.shape[0]),
        columns=int(frame.shape[1]),
        column_names=[str(name) for name in frame.columns],
    )
    try:
        registry.persist(record, content)
    except StorageError as exc:
        _raise_storage(exc)
    return DatasetUploadResponse(
        dataset_id=record.dataset_id,
        original_filename=record.original_filename,
        rows=record.rows,
        columns=record.columns,
        column_names=record.column_names,
    )


def load_registered_frame(dataset_id: str) -> pd.DataFrame:
    """Load a dataset from object storage. ``dataset_id`` is never a file path."""
    try:
        record = registry.get(dataset_id)
        csv_bytes = registry.get_csv_bytes(dataset_id) if record is not None else None
    except StorageError as exc:
        _raise_storage(exc)
    if record is None or csv_bytes is None:
        raise DatasetError(status.HTTP_404_NOT_FOUND, "Dataset not found.")
    return _load_csv_frame(csv_bytes)


def get_dataset_profile(dataset_id: str) -> DatasetProfileResponse:
    """Retrieve a dataset and return its analysis profile."""
    frame = load_registered_frame(dataset_id)
    profile = profile_dataset(frame)
    return DatasetProfileResponse(dataset_id=dataset_id, **profile.model_dump())


def get_dataset_statistics(dataset_id: str) -> DatasetStatisticsResponse:
    """Retrieve a dataset and return numeric statistics."""
    frame = load_registered_frame(dataset_id)
    stats = analyze_dataset_statistics(frame)
    return DatasetStatisticsResponse(dataset_id=dataset_id, **stats.model_dump())


def _chart_or_raise(builder):
    try:
        return builder()
    except VisualizationError as exc:
        raise DatasetError(exc.status_code, exc.detail) from exc


def get_visualization_catalog(dataset_id: str) -> VisualizationCatalogResponse:
    frame = load_registered_frame(dataset_id)
    catalog = _chart_or_raise(lambda: build_catalog(frame))
    return VisualizationCatalogResponse(dataset_id=dataset_id, **catalog.model_dump())


def get_histogram_chart(
    dataset_id: str, column: str, bins: int
) -> HistogramResponse:
    frame = load_registered_frame(dataset_id)
    chart = _chart_or_raise(lambda: build_histogram(frame, column, bins))
    return HistogramResponse(dataset_id=dataset_id, **chart.model_dump())


def get_bar_chart(dataset_id: str, column: str, limit: int) -> BarResponse:
    frame = load_registered_frame(dataset_id)
    chart = _chart_or_raise(lambda: build_bar(frame, column, limit))
    return BarResponse(dataset_id=dataset_id, **chart.model_dump())


def get_scatter_chart(
    dataset_id: str, x_column: str, y_column: str, max_points: int
) -> ScatterResponse:
    frame = load_registered_frame(dataset_id)
    chart = _chart_or_raise(lambda: build_scatter(frame, x_column, y_column, max_points))
    return ScatterResponse(dataset_id=dataset_id, **chart.model_dump())


def get_heatmap_chart(dataset_id: str) -> HeatmapResponse:
    frame = load_registered_frame(dataset_id)
    chart = _chart_or_raise(lambda: build_heatmap(frame))
    return HeatmapResponse(dataset_id=dataset_id, **chart.model_dump())
