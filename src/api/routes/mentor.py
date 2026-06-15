"""
Mentor routes - UPSC guidance and Q&A
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.models.schemas import MentorRequest, MentorResponse
from src.agents.mentor.graph import mentor_reply, detect_intent

router = APIRouter(prefix="/mentor", tags=["Mentor"])


@router.post("/chat")
async def chat(request: MentorRequest):
    """Chat with mentor (streaming)."""
    def generate():
        for chunk in mentor_reply(
            question=request.question,
            student_context=request.student_context.model_dump() if request.student_context else None,
            chat_history=[m.model_dump() for m in request.chat_history] if request.chat_history else None,
        ):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/chat/sync", response_model=MentorResponse)
async def chat_sync(request: MentorRequest):
    """Chat with mentor (non-streaming)."""
    intent = detect_intent(request.question)
    response = ""
    for chunk in mentor_reply(
        question=request.question,
        student_context=request.student_context.model_dump() if request.student_context else None,
        chat_history=[m.model_dump() for m in request.chat_history] if request.chat_history else None,
    ):
        response += chunk
    return {"response": response, "intent": intent}
