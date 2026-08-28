"""HTTP tests for GET /api/datasets/{dataset_id}/profile."""

import pytest
from fastapi.testclient import TestClient

PROFILE_CSV = (
    "region,sales,status\n"
    "east,100,ok\n"
    "west,200,ok\n"
    "east,100,ok\n"
).encode("utf-8")


def _upload(client: TestClient, content: bytes = PROFILE_CSV):
    return client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", content, "text/csv")},
    )


def test_profile_after_upload_returns_structured_json(client: TestClient) -> None:
    upload = _upload(client)
    assert upload.status_code == 201
    dataset_id = upload.json()["dataset_id"]

    response = client.get(f"/api/datasets/{dataset_id}/profile")
    assert response.status_code == 200
    payload = response.json()

    assert payload["dataset_id"] == dataset_id
    assert payload["rows"] == 3
    assert payload["columns"] == 3
    assert payload["column_names"] == ["region", "sales", "status"]
    assert payload["duplicate_row_count"] == 1
    assert "stored_path" not in payload

    by_name = {column["name"]: column for column in payload["column_profiles"]}
    assert by_name["sales"]["inferred_type"] == "numeric"
    assert by_name["sales"]["numeric_summary"]["mean"] == pytest.approx(400 / 3)
    assert by_name["region"]["inferred_type"] == "categorical"
    assert by_name["region"]["unique_count"] == 2
    assert by_name["region"]["categorical_summary"]["most_frequent_value"] == "east"


def test_profile_unknown_dataset_returns_404(client: TestClient) -> None:
    response = client.get("/api/datasets/00000000-0000-0000-0000-000000000000/profile")
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found."
    assert "uploads" not in response.json()["detail"]


def test_profile_path_parameter_is_not_treated_as_filepath(client: TestClient) -> None:
    response = client.get("/api/datasets/../../secret/profile")
    assert response.status_code == 404
    assert "stored_path" not in response.text
