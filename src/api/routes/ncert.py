"""
NCERT routes - Study sessions and chat
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.models.schemas import (
    NCERTSessionRequest, NCERTSessionResponse,
    NCERTChatRequest, NCERTListResponse
)
from src.agents.ncert.graph import (
    get_classes, get_subjects, get_chapters,
    generate_study_session, ask_ncert
)

router = APIRouter(prefix="/ncert", tags=["NCERT"])


@router.get("/classes", response_model=NCERTListResponse)
async def list_classes():
    """Get available NCERT classes."""
    return {"items": get_classes()}


@router.get("/subjects/{class_name}", response_model=NCERTListResponse)
async def list_subjects(class_name: str):
    """Get subjects for a class."""
    subjects = get_subjects(class_name)
    if not subjects:
        raise HTTPException(status_code=404, detail=f"Class '{class_name}' not found")
    return {"items": subjects}


@router.get("/chapters/{class_name}/{subject}", response_model=NCERTListResponse)
async def list_chapters(class_name: str, subject: str):
    """Get chapters for a subject."""
    chapters = get_chapters(class_name, subject)
    if not chapters:
        raise HTTPException(status_code=404, detail=f"Subject '{subject}' not found")
    return {"items": chapters}


@router.post("/study", response_model=NCERTSessionResponse)
async def create_study_session(request: NCERTSessionRequest):
    """Generate study session with notes."""
    try:
        result = generate_study_session(
            class_name=request.class_name,
            subject=request.subject,
            chapter=request.chapter,
        )
        return result
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed: {str(e)}")


@router.post("/chat")
async def chat_ncert(request: NCERTChatRequest):
    """Chat about NCERT chapter (streaming)."""
    def generate():
        for chunk in ask_ncert(
            question=request.question,
            class_name=request.class_name,
            subject=request.subject,
            chapter=request.chapter,
            chat_history=[m.model_dump() for m in request.chat_history] if request.chat_history else None,
        ):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/chat/sync")
async def chat_ncert_sync(request: NCERTChatRequest):
    """Chat about NCERT chapter (non-streaming)."""
    response = ""
    for chunk in ask_ncert(
        question=request.question,
        class_name=request.class_name,
        subject=request.subject,
        chapter=request.chapter,
        chat_history=[m.model_dump() for m in request.chat_history] if request.chat_history else None,
    ):
        response += chunk
    return {"response": response}
