from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.evaluator import evaluate_mains_answer
from app.models import MainsEvaluation, User
from app.rag import draft_mains_answer, normalize_paper
from app.schemas import (
    MainsDraftRequest,
    MainsDraftResponse,
    MainsEvaluateRequest,
    MainsEvaluateResponse,
)

router = APIRouter(prefix="/mains", tags=["mains"])


@router.post("/draft", response_model=MainsDraftResponse)
def draft_answer(
    request: MainsDraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        answer, _sources, structure = draft_mains_answer(
            question=request.question,
            paper=request.paper,
            word_limit=request.word_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return MainsDraftResponse(
        answer=answer,
        paper=normalize_paper(request.paper),
        word_limit=request.word_limit,
        structure=structure,
    )


@router.post(
    "/evaluate",
    response_model=MainsEvaluateResponse,
)
def evaluate_answer(
    request: MainsEvaluateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        evaluation = evaluate_mains_answer(
            question=request.question,
            answer=request.answer,
            paper=normalize_paper(request.paper),
            word_limit=request.word_limit,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    record = MainsEvaluation(
        user_id=user.id,
        question=request.question,
        paper=normalize_paper(request.paper),
        word_limit=request.word_limit,
        answer=request.answer,
        evaluation=evaluation,
    )

    db.add(record)
    db.commit()

    return MainsEvaluateResponse(
        question=request.question,
        paper=normalize_paper(request.paper),
        word_limit=request.word_limit,
        answer=request.answer,
        evaluation=evaluation,
    )


@router.get("/papers")
def list_papers():
    return {
        "papers": [
            {
                "id": "GS1",
                "name": "GS1 - Indian Heritage & Culture, History, Geography",
                "description": "Indian Heritage & Culture, History, Geography of the World & Society",
            },
            {
                "id": "GS2",
                "name": "GS2 - Governance, Constitution, Polity, Social Justice, IR",
                "description": "Governance, Constitution, Polity, Social Justice, International Relations",
            },
            {
                "id": "GS3",
                "name": "GS3 - Economy, Agriculture, Environment, S&T, Security",
                "description": "Technology, Economic Development, Bio-diversity, Environment, Security, Disaster Management",
            },
            {
                "id": "GS4",
                "name": "GS4 - Ethics, Integrity, Aptitude",
                "description": "Ethics, Integrity, Aptitude",
            },
            {
                "id": "ESSAY",
                "name": "Essay Paper",
                "description": "Essay writing on philosophical, social, economic, political topics",
            },
            {
                "id": "OPTIONAL",
                "name": "Optional Subject",
                "description": "Optional subject specific answers",
            },
        ]
    }
