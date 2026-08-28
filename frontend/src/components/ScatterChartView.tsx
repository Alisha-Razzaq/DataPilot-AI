import {
  CartesianGrid,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartTheme } from "../chartTheme";
import type { ScatterResponse } from "../types/api";

interface ScatterChartViewProps {
  chart: ScatterResponse;
}

export function ScatterChartView({ chart }: ScatterChartViewProps) {
  const rows = chart.data.points
    .filter((point) => point.x !== null && point.y !== null)
    .map((point) => ({ x: point.x as number, y: point.y as number }));

  if (rows.length === 0) {
    return <p className="muted">No scatter points were returned.</p>;
  }

  return (
    <div className="chart-frame">
      <h3>
        {chart.title}
        {chart.sampled ? ` · sampled ${chart.point_count} points` : ""}
      </h3>
      <ResponsiveContainer width="100%" height={320}>
        <ScatterChart margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
          <XAxis
            dataKey="x"
            type="number"
            name={chart.x_label}
            tick={{ fill: chartTheme.tick, fontSize: 12 }}
          />
          <YAxis
            dataKey="y"
            type="number"
            name={chart.y_label}
            tick={{ fill: chartTheme.tick, fontSize: 12 }}
          />
          <Tooltip
            cursor={{ strokeDasharray: "3 3" }}
            contentStyle={chartTheme.tooltip}
          />
          <Scatter data={rows} fill={chartTheme.scatter} />
        </ScatterChart>
      </ResponsiveContainer>
    </div>
  );
}
