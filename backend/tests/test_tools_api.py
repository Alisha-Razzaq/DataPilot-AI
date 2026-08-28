"""HTTP tests for GET /api/tools (catalog only, no execution)."""

from fastapi.testclient import TestClient


def test_list_tools_returns_catalog(client: TestClient) -> None:
    response = client.get("/api/tools")
    assert response.status_code == 200
    payload = response.json()
    names = [item["name"] for item in payload["tools"]]
    assert names == [
        "get_dataset_summary",
        "get_column_profile",
        "get_numeric_statistics",
        "get_correlations",
        "get_outliers",
        "get_histogram",
        "get_category_counts",
        "get_scatter_data",
        "get_correlation_heatmap",
    ]
    encoded = str(payload)
    assert "eval" not in encoded
    assert "exec" not in encoded
    assert "subprocess" not in encoded
    assert "stored_path" not in encoded
    for item in payload["tools"]:
        assert item["parameters"]["additionalProperties"] is False
        assert "execute" not in item
        assert "code" not in item["parameters"]["properties"]


def test_tools_endpoint_does_not_execute(client: TestClient) -> None:
    posted = client.post("/api/tools", json={"name": "get_dataset_summary"})
    assert posted.status_code in {404, 405, 422}
    listed = client.get("/api/tools")
    assert listed.status_code == 200
    body = listed.json()
    assert "tools" in body
    assert all("execute" not in item for item in body["tools"])
