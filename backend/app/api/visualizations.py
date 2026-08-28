"""Thin visualization routes. Chart math lives in ``app.analysis``."""

from fastapi import APIRouter, HTTPException, Query

from app.models.visualization import (
    BarResponse,
    HeatmapResponse,
    HistogramResponse,
    ScatterResponse,
    VisualizationCatalogResponse,
)
from app.services.dataset_service import (
    DatasetError,
    get_bar_chart,
    get_heatmap_chart,
    get_histogram_chart,
    get_scatter_chart,
    get_visualization_catalog,
)

router = APIRouter(prefix="/api/datasets", tags=["visualizations"])


def _unwrap(exc: DatasetError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get(
    "/{dataset_id}/visualizations",
    response_model=VisualizationCatalogResponse,
    summary="List available visualizations",
    responses={404: {"description": "Dataset not found in the in-memory registry."}},
)
def visualization_catalog(dataset_id: str) -> VisualizationCatalogResponse:
    try:
        return get_visualization_catalog(dataset_id)
    except DatasetError as exc:
        raise _unwrap(exc) from exc


@router.get(
    "/{dataset_id}/visualizations/histogram",
    response_model=HistogramResponse,
    summary="Histogram bin counts for a numeric column",
    responses={
        400: {"description": "Unknown or non-numeric column."},
        404: {"description": "Dataset not found in the in-memory registry."},
    },
)
def visualization_histogram(
    dataset_id: str,
    column: str,
    bins: int = Query(default=20),
) -> HistogramResponse:
    try:
        return get_histogram_chart(dataset_id, column, bins)
    except DatasetError as exc:
        raise _unwrap(exc) from exc


@router.get(
    "/{dataset_id}/visualizations/bar",
    response_model=BarResponse,
    summary="Bar counts for a categorical column",
    responses={
        400: {"description": "Unknown or non-categorical column."},
        404: {"description": "Dataset not found in the in-memory registry."},
    },
)
def visualization_bar(
    dataset_id: str,
    column: str,
    limit: int = Query(default=15),
) -> BarResponse:
    try:
        return get_bar_chart(dataset_id, column, limit)
    except DatasetError as exc:
        raise _unwrap(exc) from exc


@router.get(
    "/{dataset_id}/visualizations/scatter",
    response_model=ScatterResponse,
    summary="Sampled scatter points for two numeric columns",
    responses={
        400: {"description": "Unknown or non-numeric columns."},
        404: {"description": "Dataset not found in the in-memory registry."},
    },
)
def visualization_scatter(
    dataset_id: str,
    x: str,
    y: str,
    max_points: int = Query(default=500),
) -> ScatterResponse:
    try:
        return get_scatter_chart(dataset_id, x, y, max_points)
    except DatasetError as exc:
        raise _unwrap(exc) from exc


@router.get(
    "/{dataset_id}/visualizations/heatmap",
    response_model=HeatmapResponse,
    summary="Pearson correlation heatmap matrix",
    responses={404: {"description": "Dataset not found in the in-memory registry."}},
)
def visualization_heatmap(dataset_id: str) -> HeatmapResponse:
    try:
        return get_heatmap_chart(dataset_id)
    except DatasetError as exc:
        raise _unwrap(exc) from exc
