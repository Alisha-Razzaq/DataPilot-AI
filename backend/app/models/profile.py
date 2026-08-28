"""Pydantic schemas for the dataset profile response."""

from typing import Literal

from pydantic import BaseModel, Field

InferredType = Literal["numeric", "categorical", "boolean", "datetime", "text"]


class NumericSummary(BaseModel):
    """Basic descriptive stats for a numeric column (profile endpoint)."""

    count: int = Field(description="Non-missing numeric values.")
    mean: float | None = None
    median: float | None = None
    std: float | None = Field(
        default=None,
        description="Sample standard deviation (ddof=1). Null if fewer than 2 values.",
    )
    min: float | None = None
    max: float | None = None


class ValueCount(BaseModel):
    value: str | int | float | bool | None
    count: int


class CategoricalSummary(BaseModel):
    unique_count: int
    most_frequent_value: str | int | float | bool | None = None
    most_frequent_count: int | None = None
    top_values: list[ValueCount] = Field(
        default_factory=list,
        description="Up to 10 most frequent values. Never the full domain.",
    )


class ColumnProfile(BaseModel):
    name: str
    pandas_dtype: str
    inferred_type: InferredType
    non_null_count: int
    missing_count: int
    missing_percentage: float
    unique_count: int
    numeric_summary: NumericSummary | None = None
    categorical_summary: CategoricalSummary | None = None


class DatasetProfile(BaseModel):
    """Profile body produced by the analysis layer (no dataset_id)."""

    rows: int
    columns: int
    column_names: list[str]
    duplicate_row_count: int
    duplicate_row_percentage: float
    column_profiles: list[ColumnProfile]


class DatasetProfileResponse(BaseModel):
    """Public GET /profile payload, including the registry dataset_id."""

    dataset_id: str
    rows: int
    columns: int
    column_names: list[str]
    duplicate_row_count: int
    duplicate_row_percentage: float
    column_profiles: list[ColumnProfile]
