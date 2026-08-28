export type InferredType =
  | "numeric"
  | "categorical"
  | "boolean"
  | "datetime"
  | "text";

export type ChartType = "histogram" | "bar" | "scatter" | "heatmap";

export interface DatasetUploadResponse {
  dataset_id: string;
  original_filename: string;
  rows: number;
  columns: number;
  column_names: string[];
}

export interface NumericSummary {
  count: number;
  mean: number | null;
  median: number | null;
  std: number | null;
  min: number | null;
  max: number | null;
}

export interface ValueCount {
  value: string | number | boolean | null;
  count: number;
}

export interface CategoricalSummary {
  unique_count: number;
  most_frequent_value: string | number | boolean | null;
  most_frequent_count: number | null;
  top_values: ValueCount[];
}

export interface ColumnProfile {
  name: string;
  pandas_dtype: string;
  inferred_type: InferredType;
  non_null_count: number;
  missing_count: number;
  missing_percentage: number;
  unique_count: number;
  numeric_summary: NumericSummary | null;
  categorical_summary: CategoricalSummary | null;
}

export interface DatasetProfileResponse {
  dataset_id: string;
  rows: number;
  columns: number;
  column_names: string[];
  duplicate_row_count: number;
  duplicate_row_percentage: number;
  column_profiles: ColumnProfile[];
}

export interface QuartileSummary {
  q1: number | null;
  q2: number | null;
  q3: number | null;
  iqr: number | null;
}

export interface OutlierSummary {
  method: string;
  lower_fence: number | null;
  upper_fence: number | null;
  outlier_count: number;
  outlier_percentage: number;
  sample_values: number[];
}

export interface NumericColumnStatistics {
  name: string;
  count: number;
  quartiles: QuartileSummary;
  outliers: OutlierSummary;
}

export interface CorrelationPair {
  column_a: string;
  column_b: string;
  coefficient: number | null;
}

export interface DatasetStatisticsResponse {
  dataset_id: string;
  numeric_columns: string[];
  column_statistics: NumericColumnStatistics[];
  correlations: CorrelationPair[];
}

export interface CatalogColumn {
  name: string;
  inferred_type: InferredType;
  charts: ChartType[];
}

export interface VisualizationCatalogResponse {
  dataset_id: string;
  columns: CatalogColumn[];
  available_charts: ChartType[];
}

export interface HistogramResponse {
  dataset_id: string;
  chart_type: "histogram";
  title: string;
  column: string;
  bins: number;
  x_label: string;
  y_label: string;
  data: { bins: { bin_start: number | null; bin_end: number | null; count: number }[] };
}

export interface BarResponse {
  dataset_id: string;
  chart_type: "bar";
  title: string;
  column: string;
  x_label: string;
  y_label: string;
  data: { bars: { category: string | number | boolean | null; count: number }[] };
}

export interface ScatterResponse {
  dataset_id: string;
  chart_type: "scatter";
  title: string;
  x_column: string;
  y_column: string;
  x_label: string;
  y_label: string;
  sampled: boolean;
  point_count: number;
  data: { points: { x: number | null; y: number | null }[] };
}

export interface HeatmapResponse {
  dataset_id: string;
  chart_type: "heatmap";
  title: string;
  x_label: string;
  y_label: string;
  data: { columns: string[]; matrix: Array<Array<number | null>> };
}

export interface ChatResponse {
  dataset_id: string;
  message: string;
  tool_used: string | null;
  tools_used: string[];
}

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}
