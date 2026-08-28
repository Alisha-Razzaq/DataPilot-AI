"""Deeper numeric statistics: Pearson correlation, quartiles, IQR outliers.

Uses pandas/numpy only. This module does not touch HTTP or the file registry.
"""

from __future__ import annotations

import pandas as pd

from app.analysis.profiler import infer_column_type, json_safe_float
from app.models.statistics import (
    CorrelationPair,
    DatasetStatistics,
    NumericColumnStatistics,
    OutlierSummary,
    QuartileSummary,
)

_IQR_MULTIPLIER = 1.5
_OUTLIER_SAMPLE_LIMIT = 10
_CORR_MIN_PERIODS = 2


def numeric_column_names(frame: pd.DataFrame) -> list[str]:
    """Return columns the profiler would classify as numeric."""
    return [
        str(name)
        for name in frame.columns
        if infer_column_type(frame[name]) == "numeric"
    ]


def _numeric_frame(frame: pd.DataFrame) -> pd.DataFrame:
    names = numeric_column_names(frame)
    if not names:
        return pd.DataFrame()
    return frame.loc[:, names].apply(pd.to_numeric, errors="coerce")


def compute_quartiles(series: pd.Series) -> QuartileSummary:
    """Return Q1, median (Q2), Q3, and IQR for a numeric series."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    if numeric.empty:
        return QuartileSummary()
    q1 = json_safe_float(numeric.quantile(0.25))
    q2 = json_safe_float(numeric.quantile(0.50))
    q3 = json_safe_float(numeric.quantile(0.75))
    iqr = None
    if q1 is not None and q3 is not None:
        iqr = json_safe_float(q3 - q1)
    return QuartileSummary(q1=q1, q2=q2, q3=q3, iqr=iqr)


def detect_iqr_outliers(series: pd.Series) -> OutlierSummary:
    """Flag values outside the 1.5 IQR fences. Does not return every value."""
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    count = int(numeric.shape[0])
    if count == 0:
        return OutlierSummary()

    quartiles = compute_quartiles(numeric)
    if quartiles.q1 is None or quartiles.q3 is None or quartiles.iqr is None:
        return OutlierSummary()

    lower = quartiles.q1 - _IQR_MULTIPLIER * quartiles.iqr
    upper = quartiles.q3 + _IQR_MULTIPLIER * quartiles.iqr
    mask = (numeric < lower) | (numeric > upper)
    flagged = numeric.loc[mask]
    outlier_count = int(flagged.shape[0])
    sample = [
        value
        for value in (json_safe_float(item) for item in flagged.head(_OUTLIER_SAMPLE_LIMIT))
        if value is not None
    ]
    percentage = round(100.0 * outlier_count / count, 2) if count else 0.0
    return OutlierSummary(
        method="iqr",
        lower_fence=json_safe_float(lower),
        upper_fence=json_safe_float(upper),
        outlier_count=outlier_count,
        outlier_percentage=percentage,
        sample_values=sample,
    )


def pearson_correlations(frame: pd.DataFrame) -> list[CorrelationPair]:
    """Pairwise Pearson r for unique numeric column pairs (excludes the diagonal)."""
    numeric = _numeric_frame(frame)
    if numeric.shape[1] < 2:
        return []

    corr = numeric.corr(method="pearson", min_periods=_CORR_MIN_PERIODS)
    names = [str(name) for name in corr.columns]
    pairs: list[CorrelationPair] = []
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            pairs.append(
                CorrelationPair(
                    column_a=left,
                    column_b=right,
                    coefficient=json_safe_float(corr.loc[left, right]),
                )
            )
    return pairs


def summarize_numeric_columns(frame: pd.DataFrame) -> list[NumericColumnStatistics]:
    numeric = _numeric_frame(frame)
    summaries: list[NumericColumnStatistics] = []
    for name in numeric.columns:
        series = numeric[name]
        summaries.append(
            NumericColumnStatistics(
                name=str(name),
                count=int(series.notna().sum()),
                quartiles=compute_quartiles(series),
                outliers=detect_iqr_outliers(series),
            )
        )
    return summaries


def analyze_dataset_statistics(frame: pd.DataFrame) -> DatasetStatistics:
    """Build JSON-safe correlation, quartile, and IQR-outlier statistics."""
    return DatasetStatistics(
        numeric_columns=numeric_column_names(frame),
        column_statistics=summarize_numeric_columns(frame),
        correlations=pearson_correlations(frame),
    )
