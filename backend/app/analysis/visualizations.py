"""Library-agnostic chart data built with pandas/numpy.

Does not render images and does not depend on Plotly. The future frontend
maps this JSON onto any chart library.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.analysis.profiler import infer_column_type, json_safe_float, json_safe_value
from app.analysis.statistics import numeric_column_names, pearson_correlations
from app.models.visualization import (
    BarChart,
    BarData,
    BarItem,
    CatalogColumn,
    ChartType,
    HeatmapChart,
    HeatmapData,
    HistogramBin,
    HistogramChart,
    HistogramData,
    ScatterChart,
    ScatterData,
    ScatterPoint,
    VisualizationCatalog,
    VisualizationError,
)

_BINS_MIN = 5
_BINS_MAX = 50
_BINS_DEFAULT = 20
_BAR_LIMIT_MIN = 1
_BAR_LIMIT_MAX = 50
_BAR_LIMIT_DEFAULT = 15
_SCATTER_MIN = 10
_SCATTER_MAX = 2000
_SCATTER_DEFAULT = 500
_CATEGORICAL_TYPES = {"categorical", "boolean", "text"}


def clamp_bins(bins: int) -> int:
    return max(_BINS_MIN, min(_BINS_MAX, int(bins)))


def clamp_bar_limit(limit: int) -> int:
    return max(_BAR_LIMIT_MIN, min(_BAR_LIMIT_MAX, int(limit)))


def clamp_max_points(max_points: int) -> int:
    return max(_SCATTER_MIN, min(_SCATTER_MAX, int(max_points)))


def _require_column(frame: pd.DataFrame, column: str) -> None:
    if column not in frame.columns:
        raise VisualizationError(
            400,
            f"Unknown column: {column}",
        )


def _require_numeric(frame: pd.DataFrame, column: str) -> None:
    _require_column(frame, column)
    if infer_column_type(frame[column]) != "numeric":
        raise VisualizationError(
            400,
            f"Column '{column}' is not numeric.",
        )


def build_catalog(frame: pd.DataFrame) -> VisualizationCatalog:
    """Describe which chart types each column can support."""
    numeric = numeric_column_names(frame)
    catalog_columns: list[CatalogColumn] = []
    available: set[ChartType] = set()

    for name in frame.columns:
        inferred = infer_column_type(frame[name])
        charts: list[ChartType] = []
        if inferred == "numeric":
            charts.append("histogram")
            available.add("histogram")
            if len(numeric) >= 2:
                charts.append("scatter")
                charts.append("heatmap")
                available.add("scatter")
                available.add("heatmap")
        elif inferred in _CATEGORICAL_TYPES:
            charts.append("bar")
            available.add("bar")
        catalog_columns.append(
            CatalogColumn(name=str(name), inferred_type=inferred, charts=charts)
        )

    order: list[ChartType] = ["histogram", "bar", "scatter", "heatmap"]
    return VisualizationCatalog(
        columns=catalog_columns,
        available_charts=[chart for chart in order if chart in available],
    )


def build_histogram(frame: pd.DataFrame, column: str, bins: int = _BINS_DEFAULT) -> HistogramChart:
    _require_numeric(frame, column)
    n_bins = clamp_bins(bins)
    numeric = pd.to_numeric(frame[column], errors="coerce").dropna()
    chart_bins: list[HistogramBin] = []
    if not numeric.empty:
        counts, edges = np.histogram(numeric.to_numpy(), bins=n_bins)
        for index, count in enumerate(counts):
            chart_bins.append(
                HistogramBin(
                    bin_start=json_safe_float(edges[index]),
                    bin_end=json_safe_float(edges[index + 1]),
                    count=int(count),
                )
            )
    return HistogramChart(
        title=f"Distribution of {column}",
        column=column,
        bins=n_bins,
        x_label=column,
        data=HistogramData(bins=chart_bins),
    )


def build_bar(frame: pd.DataFrame, column: str, limit: int = _BAR_LIMIT_DEFAULT) -> BarChart:
    _require_column(frame, column)
    inferred = infer_column_type(frame[column])
    if inferred not in _CATEGORICAL_TYPES:
        raise VisualizationError(
            400,
            f"Column '{column}' is not categorical.",
        )

    cap = clamp_bar_limit(limit)
    non_null = frame[column].dropna()
    bars: list[BarItem] = []
    if not non_null.empty:
        counts = non_null.value_counts(dropna=True)
        if len(counts) <= cap:
            selected = counts
            leftover = 0
        else:
            head_n = max(cap - 1, 1)
            selected = counts.head(head_n)
            leftover = int(counts.iloc[head_n:].sum())
        bars = [
            BarItem(category=json_safe_value(label), count=int(frequency))
            for label, frequency in selected.items()
        ]
        if leftover > 0:
            bars.append(BarItem(category="Other", count=leftover))

    return BarChart(
        title=f"Counts by {column}",
        column=column,
        x_label=column,
        data=BarData(bars=bars),
    )


def build_scatter(
    frame: pd.DataFrame,
    x_column: str,
    y_column: str,
    max_points: int = _SCATTER_DEFAULT,
) -> ScatterChart:
    _require_numeric(frame, x_column)
    _require_numeric(frame, y_column)
    cap = clamp_max_points(max_points)

    points_frame = pd.DataFrame(
        {
            "x": pd.to_numeric(frame[x_column], errors="coerce"),
            "y": pd.to_numeric(frame[y_column], errors="coerce"),
        }
    ).dropna()

    sampled = False
    if len(points_frame) > cap:
        points_frame = points_frame.sample(n=cap, random_state=0)
        sampled = True

    points = [
        ScatterPoint(x=json_safe_float(row.x), y=json_safe_float(row.y))
        for row in points_frame.itertuples(index=False)
    ]
    return ScatterChart(
        title=f"{x_column} vs {y_column}",
        x_column=x_column,
        y_column=y_column,
        x_label=x_column,
        y_label=y_column,
        sampled=sampled,
        point_count=len(points),
        data=ScatterData(points=points),
    )


def build_heatmap(frame: pd.DataFrame) -> HeatmapChart:
    names = numeric_column_names(frame)
    if len(names) < 2:
        return HeatmapChart(
            title="Pearson correlation",
            data=HeatmapData(columns=[], matrix=[]),
        )

    index = {name: position for position, name in enumerate(names)}
    size = len(names)
    matrix: list[list[float | None]] = [
        [1.0 if row == col else None for col in range(size)] for row in range(size)
    ]
    for pair in pearson_correlations(frame):
        row = index[pair.column_a]
        col = index[pair.column_b]
        matrix[row][col] = pair.coefficient
        matrix[col][row] = pair.coefficient

    return HeatmapChart(
        title="Pearson correlation",
        data=HeatmapData(columns=names, matrix=matrix),
    )
