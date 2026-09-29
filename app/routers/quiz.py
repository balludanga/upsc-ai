from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import QuizAttempt, User
from app.rag import generate_mcqs
from app.schemas import (
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizQuestion,
    QuizSubmitRequest,
    QuizSubmitResponse,
)

router = APIRouter(prefix="/quiz", tags=["quiz"])


@router.post("/generate", response_model=QuizGenerateResponse)
def generate(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    valid_questions = generate_mcqs(
        request.topic,
        request.num_questions,
    )

    if not valid_questions:
        raise HTTPException(
            status_code=422,
            detail=(
                "Couldn't generate valid questions for that topic. "
                "Try a different topic or fewer questions."
            ),
        )

    out = []

    for q in valid_questions:
        attempt = QuizAttempt(
            user_id=user.id,
            topic=request.topic,
            question=q["question"],
            options=q["options"],
            correct_option=q["correct_option"],
        )
        db.add(attempt)
        db.flush()

        out.append(
            QuizQuestion(
                id=attempt.id,
                question=attempt.question,
                options=attempt.options,
            )
        )

    db.commit()

    return QuizGenerateResponse(questions=out)


@router.post("/submit", response_model=QuizSubmitResponse)
def submit(
    request: QuizSubmitRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.id == request.quiz_attempt_id,
            QuizAttempt.user_id == user.id,
        )
        .first()
    )

    if not attempt:
        raise HTTPException(
            status_code=404,
            detail="Quiz attempt not found",
        )

    if attempt.selected_option is not None:
        raise HTTPException(
            status_code=409,
            detail="This quiz question has already been answered.",
        )

    attempt.selected_option = request.selected_option
    attempt.is_correct = (
        request.selected_option == attempt.correct_option
    )

    db.commit()

    return QuizSubmitResponse(
        correct=bool(attempt.is_correct),
        correct_option=attempt.correct_option,
    )
