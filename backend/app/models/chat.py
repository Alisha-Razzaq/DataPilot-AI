"""Pydantic models for POST /api/chat."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    dataset_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    dataset_id: str
    message: str
    tool_used: str | None = None
    tools_used: list[str] = Field(default_factory=list)
