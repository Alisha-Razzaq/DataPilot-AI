"""Dataset HTTP routes. Handlers stay thin; validation lives in services."""

from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.models.dataset import DatasetUploadResponse
from app.models.profile import DatasetProfileResponse
from app.models.statistics import DatasetStatisticsResponse
from app.services.dataset_service import (
    DatasetError,
    get_dataset_profile,
    get_dataset_statistics,
    save_upload,
)

router = APIRouter(prefix="/api/datasets", tags=["datasets"])


@router.post(
    "/upload",
    response_model=DatasetUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV dataset",
    description=(
        "Accepts a CSV file, stores it under a server-generated id, and returns "
        "basic shape metadata. Detailed profiling is not performed."
    ),
)
async def upload_dataset(
    file: Annotated[
        UploadFile,
        File(description="CSV file. The original name is not used as the storage path."),
    ],
) -> DatasetUploadResponse:
    """Store an uploaded CSV and return dataset_id plus basic metadata."""
    try:
        return await save_upload(file)
    except DatasetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/{dataset_id}/profile",
    response_model=DatasetProfileResponse,
    summary="Profile an uploaded dataset",
    description=(
        "Returns a structured pandas profile for a previously uploaded dataset. "
        "Unknown dataset_id values return 404. Internal file paths are never exposed."
    ),
    responses={404: {"description": "Dataset not found in the in-memory registry."}},
)
def profile_dataset_endpoint(dataset_id: str) -> DatasetProfileResponse:
    """Return a JSON-safe profile for ``dataset_id``."""
    try:
        return get_dataset_profile(dataset_id)
    except DatasetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get(
    "/{dataset_id}/statistics",
    response_model=DatasetStatisticsResponse,
    summary="Numeric statistics for an uploaded dataset",
    description=(
        "Pearson correlations, quartiles, and IQR-based outlier flags for numeric "
        "columns. Unknown dataset_id values return 404. Internal file paths are "
        "never exposed."
    ),
    responses={404: {"description": "Dataset not found in the in-memory registry."}},
)
def statistics_dataset_endpoint(dataset_id: str) -> DatasetStatisticsResponse:
    """Return JSON-safe numeric statistics for ``dataset_id``."""
    try:
        return get_dataset_statistics(dataset_id)
    except DatasetError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
