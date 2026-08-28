import { useCallback, useState } from "react";

import {
  fetchCatalog,
  fetchProfile,
  fetchStatistics,
  uploadDataset,
} from "../services/api";
import { ApiError } from "../types/api";
import type {
  DatasetProfileResponse,
  DatasetStatisticsResponse,
  DatasetUploadResponse,
  VisualizationCatalogResponse,
} from "../types/api";

export interface DatasetState {
  upload: DatasetUploadResponse | null;
  profile: DatasetProfileResponse | null;
  statistics: DatasetStatisticsResponse | null;
  catalog: VisualizationCatalogResponse | null;
  uploading: boolean;
  loadingAnalysis: boolean;
  error: string | null;
  status: number | null;
}

const empty: DatasetState = {
  upload: null,
  profile: null,
  statistics: null,
  catalog: null,
  uploading: false,
  loadingAnalysis: false,
  error: null,
  status: null,
};

export function useDataset() {
  const [state, setState] = useState<DatasetState>(empty);

  const resetError = useCallback(() => {
    setState((current) => ({ ...current, error: null, status: null }));
  }, []);

  const loadDataset = useCallback(async (file: File) => {
    setState({
      ...empty,
      uploading: true,
    });
    try {
      const upload = await uploadDataset(file);
      setState({
        ...empty,
        upload,
        uploading: false,
        loadingAnalysis: true,
      });
      const [profile, statistics, catalog] = await Promise.all([
        fetchProfile(upload.dataset_id),
        fetchStatistics(upload.dataset_id),
        fetchCatalog(upload.dataset_id),
      ]);
      setState({
        upload,
        profile,
        statistics,
        catalog,
        uploading: false,
        loadingAnalysis: false,
        error: null,
        status: 200,
      });
    } catch (error) {
      const apiError = error instanceof ApiError ? error : null;
      setState({
        ...empty,
        uploading: false,
        loadingAnalysis: false,
        error: apiError?.message ?? "Upload or analysis failed.",
        status: apiError?.status ?? null,
      });
    }
  }, []);

  return { ...state, loadDataset, resetError };
}
