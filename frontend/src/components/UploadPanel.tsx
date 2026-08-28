import { useRef, useState } from "react";

interface UploadPanelProps {
  uploading: boolean;
  hasDataset: boolean;
  filename: string | null;
  onUpload: (file: File) => Promise<void>;
}

function isCsv(file: File): boolean {
  return file.name.toLowerCase().endsWith(".csv");
}

export function UploadPanel({
  uploading,
  hasDataset,
  filename,
  onUpload,
}: UploadPanelProps) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  async function acceptFile(file: File | undefined) {
    if (!file) {
      return;
    }
    if (!isCsv(file)) {
      setLocalError("Please choose a .csv file.");
      return;
    }
    if (file.size === 0) {
      setLocalError("That file is empty.");
      return;
    }
    setLocalError(null);
    await onUpload(file);
  }

  return (
    <section className="panel" aria-labelledby="upload-heading">
      <div className="panel-header">
        <div>
          <h2 id="upload-heading">{hasDataset ? "Replace dataset" : "Upload a dataset"}</h2>
          <p>
            {hasDataset
              ? `Current file: ${filename}. Choose another CSV to run a new analysis.`
              : "Start with a CSV. The server profiles it, computes statistics, and returns chart data."}
          </p>
        </div>
      </div>
      <div
        className={`dropzone ${dragOver ? "dropzone-active" : ""} ${uploading ? "dropzone-busy" : ""}`}
        role="group"
        aria-label="CSV upload dropzone"
        onDragOver={(event) => {
          event.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragOver(false);
          void acceptFile(event.dataTransfer.files[0]);
        }}
      >
        <p className="dropzone-title">Drop a CSV here</p>
        <p className="muted">
          {uploading
            ? "Upload in progress…"
            : "Only .csv files are accepted. Analysis runs on the server after upload."}
        </p>
        <button
          type="button"
          className="button"
          disabled={uploading}
          onClick={() => inputRef.current?.click()}
        >
          {uploading ? "Uploading…" : hasDataset ? "Choose another CSV" : "Choose CSV"}
        </button>
        <input
          ref={inputRef}
          type="file"
          accept=".csv,text/csv"
          hidden
          aria-label="Choose a CSV file to upload"
          onChange={(event) => {
            void acceptFile(event.target.files?.[0]);
            event.target.value = "";
          }}
        />
      </div>
      {localError ? (
        <p className="field-error" role="alert">
          {localError}
        </p>
      ) : null}
      {!hasDataset && !uploading && !localError ? (
        <p className="hint">
          After upload you will see row and column counts, numeric statistics, charts, and the AI
          Data Analyst.
        </p>
      ) : null}
    </section>
  );
}
