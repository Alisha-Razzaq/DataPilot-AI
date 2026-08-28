import type { ColumnProfile } from "../types/api";

interface ProfileTableProps {
  columns: ColumnProfile[];
}

function formatMaybe(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }
  return Number.isInteger(value) ? String(value) : value.toFixed(3);
}

export function ProfileTable({ columns }: ProfileTableProps) {
  if (columns.length === 0) {
    return (
      <section className="panel" aria-labelledby="profile-heading">
        <div className="panel-header">
          <div>
            <h2 id="profile-heading">Column profile</h2>
            <p>Types, missingness, and summaries from the backend profiler.</p>
          </div>
        </div>
        <p className="empty-copy">No column profiles were returned for this dataset.</p>
      </section>
    );
  }

  return (
    <section className="panel" aria-labelledby="profile-heading">
      <div className="panel-header">
        <div>
          <h2 id="profile-heading">Column profile</h2>
          <p>Types, missingness, and summaries from the backend profiler.</p>
        </div>
      </div>
      <div className="table-wrap">
        <table>
          <caption className="sr-only">Column types, uniqueness, and missingness</caption>
          <thead>
            <tr>
              <th scope="col">Column</th>
              <th scope="col">Type</th>
              <th scope="col">Unique</th>
              <th scope="col">Missing</th>
              <th scope="col">Missing %</th>
              <th scope="col">Numeric / categorical</th>
            </tr>
          </thead>
          <tbody>
            {columns.map((column) => (
              <tr key={column.name}>
                <th scope="row">{column.name}</th>
                <td>
                  <span className={`type-badge type-${column.inferred_type}`}>
                    {column.inferred_type}
                  </span>
                </td>
                <td>{column.unique_count}</td>
                <td>{column.missing_count}</td>
                <td>{column.missing_percentage.toFixed(2)}%</td>
                <td className="summary-cell">
                  {column.numeric_summary ? (
                    <span>
                      mean {formatMaybe(column.numeric_summary.mean)}, min{" "}
                      {formatMaybe(column.numeric_summary.min)}, max{" "}
                      {formatMaybe(column.numeric_summary.max)}
                    </span>
                  ) : null}
                  {column.categorical_summary ? (
                    <span>
                      top {String(column.categorical_summary.most_frequent_value)} (
                      {column.categorical_summary.most_frequent_count ?? 0})
                    </span>
                  ) : null}
                  {!column.numeric_summary && !column.categorical_summary ? "—" : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
