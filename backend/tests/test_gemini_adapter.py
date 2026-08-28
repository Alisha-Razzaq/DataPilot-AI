"""Gemini adapter tests. No live API calls."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.ai.gemini_adapter import (
    build_gemini_client,
    generate_content_config,
    registry_tools_for_gemini,
)
from app.ai.prompts import DATAPILOT_INSTRUCTIONS
from app.ai.registry import TOOL_NAMES, list_tool_definitions
from app.config import Settings, settings


def test_default_model_is_gemini_flash_lite() -> None:
    assert Settings.model_fields["gemini_model"].default == "gemini-3.1-flash-lite"


def test_build_gemini_client_passes_configured_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    def fake_client(**kwargs):
        captured["kwargs"] = kwargs
        return SimpleNamespace(kind="client")

    monkeypatch.setattr("app.ai.gemini_adapter.genai.Client", fake_client)
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    client = build_gemini_client()
    assert client.kind == "client"
    assert captured["kwargs"] == {"api_key": "test-key"}


def test_registry_tools_match_existing_definitions() -> None:
    tools = registry_tools_for_gemini()
    assert len(tools) == 1
    declarations = tools[0].function_declarations
    assert declarations is not None
    names = [item.name for item in declarations]
    expected = [definition.name for definition in list_tool_definitions()]
    assert names == expected
    assert set(names) == set(TOOL_NAMES)
    assert "run_shell" not in names
    first = declarations[0]
    schema = first.parameters_json_schema
    assert schema["type"] == "object"
    assert "dataset_id" in schema["properties"]


def test_automatic_function_calling_is_disabled() -> None:
    config = generate_content_config(
        registry_tools_for_gemini(), DATAPILOT_INSTRUCTIONS
    )
    assert config.automatic_function_calling is not None
    assert config.automatic_function_calling.disable is True
    assert "not from the model" in str(config.system_instruction).lower()
