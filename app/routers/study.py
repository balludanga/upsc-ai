from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models import QuizAttempt, StudySession, User
from app.schemas import (
    StudyDashboard,
    StudyPlanItem,
    StudyPlanResponse,
    StudySessionCreate,
    StudySessionOut,
)

router = APIRouter(prefix="/study", tags=["study"])


@router.post("/sessions", response_model=StudySessionOut)
def log_session(
    request: StudySessionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = StudySession(user_id=user.id, **request.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return StudySessionOut(
        **request.model_dump(), id=session.id, created_at=session.created_at.isoformat()
    )


@router.get("/plan", response_model=StudyPlanResponse)
def today_plan(user: User = Depends(get_current_user)):
    items = [
        StudyPlanItem(topic="Current affairs", mode="revise", minutes=30, reason="Build daily continuity"),
        StudyPlanItem(topic="Weakest quiz topic", mode="active recall", minutes=35, reason="Improve your lowest-confidence area"),
        StudyPlanItem(topic="Optional GS topic", mode="mains answer", minutes=25, reason="Practice structured writing"),
    ]
    return StudyPlanResponse(date=date.today().isoformat(), total_minutes=90, items=items)


@router.get("/dashboard", response_model=StudyDashboard)
def dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sessions = db.query(StudySession).filter(StudySession.user_id == user.id).all()
    attempts = db.query(QuizAttempt).filter(QuizAttempt.user_id == user.id).all()
    answered = [attempt for attempt in attempts if attempt.is_correct is not None]
    topic_scores = Counter()
    topic_totals = Counter()
    for attempt in answered:
        topic_totals[attempt.topic] += 1
        if attempt.is_correct:
            topic_scores[attempt.topic] += 1
    weak_topics = [topic for topic, _ in sorted(topic_totals.items(), key=lambda item: (topic_scores[item[0]] / item[1], -item[1]))[:3]]

    study_dates = {session.created_at.date() for session in sessions}
    streak = 0
    day = date.today()
    while day in study_dates:
        streak += 1
        day -= timedelta(days=1)

    today_minutes = sum(session.minutes for session in sessions if session.created_at.date() == date.today())
    accuracy = (sum(attempt.is_correct for attempt in answered) / len(answered) * 100) if answered else 0
    return StudyDashboard(
        today_minutes=today_minutes,
        total_minutes=sum(session.minutes for session in sessions),
        current_streak_days=streak,
        quizzes_attempted=len(answered),
        quiz_accuracy_percent=round(accuracy, 1),
        weak_topics=weak_topics,
    )