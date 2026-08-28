"""Pydantic schemas for visualization catalog and chart payloads."""

from typing import Literal

from pydantic import BaseModel

from app.models.profile import InferredType

ChartType = Literal["histogram", "bar", "scatter", "heatmap"]


class CatalogColumn(BaseModel):
    name: str
    inferred_type: InferredType
    charts: list[ChartType]


class VisualizationCatalog(BaseModel):
    columns: list[CatalogColumn]
    available_charts: list[ChartType]


class VisualizationCatalogResponse(VisualizationCatalog):
    dataset_id: str


class HistogramBin(BaseModel):
    bin_start: float | None = None
    bin_end: float | None = None
    count: int


class HistogramData(BaseModel):
    bins: list[HistogramBin]


class HistogramChart(BaseModel):
    chart_type: Literal["histogram"] = "histogram"
    title: str
    column: str
    bins: int
    x_label: str
    y_label: str = "count"
    data: HistogramData


class HistogramResponse(HistogramChart):
    dataset_id: str


class BarItem(BaseModel):
    category: str | int | float | bool | None
    count: int


class BarData(BaseModel):
    bars: list[BarItem]


class BarChart(BaseModel):
    chart_type: Literal["bar"] = "bar"
    title: str
    column: str
    x_label: str
    y_label: str = "count"
    data: BarData


class BarResponse(BarChart):
    dataset_id: str


class ScatterPoint(BaseModel):
    x: float | None = None
    y: float | None = None


class ScatterData(BaseModel):
    points: list[ScatterPoint]


class ScatterChart(BaseModel):
    chart_type: Literal["scatter"] = "scatter"
    title: str
    x_column: str
    y_column: str
    x_label: str
    y_label: str
    sampled: bool
    point_count: int
    data: ScatterData


class ScatterResponse(ScatterChart):
    dataset_id: str


class HeatmapData(BaseModel):
    columns: list[str]
    matrix: list[list[float | None]]


class HeatmapChart(BaseModel):
    chart_type: Literal["heatmap"] = "heatmap"
    title: str
    x_label: str = "column"
    y_label: str = "column"
    data: HeatmapData


class HeatmapResponse(HeatmapChart):
    dataset_id: str


class VisualizationError(Exception):
    """Invalid chart request, mapped to HTTP by the service/API layer."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)
