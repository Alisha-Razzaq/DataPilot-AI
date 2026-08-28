"""FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.datasets import router as datasets_router
from app.api.health import router as health_router
from app.api.tools import router as tools_router
from app.api.visualizations import router as visualizations_router
from app.config import settings

app = FastAPI(
    title=settings.app_name,
    description=(
        "AI-powered data analysis platform (Phase 8: hosted LLM with explicit "
        "analysis tools. Numbers come from pandas, not from the model)."
    ),
    version="0.8.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(datasets_router)
app.include_router(visualizations_router)
app.include_router(tools_router)
app.include_router(chat_router)
