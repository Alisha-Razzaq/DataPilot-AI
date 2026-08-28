import type {
  BarResponse,
  ChatResponse,
  DatasetProfileResponse,
  DatasetStatisticsResponse,
  DatasetUploadResponse,
  HeatmapResponse,
  HistogramResponse,
  ScatterResponse,
  VisualizationCatalogResponse,
} from "../types/api";
import { ApiError } from "../types/api";

async function readError(response: Response): Promise<ApiError> {
  let detail = `Request failed (${response.status})`;
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      detail = payload.detail;
    }
  } catch {
    /* keep default message */
  }
  return new ApiError(response.status, detail);
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as T;
}

async function postJson<T>(url: string, body: unknown): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as T;
}

export async function uploadDataset(file: File): Promise<DatasetUploadResponse> {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/datasets/upload", {
    method: "POST",
    body,
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return (await response.json()) as DatasetUploadResponse;
}

export function fetchProfile(datasetId: string): Promise<DatasetProfileResponse> {
  return getJson(`/api/datasets/${datasetId}/profile`);
}

export function fetchStatistics(
  datasetId: string,
): Promise<DatasetStatisticsResponse> {
  return getJson(`/api/datasets/${datasetId}/statistics`);
}

export function fetchCatalog(
  datasetId: string,
): Promise<VisualizationCatalogResponse> {
  return getJson(`/api/datasets/${datasetId}/visualizations`);
}

export function fetchHistogram(
  datasetId: string,
  column: string,
  bins: number,
): Promise<HistogramResponse> {
  const params = new URLSearchParams({
    column,
    bins: String(bins),
  });
  return getJson(`/api/datasets/${datasetId}/visualizations/histogram?${params}`);
}

export function fetchBar(
  datasetId: string,
  column: string,
  limit: number,
): Promise<BarResponse> {
  const params = new URLSearchParams({
    column,
    limit: String(limit),
  });
  return getJson(`/api/datasets/${datasetId}/visualizations/bar?${params}`);
}

export function fetchScatter(
  datasetId: string,
  x: string,
  y: string,
  maxPoints: number,
): Promise<ScatterResponse> {
  const params = new URLSearchParams({
    x,
    y,
    max_points: String(maxPoints),
  });
  return getJson(`/api/datasets/${datasetId}/visualizations/scatter?${params}`);
}

export function fetchHeatmap(datasetId: string): Promise<HeatmapResponse> {
  return getJson(`/api/datasets/${datasetId}/visualizations/heatmap`);
}

export function sendChat(datasetId: string, message: string): Promise<ChatResponse> {
  return postJson("/api/chat", {
    dataset_id: datasetId,
    message,
  });
}
