"""
Mentor Agent - Intent detection, Tavily search, streaming responses
"""

import re
import logging
import time as _time
from datetime import datetime

from src.core.llm import get_llm
from src.agents.mentor.prompts import (
    CASUAL_PROMPT, VAGUE_PROMPT, EMOTIONAL_PROMPT, MENTOR_PROMPT
)
from src.core import mentor_kb

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# SEARCH TOOL — lazy init
# ─────────────────────────────────────────

_search_tool = None

# Official / trusted sources for live UPSC facts (dates, notifications, etc.)
TRUSTED_DOMAINS = [
    "upsc.gov.in", "pib.gov.in", "mygov.in",
    "thehindu.com", "indianexpress.com", "drishtiias.com",
]


def _get_search_tool():
    global _search_tool
    if _search_tool is None:
        try:
            from langchain_tavily import TavilySearch
            try:
                _search_tool = TavilySearch(max_results=4, include_domains=TRUSTED_DOMAINS)
            except Exception:
                _search_tool = TavilySearch(max_results=4)
        except ImportError:
            try:
                from langchain_community.tools.tavily_search import TavilySearchResults
                try:
                    _search_tool = TavilySearchResults(max_results=4, include_domains=TRUSTED_DOMAINS)
                except Exception:
                    _search_tool = TavilySearchResults(max_results=4)
            except Exception as e:
                logger.warning(f"Tavily not available: {e}")
                return None
        except Exception as e:
            logger.warning(f"Tavily init failed: {e}")
            return None
    return _search_tool


# ─────────────────────────────────────────
# NEWS CACHE — refresh every 6 hours
# ─────────────────────────────────────────

_news_cache = {"content": "", "timestamp": 0}

def _fetch_latest_upsc_news() -> str:
    if _time.time() - _news_cache["timestamp"] < 21600:
        return _news_cache["content"]
    try:
        tool = _get_search_tool()
        if not tool:
            return _duckduckgo_search("latest UPSC CSE notification schedule")
        results = tool.invoke("latest UPSC CSE 2026 notification schedule update")
        if not results:
            return ""
        content = results[0].get("content", "")[:600]
        _news_cache["content"] = content
        _news_cache["timestamp"] = _time.time()
        return content
    except Exception as e:
        logger.warning(f"News fetch failed: {e}")
        return ""


# ─────────────────────────────────────────
# INTENT DETECTION PATTERNS
# ─────────────────────────────────────────

CASUAL_PATTERNS = [
    r"^(hi|hello|hey|hii|helo|hye|sup|yo|good morning|good evening|good night|gm|gn)[\s!.,]*$",
    r"^(kya haal|kaise ho|kaisa hai|kya chal raha|how are you|what's up|wassup)[\s!.,?]*$",
    r"^(thanks|thank you|shukriya|dhanyawad|thx|ty)[\s!.,]*$",
    r"^(ok|okay|theek hai|accha|acha|hmm|hm|ohh|oh)[\s!.,]*$",
    r"^(bye|goodbye|alvida|see you|cya)[\s!.,]*$",
]

VAGUE_PATTERNS = [
    r"^exam\s*20\d\d[\s!.,?]*$",
    r"^upsc\s*20\d\d[\s!.,?]*$",
    r"^(strategy|plan|help|guide me|kya karu|kya karun)[\s!.,?]*$",
    r"^(book|books|resource|resources)[\s!.,?]*$",
    r"^(syllabus)[\s!.,?]*$",
]

SEARCH_TRIGGER_PATTERNS = [
    r"\bdate\b", r"\bschedule\b", r"\bnotification\b", r"\bwhen\b",
    r"\bprelims\b", r"\bmains\b", r"\binterview\b", r"\bresult\b",
    r"\bcutoff\b", r"\bcut.?off\b", r"\bvacancy\b", r"\bpost\b",
    r"\btopper\b", r"\brank\b", r"\bsyllabus change\b", r"\bupsc 20\d\d\b",
]

EMOTIONAL_PATTERNS = [
    r"\b(stressed|anxiety|depressed|giving up|quit|fail|hopeless|scared)\b",
    r"\b(rone ka|rona|haar gaya|thak gaya|chhod dun|chhod du)\b",
    r"\b(demotivated|demoralised|tired|exhausted|burned out)\b",
]


def _is_casual(q: str) -> bool:
    return any(re.match(p, q.strip().lower()) for p in CASUAL_PATTERNS)

def _is_vague(q: str) -> bool:
    return any(re.match(p, q.strip().lower()) for p in VAGUE_PATTERNS)

def _needs_search(q: str) -> bool:
    return any(re.search(p, q.lower()) for p in SEARCH_TRIGGER_PATTERNS)

def _is_emotional(q: str) -> bool:
    return any(re.search(p, q.lower()) for p in EMOTIONAL_PATTERNS)


def detect_intent(question: str) -> str:
    """Detect user intent from question."""
    q = question.strip().lower()
    if _is_casual(q):
        return "casual"
    if _is_vague(q):
        return "vague"
    if _is_emotional(q):
        return "emotional"
    return "full"


# ─────────────────────────────────────────
# SEARCH
# ─────────────────────────────────────────

