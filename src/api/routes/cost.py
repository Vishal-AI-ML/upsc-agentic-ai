"""Cost dashboard routes (admin-only, #16).

`/cost/access` is auth-only and returns {admin} so the UI can decide whether to
show the tab without catching a 403. `/cost/overview` is admin-guarded and
returns an estimated spend breakdown. Token/agent counters are not wired in this
build, so figures start at zero and the UI shows a friendly "no traffic" note
until real usage tracking is added; the shape is stable and correct.
"""
from fastapi import APIRouter, Depends

from src.api.deps import get_current_user
from src.api.admin_access import is_admin, require_admin
from src.core.config import settings

router = APIRouter(prefix="/cost", tags=["Cost"])


@router.get("/access")
async def cost_access(user: dict = Depends(get_current_user)):
    """Auth-only: report whether the caller may see the cost dashboard."""
    return {"admin": is_admin(user.get("email", ""))}


@router.get("/overview")
async def cost_overview(user: dict = Depends(require_admin)):
    """Admin-only: estimated spend, tier mix, and cache effectiveness."""
    rates = {
        "lite": {
            "input": settings.price_lite_input_inr,
            "output": settings.price_lite_output_inr,
        },
        "strong": {
            "input": settings.price_strong_input_inr,
            "output": settings.price_strong_output_inr,
        },
    }
    return {
        "estimated": True,
        "currency": "INR",
        "totals": {
            "cost_inr": 0.0,
            "input_tokens": 0,
            "output_tokens": 0,
            "tokens": 0,
            "calls": 0,
            "avg_cost_per_call_inr": 0.0,
        },
        "agents": [],
        "tier_mix": {"lite": 0, "strong": 0, "lite_share": 0.0},
        "cache": {
            "hit_exact": 0,
            "hit_semantic": 0,
            "miss": 0,
            "skip": 0,
            "hit_rate": 0.0,
            "estimated_savings_inr": 0.0,
        },
        "rates_inr_per_1k": rates,
    }
