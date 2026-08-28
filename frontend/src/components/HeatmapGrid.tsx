import type { HeatmapResponse } from "../types/api";

interface HeatmapGridProps {
  chart: HeatmapResponse;
}

function cellColor(value: number | null): string {
  if (value === null) {
    return "#f3f4f6";
  }
  const t = (value + 1) / 2;
  const r = Math.round(254 - t * 79);
  const g = Math.round(226 + (1 - Math.abs(value)) * 18 - t * 12);
  const b = Math.round(226 + t * 28);
  return `rgb(${r}, ${g}, ${b})`;
}

export function HeatmapGrid({ chart }: HeatmapGridProps) {
  const { columns, matrix } = chart.data;
  if (columns.length === 0 || matrix.length === 0) {
    return (
      <p className="muted">
        A heatmap needs at least two numeric columns. None were available.
      </p>
    );
  }

  return (
    <div className="chart-frame">
      <h3>{chart.title}</h3>
      <div className="heatmap-wrap">
        <table className="heatmap">
          <caption className="sr-only">Pearson correlation matrix</caption>
          <thead>
            <tr>
              <th />
              {columns.map((column) => (
                <th key={column}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {matrix.map((row, rowIndex) => (
              <tr key={columns[rowIndex]}>
                <th scope="row">{columns[rowIndex]}</th>
                {row.map((value, colIndex) => (
                  <td
                    key={`${rowIndex}-${colIndex}`}
                    style={{ background: cellColor(value) }}
                    title={`${columns[rowIndex]} × ${columns[colIndex]}: ${value ?? "n/a"}`}
                  >
                    {value === null ? "—" : value.toFixed(2)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
