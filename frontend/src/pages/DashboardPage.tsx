import { ChartsPanel } from "../components/ChartsPanel";
import { ChatPanel } from "../components/ChatPanel";
import { DatasetSummary } from "../components/DatasetSummary";
import { ProfileTable } from "../components/ProfileTable";
import { SiteHeader } from "../components/SiteHeader";
import { StatisticsPanel } from "../components/StatisticsPanel";
import { StatusMessage } from "../components/StatusMessage";
import { UploadPanel } from "../components/UploadPanel";
import { useDataset } from "../hooks/useDataset";

export function DashboardPage() {
  const dataset = useDataset();
  const numericColumns = dataset.statistics?.numeric_columns ?? [];
  const categoricalColumns =
    dataset.profile?.column_profiles
      .filter(
        (column) =>
          column.inferred_type === "categorical" ||
          column.inferred_type === "text" ||
          column.inferred_type === "boolean",
      )
      .map((column) => column.name) ?? [];

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <SiteHeader filename={dataset.upload?.original_filename ?? null} />

      <main id="main-content" className="page">
        <UploadPanel
          uploading={dataset.uploading}
          hasDataset={Boolean(dataset.upload)}
          filename={dataset.upload?.original_filename ?? null}
          onUpload={dataset.loadDataset}
        />

        {dataset.uploading ? (
          <StatusMessage
            tone="info"
            title="Uploading CSV"
            detail="Sending the file to the analysis API. This usually takes a few seconds."
          />
        ) : null}
        {dataset.loadingAnalysis ? (
          <StatusMessage
            tone="info"
            title="Building analysis"
            detail="Loading the profile, numeric statistics, and visualization catalog from the server."
          />
        ) : null}
        {dataset.error ? (
          <StatusMessage
            tone="error"
            title={dataset.status === 404 ? "Dataset not found" : "Upload or analysis failed"}
            detail={`${dataset.error} Try uploading the CSV again. If the API was restarted, the in-memory registry was cleared.`}
          />
        ) : null}

        {dataset.upload && dataset.profile ? (
          <DatasetSummary
            upload={dataset.upload}
            profile={dataset.profile}
            availableCharts={dataset.catalog?.available_charts ?? []}
          />
        ) : null}

        {dataset.statistics ? <StatisticsPanel statistics={dataset.statistics} /> : null}

        {dataset.upload && dataset.catalog ? (
          <ChartsPanel datasetId={dataset.upload.dataset_id} catalog={dataset.catalog} />
        ) : null}

        {dataset.profile ? <ProfileTable columns={dataset.profile.column_profiles} /> : null}

        {dataset.upload ? (
          <ChatPanel
            datasetId={dataset.upload.dataset_id}
            numericColumns={numericColumns}
            categoricalColumns={categoricalColumns}
          />
        ) : null}
      </main>
    </div>
  );
}
