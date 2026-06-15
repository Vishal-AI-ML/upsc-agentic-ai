"""
Planner routes - Study plan generation
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.models.schemas import PlannerRequest, PlannerResponse
from src.agents.planner.graph import generate_plan

router = APIRouter(prefix="/planner", tags=["Planner"])


@router.post("/generate")
async def generate(request: PlannerRequest):
    """Generate study plan (streaming)."""
    def gen():
        for chunk in generate_plan(
            goal=request.goal,
            hours=request.hours,
            optional=request.optional,
            weak=request.weak,
            attempt_number=request.attempt_number,
        ):
            yield chunk
    
    return StreamingResponse(gen(), media_type="text/plain")


@router.post("/generate/sync", response_model=PlannerResponse)
async def generate_sync(request: PlannerRequest):
    """Generate study plan (non-streaming)."""
    response = ""
    for chunk in generate_plan(
        goal=request.goal,
        hours=request.hours,
        optional=request.optional,
        weak=request.weak,
        attempt_number=request.attempt_number,
    ):
        response += chunk
    return {"plan": response}
