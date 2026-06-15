"""
Evaluator routes - Answer evaluation
"""

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.models.schemas import (
    EvaluateRequest, MainsEvalRequest, ModelAnswerRequest
)
from src.agents.evaluator.graph import (
    evaluate_answer, evaluate_mains, get_model_answer
)

router = APIRouter(prefix="/evaluator", tags=["Evaluator"])


@router.post("/evaluate")
async def evaluate(request: EvaluateRequest):
    """Basic answer evaluation (streaming)."""
    def generate():
        for chunk in evaluate_answer(request.question, request.answer):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/evaluate/sync")
async def evaluate_sync(request: EvaluateRequest):
    """Basic answer evaluation (non-streaming)."""
    response = ""
    for chunk in evaluate_answer(request.question, request.answer):
        response += chunk
    return {"response": response}


@router.post("/mains")
async def mains_eval(request: MainsEvalRequest):
    """Mains answer evaluation (streaming)."""
    def generate():
        for chunk in evaluate_mains(
            question=request.question,
            answer=request.answer,
            marks=request.marks,
            keywords=request.keywords,
            word_limit=request.word_limit,
        ):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/mains/sync")
async def mains_eval_sync(request: MainsEvalRequest):
    """Mains answer evaluation (non-streaming)."""
    response = ""
    for chunk in evaluate_mains(
        question=request.question,
        answer=request.answer,
        marks=request.marks,
        keywords=request.keywords,
        word_limit=request.word_limit,
    ):
        response += chunk
    return {"response": response}


@router.post("/model-answer")
async def model_answer(request: ModelAnswerRequest):
    """Generate model answer (streaming)."""
    def generate():
        for chunk in get_model_answer(
            question=request.question,
            marks=request.marks,
            keywords=request.keywords,
            word_limit=request.word_limit,
        ):
            yield chunk
    
    return StreamingResponse(generate(), media_type="text/plain")


@router.post("/model-answer/sync")
async def model_answer_sync(request: ModelAnswerRequest):
    """Generate model answer (non-streaming)."""
    response = ""
    for chunk in get_model_answer(
        question=request.question,
        marks=request.marks,
        keywords=request.keywords,
        word_limit=request.word_limit,
    ):
        response += chunk
    return {"response": response}
