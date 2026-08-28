"""Frozen whitelist from model tool names to existing tools.py functions.

Lookup is a dict key check only. Model-supplied names never select Python
attributes or run generated code.
"""

from __future__ import annotations

import inspect
import json
from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

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
from app.services.dataset_service import DatasetError

ALLOWED_TOOLS: Mapping[str, Callable[..., Any]] = MappingProxyType(
    {
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
)


def dispatch_tool(
    *,
    name: str,
    arguments_json: str,
    dataset_id: str,
) -> Any:
    """Run one allow-listed tool. ``dataset_id`` always comes from the HTTP request."""
    if name not in ALLOWED_TOOLS or name not in TOOL_NAMES:
        raise DispatchError(400, "Unknown tool.")

    try:
        parsed: Any = json.loads(arguments_json) if arguments_json.strip() else {}
    except json.JSONDecodeError as exc:
        raise DispatchError(400, "Malformed tool arguments.") from exc

    if not isinstance(parsed, dict):
        raise DispatchError(400, "Malformed tool arguments.")

    payload = dict(parsed)
    payload["dataset_id"] = dataset_id

    function = ALLOWED_TOOLS[name]
    signature = inspect.signature(function)
    unexpected = set(payload) - set(signature.parameters)
    if unexpected:
        raise DispatchError(400, "Unexpected tool arguments.")

    try:
        bound = signature.bind(**payload)
        bound.apply_defaults()
    except TypeError as exc:
        raise DispatchError(400, "Invalid tool arguments.") from exc

    try:
        return function(*bound.args, **bound.kwargs)
    except DatasetError:
        raise
    except DispatchError:
        raise
