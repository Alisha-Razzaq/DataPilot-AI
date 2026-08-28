"""Convert Phase 7 registry metadata into Gemini function declarations.

The registry remains the only list of tool names and parameter schemas.
This module does not execute tools. Automatic function calling stays disabled.
"""

from __future__ import annotations

from typing import Any

from google import genai
from google.genai import types

from app.ai.registry import list_tool_definitions
from app.config import settings


def build_gemini_client() -> genai.Client:
    """Create a Gemini client. The key is never logged or returned."""
    return genai.Client(api_key=settings.gemini_api_key)


def registry_tools_for_gemini() -> list[types.Tool]:
    """Map TOOL_DEFINITIONS into Gemini function declarations."""
    declarations: list[types.FunctionDeclaration] = []
    for definition in list_tool_definitions():
        parameters = definition.parameters.model_dump(mode="json", exclude_none=True)
        declarations.append(
            types.FunctionDeclaration(
                name=definition.name,
                description=definition.description,
                parameters_json_schema=parameters,
            )
        )
    return [types.Tool(function_declarations=declarations)]


def generate_content_config(tools: list[types.Tool], system_instruction: str) -> types.GenerateContentConfig:
    """Manual function calling only: the SDK must not execute Python for us."""
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        tools=tools,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )


def function_response_part(
    *,
    name: str,
    payload: dict[str, Any],
    call_id: str | None,
) -> types.Part:
    """Official Gemini function-response part for the next generate_content turn."""
    return types.Part(
        function_response=types.FunctionResponse(
            name=name,
            response=payload,
            id=call_id,
        )
    )
