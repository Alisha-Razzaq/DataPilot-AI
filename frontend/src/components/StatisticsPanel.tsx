import type { DatasetStatisticsResponse } from "../types/api";

interface StatisticsPanelProps {
  statistics: DatasetStatisticsResponse;
}

function formatMaybe(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return value.toFixed(3);
}

export function StatisticsPanel({ statistics }: StatisticsPanelProps) {
  if (statistics.numeric_columns.length === 0) {
    return (
      <section className="panel panel-priority" aria-labelledby="stats-heading">
        <div className="panel-header">
          <div>
            <h2 id="stats-heading">Numeric statistics</h2>
            <p>Quartiles, IQR fences, and Pearson correlations from the API.</p>
          </div>
        </div>
        <p className="empty-copy">
          This dataset has no numeric columns to summarize. Charts and the AI Data Analyst can
          still use categorical columns if any exist.
        </p>
      </section>
    );
  }

  return (
    <section className="panel panel-priority" aria-labelledby="stats-heading">
      <div className="panel-header">
        <div>
          <h2 id="stats-heading">Numeric statistics</h2>
          <p>Quartiles, IQR fences, and Pearson correlations computed by pandas on the server.</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">Quartiles and outlier counts by numeric column</caption>
          <thead>
            <tr>
              <th scope="col">Column</th>
              <th scope="col">n</th>
              <th scope="col">Q1</th>
              <th scope="col">Median</th>
              <th scope="col">Q3</th>
              <th scope="col">IQR</th>
              <th scope="col">Outliers</th>
            </tr>
          </thead>
          <tbody>
            {statistics.column_statistics.map((column) => (
              <tr key={column.name}>
                <th scope="row">{column.name}</th>
                <td>{column.count}</td>
                <td>{formatMaybe(column.quartiles.q1)}</td>
                <td>{formatMaybe(column.quartiles.q2)}</td>
                <td>{formatMaybe(column.quartiles.q3)}</td>
                <td>{formatMaybe(column.quartiles.iqr)}</td>
                <td>
                  {column.outliers.outlier_count} ({column.outliers.outlier_percentage}%)
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h3 className="subhead">Correlations</h3>
      {statistics.correlations.length === 0 ? (
        <p className="muted">Need at least two numeric columns for Pearson r.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">Pearson correlation pairs</caption>
            <thead>
              <tr>
                <th scope="col">Column A</th>
                <th scope="col">Column B</th>
                <th scope="col">Pearson r</th>
              </tr>
            </thead>
            <tbody>
              {statistics.correlations.map((pair) => (
                <tr key={`${pair.column_a}-${pair.column_b}`}>
                  <td>{pair.column_a}</td>
                  <td>{pair.column_b}</td>
                  <td>{formatMaybe(pair.coefficient)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
