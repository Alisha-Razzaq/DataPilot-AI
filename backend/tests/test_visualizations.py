"""Unit tests for chart-data builders (no HTTP)."""

import json

import pandas as pd

from app.analysis.visualizations import (
    build_bar,
    build_catalog,
    build_heatmap,
    build_histogram,
    build_scatter,
    clamp_bins,
    clamp_max_points,
)
from app.models.visualization import VisualizationError


def _mixed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["east", "west", "east", "east"],
            "sales": [10.0, 20.0, 30.0, 40.0],
            "profit": [1.0, 2.0, 3.0, 4.0],
        }
    )


def test_histogram_bins_and_counts() -> None:
    chart = build_histogram(_mixed_frame(), "sales", bins=5)
    assert chart.chart_type == "histogram"
    assert chart.column == "sales"
    assert chart.bins == 5
    assert len(chart.data.bins) == 5
    assert sum(item.count for item in chart.data.bins) == 4


def test_histogram_clamps_bin_count() -> None:
    chart = build_histogram(_mixed_frame(), "sales", bins=2)
    assert chart.bins == 5


def test_histogram_rejects_non_numeric_and_unknown() -> None:
    frame = _mixed_frame()
    try:
        build_histogram(frame, "region", bins=10)
        raise AssertionError("expected VisualizationError")
    except VisualizationError as exc:
        assert exc.status_code == 400
    try:
        build_histogram(frame, "missing", bins=10)
        raise AssertionError("expected VisualizationError")
    except VisualizationError as exc:
        assert exc.status_code == 400
        assert "Unknown column" in exc.detail


def test_bar_chart_counts() -> None:
    chart = build_bar(_mixed_frame(), "region", limit=15)
    assert chart.chart_type == "bar"
    by_category = {item.category: item.count for item in chart.data.bars}
    assert by_category["east"] == 3
    assert by_category["west"] == 1


def test_bar_rejects_numeric_column() -> None:
    try:
        build_bar(_mixed_frame(), "sales", limit=10)
        raise AssertionError("expected VisualizationError")
    except VisualizationError as exc:
        assert exc.status_code == 400


def test_scatter_points() -> None:
    chart = build_scatter(_mixed_frame(), "sales", "profit", max_points=500)
    assert chart.chart_type == "scatter"
    assert chart.sampled is False
    assert chart.point_count == 4
    assert chart.data.points[0].x == 10.0
    assert chart.data.points[0].y == 1.0


def test_scatter_sampling_is_capped_and_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "x": list(range(40)),
            "y": [value * 2 for value in range(40)],
        }
    )
    first = build_scatter(frame, "x", "y", max_points=10)
    second = build_scatter(frame, "x", "y", max_points=10)
    assert first.sampled is True
    assert first.point_count == 10
    assert first.data.points == second.data.points
    assert clamp_max_points(5000) == 2000


def test_heatmap_reuses_pearson_pairs() -> None:
    chart = build_heatmap(_mixed_frame())
    assert chart.chart_type == "heatmap"
    assert chart.data.columns == ["sales", "profit"]
    assert chart.data.matrix[0][0] == 1.0
    assert chart.data.matrix[1][1] == 1.0
    assert chart.data.matrix[0][1] == 1.0
    assert chart.data.matrix[1][0] == 1.0


def test_heatmap_insufficient_numeric_columns() -> None:
    frame = pd.DataFrame({"region": ["east", "west"], "status": ["ok", "ok"]})
    chart = build_heatmap(frame)
    assert chart.data.columns == []
    assert chart.data.matrix == []


def test_catalog_lists_supported_charts() -> None:
    catalog = build_catalog(_mixed_frame())
    by_name = {item.name: item for item in catalog.columns}
    assert "histogram" in by_name["sales"].charts
    assert "bar" in by_name["region"].charts
    assert "scatter" in catalog.available_charts
    assert "heatmap" in catalog.available_charts


def test_chart_payloads_are_json_serializable() -> None:
    frame = _mixed_frame()
    payloads = [
        build_histogram(frame, "sales", bins=5).model_dump(),
        build_bar(frame, "region", limit=10).model_dump(),
        build_scatter(frame, "sales", "profit").model_dump(),
        build_heatmap(frame).model_dump(),
        build_catalog(frame).model_dump(),
    ]
    for payload in payloads:
        encoded = json.dumps(payload)
        assert "NaN" not in encoded
        assert "stored_path" not in encoded


def test_clamp_bins_bounds() -> None:
    assert clamp_bins(2) == 5
    assert clamp_bins(80) == 50
