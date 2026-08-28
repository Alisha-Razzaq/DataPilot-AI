"""Deterministic dataset profiling with pandas.

This module is the source of numerical profile values. It does not touch HTTP,
the file registry, or the LLM.
"""

from __future__ import annotations

import math
import numbers
import re
from typing import Any

import pandas as pd

from app.models.profile import (
    CategoricalSummary,
    ColumnProfile,
    DatasetProfile,
    InferredType,
    NumericSummary,
    ValueCount,
)

TOP_VALUES_LIMIT = 10
_DATETIME_SAMPLE_SIZE = 100
_DATETIME_PARSE_THRESHOLD = 0.8
_TEXT_UNIQUE_RATIO = 0.5
_TEXT_UNIQUE_ABSOLUTE = 50

# Require an explicit date-like pattern so words and IDs are not coerced.
_DATE_HINT = re.compile(
    r"(?:"
    r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
    r"|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
    r"|"
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"
    r")"
)
_NUMERIC_TOKEN = re.compile(r"[+-]?(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?$")


def json_safe_value(value: Any) -> str | int | float | bool | None:
    """Convert a pandas/numpy scalar into a JSON-safe Python value."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if isinstance(value, bool):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    if isinstance(value, numbers.Real):
        number = float(value)
        return None if not math.isfinite(number) else number
    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def json_safe_float(value: Any) -> float | None:
    """Convert a numeric stat to float, mapping NaN/inf to None."""
    converted = json_safe_value(value)
    if converted is None or isinstance(converted, bool):
        return None
    if isinstance(converted, (int, float)):
        number = float(converted)
        return None if not math.isfinite(number) else number
    return None


def _percentage(part: int, whole: int) -> float:
    if whole == 0:
        return 0.0
    return round(100.0 * part / whole, 2)


def _looks_like_datetime(series: pd.Series) -> bool:
    """Return True only when most sampled values look like real dates."""
    non_null = series.dropna()
    if non_null.empty:
        return False

    sample = (
        non_null
        if len(non_null) <= _DATETIME_SAMPLE_SIZE
        else non_null.sample(n=_DATETIME_SAMPLE_SIZE, random_state=0)
    )
    as_text = sample.astype(str).str.strip()
    if as_text.str.fullmatch(_NUMERIC_TOKEN).all():
        return False
    if as_text.str.contains(_DATE_HINT, regex=True, na=False).mean() < (
        _DATETIME_PARSE_THRESHOLD
    ):
        return False

    parsed = pd.to_datetime(as_text, errors="coerce", format="mixed")
    return float(parsed.notna().mean()) >= _DATETIME_PARSE_THRESHOLD


def _looks_like_numeric(series: pd.Series) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False
    converted = pd.to_numeric(non_null, errors="coerce")
    return float(converted.notna().mean()) >= 0.95


def _looks_like_boolean(series: pd.Series) -> bool:
    non_null = series.dropna()
    if non_null.empty:
        return False
    tokens = {str(item).strip().lower() for item in non_null.tolist()}
    return tokens <= {"true", "false"} and len(tokens) > 0


def infer_column_type(series: pd.Series) -> InferredType:
    """Classify a column into a high-level type without raising on messy data."""
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"

    if series.dropna().empty:
        return "text"
    if _looks_like_boolean(series):
        return "boolean"
    if _looks_like_datetime(series):
        return "datetime"
    if _looks_like_numeric(series):
        return "numeric"

    non_null = int(series.notna().sum())
    unique_count = int(series.nunique(dropna=True))
    unique_ratio = (unique_count / non_null) if non_null else 0.0
    # Small samples often have a high unique ratio even when they are categories
    # (e.g. 2 regions in 3 rows). Require enough rows before using the ratio.
    if unique_count > _TEXT_UNIQUE_ABSOLUTE:
        return "text"
    if non_null >= 20 and unique_ratio > _TEXT_UNIQUE_RATIO:
        return "text"
    return "categorical"


def profile_numeric_column(series: pd.Series) -> NumericSummary:
    """Return count/mean/median/std/min/max for numeric-like values."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    count = int(numeric.shape[0])
    if count == 0:
        return NumericSummary(count=0)
    std = json_safe_float(numeric.std(ddof=1)) if count >= 2 else None
    return NumericSummary(
        count=count,
        mean=json_safe_float(numeric.mean()),
        median=json_safe_float(numeric.median()),
        std=std,
        min=json_safe_float(numeric.min()),
        max=json_safe_float(numeric.max()),
    )


def profile_categorical_column(series: pd.Series) -> CategoricalSummary:
    """Return unique/mode/top-N counts. Always capped at TOP_VALUES_LIMIT."""
    non_null = series.dropna()
    unique_count = int(non_null.nunique(dropna=True))
    if non_null.empty:
        return CategoricalSummary(unique_count=0, top_values=[])

    counts = non_null.value_counts(dropna=True)
    top = counts.head(TOP_VALUES_LIMIT)
    most_value = json_safe_value(top.index[0])
    most_count = int(top.iloc[0])
    top_values = [
        ValueCount(value=json_safe_value(label), count=int(frequency))
        for label, frequency in top.items()
    ]
    return CategoricalSummary(
        unique_count=unique_count,
        most_frequent_value=most_value,
        most_frequent_count=most_count,
        top_values=top_values,
    )


def _profile_column(name: str, series: pd.Series, row_count: int) -> ColumnProfile:
    missing_count = int(series.isna().sum())
    non_null_count = int(series.notna().sum())
    inferred = infer_column_type(series)

    numeric_summary = None
    categorical_summary = None
    if inferred == "numeric":
        numeric_summary = profile_numeric_column(series)
    elif inferred in {"categorical", "boolean", "text"}:
        categorical_summary = profile_categorical_column(series)

    return ColumnProfile(
        name=name,
        pandas_dtype=str(series.dtype),
        inferred_type=inferred,
        non_null_count=non_null_count,
        missing_count=missing_count,
        missing_percentage=_percentage(missing_count, row_count),
        unique_count=int(series.nunique(dropna=True)),
        numeric_summary=numeric_summary,
        categorical_summary=categorical_summary,
    )


def profile_dataset(frame: pd.DataFrame) -> DatasetProfile:
    """Build a JSON-safe profile for an in-memory DataFrame."""
    rows = int(frame.shape[0])
    columns = int(frame.shape[1])
    column_names = [str(name) for name in frame.columns]
    duplicate_row_count = int(frame.duplicated().sum())

    return DatasetProfile(
        rows=rows,
        columns=columns,
        column_names=column_names,
        duplicate_row_count=duplicate_row_count,
        duplicate_row_percentage=_percentage(duplicate_row_count, rows),
        column_profiles=[
            _profile_column(str(name), frame[name], rows) for name in frame.columns
        ],
    )
