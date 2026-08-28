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
import type { BarResponse } from "../types/api";

interface BarChartViewProps {
  chart: BarResponse;
}

export function BarChartView({ chart }: BarChartViewProps) {
  const rows = chart.data.bars.map((bar) => ({
    category: String(bar.category ?? "—"),
    count: bar.count,
  }));

  if (rows.length === 0) {
    return <p className="muted">No categories were returned for this column.</p>;
  }

  return (
    <div className="chart-frame">
      <h3>{chart.title}</h3>
      <ResponsiveContainer width="100%" height={320}>
        <BarChart data={rows} margin={{ top: 8, right: 8, left: 0, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartTheme.grid} />
          <XAxis dataKey="category" tick={{ fill: chartTheme.tick, fontSize: 12 }} />
          <YAxis tick={{ fill: chartTheme.tick, fontSize: 12 }} />
          <Tooltip contentStyle={chartTheme.tooltip} />
          <Bar dataKey="count" fill={chartTheme.barAlt} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
