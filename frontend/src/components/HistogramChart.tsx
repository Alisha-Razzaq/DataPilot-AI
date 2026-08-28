import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { chartTheme } from "../chartTheme";
import type { HistogramResponse } from "../types/api";

interface HistogramChartProps {
  chart: HistogramResponse;
}

export function HistogramChart({ chart }: HistogramChartProps) {
  const rows = chart.data.bins.map((bin, index) => ({
    name: `${bin.bin_start ?? "?"}–${bin.bin_end ?? "?"}`,
    count: bin.count,
    key: index,
  }));

  if (rows.length === 0) {
    return <p className="muted">No histogram bins were returned for this column.</p>;
  }

  return (
    <div className="chart-frame">
      <h3>{chart.title}</h3>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
          <XAxis
            dataKey="name"
            tick={{ fill: chartTheme.tick, fontSize: 11 }}
            interval={0}
            angle={-20}
            textAnchor="end"
            height={64}
          />
          <YAxis tick={{ fill: chartTheme.tick, fontSize: 12 }} />
          <Tooltip contentStyle={chartTheme.tooltip} />
          <Bar dataKey="count" fill={chartTheme.bar} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
