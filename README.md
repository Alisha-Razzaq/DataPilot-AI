# DataPilot AI

A production-style AI-powered data analysis platform.

**Core rule:** the language model must never invent numerical answers. When a question needs a calculation, the backend runs a real analysis function against the uploaded dataset and uses that result in the reply.

This repository is being built in phases. **Phase 8** adds a backend-only hosted LLM that may request the existing analysis tools. The dashboard has no chat UI yet.

## Architecture

The system is split so each concern can change without rewriting everything else:

| Layer | Location | Responsibility |
| --- | --- | --- |
| Frontend | `frontend/` | React + TypeScript + Vite dashboard. Displays API results only. |
| Backend API | `backend/app/api/` | HTTP endpoints. Receives requests, returns JSON. |
| Services | `backend/app/services/` | Upload, validation, registry lookup, and use-case wiring. |
| Data analysis | `backend/app/analysis/` | pandas profiling, statistics, and chart-data JSON. The only source of numbers. |
| AI / orchestration | `backend/app/ai/` | Explicit tools plus a bounded Gemini generate_content loop. |
| Storage | `data/uploads/` | CSV files named `<dataset_id>.csv`. Metadata is in-memory only. |

`backend/app/main.py` wires these pieces together.

```
Browser (Vite :5173, /api proxied)  →  FastAPI (:8000)
                                         →  services/          (existing dashboard routes)
                                         →  POST /api/chat → llm_service → Gemini generate_content
                                            →  whitelist dispatch → ai/tools.py
                                               →  services/ → analysis/ (the only source of numbers)
```

Existing dashboard endpoints still call services directly. `GET /api/tools` still only describes tools. Chat executes them only through a frozen nine-function whitelist.

## Current status (Phase 8)

Included:

- Project folder structure
- FastAPI app with `GET /health`
- Environment variable loading via `.env`
- `POST /api/datasets/upload` for CSV files
- Unique `dataset_id` (UUID); stored filename is never the user's filename
- In-memory dataset registry
- `GET /api/datasets/{dataset_id}/profile` — structured pandas profile
- `GET /api/datasets/{dataset_id}/statistics` — Pearson correlations, quartiles, IQR outliers
- Chart-data JSON (no image files, no Plotly on the backend):
  - `GET /api/datasets/{dataset_id}/visualizations`
  - `GET /api/datasets/{dataset_id}/visualizations/histogram`
  - `GET /api/datasets/{dataset_id}/visualizations/bar`
  - `GET /api/datasets/{dataset_id}/visualizations/scatter`
  - `GET /api/datasets/{dataset_id}/visualizations/heatmap`
- pytest coverage for health, upload, profiling, statistics, and visualizations
- Local dashboard in `frontend/` (React, TypeScript, Vite, Recharts)
- Vite proxies `/api` to the FastAPI process
- CORS allowlist for `http://127.0.0.1:5173`
- Controlled analysis tools in `backend/app/ai/`
- `GET /api/tools` — provider-independent tool definitions (does not execute tools)
- `POST /api/chat` — hosted Gemini API; the model may request one of the nine tools; Python executes them; tests mock Gemini

The profiler reports:

- row/column counts, column names
- duplicate row count and percentage
- per-column dtype, inferred type, unique counts, missing counts/percentages
- numeric summary (count, mean, median, std, min, max)
- categorical / text / boolean summary (mode and top 10 values)

The statistics endpoint reports:

- numeric column list
- quartiles (Q1, median/Q2, Q3) and IQR
- IQR-based outlier count, fences, and up to 10 example values
- pairwise Pearson correlations when at least two numeric columns exist

The visualization endpoints return **aggregated JSON** (bins, category counts, sampled points, correlation matrix). The dashboard renders that JSON. It does not recompute statistics in the browser.

Tools (`get_dataset_summary`, `get_column_profile`, `get_numeric_statistics`, `get_correlations`, `get_outliers`, `get_histogram`, `get_category_counts`, `get_scatter_data`, `get_correlation_heatmap`) call those same services. They never calculate mean, Pearson r, IQR, or bins themselves.

```powershell
curl.exe http://127.0.0.1:8000/api/tools
```

### Ask a question (backend only)

There is no chat UI yet. The API key stays in `.env` on the server and is never sent to React.

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/chat -H "Content-Type: application/json" -d "{\"dataset_id\":\"...\",\"message\":\"What is the average sales?\"}"
```

Request shape:

```json
{
  "dataset_id": "...",
  "message": "What is the average sales?"
}
```

The model may request `get_numeric_statistics`. pandas computes the mean. The reply explains that tool JSON. There is no generated Python, no `eval`/`exec`, no RAG, and no embeddings.

Not included yet (intentionally):

- Chat frontend
- RAG or embeddings
- Database (SQLite will come later)
- Authentication
- Deployment

### In-memory registry limitation

Dataset metadata is kept **in process memory**. Restarting the server clears the registry even if CSV files remain under `data/uploads/`. Profile, statistics, and visualization requests require a `dataset_id` that is still in that registry. SQLite persistence is a later phase.

## Local setup

Requires **Python 3.11+**. On this Windows machine, prefer `py -3.12` so the venv is not created with MSYS2 Python.

From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

On macOS/Linux, activate with `source .venv/bin/activate` and copy with `cp .env.example .env`.

## Run the backend

From the repository root, with the virtual environment activated:

```powershell
uvicorn app.main:app --reload --app-dir backend
```

Then open:

- API: http://127.0.0.1:8000
- Health: http://127.0.0.1:8000/health
- Interactive docs: http://127.0.0.1:8000/docs

## Run the dashboard

In a second terminal, from `frontend/`:

```powershell
npm run dev
```

Then open http://127.0.0.1:5173

The Vite dev server proxies `/api` to `http://127.0.0.1:8000`. Keep the FastAPI process running while you use the dashboard. The in-memory registry is lost if you restart the API.

