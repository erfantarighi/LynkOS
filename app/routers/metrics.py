from typing import Any

from fastapi import APIRouter, Depends

from app.auth import current_user
from app.metrics import SAMPLE_INTERVAL, WINDOW_SECONDS, collector

router = APIRouter(prefix="/api/metrics", tags=["metrics"], dependencies=[Depends(current_user)])


@router.get("/series")
async def series() -> dict[str, Any]:
    return {
        "interval_seconds": SAMPLE_INTERVAL,
        "window_seconds": WINDOW_SECONDS,
        "samples": collector.snapshot(),
    }
