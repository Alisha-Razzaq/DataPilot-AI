"""HTTP tests for GET /api/datasets/{dataset_id}/statistics."""

from fastapi.testclient import TestClient

STATS_CSV = (
    "region,sales,profit\n"
    "east,10,1\n"
    "west,20,2\n"
    "east,30,3\n"
    "west,40,4\n"
).encode("utf-8")

CATEGORICAL_ONLY_CSV = (
    "region,status\n"
    "east,ok\n"
    "west,ok\n"
).encode("utf-8")


def _upload(client: TestClient, content: bytes, filename: str = "stats.csv"):
    return client.post(
        "/api/datasets/upload",
        files={"file": (filename, content, "text/csv")},
    )


def test_statistics_after_upload(client: TestClient) -> None:
    upload = _upload(client, STATS_CSV)
    assert upload.status_code == 201
    dataset_id = upload.json()["dataset_id"]

    response = client.get(f"/api/datasets/{dataset_id}/statistics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["dataset_id"] == dataset_id
    assert payload["numeric_columns"] == ["sales", "profit"]
    assert len(payload["correlations"]) == 1
    assert payload["correlations"][0]["coefficient"] == 1.0
    assert "stored_path" not in payload

    sales = next(
        item for item in payload["column_statistics"] if item["name"] == "sales"
    )
    assert sales["quartiles"]["q2"] == 25.0
    assert sales["outliers"]["method"] == "iqr"


def test_statistics_unknown_dataset_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/datasets/00000000-0000-0000-0000-000000000000/statistics"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found."


def test_statistics_without_enough_numeric_columns(client: TestClient) -> None:
    upload = _upload(client, CATEGORICAL_ONLY_CSV, "cats.csv")
    dataset_id = upload.json()["dataset_id"]
    response = client.get(f"/api/datasets/{dataset_id}/statistics")
    assert response.status_code == 200
    payload = response.json()
    assert payload["numeric_columns"] == []
    assert payload["column_statistics"] == []
    assert payload["correlations"] == []
