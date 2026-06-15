"""
NCERT Agent - PDF reading, notes generation, RAG chat
"""

import os
import logging
from functools import lru_cache

from pypdf import PdfReader
from langchain_core.prompts import ChatPromptTemplate

from src.core.llm import get_llm
from src.core.vector_store import create_vector_store, similarity_search, make_persist_key, persist_dir_for
from src.agents.ncert.prompts import NOTES_PROMPT, CHAT_PROMPT
from src.core.config import settings

logger = logging.getLogger(__name__)

BASE = settings.ncert_data_dir

# ─────────────────────────────────────────
# SUBJECT DETECTION
# ─────────────────────────────────────────

SUBJECT_MAP = {
    "history": ("History / Indian Heritage & Culture", "GS Paper 1"),
    "geography": ("Geography", "GS Paper 1"),
    "polity": ("Indian Polity & Constitution", "GS Paper 2"),
    "civics": ("Indian Polity & Governance", "GS Paper 2"),
    "economy": ("Indian Economy", "GS Paper 3"),
    "economics": ("Indian Economy", "GS Paper 3"),
    "science": ("Science & Technology", "GS Paper 3"),
    "biology": ("Science & Technology / Environment", "GS Paper 3"),
    "physics": ("Science & Technology", "GS Paper 3"),
    "chemistry": ("Science & Technology", "GS Paper 3"),
    "environment": ("Environment & Ecology", "GS Paper 3"),
    "sociology": ("Indian Society", "GS Paper 1"),
    "political": ("Indian Polity & Governance", "GS Paper 2"),
    "social": ("Indian Society & Social Issues", "GS Paper 1"),
}


def detect_subject_area(subject: str, class_name: str = "") -> tuple[str, str]:
    """Detect UPSC subject area from NCERT subject name."""
    key = subject.lower().strip()
    best_match = None
    best_len = 0
    for k, v in SUBJECT_MAP.items():
        if k in key and len(k) > best_len:
            best_match = v
            best_len = len(k)
    return best_match or ("General Studies", "Check UPSC Syllabus")


# ─────────────────────────────────────────
# DROPDOWN HELPERS
# ─────────────────────────────────────────

@lru_cache(maxsize=1)
def get_classes() -> list[str]:
    """Get available NCERT classes."""
    if not os.path.exists(BASE):
        logger.error(f"NCERT base directory not found: {BASE}")
        return []
    return sorted(os.listdir(BASE))


@lru_cache(maxsize=50)
def get_subjects(class_name: str) -> list[str]:
    """Get subjects for a class."""
    path = f"{BASE}/{class_name}"
    if not os.path.exists(path):
        return []
    return sorted(os.listdir(path))


@lru_cache(maxsize=200)
def get_chapters(class_name: str, subject: str) -> list[str]:
    """Get chapters for a subject."""
    path = f"{BASE}/{class_name}/{subject}"
    if not os.path.exists(path):
        return []
    return sorted(os.listdir(path))


# ─────────────────────────────────────────
# PDF READING
# ─────────────────────────────────────────

def read_chapter_pdf(class_name: str, subject: str, chapter: str) -> tuple[str, str]:
    """Read chapter PDF and return text + path."""
    path = f"{BASE}/{class_name}/{subject}/{chapter}"
    if not os.path.exists(path):
        raise FileNotFoundError(f"PDF not found: {path}")
    
    pdf = PdfReader(path)
    text = ""
    for page in pdf.pages:
        extracted = page.extract_text()
        if extracted:
            text += extracted + "\n"
    
    if not text.strip():
        raise ValueError(
            "Could not extract text from this PDF.\n"
            "The file may be scanned/image-based. Only text-based PDFs are supported."
        )
    
    logger.info(f"PDF read: {class_name}/{subject}/{chapter} — {len(text)} chars")
    return text, path


# ─────────────────────────────────────────
# STUDY SESSION
# ─────────────────────────────────────────

def generate_study_session(class_name: str, subject: str, chapter: str) -> dict:
    """Generate complete study session with notes, mindmap, questions."""
    
    # Read PDF
    text, path = read_chapter_pdf(class_name, subject, chapter)
    
    # Detect subject area
    subject_area, paper = detect_subject_area(subject, class_name)
    
    # Smart truncation for notes
    max_chars = 14000
    if len(text) > max_chars:
        mid_start = len(text) // 2 - 1000
        text_for_notes = (
            text[:8000] +
            "\n\n[...]\n\n" +
            text[mid_start:mid_start + 2000] +
            "\n\n[...]\n\n" +
            text[-2000:]
        )
    else:
        text_for_notes = text
    
    # Generate notes
    try:
        chain = NOTES_PROMPT | get_llm()
        res = chain.invoke({
            "text": text_for_notes,
            "class_name": class_name,
            "subject": subject,
            "subject_area": subject_area,
            "paper": paper,
        })
        notes = res.content.strip()
    except Exception as e:
        logger.error(f"Notes generation failed: {e}")
        notes = "⚠️ Notes generation failed. Please retry."
    
    # Create vector store for chat
    key = make_persist_key("ncert", class_name, subject, chapter)
    create_vector_store(text, persist_key=key)
    
    # Generate study aids (skip when notes failed)
    if notes and "Notes generation failed" not in notes:
        from src.core.study_aids import generate_study_aids
        mindmap_html, questions_html = generate_study_aids(text_for_notes, subject, paper)
    else:
        mindmap_html, questions_html = "", ""

    return {
        "notes": notes,
        "mindmap_html": mindmap_html,
        "questions_html": questions_html,
        "chapter_path": path,
    }


# ─────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────

def ask_ncert(
    question: str,
    class_name: str,
    subject: str,
    chapter: str,
    chat_history: list | None = None,
):
    """Chat about NCERT chapter (streaming)."""
    if not question or not question.strip():
        yield "Please ask a specific question about the chapter."
        return
    
    # Load vector store
    key = make_persist_key("ncert", class_name, subject, chapter)
    from src.core.vector_store import get_embeddings
    from langchain_chroma import Chroma
    from src.core.config import settings
    
    persist_dir = persist_dir_for(key)
    if not os.path.exists(persist_dir):
        yield "Please generate study session first before chatting."
        return
    
    db = Chroma(
        persist_directory=persist_dir,
        embedding_function=get_embeddings(),
    )
    
    ctx = similarity_search(db, question.strip(), k=5, label="ncert")
    if not ctx:
        yield "Could not find relevant content in this chapter. Try rephrasing your question."
        return
    
    subject_area, paper = detect_subject_area(subject, class_name)
    
    try:
        chain = CHAT_PROMPT | get_llm()
        for chunk in chain.stream({
            "ctx": ctx,
            "q": question.strip(),
            "class_name": class_name,
            "subject": subject,
            "subject_area": subject_area,
            "paper": paper,
        }):
            if hasattr(chunk, "content"):
                yield chunk.content
    except Exception as e:
        logger.error(f"NCERT chat failed: {e}")
        yield "⚠️ Could not process your question. Please try again."
