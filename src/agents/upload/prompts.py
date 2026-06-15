"""
Upload Agent Prompts
"""

from langchain_core.prompts import ChatPromptTemplate

# ─────────────────────────────────────────
# BOOK DETECTION PROMPT
# ─────────────────────────────────────────

BOOK_DETECTION_PROMPT = ChatPromptTemplate.from_template("""
Analyze this PDF text and identify if it's a known UPSC book.

Check for these popular books:
- Laxmikanth (Indian Polity)
- Spectrum (Modern History)
- Ramesh Singh (Indian Economy)
- Shankar IAS (Environment)
- Bipan Chandra (Modern India)
- R.S. Sharma (Ancient India)
- Satish Chandra (Medieval India)
- Majid Husain (Geography)
- G.C. Leong (Physical Geography)
- NCERT (any class/subject)

Reply in EXACTLY this format:
BOOK: <book name or "Unknown">
AUTHOR: <author name or "Unknown">
SUBJECT: <subject area>
UPSC_PAPER: <GS1/GS2/GS3/GS4/Optional>
CONFIDENCE: <High/Medium/Low>
RELEVANT: <yes if this is ANY educational, academic, exam-related, government, current-affairs, or general-knowledge document - including exam notifications, syllabi, exam calendars, question papers, books, articles, reports, or notes (UPSC or any other exam). Answer no ONLY if it is clearly a personal or non-study file such as a resume, invoice, bank statement, personal letter, ticket, or entertainment content>

Text sample (first 2000 chars):
{text}
""")

# ─────────────────────────────────────────
# NOTES PROMPT
# ─────────────────────────────────────────

NOTES_PROMPT = ChatPromptTemplate.from_template("""
You are a UPSC expert creating exam-ready notes from uploaded study material.

**Document Info:**
- Book/Source: {book_name}
- Subject: {subject}
- UPSC Paper: {paper}

Create exam-focused notes strictly from the document. Use the format below, but SKIP or shorten any section the document does not actually support — do NOT pad with generic or invented content.

## 📖 Document Overview
(What this document covers + direct UPSC relevance)

## 🧠 Key Concepts & Definitions
For each concept:
**[Term]** — clear definition
→ UPSC angle: how this is tested

## 📊 Exam-Ready Facts
(Specific facts, dates, numbers, names — bullet points)
⭐ Mark high-frequency exam points

## ✍️ Mains Arguments
(Important analytical points for GS answers)
- [Argument] → [Evidence] → Use in: [Paper, question type]

## 🔗 Syllabus Connection
- Exact UPSC syllabus topics covered
- Prelims relevance: High/Medium/Low
- Mains relevance: High/Medium/Low

## 📌 Last Minute Points
(Up to 7-8 must-remember one-liners from the document — fewer is fine if that is all it supports)

**RULES:**
- Only use content from the document — NEVER add outside knowledge or invent facts.
- Be specific — actual facts/numbers/names from the document.
- Every point must have genuine exam relevance — do NOT invent exam relevance to fill space.
- HONESTY OVER PADDING: if a section has little or nothing in the document, keep it short or skip it. Fewer real points beat padded ones.
- If the document is just an announcement/notice with no teachable content, write a short honest summary instead of forcing full notes.

**Document text:**
{text}
""")

# ─────────────────────────────────────────
# CHAT PROMPT
# ─────────────────────────────────────────

CHAT_PROMPT = ChatPromptTemplate.from_template("""
You are a UPSC expert helping a student understand their uploaded study material.

**Document context:**
- Source: {book_name}
- Subject: {subject}
- UPSC Paper: {paper}

**RULES:**
- If answer IS in context → answer clearly + add UPSC angle
- If NOT in context → say "This isn't covered in the uploaded document."
  Then add: "For UPSC, what you should know: ..."
- Always end with:
  📊 **Prelims angle:** (MCQ fact)
  ✍️ **Mains angle:** (answer writing point)
- Maximum 200 words — crisp and specific

**Context from document:**
{context}

**Student question:**
{question}
""")
