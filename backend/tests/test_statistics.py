"""Unit tests for Pearson correlation, quartiles, and IQR outliers."""

import math

import pandas as pd

from app.analysis.statistics import (
    analyze_dataset_statistics,
    compute_quartiles,
    detect_iqr_outliers,
    pearson_correlations,
)


def test_pearson_perfect_positive_correlation() -> None:
    frame = pd.DataFrame({"x": [1.0, 2.0, 3.0, 4.0], "y": [2.0, 4.0, 6.0, 8.0]})
    pairs = pearson_correlations(frame)
    assert len(pairs) == 1
    assert pairs[0].column_a == "x"
    assert pairs[0].column_b == "y"
    assert pairs[0].coefficient is not None
    assert math.isclose(pairs[0].coefficient, 1.0)


def test_pearson_requires_two_numeric_columns() -> None:
    only_one = pd.DataFrame({"sales": [10.0, 20.0, 30.0], "region": ["a", "b", "c"]})
    none_numeric = pd.DataFrame({"region": ["east", "west"], "status": ["ok", "ok"]})
    assert pearson_correlations(only_one) == []
    assert pearson_correlations(none_numeric) == []


def test_quartiles_of_simple_series() -> None:
    summary = compute_quartiles(pd.Series([1.0, 2.0, 3.0, 4.0, 5.0]))
    assert summary.q1 == 2.0
    assert summary.q2 == 3.0
    assert summary.q3 == 4.0
    assert summary.iqr == 2.0


def test_iqr_outlier_detection() -> None:
    series = pd.Series([10.0, 12.0, 11.0, 13.0, 10.0, 12.0, 100.0])
    result = detect_iqr_outliers(series)
    assert result.method == "iqr"
    assert result.outlier_count == 1
    assert 100.0 in result.sample_values
    assert result.lower_fence is not None
    assert result.upper_fence is not None
    assert result.upper_fence < 100.0


def test_iqr_handles_empty_and_constant_series() -> None:
    empty = detect_iqr_outliers(pd.Series([float("nan"), float("nan")]))
    assert empty.outlier_count == 0
    assert empty.sample_values == []

    constant = detect_iqr_outliers(pd.Series([5.0, 5.0, 5.0, 5.0]))
    assert constant.outlier_count == 0
    assert constant.lower_fence == 5.0
    assert constant.upper_fence == 5.0


def test_analyze_dataset_statistics_mixed_frame() -> None:
    frame = pd.DataFrame(
        {
            "region": ["east", "west", "east", "west"],
            "sales": [10.0, 20.0, 30.0, 40.0],
            "profit": [1.0, 2.0, 3.0, 4.0],
        }
    )
    stats = analyze_dataset_statistics(frame)
    assert stats.numeric_columns == ["sales", "profit"]
    assert len(stats.column_statistics) == 2
    assert len(stats.correlations) == 1
    assert stats.correlations[0].coefficient is not None
    assert math.isclose(stats.correlations[0].coefficient, 1.0)
    sales = next(item for item in stats.column_statistics if item.name == "sales")
    assert sales.quartiles.q2 == 25.0
    assert sales.outliers.outlier_count == 0
