import { useEffect, useMemo, useState } from "react";

import {
  fetchBar,
  fetchHeatmap,
  fetchHistogram,
  fetchScatter,
} from "../services/api";
import { ApiError } from "../types/api";
import type {
  BarResponse,
  HeatmapResponse,
  HistogramResponse,
  ScatterResponse,
  VisualizationCatalogResponse,
} from "../types/api";
import { BarChartView } from "./BarChartView";
import { HeatmapGrid } from "./HeatmapGrid";
import { HistogramChart } from "./HistogramChart";
import { ScatterChartView } from "./ScatterChartView";
import { StatusMessage } from "./StatusMessage";

interface ChartsPanelProps {
  datasetId: string;
  catalog: VisualizationCatalogResponse;
}

function columnsFor(
  catalog: VisualizationCatalogResponse,
  chart: VisualizationCatalogResponse["available_charts"][number],
): string[] {
  return catalog.columns
    .filter((column) => column.charts.includes(chart))
    .map((column) => column.name);
}

export function ChartsPanel({ datasetId, catalog }: ChartsPanelProps) {
  const histogramCols = useMemo(() => columnsFor(catalog, "histogram"), [catalog]);
  const barCols = useMemo(() => columnsFor(catalog, "bar"), [catalog]);
  const scatterCols = useMemo(() => columnsFor(catalog, "scatter"), [catalog]);

  const [histColumn, setHistColumn] = useState(histogramCols[0] ?? "");
  const [bins, setBins] = useState(20);
  const [barColumn, setBarColumn] = useState(barCols[0] ?? "");
  const [limit, setLimit] = useState(15);
  const [scatterX, setScatterX] = useState(scatterCols[0] ?? "");
  const [scatterY, setScatterY] = useState(scatterCols[1] ?? scatterCols[0] ?? "");

  const [histogram, setHistogram] = useState<HistogramResponse | null>(null);
  const [bar, setBar] = useState<BarResponse | null>(null);
  const [scatter, setScatter] = useState<ScatterResponse | null>(null);
  const [heatmap, setHeatmap] = useState<HeatmapResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoading(true);
      setError(null);
      try {
        const tasks: Promise<void>[] = [];
        if (histColumn) {
          tasks.push(
            fetchHistogram(datasetId, histColumn, bins).then((payload) => {
              if (!cancelled) setHistogram(payload);
            }),
          );
        } else {
          setHistogram(null);
        }
        if (barColumn) {
          tasks.push(
            fetchBar(datasetId, barColumn, limit).then((payload) => {
              if (!cancelled) setBar(payload);
            }),
          );
        } else {
          setBar(null);
        }
        if (scatterX && scatterY) {
          tasks.push(
            fetchScatter(datasetId, scatterX, scatterY, 500).then((payload) => {
              if (!cancelled) setScatter(payload);
            }),
          );
        } else {
          setScatter(null);
        }
        if (catalog.available_charts.includes("heatmap")) {
          tasks.push(
            fetchHeatmap(datasetId).then((payload) => {
              if (!cancelled) setHeatmap(payload);
            }),
          );
        } else {
          setHeatmap(null);
        }
        await Promise.all(tasks);
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof ApiError ? cause.message : "Could not load charts.");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [datasetId, histColumn, bins, barColumn, limit, scatterX, scatterY, catalog]);

  return (
    <section className="panel visualizations-panel" aria-labelledby="charts-heading">
      <div className="panel-header">
        <div>
          <h2 id="charts-heading">Visualizations</h2>
          <p>Charts use server-built bins, counts, samples, and the correlation matrix.</p>
        </div>
      </div>
      {loading ? (
        <p className="loading-inline" aria-live="polite">
          <span className="spinner" aria-hidden="true" />
          Loading charts from the analysis API…
        </p>
      ) : null}
      {error ? (
        <StatusMessage
          tone="error"
          title="Chart error"
          detail={`${error} Check the selected columns, then try again.`}
        />
      ) : null}

      {catalog.available_charts.length === 0 ? (
        <p className="empty-copy">
          This dataset has no chart types available. Upload a CSV with numeric or categorical
          columns to plot.
        </p>
      ) : (
        <div className="chart-grid" aria-busy={loading}>
          <article className="chart-card">
            <div className="controls">
              <label htmlFor="hist-column">
                Histogram column
                <select
                  id="hist-column"
                  value={histColumn}
                  disabled={histogramCols.length === 0}
                  onChange={(event) => setHistColumn(event.target.value)}
                >
                  {histogramCols.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
              </label>
              <label htmlFor="hist-bins">
                Bins
                <input
                  id="hist-bins"
                  type="number"
                  min={5}
                  max={50}
                  value={bins}
                  aria-label="Histogram bin count"
                  onChange={(event) => setBins(Number(event.target.value))}
                />
              </label>
            </div>
            {histColumn && histogram ? (
              <HistogramChart chart={histogram} />
            ) : (
              <p className="empty-copy">No numeric column is available for a histogram.</p>
            )}
          </article>

          <article className="chart-card">
            <div className="controls">
              <label htmlFor="bar-column">
                Bar column
                <select
                  id="bar-column"
                  value={barColumn}
                  disabled={barCols.length === 0}
                  onChange={(event) => setBarColumn(event.target.value)}
                >
                  {barCols.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
              </label>
              <label htmlFor="bar-limit">
                Limit
                <input
                  id="bar-limit"
                  type="number"
                  min={1}
                  max={50}
                  value={limit}
                  aria-label="Bar chart category limit"
                  onChange={(event) => setLimit(Number(event.target.value))}
                />
              </label>
            </div>
            {barColumn && bar ? (
              <BarChartView chart={bar} />
            ) : (
              <p className="empty-copy">No categorical column is available for a bar chart.</p>
            )}
          </article>

          <article className="chart-card">
            <div className="controls">
              <label htmlFor="scatter-x">
                Scatter X
                <select
                  id="scatter-x"
                  value={scatterX}
                  disabled={scatterCols.length === 0}
                  onChange={(event) => setScatterX(event.target.value)}
                >
                  {scatterCols.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
              </label>
              <label htmlFor="scatter-y">
                Scatter Y
                <select
                  id="scatter-y"
                  value={scatterY}
                  disabled={scatterCols.length === 0}
                  onChange={(event) => setScatterY(event.target.value)}
                >
                  {scatterCols.map((column) => (
                    <option key={column} value={column}>
                      {column}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {scatterX && scatterY && scatter ? (
              <ScatterChartView chart={scatter} />
            ) : (
              <p className="empty-copy">Need two numeric columns for a scatter plot.</p>
            )}
          </article>

          <article className="chart-card">
            {heatmap ? (
              <HeatmapGrid chart={heatmap} />
            ) : (
              <p className="empty-copy">Need two numeric columns for a correlation heatmap.</p>
            )}
          </article>
        </div>
      )}
    </section>
  );
}
