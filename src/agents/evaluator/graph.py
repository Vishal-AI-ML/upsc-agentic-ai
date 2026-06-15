"""
Evaluator Agent - Answer evaluation, mains scoring, model answers
"""

import re
import logging

from src.core.llm import get_llm
from src.agents.evaluator.prompts import (
    EVALUATOR_PROMPT, MAINS_EVAL_PROMPT, MAINS_MODEL_PROMPT
)

logger = logging.getLogger(__name__)


def _log_eval(kind, text):
    """Parse 'Score: X/Y' and log eval accuracy (best-effort)."""
    try:
        from src.core import observability
        m = re.search(r"Score:\s*(\d+)\s*/\s*(\d+)", text)
        if m:
            observability.log_eval_metrics(kind, int(m.group(1)), int(m.group(2)))
    except Exception:
        pass


# ─────────────────────────────────────────
# BASIC EVALUATION
# ─────────────────────────────────────────

def evaluate_answer(question: str, answer: str):
    """Basic answer evaluation (streaming)."""
    if not question.strip():
        yield "⚠️ Please provide a question to evaluate against."
        return
    if not answer.strip():
        yield "⚠️ Please write an answer to evaluate."
        return
    if len(answer.split()) < 50:
        yield f"⚠️ Answer too short ({len(answer.split())} words). Please write at least 50 words for a proper evaluation."
        return
    if len(question.split()) < 5:
        yield "⚠️ Please provide a complete question (at least 5 words)."
        return
    
    try:
        chain = EVALUATOR_PROMPT | get_llm()
        _buf = ""
        for chunk in chain.stream({
            "question": question.strip(),
            "answer": answer.strip(),
            "word_count": len(answer.split()),
        }):
            if hasattr(chunk, "content"):
                _buf += chunk.content
                yield chunk.content
        _log_eval("answer", _buf)
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        yield "⚠️ Evaluation failed. Please try again."


# ─────────────────────────────────────────
# MAINS EVALUATION
# ─────────────────────────────────────────

def evaluate_mains(
    question: str,
    answer: str,
    marks: int = 10,
    keywords: list = None,
    word_limit: int = 150,
):
    """Mains answer evaluation (streaming)."""
    if not answer or not answer.strip():
        yield "Please write an answer first."
        return
    
    answer_wc = len(re.findall(r'\b\w+\b', answer))
    
    if answer_wc < 30:
        yield f"⚠️ Answer too short ({answer_wc} words). Write at least 30 words for a {marks}-mark question."
        return
    
    kw_list = keywords or []
    kw_str = ", ".join(kw_list) if kw_list else "No specific keywords required"
    
    # Keyword analysis
    answer_lower = answer.lower()
    present_kw = [k for k in kw_list if k.lower() in answer_lower]
    missing_kw = [k for k in kw_list if k.lower() not in answer_lower]
    
    if missing_kw:
        keyword_analysis_instruction = (
            f"Present: {', '.join(present_kw) if present_kw else 'None'} | "
            f"Missing: {', '.join(missing_kw)}"
        )
    else:
        keyword_analysis_instruction = (
            f"All expected keywords present: {', '.join(present_kw)} ✓ — No keyword marks deduction."
        )
    
    # Marks distribution
    if marks == 10:
        content_marks, analysis_marks, structure_marks, keyword_marks = 4, 3, 2, 1
    else:
        content_marks, analysis_marks, structure_marks, keyword_marks = 6, 5, 3, 1
    
    try:
        chain = MAINS_EVAL_PROMPT | get_llm()
        _buf = ""
        for chunk in chain.stream({
            "question": question,
            "answer": answer.strip(),
            "answer_wc": answer_wc,
            "marks": marks,
            "word_limit": word_limit,
            "keywords": kw_str,
            "content_marks": content_marks,
            "analysis_marks": analysis_marks,
            "structure_marks": structure_marks,
            "keyword_marks": keyword_marks,
            "keyword_analysis_instruction": keyword_analysis_instruction,
        }):
            if hasattr(chunk, "content"):
                _buf += chunk.content
                yield chunk.content
        _log_eval("mains", _buf)
    except Exception as e:
        logger.error(f"Mains evaluation failed: {e}")
        yield "⚠️ Evaluation failed. Please try again."


# ─────────────────────────────────────────
# MODEL ANSWER
# ─────────────────────────────────────────

def get_model_answer(
    question: str,
    marks: int = 10,
    keywords: list = None,
    word_limit: int = 150,
):
    """Generate model answer (streaming)."""
    kw_str = ", ".join(keywords) if keywords else "General UPSC terminology"
    
    yield "> ⚠️ AI-generated model answer - verify facts and structure against standard sources or toppers copies." + chr(10) + chr(10)
    try:
        chain = MAINS_MODEL_PROMPT | get_llm()
        for chunk in chain.stream({
            "question": question,
            "marks": marks,
            "word_limit": word_limit,
            "keywords": kw_str,
        }):
            if hasattr(chunk, "content"):
                yield chunk.content
    except Exception as e:
        logger.error(f"Model answer generation failed: {e}")
        yield "⚠️ Could not generate model answer. Please try again."


def parse_score(evaluation: str) -> int | None:
    """Extract score from evaluation text."""
    match = re.search(r"Score:\s*(\d+)/\d+", evaluation)
    return int(match.group(1)) if match else None
