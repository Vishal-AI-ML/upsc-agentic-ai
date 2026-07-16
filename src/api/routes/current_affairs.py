"""
Current Affairs routes - Daily CA, Editorials, Monthly digest
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.agents.current_affairs.graph import (
    get_available_dates,
    get_available_months,
    get_daily_ca,
    get_editorial,
    get_editorial_topics,
    get_monthly_summary,
)
from src.schemas import (
    AvailableDatesResponse,
    AvailableMonthsResponse,
    DailyCARequest,
    EditorialRequest,
    EditorialTopicsResponse,
    MonthlyRequest,
)

router = APIRouter(prefix="/current-affairs", tags=["Current Affairs"])


@router.post("/daily")
async def daily_ca(request: DailyCARequest):
    """Get daily current affairs (streaming)."""

    def generate():
        for chunk in get_daily_ca(request.date):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/editorial")
async def editorial(request: EditorialRequest):
    """Get editorial analysis (streaming)."""

    def generate():
        for chunk in get_editorial(request.topic):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/monthly")
async def monthly(request: MonthlyRequest):
    """Get monthly digest (streaming)."""

    def generate():
        for chunk in get_monthly_summary(request.month, request.year):
            yield chunk

    return StreamingResponse(generate(), media_type="text/plain")


@router.get("/topics", response_model=EditorialTopicsResponse)
async def topics():
    """Get available editorial topics."""
    return {"topics": get_editorial_topics()}


@router.get("/dates", response_model=AvailableDatesResponse)
async def dates():
    """Get available dates for daily CA."""
    return {"dates": get_available_dates()}


@router.get("/months", response_model=AvailableMonthsResponse)
async def months():
    """Get available months for monthly digest."""
    return {"months": get_available_months()}
