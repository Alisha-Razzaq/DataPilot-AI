"""Safe whitelist dispatch for Phase 8."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.ai.dispatch import ALLOWED_TOOLS, dispatch_tool
from app.ai.errors import DispatchError
from app.ai.registry import TOOL_NAMES
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

MIXED_CSV = (
    "region,sales,profit\n"
    "east,10,1\n"
    "west,20,2\n"
    "east,30,3\n"
    "west,40,4\n"
).encode("utf-8")

EXPECTED = {
    "get_dataset_summary": get_dataset_summary,
    "get_column_profile": get_column_profile,
    "get_numeric_statistics": get_numeric_statistics,
    "get_correlations": get_correlations,
    "get_outliers": get_outliers,
    "get_histogram": get_histogram,
    "get_category_counts": get_category_counts,
    "get_scatter_data": get_scatter_data,
    "get_correlation_heatmap": get_correlation_heatmap,
}


def _upload(client: TestClient) -> str:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("tools.csv", MIXED_CSV, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["dataset_id"]


def test_whitelist_matches_existing_callables() -> None:
    assert set(ALLOWED_TOOLS) == set(TOOL_NAMES)
    for name, function in EXPECTED.items():
        assert ALLOWED_TOOLS[name] is function


def test_all_nine_tools_dispatch(client: TestClient) -> None:
    dataset_id = _upload(client)
    args = {
        "get_dataset_summary": "{}",
        "get_column_profile": '{"column": "sales"}',
        "get_numeric_statistics": '{"column": "sales"}',
        "get_correlations": "{}",
        "get_outliers": '{"column": "sales"}',
        "get_histogram": '{"column": "sales", "bins": 5}',
        "get_category_counts": '{"column": "region"}',
        "get_scatter_data": '{"x_column": "sales", "y_column": "profit"}',
        "get_correlation_heatmap": "{}",
    }
    for name, arguments in args.items():
        result = dispatch_tool(
            name=name,
            arguments_json=arguments,
            dataset_id=dataset_id,
        )
        dumped = result.model_dump(mode="json")
        assert dumped["dataset_id"] == dataset_id
        assert "stored_path" not in str(dumped)


def test_unknown_tool_is_rejected(client: TestClient) -> None:
    dataset_id = _upload(client)
    with pytest.raises(DispatchError) as caught:
        dispatch_tool(name="os.system", arguments_json="{}", dataset_id=dataset_id)
    assert caught.value.status_code == 400
    assert caught.value.detail == "Unknown tool."


def test_request_dataset_id_overrides_model(client: TestClient) -> None:
    dataset_id = _upload(client)
    result = dispatch_tool(
        name="get_numeric_statistics",
        arguments_json='{"dataset_id": "XYZ", "column": "sales"}',
        dataset_id=dataset_id,
    )
    assert result.dataset_id == dataset_id
    assert result.column == "sales"
    assert result.mean == 25.0


def test_extra_arguments_are_rejected(client: TestClient) -> None:
    dataset_id = _upload(client)
    with pytest.raises(DispatchError) as caught:
        dispatch_tool(
            name="get_numeric_statistics",
            arguments_json='{"column": "sales", "hack": true}',
            dataset_id=dataset_id,
        )
    assert caught.value.detail == "Unexpected tool arguments."


def test_malformed_json_is_rejected(client: TestClient) -> None:
    dataset_id = _upload(client)
    with pytest.raises(DispatchError) as caught:
        dispatch_tool(
            name="get_numeric_statistics",
            arguments_json="{not-json",
            dataset_id=dataset_id,
        )
    assert caught.value.detail == "Malformed tool arguments."


def test_dispatch_source_has_no_dynamic_execution() -> None:
    source = Path("backend/app/ai/dispatch.py").read_text(encoding="utf-8")
    for banned in ("eval(", "exec(", "subprocess", "globals()[", "__import__(", "getattr("):
        assert banned not in source