def _duckduckgo_search(question: str) -> str:
    # Free, keyless fallback when Tavily is unavailable or returns nothing.
    try:
        from duckduckgo_search import DDGS
    except ImportError:
        return ""
    try:
        lines = []
        with DDGS() as ddgs:
            for r in ddgs.text(question + " UPSC CSE official", max_results=4):
                title = r.get("title", "")
                body = (r.get("body", "") or "")[:300]
                href = r.get("href", "")
                lines.append(f"- {title}: {body} (Source: {href})")
        return chr(10).join(lines)
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return ""


def _fetch_search_context(question: str) -> str:
    try:
        tool = _get_search_tool()
        if not tool:
            return ""
        raw = tool.invoke(question + " UPSC CSE official 2026")
        results = raw.get("results", []) if isinstance(raw, dict) else (raw or [])
        if not results:
            return _duckduckgo_search(question)
        lines = []
        for r in results:
            title = r.get("title", "")
            content = r.get("content", "")[:300]
            url = r.get("url", "")
            lines.append(f"- {title}: {content} (Source: {url})")
        return "\n".join(lines)
    except Exception as e:
        logger.warning(f"Search failed: {e}")
        return ""


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def _build_student_context(ctx: dict | None) -> str:
    if not ctx:
        return "No profile yet — infer from the question."
    fields = {
        "Name": ctx.get("name"),
        "Optional": ctx.get("optional"),
        "Stage": ctx.get("stage"),
        "Weak Areas": ctx.get("weak_areas"),
        "Strong Areas": ctx.get("strong_areas"),
        "Target Year": ctx.get("target_year"),
        "Daily Hours": ctx.get("study_hours"),
        "Attempts": ctx.get("attempts"),
    }
    lines = [f"- {k}: {v}" for k, v in fields.items() if v]
    return "\n".join(lines) if lines else "No profile yet — infer from the question."


def _format_chat_history(history: list | None) -> str:
    if not history:
        return "No previous conversation."
    recent = history[-6:]
    lines = []
    for m in recent:
        role = "Student" if m["role"] == "user" else "Arjun"
        lines.append(f"{role}: {m['content'][:200]}")
    return "\n".join(lines)


# ─────────────────────────────────────────
# MAIN FUNCTION — streaming
# ─────────────────────────────────────────

def mentor_reply(
    question: str,
    student_context: dict | None = None,
    chat_history: list | None = None,
):
    """
    Streaming generator — yields response chunks.
    """
    if not question or not question.strip():
        yield "Ask me something — I'm here!"
        return

    question = question.strip()
    current_date = datetime.now().strftime("%B %d, %Y")
    llm = get_llm()

    # ── Casual ──
    if _is_casual(question):
        try:
            latest_news = _fetch_latest_upsc_news()
            chain = CASUAL_PROMPT | llm
            for chunk in chain.stream({
                "question": question,
                "latest_news": latest_news or "No major updates right now.",
                "current_date": current_date,
            }):
                if hasattr(chunk, "content"):
                    yield chunk.content
        except Exception as e:
            logger.error(f"Casual reply failed: {e}")
            yield "Hey! Good to have you here. What's on your mind?"
        return

    # ── Vague ──
    if _is_vague(question):
        try:
            chain = VAGUE_PROMPT | llm
            for chunk in chain.stream({"question": question}):
                if hasattr(chunk, "content"):
                    yield chunk.content
        except Exception as e:
            logger.error(f"Vague reply failed: {e}")
            yield "Can you be a bit more specific? What exactly do you want to know?"
        return

    # ── Emotional ──
    if _is_emotional(question):
        try:
            chain = EMOTIONAL_PROMPT | llm
            for chunk in chain.stream({
                "question": question,
                "current_date": current_date,
            }):
                if hasattr(chunk, "content"):
                    yield chunk.content
        except Exception as e:
            logger.error(f"Emotional reply failed: {e}")
            yield "Hey, it's okay to feel this way. Take a breath. What's going on?"
        return

    # ── Full mentor mode ──
    # Always consult the persistent background knowledge base (verified facts +
    # topper strategies). It is invisible to the user; we only pull from it on
    # demand when the question actually matches stored knowledge.
    kb_context = "No matching background knowledge."
    try:
        kb = mentor_kb.search_kb(question, k=4)
        if kb.get("context"):
            kb_context = kb["context"]
    except Exception as e:
        logger.warning(f"Mentor KB lookup failed: {e}")

    # Only hit the live web for volatile, current-year specifics.
    search_results = ""
    if _needs_search(question):
        search_results = _fetch_search_context(question)
        if search_results:
            logger.info(f"Live search injected for: {question[:60]}")

    try:
        chain = MENTOR_PROMPT | llm
        for chunk in chain.stream({
            "question": question,
            "current_date": current_date,
            "student_context": _build_student_context(student_context),
            "chat_history": _format_chat_history(chat_history),
            "kb_context": kb_context,
            "search_results": search_results or "No live search data — for exact dates/cut-offs/vacancies, verify at upsc.gov.in.",
        }):
            if hasattr(chunk, "content"):
                yield chunk.content
    except Exception as e:
        logger.error(f"Mentor reply failed: {e}")
        yield "Something went wrong — please try again in a moment."
