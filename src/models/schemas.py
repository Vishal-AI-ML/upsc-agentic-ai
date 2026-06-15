"""
Pydantic schemas for request/response models
"""

from pydantic import BaseModel, Field
from typing import Optional


# ─────────────────────────────────────────
# COMMON SCHEMAS
# ─────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    chat_history: Optional[list[ChatMessage]] = None


class ChatResponse(BaseModel):
    response: str


# ─────────────────────────────────────────
# MENTOR SCHEMAS
# ─────────────────────────────────────────

class StudentContext(BaseModel):
    name: Optional[str] = None
    optional: Optional[str] = None
    stage: Optional[str] = None
    weak_areas: Optional[str] = None
    strong_areas: Optional[str] = None
    target_year: Optional[int] = None
    study_hours: Optional[int] = None
    attempts: Optional[int] = None


class MentorRequest(BaseModel):
    question: str = Field(..., min_length=1)
    student_context: Optional[StudentContext] = None
    chat_history: Optional[list[ChatMessage]] = None


class MentorResponse(BaseModel):
    response: str
    intent: Optional[str] = None


# ─────────────────────────────────────────
# PLANNER SCHEMAS
# ─────────────────────────────────────────

class PlannerRequest(BaseModel):
    goal: str = Field(..., description="e.g., 'UPSC 2026'")
    hours: str = Field(default="6", description="Daily study hours")
    optional: Optional[str] = Field(default="Not decided")
    weak: Optional[str] = Field(default="Not specified")
    attempt_number: Optional[str] = Field(default="1")


class PlannerResponse(BaseModel):
    plan: str


# ─────────────────────────────────────────
# NCERT SCHEMAS
# ─────────────────────────────────────────

class NCERTSessionRequest(BaseModel):
    class_name: str
    subject: str
    chapter: str


class NCERTSessionResponse(BaseModel):
    notes: str
    mindmap_html: Optional[str] = ""
    questions_html: Optional[str] = ""
    chapter_path: str


class NCERTChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    class_name: str
    subject: str
    chapter: str
    chat_history: Optional[list[ChatMessage]] = None


class NCERTListResponse(BaseModel):
    items: list[str]


# ─────────────────────────────────────────
# LECTURE SCHEMAS
# ─────────────────────────────────────────

class LectureRequest(BaseModel):
    youtube_url: str = Field(..., description="YouTube video URL")
    medium: str = Field("English", description="Notes output language: English / Hindi / Hinglish")


class LectureResponse(BaseModel):
    notes: str
    topic_info: dict
    video_id: str
    mindmap_html: Optional[str] = ""
    questions_html: Optional[str] = ""


class LectureChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    video_id: str
    topic_info: Optional[dict] = None
    chat_history: Optional[list[ChatMessage]] = None


# ─────────────────────────────────────────
# CURRENT AFFAIRS SCHEMAS
# ─────────────────────────────────────────

class DailyCARequest(BaseModel):
    date: str = Field(..., description="Date in 'DD Month YYYY' format")


class EditorialRequest(BaseModel):
    topic: str


class MonthlyRequest(BaseModel):
    month: str
    year: str


class EditorialTopicsResponse(BaseModel):
    topics: list[str]


class AvailableDatesResponse(BaseModel):
    dates: list[str]


class AvailableMonthsResponse(BaseModel):
    months: list[tuple[str, str]]


# ─────────────────────────────────────────
# UPLOAD SCHEMAS
# ─────────────────────────────────────────

class UploadResponse(BaseModel):
    success: bool
    filename: str
    hash: str
    book_info: dict
    notes: str


class UploadChatRequest(BaseModel):
    question: str = Field(..., min_length=1)
    pdf_hash: str
    book_info: Optional[dict] = None
    chat_history: Optional[list[ChatMessage]] = None


# ─────────────────────────────────────────
# PYQ SCHEMAS
# ─────────────────────────────────────────

class QuestionGenRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    question_type: str = Field(default="mcq", description="'mcq' or 'mains'")
    difficulty: str = Field(default="medium", description="'easy', 'medium', 'hard'")
    num_questions: int = Field(default=5, ge=1, le=20)
    marks: int = Field(default=10, description="For mains questions")


class ParseRequest(BaseModel):
    text: str = Field(..., min_length=10)


class ParseResponse(BaseModel):
    questions: list[dict]


class HintRequest(BaseModel):
    question: str
    options: list[str]


class ExplanationRequest(BaseModel):
    question: str
    options: list[str]
    answer: str


class TopicSuggestionsResponse(BaseModel):
    topics: list[str]


# ─────────────────────────────────────────
# EVALUATOR SCHEMAS
# ─────────────────────────────────────────

class EvaluateRequest(BaseModel):
    question: str = Field(..., min_length=5)
    answer: str = Field(..., min_length=50)


class MainsEvalRequest(BaseModel):
    question: str = Field(..., min_length=5)
    answer: str = Field(..., min_length=30)
    marks: int = Field(default=10, ge=5, le=15)
    keywords: Optional[list[str]] = None
    word_limit: int = Field(default=150)


class ModelAnswerRequest(BaseModel):
    question: str = Field(..., min_length=5)
    marks: int = Field(default=10)
    keywords: Optional[list[str]] = None
    word_limit: int = Field(default=150)


# ─────────────────────────────────────────
# PYQ BANK SCHEMAS (personal, grounded on user-uploaded papers)
# ─────────────────────────────────────────

class BankGenRequest(BaseModel):
    topic: str = Field(default="", description="Topic to focus on; empty = mixed from the bank")
    question_type: str = Field(default="mcq", description="'mcq' or 'mains'")
    num_questions: int = Field(default=5, ge=1, le=20)
    marks: int = Field(default=10)
    difficulty: str = Field(default="medium")


class BankUploadResponse(BaseModel):
    success: bool
    filename: str
    hash: str
    chunks: int
    approx_questions: int


class BankStatusResponse(BaseModel):
    exists: bool


class LectureQuestionRequest(BaseModel):
    youtube_url: str = Field(..., min_length=5)
    topic: str = Field(default="")
    question_type: str = Field(default="mcq", description="'mcq' or 'mains'")
    num_questions: int = Field(default=5, ge=1, le=20)
    marks: int = Field(default=10)
    difficulty: str = Field(default="medium")
