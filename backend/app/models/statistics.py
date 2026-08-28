"""Pydantic schemas for GET /statistics responses."""

from pydantic import BaseModel, Field


class QuartileSummary(BaseModel):
    """Tukey quartiles. q2 is the median."""

    q1: float | None = None
    q2: float | None = None
    q3: float | None = None
    iqr: float | None = Field(default=None, description="Q3 minus Q1.")


class OutlierSummary(BaseModel):
    """IQR-fence outliers. Values outside [Q1 - 1.5 IQR, Q3 + 1.5 IQR]."""

    method: str = "iqr"
    lower_fence: float | None = None
    upper_fence: float | None = None
    outlier_count: int = 0
    outlier_percentage: float = 0.0
    sample_values: list[float] = Field(
        default_factory=list,
        description="Up to 10 example outlier values. Not the full list.",
    )


class NumericColumnStatistics(BaseModel):
    name: str
    count: int
    quartiles: QuartileSummary
    outliers: OutlierSummary


class CorrelationPair(BaseModel):
    column_a: str
    column_b: str
    coefficient: float | None = Field(
        default=None,
        description="Pearson r. Null if it cannot be computed.",
    )


class DatasetStatistics(BaseModel):
    """Analysis-layer body (no dataset_id)."""

    numeric_columns: list[str]
    column_statistics: list[NumericColumnStatistics]
    correlations: list[CorrelationPair]


class DatasetStatisticsResponse(BaseModel):
    """Public GET /statistics payload."""

    dataset_id: str
    numeric_columns: list[str]
    column_statistics: list[NumericColumnStatistics]
    correlations: list[CorrelationPair]
