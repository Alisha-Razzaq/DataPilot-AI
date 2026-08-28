"""Bounded Gemini generate_content orchestration. Numbers still come from tools.py."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from google.genai import types
from google.genai.errors import APIError as GeminiAPIError

from app.ai.dispatch import dispatch_tool
from app.ai.errors import LlmError
from app.ai.gemini_adapter import (
    build_gemini_client,
    function_response_part,
    generate_content_config,
    registry_tools_for_gemini,
)
from app.ai.prompts import DATAPILOT_INSTRUCTIONS
from app.config import settings
from app.models.chat import ChatResponse
from app.services.dataset_service import load_registered_frame

logger = logging.getLogger("uvicorn.error")
_SECRET_RE = re.compile(
    r"(?i)(Authorization:\s*\S+|Bearer\s+\S+|api[_-]?key\s*[=:]\s*\S+|"
    r"sk-[A-Za-z0-9_-]+|AIza[A-Za-z0-9_-]+)"
)

MAX_TOOL_ROUNDS = 3


def _function_calls(response: Any) -> list[Any]:
    calls = getattr(response, "function_calls", None) or []
    return list(calls)


def _call_name(item: Any) -> str:
    name = item["name"] if isinstance(item, dict) else item.name
    return name or ""


def _call_arguments_json(item: Any) -> str:
    raw = item["args"] if isinstance(item, dict) else getattr(item, "args", None)
    if raw is None:
        return "{}"
    if isinstance(raw, str):
        return raw
    return json.dumps(raw)


def _call_id(item: Any) -> str | None:
    value = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _tool_result_payload(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        dumped = result.model_dump(mode="json")
    else:
        dumped = result
    return {"result": dumped}


def _model_content(response: Any) -> Any:
    candidates = getattr(response, "candidates", None) or []
    if candidates:
        content = getattr(candidates[0], "content", None)
        if content is not None:
            return content
    return types.Content(role="model", parts=[])


def _final_text(response: Any) -> str:
    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text
    return "I could not produce an answer from the tool results."


def _require_llm_config() -> None:
    if not settings.gemini_api_key.strip() or not settings.gemini_model.strip():
        raise LlmError(503, "Language model is not configured.")


def _redact_secrets(text: str) -> str:
    return _SECRET_RE.sub("[redacted]", text)


def _nested_error_fields(body: object) -> dict[str, str]:
    if not isinstance(body, dict):
        return {}
    inner = body.get("error")
    source = inner if isinstance(inner, dict) else body
    fields: dict[str, str] = {}
    for key in ("type", "code", "param", "status"):
        value = source.get(key)
        if isinstance(value, str) and value.strip():
            fields[key] = value.strip()
        elif isinstance(value, int):
            fields[key] = str(value)
    return fields


def _safe_gemini_diagnostics(exc: BaseException) -> str:
    """Exception type and API error fields only. Never headers, keys, or full bodies."""
    parts = [f"exception_type={type(exc).__name__}"]
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int):
        parts.append(f"status_code={code}")
    status = getattr(exc, "status", None)
    if isinstance(status, str) and status.strip():
        parts.append(f"status={status.strip()}")
    nested = _nested_error_fields(getattr(exc, "details", None) or getattr(exc, "body", None))
    for key in ("type", "code", "param", "status"):
        if key in nested:
            parts.append(f"error_{key}={nested[key]}")
    raw_message = getattr(exc, "message", None) or str(exc)
    cleaned = _redact_secrets(str(raw_message)).replace("\n", " ").strip()
    if len(cleaned) > 300:
        cleaned = cleaned[:300] + "..."
    if cleaned:
        parts.append(f"message={cleaned}")
    return " ".join(parts)


def _generate_content(client: Any, *, model: str, contents: Any, config: Any) -> Any:
    logger.info(
        "Gemini generate_content: model=%s tool_count=%s",
        model,
        len(getattr(config, "tools", None) or []),
    )
    try:
        return client.models.generate_content(model=model, contents=contents, config=config)
    except LlmError:
        raise
    except GeminiAPIError as exc:
        logger.error("Gemini generate_content failed: %s", _safe_gemini_diagnostics(exc))
        raise LlmError(502, "The language model request failed.") from exc
    except Exception as exc:
        logger.error("Gemini generate_content failed: %s", _safe_gemini_diagnostics(exc))
        raise LlmError(502, "The language model request failed.") from exc


def answer_question(dataset_id: str, message: str) -> ChatResponse:
    """Ask the hosted model; execute at most MAX_TOOL_ROUNDS of allow-listed tools."""
    load_registered_frame(dataset_id)
    _require_llm_config()

    client = build_gemini_client()
    tools = registry_tools_for_gemini()
    config = generate_content_config(tools, DATAPILOT_INSTRUCTIONS)
    logger.info(
        "Gemini client ready: class=%s has_generate_content=%s model=%s key_configured=%s afc_disabled=%s",
        type(client).__name__,
        callable(getattr(getattr(client, "models", None), "generate_content", None)),
        settings.gemini_model,
        bool(settings.gemini_api_key.strip()),
        bool(getattr(getattr(config, "automatic_function_calling", None), "disable", False)),
    )
    user_input = f"dataset_id: {dataset_id}\n\n{message}"
    contents: list[Any] = [
        types.Content(role="user", parts=[types.Part.from_text(text=user_input)])
    ]

    response = _generate_content(
        client,
        model=settings.gemini_model,
        contents=contents,
        config=config,
    )

    tools_used: list[str] = []
    for _round in range(MAX_TOOL_ROUNDS):
        calls = _function_calls(response)
        if not calls:
            return ChatResponse(
                dataset_id=dataset_id,
                message=_final_text(response),
                tool_used=tools_used[-1] if tools_used else None,
                tools_used=tools_used,
            )

        response_parts: list[types.Part] = []
        for call in calls:
            name = _call_name(call)
            result = dispatch_tool(
                name=name,
                arguments_json=_call_arguments_json(call),
                dataset_id=dataset_id,
            )
            tools_used.append(name)
            response_parts.append(
                function_response_part(
                    name=name,
                    payload=_tool_result_payload(result),
                    call_id=_call_id(call),
                )
            )

        contents.append(_model_content(response))
        contents.append(types.Content(role="user", parts=response_parts))
        response = _generate_content(
            client,
            model=settings.gemini_model,
            contents=contents,
            config=config,
        )

    if _function_calls(response):
        raise LlmError(400, "Too many tool requests.")

    return ChatResponse(
        dataset_id=dataset_id,
        message=_final_text(response),
        tool_used=tools_used[-1] if tools_used else None,
        tools_used=tools_used,
    )
