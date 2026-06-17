"""
Lecture routes - YouTube lecture processing
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import StreamingResponse

from src.models.schemas import (
    LectureRequest, LectureResponse, LectureChatRequest, LectureTextRequest
)
from src.agents.lecture.graph import (
    process_lecture, ask_lecture, extract_video_id,
    process_lecture_from_text, process_lecture_from_audio,
    build_lecture_chat_index,
)

from src.core.config import settings

router = APIRouter(prefix="/lecture", tags=["Lecture"])


@router.post("/process", response_model=LectureResponse)
async def process(request: LectureRequest, background_tasks: BackgroundTasks):
    """Process YouTube lecture and generate notes."""
    try:
        video_id = extract_video_id(request.youtube_url)
        if not video_id:
            raise HTTPException(status_code=400, detail="Invalid YouTube URL")
        
        result = process_lecture(request.youtube_url, request.medium)
        # Index for chat AFTER the notes response is sent, so a heavy/failing
        # vector step can never drop the notes response ("Failed to fetch").
        background_tasks.add_task(
            build_lecture_chat_index, result["video_id"], result.get("_transcript", "")
        )
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


@router.post("/process-text", response_model=LectureResponse)
async def process_text(request: LectureTextRequest, background_tasks: BackgroundTasks):
    """Build lecture notes from a user-pasted transcript (no YouTube fetch)."""
    try:
        result = process_lecture_from_text(request.transcript, request.medium)
        background_tasks.add_task(
            build_lecture_chat_index, result["video_id"], result.get("_transcript", "")
        )
        return {
            "notes": result["notes"],
            "topic_info": result["topic_info"],
            "video_id": result["video_id"],
            "mindmap_html": result.get("mindmap_html", ""),
            "questions_html": result.get("questions_html", ""),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.post("/process-audio", response_model=LectureResponse)
async def process_audio(background_tasks: BackgroundTasks, file: UploadFile = File(...), medium: str = Form("English")):
    """Transcribe an uploaded audio file (Groq Whisper) and build notes.

    Works for caption-less lectures and videos the server is blocked from.
    """
    content = await file.read()
    max_bytes = settings.max_upload_mb * 1024 * 1024
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Audio file too large. Maximum allowed size is {settings.max_upload_mb} MB. Try a shorter clip or paste the transcript.",
        )
    try:
        result = process_lecture_from_audio(content, file.filename or "audio.mp3", medium)
        background_tasks.add_task(
            build_lecture_chat_index, result["video_id"], result.get("_transcript", "")
        )
        return {
            "notes": result["notes"],
            "topic_info": result["topic_info"],
            "video_id": result["video_id"],
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
