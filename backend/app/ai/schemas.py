"""Provider-independent tool definitions and tool result models.

These schemas describe what DataPilot can do. They are not tied to OpenAI,
Anthropic, or any other vendor. Phase 8 can map them into a vendor format.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.profile import ColumnProfile
from app.models.statistics import CorrelationPair, OutlierSummary, QuartileSummary
from app.models.visualization import BarItem, HistogramBin, ScatterPoint

JsonType = Literal["string", "integer"]


class ToolParameterSchema(BaseModel):
    """One JSON-Schema-like property. Easy to copy into an LLM tool spec later."""

    type: JsonType
    description: str
    default: int | None = None


class ToolParametersSchema(BaseModel):
    type: Literal["object"] = "object"
    properties: dict[str, ToolParameterSchema]
    required: list[str]
    additionalProperties: bool = False


class ToolDefinition(BaseModel):
    """Catalog entry for one explicit Python tool function."""

    name: str
    description: str
    parameters: ToolParametersSchema


class ToolCatalogResponse(BaseModel):
    """GET /api/tools payload. Describes tools; does not execute them."""

    tools: list[ToolDefinition]


class DatasetSummaryResult(BaseModel):
    dataset_id: str
    rows: int
    columns: int
    column_names: list[str]
    duplicate_row_count: int
    duplicate_row_percentage: float


class ColumnProfileResult(BaseModel):
    dataset_id: str
    column: ColumnProfile


class NumericStatisticsResult(BaseModel):
    dataset_id: str
    column: str
    count: int
    mean: float | None = None
    median: float | None = None
    std: float | None = None
    min: float | None = None
    max: float | None = None
    quartiles: QuartileSummary
    outliers: OutlierSummary


class CorrelationsResult(BaseModel):
    dataset_id: str
    numeric_columns: list[str]
    correlations: list[CorrelationPair]


class OutliersResult(BaseModel):
    dataset_id: str
    column: str
    outliers: OutlierSummary


class HistogramResult(BaseModel):
    dataset_id: str
    column: str
    bins: int
    title: str
    data: list[HistogramBin]


class CategoryCountsResult(BaseModel):
    dataset_id: str
    column: str
    categories: list[BarItem]


class ScatterResult(BaseModel):
    dataset_id: str
    x_column: str
    y_column: str
    sampled: bool
    point_count: int
    points: list[ScatterPoint]


class HeatmapResult(BaseModel):
    dataset_id: str
    title: str
    columns: list[str] = Field(description="Numeric column names in matrix order.")
    matrix: list[list[float | None]]


