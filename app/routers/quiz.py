from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import (
    PrelimsQuestion,
    PrelimsQuestionLevel,
    QuizAttempt,
    User,
)
from app.prelims_bank import assemble_question_ids
from app.schemas import (
    QuizCatalogResponse,
    QuizGenerateRequest,
    QuizGenerateResponse,
    QuizQuestion,
    QuizPracticeQuestion,
    QuizReviewItem,
    QuizReviewRequest,
    QuizReviewResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
    QuizSubjectOut,
    QuizTopicOut,
)

router = APIRouter(prefix="/quiz", tags=["quiz"])


def _get_practice_question(
    db: Session,
    target_difficulty: int,
    excluded_ids: list[int],
) -> tuple[PrelimsQuestion, int] | None:
    difficulty = func.coalesce(PrelimsQuestionLevel.difficulty, 2)
    query = (
        db.query(PrelimsQuestion, difficulty.label("difficulty"))
        .outerjoin(
            PrelimsQuestionLevel,
            PrelimsQuestionLevel.question_id == PrelimsQuestion.id,
        )
        .filter(PrelimsQuestion.correct_option.isnot(None))
    )
    if excluded_ids:
        query = query.filter(~PrelimsQuestion.id.in_(excluded_ids))

    selected = (
        query.order_by(
            func.abs(difficulty - target_difficulty),
            func.random(),
        )
        .first()
    )
    if selected is None:
        return None
    return selected[0], int(selected[1])


@router.get("/practice/next", response_model=QuizPracticeQuestion)
def next_practice_question(
    target_difficulty: int = Query(default=2, ge=1, le=3),
    exclude: list[int] = Query(default=[]),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    selected = _get_practice_question(db, target_difficulty, exclude)
    if selected is None:
        raise HTTPException(
            status_code=404,
            detail="You have explored all available questions. Start a fresh practice round.",
        )

    question, difficulty = selected
    attempt = QuizAttempt(
        user_id=user.id,
        topic=question.topic,
        question=question.question,
        options=question.options,
        correct_option=question.correct_option,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return QuizPracticeQuestion(
        id=attempt.id,
        question=question.question,
        options=question.options,
        year=question.year,
        subject=question.subject,
        topic=question.topic,
        source=question.source,
        source_url=question.source_url,
        difficulty=difficulty,
        bank_id=question.id,
    )


@router.get("/catalog", response_model=QuizCatalogResponse)
def catalog(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(
            PrelimsQuestion.subject,
            PrelimsQuestion.topic,
            func.count(PrelimsQuestion.id),
        )
        .filter(PrelimsQuestion.correct_option.isnot(None))
        .group_by(PrelimsQuestion.subject, PrelimsQuestion.topic)
        .order_by(PrelimsQuestion.subject, PrelimsQuestion.topic)
        .all()
    )
    counts: dict[str, dict[str, int]] = defaultdict(dict)
    for subject, topic, count in rows:
        counts[subject][topic] = int(count)

    subjects = [
        QuizSubjectOut(
            name=subject,
            question_count=sum(topic_counts.values()),
            topics=[
                QuizTopicOut(name=topic, question_count=count)
                for topic, count in sorted(topic_counts.items())
            ],
        )
        for subject, topic_counts in sorted(counts.items())
    ]
    return QuizCatalogResponse(subjects=subjects)


@router.post("/generate", response_model=QuizGenerateResponse)
def generate(
    request: QuizGenerateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(PrelimsQuestion).filter(
        PrelimsQuestion.correct_option.isnot(None)
    )
    if request.subject:
        query = query.filter(PrelimsQuestion.subject == request.subject)
    if request.topic:
        query = query.filter(PrelimsQuestion.topic == request.topic)

    candidates = (
        query.order_by(PrelimsQuestion.year.desc(), PrelimsQuestion.question_number)
        .limit(100)
        .all()
    )
    if not candidates:
        raise HTTPException(
            status_code=404,
            detail="No answer-keyed questions are available for this subject and topic yet.",
        )

    selected_ids = assemble_question_ids(
        topic=request.topic,
        subject=request.subject,
        questions=candidates,
        count=request.num_questions,
    )
    questions_by_id = {question.id: question for question in candidates}
    difficulty_rows = dict(
        db.query(
            PrelimsQuestionLevel.question_id,
            PrelimsQuestionLevel.difficulty,
        )
        .filter(
            PrelimsQuestionLevel.question_id.in_(questions_by_id)
        )
        .all()
    )
    out = []

    for question_id in selected_ids:
        question = questions_by_id[question_id]
        attempt = QuizAttempt(
            user_id=user.id,
            topic=question.topic,
            question=question.question,
            options=question.options,
            correct_option=question.correct_option,
        )
        db.add(attempt)
        db.flush()

        out.append(
            QuizQuestion(
                id=attempt.id,
                question=attempt.question,
                options=attempt.options,
                year=question.year,
                subject=question.subject,
                topic=question.topic,
                source=question.source,
                source_url=question.source_url,
                difficulty=difficulty_rows.get(question.id, 2),
                bank_id=question.id,
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
        selected_option=attempt.selected_option,
    )


@router.post("/review", response_model=QuizReviewResponse)
def review(
    request: QuizReviewRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    attempt_ids = list(dict.fromkeys(request.attempt_ids))
    attempts = (
        db.query(QuizAttempt)
        .filter(
            QuizAttempt.user_id == user.id,
            QuizAttempt.id.in_(attempt_ids),
        )
        .all()
    )
    attempts_by_id = {attempt.id: attempt for attempt in attempts}
    if len(attempts_by_id) != len(attempt_ids):
        raise HTTPException(
            status_code=404,
            detail="One or more quiz attempts were not found.",
        )

    return QuizReviewResponse(
        answers=[
            QuizReviewItem(
                attempt_id=attempt_id,
                correct_option=attempts_by_id[attempt_id].correct_option,
            )
            for attempt_id in attempt_ids
        ]
    )
