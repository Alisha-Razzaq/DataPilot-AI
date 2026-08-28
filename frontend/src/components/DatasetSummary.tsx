import type {
  ChartType,
  DatasetProfileResponse,
  DatasetUploadResponse,
} from "../types/api";

interface DatasetSummaryProps {
  upload: DatasetUploadResponse;
  profile: DatasetProfileResponse;
  availableCharts: ChartType[];
}

const CHART_LABELS: Record<ChartType, string> = {
  histogram: "Histogram",
  bar: "Category counts",
  scatter: "Scatter",
  heatmap: "Correlation heatmap",
};

export function DatasetSummary({
  upload,
  profile,
  availableCharts,
}: DatasetSummaryProps) {
  const cards = [
    { label: "File", value: upload.original_filename },
    { label: "Rows", value: profile.rows.toLocaleString() },
    { label: "Columns", value: profile.columns.toLocaleString() },
    {
      label: "Duplicate rows",
      value: `${profile.duplicate_row_count.toLocaleString()} (${profile.duplicate_row_percentage.toFixed(2)}%)`,
    },
  ];

  const analysis = [
    "Column profile",
    "Numeric statistics",
    ...availableCharts.map((chart) => CHART_LABELS[chart]),
    "AI Data Analyst",
  ];

  return (
    <section className="panel dataset-context" aria-labelledby="dataset-heading">
      <div className="panel-header">
        <div>
          <h2 id="dataset-heading">Dataset</h2>
          <p>
            {upload.original_filename} · {profile.column_names.length} named columns
          </p>
        </div>
      </div>
      <div className="stat-grid">
        {cards.map((card) => (
          <article key={card.label} className="stat-card">
            <span className="stat-label">{card.label}</span>
            <strong className="stat-value">{card.value}</strong>
          </article>
        ))}
      </div>
      <div className="analysis-list">
        <h3 className="subhead">Available analysis</h3>
        <ul>
          {analysis.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </div>
    </section>
  );
}
