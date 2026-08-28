"""HTTP tests for visualization endpoints."""

from fastapi.testclient import TestClient

CHART_CSV = (
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


def _upload(client: TestClient, content: bytes = CHART_CSV, name: str = "charts.csv"):
    return client.post(
        "/api/datasets/upload",
        files={"file": (name, content, "text/csv")},
    )


def test_catalog_and_all_chart_endpoints(client: TestClient) -> None:
    dataset_id = _upload(client).json()["dataset_id"]

    catalog = client.get(f"/api/datasets/{dataset_id}/visualizations")
    assert catalog.status_code == 200
    body = catalog.json()
    assert body["dataset_id"] == dataset_id
    assert "histogram" in body["available_charts"]
    assert "stored_path" not in body

    histogram = client.get(
        f"/api/datasets/{dataset_id}/visualizations/histogram",
        params={"column": "sales", "bins": 5},
    )
    assert histogram.status_code == 200
    assert histogram.json()["chart_type"] == "histogram"
    assert sum(item["count"] for item in histogram.json()["data"]["bins"]) == 4

    bar = client.get(
        f"/api/datasets/{dataset_id}/visualizations/bar",
        params={"column": "region", "limit": 15},
    )
    assert bar.status_code == 200
    assert bar.json()["chart_type"] == "bar"

    scatter = client.get(
        f"/api/datasets/{dataset_id}/visualizations/scatter",
        params={"x": "sales", "y": "profit", "max_points": 500},
    )
    assert scatter.status_code == 200
    assert scatter.json()["point_count"] == 4
    assert scatter.json()["sampled"] is False

    heatmap = client.get(f"/api/datasets/{dataset_id}/visualizations/heatmap")
    assert heatmap.status_code == 200
    assert heatmap.json()["data"]["columns"] == ["sales", "profit"]


def test_visualizations_unknown_dataset_returns_404(client: TestClient) -> None:
    response = client.get(
        "/api/datasets/00000000-0000-0000-0000-000000000000/visualizations"
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found."


def test_visualizations_unknown_column_returns_400(client: TestClient) -> None:
    dataset_id = _upload(client).json()["dataset_id"]
    response = client.get(
        f"/api/datasets/{dataset_id}/visualizations/histogram",
        params={"column": "not_a_column"},
    )
    assert response.status_code == 400
    assert "Unknown column" in response.json()["detail"]
    assert "uploads" not in response.json()["detail"]


def test_visualizations_wrong_column_type_returns_400(client: TestClient) -> None:
    dataset_id = _upload(client).json()["dataset_id"]
    histogram = client.get(
        f"/api/datasets/{dataset_id}/visualizations/histogram",
        params={"column": "region"},
    )
    scatter = client.get(
        f"/api/datasets/{dataset_id}/visualizations/scatter",
        params={"x": "region", "y": "sales"},
    )
    bar = client.get(
        f"/api/datasets/{dataset_id}/visualizations/bar",
        params={"column": "sales"},
    )
    assert histogram.status_code == 400
    assert scatter.status_code == 400
    assert bar.status_code == 400


def test_heatmap_with_insufficient_numeric_columns(client: TestClient) -> None:
    dataset_id = _upload(client, CATEGORICAL_ONLY_CSV, "cats.csv").json()["dataset_id"]
    response = client.get(f"/api/datasets/{dataset_id}/visualizations/heatmap")
    assert response.status_code == 200
    assert response.json()["data"]["columns"] == []
    assert response.json()["data"]["matrix"] == []


def test_scatter_cap_via_api(client: TestClient) -> None:
    rows = ["x,y"] + [f"{index},{index * 2}" for index in range(30)]
    content = ("\n".join(rows) + "\n").encode("utf-8")
    dataset_id = _upload(client, content, "points.csv").json()["dataset_id"]
    response = client.get(
        f"/api/datasets/{dataset_id}/visualizations/scatter",
        params={"x": "x", "y": "y", "max_points": 10},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["sampled"] is True
    assert payload["point_count"] == 10
    assert len(payload["data"]["points"]) == 10
