"""Health-check route used to verify the API process is running."""

from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return a simple status payload. No dataset or AI work happens here."""
    return {"status": "ok"}
