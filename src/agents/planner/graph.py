"""
Planner Agent - Study plan generation with live UPSC dates
"""

import re
import logging
import time as _time
from datetime import datetime, date

from src.core.llm import get_llm
from src.agents.planner.prompts import PLANNER_PROMPT
from src.agents.planner.constants import (
    get_optional_context, get_weak_context,
    get_weak_plan_instruction, get_attempt_guidance,
)
from src.core import mentor_kb

# Official / trusted domains for live UPSC date lookups
TRUSTED_DOMAINS = [
    "upsc.gov.in", "pib.gov.in", "mygov.in",
    "thehindu.com", "indianexpress.com", "drishtiias.com",
]

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# TAVILY SEARCH — lazy init + cached UPSC dates
# ─────────────────────────────────────────

_search_tool = None
_upsc_date_cache = {"date": None, "timestamp": 0}


def _get_search_tool():
    global _search_tool
    if _search_tool is None:
        try:
            from langchain_community.tools.tavily_search import TavilySearchResults
            try:
                _search_tool = TavilySearchResults(
                    max_results=4, include_domains=TRUSTED_DOMAINS
                )
            except Exception:
                _search_tool = TavilySearchResults(max_results=4)
        except Exception as e:
            logger.warning(f"Tavily init failed: {e}")
            return None
    return _search_tool


def _duckduckgo_date_search(attempt_year: int) -> str:
    """Fallback: search DuckDuckGo for the prelims date when Tavily is unavailable."""
    try:
        from duckduckgo_search import DDGS
    except Exception:
        return ""
    try:
        query = f"UPSC CSE Prelims {attempt_year} exam date official notification upsc.gov.in"
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                body = (r.get("body") or "") + " " + (r.get("title") or "")
                match = re.search(
                    r"(prelims|preliminary).*?(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})",
                    body, re.IGNORECASE,
                )
                if match:
                    return match.group(2)
    except Exception as e:
        logger.warning(f"DuckDuckGo date fetch failed: {e}")
    return ""


def _fetch_upsc_prelims_date(attempt_year: int) -> str:
    """Fetch real UPSC prelims date from web. Cached for 24 hours."""
    cache_age = _time.time() - _upsc_date_cache["timestamp"]
    if _upsc_date_cache["date"] and cache_age < 86400:
        return _upsc_date_cache["date"]
    
    date_str = ""
    try:
        tool = _get_search_tool()
        if tool:
            results = tool.invoke(f"UPSC CSE Prelims {attempt_year} exam date official notification")
            for r in (results or []):
                content = r.get("content", "") if isinstance(r, dict) else str(r)
                match = re.search(
                    r"(prelims|preliminary).*?(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})",
                    content, re.IGNORECASE
                )
                if match:
                    date_str = match.group(2)
                    break
    except Exception as e:
        logger.warning(f"UPSC date fetch failed: {e}")

    if not date_str:
        date_str = _duckduckgo_date_search(attempt_year)

    if date_str:
        _upsc_date_cache["date"] = date_str
        _upsc_date_cache["timestamp"] = _time.time()
        logger.info(f"Live UPSC date fetched: {date_str}")
    return date_str


# ─────────────────────────────────────────
# MAIN FUNCTION — streaming
# ─────────────────────────────────────────

def generate_plan(
    goal: str,
    hours: str,
    optional: str,
    weak: str,
    attempt_number: str,
):
    """
    Streaming generator — yields plan chunks.
    """
    today = datetime.now()
    
    # Parse attempt year
    match = re.search(r"20\d\d", goal)
    attempt_year = int(match.group()) if match else today.year + 1
    
    # Fetch live UPSC date
    live_date = _fetch_upsc_prelims_date(attempt_year)
    live_upsc_date = (
        f"Prelims {attempt_year} date: {live_date} (fetched from official sources)"
        if live_date else
        f"Could not fetch live date — verify at upsc.gov.in"
    )
    
    # Calculate months left
    if live_date:
        try:
            from dateutil import parser as dateparser
            prelims_dt = dateparser.parse(live_date)
            months_left = max(0,
                (prelims_dt.year - today.year) * 12 +
                (prelims_dt.month - today.month)
            )
        except Exception:
            months_left = max(0, (attempt_year - today.year) * 12 + (6 - today.month))
    else:
        months_left = max(0, (attempt_year - today.year) * 12 + (6 - today.month))
    
    # Timeline message
    if months_left == 0:
        timeline_msg = "Prelims is this month. Shift focus entirely to revision and mocks."
    elif months_left <= 2:
        timeline_msg = "CRITICAL — under 2 months. Stop new material. Only revision and mocks."
    elif months_left <= 4:
        timeline_msg = "Under 4 months. High-yield topics only. 3 mocks per week minimum."
    elif months_left <= 6:
        timeline_msg = "Under 6 months. Intensive — cover all high-priority topics with daily testing."
    elif months_left <= 12:
        timeline_msg = "Around 1 year. Balanced prep — complete syllabus with regular revision."
    else:
        timeline_msg = "1+ years. Build unshakeable base. Quality over speed."
    
    # Get contexts
    attempt_num = attempt_number.strip() if attempt_number else "1"
    attempt_guidance = get_attempt_guidance(attempt_num)
    
    optional_clean = optional.strip() if optional and optional.strip() else "Not decided"
    weak_clean = weak.strip() if weak and weak.strip() else "Not specified"
    
    optional_context, optional_plan_instruction = get_optional_context(optional_clean)
    weak_context = get_weak_context(weak_clean)
    weak_plan_instruction = get_weak_plan_instruction(weak_clean, months_left)

    # Knowledge base grounding (verified facts + topper strategies)
    try:
        if mentor_kb.kb_exists():
            kb_query = f"UPSC strategy {optional_clean} {weak_clean} prelims preparation"
            kb_res = mentor_kb.search_kb(kb_query, k=4)
            kb_context = kb_res.get("context") or "No extra knowledge-base context available."
        else:
            kb_context = "No extra knowledge-base context available."
    except Exception as e:
        logger.warning(f"Planner KB search failed: {e}")
        kb_context = "No extra knowledge-base context available."
    
    try:
        chain = PLANNER_PROMPT | get_llm()
        for chunk in chain.stream({
            "today": today.strftime("%d %B %Y"),
            "attempt_year": attempt_year,
            "months_left": months_left,
            "timeline_msg": timeline_msg,
            "hours": hours,
            "optional": optional_clean,
            "weak": weak_clean,
            "attempt_number": attempt_num,
            "live_upsc_date": live_upsc_date,
            "attempt_guidance": attempt_guidance,
            "optional_context": optional_context,
            "optional_plan_instruction": optional_plan_instruction,
            "weak_context": weak_context,
            "weak_plan_instruction": weak_plan_instruction,
            "kb_context": kb_context,
        }):
            if hasattr(chunk, "content"):
                yield chunk.content
    except Exception as e:
        logger.error(f"Plan generation failed: {e}")
        yield "⚠️ Plan generation failed. Please try again."
