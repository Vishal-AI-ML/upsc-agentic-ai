"""
PYQ routes - Question generation and practice
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse

from src.api.deps import get_current_user
from src.agents.lecture.graph import extract_video_id
from src.models.schemas import (
    QuestionGenRequest, ParseRequest, ParseResponse,
    HintRequest, ExplanationRequest, TopicSuggestionsResponse,
    BankGenRequest, BankUploadResponse, BankStatusResponse,
    LectureQuestionRequest,
)
from src.agents.pyq.graph import (
    generate_questions, parse_questions,
    get_hint, get_explanation, get_topic_suggestions,
    build_question_bank, generate_from_bank, get_bank_status, clear_bank,
    generate_from_lecture,
)

router = APIRouter(prefix="/pyq", tags=["PYQ"])


@router.post("/generate")
async def generate(request: QuestionGenRequest):
    """Generate practice questions (streaming)."""
    def gen():
        for chunk in generate_questions(
            topic=request.topic,
            question_type=request.question_type,
            difficulty=request.difficulty,
            num_questions=request.num_questions,
            marks=request.marks,
        ):
            yield chunk
    
    return StreamingResponse(gen(), media_type="text/plain")


@router.post("/generate/sync")
async def generate_sync(request: QuestionGenRequest):
    """Generate practice questions (non-streaming)."""
    response = ""
    for chunk in generate_questions(
        topic=request.topic,
        question_type=request.question_type,
        difficulty=request.difficulty,
        num_questions=request.num_questions,
        marks=request.marks,
    ):
        response += chunk
    return {"response": response}


@router.post("/parse", response_model=ParseResponse)
async def parse(request: ParseRequest):
    """Parse pasted question text."""
    questions = parse_questions(request.text)
    return {"questions": questions}


@router.post("/hint")
async def hint(request: HintRequest):
    """Get hint for MCQ (streaming)."""
    def gen():
        for chunk in get_hint(request.question, request.options):
            yield chunk
    
    return StreamingResponse(gen(), media_type="text/plain")


@router.post("/hint/sync")
async def hint_sync(request: HintRequest):
    """Get hint for MCQ (non-streaming)."""
    response = ""
    for chunk in get_hint(request.question, request.options):
        response += chunk
    return {"response": response}


@router.post("/explain")
async def explain(request: ExplanationRequest):
    """Get explanation for MCQ (streaming)."""
    def gen():
        for chunk in get_explanation(request.question, request.options, request.answer):
            yield chunk
    
    return StreamingResponse(gen(), media_type="text/plain")


@router.post("/explain/sync")
async def explain_sync(request: ExplanationRequest):
    """Get explanation for MCQ (non-streaming)."""
    response = ""
    for chunk in get_explanation(request.question, request.options, request.answer):
        response += chunk
    return {"response": response}


@router.get("/topics/{question_type}", response_model=TopicSuggestionsResponse)
async def topics(question_type: str = "mcq"):
    """Get topic suggestions."""
    return {"topics": get_topic_suggestions(question_type)}


# ─────────────────────────────────────────
# PERSONAL PYQ BANK (per-user, grounded on uploaded papers)
# ─────────────────────────────────────────

@router.post("/bank/upload", response_model=BankUploadResponse)
async def bank_upload(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """Upload a PYQ PDF into the user's personal grounded question bank."""
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")
    try:
        content = await file.read()
        result = build_question_bank(content, file.filename, current_user["id"])
        return {"success": True, **result}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bank upload failed: {str(e)}")


@router.post("/bank/generate")
async def bank_generate(
    request: BankGenRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate questions grounded on the user's own uploaded papers (streaming)."""
    def gen():
        for chunk in generate_from_bank(
            user_id=current_user["id"],
            topic=request.topic,
            question_type=request.question_type,
            num_questions=request.num_questions,
            marks=request.marks,
            difficulty=request.difficulty,
        ):
            yield chunk

    return StreamingResponse(gen(), media_type="text/plain")


@router.post("/bank/generate/sync")
async def bank_generate_sync(
    request: BankGenRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate from the user's bank (non-streaming)."""
    response = ""
    for chunk in generate_from_bank(
        user_id=current_user["id"],
        topic=request.topic,
        question_type=request.question_type,
        num_questions=request.num_questions,
        marks=request.marks,
        difficulty=request.difficulty,
    ):
        response += chunk
    return {"response": response}


@router.get("/bank/status", response_model=BankStatusResponse)
async def bank_status(current_user: dict = Depends(get_current_user)):
    """Whether the user has a personal PYQ bank yet."""
    return get_bank_status(current_user["id"])


@router.post("/bank/clear")
async def bank_clear(current_user: dict = Depends(get_current_user)):
    """Delete the user's personal PYQ bank."""
    return clear_bank(current_user["id"])


# ─────────────────────────────────────────
# LECTURE -> PRACTICE QUESTIONS (grounded on a processed YouTube lecture)
# ─────────────────────────────────────────

@router.post("/lecture/generate")
async def lecture_generate(request: LectureQuestionRequest):
    """Generate practice questions grounded on a processed YouTube lecture (streaming)."""
    vid = extract_video_id(request.youtube_url)
    if not vid:
        raise HTTPException(status_code=400, detail="Please paste a valid YouTube video URL")

    def gen():
        for chunk in generate_from_lecture(
            video_id=vid,
            topic=request.topic,
            question_type=request.question_type,
            num_questions=request.num_questions,
            marks=request.marks,
            difficulty=request.difficulty,
        ):
            yield chunk

    return StreamingResponse(gen(), media_type="text/plain")


@router.post("/lecture/generate/sync")
async def lecture_generate_sync(request: LectureQuestionRequest):
    """Generate from a lecture (non-streaming)."""
    vid = extract_video_id(request.youtube_url)
    if not vid:
        raise HTTPException(status_code=400, detail="Please paste a valid YouTube video URL")
    response = ""
    for chunk in generate_from_lecture(
        video_id=vid,
        topic=request.topic,
        question_type=request.question_type,
        num_questions=request.num_questions,
        marks=request.marks,
        difficulty=request.difficulty,
    ):
        response += chunk
    return {"response": response}
