"""Describe available DataPilot tools. This route does not execute tools."""

from fastapi import APIRouter

from app.ai.registry import list_tool_definitions
from app.ai.schemas import ToolCatalogResponse

router = APIRouter(tags=["tools"])


@router.get(
    "/api/tools",
    response_model=ToolCatalogResponse,
    response_model_exclude_none=True,
    summary="List DataPilot analysis tools",
    description=(
        "Returns provider-independent definitions of the analysis operations "
        "an LLM may request later. This endpoint does not run any tool."
    ),
)
def list_tools() -> ToolCatalogResponse:
    return ToolCatalogResponse(tools=list_tool_definitions())
