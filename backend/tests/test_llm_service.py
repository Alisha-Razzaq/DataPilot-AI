"""LLM service tests. Gemini is always mocked; no live HTTPS."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.ai.errors import DispatchError, LlmError
from app.ai.llm_service import MAX_TOOL_ROUNDS, answer_question
from app.config import settings

MIXED_CSV = (
    "region,sales,profit\n"
    "east,10,1\n"
    "west,20,2\n"
    "east,30,3\n"
    "west,40,4\n"
).encode("utf-8")


def _upload(client: TestClient) -> str:
    response = client.post(
        "/api/datasets/upload",
        files={"file": ("sales.csv", MIXED_CSV, "text/csv")},
    )
    assert response.status_code == 201
    return response.json()["dataset_id"]


def _configure_llm(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.1-flash-lite")


def _function_call(name: str, args: dict, call_id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(name=name, args=args, id=call_id)


def _response_with_calls(*calls: SimpleNamespace, text: str | None = None) -> SimpleNamespace:
    parts = [SimpleNamespace(function_call=call, text=None) for call in calls]
    content = SimpleNamespace(role="model", parts=parts)
    return SimpleNamespace(
        text=text,
        function_calls=list(calls),
        candidates=[SimpleNamespace(content=content)],
    )


def _response_text(text: str) -> SimpleNamespace:
    content = SimpleNamespace(
        role="model",
        parts=[SimpleNamespace(text=text, function_call=None)],
    )
    return SimpleNamespace(
        text=text,
        function_calls=None,
        candidates=[SimpleNamespace(content=content)],
    )


class ScriptedModels:
    def __init__(self, script: list[object]) -> None:
        self.script = list(script)
        self.calls: list[dict] = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if not self.script:
            raise AssertionError("unexpected Gemini call")
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _client(script: list[object]) -> SimpleNamespace:
    models = ScriptedModels(script)
    return SimpleNamespace(models=models, recorded=models)


def test_no_tool_returns_final_answer(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client([_response_text("Hello. I need a dataset question.")])
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    result = answer_question(dataset_id, "Hi")
    assert result.message.startswith("Hello")
    assert result.tool_used is None
    assert result.tools_used == []
    first = fake.recorded.calls[0]
    assert first["model"] == "gemini-3.1-flash-lite"
    assert first["config"].automatic_function_calling.disable is True
    assert first["config"].tools


def test_numeric_question_runs_statistics_tool(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    first = _response_with_calls(
        _function_call(
            "get_numeric_statistics",
            {"dataset_id": "XYZ", "column": "sales"},
            "call_1",
        )
    )
    second = _response_text("The average sales value is 25.0.")
    fake = _client([first, second])
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)

    result = answer_question(dataset_id, "What is the average sales?")
    assert result.tool_used == "get_numeric_statistics"
    assert result.tools_used == ["get_numeric_statistics"]
    assert "25.0" in result.message

    follow = fake.recorded.calls[1]
    contents = follow["contents"]
    function_response = contents[-1].parts[0].function_response
    assert function_response.name == "get_numeric_statistics"
    payload = str(function_response.response)
    assert '"mean": 25.0' in payload or "'mean': 25.0" in payload
    assert dataset_id in payload
    assert "XYZ" not in payload


def test_unknown_tool_call_is_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client([_response_with_calls(_function_call("run_shell", {}))])
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    with pytest.raises(DispatchError) as caught:
        answer_question(dataset_id, "hack")
    assert caught.value.detail == "Unknown tool."
    assert len(fake.recorded.calls) == 1


def test_extra_arguments_are_rejected(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client(
        [
            _response_with_calls(
                _function_call(
                    "get_numeric_statistics",
                    {"column": "sales", "eval": "os.system('x')"},
                )
            )
        ]
    )
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    with pytest.raises(DispatchError) as caught:
        answer_question(dataset_id, "hack args")
    assert caught.value.detail == "Unexpected tool arguments."


def test_tool_rounds_are_bounded(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    looping = _function_call("get_dataset_summary", {}, "call_loop")
    responses = [_response_with_calls(looping) for _ in range(MAX_TOOL_ROUNDS + 1)]
    fake = _client(responses)
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    with pytest.raises(LlmError) as caught:
        answer_question(dataset_id, "summarize forever")
    assert caught.value.status_code == 400
    assert caught.value.detail == "Too many tool requests."
    assert len(fake.recorded.calls) == MAX_TOOL_ROUNDS + 1


def test_gemini_failure_is_controlled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client([RuntimeError("network down")])
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    with pytest.raises(LlmError) as caught:
        answer_question(dataset_id, "What is the average sales?")
    assert caught.value.status_code == 502
    assert "network" not in caught.value.detail.lower()


def test_gemini_diagnostics_redact_secrets_and_keep_error_fields() -> None:
    from google.genai.errors import APIError

    from app.ai.llm_service import _safe_gemini_diagnostics

    exc = APIError(
        404,
        {
            "error": {
                "type": "invalid_request_error",
                "code": "model_not_found",
                "param": "model",
                "message": "Bearer AIzaSecretValue123 model_not_found",
            }
        },
    )
    text = _safe_gemini_diagnostics(exc)
    assert "exception_type=APIError" in text
    assert "status_code=404" in text
    assert "error_code=model_not_found" in text
    assert "AIzaSecretValue123" not in text
    assert "Bearer" not in text


def test_missing_api_key_does_not_call_gemini(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.1-flash-lite")
    dataset_id = _upload(client)
    called = {"value": False}

    def boom() -> None:
        called["value"] = True
        raise AssertionError("must not build client")

    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", boom)
    with pytest.raises(LlmError) as caught:
        answer_question(dataset_id, "What is the average sales?")
    assert caught.value.status_code == 503
    assert called["value"] is False


def test_unknown_dataset_does_not_call_gemini(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    called = {"value": False}

    def boom() -> None:
        called["value"] = True
        raise AssertionError("must not build client")

    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", boom)
    from app.services.dataset_service import DatasetError

    with pytest.raises(DatasetError):
        answer_question("00000000-0000-0000-0000-000000000000", "hello")
    assert called["value"] is False


def test_row_count_question_runs_dataset_summary(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client(
        [
            _response_with_calls(
                _function_call("get_dataset_summary", {"dataset_id": "other-id"})
            ),
            _response_text("The dataset has 4 rows."),
        ]
    )
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    result = answer_question(dataset_id, "How many rows are in the dataset?")
    assert result.message == "The dataset has 4 rows."
    assert result.tool_used == "get_dataset_summary"
    assert result.tools_used == ["get_dataset_summary"]
    payload = str(fake.recorded.calls[1]["contents"][-1].parts[0].function_response.response)
    assert "'rows': 4" in payload or '"rows": 4' in payload
    assert dataset_id in payload
    assert "other-id" not in payload


def test_category_question_runs_category_counts(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client(
        [
            _response_with_calls(
                _function_call("get_category_counts", {"column": "region"})
            ),
            _response_text("East and west each appear twice."),
        ]
    )
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    result = answer_question(dataset_id, "How many rows are in each region?")
    assert result.tool_used == "get_category_counts"
    assert result.tools_used == ["get_category_counts"]
    assert "East" in result.message or "east" in result.message.lower()
    payload = str(fake.recorded.calls[1]["contents"][-1].parts[0].function_response.response)
    assert "east" in payload.lower()
    assert "west" in payload.lower()
    assert dataset_id in payload


def test_missing_model_is_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")
    monkeypatch.setattr(settings, "gemini_model", "")
    dataset_id = _upload(client)
    called = {"value": False}

    def boom() -> None:
        called["value"] = True
        raise AssertionError("must not build client")

    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", boom)
    with pytest.raises(LlmError) as caught:
        answer_question(dataset_id, "How many rows?")
    assert caught.value.status_code == 503
    assert called["value"] is False


def test_application_and_tests_do_not_import_openai() -> None:
    import ast
    from pathlib import Path

    roots = [
        Path(__file__).resolve().parents[1] / "app",
        Path(__file__).resolve().parent,
    ]
    offenders: list[str] = []
    for root in roots:
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "openai" or alias.name.startswith("openai."):
                            offenders.append(str(path))
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ""
                    if module == "openai" or module.startswith("openai."):
                        offenders.append(str(path))
    assert offenders == []
