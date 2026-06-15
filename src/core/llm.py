"""
LLM initialization - multi-provider with automatic fallback ("router").

Provider order:
  1. Google Gemini  (flash / flash-lite)   - primary, best quality
  2. Groq           (free tier, Llama 3.x) - fallback when Gemini 429s

get_llm() / get_fast_llm() return a Runnable that already has fallbacks
attached, so EVERY existing chain (PROMPT | get_llm()) and every
.invoke()/.stream() call transparently fails over to the next provider on
any error - including 429 RESOURCE_EXHAUSTED (daily free-tier quota).

No agent code needs to change. Set GROQ_API_KEY in .env to enable the
Groq fallback (free key from https://console.groq.com). If GROQ_API_KEY is
empty, the app behaves exactly as before (Gemini only).
"""

import logging

from langchain_google_genai import ChatGoogleGenerativeAI
from src.core.config import settings
from src.core.observability import langchain_callbacks

logger = logging.getLogger(__name__)

_llm_instance = None
_fast_llm_instance = None


def _with_tracing(model, model_name: str):
    """Attach Langfuse callbacks if enabled; else return model unchanged."""
    cbs = langchain_callbacks()
    if cbs:
        return model.with_config({"callbacks": cbs, "tags": ["upsc-ai", model_name]})
    return model


def _make_gemini(model_name: str, temperature: float):
    """Build a traced Gemini model, or None if no key / init fails."""
    if not settings.google_api_key:
        return None
    try:
        model = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            max_retries=settings.llm_max_retries,
        )
        return _with_tracing(model, model_name)
    except Exception as e:
        logger.warning(f"Gemini init failed ({model_name}): {e}")
        return None


def _make_groq(model_name: str, temperature: float):
    """Build a traced Groq model, or None if no key / package / init fails."""
    if not settings.groq_api_key:
        return None
    try:
        from langchain_groq import ChatGroq
    except ImportError:
        logger.warning(
            "langchain-groq not installed; Groq fallback disabled. "
            "Run: uv add langchain-groq"
        )
        return None
    try:
        model = ChatGroq(
            model=model_name,
            api_key=settings.groq_api_key,
            temperature=temperature,
            max_retries=1,
        )
        return _with_tracing(model, model_name)
    except Exception as e:
        logger.warning(f"Groq init failed ({model_name}): {e}")
        return None


def _chain_with_fallbacks(providers: list):
    """
    providers: ordered list of (label, runnable-or-None).
    Returns the first available provider with the rest attached as fallbacks.
    """
    active = [(label, r) for label, r in providers if r is not None]
    if not active:
        raise ValueError(
            "No LLM provider available. Set GOOGLE_API_KEY and/or GROQ_API_KEY in .env."
        )
    order = " -> ".join(label for label, _ in active)
    logger.info(f"LLM chain ready: {order}")

    primary = active[0][1]
    fallbacks = [r for _, r in active[1:]]
    if not settings.enable_provider_fallback or not fallbacks:
        return primary
    return primary.with_fallbacks(fallbacks)


def get_llm():
    """
    Main LLM chain (quality first):
        Gemini flash -> Gemini flash-lite -> Groq
    Use for: notes, CA, mentor, planner, evaluator, chat, study aids.
    """
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = _chain_with_fallbacks([
            ("gemini/" + settings.llm_model, _make_gemini(settings.llm_model, settings.llm_temperature)),
            ("gemini/" + settings.llm_fast_model, _make_gemini(settings.llm_fast_model, settings.llm_temperature)),
            ("groq/" + settings.groq_model, _make_groq(settings.groq_model, settings.llm_temperature)),
        ])
    return _llm_instance


def get_fast_llm():
    """
    Fast LLM chain (cheap/quick first, preserves flash quota):
        Gemini flash-lite -> Groq fast -> Gemini flash
    Use for: mindmap, questions, topic detection, translation.
    """
    global _fast_llm_instance
    if _fast_llm_instance is None:
        _fast_llm_instance = _chain_with_fallbacks([
            ("gemini/" + settings.llm_fast_model, _make_gemini(settings.llm_fast_model, 0.2)),
            ("groq/" + settings.groq_fast_model, _make_groq(settings.groq_fast_model, 0.2)),
            ("gemini/" + settings.llm_model, _make_gemini(settings.llm_model, 0.2)),
        ])
    return _fast_llm_instance


def reset_llm() -> None:
    """Force re-initialize both LLM chains."""
    global _llm_instance, _fast_llm_instance
    _llm_instance = None
    _fast_llm_instance = None
    logger.info("LLM instances reset")
