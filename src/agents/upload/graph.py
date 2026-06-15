"""
Upload Agent - PDF processing, book detection, notes, RAG chat
"""

import os
import hashlib
import logging
from functools import lru_cache

from pypdf import PdfReader

from src.core.llm import get_llm
from src.core.vector_store import create_vector_store, similarity_search, make_persist_key, persist_dir_for
from src.agents.upload.prompts import (
    BOOK_DETECTION_PROMPT, NOTES_PROMPT, CHAT_PROMPT
)

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────
# PDF HASH CACHE — avoid reprocessing
# ─────────────────────────────────────────

_processed_cache: dict[str, dict] = {}


def _compute_hash(content: bytes) -> str:
    """Compute MD5 hash of PDF content."""
    return hashlib.md5(content).hexdigest()


# ─────────────────────────────────────────
# PDF READING
# ─────────────────────────────────────────

def extract_pdf_text(file_content: bytes, filename: str) -> tuple[str, str]:
    """Extract text from PDF bytes. Returns (text, hash)."""
    pdf_hash = _compute_hash(file_content)
    
    # Check cache
    if pdf_hash in _processed_cache:
        logger.info(f"Cache hit for {filename}")
        return _processed_cache[pdf_hash]["text"], pdf_hash
    
    try:
        import io
        pdf = PdfReader(io.BytesIO(file_content))
        text = ""
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"
        
        if not text.strip():
            raise ValueError(
                "📄 We couldn’t read any text from this PDF — it looks "
                "like a scanned or image-based document. Please upload a "
                "text-based PDF (one where you can select and copy the text)."
            )
        
        logger.info(f"PDF extracted: {filename} — {len(text)} chars")
        return text, pdf_hash
    
    except ValueError:
        raise
    except Exception as e:
        logger.error(f"PDF extraction failed: {e}")
        raise ValueError(
            "📄 We couldn’t open this PDF. The file may be corrupted "
            "or password-protected. Please try a different file."
        )


# ─────────────────────────────────────────
# BOOK DETECTION
# ─────────────────────────────────────────

def detect_book(text: str) -> dict:
    """Detect if PDF is a known UPSC book."""
    try:
        chain = BOOK_DETECTION_PROMPT | get_llm()
        res = chain.invoke({"text": text[:2000]}).content
        
        result = {
            "book": "Unknown",
            "author": "Unknown",
            "subject": "General",
            "paper": "Check Syllabus",
            "confidence": "Low",
            "relevant": True,
        }
        
        for line in res.strip().split("\n"):
            line = line.lstrip("*-#> ").replace("**", "").strip()
            if line.startswith("BOOK:"):
                result["book"] = line.replace("BOOK:", "").strip()
            elif line.startswith("AUTHOR:"):
                result["author"] = line.replace("AUTHOR:", "").strip()
            elif line.startswith("SUBJECT:"):
                result["subject"] = line.replace("SUBJECT:", "").strip()
            elif line.startswith("UPSC_PAPER:"):
                result["paper"] = line.replace("UPSC_PAPER:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                result["confidence"] = line.replace("CONFIDENCE:", "").strip()
            elif line.startswith("RELEVANT:"):
                result["relevant"] = "no" not in line.replace("RELEVANT:", "").strip().lower()
        
        return result
    
    except Exception as e:
        logger.error(f"Book detection failed: {e}")
        return {
            "book": "Unknown",
            "author": "Unknown",
            "subject": "General",
            "paper": "Check Syllabus",
            "confidence": "Low",
            "relevant": True,
        }


# ─────────────────────────────────────────
# MAIN PROCESSING
# ─────────────────────────────────────────

def process_upload(file_content: bytes, filename: str) -> dict:
    """Process uploaded PDF and generate notes."""
    
    # Extract text
    text, pdf_hash = extract_pdf_text(file_content, filename)
    
    # Check cache for full processing
    if pdf_hash in _processed_cache and "notes" in _processed_cache[pdf_hash]:
        logger.info(f"Full cache hit for {filename}")
        return _processed_cache[pdf_hash]
    
    # Detect book
    book_info = detect_book(text)
    logger.info(f"Book detected: {book_info['book']} ({book_info['confidence']})")

    # Relevance gate - refuse non-UPSC documents (resume / invoice / novel / random files)
    if not book_info.get("relevant", True):
        raise ValueError(
            "📄 This document doesn’t look like study material (it appears to be a personal or unrelated file). Please upload exam notes, books, notifications, or other study-related PDFs."
        )
    
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
        notes = chain.invoke({
            "text": text_for_notes,
            "book_name": book_info["book"],
            "subject": book_info["subject"],
            "paper": book_info["paper"],
        }).content
    except Exception as e:
        logger.error(f"Notes generation failed: {e}")
        notes = "⚠️ Notes generation failed. Please retry."

    if notes and not notes.startswith("⚠️"):
        notes = "> ⚠️ AI-generated notes - cross-check key facts, dates, and names with a standard source." + chr(10) + chr(10) + notes
    
    # Create vector store for chat
    key = make_persist_key("upload", pdf_hash)
    create_vector_store(text, persist_key=key)
    
    # Cache result
    result = {
        "notes": notes,
        "book_info": book_info,
        "text": text,
        "hash": pdf_hash,
        "filename": filename,
        "mindmap_html": "",
        "questions_html": "",
    }
    _processed_cache[pdf_hash] = result
    
    return result


# ─────────────────────────────────────────
# CHAT
# ─────────────────────────────────────────

def ask_upload(
    question: str,
    pdf_hash: str,
    book_info: dict | None = None,
    chat_history: list | None = None,
):
    """Chat about uploaded PDF (streaming)."""
    if not question or not question.strip():
        yield "Please ask a specific question about the document."
        return
    
    # Load vector store
    from src.core.vector_store import get_embeddings
    from langchain_chroma import Chroma
    from src.core.config import settings
    
    key = make_persist_key("upload", pdf_hash)
    persist_dir = persist_dir_for(key)
    
    if not os.path.exists(persist_dir):
        yield "Please upload and process the PDF first."
        return
    
    db = Chroma(
        persist_directory=persist_dir,
        embedding_function=get_embeddings(),
    )
    
    ctx = similarity_search(db, question.strip(), k=5, label="upload")
    if not ctx:
        yield "Could not find relevant content. Try rephrasing your question."
        return
    
    book_name = book_info.get("book", "Uploaded Document") if book_info else "Uploaded Document"
    subject = book_info.get("subject", "General") if book_info else "General"
    paper = book_info.get("paper", "Check Syllabus") if book_info else "Check Syllabus"
    
    try:
        chain = CHAT_PROMPT | get_llm()
        for chunk in chain.stream({
            "context": ctx,
            "question": question.strip(),
            "book_name": book_name,
            "subject": subject,
            "paper": paper,
        }):
            if hasattr(chunk, "content"):
                yield chunk.content
    except Exception as e:
        logger.error(f"Upload chat failed: {e}")
        yield "⚠️ Could not process your question. Please try again."


# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────

def get_cached_upload(pdf_hash: str) -> dict | None:
    """Get cached upload data."""
    return _processed_cache.get(pdf_hash)


def clear_cache():
    """Clear upload cache."""
    global _processed_cache
    _processed_cache = {}
    logger.info("Upload cache cleared")
