"""Thin chat route. OpenAI and pandas stay out of this module."""

from fastapi import APIRouter, HTTPException

from app.ai.errors import DispatchError, LlmError
from app.ai.llm_service import answer_question
from app.models.chat import ChatRequest, ChatResponse
from app.services.dataset_service import DatasetError

router = APIRouter(tags=["chat"])


def _http(exc: DatasetError | DispatchError | LlmError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.post(
    "/api/chat",
    response_model=ChatResponse,
    summary="Ask a question about an uploaded dataset",
    description=(
        "Sends the question to a hosted LLM. The model may request one of the "
        "existing analysis tools. Python executes that tool. Numbers come from pandas."
    ),
    responses={
        404: {"description": "Dataset not found in the in-memory registry."},
        502: {"description": "The language model request failed."},
        503: {"description": "Language model is not configured."},
    },
)
def chat(body: ChatRequest) -> ChatResponse:
    try:
        return answer_question(body.dataset_id, body.message)
    except (DatasetError, DispatchError, LlmError) as exc:
        raise _http(exc) from exc
