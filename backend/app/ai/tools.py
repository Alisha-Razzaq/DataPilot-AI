"""Explicit DataPilot tools.

Each function is a named, deterministic operation. Tools do not calculate
statistics themselves: they call existing services, which call analysis.

There is no generic executor here. An LLM (Phase 8) may only request these
functions, never eval/exec, shell, SQL, or arbitrary Python.
"""

from __future__ import annotations

from fastapi import status

from app.ai.schemas import (
    CategoryCountsResult,
    ColumnProfileResult,
    CorrelationsResult,
    DatasetSummaryResult,
    HeatmapResult,
    HistogramResult,
    NumericStatisticsResult,
    OutliersResult,
    ScatterResult,
)
from app.models.profile import ColumnProfile, DatasetProfileResponse
from app.models.statistics import NumericColumnStatistics
from app.services.dataset_service import (
    DatasetError,
    get_bar_chart,
    get_dataset_profile,
    get_dataset_statistics,
    get_heatmap_chart,
    get_histogram_chart,
    get_scatter_chart,
)


def _require_column(profile: DatasetProfileResponse, column: str) -> ColumnProfile:
    for item in profile.column_profiles:
        if item.name == column:
            return item
    raise DatasetError(status.HTTP_400_BAD_REQUEST, f"Unknown column: {column}")


def _require_numeric_column(profile: DatasetProfileResponse, column: str) -> ColumnProfile:
    item = _require_column(profile, column)
    if item.inferred_type != "numeric":
        raise DatasetError(
            status.HTTP_400_BAD_REQUEST,
            f"Column '{column}' is not numeric.",
        )
    return item


def _column_statistics(
    dataset_id: str, column: str
) -> tuple[ColumnProfile, NumericColumnStatistics]:
    profile = get_dataset_profile(dataset_id)
    column_profile = _require_numeric_column(profile, column)
    stats = get_dataset_statistics(dataset_id)
    for item in stats.column_statistics:
        if item.name == column:
            return column_profile, item
    raise DatasetError(
        status.HTTP_400_BAD_REQUEST,
        f"Column '{column}' is not numeric.",
    )


def get_dataset_summary(dataset_id: str) -> DatasetSummaryResult:
    profile = get_dataset_profile(dataset_id)
    return DatasetSummaryResult(
        dataset_id=profile.dataset_id,
        rows=profile.rows,
        columns=profile.columns,
        column_names=profile.column_names,
        duplicate_row_count=profile.duplicate_row_count,
        duplicate_row_percentage=profile.duplicate_row_percentage,
    )


def get_column_profile(dataset_id: str, column: str) -> ColumnProfileResult:
    profile = get_dataset_profile(dataset_id)
    return ColumnProfileResult(
        dataset_id=profile.dataset_id,
        column=_require_column(profile, column),
    )


def get_numeric_statistics(dataset_id: str, column: str) -> NumericStatisticsResult:
    column_profile, column_stats = _column_statistics(dataset_id, column)
    numeric = column_profile.numeric_summary
    if numeric is None:
        raise DatasetError(
            status.HTTP_400_BAD_REQUEST,
            f"Column '{column}' is not numeric.",
        )
    return NumericStatisticsResult(
        dataset_id=dataset_id,
        column=column,
        count=numeric.count,
        mean=numeric.mean,
        median=numeric.median,
        std=numeric.std,
        min=numeric.min,
        max=numeric.max,
        quartiles=column_stats.quartiles,
        outliers=column_stats.outliers,
    )


def get_correlations(dataset_id: str) -> CorrelationsResult:
    stats = get_dataset_statistics(dataset_id)
    return CorrelationsResult(
        dataset_id=stats.dataset_id,
        numeric_columns=stats.numeric_columns,
        correlations=stats.correlations,
    )


def get_outliers(dataset_id: str, column: str) -> OutliersResult:
    _, column_stats = _column_statistics(dataset_id, column)
    return OutliersResult(
        dataset_id=dataset_id,
        column=column,
        outliers=column_stats.outliers,
    )


def get_histogram(dataset_id: str, column: str, bins: int = 20) -> HistogramResult:
    chart = get_histogram_chart(dataset_id, column, bins)
    return HistogramResult(
        dataset_id=chart.dataset_id,
        column=chart.column,
        bins=chart.bins,
        title=chart.title,
        data=chart.data.bins,
    )


def get_category_counts(
    dataset_id: str, column: str, limit: int = 15
) -> CategoryCountsResult:
    chart = get_bar_chart(dataset_id, column, limit)
    return CategoryCountsResult(
        dataset_id=chart.dataset_id,
        column=chart.column,
        categories=chart.data.bars,
    )


def get_scatter_data(
    dataset_id: str,
    x_column: str,
    y_column: str,
    max_points: int = 500,
) -> ScatterResult:
    chart = get_scatter_chart(dataset_id, x_column, y_column, max_points)
    return ScatterResult(
        dataset_id=chart.dataset_id,
        x_column=chart.x_column,
        y_column=chart.y_column,
        sampled=chart.sampled,
        point_count=chart.point_count,
        points=chart.data.points,
    )


def get_correlation_heatmap(dataset_id: str) -> HeatmapResult:
    chart = get_heatmap_chart(dataset_id)
    return HeatmapResult(
        dataset_id=chart.dataset_id,
        title=chart.title,
        columns=chart.data.columns,
        matrix=chart.data.matrix,
    )