## API usage

### Health

```powershell
curl.exe http://127.0.0.1:8000/health
```

Expected: `{"status":"ok"}`

### Upload a CSV

```powershell
curl.exe -X POST http://127.0.0.1:8000/api/datasets/upload -F "file=@sales.csv"
```

Successful response (`201 Created`):

```json
{
  "dataset_id": "some-unique-id",
  "original_filename": "sales.csv",
  "rows": 1000,
  "columns": 8,
  "column_names": ["date", "region", "sales", "profit"]
}
```

The dataset rows are **not** returned. The file is stored as `data/uploads/<dataset_id>.csv`.

### Profile a dataset

Use the `dataset_id` from the upload response:

```powershell
curl.exe http://127.0.0.1:8000/api/datasets/some-unique-id/profile
```

Successful response (`200`) looks like:

```json
{
  "dataset_id": "some-unique-id",
  "rows": 4,
  "columns": 3,
  "column_names": ["region", "sales", "status"],
  "duplicate_row_count": 1,
  "duplicate_row_percentage": 25.0,
  "column_profiles": [
    {
      "name": "region",
      "pandas_dtype": "object",
      "inferred_type": "categorical",
      "non_null_count": 4,
      "missing_count": 0,
      "missing_percentage": 0.0,
      "unique_count": 2,
      "numeric_summary": null,
      "categorical_summary": {
        "unique_count": 2,
        "most_frequent_value": "east",
        "most_frequent_count": 3,
        "top_values": [
          {"value": "east", "count": 3},
          {"value": "west", "count": 1}
        ]
      }
    }
  ]
}
```

Unknown `dataset_id` values return `404`. Internal filesystem paths are never included.

### Numeric statistics

```powershell
curl.exe http://127.0.0.1:8000/api/datasets/some-unique-id/statistics
```

Successful response (`200`) looks like:

```json
{
  "dataset_id": "some-unique-id",
  "numeric_columns": ["sales", "profit"],
  "column_statistics": [
    {
      "name": "sales",
      "count": 4,
      "quartiles": {"q1": 17.5, "q2": 25.0, "q3": 32.5, "iqr": 15.0},
      "outliers": {
        "method": "iqr",
        "lower_fence": -5.0,
        "upper_fence": 55.0,
        "outlier_count": 0,
        "outlier_percentage": 0.0,
        "sample_values": []
      }
    }
  ],
  "correlations": [
    {"column_a": "sales", "column_b": "profit", "coefficient": 1.0}
  ]
}
```

A dataset with fewer than two numeric columns still returns `200`, with an empty `correlations` list. Unknown `dataset_id` values return `404`.

### Visualizations

Chart payloads are JSON data, not images.

```powershell
curl.exe http://127.0.0.1:8000/api/datasets/some-unique-id/visualizations
curl.exe "http://127.0.0.1:8000/api/datasets/some-unique-id/visualizations/histogram?column=sales&bins=20"
curl.exe "http://127.0.0.1:8000/api/datasets/some-unique-id/visualizations/bar?column=region&limit=15"
curl.exe "http://127.0.0.1:8000/api/datasets/some-unique-id/visualizations/scatter?x=sales&y=profit&max_points=500"
curl.exe http://127.0.0.1:8000/api/datasets/some-unique-id/visualizations/heatmap
```

Limits applied on the server: histogram bins 5–50, bar categories 1–50, scatter points 10–2000 (deterministic sample, `random_state=0`).

On Windows PowerShell, use `curl.exe` rather than `curl` (which is an alias for `Invoke-WebRequest`).

Rejected uploads (examples):

| Situation | HTTP status |
| --- | --- |
| Not a `.csv` file | 415 |
| Empty file | 400 |
| Unreadable / invalid CSV | 400 |
| Larger than `MAX_UPLOAD_BYTES` (default 10 MiB) | 413 |
| Unknown `dataset_id` on `/profile`, `/statistics`, or `/visualizations` | 404 |
| Unknown or wrong-type column on a chart endpoint | 400 |

## Run tests

From the repository root, with the virtual environment activated:

```powershell
pytest
```

## Environment variables

See `.env.example`. Copy it to `.env` for local overrides. `.env` is gitignored.

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_NAME` | API title | `DataPilot AI` |
| `APP_ENV` | Environment name | `development` |
| `MAX_UPLOAD_BYTES` | Maximum CSV upload size in bytes | `10485760` (10 MiB) |
| `GEMINI_API_KEY` | Hosted Gemini key (server only) | empty (chat returns 503) |
| `GEMINI_MODEL` | Gemini model id | `gemini-3.1-flash-lite` |

Never put `GEMINI_API_KEY` in React or in API responses. Tests mock Gemini and do not call the network.
