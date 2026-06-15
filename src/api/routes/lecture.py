"""
Lecture routes - YouTube lecture processing
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from src.models.schemas import (
    LectureRequest, LectureResponse, LectureChatRequest
)
from src.agents.lecture.graph import (
    process_lecture, ask_lecture, extract_video_id
)

router = APIRouter(prefix="/lecture", tags=["Lecture"])


@router.post("/process", response_model=LectureResponse)
async def process(request: LectureRequest):
    """Process YouTube lecture and generate notes."""
    try:
        video_id = extract_video_id(request.youtube_url)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        result = process_lecture(request.youtube_url, request.medium)
        return {
            "notes": result["notes"],
            "topic_info": result["topic_info"],
            "video_id": video_id,
            "mindmap_html": result.get("mindmap_html", ""),
            "questions_html": result.get("questions_html", ""),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/chat")
async def chat(request: LectureChatRequest):
    """Chat about lecture (streaming)."""
    def generate():
        for chunk in ask_lecture(
            question=request.question,
            video_id=request.video_id,
            topic_info=request.topic_info,
            chat_history=[m.model_dump() for m in request.chat_history] if request.chat_history else None,
        ):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/chat/sync")
async def chat_sync(request: LectureChatRequest):
    """Chat about lecture (non-streaming)."""
    response = ""
    for chunk in ask_lecture(
        question=request.question,
        video_id=request.video_id,
        topic_info=request.topic_info,
        chat_history=[m.model_dump() for m in request.chat_history] if request.chat_history else None,
    ):
        response += chunk
    return {"response": response}
