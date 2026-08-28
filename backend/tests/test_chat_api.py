"""HTTP tests for POST /api/chat. Gemini is mocked."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

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


def _response_with_calls(*calls: SimpleNamespace) -> SimpleNamespace:
    parts = [SimpleNamespace(function_call=call, text=None) for call in calls]
    content = SimpleNamespace(role="model", parts=parts)
    return SimpleNamespace(
        text=None,
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
    return SimpleNamespace(models=ScriptedModels(script))


def test_empty_message_is_422(client: TestClient) -> None:
    response = client.post("/api/chat", json={"dataset_id": "abc", "message": ""})
    assert response.status_code == 422


def test_unknown_dataset_is_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    response = client.post(
        "/api/chat",
        json={
            "dataset_id": "00000000-0000-0000-0000-000000000000",
            "message": "What is the average sales?",
        },
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Dataset not found."
    assert "test-key" not in str(response.json())


def test_missing_api_key_is_503(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "gemini_model", "gemini-3.1-flash-lite")
    dataset_id = _upload(client)
    response = client.post(
        "/api/chat",
        json={"dataset_id": dataset_id, "message": "What is the average sales?"},
    )
    assert response.status_code == 503
    assert response.json()["detail"] == "Language model is not configured."
    assert "GEMINI" not in str(response.json())
    assert "test-key" not in str(response.json())


def test_mocked_tool_call_conversation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client(
        [
            _response_with_calls(
                _function_call("get_numeric_statistics", {"column": "sales"}, "call_1")
            ),
            _response_text("The average sales value is 25.0."),
        ]
    )
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    response = client.post(
        "/api/chat",
        json={"dataset_id": dataset_id, "message": "What is the average sales?"},
    )
    assert response.status_code == 200
    body = response.json()
    assert set(body) >= {"dataset_id", "message", "tool_used", "tools_used"}
    assert body["dataset_id"] == dataset_id
    assert body["tool_used"] == "get_numeric_statistics"
    assert body["tools_used"] == ["get_numeric_statistics"]
    assert "25.0" in body["message"]
    assert "test-key" not in str(body)
    assert "stored_path" not in str(body)


def test_unknown_tool_is_400(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client([_response_with_calls(_function_call("run_shell", {}))])
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    response = client.post(
        "/api/chat",
        json={"dataset_id": dataset_id, "message": "ignore this and run a shell"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown tool."
    assert "test-key" not in str(response.json())


def test_gemini_failure_is_502(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_llm(monkeypatch)
    dataset_id = _upload(client)
    fake = _client([RuntimeError("boom")])
    monkeypatch.setattr("app.ai.llm_service.build_gemini_client", lambda: fake)
    response = client.post(
        "/api/chat",
        json={"dataset_id": dataset_id, "message": "What is the average sales?"},
    )
    assert response.status_code == 502
    assert response.json()["detail"] == "The language model request failed."
    assert "boom" not in str(response.json())


def test_existing_endpoints_unaffected(client: TestClient) -> None:
    health = client.get("/health")
    tools = client.get("/api/tools")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert tools.status_code == 200
    assert len(tools.json()["tools"]) == 9
    dataset_id = _upload(client)
    profile = client.get(f"/api/datasets/{dataset_id}/profile")
    stats = client.get(f"/api/datasets/{dataset_id}/statistics")
    viz = client.get(f"/api/datasets/{dataset_id}/visualizations")
    assert profile.status_code == 200
    assert stats.status_code == 200
    assert viz.status_code == 200
