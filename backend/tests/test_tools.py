"""Phase 7: controlled analysis tools (no LLM, no generic execution)."""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import app.ai.tools as tools_module
from app.ai.registry import TOOL_NAMES, list_tool_definitions
from app.ai.tools import (
    get_category_counts,
    get_column_profile,
    get_correlation_heatmap,
    get_correlations,
    get_dataset_summary,
    get_histogram,
    get_numeric_statistics,
    get_outliers,
    get_scatter_data,
)
from app.services.dataset_service import DatasetError
from fastapi.testclient import TestClient

EXPECTED_TOOLS = (
    "get_dataset_summary",
    "get_column_profile",
    "get_numeric_statistics",
    "get_correlations",
    "get_outliers",
    "get_histogram",
    "get_category_counts",
    "get_scatter_data",
    "get_correlation_heatmap",
)

MIXED_CSV = (
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

HIGH_CARDINALITY_CSV = (
    "label,sales\n" + "".join(f"cat{index},{index}\n" for index in range(20))
).encode("utf-8")

_PATH_KEY = re.compile(r"(^|_)(path|filepath|filename|dir|directory)s?$", re.I)
_DRIVE_OR_ABS = re.compile(r"(^[A-Za-z]:[\\/]|[/\\]uploads[/\\]|\\\\)")


def _upload(client: TestClient, content: bytes = MIXED_CSV, name: str = "tools.csv") -> str:
    response = client.post(
        "/api/datasets/upload",
        files={"file": (name, content, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["dataset_id"]


def _assert_no_filesystem_paths(payload: object) -> None:
    encoded = json.dumps(payload)
    assert "stored_path" not in encoded
    parsed = json.loads(encoded)

    def walk(node: object, key: str | None = None) -> None:
        if isinstance(node, dict):
            for child_key, value in node.items():
                assert child_key != "stored_path"
                assert not _PATH_KEY.search(child_key), child_key
                walk(value, child_key)
            return
        if isinstance(node, list):
            for item in node:
                walk(item, key)
            return
        if isinstance(node, str):
            assert not _DRIVE_OR_ABS.search(node), node
            assert "data/uploads" not in node.replace("\\", "/")

    walk(parsed)


def test_registry_contains_all_expected_tools() -> None:
    names = [item.name for item in list_tool_definitions()]
    assert names == list(EXPECTED_TOOLS)
    assert TOOL_NAMES == frozenset(EXPECTED_TOOLS)


def test_registry_metadata_is_complete() -> None:
    for definition in list_tool_definitions():
        assert definition.name
        assert len(definition.description) > 20
        assert definition.parameters.type == "object"
        assert definition.parameters.additionalProperties is False
        assert "dataset_id" in definition.parameters.properties
        assert "dataset_id" in definition.parameters.required
        for name, schema in definition.parameters.properties.items():
            assert schema.type in {"string", "integer"}
            assert schema.description
            assert name.isidentifier()
            assert name not in {"code", "sql", "command", "path", "eval", "exec"}


def test_registry_matches_explicit_python_functions() -> None:
    public_names = {
        name
        for name, value in inspect.getmembers(tools_module, inspect.isfunction)
        if not name.startswith("_")
    }
    assert set(EXPECTED_TOOLS) <= public_names
    source = Path(tools_module.__file__).read_text(encoding="utf-8")
    for banned in ("eval(", "exec(", "subprocess", "os.system"):
        assert banned not in source


def test_dataset_summary_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_dataset_summary(dataset_id)
    payload = result.model_dump(mode="json")
    _assert_no_filesystem_paths(payload)
    assert payload["dataset_id"] == dataset_id
    assert payload["rows"] == 4
    assert payload["columns"] == 3
    assert payload["column_names"] == ["region", "sales", "profit"]
    assert payload["duplicate_row_count"] == 0
    assert payload["duplicate_row_percentage"] == 0.0


def test_column_profile_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    numeric = get_column_profile(dataset_id, "sales")
    categorical = get_column_profile(dataset_id, "region")
    assert numeric.column.inferred_type == "numeric"
    assert numeric.column.unique_count == 4
    assert numeric.column.numeric_summary is not None
    assert numeric.column.numeric_summary.mean == 25.0
    assert categorical.column.inferred_type == "categorical"
    assert categorical.column.categorical_summary is not None
    _assert_no_filesystem_paths(numeric.model_dump(mode="json"))


def test_numeric_statistics_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_numeric_statistics(dataset_id, "sales")
    payload = result.model_dump(mode="json")
    _assert_no_filesystem_paths(payload)
    assert payload["column"] == "sales"
    assert payload["count"] == 4
    assert payload["mean"] == 25.0
    assert payload["median"] == 25.0
    assert payload["min"] == 10.0
    assert payload["max"] == 40.0
    assert payload["quartiles"]["q2"] == 25.0
    assert payload["quartiles"]["iqr"] == 15.0
    assert payload["outliers"]["method"] == "iqr"
    assert payload["outliers"]["outlier_count"] == 0


def test_correlation_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_correlations(dataset_id)
    assert result.numeric_columns == ["sales", "profit"]
    assert len(result.correlations) == 1
    assert result.correlations[0].coefficient == 1.0
    _assert_no_filesystem_paths(result.model_dump(mode="json"))


def test_outlier_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_outliers(dataset_id, "sales")
    assert result.column == "sales"
    assert result.outliers.method == "iqr"
    assert result.outliers.outlier_count == 0
    _assert_no_filesystem_paths(result.model_dump(mode="json"))


def test_histogram_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_histogram(dataset_id, "sales", bins=5)
    assert result.bins == 5
    assert result.column == "sales"
    assert sum(item.count for item in result.data) == 4
    _assert_no_filesystem_paths(result.model_dump(mode="json"))


def test_histogram_bins_are_clamped(client: TestClient) -> None:
    dataset_id = _upload(client)
    too_high = get_histogram(dataset_id, "sales", bins=100)
    too_low = get_histogram(dataset_id, "sales", bins=1)
    assert too_high.bins == 50
    assert too_low.bins == 5


def test_category_count_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_category_counts(dataset_id, "region", limit=15)
    counts = {item.category: item.count for item in result.categories}
    assert counts == {"east": 2, "west": 2}
    _assert_no_filesystem_paths(result.model_dump(mode="json"))


def test_category_count_limit_is_enforced(client: TestClient) -> None:
    dataset_id = _upload(client, HIGH_CARDINALITY_CSV, "many.csv")
    result = get_category_counts(dataset_id, "label", limit=100)
    assert len(result.categories) <= 50
    capped = get_category_counts(dataset_id, "label", limit=3)
    assert len(capped.categories) == 3
    assert capped.categories[-1].category == "Other"


def test_scatter_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_scatter_data(dataset_id, "sales", "profit", max_points=500)
    assert result.point_count == 4
    assert result.sampled is False
    assert result.points[0].x == 10.0
    _assert_no_filesystem_paths(result.model_dump(mode="json"))


def test_scatter_point_cap_is_enforced(client: TestClient) -> None:
    rows = ["x,y"] + [f"{index},{index * 2}" for index in range(30)]
    content = ("\n".join(rows) + "\n").encode("utf-8")
    dataset_id = _upload(client, content, "points.csv")
    result = get_scatter_data(dataset_id, "x", "y", max_points=10)
    assert result.sampled is True
    assert result.point_count == 10
    assert len(result.points) == 10
    over = get_scatter_data(dataset_id, "x", "y", max_points=5000)
    assert over.point_count <= 2000


def test_heatmap_tool(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = get_correlation_heatmap(dataset_id)
    assert result.columns == ["sales", "profit"]
    assert result.matrix[0][1] == 1.0
    _assert_no_filesystem_paths(result.model_dump(mode="json"))


def test_heatmap_without_enough_numeric_columns(client: TestClient) -> None:
    dataset_id = _upload(client, CATEGORICAL_ONLY_CSV, "cats.csv")
    result = get_correlation_heatmap(dataset_id)
    assert result.columns == []
    assert result.matrix == []


def test_unknown_dataset_id_is_controlled(client: TestClient) -> None:
    bogus = "00000000-0000-0000-0000-000000000000"
    try:
        get_dataset_summary(bogus)
        raise AssertionError("expected DatasetError")
    except DatasetError as exc:
        assert exc.status_code == 404
        assert exc.detail == "Dataset not found."
        assert "upload" not in exc.detail.lower() or exc.detail == "Dataset not found."
        assert "\\" not in exc.detail


def test_path_like_dataset_id_is_not_a_filesystem_read(client: TestClient) -> None:
    try:
        get_dataset_summary(r"D:\secret\file.csv")
        raise AssertionError("expected DatasetError")
    except DatasetError as exc:
        assert exc.status_code == 404
        assert exc.detail == "Dataset not found."


def test_unknown_column_is_controlled(client: TestClient) -> None:
    dataset_id = _upload(client)
    try:
        get_column_profile(dataset_id, "not_a_column")
        raise AssertionError("expected DatasetError")
    except DatasetError as exc:
        assert exc.status_code == 400
        assert "Unknown column" in exc.detail
        assert "uploads" not in exc.detail


def test_numeric_tools_reject_categorical_columns(client: TestClient) -> None:
    dataset_id = _upload(client)
    for call in (
        lambda: get_numeric_statistics(dataset_id, "region"),
        lambda: get_outliers(dataset_id, "region"),
        lambda: get_histogram(dataset_id, "region"),
        lambda: get_scatter_data(dataset_id, "region", "sales"),
    ):
        try:
            call()
            raise AssertionError("expected DatasetError")
        except DatasetError as exc:
            assert exc.status_code == 400
            assert "not numeric" in exc.detail


def test_category_counts_reject_numeric_columns(client: TestClient) -> None:
    dataset_id = _upload(client)
    try:
        get_category_counts(dataset_id, "sales")
        raise AssertionError("expected DatasetError")
    except DatasetError as exc:
        assert exc.status_code == 400
        assert "not categorical" in exc.detail
