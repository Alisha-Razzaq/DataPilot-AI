"""Unit tests for the analysis-layer profiler (no HTTP)."""

import math

import pandas as pd

from app.analysis.profiler import (
    TOP_VALUES_LIMIT,
    infer_column_type,
    profile_categorical_column,
    profile_dataset,
    profile_numeric_column,
)


def _mixed_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "region": ["east", "west", "east", "east"],
            "sales": [100.0, 200.0, None, 100.0],
            "active": [True, False, True, True],
            "order_date": ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-01"],
            "notes": [None, None, None, None],
        }
    )


def test_profile_mixed_dataset_shape_and_names() -> None:
    profile = profile_dataset(_mixed_frame())
    assert profile.rows == 4
    assert profile.columns == 5
    assert profile.column_names == [
        "region",
        "sales",
        "active",
        "order_date",
        "notes",
    ]


def test_profile_missing_values_and_percentages() -> None:
    profile = profile_dataset(_mixed_frame())
    by_name = {column.name: column for column in profile.column_profiles}

    assert by_name["sales"].missing_count == 1
    assert by_name["sales"].non_null_count == 3
    assert by_name["sales"].missing_percentage == 25.0
    assert by_name["notes"].missing_count == 4
    assert by_name["notes"].missing_percentage == 100.0
    assert by_name["notes"].unique_count == 0


def test_profile_duplicate_rows() -> None:
    frame = pd.DataFrame(
        {
            "region": ["east", "west", "east"],
            "sales": [10, 20, 10],
        }
    )
    profile = profile_dataset(frame)
    assert profile.duplicate_row_count == 1
    assert profile.duplicate_row_percentage == 33.33


def test_numeric_summary() -> None:
    series = pd.Series([10.0, 20.0, None, 30.0])
    summary = profile_numeric_column(series)
    assert summary.count == 3
    assert summary.mean == 20.0
    assert summary.median == 20.0
    assert summary.min == 10.0
    assert summary.max == 30.0
    assert summary.std is not None
    assert math.isclose(summary.std, 10.0)


def test_numeric_summary_handles_nan_and_single_value() -> None:
    empty = profile_numeric_column(pd.Series([float("nan"), float("nan")]))
    assert empty.count == 0
    assert empty.mean is None
    assert empty.std is None

    single = profile_numeric_column(pd.Series([5.0]))
    assert single.count == 1
    assert single.mean == 5.0
    assert single.std is None


def test_categorical_summary_and_unique_counts() -> None:
    profile = profile_dataset(_mixed_frame())
    region = next(
        column for column in profile.column_profiles if column.name == "region"
    )
    assert region.inferred_type == "categorical"
    assert region.unique_count == 2
    assert region.categorical_summary is not None
    assert region.categorical_summary.unique_count == 2
    assert region.categorical_summary.most_frequent_value == "east"
    assert region.categorical_summary.most_frequent_count == 3
    assert region.categorical_summary.top_values[0].value == "east"
    assert region.categorical_summary.top_values[0].count == 3


def test_empty_column_does_not_crash() -> None:
    profile = profile_dataset(pd.DataFrame({"empty": [None, None, None]}))
    column = profile.column_profiles[0]
    assert column.missing_count == 3
    assert column.unique_count == 0
    assert column.inferred_type == "text"
    assert column.categorical_summary is not None
    assert column.categorical_summary.top_values == []


def test_high_cardinality_column_is_capped() -> None:
    frame = pd.DataFrame({"user_id": [f"user-{index}" for index in range(80)]})
    profile = profile_dataset(frame)
    column = profile.column_profiles[0]
    assert column.inferred_type == "text"
    assert column.unique_count == 80
    assert column.categorical_summary is not None
    assert len(column.categorical_summary.top_values) <= TOP_VALUES_LIMIT
    assert len(column.categorical_summary.top_values) == TOP_VALUES_LIMIT


def test_infer_datetime_versus_plain_text() -> None:
    dates = pd.Series(["2024-01-01", "2024-02-15", "2024-03-20"])
    cities = pd.Series(["Karachi", "Lahore", "Islamabad"])
    assert infer_column_type(dates) == "datetime"
    assert infer_column_type(cities) == "categorical"


def test_infer_boolean_and_numeric() -> None:
    assert infer_column_type(pd.Series([True, False, True])) == "boolean"
    assert infer_column_type(pd.Series([1, 2, 3])) == "numeric"


def test_mixed_type_column_does_not_crash() -> None:
    series = pd.Series([1, "two", 3, None])
    inferred = infer_column_type(series)
    assert inferred in {"text", "categorical"}
    summary = profile_categorical_column(series)
    assert summary.unique_count == 3
    assert len(summary.top_values) <= TOP_VALUES_LIMIT
